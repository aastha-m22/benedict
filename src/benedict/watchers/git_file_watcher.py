"""Git File Watcher

Background service that monitors repositories for new commits and new .md files,
sending notifications to Slack channels.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set, Any, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from benedict.protocols.repo_change_detector import RepoChangeDetector, create_repo_change_detector
from benedict.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class GitFileWatcher:
    """Background watcher for git repositories.

    Monitors all onboarded repositories for:
    - New commits
    - New .md files

    Sends notifications to Slack channels when events occur.
    """

    def __init__(
        self,
        agent: Any,
        slack_client: WebClient,
        check_interval: int = 300,  # 5 minutes default
        state_file: Optional[str] = None,
    ):
        """Initialize git file watcher.

        Args:
            agent: RepoAgent instance for accessing state and workspace manager
            slack_client: Slack WebClient for sending messages
            check_interval: Interval in seconds between checks (default: 300 = 5 minutes)
            state_file: Optional path to watcher state file (defaults to agent's state_file with .watcher suffix)
        """
        self.agent = agent
        self.slack_client = slack_client
        self.check_interval = check_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Use watcher-specific state file or derive from agent's state file
        if state_file:
            self.state_file = Path(state_file)
        else:
            agent_state_file = Path(agent.state_file)
            self.state_file = agent_state_file.parent / f"{agent_state_file.stem}.watcher{agent_state_file.suffix}"

        # Create change detector
        self.change_detector: RepoChangeDetector = create_repo_change_detector(detector_type="auto")

        logger.info(
            f"Initialized GitFileWatcher with check_interval={check_interval}s, state_file={self.state_file}"
        )

    def start(self) -> None:
        """Start the watcher in a background thread."""
        if self.running:
            logger.warning("Watcher is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._watch_loop, daemon=True, name="GitFileWatcher")
        self.thread.start()
        logger.info("GitFileWatcher started")

    def stop(self) -> None:
        """Stop the watcher."""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("GitFileWatcher stopped")

    def _watch_loop(self) -> None:
        """Main watch loop running in background thread."""
        logger.info("Watcher loop started")
        while self.running:
            try:
                self._check_all_repos()
            except Exception as e:
                logger.error(f"Error in watcher loop: {e}", exc_info=True)

            # Sleep for check_interval, but check running flag periodically
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Watcher loop stopped")

    def _check_all_repos(self) -> None:
        """Check all onboarded repositories for changes."""
        state = self.agent.load_state()
        channels = state.get("channels", {})

        if not channels:
            logger.debug("No channels onboarded, skipping check")
            return

        watcher_state = self._load_watcher_state()

        for channel_id, channel_config in channels.items():
            repo = channel_config.get("repo")
            if not repo:
                continue

            try:
                self._check_repo(channel_id, repo, watcher_state)
            except Exception as e:
                logger.error(f"Error checking repo {repo} for channel {channel_id}: {e}", exc_info=True)

        # Save watcher state after checking all repos
        self._save_watcher_state(watcher_state)

    def _check_repo(self, channel_id: str, repo: str, watcher_state: Dict[str, Any]) -> None:
        """Check a single repository for changes.

        Args:
            channel_id: Slack channel ID
            repo: Repository identifier (e.g., "org/repo")
            watcher_state: Watcher state dictionary (modified in place)
        """
        # Get repository path from workspace
        if not self.agent.workspace_manager:
            logger.warning(f"No workspace manager available, cannot check repo {repo}")
            return

        workspace_path = self.agent.workspace_manager.get_workspace_path(channel_id)
        repo_path = workspace_path / repo

        # Resolve symlink if needed
        if repo_path.is_symlink():
            symlink_target = repo_path.readlink()
            # If symlink is relative, resolve it relative to the symlink's parent
            if not symlink_target.is_absolute():
                repo_path = (repo_path.parent / symlink_target).resolve()
            else:
                repo_path = symlink_target.resolve()

        if not repo_path.exists():
            logger.warning(f"Repository path does not exist: {repo_path}")
            return

        # Check if it's a git repository
        if not self.change_detector.supports_git(repo_path):
            logger.debug(f"Repository {repo} is not a git repository, skipping")
            return

        # Get last checked time for this repo
        repo_key = f"{channel_id}:{repo}"
        last_checked_time = watcher_state.get("repos", {}).get(repo_key, {}).get("last_commit_time")

        # Get last commit time from git
        last_commit_time = self.change_detector.get_last_commit_time(repo_path)

        if not last_commit_time:
            logger.debug(f"No commits found for repo {repo}")
            return

        # Check for new commits
        if last_checked_time:
            last_checked_dt = datetime.fromisoformat(last_checked_time.replace("Z", "+00:00"))
            if last_commit_time > last_checked_dt:
                # New commit detected
                self._handle_new_commit(channel_id, repo, repo_path, last_checked_dt, watcher_state)
        else:
            # First time checking - initialize but don't notify
            logger.info(f"Initializing watcher for repo {repo} (first check)")

        # Update last checked time
        if repo_key not in watcher_state.get("repos", {}):
            watcher_state.setdefault("repos", {})[repo_key] = {}
        watcher_state["repos"][repo_key]["last_commit_time"] = last_commit_time.isoformat()

        # Check for new .md files
        self._check_new_md_files(channel_id, repo, repo_path, watcher_state)

    def _handle_new_commit(
        self,
        channel_id: str,
        repo: str,
        repo_path: Path,
        since: datetime,
        watcher_state: Dict[str, Any],
    ) -> None:
        """Handle detection of a new commit.

        Args:
            channel_id: Slack channel ID
            repo: Repository identifier
            repo_path: Path to repository
            since: Datetime to check changes since
            watcher_state: Watcher state dictionary
        """
        changes = self.change_detector.detect_changes(repo_path, since=since)

        added_files = changes.get("added", [])
        modified_files = changes.get("modified", [])
        deleted_files = changes.get("deleted", [])
        diff_output = changes.get("diff")

        if not (added_files or modified_files or deleted_files):
            return

        # Save patch to file if diff is available
        patch_file_path = None
        workspace_path = None
        if diff_output and self.agent.workspace_manager:
            try:
                workspace_path = self.agent.workspace_manager.get_workspace_path(channel_id)
                patches_dir = workspace_path / ".benedict" / "patches"
                patches_dir.mkdir(parents=True, exist_ok=True)
                
                # Create patch file with timestamp
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                patch_file_path = patches_dir / f"patch_{timestamp}.diff"
                
                with open(patch_file_path, "w", encoding="utf-8") as f:
                    f.write(diff_output)
                
                logger.info(f"Saved patch to {patch_file_path}")
            except Exception as e:
                logger.error(f"Error saving patch file: {e}", exc_info=True)

        # Analyze changes and link to roadmap
        analysis_summary = None
        if self.agent.llm and self.agent.semantic_indexer:
            try:
                analysis_summary = self._analyze_changes_and_link_roadmap(
                    repo, repo_path, added_files, modified_files, deleted_files, diff_output
                )
            except Exception as e:
                logger.error(f"Error analyzing changes: {e}", exc_info=True)

        # Send brief title/notification to channel
        title_message = f"📝 *New commit detected in {repo}*"
        thread_ts = self._send_slack_message(channel_id, title_message)

        if not thread_ts:
            logger.error(f"Failed to send title message to channel {channel_id}")
            return

        # Build detailed content for thread
        detail_parts = []

        if added_files:
            detail_parts.append(f"*Added files ({len(added_files)}):*")
            for file_path in added_files:
                detail_parts.append(f"  • `{file_path}`")

        if modified_files:
            detail_parts.append(f"\n*Modified files ({len(modified_files)}):*")
            for file_path in modified_files:
                detail_parts.append(f"  • `{file_path}`")

        if deleted_files:
            detail_parts.append(f"\n*Deleted files ({len(deleted_files)}):*")
            for file_path in deleted_files:
                detail_parts.append(f"  • `{file_path}`")

        # Add patch file reference if saved
        if patch_file_path and workspace_path:
            try:
                rel_path = patch_file_path.relative_to(workspace_path)
                detail_parts.append(f"\n📄 *Patch saved:* `{rel_path}`")
            except ValueError:
                # If relative path calculation fails, use absolute path
                detail_parts.append(f"\n📄 *Patch saved:* `{patch_file_path}`")

        # Send file changes details in thread
        if detail_parts:
            detail_message = "\n".join(detail_parts)
            self._send_slack_message(channel_id, detail_message, thread_ts=thread_ts)

        # Send analysis summary in thread if available
        if analysis_summary:
            self._send_slack_message(channel_id, analysis_summary, thread_ts=thread_ts)

    def _analyze_changes_and_link_roadmap(
        self,
        repo: str,
        repo_path: Path,
        added_files: List[str],
        modified_files: List[str],
        deleted_files: List[str],
        diff_output: Optional[str],
    ) -> Optional[str]:
        """Analyze changes using LLM and link to roadmap.

        Args:
            repo: Repository identifier
            repo_path: Path to repository
            added_files: List of added file paths
            modified_files: List of modified file paths
            deleted_files: List of deleted file paths
            diff_output: Optional git diff output

        Returns:
            Analysis summary string, or None if analysis failed
        """
        if not self.agent.llm or not self.agent.semantic_indexer:
            return None

        try:
            # Build change description
            change_description_parts = []
            if added_files:
                change_description_parts.append(f"Added files: {', '.join(added_files[:5])}")
            if modified_files:
                change_description_parts.append(f"Modified files: {', '.join(modified_files[:5])}")
            if deleted_files:
                change_description_parts.append(f"Deleted files: {', '.join(deleted_files[:5])}")

            change_description = "\n".join(change_description_parts)

            # Search for roadmap files
            roadmap_content = self._find_roadmap_content(repo, repo_path)

            # Use semantic search to find related roadmap items
            roadmap_items = []
            if self.agent.semantic_indexer.is_indexed(repo):
                # Search for relevant roadmap items based on changed files
                search_queries = []
                for file_path in (added_files + modified_files)[:5]:  # Limit queries
                    # Extract meaningful terms from file path
                    file_name = Path(file_path).stem
                    search_queries.append(file_name)

                for query in search_queries:
                    try:
                        results = self.agent.semantic_indexer.search(
                            repo=repo,
                            query=query,
                            top_k=3,
                            workspace_path=self.agent.workspace_manager.get_workspace_path(
                                self._get_channel_for_repo(repo)
                            ) if self.agent.workspace_manager else None,
                        )
                        # Filter for roadmap-related files
                        for result in results:
                            file_path = result.get("file_path", "")
                            if any(
                                keyword in file_path.lower()
                                for keyword in ["roadmap", "plan", "milestone", "todo", "backlog"]
                            ):
                                roadmap_items.append(result)
                    except Exception as e:
                        logger.debug(f"Error searching for roadmap items with query '{query}': {e}")

            # Build context for LLM analysis
            analysis_prompt = f"""Analyze the following code changes and provide a summary that links them to the project roadmap.

Changes:
{change_description}

{f"Git Diff:\n{diff_output[:5000]}" if diff_output else "No diff available"}

{f"Roadmap Content:\n{roadmap_content[:2000]}" if roadmap_content else "No roadmap found"}

{f"Related Roadmap Items:\n{self._format_search_results(roadmap_items[:3])}" if roadmap_items else ""}

Please provide:
1. A brief summary of what changed
2. How these changes relate to the roadmap (if applicable)
3. Any roadmap items that might be affected or completed by these changes

Keep the response concise and focused on linking changes to roadmap items."""

            # Get LLM analysis
            try:
                response = self.agent.llm.generate(
                    messages=[{"role": "user", "content": analysis_prompt}],
                    system="You are a code analysis assistant that helps link code changes to project roadmaps.",
                    max_tokens=1000,
                )

                response_text = response if isinstance(response, str) else str(response)
                return f"🔍 *Change Analysis:*\n{response_text}"
            except Exception as e:
                logger.error(f"Error generating LLM analysis: {e}", exc_info=True)
                return None

        except Exception as e:
            logger.error(f"Error in change analysis: {e}", exc_info=True)
            return None

    def _find_roadmap_content(self, repo: str, repo_path: Path) -> Optional[str]:
        """Find and read roadmap files in repository.

        Args:
            repo: Repository identifier
            repo_path: Path to repository

        Returns:
            Roadmap content string, or None if not found
        """
        roadmap_files = ["ROADMAP.md", "roadmap.md", "ROADMAP.txt", "roadmap.txt", "docs/ROADMAP.md"]

        for roadmap_file in roadmap_files:
            roadmap_path = repo_path / roadmap_file
            if roadmap_path.exists() and roadmap_path.is_file():
                try:
                    with open(roadmap_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        logger.info(f"Found roadmap file: {roadmap_file}")
                        return content
                except Exception as e:
                    logger.debug(f"Error reading roadmap file {roadmap_file}: {e}")

        # Also check docs directory
        docs_path = repo_path / "docs"
        if docs_path.exists():
            for roadmap_file in roadmap_files:
                roadmap_path = docs_path / Path(roadmap_file).name
                if roadmap_path.exists() and roadmap_path.is_file():
                    try:
                        with open(roadmap_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            logger.info(f"Found roadmap file: {roadmap_path}")
                            return content
                    except Exception as e:
                        logger.debug(f"Error reading roadmap file {roadmap_path}: {e}")

        return None

    def _format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Format semantic search results for LLM context.

        Args:
            results: List of search result dictionaries

        Returns:
            Formatted string
        """
        if not results:
            return ""

        formatted = []
        for i, result in enumerate(results, 1):
            file_path = result.get("file_path", "unknown")
            content = result.get("content", "")[:500]  # Limit content length
            score = result.get("score", 0)
            formatted.append(f"{i}. {file_path} (relevance: {score:.2f})\n{content}")

        return "\n\n".join(formatted)

    def _get_channel_for_repo(self, repo: str) -> Optional[str]:
        """Get channel ID for a repository.

        Args:
            repo: Repository identifier

        Returns:
            Channel ID or None if not found
        """
        state = self.agent.load_state()
        channels = state.get("channels", {})

        for channel_id, channel_config in channels.items():
            if channel_config.get("repo") == repo:
                return channel_id

        return None

    def _check_new_md_files(
        self, channel_id: str, repo: str, repo_path: Path, watcher_state: Dict[str, Any]
    ) -> None:
        """Check for new .md files in repository.

        Args:
            channel_id: Slack channel ID
            repo: Repository identifier
            repo_path: Path to repository
            watcher_state: Watcher state dictionary (modified in place)
        """
        repo_key = f"{channel_id}:{repo}"

        # Get list of known .md files
        known_md_files = set(
            watcher_state.get("repos", {}).get(repo_key, {}).get("known_md_files", [])
        )

        # Find all .md files in repository
        current_md_files: Set[str] = set()
        try:
            for md_file in repo_path.rglob("*.md"):
                if md_file.is_file():
                    rel_path = str(md_file.relative_to(repo_path))
                    current_md_files.add(rel_path)
        except Exception as e:
            logger.error(f"Error scanning for .md files in {repo}: {e}")
            return

        # Find new .md files
        new_md_files = current_md_files - known_md_files

        if new_md_files:
            # Send brief title to channel
            title_message = f"📄 *New documentation files detected in {repo}*"
            thread_ts = self._send_slack_message(channel_id, title_message)

            if thread_ts:
                # Send file list in thread
                detail_parts = []
                for md_file in sorted(new_md_files):
                    detail_parts.append(f"  • `{md_file}`")
                detail_message = "\n".join(detail_parts)
                self._send_slack_message(channel_id, detail_message, thread_ts=thread_ts)

        # Update known .md files
        if repo_key not in watcher_state.get("repos", {}):
            watcher_state.setdefault("repos", {})[repo_key] = {}
        watcher_state["repos"][repo_key]["known_md_files"] = list(current_md_files)

    def _send_slack_message(
        self, channel_id: str, message: str, thread_ts: Optional[str] = None
    ) -> Optional[str]:
        """Send message to Slack channel.

        Args:
            channel_id: Slack channel ID
            message: Message text to send
            thread_ts: Optional thread timestamp to reply in thread

        Returns:
            Message timestamp (ts) if successful, None otherwise
        """
        try:
            kwargs = {"channel": channel_id, "text": message}
            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            response = self.slack_client.chat_postMessage(**kwargs)
            ts = response.get("ts")
            if thread_ts:
                logger.info(f"Sent thread reply to channel {channel_id} in thread {thread_ts}")
            else:
                logger.info(f"Sent notification to channel {channel_id}: {ts}")
            return ts
        except SlackApiError as e:
            logger.error(f"Error sending Slack message to {channel_id}: {e.response.get('error')}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending Slack message: {e}", exc_info=True)
            return None

    def _load_watcher_state(self) -> Dict[str, Any]:
        """Load watcher state from file.

        Returns:
            Watcher state dictionary
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    return state
            except json.JSONDecodeError:
                logger.error(f"Failed to parse watcher state file {self.state_file}")

        return {"repos": {}}

    def _save_watcher_state(self, state: Dict[str, Any]) -> None:
        """Save watcher state to file.

        Args:
            state: Watcher state dictionary
        """
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save watcher state: {e}")
