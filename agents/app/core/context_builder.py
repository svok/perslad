"""
Context Builder - умная сборка контекста с учетом лимитов токенов.

Стратегии:
1. Full context - полный контекст (если влезает)
2. Summarized context - замена больших блоков на резюме
3. Minimal context - только ключевые элементы
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..core.utils import estimate_tokens
from ..config import Config

logger = logging.getLogger("agentnet.context_builder")


@dataclass
class ContextItem:
    """Элемент контекста с метаданными."""
    content: str
    summary: Optional[str]
    priority: int  # 0-10, где 10 - наивысший приоритет
    tokens: int
    item_type: str  # "module", "file", "chunk"
    metadata: Dict[str, Any]


class ContextBuilder:
    """
    Умная сборка контекста с учетом лимитов токенов.
    
    Принципы:
    1. Приоритизация - важные элементы включаются первыми
    2. Суммаризация - большие блоки заменяются на резюме
    3. Адаптивность - подстраивается под доступный бюджет
    """
    
    def __init__(self, max_context_tokens: int = 2048):
        """
        Args:
            max_context_tokens: Максимальный размер RAG контекста в токенах
        """
        self.max_context_tokens = max_context_tokens
    
    def build_context(
        self,
        raw_items: List[Dict[str, Any]],
        available_tokens: int,
    ) -> str:
        """
        Собирает контекст с учетом доступного бюджета токенов.
        
        Args:
            raw_items: Сырые элементы контекста от Ingestor
            available_tokens: Доступный бюджет токенов
            
        Returns:
            Отформатированный контекст
        """
        if not raw_items:
            return ""
        
        # Ограничиваем бюджет максимальным размером RAG контекста
        budget = min(available_tokens, self.max_context_tokens)
        
        logger.info(f"Building context: {len(raw_items)} items, budget={budget} tokens")
        
        # Конвертируем в ContextItem с приоритетами
        context_items = self._prepare_items(raw_items)
        
        # Сортируем по приоритету
        context_items.sort(key=lambda x: x.priority, reverse=True)
        
        # Собираем контекст с учетом бюджета
        if budget >= sum(item.tokens for item in context_items):
            # Влезает полностью
            strategy = "full"
            result = self._build_full_context(context_items)
        elif budget >= sum(estimate_tokens(item.summary or "") for item in context_items if item.summary):
            # Влезают резюме
            strategy = "summarized"
            result = self._build_summarized_context(context_items, budget)
        else:
            # Только ключевые элементы
            strategy = "minimal"
            result = self._build_minimal_context(context_items, budget)
        
        actual_tokens = estimate_tokens(result)
        logger.info(
            f"Context built: strategy={strategy}, "
            f"items={len(context_items)}, "
            f"tokens={actual_tokens}/{budget}"
        )
        
        return result
    
    def _prepare_items(self, raw_items: List[Dict[str, Any]]) -> List[ContextItem]:
        """
        Конвертирует сырые элементы в ContextItem с приоритетами.
        
        Args:
            raw_items: Сырые элементы от Ingestor
            
        Returns:
            Список ContextItem
        """
        items = []
        
        for raw in raw_items:
            # Определяем тип элемента
            if raw.get("type") == "module":
                item_type = "module"
                content = self._format_module(raw)
                summary = raw.get("summary", "")
                priority = 7  # Модули - высокий приоритет
            elif raw.get("chunk_id"):
                item_type = "chunk"
                content = self._format_chunk(raw)
                summary = raw.get("summary", "")
                # Приоритет на основе similarity
                similarity = raw.get("similarity", 0.0)
                priority = int(similarity * 10)
            else:
                item_type = "unknown"
                content = str(raw)
                summary = None
                priority = 1
            
            tokens = estimate_tokens(content)
            
            items.append(ContextItem(
                content=content,
                summary=summary,
                priority=priority,
                tokens=tokens,
                item_type=item_type,
                metadata=raw,
            ))
        
        return items
    
    def _format_module(self, module: Dict[str, Any]) -> str:
        """Форматирует модуль."""
        lines = [
            f"## Module: {module.get('module_path', 'Unknown')}",
            f"Files: {module.get('files_count', 0)}",
        ]
        if module.get("summary"):
            lines.append(f"Summary: {module.get('summary')}")
        return "\n".join(lines)
    
    def _format_chunk(self, chunk: Dict[str, Any]) -> str:
        """Форматирует чанк кода."""
        lines = [
            f"### {chunk.get('file_path', 'Unknown file')}",
        ]
        if chunk.get("summary"):
            lines.append(f"Summary: {chunk.get('summary')}")
        if chunk.get("purpose"):
            lines.append(f"Purpose: {chunk.get('purpose')}")
        if chunk.get("content"):
            lines.append(f"```\n{chunk.get('content')}\n```")
        
        similarity = chunk.get("similarity")
        if similarity is not None:
            lines.append(f"Relevance: {similarity:.2f}")
        
        return "\n".join(lines)
    
    def _build_full_context(self, items: List[ContextItem]) -> str:
        """Собирает полный контекст."""
        lines = ["# Project Knowledge Context\n"]
        
        for item in items:
            lines.append(item.content)
            lines.append("")  # Пустая строка между элементами
        
        return "\n".join(lines)
    
    def _build_summarized_context(
        self,
        items: List[ContextItem],
        budget: int,
    ) -> str:
        """
        Собирает контекст с заменой больших блоков на резюме.
        
        Args:
            items: Элементы контекста
            budget: Бюджет токенов
            
        Returns:
            Отформатированный контекст
        """
        lines = ["# Project Knowledge Context (Summarized)\n"]
        used_tokens = estimate_tokens(lines[0])
        
        for item in items:
            # Пробуем добавить полный контент
            if used_tokens + item.tokens <= budget:
                lines.append(item.content)
                used_tokens += item.tokens
            elif item.summary:
                # Заменяем на резюме
                summary_text = self._format_summary(item)
                summary_tokens = estimate_tokens(summary_text)
                
                if used_tokens + summary_tokens <= budget:
                    lines.append(summary_text)
                    used_tokens += summary_tokens
                else:
                    # Даже резюме не влезает, пропускаем
                    logger.debug(f"Skipping item {item.item_type}: no space even for summary")
            else:
                # Нет резюме, пропускаем
                logger.debug(f"Skipping item {item.item_type}: no summary available")
            
            lines.append("")  # Пустая строка
        
        return "\n".join(lines)
    
    def _build_minimal_context(
        self,
        items: List[ContextItem],
        budget: int,
    ) -> str:
        """
        Собирает минимальный контекст - только ключевые элементы.
        
        Args:
            items: Элементы контекста
            budget: Бюджет токенов
            
        Returns:
            Отформатированный контекст
        """
        lines = ["# Project Knowledge Context (Minimal)\n"]
        used_tokens = estimate_tokens(lines[0])
        
        # Берем только элементы с высоким приоритетом (>= 7)
        high_priority_items = [item for item in items if item.priority >= 7]
        
        for item in high_priority_items:
            if item.summary:
                summary_text = self._format_summary(item)
                summary_tokens = estimate_tokens(summary_text)
                
                if used_tokens + summary_tokens <= budget:
                    lines.append(summary_text)
                    used_tokens += summary_tokens
                else:
                    break
            
            lines.append("")
        
        if len(lines) <= 2:  # Только заголовок
            return "# Project Knowledge Context\n\n(Context budget too small for meaningful content)"
        
        return "\n".join(lines)
    
    def _format_summary(self, item: ContextItem) -> str:
        """Форматирует резюме элемента."""
        if item.item_type == "module":
            return f"## {item.metadata.get('module_path', 'Unknown')}: {item.summary}"
        elif item.item_type == "chunk":
            file_path = item.metadata.get('file_path', 'Unknown')
            return f"### {file_path}\n{item.summary}"
        else:
            return item.summary or ""


def calculate_available_context_budget(
    messages_tokens: int,
    system_tokens: int,
    tools_tokens: int,
) -> int:
    """
    Вычисляет доступный бюджет для RAG контекста.
    
    Args:
        messages_tokens: Токены истории сообщений
        system_tokens: Токены system prompt (без RAG)
        tools_tokens: Токены инструментов
        
    Returns:
        Доступный бюджет для RAG контекста
    """
    total_used = messages_tokens + system_tokens + tools_tokens
    available = Config.MAX_MODEL_TOKENS - Config.SAFETY_MARGIN - total_used
    
    # Ограничиваем максимум для RAG контекста
    max_rag_budget = 2048  # Не более 2K токенов на RAG
    
    return max(0, min(available, max_rag_budget))
