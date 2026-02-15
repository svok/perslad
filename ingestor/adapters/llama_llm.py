from typing import Any

from llama_index.core.llms import (
    LLM,
    CompletionResponse,
    CompletionResponseGen,
)
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.base.llms.types import LLMMetadata

from infra.managers.llm import LLMManager


class InfraLLMAdapter(LLM):
    """
    LlamaIndex LLM adapter over infra.managers.llm (ChatOpenAI).
    """

    def __init__(
            self,
            llm: LLMManager,
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
        model = self._llm.get_model()
        if not model:
            raise RuntimeError("LLM not ready")

        resp = await model.ainvoke(prompt)
        text = resp.content

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
