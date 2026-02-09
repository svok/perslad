"""
Adapters package.

Provides implementations of base interfaces.
"""

from ingestor.core.ports.storage import BaseStorage
from ingestor.adapters.memory.storage import MemoryStorage
from ingestor.adapters.postgres.storage import PostgreSQLStorage
from ingestor.adapters.storage_factory import StorageFactory, get_storage

__all__ = [
    "BaseStorage",
    "MemoryStorage",
    "PostgreSQLStorage",
    "StorageFactory",
    "get_storage",
]
