import asyncio
import logging
from typing import Optional, Set

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from .base import BaseManager

logger = logging.getLogger("infra.llm")


class LLMManager(BaseManager):
    """Менеджер LLM с нативной поддержкой Qwen."""

    def __init__(self, api_base: str, api_key: SecretStr, model_name: str = "default-model", timeout: int = 30):
        super().__init__("llm")
        self.model: Optional[ChatOpenAI] = None
        self._connections["llm-server"] = False

        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    async def _connect_all(self) -> Set[str]:
        try:
            self.logger.info(f"Connecting to {self.api_base}")

            # Используем ChatOpenAI с нативной поддержкой tool calling
            self.model = ChatOpenAI(
                base_url=self.api_base,
                api_key=self.api_key,
                model=self.model_name,
                temperature=0.1,
                timeout=self.timeout,
                max_retries=2,
            )

            # Тестовый запрос (без инструментов)
            try:
                response = await asyncio.wait_for(
                    self.model
                    .bind(
                        extra_body={"chat_template_kwargs": {"enable_thinking": False}}
                    )
                    .ainvoke("ping"),
                    timeout=10.0
                )
                self.logger.info(f"Server responded: {response.content[:50]}...")
                return {"llm-server"}
            except asyncio.TimeoutError:
                self.logger.warning("Server timeout (model loading)")
                return set()

        except Exception as e:
            self.logger.error(f"Connection failed: {type(e).__name__}: {str(e)[:100]}")
            self._errors["llm-server"] = str(e)
            return set()

    async def _disconnect_all(self):
        if self.model and hasattr(self.model, 'http_client'):
            try:
                await self.model.http_client.close()
            except:
                pass
        self.model = None
        self._connections["llm-server"] = False

    def get_model(self, enable_thinking: bool = False, tools: Optional[list] = None, **generation_kwargs):
        """Returns model with optional tools and custom generation params."""
        if not self.is_ready():
            return None

        native_params = {}

        if generation_kwargs:
            for key, value in generation_kwargs.items():
                if key in ["temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty", "stop", "tool_choice"]:
                    native_params[key] = value

        bind_kwargs = {**native_params}

        if tools:
            self.logger.info(f"🔗 Binding {len(tools)} tools to model")
            return self.model.bind_tools(tools, **bind_kwargs)

        return self.model.bind(**bind_kwargs)
