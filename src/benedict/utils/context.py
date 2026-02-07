"""Context Builder

Pure functions for building context from repository files using semantic search.
"""
import logging
from typing import List, Optional
from benedict.protocols import RepoReader, SemanticIndexer

logger = logging.getLogger(__name__)


def build_context(
    repo: str,
    question: str,
    repo_reader: RepoReader,
    semantic_indexer: Optional[SemanticIndexer] = None,
    max_tokens: int = 4000
) -> str:
    """Build relevant context for question using semantic search.
    
    Args:
        repo: Repository name
        question: User question
        repo_reader: Repository reader instance
        semantic_indexer: Optional semantic indexer for intelligent file selection
        max_tokens: Maximum tokens for context
        
    Returns:
        Formatted context string
    """
    parts = []
    
    # Always include README if it exists
    try:
        readme = repo_reader.read_file(repo, "README.md")
        parts.append(f"# README.md\n{readme}")
        logger.debug(f"Added README.md to context for {repo}")
    except FileNotFoundError:
        logger.debug(f"No README.md found for {repo}")
    except Exception as e:
        logger.warning(f"Error reading README.md for {repo}: {e}")
    
    # Use semantic search if available, otherwise fall back to keyword matching
    if semantic_indexer:
        try:
            # Ensure repository is indexed
            if not semantic_indexer.is_indexed(repo):
                logger.info(f"Indexing repository {repo} for semantic search...")
                semantic_indexer.index_repository(repo, repo_reader)
            
            # Perform semantic search
            results = semantic_indexer.search(repo, question, top_k=5)
            
            # Group results by file and get full file content
            seen_files = set()
            for result in results:
                file_path = result['file_path']
                if file_path in seen_files:
                    continue
                seen_files.add(file_path)
                
                try:
                    # Get full file content (semantic search gives us chunks)
                    content = repo_reader.read_file(repo, file_path)
                    content = truncate_file_content(content, max_lines=1000)
                    parts.append(f"# {file_path}\n{content}")
                    logger.debug(f"Added {file_path} to context (semantic match, score: {result['score']:.2f})")
                except Exception as e:
                    logger.warning(f"Error reading {file_path}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error in semantic search, falling back to keyword matching: {e}")
            # Fall through to keyword matching
    
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
                        logger.debug(f"Added {file_path} to context (keyword match)")
                    except Exception as e:
                        logger.warning(f"Error reading {file_path}: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Error listing files for {repo}: {e}")
    
    # Combine and truncate to fit token limit
    full_context = "\n\n".join(parts)
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
    lines = content.split('\n')
    if len(lines) <= max_lines:
        return content
    
    truncated = '\n'.join(lines[:max_lines])
    return truncated + f"\n\n[... file truncated after {max_lines} lines ...]"


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
    last_newline = truncated.rfind('\n')
    if last_newline > max_chars * 0.9:  # If we're close to a newline
        truncated = truncated[:last_newline]
    
    return truncated + "\n\n[... context truncated to fit token limit ...]"
