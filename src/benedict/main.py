#!/usr/bin/env python3
"""
Slack Repo Agent - Main Entry Point

Composition root where all dependencies are wired together.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode import SocketModeHandler

from benedict.agent import RepoAgent
from benedict.protocols import (
    create_llm,
    create_repo_reader,
    create_semantic_indexer,
    create_conversation_repository,
    create_conversation_history_indexer,
)
from benedict.slack_app import create_slack_app
from benedict.workspace import WorkspaceManager
from benedict.lib.logging import setup_logging, get_logger
from slack_sdk import WebClient

# Configure logging first
setup_logging()
logger = get_logger(__name__)


def _find_repo_root() -> Path:
    """Find repository root by looking for common markers (.git, pyproject.toml, etc.).

    Returns:
        Path to repository root, or current working directory if not found
    """
    # Start from the directory containing this file
    current = Path(__file__).parent

    # Walk up the directory tree looking for repo markers
    for parent in [current] + list(current.parents):
        if any(
            (parent / marker).exists() for marker in [".git", "pyproject.toml", "setup.py", ".env"]
        ):
            return parent

    # Fallback to current working directory
    return Path.cwd()


def _get_data_dir() -> Path:
    """Get data directory from environment or use default.

    Returns:
        Path to data directory
    """
    data_dir = os.environ.get("BENEDICT_DATA_DIR")
    if data_dir:
        return Path(data_dir).resolve()

    # Default: use repo root
    return _find_repo_root()


def _get_env_file() -> Path:
    """Get .env file path from environment or use default.

    Returns:
        Path to .env file
    """
    env_file = os.environ.get("BENEDICT_ENV_FILE")
    if env_file:
        return Path(env_file).resolve()

    # Default: look for .env in repo root
    repo_root = _find_repo_root()
    return repo_root / ".env"


# Load environment variables from .env file only if not already set
# This respects existing environment variables and falls back to .env file
_env_path = _get_env_file()
if not os.environ.get("SLACK_BOT_TOKEN") or not os.environ.get("SLACK_APP_TOKEN"):
    if _env_path.exists():
        logger.info(f"Loading .env from: {_env_path}")
        load_dotenv(
            dotenv_path=_env_path, override=False
        )  # override=False means don't overwrite existing env vars
    else:
        logger.warning(f".env file not found at: {_env_path}")
else:
    logger.info("Using environment variables from system (not loading .env file)")


def main():
    """Root composition - wire everything together."""

    # Validate environment variables
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")

    if not bot_token:
        logger.error("SLACK_BOT_TOKEN not found in environment variables")
        raise ValueError("Missing SLACK_BOT_TOKEN")

    if not app_token:
        logger.error("SLACK_APP_TOKEN not found in environment variables")
        raise ValueError("Missing SLACK_APP_TOKEN")

    logger.info("=" * 60)
    logger.info("Starting Slack Repo Agent...")
    logger.info(f"Bot Token: {bot_token[:20]}...")
    logger.info(f"App Token: {app_token[:20]}...")
    logger.info("=" * 60)

    # Create LLM (optional - can be None for stub mode)
    llm = None
    try:
        llm = create_llm(provider="claude")
        logger.info("✅ LLM initialized (Claude)")
    except Exception as e:
        logger.warning(f"⚠️ LLM not available: {e}")
        logger.info("Running in stub mode (no LLM responses)")

    # Create repo reader (optional - can be None for stub mode)
    repo_reader = None
    try:
        repo_reader = create_repo_reader(source="local")
        logger.info("✅ Repo reader initialized (local filesystem)")
    except Exception as e:
        logger.warning(f"⚠️ Repo reader not available: {e}")
        logger.info("Running without repository access")

    # Get data directory (configurable via BENEDICT_DATA_DIR env var)
    data_dir = _get_data_dir()
    logger.info(f"Using data directory: {data_dir}")

    # Create workspace manager
    workspaces_dir = os.environ.get("BENEDICT_WORKSPACES_DIR", str(data_dir / "workspaces"))
    copy_mode = os.environ.get("BENEDICT_WORKSPACE_COPY_MODE", "symlink")
    workspace_manager = WorkspaceManager(workspaces_dir=workspaces_dir, copy_mode=copy_mode)
    logger.info(
        f"✅ Workspace manager initialized (workspaces_dir={workspaces_dir}, copy_mode={copy_mode})"
    )

    # Create semantic indexer (optional - falls back to keyword matching if None)
    semantic_indexer = None
    try:
        # Use configurable path for ChromaDB (defaults to data_dir/.chroma_db)
        chroma_db_path = os.environ.get("BENEDICT_CHROMA_DB_DIR", str(data_dir / ".chroma_db"))
        # Create metadata generator for semantic indexer
        from benedict.metadata import MetadataGenerator
        from benedict.protocols.repo_change_detector import create_repo_change_detector

        metadata_generator = MetadataGenerator()
        change_detector = create_repo_change_detector(detector_type="git")
        semantic_indexer = create_semantic_indexer(
            provider="chromadb",
            persist_directory=chroma_db_path,
            metadata_generator=metadata_generator,
            change_detector=change_detector,
        )
        logger.info(f"✅ Semantic indexer initialized (ChromaDB at {chroma_db_path})")
    except Exception as e:
        logger.warning(f"⚠️ Semantic indexer not available: {e}")
        logger.info("Falling back to keyword-based file matching")

    # Create conversation repository
    # Use configurable path for state file (defaults to data_dir/state.json)
    state_file = os.environ.get("BENEDICT_STATE_FILE", str(data_dir / "state.json"))
    conversation_repository = create_conversation_repository(provider="json", state_file=state_file)
    logger.info(f"✅ Conversation repository initialized (JSON at {state_file})")

    # Create Slack WebClient for conversation history indexing
    slack_client = WebClient(token=bot_token)

    # Create conversation history indexer (optional)
    conversation_history_indexer = None
    try:
        conversation_history_indexer = create_conversation_history_indexer(
            platform="slack", slack_client=slack_client
        )
        logger.info("✅ Conversation history indexer initialized (Slack)")
    except Exception as e:
        logger.warning(f"⚠️ Conversation history indexer not available: {e}")
        logger.info("Slack history indexing will not be available")

    # Create agent with dependencies
    agent = RepoAgent(
        state_file=state_file,
        llm=llm,
        repo_reader=repo_reader,
        semantic_indexer=semantic_indexer,
        conversation_repository=conversation_repository,
        workspace_manager=workspace_manager,
        conversation_history_indexer=conversation_history_indexer,
    )

    # Initialize state file if it doesn't exist
    state_path = Path(state_file)
    if not state_path.exists():
        agent.save_state({"channels": {}})
        logger.info(f"Created new state file: {state_path}")

    # Create and configure Slack app
    slack_app = create_slack_app(agent)

    # Start the app
    logger.info("Initializing Socket Mode handler...")
    handler = SocketModeHandler(slack_app, app_token)
    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    logger.info("Waiting for events...")
    
    try:
        handler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
