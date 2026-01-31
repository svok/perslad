"""
Storage factory for creating storage instances.

Supports memory and PostgreSQL storage backends.
"""

from typing import Optional

from ingestor.adapters.base_storage import BaseStorage
from ingestor.adapters.memory_storage import MemoryStorage
from ingestor.adapters.postgres_storage import PostgreSQLStorage
from ingestor.app.config.storage import storage as storage_config
from ingestor.app.config import runtime


class StorageFactory:
    """Factory for creating storage instances."""

    @staticmethod
    def create() -> BaseStorage:
        """
        Create a storage instance based on configuration.

        Returns:
            Storage instance (memory or postgres)
        """
        if storage_config.STORAGE_TYPE == "postgres":
            return PostgreSQLStorage()
        else:
            return MemoryStorage()

    @staticmethod
    def get_storage_type() -> str:
        """Get the configured storage type."""
        return storage_config.STORAGE_TYPE


_storage_instance: Optional[BaseStorage] = None


def get_storage() -> BaseStorage:
    """
    Get or create the storage instance.
    
    Creates a new instance each time to ensure it reads the latest configuration.
    This prevents issues where storage is initialized before environment variables are loaded.
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageFactory.create()
    return _storage_instance
