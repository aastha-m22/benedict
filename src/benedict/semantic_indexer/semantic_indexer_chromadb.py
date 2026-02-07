"""ChromaDB Semantic Indexer Implementation

Uses sentence-transformers for embeddings and ChromaDB for vector storage.
"""
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

from benedict.protocols.semantic_indexer import SemanticIndexer
from benedict.protocols.repo_reader import RepoReader

logger = logging.getLogger(__name__)


class ChromaDBSemanticIndexer:
    """ChromaDB-based semantic indexer for code repositories."""
    
    def __init__(self, persist_directory: str = "./.chroma_db"):
        """Initialize ChromaDB semantic indexer.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(exist_ok=True)
        
        # Initialize embedding model
        # Using a lightweight, fast model suitable for code
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Collection name is based on repo name, created on-demand
        self.collections: Dict[str, chromadb.Collection] = {}
        logger.info(f"Initialized ChromaDBSemanticIndexer with persist_dir={persist_directory}")
    
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
                    name=collection_name,
                    metadata={"repo": repo}
                )
                logger.debug(f"Created new collection for repo {repo}")
        
        return self.collections[collection_name]
    
    def index_repository(self, repo: str, repo_reader: RepoReader) -> None:
        """Index a repository for semantic search.
        
        Args:
            repo: Repository identifier
            repo_reader: RepoReader instance to read files
        """
        collection = self._get_collection(repo)
        
        # Check if already indexed (has documents)
        if collection.count() > 0:
            logger.info(f"Repository {repo} already indexed ({collection.count()} chunks)")
            return
        
        logger.info(f"Indexing repository {repo}...")
        
        # Get all files
        try:
            all_files = repo_reader.list_files(repo)
        except Exception as e:
            logger.error(f"Error listing files for {repo}: {e}")
            return
        
        # Filter to code/text files (exclude binaries, large files)
        code_files = self._filter_code_files(all_files)
        
        # Process files in chunks
        documents = []
        metadatas = []
        ids = []
        
        for file_path in code_files:
            try:
                content = repo_reader.read_file(repo, file_path)
                
                # Skip very large files
                if len(content) > 100000:  # ~100KB
                    logger.debug(f"Skipping large file: {file_path}")
                    continue
                
                # Split large files into chunks
                chunks = self._chunk_file_content(file_path, content)
                
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{repo}:{file_path}:{i}"
                    documents.append(chunk)
                    metadatas.append({
                        "repo": repo,
                        "file_path": file_path,
                        "chunk_index": i
                    })
                    ids.append(chunk_id)
                    
            except Exception as e:
                logger.warning(f"Error reading file {file_path} for indexing: {e}")
                continue
        
        if not documents:
            logger.warning(f"No documents to index for {repo}")
            return
        
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
        
        logger.info(f"Indexed {len(documents)} chunks from {len(code_files)} files for {repo}")
    
    def search(
        self, 
        repo: str, 
        query: str, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search repository using semantic similarity.
        
        Args:
            repo: Repository identifier
            query: Search query/question
            top_k: Number of results to return
            
        Returns:
            List of dicts with keys: 'file_path', 'content', 'score'
        """
        collection = self._get_collection(repo)
        
        if collection.count() == 0:
            logger.warning(f"Repository {repo} not indexed yet")
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
        if results['documents'] and len(results['documents'][0]) > 0:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else 0.0
                
                # Convert distance to similarity score (lower distance = higher similarity)
                score = 1.0 / (1.0 + distance)
                
                formatted_results.append({
                    'file_path': metadata.get('file_path', 'unknown'),
                    'content': doc,
                    'score': score
                })
        
        logger.debug(f"Semantic search for '{query}' in {repo} returned {len(formatted_results)} results")
        return formatted_results
    
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
        """Filter to code/text files only.
        
        Args:
            files: List of file paths
            
        Returns:
            Filtered list of code/text files
        """
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.h',
            '.cs', '.rb', '.php', '.swift', '.kt', '.scala', '.clj', '.sh', '.bash',
            '.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
            '.sql', '.html', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',
            '.dockerfile', '.makefile', '.cmake', '.gradle', '.maven', '.pom'
        }
        
        filtered = []
        for file_path in files:
            # Check extension
            if any(file_path.lower().endswith(ext) for ext in code_extensions):
                filtered.append(file_path)
            # Include files without extension that might be config files
            elif '/' not in file_path or file_path.split('/')[-1] in ['Dockerfile', 'Makefile', 'README', 'LICENSE']:
                filtered.append(file_path)
        
        return filtered
    
    def _chunk_file_content(self, file_path: str, content: str, max_chunk_size: int = 1000) -> List[str]:
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
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
