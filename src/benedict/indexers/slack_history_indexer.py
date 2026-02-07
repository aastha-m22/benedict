"""Slack Conversation History Indexer

Implements ConversationHistoryIndexer protocol for Slack.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from benedict.protocols.conversation_history_indexer import (
    ConversationHistoryIndexer,
    ConversationReader,
)

logger = logging.getLogger(__name__)


class SlackConversationReader:
    """Reader for Slack conversations."""
    
    def __init__(self, workspace_path: Path):
        """Initialize Slack conversation reader.
        
        Args:
            workspace_path: Path to workspace directory
        """
        self.workspace_path = Path(workspace_path)
        self.conversation_dir = self.workspace_path / "conversation_history"
    
    def read_conversations(
        self,
        context_id: str,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Read Slack conversations from workspace.
        
        Args:
            context_id: Context identifier (not used, conversations are in workspace)
            since: Optional datetime to get conversations since
            limit: Optional limit on number of conversations
            
        Returns:
            List of conversation dictionaries
        """
        conversations = []
        
        if not self.conversation_dir.exists():
            return conversations
        
        # Read all JSON files in conversation_history directory
        for json_file in self.conversation_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle different JSON structures
                if isinstance(data, list):
                    conversations.extend(data)
                elif isinstance(data, dict) and "messages" in data:
                    conversations.extend(data["messages"])
                elif isinstance(data, dict):
                    conversations.append(data)
            except Exception as e:
                logger.warning(f"Error reading conversation file {json_file}: {e}")
                continue
        
        # Filter by since date if provided
        if since:
            filtered = []
            for conv in conversations:
                ts = conv.get("ts") or conv.get("timestamp")
                if ts:
                    try:
                        # Parse timestamp (Slack format or ISO)
                        if isinstance(ts, str):
                            if '.' in ts:
                                conv_dt = datetime.fromtimestamp(float(ts))
                            else:
                                conv_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        else:
                            conv_dt = datetime.fromtimestamp(ts)
                        
                        if conv_dt >= since:
                            filtered.append(conv)
                    except Exception:
                        filtered.append(conv)  # Include if we can't parse
                else:
                    filtered.append(conv)  # Include if no timestamp
            conversations = filtered
        
        # Apply limit
        if limit:
            conversations = conversations[:limit]
        
        return conversations


class SlackConversationHistoryIndexer:
    """Indexes Slack conversations into workspace."""
    
    def __init__(self, slack_client=None):
        """Initialize Slack conversation history indexer.
        
        Args:
            slack_client: Optional Slack client (for future use with Slack API)
        """
        self.slack_client = slack_client
        logger.info("Initialized SlackConversationHistoryIndexer")
    
    def index_conversations(
        self,
        context_id: str,
        workspace_path: Path,
        since: Optional[datetime] = None,
        semantic_indexer=None
    ) -> None:
        """Index Slack conversations into workspace.
        
        Args:
            context_id: Context identifier (Slack channel_id)
            workspace_path: Path to workspace directory
            since: Optional datetime to index conversations since
            semantic_indexer: Optional semantic indexer to also index conversations for search
        """
        workspace_path = Path(workspace_path)
        conversation_dir = workspace_path / "conversation_history"
        conversation_dir.mkdir(parents=True, exist_ok=True)
        
        # For now, this is a placeholder - in the future, this would:
        # 1. Use Slack API to fetch conversation history
        # 2. Store conversations in conversation_dir as JSON files
        # 3. Generate metadata overlays
        # 4. Optionally index into semantic_indexer for search
        
        logger.info(f"Indexing Slack conversations for context {context_id} into {conversation_dir}")
        
        # TODO: Implement actual Slack API integration
        # For now, log that indexing would happen here
        logger.debug("Slack API integration not yet implemented - placeholder")
    
    def update_index(
        self,
        context_id: str,
        workspace_path: Path,
        since: Optional[datetime] = None,
        semantic_indexer=None
    ) -> None:
        """Incrementally update conversation index with new messages.
        
        Args:
            context_id: Context identifier (Slack channel_id)
            workspace_path: Path to workspace directory
            since: Datetime to index conversations since (required for incremental updates)
            semantic_indexer: Optional semantic indexer to also index conversations for search
        """
        if not since:
            logger.warning("update_index requires 'since' parameter for incremental updates")
            return
        
        workspace_path = Path(workspace_path)
        conversation_dir = workspace_path / "conversation_history"
        conversation_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Updating conversation index for context {context_id} since {since}")
        
        # TODO: Implement incremental update:
        # 1. Fetch new messages from Slack API since 'since' datetime
        # 2. Append to existing conversation files or create new ones
        # 3. Update metadata overlays
        # 4. Optionally index new messages into semantic_indexer
        
        logger.debug("Slack API integration not yet implemented - placeholder")
    
    def get_conversation_reader(self, workspace_path: Path) -> ConversationReader:
        """Get reader for accessing conversations.
        
        Args:
            workspace_path: Path to workspace directory
            
        Returns:
            ConversationReader instance
        """
        return SlackConversationReader(workspace_path)


class MockConversationHistoryIndexer:
    """Mock implementation for testing."""
    
    def __init__(self):
        """Initialize mock conversation history indexer."""
        logger.info("Initialized MockConversationHistoryIndexer")
    
    def index_conversations(
        self,
        context_id: str,
        workspace_path: Path,
        since: Optional[datetime] = None
    ) -> None:
        """Mock index conversations."""
        logger.debug(f"Mock indexing conversations for context {context_id}")
    
    def get_conversation_reader(self) -> ConversationReader:
        """Get mock conversation reader."""
        class MockReader:
            def read_conversations(self, context_id: str, since: Optional[datetime] = None, limit: Optional[int] = None):
                return []
        return MockReader()
