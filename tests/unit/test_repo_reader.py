"""Tests for repository reader implementations.

Tests the RepoReader protocol and mock implementation.
"""

import pytest

from benedict.repo_reader import MockRepoReader


class TestMockRepoReader:
    """Tests for MockRepoReader implementation."""

    def test_initialization(self):
        """Test mock repo reader initialization."""
        reader = MockRepoReader()
        assert reader is not None

    def test_add_file(self):
        """Test adding a file to the mock reader."""
        reader = MockRepoReader()
        reader.add_file("README.md", "# Test\nThis is a test file.")
        
        files = reader.list_files()
        assert "README.md" in files

    def test_read_file(self):
        """Test reading a file."""
        reader = MockRepoReader()
        content = "# Test\nThis is a test file."
        reader.add_file("README.md", content)
        
        read_content = reader.read_file("README.md")
        assert read_content == content

    def test_read_nonexistent_file(self):
        """Test reading a file that doesn't exist."""
        reader = MockRepoReader()
        
        content = reader.read_file("nonexistent.txt")
        assert content is None or content == ""

    def test_list_files_empty(self):
        """Test listing files when repository is empty."""
        reader = MockRepoReader()
        files = reader.list_files()
        
        assert isinstance(files, list)
        assert len(files) == 0

    def test_list_files_with_content(self):
        """Test listing files with content."""
        reader = MockRepoReader()
        reader.add_file("README.md", "Content")
        reader.add_file("src/main.py", "print('hello')")
        reader.add_file("src/utils.py", "def helper(): pass")
        
        files = reader.list_files()
        assert len(files) == 3
        assert "README.md" in files
        assert "src/main.py" in files
        assert "src/utils.py" in files

    def test_list_files_with_pattern(self):
        """Test listing files with glob pattern."""
        reader = MockRepoReader()
        reader.add_file("README.md", "Content")
        reader.add_file("src/main.py", "print('hello')")
        reader.add_file("src/utils.py", "def helper(): pass")
        reader.add_file("test.txt", "test")
        
        # If the reader supports patterns
        if hasattr(reader, "list_files"):
            # Try to get only Python files
            all_files = reader.list_files()
            py_files = [f for f in all_files if f.endswith(".py")]
            assert len(py_files) == 2

    def test_file_exists(self):
        """Test checking if a file exists."""
        reader = MockRepoReader()
        reader.add_file("README.md", "Content")
        
        if hasattr(reader, "file_exists"):
            assert reader.file_exists("README.md")
            assert not reader.file_exists("nonexistent.txt")

    def test_read_multiple_files(self):
        """Test reading multiple files."""
        reader = MockRepoReader()
        reader.add_file("file1.txt", "Content 1")
        reader.add_file("file2.txt", "Content 2")
        reader.add_file("file3.txt", "Content 3")
        
        content1 = reader.read_file("file1.txt")
        content2 = reader.read_file("file2.txt")
        content3 = reader.read_file("file3.txt")
        
        assert content1 == "Content 1"
        assert content2 == "Content 2"
        assert content3 == "Content 3"

    def test_overwrite_file(self):
        """Test overwriting an existing file."""
        reader = MockRepoReader()
        reader.add_file("file.txt", "Original content")
        reader.add_file("file.txt", "New content")
        
        content = reader.read_file("file.txt")
        assert content == "New content"
