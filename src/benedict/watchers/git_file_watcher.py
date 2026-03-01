"""Git File Watcher

Background service that monitors repositories for new commits and new .md files,
sending notifications to Slack channels.
"""

import json
import logging
import os
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

# Exclusion directories and patterns (shared constant)
_EXCLUDE_DIRS = {
    ".venv",
    "venv",
    ".virtualenv",
    "virtualenv",
    "env",
    ".env",
    "__pycache__",
    ".pytest_cache",
    "pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".node_modules",
    "dist",
    "build",
    ".build",
    "site-packages",
    ".git",
}

_EXCLUDE_PATTERNS = [".egg-info", ".dist-info"]


def _should_exclude_md_file(file_path: str) -> bool:
    """Check if an .md file path should be excluded.
    
    Args:
        file_path: Relative file path from repo root
        
    Returns:
        True if file should be excluded, False otherwise
    """
    path_parts = Path(file_path).parts
    path_str = str(file_path).lower()
    
    # Check if any part matches excluded directories (exact match)
    for part in path_parts:
        if part in _EXCLUDE_DIRS:
            logger.debug(f"Excluding {file_path}: part '{part}' matches excluded directory")
            return True
    
    # Check if path contains excluded directory names anywhere (case-insensitive)
    # This catches nested venv directories like examples/project/venv/...
    for excluded_dir in _EXCLUDE_DIRS:
        if excluded_dir.lower() in path_str:
            logger.debug(f"Excluding {file_path}: contains '{excluded_dir}' in path")
            return True
    
    # Check if any part matches exclusion patterns
    for part in path_parts:
        for pattern in _EXCLUDE_PATTERNS:
            if pattern in part:
                logger.debug(f"Excluding {file_path}: part '{part}' matches pattern '{pattern}'")
                return True
    
    # Exclude LICENSE.md files (case-insensitive)
    file_name = Path(file_path).name.lower()
    if file_name == "license.md":
        logger.debug(f"Excluding {file_path}: LICENSE.md file")
        return True
    
    return False


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

        # Get last checked commit hash for this repo
        repo_key = f"{channel_id}:{repo}"
        last_commit_hash = watcher_state.get("repos", {}).get(repo_key, {}).get("last_commit_hash")

        # Get current HEAD commit hash
        current_commit_hash = self._get_current_commit_hash(repo_path)

        if not current_commit_hash:
            logger.debug(f"No commits found for repo {repo}")
            return

        # Check for new commits by comparing commit hashes
        if last_commit_hash:
            if current_commit_hash != last_commit_hash:
                # New commit detected - use commit hashes for diff
                logger.info(f"New commit detected in {repo}: {last_commit_hash[:8]} -> {current_commit_hash[:8]}")
                self._handle_new_commit(channel_id, repo, repo_path, last_commit_hash, current_commit_hash, watcher_state)
        else:
            # First time checking - initialize but don't notify
            logger.info(f"Initializing watcher for repo {repo} (first check, commit: {current_commit_hash[:8]})")

        # Update last checked commit hash
        if repo_key not in watcher_state.get("repos", {}):
            watcher_state.setdefault("repos", {})[repo_key] = {}
        watcher_state["repos"][repo_key]["last_commit_hash"] = current_commit_hash
        # Also store commit time for reference
        current_commit_time = self._get_commit_time(repo_path, current_commit_hash)
        if current_commit_time:
            watcher_state["repos"][repo_key]["last_commit_time"] = current_commit_time.isoformat()

        # Check for new .md files
        self._check_new_md_files(channel_id, repo, repo_path, watcher_state)

    def _handle_new_commit(
        self,
        channel_id: str,
        repo: str,
        repo_path: Path,
        from_commit_hash: str,
        to_commit_hash: str,
        watcher_state: Dict[str, Any],
    ) -> None:
        """Handle detection of a new commit.

        Args:
            channel_id: Slack channel ID
            repo: Repository identifier
            repo_path: Path to repository
            from_commit_hash: Previous commit hash
            to_commit_hash: Current commit hash
            watcher_state: Watcher state dictionary
        """
        # Get name-status diff to parse changed files
        name_status_diff = self._get_diff_between_commits(repo_path, from_commit_hash, to_commit_hash)
        
        # Parse diff to get changed files
        changed_files = self._parse_diff_files(name_status_diff)
        
        added_files = changed_files.get("added", [])
        modified_files = changed_files.get("modified", [])
        deleted_files = changed_files.get("deleted", [])
        
        # Get full diff (with content) for patch file
        diff_output = self._get_full_diff_between_commits(repo_path, from_commit_hash, to_commit_hash)

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

    def _get_current_commit_hash(self, repo_path: Path) -> Optional[str]:
        """Get current HEAD commit hash.

        Args:
            repo_path: Path to repository

        Returns:
            Commit hash string or None if not available
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            commit_hash = result.stdout.strip()
            return commit_hash if commit_hash else None
        except subprocess.CalledProcessError:
            return None
        except Exception as e:
            logger.debug(f"Error getting commit hash: {e}")
            return None

    def _get_commit_time(self, repo_path: Path, commit_hash: str) -> Optional[datetime]:
        """Get commit timestamp for a specific commit hash.

        Args:
            repo_path: Path to repository
            commit_hash: Commit hash

        Returns:
            Commit datetime or None if not available
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ct", commit_hash],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout.strip():
                timestamp = int(result.stdout.strip())
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (subprocess.CalledProcessError, ValueError):
            pass
        return None

    def _get_diff_between_commits(self, repo_path: Path, from_hash: str, to_hash: str) -> str:
        """Get git diff --name-status between two commit hashes.

        Args:
            repo_path: Path to repository
            from_hash: Previous commit hash
            to_hash: Current commit hash

        Returns:
            Git diff --name-status output as string
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "--name-status", from_hash, to_hash],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error getting diff between commits: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error getting diff: {e}", exc_info=True)
            return ""

    def _get_full_diff_between_commits(self, repo_path: Path, from_hash: str, to_hash: str) -> str:
        """Get full git diff (with content) between two commit hashes.

        Args:
            repo_path: Path to repository
            from_hash: Previous commit hash
            to_hash: Current commit hash

        Returns:
            Full git diff output as string
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", from_hash, to_hash],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error getting full diff between commits: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error getting full diff: {e}", exc_info=True)
            return ""

    def _parse_diff_files(self, diff_output: str) -> Dict[str, List[str]]:
        """Parse git diff --name-status output to extract changed files.

        Git diff --name-status format:
        A <file>  - Added
        M <file>  - Modified
        D <file>  - Deleted

        Args:
            diff_output: Git diff --name-status output

        Returns:
            Dictionary with 'added', 'modified', 'deleted' lists
        """
        added = []
        modified = []
        deleted = []

        for line in diff_output.strip().split("\n"):
            if not line.strip():
                continue

            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue

            status = parts[0].strip()
            file_path = parts[1].strip()

            if status.startswith("A"):
                added.append(file_path)
            elif status.startswith("M"):
                modified.append(file_path)
            elif status.startswith("D"):
                deleted.append(file_path)

        return {"added": added, "modified": modified, "deleted": deleted}

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

        # Get list of known .md files and filter out excluded ones
        raw_known_md_files = watcher_state.get("repos", {}).get(repo_key, {}).get("known_md_files", [])
        logger.debug(f"Raw known .md files for {repo}: {len(raw_known_md_files)}")
        
        # Filter out excluded files from known files (cleanup old state)
        known_md_files = set()
        excluded_from_known = 0
        for file_path in raw_known_md_files:
            if _should_exclude_md_file(file_path):
                excluded_from_known += 1
                logger.debug(f"Excluding known file: {file_path}")
            else:
                known_md_files.add(file_path)
        
        if excluded_from_known > 0:
            logger.info(f"Filtered out {excluded_from_known} excluded files from known files for {repo}")

        # Find all .md files in repository (excluding virtual environments and build directories)
        # Use a custom walker that skips excluded directories during traversal
        current_md_files: Set[str] = set()
        try:
            def _should_skip_directory(dir_path: Path) -> bool:
                """Check if a directory should be skipped during traversal.
                
                Args:
                    dir_path: Path to directory (absolute path from os.walk)
                    
                Returns:
                    True if directory should be skipped, False otherwise
                """
                # Get relative path from repo root
                try:
                    rel_path = dir_path.relative_to(repo_path)
                except ValueError:
                    # If not under repo_path, check the directory name itself
                    dir_name = dir_path.name
                    return dir_name in _EXCLUDE_DIRS or any(pattern in dir_name for pattern in _EXCLUDE_PATTERNS)
                
                # Check if directory name matches excluded directories
                dir_name = dir_path.name
                if dir_name in _EXCLUDE_DIRS:
                    return True
                
                # Check if any part of the relative path matches excluded directories
                path_parts = rel_path.parts
                for part in path_parts:
                    if part in _EXCLUDE_DIRS:
                        return True
                
                # Check if path contains excluded directory names (case-insensitive)
                rel_path_str_lower = str(rel_path).lower()
                for excluded_dir in _EXCLUDE_DIRS:
                    if excluded_dir.lower() in rel_path_str_lower:
                        return True
                
                # Check if directory name matches exclusion patterns
                for pattern in _EXCLUDE_PATTERNS:
                    if pattern in dir_name:
                        return True
                
                return False
            
            # Walk directory tree, skipping excluded directories
            for root, dirs, files in os.walk(repo_path):
                root_path = Path(root)
                
                # Filter out excluded directories from dirs list (modifies in place)
                # This prevents os.walk from descending into excluded directories
                original_dirs = dirs[:]
                dirs[:] = [d for d in dirs if not _should_skip_directory(root_path / d)]
                
                # Log if we're skipping any directories
                skipped_dirs = set(original_dirs) - set(dirs)
                if skipped_dirs:
                    logger.debug(f"Skipping excluded directories in {root_path}: {skipped_dirs}")
                
                # Check files in current directory
                for file_name in files:
                    if not file_name.endswith('.md'):
                        continue
                    
                    file_path = root_path / file_name
                    if not file_path.is_file():
                        continue
                    
                    # Get relative path from repo root
                    try:
                        rel_path = file_path.relative_to(repo_path)
                    except ValueError:
                        # File is not under repo_path, skip it
                        continue
                    
                    rel_path_str = str(rel_path)
                    
                    # Final safety check: use the exclusion function to catch any files that slipped through
                    if _should_exclude_md_file(rel_path_str):
                        logger.debug(f"Excluding .md file: {rel_path_str}")
                        continue
                    
                    current_md_files.add(rel_path_str)
        except Exception as e:
            logger.error(f"Error scanning for .md files in {repo}: {e}")
            return

        # Find new .md files
        new_md_files = current_md_files - known_md_files
        logger.debug(f"New .md files before exclusion check: {len(new_md_files)}")
        
        # Safety check: filter out any excluded files that might have slipped through
        excluded_from_new = 0
        filtered_new_md_files = set()
        for f in new_md_files:
            if _should_exclude_md_file(f):
                excluded_from_new += 1
                logger.warning(f"Excluded file slipped through to new_md_files: {f}")
            else:
                filtered_new_md_files.add(f)
        
        new_md_files = filtered_new_md_files
        
        if excluded_from_new > 0:
            logger.warning(f"Filtered out {excluded_from_new} excluded files from new_md_files for {repo}")

        # Only notify if there are actually new files (not first run)
        # On first run, known_md_files will be empty, so we'll silently initialize
        if new_md_files and known_md_files:
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

        # Update known .md files (always update, even on first run)
        # Filter out excluded files before saving (cleanup)
        filtered_current_md_files = [f for f in current_md_files if not _should_exclude_md_file(f)]
        
        if repo_key not in watcher_state.get("repos", {}):
            watcher_state.setdefault("repos", {})[repo_key] = {}
        watcher_state["repos"][repo_key]["known_md_files"] = filtered_current_md_files
        
        if len(filtered_current_md_files) != len(current_md_files):
            logger.info(f"Cleaned up watcher state: removed {len(current_md_files) - len(filtered_current_md_files)} excluded files from state for {repo}")

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
