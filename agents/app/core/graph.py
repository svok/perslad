from langgraph.graph import StateGraph, END
from langchain_core.runnables import Runnable, RunnableLambda
from typing import Dict, Any, Optional

from .state import AgentState
from ..nodes.agent import agent_node
from ..nodes.tools import tool_node

def create_graph(llm: Runnable, tool_registry, ingestor_manager=None):
    """Создает граф с корректной обработкой инструментов."""
    workflow = StateGraph(AgentState)

    # 1. Узел Агента
    async def agent_wrapper(state: dict):
        # Передаем LLM и ingestor manager для RAG контекста
        return await agent_node(state, llm, ingestor_manager)

    workflow.add_node("agent", RunnableLambda(agent_wrapper))

    # 2. Узел Инструментов
    async def tools_wrapper(state: dict):
        return await tool_node(state, tool_registry)

    workflow.add_node("tools", RunnableLambda(tools_wrapper))

    # Точка входа
    workflow.set_entry_point("agent")

    # Условные переходы: проверяем наличие tool_calls в последнем сообщении
    def should_continue(state: AgentState) -> str:
        messages = state["messages"]
        last_message = messages[-1]

        # Если последнее сообщение содержит вызовы инструментов - идем в tools
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        # Иначе завершаем
        return END

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )

    # После инструментов всегда возвращаемся к агенту
    workflow.add_edge("tools", "agent")

    return workflow.compile()
