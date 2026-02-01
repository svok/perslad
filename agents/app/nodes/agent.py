import logging
from typing import Dict, Any, Optional, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import Runnable

from ..config import Config
from ..core.utils import estimate_tokens
from ..core.context_builder import ContextBuilder, calculate_available_context_budget

logger = logging.getLogger("agentnet.agent")

def estimate_messages_tokens(messages):
    total = 0
    for m in messages:
        if hasattr(m, "content") and m.content:
            total += estimate_tokens(str(m.content))
    return total


async def retrieve_rag_context(
    query: str,
    ingestor_manager,
    available_tokens: int,
) -> str:
    """
    Получает релевантный контекст из Ingestor на основе запроса.
    
    Args:
        query: Текстовый запрос пользователя
        ingestor_manager: Менеджер Ingestor
        available_tokens: Доступный бюджет токенов для RAG контекста
        
    Returns:
        Отформатированный контекст для LLM
    """
    if not ingestor_manager or not ingestor_manager.is_ready():
        logger.debug("Ingestor not available, skipping RAG context")
        return ""
    
    if available_tokens <= 0:
        logger.warning("No token budget for RAG context")
        return ""
    
    try:
        # Получаем контекст из Ingestor
        context_items = await ingestor_manager.search_by_query(query, top_k=10)
        
        if not context_items:
            logger.debug("No RAG context found")
            return ""
        
        # Используем ContextBuilder для умной сборки контекста
        builder = ContextBuilder(max_context_tokens=2048)
        context_text = builder.build_context(context_items, available_tokens)
        
        actual_tokens = estimate_tokens(context_text)
        logger.info(
            f"Retrieved RAG context: {len(context_items)} items, "
            f"{actual_tokens}/{available_tokens} tokens"
        )
        return context_text
        
    except Exception as e:
        logger.error(f"Failed to retrieve RAG context: {e}")
        return ""


async def agent_node(state: Dict[str, Any], llm: Runnable, ingestor_manager=None) -> Dict[str, Any]:
    messages = state["messages"]

    # Извлекаем последний запрос пользователя для RAG
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break
    
    # Вычисляем токены для расчета бюджета
    messages_tokens = estimate_messages_tokens(messages)
    system_tokens = estimate_tokens(Config.SYSTEM_PROMPT)
    
    # Вычисляем доступный бюджет для RAG контекста
    # Предполагаем, что tools_tokens уже учтены в модели (bind_tools)
    available_rag_budget = calculate_available_context_budget(
        messages_tokens=messages_tokens,
        system_tokens=system_tokens,
        tools_tokens=0,  # Инструменты уже в модели
    )
    
    logger.info(
        f"Token budget: messages={messages_tokens}, "
        f"system={system_tokens}, "
        f"available_for_rag={available_rag_budget}"
    )
    
    # Получаем RAG контекст с учетом доступного бюджета
    rag_context = ""
    if last_user_message and ingestor_manager and available_rag_budget > 0:
        rag_context = await retrieve_rag_context(
            last_user_message,
            ingestor_manager,
            available_rag_budget,
        )
    
    # Формируем system prompt с RAG контекстом
    system_content = Config.SYSTEM_PROMPT
    if rag_context:
        system_content = f"{Config.SYSTEM_PROMPT}\n\n{rag_context}"
    
    rag_tokens = estimate_tokens(rag_context) if rag_context else 0
    total_tokens = messages_tokens + system_tokens + rag_tokens
    
    logger.info(
        f"Final context: messages={messages_tokens}, "
        f"system={system_tokens}, "
        f"rag={rag_tokens}, "
        f"total={total_tokens}/{Config.MAX_MODEL_TOKENS}"
    )

    # Проверка переполнения (на всякий случай)
    if total_tokens > Config.MAX_MODEL_TOKENS - Config.SAFETY_MARGIN:
        logger.error(
            f"Context overflow after RAG: {total_tokens} tokens, "
            f"this should not happen!"
        )
        # Fallback: убираем RAG контекст
        system_content = Config.SYSTEM_PROMPT
        rag_tokens = 0

    # Добавляем system prompt только если его нет
    has_system = any(isinstance(msg, SystemMessage) for msg in messages)
    if not has_system:
        messages = [
                       SystemMessage(content=system_content)
                   ] + messages
    else:
        # Обновляем существующий system prompt с RAG контекстом
        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                messages[i] = SystemMessage(content=system_content)
                break

    response = await llm.ainvoke(messages)
    logger.info(f"Response from LLM: {response}")

    return {"messages": [response]}