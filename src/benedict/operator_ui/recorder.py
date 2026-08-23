"""Append-only run log for the operator console.

Recording must never raise into Slack or MCP handlers.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_DETAIL_BYTES = 32 * 1024
MAX_RUNS = 2000
_current: ContextVar[Optional["ActiveRun"]] = ContextVar("benedict_run", default=None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _new_id() -> str:
    return uuid.uuid4().hex[:12].upper()


def _truncate(value: Any) -> Any:
    """Keep JSON payloads under MAX_DETAIL_BYTES."""
    try:
        raw = json.dumps(value, default=str)
    except (TypeError, ValueError):
        raw = str(value)
    if len(raw.encode("utf-8")) <= MAX_DETAIL_BYTES:
        return value
    if isinstance(value, str):
        return {"truncated": True, "preview": value[:8000]}
    if isinstance(value, dict):
        return {"truncated": True, "keys": list(value.keys())[:40]}
    if isinstance(value, list):
        return {"truncated": True, "n": len(value), "preview": value[:5]}
    return {"truncated": True, "preview": raw[:8000]}


def current_run() -> Optional["ActiveRun"]:
    return _current.get()


def record_stage(
    name: str,
    *,
    status: str = "ok",
    duration_ms: int = 0,
    label: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    child: bool = False,
) -> None:
    """Add a stage to the current run, if any."""
    run = current_run()
    if run is None:
        return
    run.add_stage(
        name,
        status=status,
        duration_ms=duration_ms,
        label=label,
        detail=detail,
        child=child,
    )


class ActiveRun:
    """One inbound event currently being recorded."""

    def __init__(self, recorder: "JsonlRunRecorder", fields: Dict[str, Any]):
        self._recorder = recorder
        self._done = False
        self._t0 = time.perf_counter()
        self.data: Dict[str, Any] = {
            "id": fields.get("id") or _new_id(),
            "source": fields.get("source") or "slack",
            "kind": fields.get("kind") or "conversation",
            "status": "running",
            "started_at": fields.get("started_at") or _utc_now(),
            "ended_at": None,
            "duration_ms": None,
            "channel_id": fields.get("channel_id") or "",
            "channel_name": fields.get("channel_name") or "",
            "user_id": fields.get("user_id") or "",
            "repo": fields.get("repo") or "",
            "thread_ts": fields.get("thread_ts") or "",
            "query": fields.get("query") or "",
            "route": fields.get("route") or "",
            "reply": None,
            "error": None,
            "stages": [],
        }

    @property
    def id(self) -> str:
        return self.data["id"]

    def set(self, **fields: Any) -> None:
        try:
            for key, value in fields.items():
                if key in self.data and key != "stages":
                    self.data[key] = value
            self._recorder.touch(self)
        except Exception:
            logger.warning("Failed to update run %s", self.id, exc_info=True)

    def add_stage(
        self,
        name: str,
        *,
        status: str = "ok",
        duration_ms: int = 0,
        label: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        child: bool = False,
    ) -> None:
        try:
            stage = {
                "name": name,
                "status": status,
                "duration_ms": int(duration_ms),
                "label": label or name,
                "child": child,
            }
            if detail is not None:
                stage["detail"] = _truncate(detail)
            self.data["stages"].append(stage)
            self._recorder.touch(self)
        except Exception:
            logger.warning("Failed to add stage %s on run %s", name, self.id, exc_info=True)

    def finish(
        self,
        *,
        status: str = "ok",
        reply: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        if self._done:
            return
        self._done = True
        try:
            self.data["status"] = status
            self.data["ended_at"] = _utc_now()
            self.data["duration_ms"] = int((time.perf_counter() - self._t0) * 1000)
            if reply is not None:
                self.data["reply"] = reply if len(reply) <= 8000 else reply[:8000] + "…"
            if error is not None:
                self.data["error"] = error[:500]
            self._recorder.persist(self)
        except Exception:
            logger.warning("Failed to finish run %s", self.id, exc_info=True)
        finally:
            token = getattr(self, "_token", None)
            if token is not None:
                try:
                    _current.reset(token)
                except Exception:
                    _current.set(None)


class NullActiveRun:
    """No-op run used when recording is disabled or begin() failed."""

    id = ""

    def set(self, **fields: Any) -> None:
        return None

    def add_stage(self, *args: Any, **kwargs: Any) -> None:
        return None

    def finish(self, **kwargs: Any) -> None:
        return None


class NullRunRecorder:
    """Drop all events. Safe default when the operator UI is off."""

    def begin(self, **fields: Any) -> NullActiveRun:
        return NullActiveRun()

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        return None

    def list_runs(
        self,
        limit: int = 50,
        source: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return []

    def runs_today(self) -> int:
        return 0


class JsonlRunRecorder:
    """In-memory running runs plus an append-only JSONL file.

    Slack and MCP are separate processes that share ``runs.jsonl``. Reads
    reload when another process has appended, so the operator UI sees MCP
    runs without restarting the Slack bot.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._running: Dict[str, Dict[str, Any]] = {}
        self._recent: List[Dict[str, Any]] = []
        self._file_key: Optional[tuple] = None
        self._load()
        self._file_key = self._stat_key()

    def begin(self, **fields: Any) -> ActiveRun:
        try:
            run = ActiveRun(self, fields)
            snapshot = json.loads(json.dumps(run.data, default=str))
            with self._lock:
                self._running[run.id] = snapshot
            run._token = _current.set(run)
            return run
        except Exception:
            logger.warning("Failed to begin run", exc_info=True)
            return NullActiveRun()  # type: ignore[return-value]

    def touch(self, run: ActiveRun) -> None:
        try:
            snapshot = json.loads(json.dumps(run.data, default=str))
            with self._lock:
                if run.id in self._running:
                    self._running[run.id] = snapshot
        except Exception:
            logger.warning("Failed to update running run %s", run.id, exc_info=True)

    def persist(self, run: ActiveRun) -> None:
        try:
            snapshot = json.loads(json.dumps(run.data, default=str))
            with self._lock:
                self._reload_if_stale_locked()
                self._running.pop(run.id, None)
                self._recent = [row for row in self._recent if row.get("id") != run.id]
                self._recent.append(snapshot)
                if len(self._recent) > MAX_RUNS:
                    self._recent = self._recent[-MAX_RUNS:]
                    self._rewrite_locked()
                else:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with self.path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(snapshot, default=str) + "\n")
                self._file_key = self._stat_key()
        except Exception:
            logger.warning("Failed to persist run %s", run.id, exc_info=True)

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._lock:
                self._reload_if_stale_locked()
                if run_id in self._running:
                    return json.loads(json.dumps(self._running[run_id]))
                for item in reversed(self._recent):
                    if item.get("id") == run_id:
                        return json.loads(json.dumps(item))
        except Exception:
            logger.warning("Failed to read run %s", run_id, exc_info=True)
        return None

    def list_runs(
        self,
        limit: int = 50,
        source: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            cap = max(1, min(int(limit), 200))
            with self._lock:
                self._reload_if_stale_locked()
                items = list(self._running.values()) + list(self._recent)
            items.sort(key=lambda row: row.get("started_at") or "", reverse=True)
            out = []
            for row in items:
                if source and row.get("source") != source:
                    continue
                if status and row.get("status") != status:
                    continue
                out.append(json.loads(json.dumps(row)))
                if len(out) >= cap:
                    break
            return out
        except Exception:
            logger.warning("Failed to list runs", exc_info=True)
            return []

    def runs_today(self) -> int:
        try:
            today = _utc_now()[:10]
            with self._lock:
                self._reload_if_stale_locked()
                items = list(self._running.values()) + list(self._recent)
            return sum(1 for row in items if str(row.get("started_at") or "").startswith(today))
        except Exception:
            return 0

    def _stat_key(self) -> Optional[tuple]:
        try:
            if not self.path.exists():
                return None
            stat = self.path.stat()
            return (stat.st_mtime_ns, stat.st_size)
        except OSError:
            return None

    def _reload_if_stale_locked(self) -> None:
        """Re-read JSONL when another process has written it."""
        key = self._stat_key()
        if key == self._file_key:
            return
        self._load()
        self._file_key = key

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            rows: List[Dict[str, Any]] = []
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            self._recent = rows[-MAX_RUNS:]
        except Exception:
            logger.warning("Failed to load run log %s", self.path, exc_info=True)
            self._recent = []

    def _rewrite_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for row in self._recent:
                handle.write(json.dumps(row, default=str) + "\n")
        tmp.replace(self.path)
