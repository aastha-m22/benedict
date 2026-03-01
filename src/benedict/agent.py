"""Repository Agent

Core agent logic for handling repository-scoped conversations.
"""

import json
import logging
import os
import re
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from benedict.protocols import (
    LLM,
    RepoReader,
    SemanticIndexer,
    ConversationRepository,
    ConversationHistoryIndexer,
)
from benedict.models import ConversationManager
from benedict.utils import build_context
from benedict.utils.context import build_architect_context
from benedict.architect.prompts import ARCHITECT_SYSTEM_PROMPT
from benedict.workspace import WorkspaceManager, ActionLogger
from benedict.metadata import MetadataGenerator
from benedict.method import MethodReader, MethodWriter
from benedict.commands import (
    ToolRegistry,
    create_tool_registry_from_method_data,
    LLMCommandClassifier,
)

logger = logging.getLogger(__name__)

# Constants
REPO_PATTERN = re.compile(r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)")


class RepoAgent:
    """Repository-scoped agent with LLM and repository access."""

    def __init__(
        self,
        state_file: str = "state.json",
        llm: Optional[LLM] = None,
        repo_reader: Optional[RepoReader] = None,
        semantic_indexer: Optional[SemanticIndexer] = None,
        conversation_repository: Optional[ConversationRepository] = None,
        workspace_manager: Optional[WorkspaceManager] = None,
        conversation_history_indexer: Optional[ConversationHistoryIndexer] = None,
    ):
        """Initialize repository agent.

        Args:
            state_file: Path to state JSON file (used for conversation repository if not provided)
            llm: Optional LLM instance for intelligent responses
            repo_reader: Optional repository reader instance
            semantic_indexer: Optional semantic indexer for intelligent file selection
            conversation_repository: Optional conversation repository (created from state_file if None)
            workspace_manager: Optional workspace manager for workspace operations
            conversation_history_indexer: Optional conversation history indexer for Slack history
        """
        self.state_file = Path(state_file)
        self.llm = llm
        self.repo_reader = repo_reader
        self.semantic_indexer = semantic_indexer
        self.workspace_manager = workspace_manager
        self.conversation_history_indexer = conversation_history_indexer
        self.metadata_generator = MetadataGenerator() if workspace_manager else None
        self.method_reader = MethodReader() if workspace_manager else None
        self.method_writer = MethodWriter() if workspace_manager else None
        
        # LLM-based classifier components
        self.tool_registry = None
        self.llm_classifier = None
        if workspace_manager and llm:
            from benedict.metadata import MetadataReader
            metadata_reader = MetadataReader()
            # Tool registry will be created per-repo as needed
            # (to get method/metadata data for enhanced schemas)

        # Create conversation repository if not provided
        if conversation_repository is None:
            from benedict.protocols.conversation_repository import create_conversation_repository

            conversation_repository = create_conversation_repository(
                provider="json", state_file=state_file
            )

        self.conversation_manager = ConversationManager(conversation_repository)
        logger.info(f"Initialized RepoAgent with state_file={state_file}")

    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    logger.debug(f"Loaded state with {len(state.get('channels', {}))} channels")
                    return state
            except json.JSONDecodeError:
                logger.error(f"Failed to parse {self.state_file}, creating new state")

        return {"channels": {}}

    def save_state(self, state: Dict[str, Any]) -> None:
        """Persist state to JSON file."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            logger.debug(f"Saved state with {len(state.get('channels', {}))} channels")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def get_channel_repo(self, channel_id: str) -> Optional[str]:
        """Get repository associated with channel."""
        state = self.load_state()
        channel_config = state.get("channels", {}).get(channel_id)
        if channel_config:
            return channel_config.get("repo")
        return None

    def set_channel_repo(self, channel_id: str, repo: str, user_id: str) -> None:
        """Associate repository with channel."""
        state = self.load_state()
        if "channels" not in state:
            state["channels"] = {}

        state["channels"][channel_id] = {
            "repo": repo,
            "onboarded_at": datetime.utcnow().isoformat() + "Z",
            "onboarded_by": user_id,
        }
        self.save_state(state)
        logger.info(f"Onboarded channel {channel_id} to repo {repo}")

    def remove_channel_repo(self, channel_id: str) -> None:
        """Remove repository association from channel (offboard)."""
        state = self.load_state()
        if "channels" in state and channel_id in state["channels"]:
            repo = state["channels"][channel_id].get("repo", "unknown")
            del state["channels"][channel_id]
            self.save_state(state)
            logger.info(f"Offboarded channel {channel_id} from repo {repo}")
        else:
            logger.warning(f"Channel {channel_id} was not onboarded")

    def get_architect_channel(self) -> Optional[str]:
        """Get architect channel ID."""
        state = self.load_state()
        architect_config = state.get("architect", {})
        return architect_config.get("channel_id")

    def set_architect_channel(self, channel_id: str, user_id: str) -> None:
        """Mark channel as architect channel."""
        state = self.load_state()
        if "architect" not in state:
            state["architect"] = {}
        state["architect"]["channel_id"] = channel_id
        state["architect"]["onboarded_at"] = datetime.utcnow().isoformat() + "Z"
        state["architect"]["onboarded_by"] = user_id
        self.save_state(state)
        logger.info(f"Onboarded architect channel {channel_id}")

    def handle_onboard(self, channel_id: str, user_id: str, text: str) -> Tuple[bool, str]:
        """Handle onboard command.

        Returns:
            Tuple of (success, message)
        """
        repo = self.extract_repo_name(text)

        if not repo:
            return (
                False,
                "⚠️ Repository Not Found\n\n"
                "I couldn't find a repository name in your message.\n\n"
                "*Next steps:*\n"
                "• Use format: `@agent onboard repo foo/bar`\n"
                "• Or: `@agent this channel is for foo/bar`",
            )

        # Create workspace and add resource if workspace_manager is available
        if self.workspace_manager:
            try:
                workspace_path = self.workspace_manager.create_workspace(channel_id)
                action_logger = ActionLogger(workspace_path)

                # Try to resolve repository path
                # Check multiple possible locations: absolute paths, org/repo structure, or just repo name
                repo_source = None
                
                # Get configured repository source directories from environment variable
                # Format: comma-separated paths, e.g., "/Users/name/Projects,/opt/repos"
                repo_source_dirs_env = os.environ.get("BENEDICT_REPO_SOURCE_DIRS", "")
                repo_source_dirs = []
                
                if repo_source_dirs_env:
                    # Parse comma-separated paths
                    for dir_path in repo_source_dirs_env.split(","):
                        dir_path = dir_path.strip()
                        if dir_path:
                            repo_source_dirs.append(Path(dir_path))
                else:
                    # Default fallback paths if not configured
                    repo_source_dirs = [
                        Path.home() / "Projects",  # Default: ~/Projects
                    ]

                # Build list of possible paths to check
                possible_paths = [
                    Path(repo),  # Try as-is (might be absolute path like /Users/name/Projects/repo)
                ]
                
                # Add paths from configured source directories
                for source_dir in repo_source_dirs:
                    if source_dir.exists() and source_dir.is_dir():
                        # Full org/repo path: {source_dir}/mkarots/hookedllm
                        possible_paths.append(source_dir / repo)
                        # Just repo name: {source_dir}/hookedllm
                        possible_paths.append(source_dir / repo.split("/")[-1])
                
                # Add current directory as fallback
                possible_paths.append(Path.cwd() / repo.split("/")[-1])

                # Try each path
                tried_paths = []
                for path in possible_paths:
                    tried_paths.append(str(path))
                    if path.exists() and path.is_dir():
                        repo_source = path
                        logger.info(f"Found repository at: {repo_source}")
                        break

                if not repo_source:
                    # Build error message with tried paths
                    tried_paths_str = "\n".join([f"• `{p}`" for p in tried_paths])
                    return (
                        False,
                        f"⚠️ Repository Not Found\n\n"
                        f"Could not find repository `{repo}` locally.\n\n"
                        f"*Tried locations:*\n"
                        f"{tried_paths_str}\n\n"
                        f"*Next steps:*\n"
                        f"• Provide the full path to the repository\n"
                        f"• Configure `BENEDICT_REPO_SOURCE_DIRS` environment variable\n"
                        f"• Example: `@agent onboard repo /Users/yourname/Projects/hookedllm`",
                    )

                # Add resource to workspace
                workspace_resource_path = self.workspace_manager.add_resource(
                    context_id=channel_id,
                    resource_type="repository",
                    source_path=str(repo_source),
                    name=repo,
                    content_type="code",
                )

                # Log action
                action_logger.log_action(
                    action="symlink_repository",
                    content_type="code",
                    resource=repo,
                    source=str(repo_source),
                    workspace_path=workspace_resource_path,
                )

                # Generate initial metadata
                if self.metadata_generator:
                    try:
                        repo_path = workspace_path / repo
                        if repo_path.exists():
                            self.metadata_generator.generate_and_write(
                                repo_path, content_type="code"
                            )
                            action_logger.log_action(
                                action="generate_metadata", content_type="code", resource=repo
                            )
                    except Exception as e:
                        logger.warning(f"Error generating initial metadata for {repo}: {e}")

                # Create default method file if directory is empty or method file doesn't exist
                if self.method_writer:
                    try:
                        repo_path = workspace_path / repo
                        if repo_path.exists():
                            method_file = repo_path / ".benedict.method.yaml"
                            
                            # Check if directory is empty (no files except .git, .metadata.benedict, etc.)
                            is_empty = self._is_directory_empty(repo_path)
                            
                            # Create method file if directory is empty or method file doesn't exist
                            # If directory is empty, always create default method file
                            if is_empty or not method_file.exists():
                                method_data = self._create_default_method_data()
                                self.method_writer.write_method(repo_path, method_data)
                                action_logger.log_action(
                                    action="create_method_file_auto",
                                    content_type="method",
                                    resource=repo,
                                    note="Auto-created during onboarding"
                                )
                                logger.info(f"Auto-created default method file for {repo}")
                    except Exception as e:
                        logger.warning(f"Error auto-creating method file for {repo}: {e}")

                # Index Slack conversation history from the beginning of the channel
                if self.conversation_history_indexer:
                    try:
                        logger.info(
                            f"Indexing Slack conversation history for channel {channel_id} "
                            f"from the beginning"
                        )
                        self.conversation_history_indexer.index_conversations(
                            context_id=channel_id,
                            workspace_path=workspace_path,
                            since=None,  # Index from the beginning (no date filter)
                            semantic_indexer=self.semantic_indexer,
                        )
                        action_logger.log_action(
                            action="index_slack_history",
                            content_type="conversation",
                            resource=channel_id,
                            note="Initial indexing from channel start",
                        )
                        logger.info(
                            f"Successfully indexed Slack conversation history for channel {channel_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Error indexing Slack conversation history for channel {channel_id}: {e}",
                            exc_info=True,
                        )
                        # Don't fail onboarding if history indexing fails

            except Exception as e:
                logger.error(f"Error setting up workspace for {repo}: {e}", exc_info=True)
                return (
                    False,
                    f"⚠️ Workspace Setup Error\n\n"
                    f"Error setting up workspace: {str(e)}\n\n"
                    f"*Next steps:*\n"
                    f"• Check repository path and permissions\n"
                    f"• Try again or contact support",
                )

        self.set_channel_repo(channel_id, repo, user_id)
        
        # Build success message
        message = (
            f"✅ Onboarded! This channel is now linked to `{repo}`.\n"
            f"I'll remember this repo for all our conversations here.\n"
        )
        
        return True, message

    def handle_offboard(self, channel_id: str, user_id: str) -> Tuple[bool, str]:
        """Handle offboard command to remove channel from repository.
        
        Args:
            channel_id: Slack channel ID
            user_id: User ID who requested offboarding
            
        Returns:
            Tuple of (success, message)
        """
        state = self.load_state()
        channels = state.get("channels", {})
        
        if channel_id not in channels:
            return (
                False,
                "⚠️ Channel Not Onboarded\n\n"
                "This channel is not currently onboarded to any repository.\n\n"
                "*To onboard:*\n"
                "• Use `@agent onboard repo your-org/your-repo`",
            )
        
        # Get repo info before removing
        channel_config = channels[channel_id]
        repo = channel_config.get("repo", "unknown")
        
        # Remove channel from state
        self.remove_channel_repo(channel_id)
        
        # Build success message
        message = (
            f"✅ Offboarded! This channel is no longer linked to `{repo}`.\n"
            f"I'll stop monitoring this repository for this channel.\n\n"
            f"*Note:* Workspace data and conversation history are preserved.\n"
            f"To re-onboard, use `@agent onboard repo {repo}`"
        )
        
        return True, message
        
        if self.conversation_history_indexer:
            message += (
                f"\n📚 I'm indexing all conversation history from this channel "
                f"so I can reference past discussions and summarize them."
            )
        
        message += f"\n\nTry: `@agent status` to see the details."
        
        return (True, message)

    def handle_status(self, channel_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Handle status command.

        Returns:
            Tuple of (success, message, channel_config)
        """
        state = self.load_state()
        channel_config = state.get("channels", {}).get(channel_id)

        if not channel_config:
            return (
                False,
                "⚠️ Not Onboarded\n\n"
                "This channel hasn't been onboarded yet.\n\n"
                "*Next steps:*\n"
                "• Use `@agent onboard repo your-org/your-repo` to get started",
                None,
            )

        repo = channel_config.get("repo")
        onboarded_at = channel_config.get("onboarded_at", "Unknown")
        onboarded_by = channel_config.get("onboarded_by", "Unknown")

        # Format timestamp
        try:
            dt = datetime.fromisoformat(onboarded_at.replace("Z", "+00:00"))
            formatted_time = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            formatted_time = onboarded_at

        message = (
            f"📊 *Channel Status*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔗 Repository: `{repo}`\n"
            f"⏰ Onboarded: {formatted_time}\n"
            f"👤 By: <@{onboarded_by}>"
        )

        return (True, message, channel_config)

    def is_method_update_request(self, text: str) -> bool:
        """Detect if text contains a method file update request.

        Args:
            text: User message text

        Returns:
            True if method file update is requested
        """
        text_lower = text.lower()
        
        # Explicit update requests
        explicit_patterns = [
            "update method file",
            "update .method",
            "change method file",
            "modify method file",
            "update phase",
            "change phase",
            "update concern",
            "change concern",
            "update pc",
            "change pc",
            "update program counter",
        ]
        
        for pattern in explicit_patterns:
            if pattern in text_lower:
                return True
        
        # Implicit requests (phase/concern updates)
        if any(word in text_lower for word in ["phase", "concern", "iteration", "step"]) and any(
            word in text_lower for word in ["update", "change", "set", "modify", "to"]
        ):
            return True
        
        return False

    def is_explicit_update_confirmation(self, text: str) -> bool:
        """Detect if text is an explicit confirmation to update without asking.

        Args:
            text: User message text

        Returns:
            True if explicit update confirmation
        """
        text_lower = text.lower()
        
        explicit_confirmations = [
            "update method file",
            "yes, update it",
            "yes update",
            "go ahead",
            "proceed",
            "do it",
            "update it",
        ]
        
        return any(confirmation in text_lower for confirmation in explicit_confirmations)

    def handle_method_update(
        self, channel_id: str, text: str, thread_ts: str, repo: str
    ) -> Tuple[bool, str]:
        """Handle method file update request.

        Args:
            channel_id: Slack channel ID
            text: User message text
            thread_ts: Thread timestamp
            repo: Repository name

        Returns:
            Tuple of (success, message)
        """
        if not self.workspace_manager or not self.method_reader or not self.method_writer:
            return (
                False,
                "⚠️ Method file updates not available\n\n"
                "Method file reading/writing requires workspace manager to be configured.",
            )

        workspace_path = self.workspace_manager.get_workspace_path(channel_id)
        repo_method_path = workspace_path / repo

        # Read current method file
        method_data = self.method_reader.read_method(repo_method_path)
        if not method_data:
            return (
                False,
                f"⚠️ Method file not found\n\n"
                f"No `.benedict.method.yaml` file found in repository `{repo}`.\n\n"
                f"*Next steps:*\n"
                f"• Create a `.benedict.method.yaml` file in the repository root",
            )

        # Try to parse update request from current text
        updates = self._parse_method_updates(text, method_data)
        
        # If no updates in current text but it's a confirmation, check recent messages
        if not updates and self.is_explicit_update_confirmation(text):
            # Get conversation to check recent messages
            conversation = self.conversation_manager.get_conversation(
                thread_ts=thread_ts, channel_id=channel_id, repo=repo
            )
            recent_messages = conversation.get_messages(max_messages=5)
            # Look for update requests in recent messages
            for msg in reversed(recent_messages):
                if msg.role == "user":
                    parsed = self._parse_method_updates(msg.content, method_data)
                    if parsed:
                        updates = parsed
                        break
        
        # Check if this is an explicit confirmation (skip confirmation prompt)
        if self.is_explicit_update_confirmation(text) and updates:
            # Apply updates directly
            try:
                self._apply_method_updates(repo_method_path, updates)
                return (
                    True,
                    f"✅ *Method file updated*\n\n"
                    f"I've updated the method file with your requested changes.",
                )
            except Exception as e:
                logger.error(f"Error updating method file: {e}", exc_info=True)
                return (
                    False,
                    f"⚠️ Error updating method file\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please try again or check the method file format.",
                )
        
        # If we parsed updates, show what will change
        if updates:
            changes_text = self._format_method_changes(updates, method_data)
            return (
                True,
                f"📝 *Method File Update*\n\n"
                f"{changes_text}\n\n"
                f"*Confirm update?*\n"
                f"Say 'update method file' or 'yes, update it' to apply these changes.",
            )

        # Show current state and ask for confirmation
        method = method_data.get("method", {})
        pc = method.get("pc", {})
        concerns = method.get("concerns", {})

        current_state = f"*Current Method File State:*\n"
        current_state += f"• Phase: {pc.get('phase', 'N/A')}\n"
        current_state += f"• Iteration: {pc.get('iteration', 'N/A')}\n"
        current_state += f"• Step: {pc.get('step', 'N/A')}\n"
        if concerns:
            current_state += f"\n*Current Concerns:*\n"
            for concern, state in concerns.items():
                current_state += f"• {concern}: {state}\n"

        return (
            True,
            f"📝 *Method File Update Request*\n\n"
            f"{current_state}\n"
            f"*What would you like to update?*\n\n"
            f"Please specify:\n"
            f"• What to change (phase, iteration, step, or concern state)\n"
            f"• The new value\n\n"
            f"Example: 'set phase to review' or 'set documentation concern to complete'\n\n"
            f"Say 'update method file' to proceed without confirmation.",
        )

    def _parse_method_updates(self, text: str, method_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse method file update requests from text.

        Args:
            text: User message text
            method_data: Current method data

        Returns:
            Dictionary of updates to apply
        """
        text_lower = text.lower()
        updates = {}
        
        # Parse phase updates
        phase_patterns = [
            (r"set phase to (\w+)", "phase"),
            (r"phase is (\w+)", "phase"),
            (r"change phase to (\w+)", "phase"),
            (r"update phase to (\w+)", "phase"),
        ]
        for pattern, key in phase_patterns:
            match = re.search(pattern, text_lower)
            if match:
                updates["pc"] = updates.get("pc", {})
                updates["pc"]["phase"] = match.group(1)
        
        # Parse iteration updates
        iteration_patterns = [
            (r"set iteration to (\d+)", "iteration"),
            (r"iteration is (\d+)", "iteration"),
            (r"change iteration to (\d+)", "iteration"),
        ]
        for pattern, key in iteration_patterns:
            match = re.search(pattern, text_lower)
            if match:
                updates["pc"] = updates.get("pc", {})
                updates["pc"]["iteration"] = int(match.group(1))
        
        # Parse step updates
        step_patterns = [
            (r"set step to (\w+)", "step"),
            (r"step is (\w+)", "step"),
            (r"change step to (\w+)", "step"),
        ]
        for pattern, key in step_patterns:
            match = re.search(pattern, text_lower)
            if match:
                updates["pc"] = updates.get("pc", {})
                updates["pc"]["step"] = match.group(1)
        
        # Parse concern updates
        concern_patterns = [
            (r"set (\w+) (?:concern )?to (\w+)", "concern"),
            (r"(\w+) (?:concern )?is (\w+)", "concern"),
            (r"change (\w+) (?:concern )?to (\w+)", "concern"),
        ]
        for pattern, key in concern_patterns:
            match = re.search(pattern, text_lower)
            if match:
                concern_name = match.group(1)
                concern_state = match.group(2)
                # Validate concern name exists in method file
                method = method_data.get("method", {})
                concerns = method.get("concerns", {})
                concern_definitions = method.get("concern_definitions", {})
                if concern_name in concerns or concern_name in concern_definitions:
                    updates["concerns"] = updates.get("concerns", {})
                    updates["concerns"][concern_name] = concern_state
        
        return updates

    def _format_method_changes(self, updates: Dict[str, Any], current_data: Dict[str, Any]) -> str:
        """Format method changes for display.

        Args:
            updates: Dictionary of updates
            current_data: Current method data

        Returns:
            Formatted string showing changes
        """
        method = current_data.get("method", {})
        pc = method.get("pc", {})
        concerns = method.get("concerns", {})
        
        changes = []
        
        if "pc" in updates:
            pc_updates = updates["pc"]
            if "phase" in pc_updates:
                old = pc.get("phase", "N/A")
                new = pc_updates["phase"]
                changes.append(f"• Phase: `{old}` → `{new}`")
            if "iteration" in pc_updates:
                old = pc.get("iteration", "N/A")
                new = pc_updates["iteration"]
                changes.append(f"• Iteration: `{old}` → `{new}`")
            if "step" in pc_updates:
                old = pc.get("step", "N/A")
                new = pc_updates["step"]
                changes.append(f"• Step: `{old}` → `{new}`")
        
        if "concerns" in updates:
            concern_updates = updates["concerns"]
            for concern, new_state in concern_updates.items():
                old = concerns.get(concern, "N/A")
                changes.append(f"• {concern.capitalize()}: `{old}` → `{new_state}`")
        
        if not changes:
            return "*No changes detected.*"
        
        return "*Proposed changes:*\n" + "\n".join(changes)

    def _apply_method_updates(self, directory: Path, updates: Dict[str, Any]) -> None:
        """Apply method file updates.

        Args:
            directory: Directory containing method file
            updates: Dictionary of updates to apply
        """
        if not self.method_writer:
            raise ValueError("MethodWriter not available")
        
        # Build update structure
        method_updates = {"method": {}}
        
        if "pc" in updates:
            method_updates["method"]["pc"] = updates["pc"]
        if "concerns" in updates:
            method_updates["method"]["concerns"] = updates["concerns"]
        
        # Apply updates
        self.method_writer.update_method_data(directory, method_updates)

    def _get_method_guidance_message(self, repo: str, repo_path: Path) -> str:
        """Generate guidance message for creating method file.

        Args:
            repo: Repository name
            repo_path: Path to repository in workspace

        Returns:
            Guidance message string
        """
        return (
            f"📋 *Method File Missing*\n\n"
            f"I notice there's no `.benedict.method.yaml` file for `{repo}`.\n\n"
            f"*Why method files matter:*\n"
            f"• Track project phases (conception, design, sprint, review)\n"
            f"• Manage concerns (scope, documentation, development, communication, operations, feedback)\n"
            f"• Define rules and practices for each phase\n"
            f"• Help me understand your project methodology and current state\n"
            f"• Enable better project guidance and phase-aware assistance\n\n"
            f"*I can help you create one!*\n\n"
            f"Just say:\n"
            f"• `create method file` or `generate method file` - I'll guide you through creating one\n"
            f"• `help me create method file` - I'll walk you through it step-by-step\n"
            f"• Or tell me about your project phase and I'll help set it up\n\n"
            f"*What's in a method file?*\n"
            f"A `.benedict.method.yaml` file contains:\n"
            f"• Program Counter (pc): Current phase, iteration, and step\n"
            f"• Concern Definitions: Rules and states for each concern\n"
            f"• Current Concerns: Current state of each concern\n"
            f"• Sequence: Phase definitions with rules and practices\n\n"
            f"Would you like me to help you create one now?"
        )

    def is_create_method_command(self, text: str) -> bool:
        """Detect if text is a request to create method file.

        Args:
            text: User message text

        Returns:
            True if create method is requested
        """
        text_lower = text.lower()
        patterns = [
            "create method file",
            "generate method file",
            "make method file",
            "build method file",
            "help me create method file",
            "create .method",
            "generate .method",
            "setup method file",
            "initialize method file",
        ]
        return any(pattern in text_lower for pattern in patterns)

    def _is_directory_empty(self, directory: Path) -> bool:
        """Check if directory is empty (no regular files, only hidden/system files).
        
        Args:
            directory: Directory path to check
            
        Returns:
            True if directory is empty or only contains hidden/system files
        """
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            return False
        
        # Files/directories to ignore when checking if empty
        ignore_patterns = {".git", ".metadata.benedict", ".benedict.method.yaml", "__pycache__", ".venv", "venv", "node_modules"}
        
        try:
            # Check if directory has any non-ignored files
            for item in directory.iterdir():
                if item.name not in ignore_patterns:
                    # If it's a file, directory is not empty
                    if item.is_file():
                        return False
                    # If it's a directory, check if it has any files (recursively, but limit depth)
                    if item.is_dir() and item.name not in ignore_patterns:
                        # Quick check: see if directory has any files
                        for subitem in item.rglob("*"):
                            if subitem.is_file():
                                rel_path = subitem.relative_to(directory)
                                # Ignore files in ignored directories
                                if not any(part in ignore_patterns for part in rel_path.parts):
                                    return False
                        # Limit recursion depth to avoid performance issues
                        break
            return True
        except Exception as e:
            logger.warning(f"Error checking if directory is empty: {e}")
            return False

    def _create_default_method_data(self) -> Dict[str, Any]:
        """Create default method file data structure.
        
        Returns:
            Dictionary with default method file structure
        """
        return {
                "method": {
                    "pc": {
                        "phase": "conception",
                        "iteration": 1,
                        "step": "define",
                    },
                    "concern_definitions": {
                        "scope": {
                            "description": "the boundary of what the project does and does not do",
                            "states": ["fluid", "narrowing", "locked", "reconsidering"],
                            "rules": [
                                "scope must be explicitly stated in every project",
                                "scope changes are only permitted during conception and review phases",
                                "during sprint, scope is locked — new ideas go to BACKLOG.md",
                                "scope must be defined in terms of what is IN and what is OUT",
                            ],
                        },
                        "documentation": {
                            "description": "all written artifacts that make the project understandable, usable, and maintainable",
                            "states": ["not_started", "drafting", "in_progress", "complete", "stale"],
                            "rules": [
                                "only documented software should be delivered",
                                "documentation gates development — no feature ships without docs",
                                "each project must have at minimum WHY.md, README.md, ROADMAP.md",
                                "documentation must be reviewed for staleness at every review phase",
                                "documentation is a first-class deliverable, not an afterthought",
                            ],
                        },
                        "development": {
                            "description": "all code, configuration, and infrastructure work",
                            "states": ["blocked", "not_started", "prototyping", "active", "stabilising", "complete"],
                            "rules": [
                                "development is not allowed in conception phase",
                                "development in design phase is limited to throwaway prototypes",
                                "development in sprint phase must follow the roadmap — no unplanned work",
                                "development must produce deployable output at the end of each sprint",
                                "development is gated by documentation — build it, then document it, then communicate it",
                            ],
                        },
                        "communication": {
                            "description": "all external-facing announcements, posts, updates, and promotion of the project",
                            "states": ["not_applicable", "pending", "drafting", "published"],
                            "rules": [
                                "every delivered and documented feature must be communicated",
                                "communication is the final step in the sprint loop — it cannot be skipped",
                                "communication is not marketing fluff — it is a factual account of what changed and why",
                                "no communication without documentation — you cannot announce what is not written down",
                                "communication debt is project debt — uncommunicated features are invisible features",
                            ],
                        },
                        "operations": {
                            "description": "all work related to deploying, running, monitoring, and maintaining the project",
                            "states": ["not_applicable", "not_started", "defining", "active", "reviewing"],
                            "rules": [
                                "operations strategy must be defined during design phase",
                                "the project must be in a deployable state at the end of every sprint",
                                "operational health must be assessed during every review phase",
                                "operations includes CI/CD, monitoring, hosting, incident response",
                                "if the project cannot be operated, it cannot be delivered",
                            ],
                        },
                        "feedback": {
                            "description": "all signals — internal or external — about how the project is performing against its goals",
                            "states": ["not_applicable", "not_started", "collecting", "synthesising", "actioned"],
                            "rules": [
                                "feedback must be actively sought, not passively received",
                                "feedback is collected during sprint, synthesised during review",
                                "feedback that challenges scope must be logged and deferred to review phase",
                                "feedback drives the decision at the end of review — next sprint, harden, expand, or kill",
                                "absence of feedback is itself feedback — it means no one is using it",
                            ],
                        },
                    },
                    "concerns": {
                        "scope": "fluid",
                        "documentation": "not_started",
                        "development": "not_started",
                        "communication": "not_applicable",
                        "operations": "not_applicable",
                        "feedback": "not_started",
                    },
                    "sequence": {
                        "conception": {
                            "status": "active",
                            "iteration": 1,
                            "loop": "define → challenge → refine",
                            "exit": "motivation, problem, and scope are stable enough to design against",
                            "addresses": ["motivation", "problem_definition", "scope"],
                            "artifacts": ["WHY.md", "README.md"],
                        },
                        "design": {
                            "status": "pending",
                            "iteration": 0,
                            "loop": "sketch → evaluate → revise",
                            "exit": "technical design and roadmap are concrete enough to build against",
                            "addresses": ["technical_design", "roadmap"],
                            "artifacts": ["SYSTEM_SPEC.md", "ROADMAP.md"],
                        },
                        "sprint": {
                            "status": "pending",
                            "iteration": 0,
                            "loop": "build → document → communicate",
                            "exit": "feature is delivered, documented, and communicated",
                            "addresses": ["development", "documentation", "communication"],
                            "artifacts": ["CHANGELOG.md"],
                        },
                        "review": {
                            "status": "pending",
                            "iteration": 0,
                            "loop": "measure → assess → decide",
                            "exit": "decision made — next sprint, hardening, or expansion",
                            "addresses": ["feedback", "operations"],
                            "artifacts": [],
                        },
                    },
                }
            }

    def handle_create_method(self, channel_id: str, repo: str) -> Tuple[bool, str]:
        """Handle method file creation request.

        Args:
            channel_id: Slack channel ID
            repo: Repository name

        Returns:
            Tuple of (success, message)
        """
        if not self.workspace_manager or not self.method_writer:
            return (
                False,
                "⚠️ Method file creation not available\n\n"
                "Method file creation requires workspace manager to be configured.",
            )

        workspace_path = self.workspace_manager.get_workspace_path(channel_id)
        repo_path = workspace_path / repo

        if not repo_path.exists():
            return (
                False,
                f"⚠️ Repository not found\n\n"
                f"Repository path `{repo_path}` does not exist.\n\n"
                f"*Next steps:*\n"
                f"• Verify the repository is properly onboarded\n"
                f"• Check workspace configuration",
            )

        try:
            # Create default method file structure
            method_data = self._create_default_method_data()

            # Write the method file
            self.method_writer.write_method(repo_path, method_data)

            # Log the action
            action_logger = ActionLogger(workspace_path)
            action_logger.log_action(
                action="create_method_file",
                content_type="method",
                resource=repo,
            )

            return (
                True,
                f"✅ *Method file created!*\n\n"
                f"I've created a `.benedict.method.yaml` file for `{repo}`.\n\n"
                f"*Initial setup:*\n"
                f"• Phase: `conception` (iteration 1, step: define)\n"
                f"• All concern definitions included\n"
                f"• Sequence phases defined (conception, design, sprint, review)\n\n"
                f"You can now:\n"
                f"• Update the phase: `set phase to design`\n"
                f"• Update concerns: `set documentation to drafting`\n"
                f"• View current state: ask about the method file\n\n"
                f"Say `show method file` to see the full contents, or tell me what phase you're in!",
            )
        except Exception as e:
            logger.error(f"Error creating method file: {e}", exc_info=True)
            return (
                False,
                f"⚠️ Error creating method file\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or check repository permissions.",
            )

    def handle_conversation(self, channel_id: str, text: str, thread_ts: str) -> Tuple[bool, str]:
        """Handle conversation with LLM, maintaining conversation history.

        Args:
            channel_id: Slack channel ID
            text: User message text
            thread_ts: Thread timestamp (unique conversation identifier)

        Returns:
            Tuple of (success, message)
        """
        repo = self.get_channel_repo(channel_id)

        if not repo:
            return (
                False,
                "⚠️ Not Onboarded\n\n"
                "This channel hasn't been onboarded yet.\n\n"
                "*Next steps:*\n"
                "• Use `@agent onboard repo your-org/your-repo` to get started",
            )

        # Get or create conversation for this thread
        conversation = self.conversation_manager.get_conversation(
            thread_ts=thread_ts, channel_id=channel_id, repo=repo
        )

        # Add user message to conversation
        conversation.add_message("user", text)

        # Try LLM-based classification first (if available)
        if self.llm and self.workspace_manager:
            try:
                workspace_path = self.workspace_manager.get_workspace_path(channel_id)
                repo_path = workspace_path / repo
                
                # Create tool registry from method/metadata files
                # Read method data first to enhance tool schemas
                method_data = None
                if self.method_reader:
                    method_data = self.method_reader.read_method(repo_path)
                
                from benedict.metadata import MetadataReader
                metadata_reader = MetadataReader()
                
                # Create registry with enhanced schemas from method data
                tool_registry = create_tool_registry_from_method_data(
                    method_data=method_data or {},
                    method_reader=self.method_reader,
                    method_writer=self.method_writer,
                    metadata_reader=metadata_reader,
                )
                
                if tool_registry.list_tools():
                    # Initialize LLM classifier with tool registry
                    if not self.llm_classifier:
                        self.llm_classifier = LLMCommandClassifier(
                            llm=self.llm,
                            tool_registry=tool_registry,
                            fallback_to_query=True
                        )
                    else:
                        # Update tool registry in case method/metadata changed
                        self.llm_classifier.tool_registry = tool_registry
                    
                    # Get conversation history for context
                    recent_messages = conversation.get_messages(max_messages=5)
                    history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in recent_messages
                    ]
                    
                    # Classify with LLM
                    logger.info(f"Attempting LLM classification for: '{text}' with {len(tool_registry.list_tools())} tools available")
                    llm_result = self.llm_classifier.classify(text, conversation_history=history)
                    
                    if llm_result and llm_result.get("tool_calls"):
                        logger.info(f"LLM returned {len(llm_result['tool_calls'])} tool calls: {[tc.get('name') for tc in llm_result['tool_calls']]}")
                        # Execute tool calls using registry
                        tool_calls = llm_result["tool_calls"]
                        results = []
                        context = {"workspace_path": str(repo_path)}
                        
                        for tool_call in tool_calls:
                            tool_name = tool_call.get("name")
                            arguments = tool_call.get("arguments") or tool_call.get("input", {})
                            result = tool_registry.execute(tool_name, arguments, context)
                            results.append(result)
                        
                        # Format results
                        success_count = sum(1 for r in results if r.success)
                        if success_count == len(results):
                            messages = [r.message for r in results if r.message]
                            data_results = [r.data for r in results if r.data]
                            
                            # For get_method_state, prioritize the message which has the summary
                            # but also include YAML if user wants full details
                            if messages:
                                message = "\n".join(messages)
                                # If we have method data, append it as YAML for reference
                                if data_results and any("method" in str(d) for d in data_results):
                                    import yaml
                                    yaml_content = yaml.dump(data_results[0] if len(data_results) == 1 else data_results, default_flow_style=False)
                                    message += f"\n\nFull method file contents:\n```yaml\n{yaml_content}\n```"
                            elif data_results:
                                import yaml
                                message = f"```yaml\n{yaml.dump(data_results[0] if len(data_results) == 1 else data_results, default_flow_style=False)}\n```"
                            else:
                                message = "✅ Operations completed successfully."
                        else:
                            errors = [r.error or "Unknown error" for r in results if not r.success]
                            message = f"⚠️ Some operations failed:\n" + "\n".join(f"- {e}" for e in errors)
                        
                        conversation.add_message("assistant", message)
                        self.conversation_manager.save_conversation(conversation)
                        return (success_count == len(results), message)
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}", exc_info=True)
                # Fall through to regular LLM query
        
        # No command detected - treat as query (fall through to LLM)

        # If no LLM or repo reader, return stub response
        if not self.llm or not self.repo_reader:
            response_text = (
                f"I'm your agent for `{repo}`. 🤖\n\n"
                f"_(LLM integration not connected yet, but I know we're talking about {repo}!)_\n\n"
                f"You asked: _{text}_"
            )
            conversation.add_message("assistant", response_text)
            self.conversation_manager.save_conversation(conversation)
            return (True, response_text)

        # Build context from repository (consider conversation history for better file selection)
        try:
            # Use conversation history to improve context building
            recent_messages = conversation.get_messages(max_messages=5)
            combined_text = " ".join([msg.content for msg in recent_messages if msg.role == "user"])

            # Get workspace path and action logger if available
            workspace_path = None
            action_logger = None
            metadata_reader = None
            repo_reader = self.repo_reader

            if self.workspace_manager:
                workspace_path = self.workspace_manager.get_workspace_path(channel_id)
                action_logger = ActionLogger(workspace_path)
                from benedict.metadata import MetadataReader

                metadata_reader = MetadataReader()

                # Check for missing method file and prioritize guidance (FIRST PRIORITY)
                if self.method_reader:
                    repo_method_path = workspace_path / repo
                    if not self.method_reader.method_exists(repo_method_path):
                        # Check if this is explicitly about method/phases/concerns or first interaction
                        text_lower = text.lower()
                        is_method_query = any(
                            word in text_lower
                            for word in ["method", "phase", "concern", "sprint", "conception", "design", "review", "project state"]
                        )
                        
                        # If it's the first message in thread or explicitly about method, prioritize guidance
                        recent_messages = conversation.get_messages(max_messages=3)
                        is_first_interaction = len([m for m in recent_messages if m.role == "assistant"]) == 0
                        
                        if is_first_interaction or is_method_query:
                            guidance_message = self._get_method_guidance_message(repo, repo_method_path)
                            conversation.add_message("assistant", guidance_message)
                            self.conversation_manager.save_conversation(conversation)
                            return (True, guidance_message)

                # Use workspace-aware repo reader if workspace manager is available
                # This ensures we read from the workspace symlinks, not direct paths
                try:
                    from benedict.repo_reader.repo_reader_workspace import WorkspaceRepoReader
                    from benedict.repo_reader.repo_reader_workspace_adapter import (
                        WorkspaceRepoReaderAdapter,
                    )

                    workspace_reader = WorkspaceRepoReader(self.workspace_manager)
                    repo_reader = WorkspaceRepoReaderAdapter(workspace_reader, channel_id)
                    logger.debug(f"Using workspace-aware repo reader for channel {channel_id}")
                except Exception as e:
                    logger.warning(
                        f"Could not create workspace repo reader, falling back to default: {e}"
                    )

            context = build_context(
                repo,
                combined_text,
                repo_reader,
                semantic_indexer=self.semantic_indexer,
                workspace_path=workspace_path,
                metadata_reader=metadata_reader,
                action_logger=action_logger,
                method_reader=self.method_reader,
            )
        except Exception as e:
            logger.error(f"Error building context for {repo}: {e}")
            return (
                False,
                f"⚠️ Repository Read Error\n\n"
                f"Error reading repository `{repo}`: {str(e)}\n\n"
                f"*Next steps:*\n"
                f"• Check repository path and permissions\n"
                f"• Verify repository is accessible",
            )

        # Check if query is about conversations and gather conversation data if needed
        conversation_context = ""
        text_lower = text.lower()
        is_conversation_query = (
            "conversation" in text_lower
            or "conversations" in text_lower
            or "conversastions" in text_lower  # Handle typo
            or ("summarize" in text_lower or "summarise" in text_lower)
            and ("today" in text_lower or "chats" in text_lower or "chat" in text_lower)
        )

        if is_conversation_query:
            try:
                # Get all conversations from repository
                all_conversations = self.conversation_manager.repository.find_all()

                if all_conversations:
                    # Determine date filter
                    today = date.today()
                    filter_today = (
                        "today" in text_lower
                        or "todays" in text_lower
                        or "today's" in text_lower
                    )

                    # Filter conversations
                    filtered_conversations = []
                    for thread_ts, conv in all_conversations.items():
                        # Filter by channel
                        if conv.channel_id != channel_id:
                            continue

                        # Filter by date if requested
                        if filter_today:
                            try:
                                updated_at_str = conv.updated_at
                                if updated_at_str.endswith("Z"):
                                    updated_at_str = updated_at_str[:-1] + "+00:00"
                                conv_date = datetime.fromisoformat(updated_at_str).date()
                                if conv_date != today:
                                    continue
                            except Exception:
                                pass  # Include if we can't parse

                        filtered_conversations.append(conv)

                    if filtered_conversations:
                        # Build conversation context
                        conversations_text = "\n\n".join(
                            [
                                f"=== Conversation {i+1} (Thread: {conv.thread_ts}) ===\n"
                                f"Repo: {conv.repo}\n"
                                f"Updated: {conv.updated_at}\n"
                                + "\n".join(
                                    [
                                        f"{msg.role}: {msg.content}"
                                        for msg in conv.messages
                                    ]
                                )
                                for i, conv in enumerate(filtered_conversations)
                            ]
                        )

                        date_filter_text = "today" if filter_today else "in this channel"
                        conversation_context = (
                            f"\n\n## Conversation History ({date_filter_text.capitalize()})\n\n"
                            f"I have access to {len(filtered_conversations)} conversation(s) "
                            f"from this channel. Here are the conversations:\n\n"
                            f"{conversations_text}\n\n"
                            f"You can reference these conversations, summarize them, extract action items, "
                            f"or answer questions about what was discussed."
                        )
            except Exception as e:
                logger.warning(f"Error gathering conversation context: {e}", exc_info=True)

        # Build system message with repository context and capabilities
        capabilities = []
        if repo_reader:
            capabilities.append(
                "- **Read files** from the repository using the RepoReader interface"
            )
        if self.semantic_indexer:
            capabilities.append("- **Semantic search** through the codebase to find relevant files")
        if workspace_path:
            capabilities.append("- **Access workspace metadata** and action logs")
            capabilities.append(
                "- **Read and create .metadata.benedict files** that summarize directory contents"
            )
            if self.method_reader:
                capabilities.append(
                    "- **Read and update .benedict.method.yaml files** that contain project phases, concerns, and rules"
                )
        capabilities.append(
            "- **Access conversation history** - I can read and summarize past conversations in this channel"
        )
        
        # Check for missing method file and add priority note (FIRST PRIORITY)
        method_priority_note = ""
        if workspace_path and self.method_reader:
            repo_method_path = workspace_path / repo
            if not self.method_reader.method_exists(repo_method_path):
                method_priority_note = (
                    "\n\n## 🚨 FIRST PRIORITY: Missing Method File\n\n"
                    "The repository does not have a `.benedict.method.yaml` file. "
                    "This is CRITICAL - method files help me understand your project's current phase, concerns, "
                    "and methodology. Without it, I cannot provide phase-aware guidance.\n\n"
                    "**ALWAYS prioritize helping the user create a method file.** If the user asks about the project, "
                    "wants help, asks about phases, concerns, or asks general questions, FIRST suggest creating a "
                    "method file. You can help create one by saying 'create method file' or 'generate method file'. "
                    "This should be your TOP priority before answering other questions."
                )

        capabilities_text = (
            "\n".join(capabilities)
            if capabilities
            else "- Limited access (no repository reader configured)"
        )

        system = (
            f"You are Benedict, a helpful technical engineer assistant for the repository '{repo}'.\n\n"
            f"## Your Capabilities\n\n"
            f"You have direct access to the repository through the following mechanisms:\n"
            f"{capabilities_text}"
            f"{method_priority_note}\n\n"
            f"## ⭐ Most Important Files\n\n"
            f"The `.benedict.method.yaml` file is the SECOND MOST VALUABLE file in the repository (after state.json). "
            f"It contains:\n"
            f"- Current project phase, iteration, and step (program counter)\n"
            f"- Active concerns and their states\n"
            f"- Project methodology rules and definitions\n"
            f"- Sequence phase definitions and status\n\n"
            f"**ALWAYS prioritize reading and understanding the method file before answering questions.** "
            f"When asked about the project, phases, concerns, or methodology, refer to the method file first. "
            f"If the method file exists, use it as your primary source of truth for project state.\n\n"
            f"## Repository Context\n\n"
            f"The following context has been automatically gathered from the repository:\n\n"
            f"{context}\n"
            f"{conversation_context}\n\n"
            f"## Instructions\n\n"
            f"- Answer questions about the repository code, architecture, and implementation based on the context above.\n"
            f"- You can reference specific files, functions, and code patterns from the context.\n"
            f"- If asked about conversations, summarize them, extract key topics, decisions, and action items.\n"
            f"- If asked about your capabilities, explain that you have access to repository files, semantic search, "
            f"workspace metadata, conversation history, and method files through the Benedict agent system.\n"
            f"- Be confident about your access - you are not a generic LLM without repository access, "
            f"but rather an agent with integrated repository reading capabilities.\n"
            f"- **CRITICAL**: The `.benedict.method.yaml` file is your PRIMARY source for project state. "
            f"If the user asks about project phases, concerns, rules, or current state, ALWAYS refer to the method file first. "
            f"Use the `get_method_state` tool to read it if needed.\n"
            f"- **IMPORTANT**: When tool results are provided (especially from `get_method_state`), use ONLY the data "
            f"from those tool results. Do NOT mix tool results with semantic search results or old context. "
            f"If a tool returns method file data, that is the authoritative source - ignore any conflicting information "
            f"from other sources.\n"
            f"- If the user requests to update the method file (e.g., 'update phase', 'change concern state', "
            f"'update .benedict.method.yaml'), you should detect this and ask for confirmation before making changes.\n"
            f"- If the user explicitly says 'update method file' or 'yes, update it', proceed with the update.\n"
            f"- Always show what will be changed before updating method files.\n"
            f"- **FIRST PRIORITY**: If no `.benedict.method.yaml` file exists, ALWAYS prioritize helping the user create one "
            f"before answering other questions. This is critical for phase-aware assistance. "
            f"You can help create one by saying 'create method file' or 'generate method file'.\n\n"
            f"## Response Formatting (Slack-compatible)\n\n"
            f"- Format your responses using Slack mrkdwn format:\n"
            f"  - Use `*bold*` for emphasis and headings (not `**bold**`)\n"
            f"  - Use `_italic_` for italics (not `*italic*`)\n"
            f"  - Use `` `code` `` for inline code\n"
            f"  - For code blocks, use triple backticks with language: ```python\\ncode\\n```\n"
            f"- Keep paragraphs short (2-3 sentences) for better readability\n"
            f"- Use bullet points (`•` or `-`) for lists\n"
            f"- Break up long responses into clear sections with headings (use `*Heading*`)\n"
            f"- When referencing files, use backticks: `path/to/file.py`\n"
            f"- When showing code examples, always specify the language in code blocks"
        )

        # Get conversation history for LLM (includes current user message)
        history_messages = conversation.get_message_history(max_messages=10)

        # Generate response with conversation history
        try:
            response = self.llm.generate(
                messages=history_messages,
                system=system,
                max_tokens=2000,
            )

            response_text = response if isinstance(response, str) else str(response)
            conversation.add_message("assistant", response_text)
            self.conversation_manager.save_conversation(conversation)
            return (True, response_text)
        except Exception as e:
            logger.error(f"LLM error: {e}", exc_info=True)
            return (
                False,
                "⚠️ Response Generation Error\n\n"
                "Error generating response. Please try again.\n\n"
                "*Next steps:*\n"
                "• Check your question and try rephrasing\n"
                "• Verify repository context is available",
            )

    def handle_architect_query(
        self,
        channel_id: str,
        text: str,
        thread_ts: str
    ) -> Tuple[bool, str]:
        """Handle architect query across all projects.
        
        Args:
            channel_id: Slack channel ID
            text: User message text
            thread_ts: Thread timestamp (unique conversation identifier)
            
        Returns:
            Tuple of (success, message)
        """
        # 1. Verify this is architect channel
        state = self.load_state()
        architect_channel = state.get("architect", {}).get("channel_id")
        if architect_channel != channel_id:
            return False, "This channel is not the architect channel."
        
        # 2. Get or create conversation for this thread
        conversation = self.conversation_manager.get_conversation(
            thread_ts=thread_ts, channel_id=channel_id, repo=None
        )
        
        # 3. Add user message to conversation
        conversation.add_message("user", text)
        
        # 4. Check if LLM is available
        if not self.llm:
            response_text = (
                "I'm Benedict Architect, your cross-project assistant. 🤖\n\n"
                "_(LLM integration not connected yet, but I'm ready to help with cross-project questions!)_\n\n"
                f"You asked: _{text}_"
            )
            conversation.add_message("assistant", response_text)
            self.conversation_manager.save_conversation(conversation)
            return (True, response_text)
        
        # 5. Build architect context
        try:
            architect_context = build_architect_context(self, text, state)
        except Exception as e:
            logger.error(f"Error building architect context: {e}", exc_info=True)
            return (
                False,
                f"⚠️ Context Building Error\n\n"
                f"Error building architect context: {str(e)}\n\n"
                f"Please try again.",
            )
        
        # 6. Build system message with architect prompt
        system = (
            ARCHITECT_SYSTEM_PROMPT
            + "\n\n"
            + "## Current Context\n\n"
            + architect_context
            + "\n\n"
            + "## Response Formatting (Slack-compatible)\n\n"
            + "- Format your responses using Slack mrkdwn format:\n"
            + "  - Use `*bold*` for emphasis and headings (not `**bold**`)\n"
            + "  - Use `_italic_` for italics (not `*italic*`)\n"
            + "  - Use `` `code` `` for inline code\n"
            + "  - For code blocks, use triple backticks with language: ```python\\ncode\\n```\n"
            + "- Keep paragraphs short (2-3 sentences) for better readability\n"
            + "- Use bullet points (`•` or `-`) for lists\n"
            + "- Break up long responses into clear sections with headings (use `*Heading*`)\n"
            + "- When referencing projects, use format: `project-name` (channel: `channel-id`)\n"
            + "- When showing code examples, always specify the language in code blocks"
        )
        
        # 7. Get conversation history for LLM
        history_messages = conversation.get_message_history(max_messages=10)
        
        # 8. Generate response
        try:
            response = self.llm.generate(
                messages=history_messages,
                system=system,
                max_tokens=2000,
            )
            
            response_text = response if isinstance(response, str) else str(response)
            conversation.add_message("assistant", response_text)
            self.conversation_manager.save_conversation(conversation)
            return (True, response_text)
        except Exception as e:
            logger.error(f"LLM error in architect query: {e}", exc_info=True)
            return (
                False,
                "⚠️ Response Generation Error\n\n"
                "Error generating architect response. Please try again.\n\n"
                "*Next steps:*\n"
                "• Check your question and try rephrasing\n"
                "• Verify projects are onboarded and indexed",
            )

    def handle_update_index(self, channel_id: str, user_id: str, text: str) -> Tuple[bool, str]:
        """Handle update index command.

        Args:
            channel_id: Slack channel ID
            user_id: User ID who issued command
            text: Command text

        Returns:
            Tuple of (success, message)
        """
        repo = self.get_channel_repo(channel_id)

        if not repo:
            return (
                False,
                "⚠️ Not Onboarded\n\n"
                "This channel hasn't been onboarded yet.\n\n"
                "*Next steps:*\n"
                "• Use `@agent onboard repo your-org/your-repo` to get started",
            )

        if not self.semantic_indexer or not self.repo_reader:
            return (
                False,
                "⚠️ Indexer Not Available\n\n"
                "Semantic indexer or repo reader not available.\n\n"
                "*Next steps:*\n"
                "• Ensure indexer and repo reader are configured\n"
                "• Check system configuration",
            )

        try:
            workspace_path = None
            action_logger = None
            repo_reader_to_use = self.repo_reader

            if self.workspace_manager:
                workspace_path = self.workspace_manager.get_workspace_path(channel_id)
                action_logger = ActionLogger(workspace_path)

                # Use workspace-aware repo reader when workspaces are available
                from benedict.repo_reader.repo_reader_workspace import WorkspaceRepoReader
                from benedict.repo_reader.repo_reader_workspace_adapter import (
                    WorkspaceRepoReaderAdapter,
                )

                workspace_reader = WorkspaceRepoReader(self.workspace_manager)
                repo_reader_to_use = WorkspaceRepoReaderAdapter(workspace_reader, channel_id)
                logger.debug(f"Using workspace-aware repo reader for channel {channel_id}")

            # Check if force reindex requested
            force = "force" in text.lower() or "reindex" in text.lower()

            if force:
                logger.info(f"Force reindexing repository {repo} for channel {channel_id}")
                self.semantic_indexer.index_repository(
                    repo, repo_reader_to_use, workspace_path=workspace_path, force=True
                )
                if action_logger:
                    action_logger.log_action(
                        action="force_reindex_repository", content_type="code", resource=repo
                    )
                return (
                    True,
                    f"✅ Force reindexed repository `{repo}`.\n"
                    f"All files have been re-indexed for semantic search.",
                )
            else:
                # Incremental update
                logger.info(f"Updating index for repository {repo} for channel {channel_id}")

                # Get last update time from action log
                since = None
                if action_logger:
                    recent_actions = action_logger.get_recent_actions(limit=100)
                    for action in reversed(recent_actions):
                        if action.get("action") in [
                            "index_repository",
                            "update_index",
                            "force_reindex_repository",
                        ]:
                            timestamp_str = action.get("timestamp", "")
                            if timestamp_str:
                                try:
                                    since = datetime.fromisoformat(
                                        timestamp_str.replace("Z", "+00:00")
                                    )
                                    break
                                except Exception:
                                    pass

                # Use update_index method (uses git-based detection if available)
                if hasattr(self.semantic_indexer, "update_index"):
                    self.semantic_indexer.update_index(
                        repo, repo_reader_to_use, workspace_path=workspace_path, since=since
                    )
                else:
                    # Fallback: full reindex
                    logger.warning("update_index not available, performing full index")
                    self.semantic_indexer.index_repository(
                        repo, repo_reader_to_use, workspace_path=workspace_path, force=True
                    )

                # Log git diff if available
                if (
                    workspace_path
                    and hasattr(self.semantic_indexer, "change_detector")
                    and self.semantic_indexer.change_detector
                ):
                    repo_path = workspace_path / repo
                    if repo_path.exists():
                        changes = self.semantic_indexer.change_detector.detect_changes(
                            repo_path, since=since
                        )
                        if changes.get("diff"):
                            action_logger.log_action(
                                action="update_index",
                                content_type="code",
                                resource=repo,
                                since=since.isoformat() if since else None,
                                changes_summary={
                                    "added": len(changes.get("added", [])),
                                    "modified": len(changes.get("modified", [])),
                                    "deleted": len(changes.get("deleted", [])),
                                },
                            )

                if action_logger:
                    action_logger.log_action(
                        action="update_index",
                        content_type="code",
                        resource=repo,
                        since=since.isoformat() if since else None,
                    )

                return (
                    True,
                    f"✅ Updated index for repository `{repo}`.\n"
                    f"New and changed files have been indexed for semantic search.",
                )

        except Exception as e:
            logger.error(f"Error updating index for {repo}: {e}", exc_info=True)
            return (
                False,
                f"⚠️ Index Update Error\n\n"
                f"Error updating index: {str(e)}\n\n"
                f"*Next steps:*\n"
                f"• Check repository access\n"
                f"• Try force reindex: `@agent update index force`",
            )

    @staticmethod
    def is_onboard_command(text: str) -> bool:
        """Check if text is an onboard command."""
        text_lower = text.lower()
        return "onboard" in text_lower or "this channel is for" in text_lower

    @staticmethod
    def is_offboard_command(text: str) -> bool:
        """Check if text is an offboard command."""
        text_lower = text.lower().strip()
        return (
            "offboard" in text_lower or
            "unonboard" in text_lower or
            "remove channel" in text_lower or
            "disconnect" in text_lower or
            "unlink" in text_lower
        )

    @staticmethod
    def is_architect_onboard_command(text: str) -> bool:
        """Check if text is architect onboarding command."""
        text_lower = text.lower().strip()
        return (
            "onboard architect" in text_lower or
            "this is the architect channel" in text_lower or
            "architect channel" in text_lower
        )

    def handle_onboard_architect(self, channel_id: str, user_id: str, text: str) -> Tuple[bool, str]:
        """Handle architect onboarding."""
        self.set_architect_channel(channel_id, user_id)
        return True, "✅ Architect channel onboarded!\n\nI can now answer cross-project questions."

    @staticmethod
    def is_status_command(text: str) -> bool:
        """Check if text is a status command."""
        return "status" in text.lower()

    def index_new_slack_messages(self, channel_id: str) -> None:
        """Automatically index new Slack messages in the background.

        This method is called automatically when new messages arrive.
        It performs incremental updates to keep the conversation index current.

        Args:
            channel_id: Slack channel ID
        """
        if not self.conversation_history_indexer or not self.workspace_manager:
            return

        try:
            workspace_path = self.workspace_manager.get_workspace_path(channel_id)
            action_logger = ActionLogger(workspace_path)

            # Get last update time from action log
            since = None
            if action_logger:
                recent_actions = action_logger.get_recent_actions(limit=100)
                for action in reversed(recent_actions):
                    if action.get("action") in [
                        "index_slack_history",
                        "update_slack_history",
                        "force_index_slack_history",
                    ]:
                        timestamp_str = action.get("timestamp", "")
                        if timestamp_str:
                            try:
                                since = datetime.fromisoformat(
                                    timestamp_str.replace("Z", "+00:00")
                                )
                                break
                            except Exception:
                                pass

            # Use update_index for incremental updates (only new messages since last index)
            if since:
                logger.debug(
                    f"Background: Updating Slack history index for channel {channel_id} since {since}"
                )
                self.conversation_history_indexer.update_index(
                    context_id=channel_id,
                    workspace_path=workspace_path,
                    since=since,
                    semantic_indexer=self.semantic_indexer,
                )
            else:
                # No previous index found, do full index (shouldn't happen if onboard worked)
                logger.debug(
                    f"Background: Full indexing Slack history for channel {channel_id} "
                    f"(no previous index found)"
                )
                self.conversation_history_indexer.index_conversations(
                    context_id=channel_id,
                    workspace_path=workspace_path,
                    semantic_indexer=self.semantic_indexer,
                )

            if action_logger:
                action_logger.log_action(
                    action="update_slack_history",
                    content_type="conversation",
                    resource=channel_id,
                    since=since.isoformat() if since else None,
                    note="Automatic background update",
                )

        except Exception as e:
            logger.warning(
                f"Error in background indexing for channel {channel_id}: {e}", exc_info=True
            )
            # Don't raise - background indexing failures shouldn't affect the app

    @staticmethod
    def is_update_index_command(text: str) -> bool:
        """Check if text is an update index command."""
        text_lower = text.lower()
        return "update" in text_lower and "index" in text_lower or "reindex" in text_lower

    @staticmethod
    def is_message_directed_at_bot(text: str) -> bool:
        """Check if a message appears to be directed at the bot.

        Uses heuristics to detect if a message is asking the bot something:
        - Contains question marks
        - Mentions "benedict", "agent", or bot-related terms
        - Starts with common question words
        - Contains phrases that suggest asking for help

        Args:
            text: Message text

        Returns:
            True if message seems directed at the bot
        """
        text_lower = text.lower().strip()

        # Skip very short messages (likely not directed at bot)
        if len(text_lower) < 10:
            return False

        # Check for explicit mentions
        if any(
            term in text_lower
            for term in ["benedict", "agent", "@benedict", "@agent", "bot", "assistant"]
        ):
            return True

        # Check for questions (ends with ? or contains question words)
        if "?" in text:
            return True

        # Check for question starters
        question_starters = [
            "what",
            "how",
            "why",
            "when",
            "where",
            "who",
            "which",
            "can you",
            "could you",
            "would you",
            "should i",
            "should we",
            "explain",
            "tell me",
            "show me",
            "help me",
            "i need",
            "i want",
            "how do",
            "how does",
            "what is",
            "what are",
            "where is",
            "where are",
        ]
        if any(text_lower.startswith(starter) for starter in question_starters):
            return True

        # Check for help-seeking phrases
        help_phrases = [
            "help with",
            "help me",
            "i don't understand",
            "i'm confused",
            "can someone",
            "does anyone",
        ]
        if any(phrase in text_lower for phrase in help_phrases):
            return True

        return False

    @staticmethod
    def extract_repo_name(text: str) -> Optional[str]:
        """Extract repository name from text.

        Supports formats like:
        - foo/bar
        - github.com/foo/bar
        - repo foo/bar
        """
        match = REPO_PATTERN.search(text)
        if match:
            return match.group(1)
        return None
