"""Repository Agent

Core agent logic for handling repository-scoped conversations.
"""

import json
import logging
import os
import re
import time
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
from benedict.commands import (
    LLMCommandClassifier,
    ToolRegistry,
    create_tool_registry,
)
from benedict.commands.github_tools import RunGithubTool
from benedict.commands.tool_loop import run_tool_loop
from benedict.operator_ui.recorder import record_llm_stage, record_stage

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
        run_recorder=None,
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
            run_recorder: Optional operator-UI run recorder
        """
        self.state_file = Path(state_file)
        self.llm = llm
        self.repo_reader = repo_reader
        self.semantic_indexer = semantic_indexer
        self.workspace_manager = workspace_manager
        self.conversation_history_indexer = conversation_history_indexer
        if run_recorder is None:
            from benedict.operator_ui.recorder import NullRunRecorder

            run_recorder = NullRunRecorder()
        self.run_recorder = run_recorder
        self.metadata_generator = MetadataGenerator() if workspace_manager else None
        self.tool_registry = None
        self.llm_classifier = None

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
            record_stage(
                "reply",
                status="error",
                label="not onboarded",
                detail={"reason": "no channel → repo mapping"},
            )
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

        # Metadata classifier is a narrow shortcut. GitHub, code Q&A, and
        # issue creation belong on the conversation path (run_github).
        if self.llm and self.workspace_manager and self.is_metadata_command(text):
            classify_started = time.perf_counter()
            try:
                workspace_path = self.workspace_manager.get_workspace_path(channel_id)
                repo_path = workspace_path / repo
                
                from benedict.metadata import MetadataReader
                metadata_reader = MetadataReader()
                tool_registry = create_tool_registry(
                    metadata_reader=metadata_reader,
                    repo_path=repo_path,
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
                        # Update tool registry in case metadata changed
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
                        record_stage(
                            "classify",
                            duration_ms=int((time.perf_counter() - classify_started) * 1000),
                            label="metadata shortcut",
                            detail={
                                "tool_calls": [tc.get("name") for tc in llm_result["tool_calls"]]
                            },
                        )
                        # Execute tool calls using registry
                        tool_calls = llm_result["tool_calls"]
                        results = []
                        context = {"workspace_path": str(repo_path)}
                        
                        for tool_call in tool_calls:
                            tool_name = tool_call.get("name")
                            arguments = tool_call.get("arguments") or tool_call.get("input", {})
                            tool_started = time.perf_counter()
                            result = tool_registry.execute(tool_name, arguments, context)
                            record_stage(
                                "tool",
                                status="ok" if result.success else "error",
                                duration_ms=int((time.perf_counter() - tool_started) * 1000),
                                label=tool_name or "tool",
                                detail={"name": tool_name, "arguments": arguments},
                                child=True,
                            )
                            results.append(result)
                        
                        # Format results
                        success_count = sum(1 for r in results if r.success)
                        if success_count == len(results):
                            messages = [r.message for r in results if r.message]
                            data_results = [r.data for r in results if r.data]
                            
                            if messages:
                                message = "\n".join(messages)
                            elif data_results:
                                import yaml
                                message = f"```yaml\n{yaml.dump(data_results[0] if len(data_results) == 1 else data_results, default_flow_style=False)}\n```"
                            else:
                                message = "✅ Operations completed successfully."
                            conversation.add_message("assistant", message)
                            self.conversation_manager.save_conversation(conversation)
                            return (True, message)

                        errors = [r.error or "Unknown error" for r in results if not r.success]
                        logger.warning(
                            "Metadata tools failed (%s); falling through to conversation",
                            errors,
                        )
                        record_stage(
                            "classify",
                            status="error",
                            duration_ms=int((time.perf_counter() - classify_started) * 1000),
                            label="metadata shortcut failed",
                            detail={"errors": errors},
                        )
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}", exc_info=True)
                record_stage(
                    "classify",
                    status="error",
                    label="classifier exception",
                    detail={"error": str(e)},
                )
                # Fall through to regular LLM query
        else:
            record_stage(
                "classify",
                status="skip",
                label="skipped — not metadata wording",
                detail={"is_metadata_command": False},
            )
        
        # No command detected - treat as query (fall through to LLM)

        # If no LLM or repo reader, return stub response
        if not self.llm or not self.repo_reader:
            record_stage("llm", status="skip", label="stub — no LLM or repo reader")
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
            capabilities.append(
                "- **Run GitHub CLI (`gh`)** in this repository via the `run_github` tool"
            )
        capabilities.append(
            "- **Access conversation history** - I can read and summarize past conversations in this channel"
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
            f"{capabilities_text}\n\n"
            f"## Repository Context\n\n"
            f"The following context has been automatically gathered from the repository:\n\n"
            f"{context}\n"
            f"{conversation_context}\n\n"
            f"## Instructions\n\n"
            f"- Answer questions about the repository code, architecture, and implementation based on the context above.\n"
            f"- You can reference specific files, functions, and code patterns from the context.\n"
            f"- If asked about conversations, summarize them, extract key topics, decisions, and action items.\n"
            f"- If asked about your capabilities, explain that you have access to repository files, semantic search, "
            f"workspace metadata, conversation history, and GitHub via `run_github`.\n"
            f"- Be confident about your access - you are not a generic LLM without repository access, "
            f"but rather an agent with integrated repository reading capabilities.\n"
            f"- **GitHub (`run_github`)**: To inspect PRs, issues, checks, or other GitHub data, call "
            f"`run_github` with argv only (do not include `gh`). Example: "
            f"`argv=[\"pr\", \"list\", \"--json\", \"title,url,author\"]`. Prefer `--json` so you can parse "
            f"results. This is not a general shell — only `gh` runs. Ask the user before mutating GitHub "
            f"(create, merge, close, comment). Never print tokens or secrets. If `gh` is missing or not "
            f"authenticated, explain that the host running Benedict must install GitHub CLI and run "
            f"`gh auth login`.\n\n"
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

        # Generate response with conversation history.
        # GitHub is a conversation tool (interpret output), not a classifier command.
        try:
            github_registry = ToolRegistry()
            tool_context: Dict[str, Any] = {}
            if workspace_path:
                github_registry.register(RunGithubTool())
                tool_context["workspace_path"] = str(workspace_path / repo)

            if github_registry.list_tools():
                response_text = run_tool_loop(
                    llm=self.llm,
                    messages=history_messages,
                    system=system,
                    tool_registry=github_registry,
                    context=tool_context,
                )
            else:
                llm_started = time.perf_counter()
                response = self.llm.generate(
                    messages=history_messages,
                    system=system,
                    max_tokens=2000,
                )
                record_llm_stage(
                    system=system,
                    messages=history_messages,
                    duration_ms=int((time.perf_counter() - llm_started) * 1000),
                    label=os.environ.get("ANTHROPIC_MODEL", "claude"),
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
            llm_started = time.perf_counter()
            response = self.llm.generate(
                messages=history_messages,
                system=system,
                max_tokens=2000,
            )
            record_llm_stage(
                system=system,
                messages=history_messages,
                duration_ms=int((time.perf_counter() - llm_started) * 1000),
                label=os.environ.get("ANTHROPIC_MODEL", "claude"),
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
    def is_metadata_command(text: str) -> bool:
        """True only for explicit metadata-file operations.

        GitHub issues, PRs, and general questions must not enter the
        metadata classifier. That classifier has no run_github tool and
        used to abort the conversation with "Metadata file not found".
        """
        text_lower = text.lower()
        return any(
            pattern in text_lower
            for pattern in (
                "metadata",
                "list files",
                "list key files",
                "repository summary",
                "repo summary",
            )
        )

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
