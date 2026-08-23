"""Context Builder

Pure functions for building context from repository files using semantic search.
"""

import logging
import re
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from benedict.protocols import RepoReader, SemanticIndexer
from benedict.operator_ui.recorder import record_stage

logger = logging.getLogger(__name__)


def build_context(
    repo: str,
    question: str,
    repo_reader: RepoReader,
    semantic_indexer: Optional[SemanticIndexer] = None,
    max_tokens: int = 4000,
    workspace_path: Optional[Path] = None,
    metadata_reader=None,
    action_logger=None,
) -> str:
    """Build relevant context for question using semantic search.

    Args:
        repo: Repository name
        question: User question
        repo_reader: Repository reader instance
        semantic_indexer: Optional semantic indexer for intelligent file selection
        max_tokens: Maximum tokens for context
        workspace_path: Optional workspace path for metadata and action log
        metadata_reader: Optional metadata reader for including metadata in context
        action_logger: Optional action logger for including recent actions

    Returns:
        Formatted context string
    """
    parts = []
    context_files: List[str] = []
    search_started = time.perf_counter()

    # Include recent actions if available
    if action_logger and workspace_path:
        try:
            recent_actions = action_logger.get_recent_actions(limit=5)
            if recent_actions:
                action_summary = "Recent workspace actions:\n"
                for action in recent_actions:
                    action_summary += f"- {action.get('action')}: {action.get('resource', 'N/A')} ({action.get('timestamp', '')[:10]})\n"
                parts.append(action_summary)
        except Exception as e:
            logger.warning(f"Error reading action log: {e}")

    # Include metadata summary if available
    if metadata_reader and workspace_path:
        try:
            repo_metadata_path = workspace_path / repo
            metadata = metadata_reader.read_metadata(repo_metadata_path)
            if metadata:
                metadata_summary = f"# Repository Metadata: {repo}\n"
                metadata_summary += f"Summary: {metadata.get('summary', 'N/A')}\n"
                metadata_summary += f"Purpose: {metadata.get('purpose', 'N/A')}\n"
                if metadata.get("files"):
                    metadata_summary += "\nKey files:\n"
                    for file_info in metadata.get("files", [])[:5]:
                        metadata_summary += (
                            f"- {file_info.get('name')}: {file_info.get('purpose', 'N/A')}\n"
                        )
                parts.append(metadata_summary)
        except Exception as e:
            logger.warning(f"Error reading metadata: {e}")

    # Check if user is asking for a specific file - read it directly
    requested_file = _extract_file_request(question)
    if requested_file:
        try:
            # Try to read the requested file directly
            content = repo_reader.read_file(repo, requested_file)
            parts.append(f"# {requested_file}\n{content}")
            context_files.append(requested_file)
            logger.info(f"Added directly requested file {requested_file} to context")
            # Still include other context, but prioritize the direct file read
        except FileNotFoundError:
            logger.debug(f"Requested file {requested_file} not found")
        except Exception as e:
            logger.warning(f"Error reading requested file {requested_file}: {e}")

    # Always include README if it exists
    try:
        readme = repo_reader.read_file(repo, "README.md")
        parts.append(f"# README.md\n{readme}")
        context_files.append("README.md")
        logger.debug(f"Added README.md to context for {repo}")
    except FileNotFoundError:
        logger.debug(f"No README.md found for {repo}")
    except Exception as e:
        logger.warning(f"Error reading README.md for {repo}: {e}")

    # Use semantic search if available, otherwise fall back to keyword matching
    if semantic_indexer:
        try:
            # Ensure repository is indexed (incremental update if already indexed)
            if not semantic_indexer.is_indexed(repo):
                logger.info(f"Indexing repository {repo} for semantic search...")
                semantic_indexer.index_repository(repo, repo_reader, workspace_path=workspace_path)
            else:
                # Incremental update: check for changes since last index
                # For now, we'll do a full update on each query (can be optimized later)
                # In the future, we could track last_index_time and use update_index()
                logger.debug(
                    f"Repository {repo} already indexed, skipping reindex (use update_index() for incremental updates)"
                )

            # Perform semantic search with metadata boosting if available
            results = semantic_indexer.search(
                repo,
                question,
                top_k=5,
                workspace_path=workspace_path,
                metadata_reader=metadata_reader,
            )
            hits = []
            for item in results[:8]:
                hits.append([item.get("file_path"), round(float(item.get("score") or 0), 2)])
            record_stage(
                "search",
                duration_ms=int((time.perf_counter() - search_started) * 1000),
                label=f"{len(results)} hits",
                detail={"query": question, "hits": hits},
            )

            # Group results by file and get full file content
            seen_files = set()
            # If a specific file was requested directly, don't add it again from semantic search
            if requested_file:
                seen_files.add(requested_file)
            
            for result in results:
                file_path = result["file_path"]
                if file_path in seen_files:
                    continue
                seen_files.add(file_path)

                try:
                    # Get full file content (semantic search gives us chunks)
                    content = repo_reader.read_file(repo, file_path)
                    content = truncate_file_content(content, max_lines=1000)
                    parts.append(f"# {file_path}\n{content}")
                    context_files.append(file_path)
                    logger.debug(
                        f"Added {file_path} to context (semantic match, score: {result['score']:.2f})"
                    )
                except Exception as e:
                    logger.warning(f"Error reading {file_path}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error in semantic search, falling back to keyword matching: {e}")
            record_stage(
                "search",
                status="error",
                duration_ms=int((time.perf_counter() - search_started) * 1000),
                label="search failed",
                detail={"error": str(e)},
            )
            # Fall through to keyword matching
    else:
        record_stage("search", status="skip", label="no indexer")

    # Fallback to keyword matching if semantic search not available or failed
    if not semantic_indexer or len(parts) == 1:  # Only README added
        keywords = extract_keywords(question)
        if keywords:
            try:
                all_files = repo_reader.list_files(repo)
                relevant = find_relevant_files(all_files, keywords)

                # Add relevant files (limit to 5)
                for file_path in relevant[:5]:
                    try:
                        content = repo_reader.read_file(repo, file_path)
                        content = truncate_file_content(content, max_lines=1000)
                        parts.append(f"# {file_path}\n{content}")
                        context_files.append(file_path)
                        logger.debug(f"Added {file_path} to context (keyword match)")
                    except Exception as e:
                        logger.warning(f"Error reading {file_path}: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Error listing files for {repo}: {e}")

    # Combine and truncate to fit token limit
    full_context = "\n\n".join(parts)
    record_stage(
        "context",
        duration_ms=int((time.perf_counter() - search_started) * 1000),
        label=f"{len(context_files)} files",
        detail={"files": context_files},
    )
    return truncate_to_tokens(full_context, max_tokens)


def extract_keywords(question: str) -> List[str]:
    """Extract keywords from question.

    Simple implementation for M1: extract words longer than 3 characters.

    Args:
        question: User question

    Returns:
        List of keywords
    """
    words = question.lower().split()
    # Filter out common words and short words
    stop_words = {"what", "the", "this", "that", "with", "from", "about", "which"}
    keywords = [w for w in words if len(w) > 3 and w not in stop_words]
    return keywords


def find_relevant_files(files: List[str], keywords: List[str]) -> List[str]:
    """Find files matching keywords.

    Args:
        files: List of file paths
        keywords: List of keywords to match

    Returns:
        List of relevant file paths, sorted by relevance
    """
    if not keywords:
        return []

    relevant = []
    for file in files:
        file_lower = file.lower()
        # Count keyword matches
        matches = sum(1 for kw in keywords if kw in file_lower)
        if matches > 0:
            relevant.append((matches, file))

    # Sort by number of matches (descending)
    relevant.sort(reverse=True, key=lambda x: x[0])
    return [file for _, file in relevant]


def truncate_file_content(content: str, max_lines: int = 1000) -> str:
    """Truncate file content to maximum number of lines.

    Args:
        content: File content
        max_lines: Maximum number of lines

    Returns:
        Truncated content with indicator if truncated
    """
    lines = content.split("\n")
    if len(lines) <= max_lines:
        return content

    truncated = "\n".join(lines[:max_lines])
    return truncated + f"\n\n[... file truncated after {max_lines} lines ...]"


def _extract_file_request(question: str) -> Optional[str]:
    """Extract specific file path from question if user is asking for a file.
    
    Detects patterns like:
    - "tell me the contents of README.md"
    - "show me src/agent.py"
    - "read Makefile"
    - "what's in pyproject.toml"
    - "contents of docs/ARCHITECTURE.md"
    
    Args:
        question: User question
        
    Returns:
        File path if detected, None otherwise
    """
    question_lower = question.lower()
    
    # Patterns that indicate a file request
    file_request_patterns = [
        r"contents?\s+of\s+([^\s]+)",
        r"show\s+me\s+([^\s]+)",
        r"read\s+([^\s]+)",
        r"tell\s+me\s+(?:the\s+)?contents?\s+of\s+([^\s]+)",
        r"what'?s?\s+in\s+([^\s]+)",
        r"what\s+does\s+([^\s]+)\s+contain",
        r"display\s+([^\s]+)",
        r"open\s+([^\s]+)",
    ]
    
    for pattern in file_request_patterns:
        match = re.search(pattern, question_lower)
        if match:
            file_path = match.group(1).strip()
            # Remove trailing punctuation
            file_path = file_path.rstrip('.,!?;:')
            # Only return if it looks like a file path (contains . or starts with .)
            if '.' in file_path or file_path.startswith('.'):
                return file_path
    
    # Also check for explicit file mentions in quotes or backticks
    quoted_file = re.search(r'["\']([^"\']+\.[^"\']+)["\']', question)
    if quoted_file:
        return quoted_file.group(1)
    
    backtick_file = re.search(r'`([^`]+\.[^`]+)`', question)
    if backtick_file:
        return backtick_file.group(1)
    
    return None


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit token limit.

    Rough estimate: 1 token ≈ 4 characters.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens

    Returns:
        Truncated text with indicator if truncated
    """
    # Rough estimate: 1 token ≈ 4 characters
    max_chars = max_tokens * 4

    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Try to truncate at a reasonable boundary (end of line)
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars * 0.9:  # If we're close to a newline
        truncated = truncated[:last_newline]

    return truncated + "\n\n[... context truncated to fit token limit ...]"


def build_architect_context(
    agent: Any,
    query: str,
    state: Dict[str, Any]
) -> str:
    """Build context for architect queries across all projects.
    
    Args:
        agent: RepoAgent instance with semantic_indexer
        query: User query/question
        state: State dictionary with channels mapping
        
    Returns:
        Formatted context string with project list and combined search results
    """
    parts = []
    
    # 1. Get all channel→repo mappings
    channels = state.get("channels", {})
    
    # 2. Build project list
    projects = []
    for channel_id, config in channels.items():
        repo = config.get("repo")
        if repo:
            projects.append({
                "channel_id": channel_id,
                "repo": repo,
                "onboarded_at": config.get("onboarded_at")
            })
    
    # 3. Add project list to context
    if projects:
        projects_context = f"# Projects Managed by Benedict ({len(projects)} total)\n\n"
        for project in projects:
            projects_context += f"- **{project['repo']}** (channel: {project['channel_id']})\n"
        parts.append(projects_context)
    else:
        parts.append("# Projects Managed by Benedict\n\nNo projects currently onboarded.")
    
    # 4. Search across all projects' RAG
    all_results = []
    if agent.semantic_indexer and projects:
        for project in projects:
            repo = project["repo"]
            try:
                # Ensure repository is indexed
                if not agent.semantic_indexer.is_indexed(repo):
                    logger.debug(f"Repository {repo} not indexed, skipping for architect query")
                    continue
                
                # Perform semantic search
                results = agent.semantic_indexer.search(repo, query, top_k=5)
                for result in results:
                    result["project"] = repo
                    all_results.append(result)
            except Exception as e:
                logger.warning(f"Error searching repository {repo} for architect query: {e}")
                continue
    
    # 5. Combine search results into context
    if all_results:
        # Sort by score (descending) and take top 10
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_results = all_results[:10]
        
        results_context = f"\n# Relevant Code Across Projects ({len(all_results)} total results, showing top {len(top_results)})\n\n"
        for result in top_results:
            project = result.get("project", "unknown")
            file_path = result.get("file_path", "unknown")
            content = result.get("content", "")
            score = result.get("score", 0)
            
            results_context += f"## [{project}] {file_path} (score: {score:.2f})\n"
            results_context += f"```\n{content[:500]}{'...' if len(content) > 500 else ''}\n```\n\n"
        
        parts.append(results_context)
    else:
        parts.append("\n# Relevant Code Across Projects\n\nNo relevant code found across projects.")
    
    return "\n".join(parts)
