import logging
from typing import Dict, Any

from langchain_core.messages import SystemMessage
from langchain_core.runnables import Runnable

from ..config import Config
from ..core.utils import estimate_tokens

logger = logging.getLogger("agentnet.agent")

def estimate_messages_tokens(messages):
    total = 0
    for m in messages:
        if hasattr(m, "content") and m.content:
            total += estimate_tokens(str(m.content))
    return total


async def agent_node(state: Dict[str, Any], llm: Runnable) -> Dict[str, Any]:
    messages = state["messages"]

    tokens = estimate_messages_tokens(messages)

    if tokens > Config.MAX_MODEL_TOKENS - Config.SAFETY_MARGIN:
        raise RuntimeError(
            f"Context overflow before LLM call: {tokens} tokens"
        )

    # Добавляем system prompt только если его нет
    has_system = any(isinstance(msg, SystemMessage) for msg in messages)
    if not has_system:
        messages = [
                       SystemMessage(content=Config.SYSTEM_PROMPT)
                   ] + messages

    response = await llm.ainvoke(messages)
    logger.info(f"Response from LLM: {response}")

    return {"messages": [response]}