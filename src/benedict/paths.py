"""Runtime path helpers shared by the Slack bot and the MCP server."""

import os
from pathlib import Path


def find_repo_root() -> Path:
    """Find repository root by looking for common markers.

    Returns:
        Path to repository root, or current working directory if not found.
    """
    current = Path(__file__).parent
    for parent in [current] + list(current.parents):
        if any(
            (parent / marker).exists() for marker in [".git", "pyproject.toml", "setup.py", ".env"]
        ):
            return parent
    return Path.cwd()


def get_data_dir() -> Path:
    """Get data directory from BENEDICT_DATA_DIR or the repo root."""
    data_dir = os.environ.get("BENEDICT_DATA_DIR")
    if data_dir:
        return Path(data_dir).resolve()
    return find_repo_root()


def get_env_file() -> Path:
    """Get .env file path from BENEDICT_ENV_FILE or the repo root."""
    env_file = os.environ.get("BENEDICT_ENV_FILE")
    if env_file:
        return Path(env_file).resolve()
    return find_repo_root() / ".env"
