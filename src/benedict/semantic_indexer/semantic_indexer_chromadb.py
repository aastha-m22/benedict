"""ChromaDB Semantic Indexer Implementation

Uses sentence-transformers for embeddings and ChromaDB for vector storage.
"""

import logging
import hashlib
import os
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any

import numpy as np
from benedict.lib.dateutil import normalize_to_utc
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

from benedict.protocols.repo_reader import RepoReader
from benedict.protocols.repo_change_detector import RepoChangeDetector
from benedict.metadata import MetadataGenerator

logger = logging.getLogger(__name__)


class ChromaDBSemanticIndexer:
    """ChromaDB-based semantic indexer for code repositories."""

    def __init__(
        self,
        persist_directory: str = "./.chroma_db",
        metadata_generator: Optional[MetadataGenerator] = None,
        change_detector: Optional[RepoChangeDetector] = None,
    ):
        """Initialize ChromaDB semantic indexer.

        Args:
            persist_directory: Directory to persist ChromaDB data
            metadata_generator: Optional metadata generator for creating .metadata.benedict overlays
            change_detector: Optional change detector for git-based incremental updates
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(exist_ok=True)

        # Initialize embedding model
        # Using a lightweight, fast model suitable for code
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory), settings=Settings(anonymized_telemetry=False)
        )

        # Collection name is based on repo name, created on-demand
        self.collections: Dict[str, chromadb.Collection] = {}

        # Initialize metadata generator
        self.metadata_generator = metadata_generator or MetadataGenerator()

        # Store change detector for incremental updates
        self.change_detector = change_detector

        # Configure chunk size (default: 2000 characters, configurable via BENEDICT_CHUNK_SIZE env var)
        self.max_chunk_size = int(os.environ.get("BENEDICT_CHUNK_SIZE", "2000"))
        logger.info(
            f"Initialized ChromaDBSemanticIndexer with persist_dir={persist_directory}, max_chunk_size={self.max_chunk_size}"
        )

    def _get_collection(self, repo: str) -> chromadb.Collection:
        """Get or create collection for repository.

        Args:
            repo: Repository identifier

        Returns:
            ChromaDB collection for this repository
        """
        # Sanitize repo name for collection name
        collection_name = f"repo_{hashlib.md5(repo.encode()).hexdigest()[:16]}"

        if collection_name not in self.collections:
            try:
                self.collections[collection_name] = self.client.get_collection(collection_name)
                logger.debug(f"Loaded existing collection for repo {repo}")
            except Exception:
                self.collections[collection_name] = self.client.create_collection(
                    name=collection_name, metadata={"repo": repo}
                )
                logger.debug(f"Created new collection for repo {repo}")

        return self.collections[collection_name]

    def index_repository(
        self,
        repo: str,
        repo_reader: RepoReader,
        workspace_path: Optional[Path] = None,
        force: bool = False,
    ) -> None:
        """Index a repository for semantic search.

        Args:
            repo: Repository identifier
            repo_reader: RepoReader instance to read files
            workspace_path: Optional workspace path for generating metadata overlays
            force: If True, reindex even if already indexed (default: False)
        """
        collection = self._get_collection(repo)

        # Check if already indexed (has documents)
        if collection.count() > 0 and not force:
            logger.info(
                f"Repository {repo} already indexed ({collection.count()} chunks), skipping full reindex."
            )
            # Still generate/update metadata if workspace_path provided
            if workspace_path:
                self._generate_metadata_overlays(repo, repo_reader, workspace_path)
            return

        logger.info(f"Indexing repository {repo} (force={force})...")

        # Clear existing index if force reindexing
        if force and collection.count() > 0:
            logger.info(f"Clearing existing index for {repo}")
            self.client.delete_collection(name=collection.name)
            collection = self._get_collection(repo)  # Recreate empty collection

        # Get all files
        try:
            all_files = repo_reader.list_files(repo)
        except Exception as e:
            logger.error(f"Error listing files for {repo}: {e}")
            return

        # Filter to code/text files (exclude binaries, large files)
        code_files = self._filter_code_files(all_files)

        # Index files
        self._index_files(repo, repo_reader, collection, code_files, workspace_path=workspace_path)

        # Generate metadata overlays if workspace_path provided
        if workspace_path:
            self._generate_metadata_overlays(repo, repo_reader, workspace_path)

    def search(
        self,
        repo: str,
        query: str,
        top_k: int = 5,
        workspace_path: Optional[Path] = None,
        metadata_reader=None,
    ) -> List[Dict[str, Any]]:
        """Search repository using semantic similarity.

        Args:
            repo: Repository identifier
            query: Search query/question
            top_k: Number of results to return
            workspace_path: Optional workspace path for metadata-based boosting
            metadata_reader: Optional metadata reader for directory-level search

        Returns:
            List of dicts with keys: 'file_path', 'content', 'score'
        """
        collection = self._get_collection(repo)

        if collection.count() == 0:
            logger.warning(f"Repository {repo} not indexed yet")
            return []

        # Stage 1: Find relevant directories via metadata search (if available)
        relevant_dir_paths = set()
        if metadata_reader and workspace_path:
            try:
                metadata_matches = metadata_reader.search_metadata(workspace_path, query)
                for match in metadata_matches:
                    # Store relative paths from repo root
                    rel_path = match["path"]
                    if rel_path.startswith(repo + "/"):
                        rel_path = rel_path[len(repo) + 1 :]
                    relevant_dir_paths.add(rel_path)
                    # Also add parent directories
                    path_parts = rel_path.split("/")
                    for i in range(1, len(path_parts)):
                        relevant_dir_paths.add("/".join(path_parts[:i]))
                logger.debug(
                    f"Found {len(relevant_dir_paths)} relevant directories via metadata search"
                )
            except Exception as e:
                logger.debug(f"Error in metadata search: {e}")

        # Embed query
        query_embedding = self.embedding_model.encode([query])[0]

        # Search with higher top_k if we have metadata boosting (to allow re-ranking)
        search_top_k = top_k * 2 if relevant_dir_paths else top_k

        # Search
        results = collection.query(
            query_embeddings=[query_embedding.tolist()], n_results=search_top_k
        )

        # Format results and apply metadata-based boosting
        formatted_results = []
        if results["documents"] and len(results["documents"][0]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0

                # Convert distance to similarity score (lower distance = higher similarity)
                score = 1.0 / (1.0 + distance)

                file_path = metadata.get("file_path", "unknown")

                # Boost score if file is in a relevant directory
                if relevant_dir_paths:
                    file_dir = str(Path(file_path).parent)
                    # Check if file's directory or any parent matches relevant directories
                    for rel_dir in relevant_dir_paths:
                        if file_dir == rel_dir or file_dir.startswith(rel_dir + "/"):
                            score *= 1.2  # 20% boost for files in relevant directories
                            logger.debug(
                                f"Boosted score for {file_path} (in relevant directory: {rel_dir})"
                            )
                            break

                formatted_results.append({"file_path": file_path, "content": doc, "score": score})

        # Re-sort by boosted score and return top_k
        formatted_results.sort(key=lambda x: x["score"], reverse=True)
        formatted_results = formatted_results[:top_k]

        logger.debug(
            f"Semantic search for '{query}' in {repo} returned {len(formatted_results)} results"
        )
        return formatted_results

    def update_index(
        self,
        repo: str,
        repo_reader: RepoReader,
        workspace_path: Optional[Path] = None,
        since: Optional[datetime] = None,
    ) -> None:
        """Incrementally update index with new/changed content.

        Args:
            repo: Repository identifier
            repo_reader: RepoReader instance to read files
            workspace_path: Optional workspace path for generating metadata overlays
            since: Optional datetime to only index files modified since this time
        """
        collection = self._get_collection(repo)

        if not workspace_path:
            logger.warning("Workspace path not provided, cannot perform incremental update.")
            self.index_repository(repo, repo_reader, workspace_path=workspace_path, force=True)
            return

        repo_full_path = workspace_path / repo
        if not repo_full_path.exists():
            logger.warning(f"Repository path {repo_full_path} does not exist, cannot update index.")
            return

        # Use git-based detection if available, otherwise fall back to file modification time
        if self.change_detector and self.change_detector.supports_git(repo_full_path):
            self._update_index_git(repo, repo_reader, collection, repo_full_path, since)
        else:
            self._update_index_file_mtime(repo, repo_reader, collection, repo_full_path, since)

        # Generate/update metadata overlays
        if workspace_path:
            self._generate_metadata_overlays(repo, repo_reader, workspace_path)

    def _update_index_git(
        self,
        repo: str,
        repo_reader: RepoReader,
        collection: chromadb.Collection,
        repo_full_path: Path,
        since: Optional[datetime],
    ) -> None:
        """Update index using git change detection."""
        logger.info(f"Updating index for {repo} using git change detection (since={since})...")

        changes = self.change_detector.detect_changes(repo_full_path, since=since)
        added_files = changes.get("added", [])
        modified_files = changes.get("modified", [])
        deleted_files = changes.get("deleted", [])

        if not (added_files or modified_files or deleted_files):
            logger.info(f"No new git changes detected for {repo} since {since}")
            return

        logger.info(
            f"Git changes: {len(added_files)} added, {len(modified_files)} modified, {len(deleted_files)} deleted"
        )

        # Remove deleted and modified files from index
        files_to_remove = deleted_files + modified_files
        if files_to_remove:
            # Get all chunks for these files
            # ChromaDB doesn't support combining equality with $in, so we query by repo first
            # and filter by file_path in Python, or query each file individually
            try:
                ids_to_delete = []
                # Query for each file individually to avoid ChromaDB query limitations
                for file_path in files_to_remove:
                    try:
                        results = collection.get(
                            where={"repo": repo, "file_path": file_path}
                        )
                        ids_to_delete.extend(results.get("ids", []))
                    except Exception as e:
                        logger.debug(f"Error querying chunks for {file_path}: {e}")
                        continue
                
                if ids_to_delete:
                    collection.delete(ids=ids_to_delete)
                    logger.info(
                        f"Removed {len(ids_to_delete)} chunks for deleted/modified files from {repo}"
                    )
            except Exception as e:
                logger.warning(f"Error removing old chunks: {e}")

        # Index added and modified files
        files_to_index = self._filter_code_files(added_files + modified_files)
        if files_to_index:
            self._index_files(
                repo, repo_reader, collection, files_to_index, workspace_path=repo_full_path.parent
            )
        else:
            logger.info(f"No new code files to index for {repo}")

    def _update_index_file_mtime(
        self,
        repo: str,
        repo_reader: RepoReader,
        collection: chromadb.Collection,
        repo_full_path: Path,
        since: Optional[datetime],
    ) -> None:
        """Update index using file modification time detection."""
        logger.info(f"Updating index for {repo} using file modification time (since={since})...")

        if not since:
            logger.warning(
                "No 'since' timestamp provided for file modification time detection, performing full reindex."
            )
            self.index_repository(
                repo, repo_reader, workspace_path=repo_full_path.parent, force=True
            )
            return

        # Normalize since to UTC for comparison
        since_utc = normalize_to_utc(since)

        all_files = repo_reader.list_files(repo)
        modified_files = []
        for file_path_str in all_files:
            file_path = repo_full_path / file_path_str
            if file_path.is_file():
                try:
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                    if file_mtime > since_utc:
                        modified_files.append(file_path_str)
                except (OSError, ValueError) as e:
                    logger.debug(f"Error checking file {file_path}: {e}")
                    continue

        if not modified_files:
            logger.info(f"No new or modified files detected for {repo} since {since}")
            return

        logger.info(f"Detected {len(modified_files)} modified files for {repo}")

        # Remove old chunks for modified files
        try:
            results = collection.get(where={"repo": repo, "file_path": {"$in": modified_files}})
            ids_to_delete = results.get("ids", [])
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Removed {len(ids_to_delete)} chunks for modified files from {repo}")
        except Exception as e:
            logger.warning(f"Error removing old chunks: {e}")

        # Index modified files
        files_to_index = self._filter_code_files(modified_files)
        if files_to_index:
            self._index_files(
                repo, repo_reader, collection, files_to_index, workspace_path=repo_full_path.parent
            )
        else:
            logger.info(f"No new code files to index for {repo}")

    def _index_files(
        self,
        repo: str,
        repo_reader: RepoReader,
        collection: chromadb.Collection,
        files: List[str],
        workspace_path: Optional[Path] = None,
    ) -> None:
        """Helper method to index a list of files."""
        documents = []
        metadatas = []
        ids = []

        # Track statistics for diagnostics
        file_chunk_counts = []
        total_content_size = 0
        skipped_large_files = 0

        for file_path in files:
            try:
                content = repo_reader.read_file(repo, file_path)

                # Skip very large files
                if len(content) > 100000:  # ~100KB
                    logger.debug(f"Skipping large file: {file_path}")
                    skipped_large_files += 1
                    continue

                total_content_size += len(content)

                # Enhance content with file metadata if available
                if workspace_path:
                    file_metadata_text = self._get_file_metadata_text(
                        file_path, workspace_path, repo
                    )
                    if file_metadata_text:
                        content = file_metadata_text + "\n\n" + content
                        logger.debug(f"Enhanced {file_path} with metadata for indexing")

                # Split large files into chunks
                chunks = self._chunk_file_content(file_path, content, self.max_chunk_size)
                chunk_count = len(chunks)
                file_chunk_counts.append((file_path, chunk_count, len(content)))

                for i, chunk in enumerate(chunks):
                    chunk_id = f"{repo}:{file_path}:{i}"
                    documents.append(chunk)
                    metadatas.append({"repo": repo, "file_path": file_path, "chunk_index": i})
                    ids.append(chunk_id)

            except Exception as e:
                logger.warning(f"Error reading file {file_path} for indexing: {e}")
                continue

        if not documents:
            logger.warning(f"No documents to index for {repo}")
            return

        # Log diagnostic information
        total_files = len(file_chunk_counts)
        total_chunks = len(documents)
        avg_chunks_per_file = total_chunks / total_files if total_files > 0 else 0
        avg_file_size = total_content_size / total_files if total_files > 0 else 0

        logger.info(
            f"Chunking statistics for {repo}: "
            f"{total_files:,} files → {total_chunks:,} chunks "
            f"(avg: {avg_chunks_per_file:.1f} chunks/file, "
            f"avg file size: {avg_file_size:,.0f} chars, "
            f"skipped {skipped_large_files} large files)"
        )

        # Show top 10 files by chunk count
        if file_chunk_counts:
            top_chunkers = sorted(file_chunk_counts, key=lambda x: x[1], reverse=True)[:10]
            if top_chunkers and top_chunkers[0][1] > 1:
                logger.info("Top files by chunk count:")
                for file_path, chunk_count, file_size in top_chunkers:
                    logger.info(
                        f"  {file_path}: {chunk_count} chunks "
                        f"({file_size:,} chars, {file_size/chunk_count:.0f} chars/chunk)"
                    )

        # Generate embeddings with progress logging
        total_chunks = len(documents)
        logger.info(f"Generating embeddings for {total_chunks:,} chunks...")

        # Process embeddings in batches to show progress
        embedding_batch_size = 10000  # Process embeddings in batches for progress updates
        embedding_start_time = time.time()
        all_embeddings = []

        embedding_batches = (total_chunks + embedding_batch_size - 1) // embedding_batch_size
        for emb_batch_idx in range(embedding_batches):
            emb_start_idx = emb_batch_idx * embedding_batch_size
            emb_end_idx = min(emb_start_idx + embedding_batch_size, total_chunks)
            batch_docs = documents[emb_start_idx:emb_end_idx]

            batch_embeddings = self.embedding_model.encode(batch_docs, show_progress_bar=False)
            all_embeddings.append(batch_embeddings)

            # Log progress every batch or every 10% of total
            progress_pct = (emb_end_idx / total_chunks) * 100
            elapsed_time = time.time() - embedding_start_time
            rate = emb_end_idx / elapsed_time if elapsed_time > 0 else 0
            remaining_chunks = total_chunks - emb_end_idx
            eta_seconds = remaining_chunks / rate if rate > 0 else 0

            logger.info(
                f"Embedding progress: {emb_end_idx:,}/{total_chunks:,} chunks "
                f"({progress_pct:.1f}%) | "
                f"Elapsed: {elapsed_time:.1f}s | "
                f"Rate: {rate:.0f} chunks/s | "
                f"ETA: {eta_seconds:.0f}s"
            )

        # Concatenate all embeddings
        embeddings = np.vstack(all_embeddings)
        embedding_total_time = time.time() - embedding_start_time
        logger.info(
            f"✅ Completed embedding generation in {embedding_total_time:.1f}s ({total_chunks / embedding_total_time:.0f} chunks/s avg)"
        )

        # Batch add to collection (ChromaDB has max batch size limit of ~5461)
        batch_size = 5000  # Safe batch size (under ChromaDB's limit)
        total_batches = (len(documents) + batch_size - 1) // batch_size

        logger.info(f"Adding {total_chunks:,} chunks to ChromaDB in {total_batches} batches...")
        insertion_start_time = time.time()

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(documents))

            batch_documents = documents[start_idx:end_idx]
            batch_embeddings = embeddings[start_idx:end_idx]
            batch_metadatas = metadatas[start_idx:end_idx]
            batch_ids = ids[start_idx:end_idx]

            batch_insert_start = time.time()
            collection.add(
                embeddings=batch_embeddings.tolist(),
                documents=batch_documents,
                metadatas=batch_metadatas,
                ids=batch_ids,
            )
            batch_insert_elapsed = time.time() - batch_insert_start

            progress_pct = (end_idx / total_chunks) * 100
            logger.info(
                f"Inserted batch {batch_idx + 1}/{total_batches} "
                f"({len(batch_documents):,} chunks, {progress_pct:.1f}%) "
                f"in {batch_insert_elapsed:.2f}s"
            )

        insertion_total_time = time.time() - insertion_start_time
        total_time = time.time() - embedding_start_time
        logger.info(
            f"✅ Indexed {total_chunks:,} chunks from {len(files)} files for {repo} | "
            f"Total time: {total_time:.1f}s (embedding: {embedding_total_time:.1f}s, "
            f"insertion: {insertion_total_time:.1f}s)"
        )

    def is_indexed(self, repo: str) -> bool:
        """Check if repository is indexed.

        Args:
            repo: Repository identifier

        Returns:
            True if repository is indexed
        """
        try:
            collection = self._get_collection(repo)
            return collection.count() > 0
        except Exception:
            return False

    def _filter_code_files(self, files: List[str]) -> List[str]:
        """Filter to code/text files only, excluding common build/cache directories.

        Args:
            files: List of file paths

        Returns:
            Filtered list of code/text files
        """
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".h",
            ".cs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".scala",
            ".clj",
            ".sh",
            ".bash",
            ".md",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".sql",
            ".html",
            ".css",
            ".scss",
            ".sass",
            ".less",
            ".vue",
            ".svelte",
            ".dockerfile",
            ".makefile",
            ".cmake",
            ".gradle",
            ".maven",
            ".pom",
        }

        # Directories to exclude (virtual environments, dependencies, build artifacts, etc.)
        exclude_dirs = {
            ".venv",
            "venv",
            "env",
            ".env",
            "ENV",
            "virtualenv",
            "node_modules",
            ".node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".git",
            ".hg",
            ".svn",
            "build",
            "dist",
            ".build",
            ".dist",
            ".tox",
            ".coverage",
            "htmlcov",
            ".eggs",
            ".idea",
            ".vscode",
            ".vs",
            ".DS_Store",
            "target",
            ".cargo",
            ".gradle",
            ".maven",
            ".next",
            ".nuxt",
            ".cache",
            ".parcel-cache",
            "coverage",
            ".nyc_output",
            ".sass-cache",
        }

        filtered = []
        for file_path in files:
            # Skip files in excluded directories
            path_parts = file_path.split("/")
            if any(part in exclude_dirs or part.endswith(".egg-info") for part in path_parts):
                continue

            # Check extension
            if any(file_path.lower().endswith(ext) for ext in code_extensions):
                filtered.append(file_path)
            # Include files without extension that might be config files
            elif "/" not in file_path or file_path.split("/")[-1] in [
                "Dockerfile",
                "Makefile",
                "README",
                "LICENSE",
            ]:
                filtered.append(file_path)

        return filtered

    def _chunk_file_content(self, file_path: str, content: str, max_chunk_size: int) -> List[str]:
        """Split file content into chunks for indexing.

        Args:
            file_path: File path
            content: File content
            max_chunk_size: Maximum characters per chunk

        Returns:
            List of content chunks
        """
        if len(content) <= max_chunk_size:
            return [content]

        # Try to chunk at line boundaries
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for newline

            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _get_file_metadata_text(
        self, file_path: str, workspace_path: Path, repo: str
    ) -> Optional[str]:
        """Get file metadata text from .metadata.benedict files for inclusion in embeddings.

        Args:
            file_path: Relative file path within repository
            workspace_path: Workspace path containing the repository
            repo: Repository identifier

        Returns:
            Metadata text string or None if not found
        """
        try:
            repo_path = workspace_path / repo
            file_full_path = repo_path / file_path

            if not file_full_path.exists():
                return None

            # Find .metadata.benedict file in the file's directory or parent directories
            current_dir = file_full_path.parent

            # Walk up the directory tree looking for .metadata.benedict files
            while current_dir != repo_path.parent:
                metadata_file = current_dir / ".metadata.benedict"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = yaml.safe_load(f)

                        if not metadata:
                            current_dir = current_dir.parent
                            continue

                        # Look for this file in the metadata
                        files = metadata.get("files", [])
                        file_name = file_full_path.name

                        for file_info in files:
                            if file_info.get("name") == file_name:
                                # Build metadata text
                                metadata_parts = []

                                purpose = file_info.get("purpose", "")
                                if purpose:
                                    metadata_parts.append(f"File purpose: {purpose}")

                                key_functions = file_info.get("key_functions", [])
                                if key_functions:
                                    metadata_parts.append(
                                        f"Key functions: {', '.join(key_functions)}"
                                    )

                                key_classes = file_info.get("key_classes", [])
                                if key_classes:
                                    metadata_parts.append(f"Key classes: {', '.join(key_classes)}")

                                if metadata_parts:
                                    return "\n".join(metadata_parts)

                                break

                        # If file not found in this .metadata.benedict, check parent
                        current_dir = current_dir.parent
                        continue

                    except Exception as e:
                        logger.debug(f"Error reading .metadata.benedict file {metadata_file}: {e}")
                        current_dir = current_dir.parent
                        continue

                current_dir = current_dir.parent

            return None

        except Exception as e:
            logger.debug(f"Error getting file metadata for {file_path}: {e}")
            return None

    def _generate_metadata_overlays(
        self, repo: str, repo_reader: RepoReader, workspace_path: Path
    ) -> None:
        """Generate metadata overlays for repository in workspace.

        Args:
            repo: Repository identifier
            repo_reader: RepoReader instance
            workspace_path: Workspace path
        """
        try:
            repo_path = workspace_path / repo
            if not repo_path.exists():
                logger.warning(
                    f"Repository path {repo_path} does not exist, skipping metadata generation"
                )
                return

            logger.info(f"Generating metadata overlays for {repo} in {repo_path}")

            # Common directories to skip (venv, cache, build artifacts, etc.)
            skip_patterns = {
                "venv",
                "__pycache__",
                ".mypy_cache",
                ".pytest_cache",
                "node_modules",
                ".git",
                ".hg",
                ".svn",
                "build",
                "dist",
                ".tox",
                ".coverage",
                "htmlcov",
                ".eggs",
                ".idea",
                ".vscode",
                ".DS_Store",
            }

            def should_skip_directory(directory: Path) -> bool:
                """Check if directory should be skipped."""
                # Skip hidden directories (already handled, but keep for clarity)
                if directory.name.startswith("."):
                    return True

                # Skip common build/cache directories
                if directory.name in skip_patterns:
                    return True

                # Skip .egg-info directories
                if directory.name.endswith(".egg-info"):
                    return True

                # Skip if any parent is in skip patterns
                for parent in directory.parents:
                    if parent.name in skip_patterns:
                        return True

                return False

            # Generate metadata recursively for all directories
            for directory in [repo_path] + list(repo_path.rglob("*")):
                if directory.is_dir() and not should_skip_directory(directory):
                    try:
                        self.metadata_generator.generate_and_write(directory)
                    except Exception as e:
                        logger.warning(f"Error generating metadata for {directory}: {e}")
                        continue

            logger.info(f"Generated metadata overlays for {repo}")
        except Exception as e:
            logger.error(f"Error generating metadata overlays for {repo}: {e}")
