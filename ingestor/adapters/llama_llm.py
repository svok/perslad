"""
LLM adapter wrapping LLMManager.

Provides basic LLM interface for compatibility.
"""

from infra.managers.llm import LLMManager


class InfraLLMAdapter:
    """
    Simple wrapper around LLMManager.
    """
    
    def __init__(self, llm_manager: LLMManager, context_window: int, model_name: str):
        self._llm_manager = llm_manager
        self._context_window = context_window
        self._model_name = model_name
    
    async def initialize(self) -> None:
        """Initialize the LLM manager."""
        await self._llm_manager.initialize()
    
    async def close(self) -> None:
        """Close the LLM manager."""
        await self._llm_manager.close()
