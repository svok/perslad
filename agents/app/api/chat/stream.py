import json
import logging
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi.responses import StreamingResponse

from .base import BaseChatHandler

logger = logging.getLogger("agentnet.chat.stream")


class StreamChatHandler(BaseChatHandler):
    """Потоковый обработчик чата - возвращает SSE поток."""

    async def handle(
        self,
        messages: List[Dict[str, Any]],
        enable_thinking: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        request_tools: Optional[List[Dict[str, Any]]] = None
    ) -> StreamingResponse:
        """Обработка потокового запроса."""
        request_id = f"chatcmpl-{int(time.time())}"
        start_time = time.time()

        logger.info(
            f"📥 [STREAM] Request {request_id}: "
            f"{len(messages)} messages, thinking={enable_thinking}"
        )

        async def stream_generator() -> AsyncGenerator[str, None]:
            try:
                if not self._check_llm_ready():
                    yield self._sse_error(request_id, "LLM connection lost")
                    return

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
                    yield self._sse_error(request_id, "Failed to initialize model")
                    return

                max_iterations = 10

                for iteration in range(max_iterations):
                    logger.info(f"🔄 Stream iteration {iteration + 1}/{max_iterations}")

                    try:
                        response = await model.ainvoke(prepared_messages)
                    except Exception as e:
                        logger.error(f"❌ LLM invoke error: {e}")
                        break

                    if not response:
                        break

                    tool_calls = self._extract_tool_calls_from_message(response)

                    if tool_calls:
                        logger.info(f"🛠️ Stream: found {len(tool_calls)} tool calls")
                        tool_messages = await self._execute_tool_calls(tool_calls)

                        prepared_messages = list(prepared_messages) + tool_messages
                        model = self._recreate_model_with_same_tools(model)
                        continue

                    content = response.content if hasattr(response, "content") else str(response)

                    if content:
                        yield self._sse_content(request_id, content)

                    yield self._sse_done(request_id)
                    yield "data: [DONE]\n\n"

                    total_time = time.time() - start_time
                    logger.info(f"✅ Stream {request_id} completed in {total_time:.2f}s")
                    return

                yield self._sse_done(request_id)
                yield "data: [DONE]\n\n"

            except Exception as e:
                total_time = time.time() - start_time
                logger.error(f"❌ Stream {request_id} failed after {total_time:.2f}s: {e}")
                yield self._sse_error(request_id, str(e))

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    def _sse_content(self, request_id: str, content: str) -> str:
        """Формирование SSE chunk с контентом."""
        data = json.dumps({
            "id": request_id,
            "choices": [{"delta": {"content": content}, "index": 0}]
        })
        return f"data: {data}\n\n"

    def _sse_done(self, request_id: str) -> str:
        """Формирование SSE finish."""
        data = json.dumps({
            "id": request_id,
            "choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]
        })
        return f"data: {data}\n\n"

    def _sse_error(self, request_id: str, message: str) -> str:
        """Формирование SSE ошибки."""
        data = json.dumps({
            "id": request_id,
            "error": {"message": message}
        })
        return f"data: {data}\n\n"
