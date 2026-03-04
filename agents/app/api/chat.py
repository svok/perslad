import json
import logging
import time
from typing import List, Dict, Any, Optional
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.callbacks.base import BaseCallbackHandler

from ..config import Config
from ..core.graph import create_graph
from ..managers.system import SystemManager
from ..core.utils import estimate_tokens
from infra.metrics import metrics_manager

logger = logging.getLogger("agentnet.chat")

class ChatHandler:
    def __init__(self, system: SystemManager):
        self.system = system
        self._graph = None

    def _convert_messages(self, messages: List[Dict]) -> List:
        converted = []
        for msg in messages:
            if msg["role"] == "user":
                converted.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                converted.append(AIMessage(content=msg["content"]))
        return converted

    async def _ensure_graph(self):
        if self._graph is None:
            if not self.system.llm.is_ready():
                logger.error("Cannot create graph: LLM not connected")
                return None

            model = self.system.llm.get_model()
            raw_tools = await self.system.tools.get_tools()

            if model and raw_tools:
                logger.info(f"🏗️  Creating graph with {len(raw_tools)} tools")
                logger.info(f"🔧 Tools: {[t['name'] for t in raw_tools]}")

                formatted_tools = []
                for t in raw_tools:
                    schema = t.get("inputSchema", {"type": "object", "properties": {}})
                    if not schema.get("properties"):
                        schema["additionalProperties"] = True
                    formatted_tools.append({
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": schema
                        }
                    })

                logger.info(f"Formatted Tools: {formatted_tools}")
                model_with_tools = model.bind_tools(formatted_tools, tool_choice="auto")

                self._graph = create_graph(model_with_tools, self.system.tools, self.system.ingestor)
                logger.info("✅ Graph created (Native LangChain + vLLM Qwen Parser)")
            else:
                logger.error("❌ Cannot create graph")
                return None

        return self._graph

    async def direct_response(self, messages: List[Dict]) -> Dict[str, Any]:
        system_status = self.system.get_status()
        if not system_status['llm_ready']:
            return {"error": {"message": "LLM connection lost"}}

        graph = await self._ensure_graph()
        if not graph:
            return {"error": {"message": "System initialization failed"}}

        try:
            # 1. Конвертируем сообщения
            converted_messages = self._convert_messages(messages)

            # === УПРАВЛЕНИЕ КОНТЕКСТОМ ===

            # 2. Считаем стоимость Инструментов
            # Получаем актуальные инструменты для точного расчета их размера
            raw_tools = await self.system.tools.get_tools()
            # Сериализуем в строку, чтобы оценить размер в токенах
            tools_json_str = json.dumps(raw_tools, ensure_ascii=False)
            tools_tokens = estimate_tokens(tools_json_str)

            # 3. Считаем стоимость Истории
            history_tokens = sum(
                estimate_tokens(msg.content) for msg in converted_messages
            )
            system_tokens = estimate_tokens(Config.SYSTEM_PROMPT)
            if system_tokens + tools_tokens >= Config.MAX_MODEL_TOKENS - Config.SAFETY_MARGIN:
                logger.error(
                    f"🚨 System ({system_tokens}) + tools ({tools_tokens}) exceed "
                    f"context window {Config.MAX_MODEL_TOKENS}"
                )
                return {
                    "error": {
                        "message": "System prompt and tools exceed model context window"
                    }
                }



    # 4. Итоговая статистика
            total_used = system_tokens + tools_tokens + history_tokens
            limit_threshold = Config.MAX_MODEL_TOKENS - Config.SAFETY_MARGIN

            # Логирование размеров (Требование а)
            logger.info(
                f"📊 Context Usage: "
                f"System={system_tokens}, "
                f"Tools={tools_tokens}, "
                f"History={history_tokens} | "
                f"Total={total_used}/{Config.MAX_MODEL_TOKENS} (Limit={limit_threshold})"
            )

            final_messages = converted_messages

            # 5. Контроль и обрезка (Требование б)
            if total_used > limit_threshold:
                logger.warning(f"⚠️ Context Overflow! Truncating history to fit {Config.MAX_MODEL_TOKENS} limit...")

                # Вычисляем бюджет для истории (Всего - Система - Инструменты - Запас)
                available_for_history = (
                        Config.MAX_MODEL_TOKENS
                        - system_tokens
                        - tools_tokens
                        - Config.SAFETY_MARGIN
                )

                if available_for_history < 0:
                    logger.error("🚨 Tools and System prompt exceed max context! Request will fail.")
                else:
                    # Обрезаем историю с начала, пока не влезем в бюджет
                    # Скользящее окно: сохраняем последние сообщения
                    current_size = 0
                    truncated_list = []

                    for msg in reversed(converted_messages):
                        msg_size = estimate_tokens(msg.content)

                        # одиночное сообщение больше бюджета — пропускаем
                        if msg_size > available_for_history:
                            continue

                        if current_size + msg_size > available_for_history:
                            break

                        truncated_list.insert(0, msg)
                        current_size += msg_size

                    final_messages = truncated_list
                    logger.info(f"✂️ History truncated from {len(converted_messages)} to {len(final_messages)} messages.")

            # Запуск графа с оптимизированным списком
            initial_state = {
                "messages": final_messages
            }

            result = await graph.ainvoke(initial_state)
            final_messages_res = result["messages"]

            last_ai_message = None
            for msg in reversed(final_messages_res):
                if isinstance(msg, AIMessage) and not msg.tool_calls:
                    last_ai_message = msg
                    break

            content = ""
            if last_ai_message:
                content = last_ai_message.content
            elif final_messages_res and isinstance(final_messages_res[-1], AIMessage):
                content = final_messages_res[-1].content or "Action executed."
            else:
                content = "No response generated."

            return {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }]
            }

        except Exception as e:
            logger.error(f"❌ Graph execution error: {e}", exc_info=True)
            return {"error": {"message": str(e)}}

    async def stream_response(self, messages: List[Dict]) -> StreamingResponse:
        async def fake_stream():
            result = await self.direct_response(messages)
            import json
            if "error" in result:
                yield f"data: {json.dumps(result)}\n\n"
            else:
                choice = result["choices"][0]
                yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant'}}]})}\n\n"
                yield f"data: {json.dumps({'choices': [{'delta': {'content': choice['message']['content']}}]})}\n\n"
                yield f"data: {json.dumps({'choices': [{'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(fake_stream(), media_type="text/event-stream")
