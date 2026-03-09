import logging
from typing import Dict, Any
import asyncio
from langchain_core.messages import ToolMessage

from ..core.utils import estimate_tokens
from ..config import Config

logger = logging.getLogger("agentnet.tools")

async def tool_node(state: Dict[str, Any], tool_registry) -> Dict[str, Any]:
    """Узел для выполнения инструментов."""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        logger.info("🛠️  Tool Node: No tool calls found in last message")
        return {"messages": []}

    logger.info(f"🛠️  Tool Node: Executing {len(last_message.tool_calls)} tools")

    tool_outputs = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        logger.info(f"   ↪️ Executing: {tool_name} with args: {tool_args}")

        try:
            result = await asyncio.wait_for(
                tool_registry.execute_tool(tool_name, tool_args),
                timeout=60.0
            )

            raw_content = (
                str(result.get("result", result))
                if isinstance(result, dict)
                else str(result)
            )

            tokens = estimate_tokens(raw_content)

            if tokens > Config.MAX_TOOL_TOKENS:
                logger.warning(
                    f"⚠️ Tool output truncated: {tokens} → {Config.MAX_TOOL_TOKENS} tokens"
                )

                # грубая, но безопасная обрезка по символам
                approx_chars = Config.MAX_TOOL_TOKENS * 2
                content = raw_content[:approx_chars] + (
                    "\n\n⚠️ Output truncated due to context limits."
                )
            else:
                content = raw_content

            logger.info(
                f"   ✅ Result size: ~{estimate_tokens(content)} tokens"
            )

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

    return {"messages": tool_outputs}
