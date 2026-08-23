"""Read-only localhost HTTP server for the operator console."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from benedict import __version__
from benedict.operator_ui.recorder import JsonlRunRecorder, NullRunRecorder

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"
MCP_PID_NAME = "mcp.pid"


class StatusMonitor:
    """Read-only snapshot of process, state, and runs."""

    def __init__(
        self,
        *,
        data_dir: Path,
        recorder,
        state_file: Path,
        workspaces_dir: Path,
        chroma_path: Path,
        started_at: datetime,
        model: str,
        copy_mode: str,
    ):
        self.data_dir = Path(data_dir)
        self.recorder = recorder
        self.state_file = Path(state_file)
        self.workspaces_dir = Path(workspaces_dir)
        self.chroma_path = Path(chroma_path)
        self.started_at = started_at
        self.model = model
        self.copy_mode = copy_mode

    def status(self) -> Dict[str, Any]:
        state_ok, channels, state_detail = self._read_state()
        chroma_ok = self.chroma_path.exists()
        mcp_ok, mcp_detail = self._mcp_status()
        return {
            "version": __version__,
            "uptime_s": int((datetime.now(timezone.utc) - self.started_at).total_seconds()),
            "data_dir": str(self.data_dir),
            "model": self.model,
            "copy_mode": self.copy_mode,
            "host": os.environ.get("BENEDICT_OPERATOR_UI_HOST", "127.0.0.1"),
            "port": int(os.environ.get("BENEDICT_OPERATOR_UI_PORT", "8765")),
            "components": {
                "slack": {"ok": True, "detail": "this process"},
                "mcp": {"ok": mcp_ok, "detail": mcp_detail},
                "chroma": {"ok": chroma_ok, "detail": str(self.chroma_path)},
                "state": {"ok": state_ok, "detail": state_detail},
            },
            "channels": channels,
            "runs_today": self.recorder.runs_today() if hasattr(self.recorder, "runs_today") else 0,
        }

    def workspaces(self) -> Dict[str, Any]:
        state_ok, _, _ = self._read_state()
        if not state_ok:
            return {"workspaces": []}
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"workspaces": []}
        channels = payload.get("channels") or {}
        architect = (payload.get("architect") or {}).get("channel_id")
        recent = []
        if hasattr(self.recorder, "list_runs"):
            recent = self.recorder.list_runs(limit=200)
        last_by_channel: Dict[str, str] = {}
        for row in recent:
            channel_id = row.get("channel_id") or ""
            if channel_id and channel_id not in last_by_channel:
                last_by_channel[channel_id] = row.get("started_at") or ""
        items = []
        for channel_id, config in channels.items():
            if not isinstance(config, dict):
                continue
            workspace_path = self.workspaces_dir / channel_id
            items.append(
                {
                    "channel_id": channel_id,
                    "repository": config.get("repo") or "",
                    "onboarded_at": config.get("onboarded_at") or "",
                    "notion": bool(config.get("notion")),
                    "architect": channel_id == architect,
                    "workspace_path": str(workspace_path),
                    "indexed": (self.chroma_path / "chroma.sqlite3").exists()
                    or self.chroma_path.exists(),
                    "last_run": last_by_channel.get(channel_id) or "",
                }
            )
        return {"workspaces": items}

    def _read_state(self) -> tuple:
        if not self.state_file.exists():
            return False, 0, f"missing {self.state_file}"
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            channels = payload.get("channels") or {}
            return True, len(channels), str(self.state_file)
        except (OSError, json.JSONDecodeError) as exc:
            return False, 0, str(exc)

    def _mcp_status(self) -> tuple:
        pid_file = self.data_dir / MCP_PID_NAME
        if not pid_file.exists():
            return False, "not running"
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            return True, f"pid {pid}"
        except (OSError, ValueError):
            return False, "not running"


def write_mcp_pid(data_dir: Path) -> Path:
    """Record the MCP process id so the Slack-side UI can show it."""
    path = Path(data_dir) / MCP_PID_NAME
    path.write_text(str(os.getpid()), encoding="utf-8")
    return path


def clear_mcp_pid(data_dir: Path) -> None:
    path = Path(data_dir) / MCP_PID_NAME
    try:
        path.unlink()
    except FileNotFoundError:
        return


class _Handler(BaseHTTPRequestHandler):
    monitor: StatusMonitor

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("operator-ui " + fmt, *args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/api/status":
                self._json(200, self.monitor.status())
                return
            if path == "/api/runs":
                limit = _int_arg(query, "limit", 50)
                source = (query.get("source") or [None])[0] or None
                status = (query.get("status") or [None])[0] or None
                runs = self.monitor.recorder.list_runs(limit=limit, source=source, status=status)
                self._json(200, {"runs": [_summary(row) for row in runs]})
                return
            if path.startswith("/api/runs/"):
                run_id = path.split("/", 3)[-1]
                row = self.monitor.recorder.get(run_id)
                if row is None:
                    self._json(404, {"error": "run not found"})
                    return
                self._json(200, row)
                return
            if path == "/api/workspaces":
                self._json(200, self.monitor.workspaces())
                return
            if path in ("/", "/index.html"):
                self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
                return
            self._json(404, {"error": "not found"})
        except Exception as exc:
            logger.warning("Operator UI request failed: %s", exc, exc_info=True)
            self._json(500, {"error": "internal error"})

    def _json(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._json(404, {"error": "ui missing"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _int_arg(query: Dict[str, list], name: str, default: int) -> int:
    raw = (query.get(name) or [None])[0]
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _summary(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "source": row.get("source"),
        "kind": row.get("kind"),
        "status": row.get("status"),
        "started_at": row.get("started_at"),
        "duration_ms": row.get("duration_ms"),
        "channel_id": row.get("channel_id"),
        "channel_name": row.get("channel_name"),
        "repo": row.get("repo"),
        "query": row.get("query"),
        "route": row.get("route"),
    }


def operator_ui_enabled() -> bool:
    raw = os.environ.get("BENEDICT_OPERATOR_UI", "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def start_operator_ui(monitor: StatusMonitor) -> Optional[ThreadingHTTPServer]:
    """Start the console in a daemon thread. Returns the server or None."""
    if not operator_ui_enabled():
        logger.info("Operator UI disabled (BENEDICT_OPERATOR_UI=0)")
        return None
    host = os.environ.get("BENEDICT_OPERATOR_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("BENEDICT_OPERATOR_UI_PORT", "8765"))
    _Handler.monitor = monitor
    try:
        server = ThreadingHTTPServer((host, port), _Handler)
    except OSError as exc:
        logger.warning("Operator UI did not start on %s:%s: %s", host, port, exc)
        return None
    thread = threading.Thread(target=server.serve_forever, name="operator-ui", daemon=True)
    thread.start()
    logger.info("Operator UI http://%s:%s", host, port)
    return server


def create_recorder(data_dir: Path) -> JsonlRunRecorder | NullRunRecorder:
    if not operator_ui_enabled():
        return NullRunRecorder()
    return JsonlRunRecorder(Path(data_dir) / "runs.jsonl")
