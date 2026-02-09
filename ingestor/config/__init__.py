"""
Configuration package.

Split configuration by concern into separate modules.
"""

from .runtime import RuntimeConfig
from .storage import StorageConfig
from .llm import LLMConfig
from .llm_lock import LLMLockConfig

runtime = RuntimeConfig()
storage = StorageConfig()
llm = LLMConfig()
llm_lock = LLMLockConfig()

__all__ = ["runtime", "storage", "llm", "llm_lock"]
