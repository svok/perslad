import logging
import time
from typing import List, Dict, Any, Optional

from .base import BaseChatHandler

logger = logging.getLogger("agentnet.chat.direct")


class DirectChatHandler(BaseChatHandler):
    """Синхронный обработчик чата - формирует JSON ответ."""

    async def handle(
        self,
        messages: List[Dict[str, Any]],
        enable_thinking: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        request_tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Обработка синхронного запроса."""
        start_time = time.time()

        if not self._check_llm_ready():
            return {"error": {"message": "LLM connection lost"}}

        try:
            prepared_messages, tools, token_stats = await self._prepare_messages(
                messages, request_tools
            )

            generation_config = self._build_generation_config(
                temperature=temperature,
                max_tokens=max_tokens
            )

            model = self._create_model(
                enable_thinking=enable_thinking,
                tools=tools,
                **generation_config
            )

            if model is None:
                return {"error": {"message": "Failed to initialize model"}}

            logger.info(f"🤖 LLM request: {len(prepared_messages)} messages")

            request_id = f"chatcmpl-{int(time.time())}"
            final_content, _ = await self._run_llm_loop(
                model,
                prepared_messages,
                request_id
            )

            total_time = time.time() - start_time
            logger.info(f"✅ Direct request completed in {total_time:.2f}s")

            return {
                "id": request_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": final_content
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": token_stats["total"],
                    "completion_tokens": 0,
                    "total_tokens": token_stats["total"]
                }
            }

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"❌ Direct request failed after {total_time:.2f}s: {e}", exc_info=True)
            return {"error": {"message": str(e)}}
