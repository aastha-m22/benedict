"""Repository Change Detector module.

Provides implementations for detecting changes in repositories.
"""

from .git_change_detector import GitChangeDetector
from .file_watcher_detector import FileWatcherDetector

__all__ = ["GitChangeDetector", "FileWatcherDetector"]
