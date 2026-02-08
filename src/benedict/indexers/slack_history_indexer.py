"""Slack Conversation History Indexer

Implements ConversationHistoryIndexer protocol for Slack.
"""

import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from benedict.lib.dateutil import normalize_to_utc
from benedict.protocols.conversation_history_indexer import (
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
        self, context_id: str, since: Optional[datetime] = None, limit: Optional[int] = None
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
                with open(json_file, "r", encoding="utf-8") as f:
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
                            if "." in ts:
                                conv_dt = datetime.fromtimestamp(float(ts))
                            else:
                                conv_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
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
        semantic_indexer=None,
    ) -> None:
        """Index Slack conversations into workspace.

        Args:
            context_id: Context identifier (Slack channel_id)
            workspace_path: Path to workspace directory
            since: Optional datetime to index conversations since
            semantic_indexer: Optional semantic indexer to also index conversations for search
        """
        if not self.slack_client:
            logger.warning("Slack client not available, cannot index conversations")
            return

        workspace_path = Path(workspace_path)
        conversation_dir = workspace_path / "conversation_history"
        conversation_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Indexing Slack conversations for channel {context_id} into {conversation_dir}"
        )

        # Convert datetime to Slack timestamp format (Unix timestamp as string)
        oldest_ts = None
        if since:
            # Normalize to UTC and convert to timestamp
            since_utc = normalize_to_utc(since)
            oldest_ts = str(since_utc.timestamp())

        # Fetch all messages from the channel
        all_messages = self._fetch_channel_history(context_id, oldest=oldest_ts)

        if not all_messages:
            logger.info(f"No messages found for channel {context_id}")
            return

        logger.info(f"Fetched {len(all_messages)} messages from channel {context_id}")

        # Fetch thread replies for threaded messages
        threaded_messages = {}
        for msg in all_messages:
            if msg.get("thread_ts") and msg.get("thread_ts") != msg.get("ts"):
                # This is a thread reply, fetch full thread
                thread_ts = msg.get("thread_ts")
                if thread_ts not in threaded_messages:
                    thread_replies = self._fetch_thread_replies(context_id, thread_ts)
                    threaded_messages[thread_ts] = thread_replies

        # Store messages in JSON file
        output_file = conversation_dir / f"{context_id}.json"
        conversation_data = {
            "channel_id": context_id,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "message_count": len(all_messages),
            "messages": all_messages,
            "threads": threaded_messages,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(conversation_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Stored {len(all_messages)} messages to {output_file}")

        # Optionally index into semantic indexer
        if semantic_indexer:
            self._index_into_semantic_indexer(
                context_id, all_messages, threaded_messages, semantic_indexer
            )

    def update_index(
        self,
        context_id: str,
        workspace_path: Path,
        since: Optional[datetime] = None,
        semantic_indexer=None,
    ) -> None:
        """Incrementally update conversation index with new messages.

        Args:
            context_id: Context identifier (Slack channel_id)
            workspace_path: Path to workspace directory
            since: Datetime to index conversations since (required for incremental updates)
            semantic_indexer: Optional semantic indexer to also index conversations for search
        """
        if not self.slack_client:
            logger.warning("Slack client not available, cannot update conversation index")
            return

        if not since:
            logger.warning("update_index requires 'since' parameter for incremental updates")
            return

        workspace_path = Path(workspace_path)
        conversation_dir = workspace_path / "conversation_history"
        conversation_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Updating conversation index for channel {context_id} since {since}")

        # Convert datetime to Slack timestamp (normalize to UTC first)
        since_utc = normalize_to_utc(since)
        oldest_ts = str(since_utc.timestamp())

        # Fetch new messages since 'since'
        new_messages = self._fetch_channel_history(context_id, oldest=oldest_ts)

        if not new_messages:
            logger.info(f"No new messages found for channel {context_id} since {since}")
            return

        logger.info(f"Fetched {len(new_messages)} new messages from channel {context_id}")

        # Load existing messages if file exists
        output_file = conversation_dir / f"{context_id}.json"
        existing_messages = []
        existing_threads = {}

        if output_file.exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_messages = existing_data.get("messages", [])
                    existing_threads = existing_data.get("threads", {})
            except Exception as e:
                logger.warning(f"Error reading existing conversation file: {e}")

        # Merge new messages (avoid duplicates by timestamp)
        existing_ts_set = {msg.get("ts") for msg in existing_messages}
        unique_new_messages = [
            msg for msg in new_messages if msg.get("ts") not in existing_ts_set
        ]

        if not unique_new_messages:
            logger.info("No new unique messages to add")
            return

        # Fetch thread replies for new threaded messages
        for msg in unique_new_messages:
            if msg.get("thread_ts") and msg.get("thread_ts") != msg.get("ts"):
                thread_ts = msg.get("thread_ts")
                if thread_ts not in existing_threads:
                    thread_replies = self._fetch_thread_replies(context_id, thread_ts)
                    existing_threads[thread_ts] = thread_replies

        # Combine existing and new messages
        all_messages = existing_messages + unique_new_messages
        # Sort by timestamp (oldest first)
        all_messages.sort(key=lambda x: float(x.get("ts", "0")))

        # Update stored file
        conversation_data = {
            "channel_id": context_id,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "message_count": len(all_messages),
            "messages": all_messages,
            "threads": existing_threads,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(conversation_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Updated conversation file with {len(unique_new_messages)} new messages "
            f"(total: {len(all_messages)} messages)"
        )

        # Optionally index new messages into semantic indexer
        if semantic_indexer:
            self._index_into_semantic_indexer(
                context_id, unique_new_messages, existing_threads, semantic_indexer
            )

    def get_conversation_reader(self, workspace_path: Path) -> ConversationReader:
        """Get reader for accessing conversations.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            ConversationReader instance
        """
        return SlackConversationReader(workspace_path)

    def _fetch_channel_history(
        self, channel_id: str, oldest: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch channel history using Slack API with pagination.

        Args:
            channel_id: Slack channel ID
            oldest: Optional oldest timestamp (Unix timestamp as string)
            limit: Maximum number of messages to fetch

        Returns:
            List of message dictionaries
        """
        messages = []
        cursor = None

        while len(messages) < limit:
            try:
                params = {
                    "channel": channel_id,
                    "limit": min(200, limit - len(messages)),  # Slack max is 200 per request
                }

                if oldest:
                    params["oldest"] = oldest

                if cursor:
                    params["cursor"] = cursor

                response = self.slack_client.conversations_history(**params)

                if not response.get("ok"):
                    error = response.get("error", "unknown error")
                    logger.error(f"Error fetching channel history: {error}")
                    break

                batch = response.get("messages", [])
                if not batch:
                    break

                # Filter out bot messages and system messages
                filtered = [msg for msg in batch if self._should_index_message(msg)]
                messages.extend(filtered)

                # Check for more pages
                response_metadata = response.get("response_metadata", {})
                cursor = response_metadata.get("next_cursor")
                if not cursor:
                    break

            except Exception as e:
                logger.error(f"Error fetching channel history: {e}", exc_info=True)
                break

        logger.debug(f"Fetched {len(messages)} messages from channel {channel_id}")
        return messages[:limit]

    def _fetch_thread_replies(self, channel_id: str, thread_ts: str) -> List[Dict[str, Any]]:
        """Fetch thread replies using Slack API.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp

        Returns:
            List of message dictionaries in the thread
        """
        try:
            response = self.slack_client.conversations_replies(
                channel=channel_id, ts=thread_ts
            )

            if not response.get("ok"):
                error = response.get("error", "unknown error")
                logger.error(f"Error fetching thread replies: {error}")
                return []

            messages = response.get("messages", [])
            # Filter out bot messages and system messages
            filtered = [msg for msg in messages if self._should_index_message(msg)]
            return filtered

        except Exception as e:
            logger.error(f"Error fetching thread replies: {e}", exc_info=True)
            return []

    def _should_index_message(self, msg: Dict[str, Any]) -> bool:
        """Check if message should be indexed.

        Filters out:
        - Bot messages (subtype='bot_message')
        - System messages (subtype starts with 'channel_')
        - Deleted messages
        - Messages without text

        Args:
            msg: Message dictionary

        Returns:
            True if message should be indexed
        """
        # Skip bot messages
        if msg.get("subtype") == "bot_message":
            return False

        # Skip system messages
        subtype = msg.get("subtype", "")
        if subtype.startswith("channel_"):
            return False

        # Skip deleted messages
        if subtype == "message_deleted":
            return False

        # Must have text
        if not msg.get("text"):
            return False

        return True

    def _index_into_semantic_indexer(
        self,
        channel_id: str,
        messages: List[Dict[str, Any]],
        threads: Dict[str, List[Dict[str, Any]]],
        semantic_indexer,
    ) -> None:
        """Index messages into semantic indexer for search with embeddings.

        Args:
            channel_id: Slack channel ID
            messages: List of message dictionaries
            threads: Dictionary mapping thread_ts to thread replies
            semantic_indexer: Semantic indexer instance (ChromaDBSemanticIndexer)
        """
        if not semantic_indexer:
            return

        # Check if semantic indexer has the necessary attributes
        if not hasattr(semantic_indexer, "embedding_model") or not hasattr(
            semantic_indexer, "client"
        ):
            logger.debug("Semantic indexer does not support channel message indexing, skipping")
            return

        try:
            import numpy as np

            # Create a collection name for this channel
            collection_name = f"slack_channel_{hashlib.md5(channel_id.encode()).hexdigest()[:16]}"

            # Get or create collection
            try:
                collection = semantic_indexer.client.get_collection(collection_name)
            except Exception:
                collection = semantic_indexer.client.create_collection(
                    name=collection_name, metadata={"channel_id": channel_id, "type": "slack_channel"}
                )

            # Prepare documents for indexing
            documents = []
            metadatas = []
            ids = []

            # Index main messages
            for msg in messages:
                text = msg.get("text", "")
                if not text:
                    continue

                msg_ts = msg.get("ts", "")
                doc_id = f"{channel_id}:{msg_ts}"
                documents.append(text)
                
                # Build metadata, filtering out None values (ChromaDB doesn't accept None)
                metadata = {
                    "channel_id": channel_id,
                    "message_ts": msg_ts,
                    "type": "message",
                    "repo": "slack_channel",  # Use special repo identifier for channels
                }
                # Only add optional fields if they're not None
                if msg.get("thread_ts"):
                    metadata["thread_ts"] = msg.get("thread_ts")
                if msg.get("user"):
                    metadata["user"] = msg.get("user")
                
                metadatas.append(metadata)
                ids.append(doc_id)

            # Index thread replies
            for thread_ts, thread_messages in threads.items():
                for msg in thread_messages:
                    text = msg.get("text", "")
                    if not text:
                        continue

                    msg_ts = msg.get("ts", "")
                    doc_id = f"{channel_id}:{msg_ts}:thread"
                    documents.append(text)
                    
                    # Build metadata, filtering out None values (ChromaDB doesn't accept None)
                    metadata = {
                        "channel_id": channel_id,
                        "message_ts": msg_ts,
                        "thread_ts": thread_ts,
                        "type": "thread_reply",
                        "repo": "slack_channel",
                    }
                    # Only add optional fields if they're not None
                    if msg.get("user"):
                        metadata["user"] = msg.get("user")
                    
                    metadatas.append(metadata)
                    ids.append(doc_id)

            if not documents:
                logger.debug("No documents to index into semantic indexer")
                return

            logger.info(
                f"Indexing {len(documents)} messages from channel {channel_id} "
                f"into semantic indexer with embeddings"
            )

            # Generate embeddings
            embeddings = semantic_indexer.embedding_model.encode(documents, show_progress_bar=False)

            # Add to collection in batches (ChromaDB has max batch size limit of ~5461)
            batch_size = 5000
            total_batches = (len(documents) + batch_size - 1) // batch_size

            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(documents))

                batch_documents = documents[start_idx:end_idx]
                batch_embeddings = embeddings[start_idx:end_idx]
                batch_metadatas = metadatas[start_idx:end_idx]
                batch_ids = ids[start_idx:end_idx]

                collection.add(
                    embeddings=batch_embeddings.tolist(),
                    documents=batch_documents,
                    metadatas=batch_metadatas,
                    ids=batch_ids,
                )

            logger.info(
                f"✅ Indexed {len(documents)} messages from channel {channel_id} "
                f"into semantic indexer with embeddings"
            )

        except Exception as e:
            logger.warning(f"Error indexing messages into semantic indexer: {e}", exc_info=True)


class MockConversationHistoryIndexer:
    """Mock implementation for testing."""

    def __init__(self):
        """Initialize mock conversation history indexer."""
        logger.info("Initialized MockConversationHistoryIndexer")

    def index_conversations(
        self, context_id: str, workspace_path: Path, since: Optional[datetime] = None
    ) -> None:
        """Mock index conversations."""
        logger.debug(f"Mock indexing conversations for context {context_id}")

    def get_conversation_reader(self) -> ConversationReader:
        """Get mock conversation reader."""

        class MockReader:
            def read_conversations(
                self, context_id: str, since: Optional[datetime] = None, limit: Optional[int] = None
            ):
                return []

        return MockReader()
