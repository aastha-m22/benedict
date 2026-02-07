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
        conversation_repository: Optional[ConversationRepository] = None
    ):
        """Initialize repository agent.
        
        Args:
            state_file: Path to state JSON file (used for conversation repository if not provided)
            llm: Optional LLM instance for intelligent responses
            repo_reader: Optional repository reader instance
            semantic_indexer: Optional semantic indexer for intelligent file selection
            conversation_repository: Optional conversation repository (created from state_file if None)
        """
        self.state_file = Path(state_file)
        self.llm = llm
        self.repo_reader = repo_reader
        self.semantic_indexer = semantic_indexer
        
        # Create conversation repository if not provided
        if conversation_repository is None:
            from conversation_repository import create_conversation_repository
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
            return (False, "⚠️ I couldn't find a repository name in your message.\n"
                          "Please use format: `@agent onboard repo foo/bar`")
        
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
            return (False, "⚠️ This channel hasn't been onboarded yet.\n"
                          "To get started: `@agent onboard repo your-org/your-repo`", None)
        
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
            return (False, "⚠️ This channel hasn't been onboarded yet.\n"
                          "To get started: `@agent onboard repo your-org/your-repo`")
        
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
            context = build_context(
                repo, 
                combined_text, 
                self.repo_reader,
                semantic_indexer=self.semantic_indexer
            )
        except Exception as e:
            logger.error(f"Error building context for {repo}: {e}")
            return (False, f"⚠️ Error reading repository `{repo}`: {str(e)}")
        
        # Build system message with repository context
        system = (
            f"You are a helpful technical engineer assistant for the repository '{repo}'.\n\n"
            f"Repository Context:\n{context}\n\n"
            f"Answer questions about the repository code and architecture based on the context provided above."
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
            return (False, "⚠️ Error generating response. Please try again.")
    
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
