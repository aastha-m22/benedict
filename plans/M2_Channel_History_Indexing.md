# M2: Channel History Indexing

Index Slack channel history for semantic search, similar to repository code indexing.

## 1. Overview

**What:**
Add semantic indexing for Slack channel history, allowing the agent to search through past conversations and include relevant context when answering questions.

**Why:**
Channel history contains valuable context:
- Previous discussions about code decisions
- Questions and answers about the repository
- Architecture discussions
- Bug reports and solutions
- Team knowledge that isn't in code

**When to use:**
When building context for LLM responses, include relevant channel history alongside repository code.

## 2. Non-Goals

- No real-time indexing (index on-demand or scheduled)
- No cross-channel search (channel-scoped only)
- No message editing/deletion tracking (index what exists)
- No DMs or private channels (public channels only)

## 3. Key Concepts

| Term | Meaning |
|------|---------|
| Channel History Reader | Protocol for fetching Slack channel messages |
| Channel Indexer | Extension of SemanticIndexer for channel messages |
| Message Chunk | Grouped messages for indexing (conversation context) |
| Channel Collection | ChromaDB collection per channel (like repo collections) |

## 4. High-Level Design

### Components

```
main.py (composition root)
  ├─> slack_client = SlackClient(token)
  ├─> channel_history_reader = SlackChannelHistoryReader(slack_client)
  ├─> semantic_indexer = ChromaDBSemanticIndexer()
  │     └─> Can index both repos and channels
  └─> agent = RepoAgent(..., channel_history_reader, semantic_indexer)
```

### Data Flow

1. User asks question in Slack channel
2. Agent builds context:
   - Repository code (existing)
   - Channel history (new) - semantic search for relevant messages
3. Combine both contexts
4. Send to LLM with combined context
5. Return response

### Key Invariants

- Channel history reader is injected, never instantiated in agent
- Same semantic indexer handles both repos and channels
- Channel collections separate from repo collections
- Indexing happens on-demand or scheduled, not real-time

## 5. API / Interface

### ChannelHistoryReader Protocol

```python
class ChannelHistoryReader(Protocol):
    """Protocol for reading Slack channel history."""
    
    def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 1000,
        oldest: Optional[str] = None,
        latest: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch channel message history.
        
        Args:
            channel_id: Slack channel ID
            limit: Maximum number of messages to fetch
            oldest: Oldest timestamp (Unix time)
            latest: Latest timestamp (Unix time)
            
        Returns:
            List of message dicts with keys: 'ts', 'user', 'text', 'thread_ts', etc.
        """
        ...
    
    def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str
    ) -> List[Dict[str, Any]]:
        """Fetch thread message history.
        
        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp
            
        Returns:
            List of message dicts in thread
        """
        ...
```

### SemanticIndexer Extension

Extend existing `SemanticIndexer` protocol:

```python
class SemanticIndexer(Protocol):
    # Existing methods...
    
    def index_channel(
        self,
        channel_id: str,
        channel_history_reader: ChannelHistoryReader
    ) -> None:
        """Index channel history for semantic search.
        
        Args:
            channel_id: Slack channel ID
            channel_history_reader: ChannelHistoryReader instance
        """
        ...
    
    def search_channel(
        self,
        channel_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search channel history using semantic similarity.
        
        Args:
            channel_id: Slack channel ID
            query: Search query/question
            top_k: Number of results to return
            
        Returns:
            List of dicts with keys: 'text', 'user', 'ts', 'thread_ts', 'score'
        """
        ...
    
    def is_channel_indexed(self, channel_id: str) -> bool:
        """Check if channel is indexed.
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            True if channel is indexed
        """
        ...
```

### Context Builder Extension

Extend `build_context` to include channel history:

```python
def build_context(
    repo: str,
    question: str,
    repo_reader: RepoReader,
    channel_id: Optional[str] = None,  # New parameter
    semantic_indexer: Optional[SemanticIndexer] = None,
    channel_history_reader: Optional[ChannelHistoryReader] = None,  # New parameter
    max_tokens: int = 4000
) -> str:
    """Build relevant context from repo code and channel history.
    
    Args:
        repo: Repository name
        question: User question
        repo_reader: Repository reader instance
        channel_id: Optional Slack channel ID for history search
        semantic_indexer: Optional semantic indexer
        channel_history_reader: Optional channel history reader
        max_tokens: Maximum tokens for context
        
    Returns:
        Formatted context string with repo code and channel history
    """
    # ... existing repo context building ...
    
    # Add channel history if available
    if channel_id and channel_history_reader and semantic_indexer:
        # Search channel history semantically
        # Add relevant messages to context
        ...
```

## 6. Implementation Details

### Step 1: Create ChannelHistoryReader Protocol

**File**: `channel_history_reader.py`

```python
"""Channel History Reader Protocol

Defines interface for reading Slack channel history.
"""
from typing import Protocol, List, Dict, Optional, Any


class ChannelHistoryReader(Protocol):
    """Protocol for reading Slack channel history."""
    
    def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 1000,
        oldest: Optional[str] = None,
        latest: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch channel message history."""
        ...
    
    def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str
    ) -> List[Dict[str, Any]]:
        """Fetch thread message history."""
        ...


def create_channel_history_reader(provider: str = "slack", **kwargs) -> ChannelHistoryReader:
    """Factory function to create ChannelHistoryReader instance."""
    if provider == "slack":
        from channel_history_reader_slack import SlackChannelHistoryReader
        return SlackChannelHistoryReader(**kwargs)
    elif provider == "mock":
        from channel_history_reader_mock import MockChannelHistoryReader
        return MockChannelHistoryReader()
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

### Step 2: Implement SlackChannelHistoryReader

**File**: `channel_history_reader_slack.py`

```python
"""Slack Channel History Reader Implementation

Uses Slack Web API to fetch channel history.
"""
import logging
from typing import List, Dict, Optional, Any
from slack_sdk import WebClient

from channel_history_reader import ChannelHistoryReader

logger = logging.getLogger(__name__)


class SlackChannelHistoryReader:
    """Slack API implementation of ChannelHistoryReader."""
    
    def __init__(self, slack_client: WebClient):
        """Initialize with Slack WebClient.
        
        Args:
            slack_client: Slack WebClient instance
        """
        self.client = slack_client
        logger.info("Initialized SlackChannelHistoryReader")
    
    def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 1000,
        oldest: Optional[str] = None,
        latest: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch channel message history with pagination.
        
        Handles Slack API pagination automatically.
        Filters out bot messages and system messages.
        """
        messages = []
        cursor = None
        
        while len(messages) < limit:
            try:
                response = self.client.conversations_history(
                    channel=channel_id,
                    limit=min(200, limit - len(messages)),  # Slack max is 200
                    oldest=oldest,
                    latest=latest,
                    cursor=cursor
                )
                
                if not response["ok"]:
                    logger.error(f"Error fetching history: {response.get('error')}")
                    break
                
                batch = response["messages"]
                
                # Filter out bot messages, system messages, etc.
                filtered = [
                    msg for msg in batch
                    if self._should_index_message(msg)
                ]
                
                messages.extend(filtered)
                
                # Check for more pages
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching channel history: {e}")
                break
        
        logger.info(f"Fetched {len(messages)} messages from channel {channel_id}")
        return messages[:limit]
    
    def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str
    ) -> List[Dict[str, Any]]:
        """Fetch thread replies."""
        try:
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            
            if not response["ok"]:
                logger.error(f"Error fetching thread: {response.get('error')}")
                return []
            
            messages = response["messages"]
            filtered = [
                msg for msg in messages
                if self._should_index_message(msg)
            ]
            
            return filtered
        except Exception as e:
            logger.error(f"Error fetching thread history: {e}")
            return []
    
    def _should_index_message(self, msg: Dict[str, Any]) -> bool:
        """Check if message should be indexed.
        
        Filters out:
        - Bot messages (subtype='bot_message')
        - System messages (subtype starts with 'channel_')
        - Messages without text
        - Deleted messages
        """
        # Skip bot messages
        if msg.get("subtype") == "bot_message":
            return False
        
        # Skip system messages
        if msg.get("subtype", "").startswith("channel_"):
            return False
        
        # Skip deleted messages
        if msg.get("subtype") == "message_deleted":
            return False
        
        # Must have text
        if not msg.get("text"):
            return False
        
        return True
```

### Step 3: Extend ChromaDBSemanticIndexer

**File**: `semantic_indexer_chromadb.py`

Add methods to existing class:

```python
def index_channel(
    self,
    channel_id: str,
    channel_history_reader: ChannelHistoryReader
) -> None:
    """Index channel history for semantic search.
    
    Groups messages into conversation chunks for better context.
    """
    collection = self._get_channel_collection(channel_id)
    
    # Check if already indexed
    if collection.count() > 0:
        logger.info(f"Channel {channel_id} already indexed ({collection.count()} chunks)")
        return
    
    logger.info(f"Indexing channel {channel_id}...")
    
    # Fetch channel history
    messages = channel_history_reader.fetch_channel_history(channel_id, limit=1000)
    
    if not messages:
        logger.warning(f"No messages to index for channel {channel_id}")
        return
    
    # Group messages into conversation chunks
    chunks = self._chunk_messages(messages)
    
    # Process chunks
    documents = []
    metadatas = []
    ids = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"{channel_id}:{i}"
        documents.append(chunk["text"])
        metadatas.append({
            "channel_id": channel_id,
            "message_ts": chunk.get("ts"),
            "thread_ts": chunk.get("thread_ts"),
            "user": chunk.get("user"),
            "chunk_index": i
        })
        ids.append(chunk_id)
    
    # Generate embeddings
    logger.info(f"Generating embeddings for {len(documents)} chunks...")
    embeddings = self.embedding_model.encode(documents, show_progress_bar=False)
    
    # Add to collection
    collection.add(
        embeddings=embeddings.tolist(),
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    logger.info(f"Indexed {len(documents)} chunks from channel {channel_id}")

def _get_channel_collection(self, channel_id: str) -> chromadb.Collection:
    """Get or create collection for channel."""
    collection_name = f"channel_{hashlib.md5(channel_id.encode()).hexdigest()[:16]}"
    
    if collection_name not in self.collections:
        try:
            self.collections[collection_name] = self.client.get_collection(collection_name)
        except Exception:
            self.collections[collection_name] = self.client.create_collection(
                name=collection_name,
                metadata={"channel_id": channel_id, "type": "channel"}
            )
    
    return self.collections[collection_name]

def _chunk_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group messages into conversation chunks.
    
    Groups consecutive messages from same thread or same user
    into chunks for better semantic context.
    """
    chunks = []
    current_chunk = None
    
    for msg in messages:
        thread_ts = msg.get("thread_ts") or msg.get("ts")
        user = msg.get("user")
        text = msg.get("text", "")
        
        # Start new chunk if:
        # - No current chunk
        # - Different thread
        # - Different user and previous chunk is large enough
        if (not current_chunk or
            current_chunk.get("thread_ts") != thread_ts or
            (current_chunk.get("user") != user and len(current_chunk["text"]) > 500)):
            
            if current_chunk:
                chunks.append(current_chunk)
            
            current_chunk = {
                "text": text,
                "ts": msg.get("ts"),
                "thread_ts": thread_ts,
                "user": user
            }
        else:
            # Append to current chunk
            current_chunk["text"] += "\n\n" + text
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def search_channel(
    self,
    channel_id: str,
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Search channel history using semantic similarity."""
    collection = self._get_channel_collection(channel_id)
    
    if collection.count() == 0:
        logger.warning(f"Channel {channel_id} not indexed yet")
        return []
    
    # Embed query
    query_embedding = self.embedding_model.encode([query])[0]
    
    # Search
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k
    )
    
    # Format results
    formatted_results = []
    for i, doc_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        
        formatted_results.append({
            "text": results["documents"][0][i],
            "ts": metadata.get("message_ts"),
            "thread_ts": metadata.get("thread_ts"),
            "user": metadata.get("user"),
            "score": 1 - distance  # Convert distance to similarity score
        })
    
    return formatted_results

def is_channel_indexed(self, channel_id: str) -> bool:
    """Check if channel is indexed."""
    try:
        collection = self._get_channel_collection(channel_id)
        return collection.count() > 0
    except Exception:
        return False
```

### Step 4: Update SemanticIndexer Protocol

**File**: `semantic_indexer.py`

Add new methods to protocol:

```python
class SemanticIndexer(Protocol):
    # Existing methods...
    
    def index_channel(
        self,
        channel_id: str,
        channel_history_reader: "ChannelHistoryReader"
    ) -> None:
        """Index channel history for semantic search."""
        ...
    
    def search_channel(
        self,
        channel_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search channel history using semantic similarity."""
        ...
    
    def is_channel_indexed(self, channel_id: str) -> bool:
        """Check if channel is indexed."""
        ...
```

### Step 5: Update Context Builder

**File**: `context.py`

```python
def build_context(
    repo: str,
    question: str,
    repo_reader: RepoReader,
    channel_id: Optional[str] = None,
    semantic_indexer: Optional[SemanticIndexer] = None,
    channel_history_reader: Optional[ChannelHistoryReader] = None,
    max_tokens: int = 4000
) -> str:
    """Build relevant context from repo code and channel history."""
    parts = []
    
    # ... existing repo context building ...
    
    # Add channel history if available
    if channel_id and channel_history_reader and semantic_indexer:
        try:
            # Ensure channel is indexed
            if not semantic_indexer.is_channel_indexed(channel_id):
                logger.info(f"Indexing channel {channel_id} for semantic search...")
                semantic_indexer.index_channel(channel_id, channel_history_reader)
            
            # Perform semantic search
            channel_results = semantic_indexer.search_channel(channel_id, question, top_k=3)
            
            if channel_results:
                parts.append("\n# Channel History Context\n")
                for result in channel_results:
                    parts.append(
                        f"**Message** (score: {result['score']:.2f}):\n"
                        f"{result['text']}\n"
                    )
                logger.debug(f"Added {len(channel_results)} channel messages to context")
        except Exception as e:
            logger.warning(f"Error searching channel history: {e}")
    
    # Combine and truncate
    full_context = "\n\n".join(parts)
    return truncate_to_tokens(full_context, max_tokens)
```

### Step 6: Update Agent

**File**: `agent.py`

```python
class RepoAgent:
    def __init__(
        self,
        state_file: str = "state.json",
        llm: Optional[LLM] = None,
        repo_reader: Optional[RepoReader] = None,
        semantic_indexer: Optional[SemanticIndexer] = None,
        conversation_repository: Optional[ConversationRepository] = None,
        channel_history_reader: Optional[ChannelHistoryReader] = None  # New parameter
    ):
        # ... existing initialization ...
        self.channel_history_reader = channel_history_reader
    
    def handle_conversation(
        self,
        channel_id: str,
        text: str,
        thread_ts: str
    ) -> Tuple[bool, str]:
        # ... existing code ...
        
        # Build context (now includes channel history)
        context = build_context(
            repo,
            combined_text,
            self.repo_reader,
            channel_id=channel_id,  # Pass channel_id
            semantic_indexer=self.semantic_indexer,
            channel_history_reader=self.channel_history_reader  # Pass reader
        )
        
        # ... rest of method ...
```

### Step 7: Update Main Composition Root

**File**: `main.py`

```python
from channel_history_reader import create_channel_history_reader
from slack_sdk import WebClient

def main():
    # ... existing setup ...
    
    # Create Slack client for channel history
    slack_client = WebClient(token=bot_token)
    
    # Create channel history reader
    channel_history_reader = None
    try:
        channel_history_reader = create_channel_history_reader(
            provider="slack",
            slack_client=slack_client
        )
        logger.info("✅ Channel history reader initialized")
    except Exception as e:
        logger.warning(f"⚠️ Channel history reader not available: {e}")
    
    # Create agent with channel history reader
    agent = RepoAgent(
        state_file=state_file,
        llm=llm,
        repo_reader=repo_reader,
        semantic_indexer=semantic_indexer,
        conversation_repository=conversation_repository,
        channel_history_reader=channel_history_reader  # New dependency
    )
    
    # ... rest of main ...
```

### Step 8: Create Mock Implementation

**File**: `channel_history_reader_mock.py`

```python
"""Mock Channel History Reader for testing."""
from typing import List, Dict, Any, Optional
from channel_history_reader import ChannelHistoryReader


class MockChannelHistoryReader:
    """Mock implementation for testing."""
    
    def fetch_channel_history(
        self,
        channel_id: str,
        limit: int = 1000,
        oldest: Optional[str] = None,
        latest: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return mock messages."""
        return [
            {
                "ts": "1234567890.123456",
                "user": "U123456",
                "text": "Mock message about authentication",
                "thread_ts": None
            }
        ]
    
    def fetch_thread_history(
        self,
        channel_id: str,
        thread_ts: str
    ) -> List[Dict[str, Any]]:
        """Return mock thread messages."""
        return []
```

## 7. Happy Path Example

1. User asks: `@agent how did we decide on the auth approach?`
2. Agent:
   - Searches repository code semantically (existing)
   - Searches channel history semantically (new)
   - Finds relevant messages: "We discussed using OAuth2 because..."
   - Combines both contexts
   - Sends to LLM with full context
3. LLM responds with answer referencing both code and discussion history

## 8. Edge Cases & Failure Modes

### Rate Limiting
- **Problem**: Slack API rate limits
- **Solution**: Implement exponential backoff, cache results

### Large Channels
- **Problem**: Channels with 10k+ messages
- **Solution**: Limit indexing to recent messages (e.g., last 30 days), paginate

### Missing Permissions
- **Problem**: Bot doesn't have `channels:history` scope
- **Solution**: Graceful degradation, log warning, skip channel indexing

### Empty Channels
- **Problem**: Channel has no messages
- **Solution**: Skip indexing, return empty results

### Message Formatting
- **Problem**: Slack messages have formatting, mentions, links
- **Solution**: Clean text before indexing (strip formatting, resolve user mentions)

## 9. Constraints & Assumptions

- **Slack API Limits**: 200 messages per request, rate limits apply
- **Indexing Time**: Can be slow for large channels (1000+ messages)
- **Storage**: ChromaDB collections per channel (similar to repos)
- **Permissions**: Requires `channels:history` scope (already have it)

## 10. Alternatives Considered

### Option A: Index All Messages Individually
- **Rejected**: Too many small chunks, poor semantic context

### Option B: Index Entire Channel as One Document
- **Rejected**: Too large, poor search granularity

### Option C: Group by Thread
- **Considered**: Good for threaded discussions, but many messages aren't threaded
- **Chosen**: Hybrid approach - group by thread when available, otherwise by conversation flow

### Option D: Real-time Indexing
- **Rejected**: Too complex, on-demand indexing is sufficient

## 11. Implementation Checklist

- [ ] Create `channel_history_reader.py` protocol
- [ ] Create `channel_history_reader_slack.py` implementation
- [ ] Create `channel_history_reader_mock.py` mock
- [ ] Extend `semantic_indexer.py` protocol with channel methods
- [ ] Extend `semantic_indexer_chromadb.py` with channel indexing
- [ ] Update `context.py` to include channel history
- [ ] Update `agent.py` to pass channel_id and reader
- [ ] Update `main.py` to create channel history reader
- [ ] Add tests for channel history indexing
- [ ] Update documentation

## 12. Success Criteria

- ✅ Channel history can be indexed semantically
- ✅ Channel history search returns relevant messages
- ✅ Context builder includes channel history alongside repo code
- ✅ LLM responses reference both code and discussion history
- ✅ Graceful degradation if channel history unavailable
- ✅ Handles large channels efficiently
- ✅ Respects Slack API rate limits

## 13. Dependencies

**No new packages needed** - Uses existing:
- `slack_sdk` (already have via `slack-bolt`)
- `chromadb` (already have)
- `sentence-transformers` (already have)

## 14. Rollout Plan

1. **Implement** - Build all components
2. **Test locally** - Index test channel, verify search works
3. **Deploy** - Update production bot
4. **Monitor** - Watch for rate limits, indexing performance
5. **Iterate** - Improve message chunking, add scheduling

Ready to implement M2.
