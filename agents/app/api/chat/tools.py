import logging
import asyncio
from typing import Dict, Any, List, Optional

from langchain_core.messages import ToolMessage

from ...core.utils import estimate_tokens
from ...config import Config

logger = logging.getLogger("agentnet.chat.tools")


class ToolExecutor:
    """Исполнитель tool_calls с кэшированием результатов."""

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    async def execute(
        self,
        tool_calls: List[Dict[str, Any]],
        request_tools: Optional[List[Dict[str, Any]]] = None
    ) -> List[ToolMessage]:
        """Выполнение списка tool_calls."""
        if not tool_calls:
            return []

        if request_tools:
            self.tool_registry.register_request_tools(request_tools)

        logger.info(f"🛠️ ToolExecutor: executing {len(tool_calls)} tool calls")

        logger.info(f"🛠️ ToolExecutor: executing {len(tool_calls)} tool calls")

        tool_outputs = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            logger.info(f"   ↪️ Executing: {tool_name} with args: {tool_args}")

            try:
                result = await asyncio.wait_for(
                    self.tool_registry.execute_tool(tool_name, tool_args),
                    timeout=60.0
                )

                content = self._process_result(result)
                content = self._truncate_if_needed(content)

                tool_message = ToolMessage(
                    content=content,
                    tool_call_id=tool_id,
                    name=tool_name
                )
                tool_outputs.append(tool_message)

            except asyncio.TimeoutError:
                logger.error(f"   ⏰ Timeout: {tool_name}")
                tool_outputs.append(ToolMessage(
                    content="Error: Tool execution timed out",
                    tool_call_id=tool_id,
                    name=tool_name
                ))
            except Exception as e:
                logger.error(f"   ❌ Error: {tool_name} - {e}")
                tool_outputs.append(ToolMessage(
                    content=f"Error: {str(e)}",
                    tool_call_id=tool_id,
                    name=tool_name
                ))

        if request_tools:
            self.tool_registry.clear_request_tools()

        return tool_outputs

    def _process_result(self, result: Any) -> str:
        """Обработка результата выполнения инструмента."""
        if isinstance(result, dict):
            return str(result.get("result", result))
        return str(result)

    def _truncate_if_needed(self, content: str) -> str:
        """Обрезка результата если превышает лимит токенов."""
        tokens = estimate_tokens(content)

        if tokens > Config.MAX_TOOL_TOKENS:
            logger.warning(
                f"⚠️ Tool output truncated: {tokens} → {Config.MAX_TOOL_TOKENS} tokens"
            )
            approx_chars = Config.MAX_TOOL_TOKENS * 2
            content = content[:approx_chars] + "\n\n⚠️ Output truncated due to context limits."

        logger.info(f"   ✅ Result size: ~{estimate_tokens(content)} tokens")
        return content
