import asyncio
import os
from typing import Optional, Callable, Awaitable, Any

from langchain_openai import ChatOpenAI

from .health import HealthFlag
from .logger import get_logger
from .reconnect import retry_forever

log = get_logger("infra.llm")


class LLMClient:
    """
    Infra-level LLM client.
    Основан на проверенной логике LLMManager (ChatOpenAI).
    """

    def __init__(self) -> None:
        self.base_url = os.environ.get("OPENAI_API_BASE")
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model_name = os.environ.get("MODEL_NAME", "default-model")

        self.model: Optional[ChatOpenAI] = None
        self.health = HealthFlag()

    async def _connect_once(self) -> None:
        log.info("llm.connect.attempt", base_url=self.base_url)

        self.health.set_not_ready()

        self.model = ChatOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model_name,
            temperature=0.1,
            timeout=30.0,
            max_retries=2,
        )

        # ping — ровно как у тебя
        try:
            response = await asyncio.wait_for(
                self.model.ainvoke("ping"),
                timeout=10.0,
            )
            log.info(
                "llm.connect.ok",
                preview=str(response.content)[:50],
            )
            self.health.set_ready()
        except Exception:
            self.model = None
            raise

    async def ensure_ready(self) -> None:
        """
        Бесконечно пытается восстановить соединение с LLM.
        Никогда не падает наружу.
        """
        await retry_forever(self._connect_once)

    async def wait_ready(self) -> None:
        await self.health.wait_ready()

    async def call_raw(
            self,
            fn: Callable[[ChatOpenAI], Awaitable[Any]],
    ) -> Any:
        """
        Универсальная обёртка для ЛЮБОГО LLM-вызова.
        """

        await self.health.wait_ready()

        try:
            assert self.model is not None
            return await fn(self.model)
        except Exception as e:
            log.warning("llm.call.failed", error=str(e))
            self.health.set_not_ready()
            raise


_llm: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
