import asyncio
import json
import logging
import time
from typing import List, Dict, Any
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from ..config import Config
from ..core.graph import create_graph
from ..managers.system import SystemManager
from ..core.utils import estimate_tokens

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

    async def _ensure_graph(self, enable_thinking: bool = False):
        # Don't cache - recreate for each request to support different thinking modes
        if not self.system.llm.is_ready():
            logger.error("Cannot create graph: LLM not connected")
            return None

        model = self.system.llm.get_model(enable_thinking=enable_thinking)
        raw_tools = await self.system.tools.get_tools()

        if model and raw_tools:
            logger.info(f"🏗️  Creating graph with {len(raw_tools)} tools (thinking={enable_thinking})")
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

            graph = create_graph(model_with_tools, self.system.tools, self.system.ingestor)
            logger.info("✅ Graph created (Native LangChain + vLLM Qwen Parser)")
            return graph
        else:
            logger.error("❌ Cannot create graph")
            return None

    async def direct_response(self, messages: List[Dict], enable_thinking: bool = False) -> Dict[str, Any]:
        system_status = self.system.get_status()
        if not system_status['llm_ready']:
            return {"error": {"message": "LLM connection lost"}}

        graph = await self._ensure_graph(enable_thinking=enable_thinking)
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

            # Use astream_events to avoid timeout during LLM thinking
            accumulated_content = ""
            
            try:
                async for event in graph.astream_events(
                    {"messages": final_messages},
                    version="v1"
                ):
                    event_type = event.get("event")
                    
                    # Handle LLM token generation
                    if event_type == "on_chat_model_stream":
                        chunk_data = event.get("data", {}).get("chunk")
                        if chunk_data and hasattr(chunk_data, "content"):
                            content = chunk_data.content
                            if content:
                                accumulated_content += content
                
                final_content = accumulated_content if accumulated_content else "Action executed."
                
            except Exception as e:
                logger.error(f"❌ Graph execution error: {e}", exc_info=True)
                # If we have partial content, return it
                if accumulated_content:
                    final_content = accumulated_content
                else:
                    return {"error": {"message": str(e)}}

            return {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": final_content
                    },
                    "finish_reason": "stop"
                }]
            }

        except Exception as e:
            logger.error(f"❌ Graph execution error: {e}", exc_info=True)
            return {"error": {"message": str(e)}}

    async def stream_response(self, messages: List[Dict], enable_thinking: bool = False) -> StreamingResponse:
        logger.info(f"📥 [REQUEST] stream_response called with {len(messages)} messages, thinking={enable_thinking}")
        
        async def stream_generator():
            request_id = f"chatcmpl-{int(time.time())}"
            logger.info(f"📥 [REQUEST] Generated request_id: {request_id}")
            
            try:
                system_status = self.system.get_status()
                if not system_status['llm_ready']:
                    yield f"data: {json.dumps({'id': request_id, 'error': {'message': 'LLM connection lost'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                graph = await self._ensure_graph(enable_thinking=enable_thinking)
                if not graph:
                    yield f"data: {json.dumps({'id': request_id, 'error': {'message': 'System initialization failed'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                converted_messages = self._convert_messages(messages)
                
                # Context management - same as direct_response
                raw_tools = await self.system.tools.get_tools()
                tools_json_str = json.dumps(raw_tools, ensure_ascii=False)
                tools_tokens = estimate_tokens(tools_json_str)
                system_tokens = estimate_tokens(Config.SYSTEM_PROMPT)
                history_tokens = sum(estimate_tokens(msg.content) for msg in converted_messages)
                total_used = system_tokens + tools_tokens + history_tokens
                limit_threshold = Config.MAX_MODEL_TOKENS - Config.SAFETY_MARGIN

                if system_tokens + tools_tokens >= limit_threshold:
                    yield f"data: {json.dumps({'id': request_id, 'error': {'message': 'System prompt and tools exceed model context window'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                logger.info(
                    f"📊 Stream Context: System={system_tokens}, Tools={tools_tokens}, "
                    f"History={history_tokens} | Total={total_used}/{Config.MAX_MODEL_TOKENS}"
                )

                final_messages = converted_messages

                if total_used > limit_threshold:
                    logger.warning(f"⚠️ Context Overflow! Truncating history...")
                    available_for_history = (
                        Config.MAX_MODEL_TOKENS
                        - system_tokens
                        - tools_tokens
                        - Config.SAFETY_MARGIN
                    )
                    
                    if available_for_history > 0:
                        current_size = 0
                        truncated_list = []
                        
                        for msg in reversed(converted_messages):
                            msg_size = estimate_tokens(msg.content)
                            if msg_size > available_for_history:
                                continue
                            if current_size + msg_size > available_for_history:
                                break
                            truncated_list.insert(0, msg)
                            current_size += msg_size
                        
                        final_messages = truncated_list

                # SSE format: OpenAI compatible + OpenWebUI status events
                # Note: content_status removed - it pollutes chat history
                def sse_status(description: str):
                    # OpenAI compatible status
                    openai_status = f"data: {json.dumps({'type': 'status', 'content': description})}\n\n"
                    # OpenWebUI status event (for status display)
                    openwebui_status = f"event: message\ndata: {json.dumps({'type': 'status', 'data': {'description': description, 'done': False, 'hidden': False}})}\n\n"
                    return openai_status + openwebui_status
                
                def sse_status_done(description: str):
                    openai_status = f"data: {json.dumps({'type': 'status', 'content': description})}\n\n"
                    openwebui_status = f"event: message\ndata: {json.dumps({'type': 'status', 'data': {'description': description, 'done': True, 'hidden': False}})}\n\n"
                    return openai_status + openwebui_status
                
                def sse_content(content: str):
                    return f"data: {json.dumps({'id': request_id, 'choices': [{'delta': {'content': content}, 'index': 0}]})}\n\n"

                def sse_done():
                    return f"data: {json.dumps({'id': request_id, 'choices': [{'delta': {}, 'finish_reason': 'stop', 'index': 0}]})}\n\n"

                # Send initial role message
                logger.info("📤 [SSE] Sending initial delta")
                yield sse_content("")
                await asyncio.sleep(0)

                # Stream through graph using astream_events for real-time tokens
                tool_calls_buffer = []
                
                # Send initial status
                logger.info("📤 [SSE] Sending: Processing request...")
                yield sse_status("Processing request...")
                await asyncio.sleep(0)
                
                try:
                    logger.info("📥 [STREAM] Starting astream_events")
                    async for event in graph.astream_events(
                        {"messages": final_messages},
                        version="v1"
                    ):
                        try:
                            event_type = event.get("event")
                            
                            # Handle LLM token generation
                            if event_type == "on_chat_model_stream":
                                chunk_data = event.get("data", {}).get("chunk")
                                if chunk_data and hasattr(chunk_data, "content"):
                                    content = chunk_data.content
                                    if content:
                                        yield sse_content(content)
                                        await asyncio.sleep(0)
                            
                            # Handle LLM start
                            elif event_type == "on_chat_model_start":
                                logger.info("📤 [SSE] LLM started")
                                yield sse_status("Generating response...")
                                await asyncio.sleep(0)
                            
                            # Handle LLM end
                            elif event_type == "on_chat_model_end":
                                logger.info("📤 [SSE] LLM ended")
                                yield sse_status_done("Response generated")
                                await asyncio.sleep(0)
                            
                            # Handle tool node execution
                            elif event_type == "on_tool_start":
                                tool_name = event.get("name", "tool")
                                # Get tool input arguments for better status
                                tool_input = event.get("data", {}).get("input", {})
                                input_str = ""
                                if tool_input:
                                    # Show first few args truncated
                                    input_preview = str(tool_input)[:100]
                                    input_str = f" ({input_preview}...)" if len(str(tool_input)) > 100 else f" ({tool_input})"
                                logger.info(f"📤 [SSE] Tool started: {tool_name}{input_str}")
                                yield sse_status(f"Running tool: {tool_name}{input_str}...")
                                await asyncio.sleep(0)
                            
                            # Handle tool node end
                            elif event_type == "on_tool_end":
                                tool_name = event.get("name", "tool")
                                logger.info(f"📤 [SSE] Tool ended: {tool_name}")
                                yield sse_status_done(f"Tool {tool_name} completed")
                                await asyncio.sleep(0)
                            
                            # Handle RAG/context operations
                            elif event_type == "on_retriever_start":
                                logger.info("📤 [SSE] Retriever started")
                                yield sse_status("Searching knowledge base...")
                                await asyncio.sleep(0)
                            
                            elif event_type == "on_retriever_end":
                                logger.info("📤 [SSE] Retriever ended")
                                yield sse_status_done("Knowledge base search complete")
                                await asyncio.sleep(0)
                            
                            # Handle chain start/end
                            elif event_type == "on_chain_start":
                                chain_name = event.get("name", "chain")
                                if "agent" in str(chain_name).lower():
                                    logger.info("📤 [SSE] Chain started")
                                    yield sse_status("Starting agent...")
                                    await asyncio.sleep(0)
                            
                            elif event_type == "on_chain_end":
                                logger.info("📤 [SSE] Chain ended")
                                yield sse_status_done("Agent completed")
                                await asyncio.sleep(0)
                            
                            else:
                                logger.info(f"📥 [STREAM] Event: {event_type}")
                        except Exception as inner_e:
                            logger.error(f"❌ Error processing event: {inner_e}")
                            yield sse_status_done(f"Error: {str(inner_e)[:50]}")
                except Exception as stream_err:
                    logger.error(f"❌ Stream iteration error: {stream_err}", exc_info=True)
                    yield sse_status_done(f"Error: {str(stream_err)[:50]}")

                # astream_events already returns all messages, no need for extra invoke
                logger.info("📤 [SSE] Sending: Done")
                yield sse_status_done("Done")
                yield sse_done()
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                logger.error(f"❌ Stream error: {e}", exc_info=True)
                yield f"event: message\ndata: {json.dumps({'type': 'status', 'data': {'description': f'Error: {str(e)}', 'done': True, 'hidden': False}})}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
