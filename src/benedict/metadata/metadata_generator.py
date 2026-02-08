"""Metadata Generator

Generates content-agnostic .metadata.benedict files for directories.
"""
import logging
import yaml
from pathlib import Path
from typing import Dict, Optional, Any

from .content_handlers import (
    CodeHandler,
    ConversationHistoryHandler,
    DocumentHandler,
    DataHandler,
    ContentHandler,
)

logger = logging.getLogger(__name__)


class MetadataGenerator:
    """Generates .metadata.benedict files for directories."""
    
    def __init__(self):
        """Initialize metadata generator with content handlers."""
        self.handlers = {
            "code": CodeHandler(),
            "conversation_history": ConversationHistoryHandler(),
            "documentation": DocumentHandler(),
            "data": DataHandler(),
        }
        logger.debug("Initialized MetadataGenerator")
    
    def generate_metadata(
        self,
        directory: Path,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate metadata for a directory.
        
        Args:
            directory: Directory path
            content_type: Optional content type (auto-detected if not provided)
            
        Returns:
            Metadata dictionary
        """
        directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory does not exist: {directory}")
        
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")
        
        # Detect content type if not provided
        if not content_type:
            content_type = self._detect_content_type(directory)
        
        # Get appropriate handler
        handler = self._get_handler(content_type)
        
        if not handler:
            logger.debug(f"No handler found for content_type={content_type}, using generic handler")
            handler = CodeHandler()  # Default fallback
        
        # Analyze directory
        analysis = handler.analyze_directory(directory)
        
        # Build metadata
        metadata = {
            "content_type": content_type,
            "summary": self._generate_summary(directory, content_type, analysis),
            "purpose": self._generate_purpose(directory, content_type),
            **analysis
        }
        
        logger.debug(f"Generated metadata for {directory} (content_type={content_type})")
        return metadata
    
    def write_metadata(self, directory: Path, metadata: Dict[str, Any]) -> None:
        """Write .metadata.benedict file to directory.
        
        Args:
            directory: Directory path
            metadata: Metadata dictionary
        """
        directory = Path(directory)
        metadata_file = directory / ".metadata.benedict"
        
        # Check if .metadata.benedict already exists as a directory (conflict)
        if metadata_file.exists() and metadata_file.is_dir():
            logger.debug(f".metadata.benedict path exists as directory at {metadata_file}, skipping write")
            return
        
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.debug(f"Wrote .metadata.benedict to {metadata_file}")
        except Exception as e:
            logger.error(f"Error writing .metadata.benedict to {metadata_file}: {e}")
            raise
    
    def generate_and_write(self, directory: Path, content_type: Optional[str] = None) -> Dict[str, Any]:
        """Generate and write metadata in one step.
        
        Args:
            directory: Directory path
            content_type: Optional content type
            
        Returns:
            Generated metadata dictionary
        """
        metadata = self.generate_metadata(directory, content_type)
        self.write_metadata(directory, metadata)
        return metadata
    
    def _detect_content_type(self, directory: Path) -> str:
        """Detect content type of directory.
        
        Args:
            directory: Directory path
            
        Returns:
            Content type string
        """
        # Try each handler to detect content type
        for content_type, handler in self.handlers.items():
            detected = handler.detect_content_type(directory)
            if detected == content_type:
                return content_type
        
        # Check for mixed content
        detected_types = set()
        for handler in self.handlers.values():
            detected = handler.detect_content_type(directory)
            if detected != "unknown":
                detected_types.add(detected)
        
        if len(detected_types) > 1:
            return "mixed"
        elif len(detected_types) == 1:
            return detected_types.pop()
        
        # Default to code if it looks like a repository
        if (directory / ".git").exists():
            return "code"
        
        return "unknown"
    
    def _get_handler(self, content_type: str) -> Optional[ContentHandler]:
        """Get handler for content type.
        
        Args:
            content_type: Content type string
            
        Returns:
            Content handler or None
        """
        return self.handlers.get(content_type)
    
    def _generate_summary(
        self,
        directory: Path,
        content_type: str,
        analysis: Dict[str, Any]
    ) -> str:
        """Generate summary text for directory.
        
        Args:
            directory: Directory path
            content_type: Content type
            analysis: Analysis results
            
        Returns:
            Summary string
        """
        if content_type == "code":
            files = analysis.get("files", [])
            subdirs = analysis.get("subdirectories", [])
            return f"Code directory with {len(files)} files and {len(subdirs)} subdirectories"
        
        elif content_type == "conversation_history":
            total_messages = analysis.get("total_messages", 0)
            date_range = analysis.get("date_range", "")
            return f"Conversation history with {total_messages} messages" + (f" ({date_range})" if date_range else "")
        
        elif content_type == "documentation":
            files = analysis.get("files", [])
            return f"Documentation directory with {len(files)} files"
        
        elif content_type == "data":
            files = analysis.get("files", [])
            return f"Data directory with {len(files)} files"
        
        else:
            return f"Directory: {directory.name}"
    
    def _generate_purpose(self, directory: Path, content_type: str) -> str:
        """Generate purpose text for directory.
        
        Args:
            directory: Directory path
            content_type: Content type
            
        Returns:
            Purpose string
        """
        if content_type == "code":
            return f"Source code directory: {directory.name}"
        elif content_type == "conversation_history":
            return "Historical conversation data"
        elif content_type == "documentation":
            return "Documentation and guides"
        elif content_type == "data":
            return "Structured data files"
        else:
            return f"Directory containing {content_type} content"
