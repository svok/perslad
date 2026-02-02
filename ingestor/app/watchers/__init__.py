"""
File Watchers Package

Модуль для индексации файлов с поддержкой:
- Full workspace scan (startup)
- Runtime file watching (inotify/fsnotify)
"""

from ingestor.app.watchers.base import BaseFileSource
from ingestor.app.watchers.scanner import FileScannerSource
from ingestor.app.watchers.notifier import FileNotifierSource

__all__ = [
    "BaseFileSource",
    "FileScannerSource",
    "FileNotifierSource",
]
