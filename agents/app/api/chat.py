import asyncio
import json
import logging
import time
from typing import List, Dict, Any, Optional
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from ..config import Config
from ..core.graph import create_graph
from ..managers.system import SystemManager
from ..core.utils import estimate_tokens

logger = logging.getLogger("agentnet.chat")

class ChatHandler:
    def __init__(self, system: SystemManager):
        self.system = system
        self._graph = None
        self._graph_thinking = None
        self._raw_tools = None

    def _convert_messages(self, messages: List[Dict]) -> List:
        converted = []
        for msg in messages:
            if msg["role"] == "user":
                converted.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                converted.append(AIMessage(content=msg["content"]))
        return converted

    async def _ensure_tools(self):
        """Cache tools to avoid repeated fetching"""
        if self._raw_tools is None:
            self._raw_tools = await self.system.tools.get_tools()
            logger.info(f"✅ Cached {len(self._raw_tools)} tools")
        return self._raw_tools

    async def direct_response(self, messages: List[Dict], enable_thinking: bool = False, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> Dict[str, Any]:
        start_time = time.time()
        system_status = self.system.get_status()
        if not system_status['llm_ready']:
            return {"error": {"message": "LLM connection lost"}}

        try:
            # Step 2: Convert messages
            convert_start = time.time()
            converted_messages = self._convert_messages(messages)
            convert_time = time.time() - convert_start
            logger.info(f"📝 Message conversion took {convert_time:.2f}s")

            # === CONTEXT MANAGEMENT ===
            # Step 3: Calculate tool tokens
            tools_start = time.time()
            raw_tools = await self._ensure_tools()
            tools_json_str = json.dumps(raw_tools, ensure_ascii=False)
            tools_tokens = estimate_tokens(tools_json_str)
            tools_time = time.time() - tools_start
            logger.info(f"🧰 Tool processing took {tools_time:.2f}s, {tools_tokens} tokens")

            # Step 4: Calculate history and system tokens
            count_start = time.time()
            history_tokens = sum(
                estimate_tokens(msg.content) for msg in converted_messages
            )
            system_tokens = estimate_tokens(Config.SYSTEM_PROMPT)
            count_time = time.time() - count_start
            logger.info(f"🔢 Token counting took {count_time:.2f}s")

            # Step 5: Context overflow check
            limit_start = time.time()
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

            if total_used > limit_threshold:
                truncate_start = time.time()
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
                
                truncate_time = time.time() - truncate_start
                logger.info(f"✂️ Context truncation took {truncate_time:.2f}s")

            limit_time = time.time() - limit_start
            logger.info(f"🎛️ Context management took {limit_time:.2f}s")

            # Step 6: Configure model parameters with temperature and max_tokens
            generation_config = {}
            if temperature is not None:
                generation_config["temperature"] = temperature
                logger.info(f"🌡️ Setting temperature={temperature} from request")
            if max_tokens is not None:
                generation_config["max_tokens"] = max_tokens
                logger.info(f"⚙️ Setting max_tokens={max_tokens} from request")

            # Step 7: Execute graph
            stream_start = time.time()
            accumulated_content = ""
            
            # Create model with generation parameters BEFORE executing graph
            model = self.system.llm.get_model(
                enable_thinking=enable_thinking,
                **generation_config
            )
            if model is None:
                return {"error": {"message": "Failed to initialize model with specified parameters"}}

            final_messages.insert(0, SystemMessage(content="/no_think"))
            logger.info(f"🤖 LLM request messages: {final_messages}")

            try:
                async for event in model.astream_events(
                    # {"messages": final_messages},
                    final_messages,
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

            stream_time = time.time() - stream_start
            logger.info(f"🤖 LLM generation took {stream_time:.2f}s, generated {len(accumulated_content)} chars")

            # Step 8: Final response
            total_time = time.time() - start_time
            logger.info(f"✅ Total request processing took {total_time:.2f}s")

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
            total_time = time.time() - start_time
            logger.error(f"❌ Total request failed after {total_time:.2f}s: {e}", exc_info=True)
            return {"error": {"message": str(e)}}

    async def stream_response(self, messages: List[Dict], enable_thinking: bool = False, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> StreamingResponse:
        start_time = time.time()
        logger.info(f"📥 [REQUEST] stream_response called with {len(messages)} messages, thinking={enable_thinking}, max_tokens={max_tokens}, temperature={temperature}")
        
        async def stream_generator():
            request_id = f"chatcmpl-{int(time.time())}"
            logger.info(f"📥 [REQUEST] Generated request_id: {request_id}")
            
            try:
                # Step 1: Check service status
                status_start = time.time()
                system_status = self.system.get_status()
                if not system_status['llm_ready']:
                    logger.warning(f"❌ LLM not ready for stream request {request_id}")
                    yield f"data: {json.dumps({'id': request_id, 'error': {'message': 'LLM connection lost'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                status_time = time.time() - status_start
                logger.info(f"🔍 Status check took {status_time:.2f}s")

                # Step 3: Convert messages
                convert_start = time.time()
                converted_messages = self._convert_messages(messages)
                convert_time = time.time() - convert_start
                logger.info(f"📝 Message conversion took {convert_time:.2f}s")

                # Step 4: Context management
                context_start = time.time()
                raw_tools = await self._ensure_tools()
                tools_json_str = json.dumps(raw_tools, ensure_ascii=False)
                tools_tokens = estimate_tokens(tools_json_str)
                system_tokens = estimate_tokens(Config.SYSTEM_PROMPT)
                history_tokens = sum(estimate_tokens(msg.content) for msg in converted_messages)
                total_used = system_tokens + tools_tokens + history_tokens
                limit_threshold = Config.MAX_MODEL_TOKENS - Config.SAFETY_MARGIN

                logger.info(
                    f"📊 Stream Context: System={system_tokens}, Tools={tools_tokens}, "
                    f"History={history_tokens} | Total={total_used}/{Config.MAX_MODEL_TOKENS}"
                )

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
                        logger.info(f"✂️ History truncated from {len(converted_messages)} to {len(final_messages)} messages.")
                
                context_time = time.time() - context_start
                logger.info(f"🎛️ Context management took {context_time:.2f}s")

                # Step 5: Configure model parameters with temperature and max_tokens
                generation_config = {}
                if temperature is not None:
                    generation_config["temperature"] = temperature
                    logger.info(f"🌡️ Setting temperature={temperature} from request")
                if max_tokens is not None:
                    generation_config["max_tokens"] = max_tokens
                    logger.info(f"⚙️ Setting max_tokens={max_tokens} from request")
                
                # Pure OpenAI-compatible SSE format
                def sse_content(content: str):
                    data = json.dumps({
                        'id': request_id, 
                        'choices': [{'delta': {'content': content}, 'index': 0}]
                    })
                    return f"data: {data}\n\n"

                def sse_done():
                    data = json.dumps({
                        'id': request_id, 
                        'choices': [{'delta': {}, 'finish_reason': 'stop', 'index': 0}]
                    })
                    return f"data: {data}\n\n"

                # Step 6: Stream generation
                stream_start = time.time()
                
                # Create model with generation parameters BEFORE executing graph
                model = self.system.llm.get_model(
                    enable_thinking=enable_thinking,
                    **generation_config
                )
                if model is None:
                    yield f"data: {json.dumps({'id': request_id, 'error': {'message': 'Failed to initialize model with specified parameters'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                final_messages.insert(0, SystemMessage(content="/no_think"))

                try:
                    logger.info("📥 [STREAM] Starting astream_events")
                    
                    async for event in model.astream_events(
                        # {"messages": final_messages},
                        final_messages,
                        version="v1"
                    ):
                        event_type = event.get("event")
                        
                        # Only stream LLM token generation, ignore other events
                        if event_type == "on_chat_model_stream":
                            chunk_data = event.get("data", {}).get("chunk")
                            if chunk_data and hasattr(chunk_data, "content"):
                                content = chunk_data.content
                                if content:
                                    yield sse_content(content)
                    
                    # Signal completion
                    yield sse_done()
                    stream_time = time.time() - stream_start
                    logger.info(f"🤖 Stream generation completed in {stream_time:.2f}s")
                    yield "data: [DONE]\n\n"
                except Exception as stream_err:
                    stream_time = time.time() - stream_start
                    logger.error(f"❌ Stream iteration error after {stream_time:.2f}s: {stream_err}", exc_info=True)
                    yield sse_done()
                    yield "data: [DONE]\n\n"
                    return
                
                total_time = time.time() - start_time
                logger.info(f"✅ Stream request {request_id} completed in {total_time:.2f}s")
                
            except Exception as e:
                total_time = time.time() - start_time
                logger.error(f"❌ Stream request {request_id} failed after {total_time:.2f}s: {e}", exc_info=True)
                # Create done response directly since sse_done may not be in scope
                done_data = json.dumps({
                    'id': request_id, 
                    'choices': [{'delta': {}, 'finish_reason': 'stop', 'index': 0}]
                })
                yield f"data: {done_data}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
