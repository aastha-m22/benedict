"""MCP stdio server composition root.

Cursor, Claude Code, and other MCP clients launch this process. It does not
start Slack. It reads the same state, workspaces, and index as the Slack bot.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from benedict.mcp.project import ProjectResolver, load_channel_state
from benedict.mcp.service import BenedictMcpService
from benedict.paths import get_data_dir, get_env_file
from benedict.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Log to stderr so stdio MCP JSON-RPC on stdout stays clean."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
        force=True,
    )


def _load_env() -> None:
    env_path = get_env_file()
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        logger.info("Loaded environment from %s", env_path)
    else:
        logger.info("No .env file at %s; using process environment", env_path)


def build_mcp_service(
    data_dir: Optional[Path] = None,
    workspaces_dir: Optional[Path] = None,
    state_file: Optional[Path] = None,
    chroma_db_dir: Optional[Path] = None,
) -> BenedictMcpService:
    """Wire MCP service dependencies. Concrete types are created here only."""
    data = Path(data_dir) if data_dir is not None else get_data_dir()
    workspaces = Path(
        workspaces_dir
        if workspaces_dir is not None
        else os.environ.get("BENEDICT_WORKSPACES_DIR", str(data / "workspaces"))
    )
    state_path = Path(
        state_file
        if state_file is not None
        else os.environ.get("BENEDICT_STATE_FILE", str(data / "state.json"))
    )
    chroma_path = Path(
        chroma_db_dir
        if chroma_db_dir is not None
        else os.environ.get("BENEDICT_CHROMA_DB_DIR", str(data / ".chroma_db"))
    )
    copy_mode = os.environ.get("BENEDICT_WORKSPACE_COPY_MODE", "symlink")

    from benedict.metadata import MetadataReader
    from benedict.protocols import create_llm, create_repo_reader, create_semantic_indexer

    workspace_manager = WorkspaceManager(workspaces_dir=str(workspaces), copy_mode=copy_mode)
    resolver = ProjectResolver(load_channel_state(state_path), workspaces)

    llm = None
    try:
        llm = create_llm(provider="claude")
        logger.info("LLM initialized for ask_benedict")
    except Exception as exc:
        logger.warning("LLM not available: %s", exc)

    repo_reader = None
    try:
        repo_reader = create_repo_reader(source="local")
    except Exception as exc:
        logger.warning("Repo reader not available: %s", exc)

    semantic_indexer = None
    try:
        from benedict.metadata import MetadataGenerator
        from benedict.protocols.repo_change_detector import create_repo_change_detector

        semantic_indexer = create_semantic_indexer(
            provider="chromadb",
            persist_directory=str(chroma_path),
            metadata_generator=MetadataGenerator(),
            change_detector=create_repo_change_detector(detector_type="git"),
        )
        logger.info("Semantic indexer initialized (%s)", chroma_path)
    except Exception as exc:
        logger.warning("Semantic indexer not available: %s", exc)

    from benedict.operator_ui.server import create_recorder

    return BenedictMcpService(
        resolver=resolver,
        metadata_reader=MetadataReader(),
        semantic_indexer=semantic_indexer,
        llm=llm,
        workspace_manager=workspace_manager,
        repo_reader=repo_reader,
        run_recorder=create_recorder(data),
    )


def create_mcp_server(service: BenedictMcpService):
    """Create an MCP server that delegates tools to ``service``."""
    from mcp.server import MCPServer

    mcp = MCPServer(
        "benedict",
        instructions=(
            "Benedict is a repo-scoped project assistant. Use list_projects if the "
            "target repo is unclear. Prefer get_repository_summary and search_code "
            "for facts already indexed. ask_benedict answers from Benedict's index "
            "and metadata; it does not include Slack history. These tools are read-only."
        ),
    )

    @mcp.tool()
    def list_projects() -> dict:
        """List repositories Benedict has onboarded (Slack channel → repo)."""
        return service.list_projects()

    @mcp.tool()
    def get_repository_summary(repo: Optional[str] = None) -> dict:
        """Get the repository metadata summary and purpose.

        Args:
            repo: Onboarded repo id (e.g. org/name). Omit to use the current workspace.
        """
        return service.get_repository_summary(repo=repo, cwd=Path.cwd())

    @mcp.tool()
    def search_code(query: str, repo: Optional[str] = None, top_k: int = 5) -> dict:
        """Semantic search over Benedict's code index for an onboarded repo.

        Args:
            query: Natural-language search query.
            repo: Onboarded repo id (e.g. org/name). Omit to use the current workspace.
            top_k: Number of hits to return (1-20).
        """
        return service.search_code(query=query, repo=repo, cwd=Path.cwd(), top_k=top_k)

    @mcp.tool()
    def get_recent_actions(repo: Optional[str] = None, limit: int = 10) -> dict:
        """Get recent Benedict workspace actions for a project.

        Args:
            repo: Onboarded repo id (e.g. org/name). Omit to use the current workspace.
            limit: Maximum number of actions to return (1-50).
        """
        return service.get_recent_actions(repo=repo, cwd=Path.cwd(), limit=limit)

    @mcp.tool()
    def ask_benedict(question: str, repo: Optional[str] = None) -> dict:
        """Ask Benedict a question about an onboarded repo using its project context.

        Does not include Slack conversation history.

        Args:
            question: The question to answer from repository context.
            repo: Onboarded repo id (e.g. org/name). Omit to use the current workspace.
        """
        return service.ask(question=question, repo=repo, cwd=Path.cwd())

    return mcp


def main() -> None:
    """Load env, wire the service, and serve MCP over stdio."""
    _setup_logging()
    _load_env()
    data_dir = get_data_dir()
    logger.info("Starting Benedict MCP server (data_dir=%s)", data_dir)
    from benedict.operator_ui.server import clear_mcp_pid, write_mcp_pid

    write_mcp_pid(data_dir)
    try:
        service = build_mcp_service(data_dir=data_dir)
        mcp = create_mcp_server(service)
        mcp.run(transport="stdio")
    finally:
        clear_mcp_pid(data_dir)


if __name__ == "__main__":
    main()
