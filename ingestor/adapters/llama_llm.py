from typing import Any

from llama_index.core.llms import (
    LLM,
    CompletionResponse,
    CompletionResponseGen,
)
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.base.llms.types import LLMMetadata

from infra.llm import LLMClient


class InfraLLMAdapter(LLM):
    """
    LlamaIndex LLM adapter over infra.llm (ChatOpenAI).
    """

    def __init__(
            self,
            llm: LLMClient,
            context_window: int,
            model_name: str,
            /,
            **data: Any
    ) -> None:
        super().__init__(**data)
        self._llm = llm
        self._context_window = context_window
        self._model_name = model_name

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=self._context_window,
            num_output=1024,
            model_name=self._model_name,
        )

    def complete(self, prompt: str, **kwargs: Any):
        raise RuntimeError("Sync LLM calls are not supported")

    @llm_completion_callback()
    async def acomplete(
            self,
            prompt: str,
            **kwargs: Any,
    ) -> CompletionResponse:
        async def _request(model):
            resp = await model.ainvoke(prompt)
            return resp.content

        text = await self._llm.call_raw(_request)

        return CompletionResponse(
            text=text,
            raw=text,
        )

    async def astream_complete(
            self,
            prompt: str,
            **kwargs: Any,
    ) -> CompletionResponseGen:
        raise NotImplementedError("Streaming not implemented yet")
