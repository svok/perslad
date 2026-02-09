"""
Storage factory for creating storage instances.

Supports memory and PostgreSQL storage backends.
"""

from typing import Optional

from infra.logger import get_logger
from ingestor.core.ports.storage import BaseStorage
from ingestor.adapters.memory.storage import MemoryStorage
from ingestor.adapters.postgres.storage import PostgreSQLStorage
from ingestor.config.storage import storage as storage_config

log = get_logger("ingestor.storage.factory")

class StorageFactory:
    """Factory for creating storage instances."""

    @staticmethod
    def create() -> BaseStorage:
        """
        Create a storage instance based on configuration.

        Returns:
            Storage instance (memory or postgres)
        """
        log.info("storage.factory.config", **storage_config.to_dict_public())
        storage_type = (
            storage_config.STORAGE_TYPE.lower()
            if isinstance(storage_config.STORAGE_TYPE, str)
            else storage_config.STORAGE_TYPE
        )

        match storage_type:
            case "pg" | "postgres" | "postgresql":
                return PostgreSQLStorage()
            case None | "mem" | "memory" | "in-memory":
                return MemoryStorage()
            case _:
                # Показываем исходное значение для отладки
                raise ValueError(
                    f"Unsupported storage type: {repr(storage_config.STORAGE_TYPE)}. "
                    f"Supported values: 'pg', 'postgres', 'postgresql', 'mem', 'memory', 'in-memory', None"
                )

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
