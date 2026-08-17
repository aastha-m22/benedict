"""GitHub CLI tool.

One tool that runs `gh` with caller-supplied argv. The prompt owns GitHub
usage; this module only locks cwd, timeout, output size, and the binary.
"""

import logging
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .tool_framework import Tool, ToolResult

logger = logging.getLogger(__name__)

GITHUB_BINARY = "gh"
DEFAULT_TIMEOUT_S = 30
MAX_OUTPUT_CHARS = 32000
_TOKEN_RE = re.compile(r"(ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]+")


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate text and note if it was cut."""
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated, {len(text) - limit} chars omitted]"


def _redact_tokens(text: str) -> str:
    """Strip GitHub token-shaped strings from tool output."""
    if not text:
        return text
    return _TOKEN_RE.sub("[redacted-token]", text)


def _normalize_argv(raw: Union[List[Any], str, None]) -> Optional[List[str]]:
    """Coerce argv to a list of strings. Strips a leading `gh` if the model included it."""
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            argv = shlex.split(raw)
        except ValueError:
            return None
    elif isinstance(raw, list):
        argv = [str(item) for item in raw]
    else:
        return None

    if argv and argv[0] in (GITHUB_BINARY, f"{GITHUB_BINARY}.exe"):
        argv = argv[1:]
    return argv


class RunGithubTool(Tool):
    """Run `gh` in the workspace repository. Not a general shell."""

    def __init__(self, timeout_s: int = DEFAULT_TIMEOUT_S):
        super().__init__(
            name="run_github",
            description=(
                "Run the GitHub CLI (`gh`) in this repository. Pass arguments only — "
                'do not include `gh` itself. Example: argv=["pr", "list", "--json", '
                '"title,url,author"]. Use --json when you need to parse results. '
                "This is not a general shell: you cannot run git, bash, or other binaries. "
                "Ask the user before mutating GitHub (create, merge, close, comment)."
            ),
        )
        self.timeout_s = timeout_s

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Arguments for `gh` (without the `gh` binary). "
                            'Example: ["pr", "view", "12", "--json", "title,body,checks"]'
                        ),
                    }
                },
                "required": ["argv"],
            },
        }

    def execute(
        self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        argv = _normalize_argv(arguments.get("argv"))
        if argv is None:
            return ToolResult(
                success=False,
                error="argv must be a list of strings or a shell-style string",
            )
        if not argv:
            return ToolResult(success=False, error="argv must not be empty")
        if any("\x00" in part for part in argv):
            return ToolResult(success=False, error="argv contains invalid characters")
        if argv[0] == "auth" and len(argv) > 1 and argv[1] == "token":
            return ToolResult(
                success=False,
                error="Refusing to run `gh auth token` (would expose credentials).",
            )

        if not context or not context.get("workspace_path"):
            return ToolResult(
                success=False,
                error="workspace_path not provided in context",
            )

        cwd = Path(context["workspace_path"])
        if not cwd.is_dir():
            return ToolResult(
                success=False,
                error=f"Repository path does not exist: {cwd}",
            )

        if shutil.which(GITHUB_BINARY) is None:
            return ToolResult(
                success=False,
                error=(
                    "gh is not installed on the host running Benedict. "
                    "Install GitHub CLI and authenticate (`gh auth login`)."
                ),
            )

        command = [GITHUB_BINARY, *argv]
        logger.info("Running GitHub CLI: %s (cwd=%s)", command, cwd)

        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"gh timed out after {self.timeout_s}s",
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="gh is not installed on the host running Benedict.",
            )
        except OSError as exc:
            logger.error("Failed to run gh: %s", exc, exc_info=True)
            return ToolResult(success=False, error=str(exc))

        stdout = _redact_tokens(_truncate(completed.stdout or ""))
        stderr = _redact_tokens(_truncate(completed.stderr or ""))
        if completed.returncode == 0:
            message = stdout or "gh exited 0 with no output"
        else:
            details = stderr or stdout or "no output"
            message = f"gh exited {completed.returncode}\n{details}"
        return ToolResult(
            success=True,
            message=message,
            data={
                "exit_code": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
            },
        )
