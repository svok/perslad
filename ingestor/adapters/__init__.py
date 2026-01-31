"""
Adapters package.

Provides implementations of base interfaces.
"""

from .base_storage import BaseStorage
from .memory_storage import MemoryStorage
from .postgres_storage import PostgreSQLStorage
from .storage_factory import StorageFactory, get_storage

__all__ = [
    "BaseStorage",
    "MemoryStorage",
    "PostgreSQLStorage",
    "StorageFactory",
    "get_storage",
]
