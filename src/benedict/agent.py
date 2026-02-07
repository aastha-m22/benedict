"""Repository Agent

Core agent logic for handling repository-scoped conversations.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from benedict.protocols import LLM, RepoReader, SemanticIndexer, ConversationRepository
from benedict.models import ConversationManager, Conversation
from benedict.utils import build_context
from benedict.workspace import WorkspaceManager, ActionLogger
from benedict.metadata import MetadataGenerator

logger = logging.getLogger(__name__)

# Constants
REPO_PATTERN = re.compile(r'([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)')


class RepoAgent:
    """Repository-scoped agent with LLM and repository access."""
    
    def __init__(
        self,
        state_file: str = "state.json",
        llm: Optional[LLM] = None,
        repo_reader: Optional[RepoReader] = None,
        semantic_indexer: Optional[SemanticIndexer] = None,
        conversation_repository: Optional[ConversationRepository] = None,
        workspace_manager: Optional[WorkspaceManager] = None
    ):
        """Initialize repository agent.
        
        Args:
            state_file: Path to state JSON file (used for conversation repository if not provided)
            llm: Optional LLM instance for intelligent responses
            repo_reader: Optional repository reader instance
            semantic_indexer: Optional semantic indexer for intelligent file selection
            conversation_repository: Optional conversation repository (created from state_file if None)
            workspace_manager: Optional workspace manager for workspace operations
        """
        self.state_file = Path(state_file)
        self.llm = llm
        self.repo_reader = repo_reader
        self.semantic_indexer = semantic_indexer
        self.workspace_manager = workspace_manager
        self.metadata_generator = MetadataGenerator() if workspace_manager else None
        
        # Create conversation repository if not provided
        if conversation_repository is None:
            from benedict.protocols.conversation_repository import create_conversation_repository
            conversation_repository = create_conversation_repository(provider="json", state_file=state_file)
        
        self.conversation_manager = ConversationManager(conversation_repository)
        logger.info(f"Initialized RepoAgent with state_file={state_file}")
    
    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    logger.debug(f"Loaded state with {len(state.get('channels', {}))} channels")
                    return state
            except json.JSONDecodeError:
                logger.error(f"Failed to parse {self.state_file}, creating new state")
        
        return {"channels": {}}
    
    def save_state(self, state: Dict[str, Any]) -> None:
        """Persist state to JSON file."""
        try:
            with open(self.state_file, 'w') as f:
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
            "onboarded_by": user_id
        }
        self.save_state(state)
        logger.info(f"Onboarded channel {channel_id} to repo {repo}")
    
    def handle_onboard(self, channel_id: str, user_id: str, text: str) -> Tuple[bool, str]:
        """Handle onboard command.
        
        Returns:
            Tuple of (success, message)
        """
        repo = self.extract_repo_name(text)
        
        if not repo:
            return (False, "⚠️ Repository Not Found\n\n"
                          "I couldn't find a repository name in your message.\n\n"
                          "*Next steps:*\n"
                          "• Use format: `@agent onboard repo foo/bar`\n"
                          "• Or: `@agent this channel is for foo/bar`")
        
        # Create workspace and add resource if workspace_manager is available
        if self.workspace_manager:
            try:
                workspace_path = self.workspace_manager.create_workspace(channel_id)
                action_logger = ActionLogger(workspace_path)
                
                # Try to resolve repository path
                # Check multiple possible locations: absolute paths, org/repo structure, or just repo name
                repo_source = None
                possible_paths = [
                    Path(repo),  # Try as-is (might be absolute path like /Users/name/Projects/repo)
                    Path.home() / "Projects" / repo,  # Full org/repo path: ~/Projects/mkarots/hookedllm
                    Path.home() / "Projects" / repo.split('/')[-1],  # Just repo name: ~/Projects/hookedllm
                    Path.cwd() / repo.split('/')[-1],  # Current directory: ./hookedllm
                ]
                
                for path in possible_paths:
                    if path.exists() and path.is_dir():
                        repo_source = path
                        logger.info(f"Found repository at: {repo_source}")
                        break
                
                if not repo_source:
                    return (False, f"⚠️ Repository Not Found\n\n"
                                  f"Could not find repository `{repo}` locally.\n\n"
                                  f"*Tried locations:*\n"
                                  f"• `{Path(repo)}`\n"
                                  f"• `{Path.home() / 'Projects' / repo}`\n"
                                  f"• `{Path.home() / 'Projects' / repo.split('/')[-1]}`\n"
                                  f"• `{Path.cwd() / repo.split('/')[-1]}`\n\n"
                                  f"*Next steps:*\n"
                                  f"• Provide the full path to the repository\n"
                                  f"• Example: `@agent onboard repo /Users/yourname/Projects/hookedllm`")
                
                # Add resource to workspace
                workspace_resource_path = self.workspace_manager.add_resource(
                    context_id=channel_id,
                    resource_type="repository",
                    source_path=str(repo_source),
                    name=repo,
                    content_type="code"
                )
                
                # Log action
                action_logger.log_action(
                    action="symlink_repository",
                    content_type="code",
                    resource=repo,
                    source=str(repo_source),
                    workspace_path=workspace_resource_path
                )
                
                # Generate initial metadata
                if self.metadata_generator:
                    try:
                        repo_path = workspace_path / repo
                        if repo_path.exists():
                            self.metadata_generator.generate_and_write(repo_path, content_type="code")
                            action_logger.log_action(
                                action="generate_metadata",
                                content_type="code",
                                resource=repo
                            )
                    except Exception as e:
                        logger.warning(f"Error generating initial metadata for {repo}: {e}")
                
            except Exception as e:
                logger.error(f"Error setting up workspace for {repo}: {e}", exc_info=True)
                return (False, f"⚠️ Workspace Setup Error\n\n"
                              f"Error setting up workspace: {str(e)}\n\n"
                              f"*Next steps:*\n"
                              f"• Check repository path and permissions\n"
                              f"• Try again or contact support")
        
        self.set_channel_repo(channel_id, repo, user_id)
        return (True, f"✅ Onboarded! This channel is now linked to `{repo}`.\n"
                      f"I'll remember this repo for all our conversations here.\n\n"
                      f"Try: `@agent status` to see the details.")
    
    def handle_status(self, channel_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Handle status command.
        
        Returns:
            Tuple of (success, message, channel_config)
        """
        state = self.load_state()
        channel_config = state.get("channels", {}).get(channel_id)
        
        if not channel_config:
            return (False, "⚠️ Not Onboarded\n\n"
                          "This channel hasn't been onboarded yet.\n\n"
                          "*Next steps:*\n"
                          "• Use `@agent onboard repo your-org/your-repo` to get started", None)
        
        repo = channel_config.get("repo")
        onboarded_at = channel_config.get("onboarded_at", "Unknown")
        onboarded_by = channel_config.get("onboarded_by", "Unknown")
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(onboarded_at.replace('Z', '+00:00'))
            formatted_time = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            formatted_time = onboarded_at
        
        message = (f"📊 *Channel Status*\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"🔗 Repository: `{repo}`\n"
                   f"⏰ Onboarded: {formatted_time}\n"
                   f"👤 By: <@{onboarded_by}>")
        
        return (True, message, channel_config)
    
    def handle_conversation(
        self, 
        channel_id: str, 
        text: str,
        thread_ts: str
    ) -> Tuple[bool, str]:
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
            return (False, "⚠️ Not Onboarded\n\n"
                          "This channel hasn't been onboarded yet.\n\n"
                          "*Next steps:*\n"
                          "• Use `@agent onboard repo your-org/your-repo` to get started")
        
        # Get or create conversation for this thread
        conversation = self.conversation_manager.get_conversation(
            thread_ts=thread_ts,
            channel_id=channel_id,
            repo=repo
        )
        
        # Add user message to conversation
        conversation.add_message("user", text)
        
        # If no LLM or repo reader, return stub response
        if not self.llm or not self.repo_reader:
            response_text = (f"I'm your agent for `{repo}`. 🤖\n\n"
                            f"_(LLM integration not connected yet, but I know we're talking about {repo}!)_\n\n"
                            f"You asked: _{text}_")
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
                    from benedict.repo_reader.repo_reader_workspace_adapter import WorkspaceRepoReaderAdapter
                    workspace_reader = WorkspaceRepoReader(self.workspace_manager)
                    repo_reader = WorkspaceRepoReaderAdapter(workspace_reader, channel_id)
                    logger.debug(f"Using workspace-aware repo reader for channel {channel_id}")
                except Exception as e:
                    logger.warning(f"Could not create workspace repo reader, falling back to default: {e}")
            
            context = build_context(
                repo, 
                combined_text, 
                repo_reader,
                semantic_indexer=self.semantic_indexer,
                workspace_path=workspace_path,
                metadata_reader=metadata_reader,
                action_logger=action_logger
            )
        except Exception as e:
            logger.error(f"Error building context for {repo}: {e}")
            return (False, f"⚠️ Repository Read Error\n\n"
                          f"Error reading repository `{repo}`: {str(e)}\n\n"
                          f"*Next steps:*\n"
                          f"• Check repository path and permissions\n"
                          f"• Verify repository is accessible")
        
        # Build system message with repository context and capabilities
        capabilities = []
        if repo_reader:
            capabilities.append("- **Read files** from the repository using the RepoReader interface")
        if self.semantic_indexer:
            capabilities.append("- **Semantic search** through the codebase to find relevant files")
        if workspace_path:
            capabilities.append("- **Access workspace metadata** and action logs")
            capabilities.append("- **Read METADATA overlays** that summarize directory contents")
        
        capabilities_text = "\n".join(capabilities) if capabilities else "- Limited access (no repository reader configured)"
        
        system = (
            f"You are Benedict, a helpful technical engineer assistant for the repository '{repo}'.\n\n"
            f"## Your Capabilities\n\n"
            f"You have direct access to the repository through the following mechanisms:\n"
            f"{capabilities_text}\n\n"
            f"## Repository Context\n\n"
            f"The following context has been automatically gathered from the repository:\n\n"
            f"{context}\n\n"
            f"## Instructions\n\n"
            f"- Answer questions about the repository code, architecture, and implementation based on the context above.\n"
            f"- You can reference specific files, functions, and code patterns from the context.\n"
            f"- If asked about your capabilities, explain that you have access to repository files, semantic search, "
            f"and workspace metadata through the Benedict agent system.\n"
            f"- Be confident about your access - you are not a generic LLM without repository access, "
            f"but rather an agent with integrated repository reading capabilities.\n\n"
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
                max_tokens=2000
            )
            
            # Add assistant response to conversation
            conversation.add_message("assistant", response)
            self.conversation_manager.save_conversation(conversation)
            
            return (True, response)
        except Exception as e:
            logger.error(f"LLM error: {e}", exc_info=True)
            return (False, "⚠️ Response Generation Error\n\n"
                          "Error generating response. Please try again.\n\n"
                          "*Next steps:*\n"
                          "• Check your question and try rephrasing\n"
                          "• Verify repository context is available")
    
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
            return (False, "⚠️ Not Onboarded\n\n"
                          "This channel hasn't been onboarded yet.\n\n"
                          "*Next steps:*\n"
                          "• Use `@agent onboard repo your-org/your-repo` to get started")
        
        if not self.semantic_indexer or not self.repo_reader:
            return (False, "⚠️ Indexer Not Available\n\n"
                          "Semantic indexer or repo reader not available.\n\n"
                          "*Next steps:*\n"
                          "• Ensure indexer and repo reader are configured\n"
                          "• Check system configuration")
        
        try:
            workspace_path = None
            action_logger = None
            
            if self.workspace_manager:
                workspace_path = self.workspace_manager.get_workspace_path(channel_id)
                action_logger = ActionLogger(workspace_path)
            
            # Check if force reindex requested
            force = "force" in text.lower() or "reindex" in text.lower()
            
            if force:
                logger.info(f"Force reindexing repository {repo} for channel {channel_id}")
                self.semantic_indexer.index_repository(repo, self.repo_reader, workspace_path=workspace_path, force=True)
                if action_logger:
                    action_logger.log_action(
                        action="force_reindex_repository",
                        content_type="code",
                        resource=repo
                    )
                return (True, f"✅ Force reindexed repository `{repo}`.\n"
                              f"All files have been re-indexed for semantic search.")
            else:
                # Incremental update
                logger.info(f"Updating index for repository {repo} for channel {channel_id}")
                
                # Get last update time from action log
                since = None
                if action_logger:
                    recent_actions = action_logger.get_recent_actions(limit=100)
                    for action in reversed(recent_actions):
                        if action.get('action') in ['index_repository', 'update_index', 'force_reindex_repository']:
                            timestamp_str = action.get('timestamp', '')
                            if timestamp_str:
                                try:
                                    since = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                    break
                                except Exception:
                                    pass
                
                # Use update_index method (uses git-based detection if available)
                if hasattr(self.semantic_indexer, 'update_index'):
                    self.semantic_indexer.update_index(repo, self.repo_reader, workspace_path=workspace_path, since=since)
                else:
                    # Fallback: full reindex
                    logger.warning("update_index not available, performing full index")
                    self.semantic_indexer.index_repository(repo, self.repo_reader, workspace_path=workspace_path, force=True)
                
                # Log git diff if available
                if workspace_path and hasattr(self.semantic_indexer, 'change_detector') and self.semantic_indexer.change_detector:
                    repo_path = workspace_path / repo
                    if repo_path.exists():
                        changes = self.semantic_indexer.change_detector.detect_changes(repo_path, since=since)
                        if changes.get('diff'):
                            action_logger.log_action(
                                action="update_index",
                                content_type="code",
                                resource=repo,
                                since=since.isoformat() if since else None,
                                changes_summary={
                                    "added": len(changes.get('added', [])),
                                    "modified": len(changes.get('modified', [])),
                                    "deleted": len(changes.get('deleted', []))
                                }
                            )
                
                if action_logger:
                    action_logger.log_action(
                        action="update_index",
                        content_type="code",
                        resource=repo,
                        since=since.isoformat() if since else None
                    )
                
                return (True, f"✅ Updated index for repository `{repo}`.\n"
                              f"New and changed files have been indexed for semantic search.")
                
        except Exception as e:
            logger.error(f"Error updating index for {repo}: {e}", exc_info=True)
            return (False, f"⚠️ Index Update Error\n\n"
                          f"Error updating index: {str(e)}\n\n"
                          f"*Next steps:*\n"
                          f"• Check repository access\n"
                          f"• Try force reindex: `@agent update index force`")
    
    @staticmethod
    def is_onboard_command(text: str) -> bool:
        """Check if text is an onboard command."""
        text_lower = text.lower()
        return "onboard" in text_lower or "this channel is for" in text_lower
    
    @staticmethod
    def is_status_command(text: str) -> bool:
        """Check if text is a status command."""
        return "status" in text.lower()
    
    @staticmethod
    def is_update_index_command(text: str) -> bool:
        """Check if text is an update index command."""
        text_lower = text.lower()
        return "update" in text_lower and "index" in text_lower or "reindex" in text_lower
    
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
