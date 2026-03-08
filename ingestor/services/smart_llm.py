import asyncio
from typing import Any

from llama_index.core.llms import LLM
from llama_index.core.base.llms.types import CompletionResponse
from llama_index.llms.openai_like import OpenAILike


class SmartLLMService():
    """Wrapper around LLM that provides fast and reasoning modes."""

    def __init__(self, llm: LLM, max_workers: int = 2, **kwargs: Any):
        super().__init__(**kwargs)
        self.llm = llm
        self._semaphore = asyncio.Semaphore(max_workers)

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 500,
        enable_thinking: bool = False,
    ) -> str:
        """Complete prompt with optional thinking mode."""
        if enable_thinking:
            prompt = f"/think\n{prompt}"
        else:
            prompt = f"/no_think\n{prompt}"


        async with self._semaphore:
            response: CompletionResponse = await self.llm.acomplete(
                prompt,
                max_tokens=max_tokens,
            )
            return response.text if response else ""
