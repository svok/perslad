import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable

from ...config import Config
from ...managers.system import SystemManager
from ...core.utils import estimate_tokens
from .tools import ToolExecutor

logger = logging.getLogger("agentnet.chat.base")


class BaseChatHandler:
    """Базовый класс с общей логикой для синхронного и потокового обработчиков."""

    def __init__(self, system: SystemManager):
        self.system = system
        self._raw_tools: Optional[List[Dict[str, Any]]] = None
        self._tool_executor = ToolExecutor(system.tools)
        self._current_request_tools: Optional[List[Dict[str, Any]]] = None

    def _convert_messages(self, messages: List[Dict]) -> List:
        """Конвертация Dict сообщений в LangChain messages."""
        converted = []
        for msg in messages:
            if msg["role"] == "user":
                converted.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                converted.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                converted.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "tool":
                converted.append(ToolMessage(
                    content=msg["content"],
                    tool_call_id=msg.get("tool_call_id", ""),
                    name=msg.get("name", "")
                ))
        return converted

    async def _ensure_tools(self) -> List[Dict[str, Any]]:
        """Кэширование инструментов из MCP."""
        if self._raw_tools is None:
            self._raw_tools = await self.system.tools.get_tools()
            logger.info(f"✅ Cached {len(self._raw_tools)} tools")
        return self._raw_tools or []

    def _check_llm_ready(self) -> bool:
        """Проверка готовности LLM."""
        return self.system.llm.is_ready()

    def _calculate_tokens(
        self,
        converted_messages: List,
        raw_tools: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Подсчёт токенов для system, tools, history."""
        tools_json_str = json.dumps(raw_tools, ensure_ascii=False)
        tools_tokens = estimate_tokens(tools_json_str)

        history_tokens = sum(
            estimate_tokens(msg.content) for msg in converted_messages
            if hasattr(msg, "content")
        )

        system_tokens = estimate_tokens(Config.SYSTEM_PROMPT)

        return {
            "system": system_tokens,
            "tools": tools_tokens,
            "history": history_tokens,
            "total": system_tokens + tools_tokens + history_tokens
        }

    def _truncate_history(
        self,
        converted_messages: List,
        tools_tokens: int,
        available_budget: int
    ) -> List:
        """Обрезка истории сообщений до доступного бюджета."""
        current_size = 0
        truncated_list = []

        for msg in reversed(converted_messages):
            msg_size = estimate_tokens(msg.content) if hasattr(msg, "content") else 0

            if msg_size > available_budget:
                continue

            if current_size + msg_size > available_budget:
                break

            truncated_list.insert(0, msg)
            current_size += msg_size

        logger.info(f"✂️ History truncated: {len(converted_messages)} → {len(truncated_list)} messages")
        return truncated_list

    def _build_generation_config(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Формирование конфига для модели."""
        config = {}
        if temperature is not None:
            config["temperature"] = temperature
        if max_tokens is not None:
            config["max_tokens"] = max_tokens
        return config

    def _create_model(
        self,
        enable_thinking: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        **generation_kwargs
    ) -> Optional[Runnable]:
        """Создание модели с привязкой инструментов."""
        model = self.system.llm.get_model(
            enable_thinking=enable_thinking,
            **generation_kwargs
        )

        if model is None:
            logger.error("❌ Failed to initialize model")
            return None

        if tools:
            logger.info(f"🔗 Binding {len(tools)} tools to model")
            model = model.bind_tools(tools)

        return model

    async def _run_llm_loop(
        self,
        model: Runnable,
        messages: List,
        request_id: str
    ) -> tuple[str, bool]:
        """
        Главный цикл: LLM → tool_calls → выполнение → LLM → ... → финал.
        
        Returns:
            (content, has_tool_calls) - контент и флаг были ли tool_calls
        """
        max_iterations = 10

        for iteration in range(max_iterations):
            logger.info(f"🔄 LLM iteration {iteration + 1}/{max_iterations}")

            try:
                response = await model.ainvoke(messages)
            except Exception as e:
                logger.error(f"❌ LLM invoke error: {e}")
                break

            if not response:
                logger.warning("⚠️ Empty response from LLM")
                break

            content = response.content if hasattr(response, "content") else str(response)
            tool_calls = self._extract_tool_calls_from_message(response)

            if not tool_calls:
                logger.info("✅ No tool calls - final response")
                return content, False

            logger.info(f"🛠️ Found {len(tool_calls)} tool calls in response")

            tool_messages = await self._execute_tool_calls(tool_calls)
            messages = list(messages) + tool_messages

            model = self._recreate_model_with_same_tools(model)

        logger.warning("⚠️ Max iterations reached")
        return content if 'content' in locals() else "Action executed.", False

    async def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[ToolMessage]:
        """Execute tool calls with request_tools from the current request."""
        return await self._tool_executor.execute(
            tool_calls,
            request_tools=self._current_request_tools
        )

    def _extract_tool_calls_from_message(self, response) -> List[Dict[str, Any]]:
        """Извлечение tool_calls из AIMessage."""
        if hasattr(response, "tool_calls") and response.tool_calls:
            return response.tool_calls
        return []

    def _recreate_model_with_same_tools(self, model: Runnable) -> Runnable:
        """Пересоздание модели с теми же tools после tool call."""
        tools = getattr(model, "tools", None)
        if tools:
            return self.system.llm.get_model().bind_tools(tools)
        return self.system.llm.get_model()

    async def _prepare_messages(
        self,
        messages: List[Dict],
        request_tools: Optional[List[Dict[str, Any]]] = None
    ) -> tuple[List, Optional[List[Dict[str, Any]]], Dict[str, int]]:
        """
        Подготовка сообщений: конвертация, подсчёт токенов, truncate при needed.
        
        Returns:
            (prepared_messages, tools, token_stats)
        """
        converted_messages = self._convert_messages(messages)

        request_tools = request_tools or []
        self._current_request_tools = request_tools
        mcp_tools = await self._ensure_tools()
        all_tools = mcp_tools + request_tools

        token_stats = self._calculate_tokens(converted_messages, all_tools)

        limit_threshold = Config.MAX_MODEL_TOKENS - Config.SAFETY_MARGIN

        logger.info(
            f"📊 Context: System={token_stats['system']}, "
            f"Tools={token_stats['tools']}, "
            f"History={token_stats['history']} | "
            f"Total={token_stats['total']}/{Config.MAX_MODEL_TOKENS}"
        )

        if token_stats["total"] > limit_threshold:
            available_for_history = (
                Config.MAX_MODEL_TOKENS
                - token_stats["system"]
                - token_stats["tools"]
                - Config.SAFETY_MARGIN
            )

            if available_for_history > 0:
                converted_messages = self._truncate_history(
                    converted_messages,
                    token_stats["tools"],
                    available_for_history
                )

        if not any(isinstance(m, SystemMessage) for m in converted_messages):
            converted_messages = [
                SystemMessage(content=Config.SYSTEM_PROMPT)
            ] + converted_messages

        return converted_messages, all_tools if all_tools else None, token_stats
