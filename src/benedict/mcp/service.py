"""Read-only Benedict operations used by the MCP server.

Keeps MCP SDK types out of domain logic so the service can be unit-tested
without a protocol session.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from benedict.mcp.project import Project, ProjectResolutionError, ProjectResolver
from benedict.operator_ui.recorder import record_llm_stage
from benedict.workspace.action_logger import ActionLogger

MAX_SEARCH_CONTENT_CHARS = 4000
DEFAULT_SEARCH_TOP_K = 5
MAX_SEARCH_TOP_K = 20
DEFAULT_ACTIONS_LIMIT = 10
MAX_ACTIONS_LIMIT = 50
ASK_CONTEXT_MAX_TOKENS = 4000
ASK_MAX_TOKENS = 2000


def _ok(**payload: Any) -> Dict[str, Any]:
    return {"ok": True, **payload}


def _err(message: str, **payload: Any) -> Dict[str, Any]:
    return {"ok": False, "error": message, **payload}


def _truncate(text: str, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n...[truncated, {omitted} chars omitted]"


class BenedictMcpService:
    """Project-scoped reads: metadata, search, actions, Q&A."""

    def __init__(
        self,
        resolver: ProjectResolver,
        metadata_reader,
        semantic_indexer=None,
        llm=None,
        workspace_manager=None,
        repo_reader=None,
        run_recorder=None,
    ):
        """Initialize service with injected dependencies.

        Args:
            resolver: Maps repo/cwd to an onboarded project.
            metadata_reader: MetadataReader instance.
            semantic_indexer: Optional SemanticIndexer.
            llm: Optional LLM for ask_benedict.
            workspace_manager: Optional WorkspaceManager for workspace-aware file reads.
            repo_reader: Optional fallback RepoReader for ask_benedict.
            run_recorder: Optional operator-UI run recorder.
        """
        self._resolver = resolver
        self._metadata_reader = metadata_reader
        self._semantic_indexer = semantic_indexer
        self._llm = llm
        self._workspace_manager = workspace_manager
        self._repo_reader = repo_reader
        if run_recorder is None:
            from benedict.operator_ui.recorder import NullRunRecorder

            run_recorder = NullRunRecorder()
        self._run_recorder = run_recorder

    def _mcp_run(self, route: str, query: str, repo, fn):
        run = self._run_recorder.begin(
            source="mcp",
            kind="mcp",
            query=query,
            repo=repo or "",
            route=route,
        )
        run.add_stage("route", label=route, detail={"matched": route})
        try:
            result = fn()
            success = bool(result.get("ok")) if isinstance(result, dict) else True
            reply = None
            if isinstance(result, dict):
                reply = result.get("answer") or result.get("error") or result.get("summary")
                if reply is not None:
                    reply = str(reply)
                if result.get("repo"):
                    run.set(repo=result.get("repo"), channel_id=result.get("channel_id") or "")
            run.finish(
                status="ok" if success else "error",
                reply=reply,
                error=None if success else (result.get("error") if isinstance(result, dict) else None),
            )
            return result
        except Exception as exc:
            run.finish(status="error", error=str(exc))
            raise

    def list_projects(self) -> Dict[str, Any]:
        """List onboarded projects."""

        def _do():
            projects = [project.to_dict() for project in self._resolver.list_projects()]
            return _ok(projects=projects, count=len(projects))

        return self._mcp_run("list_projects", "list_projects", None, _do)

    def get_repository_summary(
        self, repo: Optional[str] = None, cwd: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Return root `.metadata.benedict` summary and purpose."""
        try:
            project = self._resolver.resolve(repo=repo, cwd=cwd)
        except ProjectResolutionError as exc:
            return _err(exc.message)

        metadata = self._metadata_reader.read_metadata(project.repo_path)
        if not metadata:
            return _err(
                f"No `.metadata.benedict` found for `{project.repo}`.",
                repo=project.repo,
                channel_id=project.channel_id,
            )
        return _ok(
            repo=project.repo,
            channel_id=project.channel_id,
            summary=metadata.get("summary"),
            purpose=metadata.get("purpose"),
        )

    def search_code(
        self,
        query: str,
        repo: Optional[str] = None,
        cwd: Optional[Path] = None,
        top_k: int = DEFAULT_SEARCH_TOP_K,
    ) -> Dict[str, Any]:
        """Semantic search over an onboarded repository index."""
        if not query or not str(query).strip():
            return _err("query must be a non-empty string.")
        if not self._semantic_indexer:
            return _err("Semantic index is not available on this Benedict instance.")

        try:
            project = self._resolver.resolve(repo=repo, cwd=cwd)
        except ProjectResolutionError as exc:
            return _err(exc.message)

        limit = max(1, min(int(top_k), MAX_SEARCH_TOP_K))
        if not self._semantic_indexer.is_indexed(project.repo):
            return _ok(
                repo=project.repo,
                channel_id=project.channel_id,
                results=[],
                note=(
                    f"`{project.repo}` is not indexed yet. In Slack, run "
                    "`@benedict update index`."
                ),
            )

        raw_results = self._semantic_indexer.search(project.repo, query.strip(), top_k=limit)
        results: List[Dict[str, Any]] = []
        for item in raw_results:
            results.append(
                {
                    "file_path": item.get("file_path"),
                    "score": item.get("score"),
                    "content": _truncate(str(item.get("content") or ""), MAX_SEARCH_CONTENT_CHARS),
                }
            )
        return _ok(
            repo=project.repo, channel_id=project.channel_id, query=query.strip(), results=results
        )

    def get_recent_actions(
        self,
        repo: Optional[str] = None,
        cwd: Optional[Path] = None,
        limit: int = DEFAULT_ACTIONS_LIMIT,
    ) -> Dict[str, Any]:
        """Return recent workspace actions for the project's Slack channel."""
        try:
            project = self._resolver.resolve(repo=repo, cwd=cwd)
        except ProjectResolutionError as exc:
            return _err(exc.message)

        cap = max(1, min(int(limit), MAX_ACTIONS_LIMIT))
        action_logger = ActionLogger(project.workspace_path)
        actions = action_logger.get_recent_actions(limit=cap)
        return _ok(repo=project.repo, channel_id=project.channel_id, actions=actions)

    def ask(
        self,
        question: str,
        repo: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Answer a question using repository context. Does not include Slack history."""
        return self._mcp_run(
            "BenedictMcpService.ask",
            f"ask_benedict  {question or ''}",
            repo,
            lambda: self._ask_untraced(question, repo, cwd),
        )

    def _ask_untraced(
        self,
        question: str,
        repo: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> Dict[str, Any]:
        if not question or not str(question).strip():
            return _err("question must be a non-empty string.")
        if not self._llm:
            return _err("LLM is not available. Set ANTHROPIC_API_KEY for the Benedict MCP process.")

        try:
            project = self._resolver.resolve(repo=repo, cwd=cwd)
        except ProjectResolutionError as exc:
            return _err(exc.message)

        repo_reader = self._repo_reader_for(project)
        if repo_reader is None:
            return _err("No repository reader is configured.")

        from benedict.utils.context import build_context

        action_logger = ActionLogger(project.workspace_path)
        context = build_context(
            repo=project.repo,
            question=question.strip(),
            repo_reader=repo_reader,
            semantic_indexer=self._semantic_indexer,
            max_tokens=ASK_CONTEXT_MAX_TOKENS,
            workspace_path=project.workspace_path,
            metadata_reader=self._metadata_reader,
            action_logger=action_logger,
        )
        system = (
            f"You are Benedict, a repo-scoped assistant for `{project.repo}`.\n\n"
            "Answer from the repository context below. Do not invent files or "
            "decisions that are not in the context.\n"
            "This call does not include Slack conversation history.\n\n"
            f"## Repository context\n\n{context}"
        )
        messages = [{"role": "user", "content": question.strip()}]
        llm_started = time.perf_counter()
        answer = self._llm.generate(
            messages=messages,
            system=system,
            max_tokens=ASK_MAX_TOKENS,
        )
        record_llm_stage(
            system=system,
            messages=messages,
            duration_ms=int((time.perf_counter() - llm_started) * 1000),
            label=os.environ.get("ANTHROPIC_MODEL", "claude"),
        )
        if isinstance(answer, dict):
            answer = str(answer)
        return _ok(repo=project.repo, channel_id=project.channel_id, answer=str(answer))

    def _repo_reader_for(self, project: Project):
        """Prefer a workspace-bound reader; fall back to the injected reader."""
        if self._workspace_manager:
            try:
                from benedict.repo_reader.repo_reader_workspace import WorkspaceRepoReader
                from benedict.repo_reader.repo_reader_workspace_adapter import (
                    WorkspaceRepoReaderAdapter,
                )

                workspace_reader = WorkspaceRepoReader(self._workspace_manager)
                return WorkspaceRepoReaderAdapter(workspace_reader, project.channel_id)
            except Exception:
                pass
        return self._repo_reader
