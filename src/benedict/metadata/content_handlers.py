"""Content-Type Handlers

Provide content-type-specific analysis and summarization.
"""

import logging
import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Protocol

logger = logging.getLogger(__name__)


class ContentHandler(Protocol):
    """Protocol for content-type handlers."""

    def detect_content_type(self, path: Path) -> str:
        """Detect content type from path.

        Args:
            path: File or directory path

        Returns:
            Content type string
        """
        ...

    def analyze_directory(self, directory: Path) -> Dict[str, Any]:
        """Analyze directory structure and contents.

        Args:
            directory: Directory path

        Returns:
            Dictionary with analysis results
        """
        ...

    def summarize_file(self, file_path: Path) -> Dict[str, Any]:
        """Summarize a single file.

        Args:
            file_path: File path

        Returns:
            Dictionary with file summary
        """
        ...

    def extract_key_concepts(self, content: str) -> List[str]:
        """Extract key concepts from content.

        Args:
            content: File content

        Returns:
            List of key concepts
        """
        ...


class CodeHandler:
    """Handler for code files."""

    def detect_content_type(self, path: Path) -> str:
        """Detect if path is code."""
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".h",
            ".cs",
            ".rb",
            ".php",
        }
        if path.is_file():
            return "code" if path.suffix in code_extensions else "unknown"
        elif path.is_dir():
            # Check if directory contains code files
            for ext in code_extensions:
                if any(path.glob(f"**/*{ext}")):
                    return "code"
        return "unknown"

    def analyze_directory(self, directory: Path) -> Dict[str, Any]:
        """Analyze code directory structure."""
        files = []
        subdirectories = []
        
        # Special files that should be included even though they start with "."
        special_files = {".metadata.benedict"}

        for item in sorted(directory.iterdir()):
            # Skip hidden files except special ones
            if item.name.startswith(".") and item.name not in special_files:
                continue
            
            # Skip .metadata.benedict if it's a directory (conflict)
            if item.name == ".metadata.benedict" and item.is_dir():
                continue

            if item.is_file():
                summary = self.summarize_file(item)
                files.append(summary)
            elif item.is_dir():
                # Quick summary of subdirectory
                code_files = list(item.glob("**/*.py"))
                subdirectories.append(
                    {
                        "name": item.name,
                        "summary": f"Contains {len(code_files)} Python files",
                        "content_type": "code",
                    }
                )

        return {"files": files, "subdirectories": subdirectories}

    def summarize_file(self, file_path: Path) -> Dict[str, Any]:
        """Summarize a code file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Error reading file {file_path}: {e}")
            return {
                "name": file_path.name,
                "content_type": "code",
                "purpose": "Unable to read file",
            }

        summary = {
            "name": file_path.name,
            "content_type": "code",
            "purpose": self._extract_file_purpose(content, file_path.suffix),
            "key_functions": [],
            "key_classes": [],
        }

        # Extract functions and classes for Python files
        if file_path.suffix == ".py":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        summary["key_functions"].append(node.name)
                    elif isinstance(node, ast.ClassDef):
                        summary["key_classes"].append(node.name)
            except SyntaxError:
                pass

        return summary

    def _extract_file_purpose(self, content: str, extension: str) -> str:
        """Extract file purpose from docstring or comments."""
        # Try to find module docstring (Python)
        if extension == ".py":
            match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            if match:
                return match.group(1).strip().split("\n")[0]

        # Try to find file-level comment
        lines = content.split("\n")[:10]
        for line in lines:
            if line.strip().startswith("#") and len(line.strip()) > 10:
                return line.strip("#").strip()

        return "Code file"

    def extract_key_concepts(self, content: str) -> List[str]:
        """Extract key concepts from code."""
        concepts = []

        # Extract imports
        import_pattern = re.compile(r"^(?:from|import)\s+(\w+)", re.MULTILINE)
        imports = import_pattern.findall(content)
        concepts.extend(imports[:5])  # Limit to 5

        # Extract class and function names
        class_pattern = re.compile(r"class\s+(\w+)")
        func_pattern = re.compile(r"def\s+(\w+)")
        concepts.extend(class_pattern.findall(content)[:5])
        concepts.extend(func_pattern.findall(content)[:5])

        return list(set(concepts))[:10]  # Return unique concepts, limit to 10


class ConversationHistoryHandler:
    """Handler for conversation history (platform-agnostic)."""

    def detect_content_type(self, path: Path) -> str:
        """Detect if path is conversation history."""
        if path.name == "conversation_history" or "conversation" in path.name.lower():
            return "conversation_history"
        if path.suffix == ".json" and "conversation" in path.name.lower():
            return "conversation_history"
        return "unknown"

    def analyze_directory(self, directory: Path) -> Dict[str, Any]:
        """Analyze conversation history directory."""
        files = []
        total_messages = 0
        date_ranges = []

        for item in sorted(directory.iterdir()):
            if item.is_file() and item.suffix == ".json":
                summary = self.summarize_file(item)
                files.append(summary)
                total_messages += summary.get("message_count", 0)
                if "date_range" in summary:
                    date_ranges.append(summary["date_range"])

        return {
            "files": files,
            "total_messages": total_messages,
            "date_range": self._merge_date_ranges(date_ranges) if date_ranges else None,
        }

    def summarize_file(self, file_path: Path) -> Dict[str, Any]:
        """Summarize a conversation history file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Error reading conversation file {file_path}: {e}")
            return {
                "name": file_path.name,
                "content_type": "conversation_history",
                "purpose": "Unable to read file",
            }

        # Extract conversation metadata
        messages = (
            data.get("messages", [])
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        message_count = len(messages)

        # Extract date range
        dates = []
        for msg in messages[:100]:  # Sample first 100 messages
            if isinstance(msg, dict):
                ts = msg.get("timestamp") or msg.get("ts")
                if ts:
                    dates.append(ts)

        date_range = None
        if dates:
            dates.sort()
            date_range = f"{dates[0]} to {dates[-1]}"

        # Extract key topics (simple keyword extraction)
        all_text = " ".join(
            [str(msg.get("text", "") or msg.get("content", "")) for msg in messages[:50]]
        )
        key_topics = self.extract_key_concepts(all_text)

        return {
            "name": file_path.name,
            "content_type": "conversation_history",
            "purpose": f"Historical conversations ({message_count} messages)",
            "message_count": message_count,
            "date_range": date_range,
            "key_topics": key_topics[:10],
        }

    def extract_key_concepts(self, content: str) -> List[str]:
        """Extract key topics from conversation content."""
        # Simple keyword extraction (can be enhanced with NLP)
        words = re.findall(r"\b[a-z]{4,}\b", content.lower())

        # Common stop words
        stop_words = {
            "that",
            "this",
            "with",
            "from",
            "have",
            "been",
            "will",
            "would",
            "could",
            "should",
        }
        filtered = [w for w in words if w not in stop_words]

        # Count frequency
        from collections import Counter

        word_counts = Counter(filtered)

        # Return top keywords
        return [word for word, _ in word_counts.most_common(10)]

    def _merge_date_ranges(self, date_ranges: List[str]) -> str:
        """Merge multiple date ranges into one."""
        if not date_ranges:
            return None

        # Simple implementation - return first to last
        all_dates = []
        for dr in date_ranges:
            if " to " in dr:
                start, end = dr.split(" to ")
                all_dates.extend([start.strip(), end.strip()])

        if all_dates:
            all_dates.sort()
            return f"{all_dates[0]} to {all_dates[-1]}"

        return date_ranges[0]


class DocumentHandler:
    """Handler for documentation files."""

    def detect_content_type(self, path: Path) -> str:
        """Detect if path is documentation."""
        doc_extensions = {".md", ".txt", ".rst", ".adoc", ".org"}
        if path.is_file():
            return "documentation" if path.suffix in doc_extensions else "unknown"
        elif path.is_dir():
            if any(path.glob("**/*.md")) or any(path.glob("**/*.txt")):
                return "documentation"
        return "unknown"

    def analyze_directory(self, directory: Path) -> Dict[str, Any]:
        """Analyze documentation directory."""
        files = []
        subdirectories = []

        for item in sorted(directory.iterdir()):
            if item.name.startswith(".") or item.name == ".metadata.benedict":
                continue

            if item.is_file() and item.suffix in {".md", ".txt", ".rst"}:
                summary = self.summarize_file(item)
                files.append(summary)
            elif item.is_dir():
                doc_files = list(item.glob("**/*.md")) + list(item.glob("**/*.txt"))
                subdirectories.append(
                    {
                        "name": item.name,
                        "summary": f"Contains {len(doc_files)} documentation files",
                        "content_type": "documentation",
                    }
                )

        return {"files": files, "subdirectories": subdirectories}

    def summarize_file(self, file_path: Path) -> Dict[str, Any]:
        """Summarize a documentation file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Error reading file {file_path}: {e}")
            return {
                "name": file_path.name,
                "content_type": "documentation",
                "purpose": "Unable to read file",
            }

        # Extract title (first heading or first line)
        title = file_path.stem.replace("_", " ").title()
        lines = content.split("\n")
        for line in lines[:10]:
            if line.startswith("#") and len(line.strip()) > 1:
                title = line.strip("#").strip()
                break

        # Extract purpose from first paragraph
        purpose = "Documentation file"
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if paragraphs:
            purpose = paragraphs[0][:200]  # First 200 chars

        return {
            "name": file_path.name,
            "content_type": "documentation",
            "purpose": purpose,
            "title": title,
        }

    def extract_key_concepts(self, content: str) -> List[str]:
        """Extract key concepts from documentation."""
        # Extract headings
        headings = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)

        # Extract emphasized words
        emphasized = re.findall(r"\*\*(.+?)\*\*", content)

        concepts = headings[:5] + emphasized[:5]
        return list(set(concepts))[:10]


class DataHandler:
    """Handler for structured data files."""

    def detect_content_type(self, path: Path) -> str:
        """Detect if path is data."""
        data_extensions = {".json", ".csv", ".yaml", ".yml", ".toml", ".xml"}
        if path.is_file():
            return "data" if path.suffix in data_extensions else "unknown"
        return "unknown"

    def analyze_directory(self, directory: Path) -> Dict[str, Any]:
        """Analyze data directory."""
        files = []

        for item in sorted(directory.iterdir()):
            if item.is_file() and item.suffix in {".json", ".csv", ".yaml", ".yml"}:
                summary = self.summarize_file(item)
                files.append(summary)

        return {"files": files}

    def summarize_file(self, file_path: Path) -> Dict[str, Any]:
        """Summarize a data file."""
        try:
            if file_path.suffix == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict):
                    schema = list(data.keys())[:10]
                    return {
                        "name": file_path.name,
                        "content_type": "data",
                        "purpose": f"JSON data with keys: {', '.join(schema)}",
                        "schema": schema,
                    }
                elif isinstance(data, list) and data:
                    if isinstance(data[0], dict):
                        schema = list(data[0].keys())[:10]
                        return {
                            "name": file_path.name,
                            "content_type": "data",
                            "purpose": f"JSON array with {len(data)} items, schema: {', '.join(schema)}",
                            "item_count": len(data),
                            "schema": schema,
                        }

            # For other formats, basic summary
            size = file_path.stat().st_size
            return {
                "name": file_path.name,
                "content_type": "data",
                "purpose": f"Data file ({size} bytes)",
                "format": file_path.suffix[1:] if file_path.suffix else "unknown",
            }
        except Exception as e:
            logger.warning(f"Error reading data file {file_path}: {e}")
            return {
                "name": file_path.name,
                "content_type": "data",
                "purpose": "Unable to read file",
            }

    def extract_key_concepts(self, content: str) -> List[str]:
        """Extract key concepts from structured data."""
        # For JSON, extract keys
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return list(data.keys())[:10]
        except Exception:
            pass

        return []
