"""Resolve onboarded Benedict projects from state.json, workspace paths, and cwd."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProjectResolutionError(Exception):
    """Raised when a project cannot be chosen unambiguously."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class Project:
    """One Slack-onboarded repository Benedict knows about."""

    repo: str
    channel_id: str
    workspace_path: Path
    repo_path: Path
    source_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable project summary."""
        return {
            "repo": self.repo,
            "channel_id": self.channel_id,
            "workspace_path": str(self.workspace_path),
            "repo_path": str(self.repo_path),
            "source_path": str(self.source_path) if self.source_path else None,
        }


def load_channel_state(state_file: Path) -> Dict[str, Any]:
    """Load channel→repo mappings from state.json.

    Returns:
        State dict with a ``channels`` key. Missing or invalid files yield empty channels.
    """
    if not state_file.exists():
        return {"channels": {}}
    try:
        with open(state_file, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"channels": {}}
    if not isinstance(data, dict):
        return {"channels": {}}
    if "channels" not in data or not isinstance(data.get("channels"), dict):
        data["channels"] = {}
    return data


def _resolve_source_path(repo_path: Path) -> Optional[Path]:
    """Return the real repository path if the workspace resource exists."""
    if not repo_path.exists() and not repo_path.is_symlink():
        return None
    try:
        return repo_path.resolve()
    except OSError:
        return None


def _cwd_matches(cwd: Path, candidate: Optional[Path]) -> bool:
    """True if cwd is the candidate directory or a subdirectory of it."""
    if candidate is None:
        return False
    try:
        cwd_resolved = cwd.resolve()
        candidate_resolved = candidate.resolve()
    except OSError:
        return False
    return cwd_resolved == candidate_resolved or candidate_resolved in cwd_resolved.parents


class ProjectResolver:
    """Map repo name or working directory to an onboarded project."""

    def __init__(self, state: Dict[str, Any], workspaces_dir: Path):
        """Initialize resolver.

        Args:
            state: Loaded state.json contents (``channels`` mapping).
            workspaces_dir: Benedict workspaces directory.
        """
        self._state = state
        self._workspaces_dir = Path(workspaces_dir)

    def list_projects(self) -> List[Project]:
        """Return every onboarded project, in state-file order."""
        projects: List[Project] = []
        channels = self._state.get("channels", {})
        for channel_id, config in channels.items():
            if not isinstance(config, dict):
                continue
            repo = config.get("repo")
            if not repo or not isinstance(repo, str):
                continue
            workspace_path = self._workspaces_dir / channel_id
            repo_path = workspace_path / repo
            projects.append(
                Project(
                    repo=repo,
                    channel_id=channel_id,
                    workspace_path=workspace_path,
                    repo_path=repo_path,
                    source_path=_resolve_source_path(repo_path),
                )
            )
        return projects

    def resolve(
        self,
        repo: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> Project:
        """Choose a project from an explicit repo name and/or the caller's cwd.

        Preference order:
        1. Explicit ``repo`` (exact, then unique suffix / basename).
        2. ``cwd`` inside a project's source or workspace repo path.
        3. The only onboarded project.

        Raises:
            ProjectResolutionError: No match, or more than one match.
        """
        projects = self.list_projects()
        if repo:
            return self._resolve_by_repo(repo, projects)

        if cwd is not None:
            cwd_matches = [
                project
                for project in projects
                if _cwd_matches(cwd, project.source_path) or _cwd_matches(cwd, project.repo_path)
            ]
            if len(cwd_matches) == 1:
                return cwd_matches[0]
            if cwd_matches:
                repo_names = {project.repo for project in cwd_matches}
                if len(repo_names) == 1:
                    return cwd_matches[0]
                return self._raise_ambiguous(
                    "Working directory matches multiple Benedict projects.",
                    cwd_matches,
                )

        if len(projects) == 1:
            return projects[0]
        if not projects:
            raise ProjectResolutionError(
                "No Benedict projects are onboarded. In Slack, run "
                "`@benedict onboard repo org/repo`, then retry."
            )
        return self._raise_ambiguous(
            "Multiple Benedict projects are onboarded. Pass `repo` from list_projects, "
            "or run this from an onboarded repository.",
            projects,
        )

    def _resolve_by_repo(self, repo: str, projects: List[Project]) -> Project:
        needle = repo.strip().rstrip("/")
        if not needle:
            raise ProjectResolutionError("repo must be a non-empty string.")

        exact = [project for project in projects if project.repo == needle]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return self._raise_ambiguous(f"Multiple projects named `{needle}`.", exact)

        lowered = needle.lower()
        casefold = [project for project in projects if project.repo.lower() == lowered]
        if len(casefold) == 1:
            return casefold[0]

        suffix = [
            project
            for project in projects
            if project.repo.lower().endswith("/" + lowered)
            or Path(project.repo).name.lower() == lowered
        ]
        if len(suffix) == 1:
            return suffix[0]
        if len(suffix) > 1:
            return self._raise_ambiguous(f"`{needle}` matches multiple projects.", suffix)

        available = ", ".join(f"`{project.repo}`" for project in projects) or "(none)"
        raise ProjectResolutionError(
            f"No onboarded Benedict project matches `{needle}`. Available: {available}."
        )

    def _raise_ambiguous(self, prefix: str, matches: List[Project]) -> Project:
        listing = ", ".join(
            f"`{project.repo}` (channel {project.channel_id})" for project in matches
        )
        raise ProjectResolutionError(f"{prefix} Matches: {listing}. Pass `repo` to choose.")
