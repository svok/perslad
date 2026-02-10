import asyncio
import logging
from typing import Optional, Set, List, Dict, Any
import httpx

from infra.managers.base import BaseManager
from ..config import Config

logger = logging.getLogger("agentnet.ingestor")


class IngestorManager(BaseManager):
    """Менеджер для взаимодействия с Ingestor (RAG)."""

    def __init__(self):
        super().__init__("ingestor")
        self.base_url = Config.INGESTOR_URL
        self.client: Optional[httpx.AsyncClient] = None
        self._connections["ingestor-server"] = False

    async def _connect_all(self) -> Set[str]:
        """Подключение к Ingestor."""
        try:
            self.logger.info(f"Connecting to Ingestor at {self.base_url}")
            
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
            
            # Проверяем доступность через health endpoint
            try:
                response = await asyncio.wait_for(
                    self.client.get("/health"),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.logger.info(f"Ingestor connected: {data}")
                    return {"ingestor-server"}
                else:
                    self.logger.warning(f"Ingestor health check failed: {response.status_code}")
                    return set()
                    
            except asyncio.TimeoutError:
                self.logger.warning("Ingestor timeout")
                return set()
                
        except Exception as e:
            self.logger.error(f"Ingestor connection failed: {type(e).__name__}: {str(e)[:100]}")
            self._errors["ingestor-server"] = str(e)
            return set()

    async def _disconnect_all(self):
        """Отключение от Ingestor."""
        if self.client:
            try:
                await self.client.aclose()
            except:
                pass
        self.client = None
        self._connections["ingestor-server"] = False

    async def search_by_query(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Поиск релевантного контекста по текстовому запросу.
        
        Args:
            query: Текстовый запрос пользователя
            top_k: Количество результатов
            
        Returns:
            Список релевантных чанков кода
        """
        if not self.is_ready() or not self.client:
            self.logger.warning("Ingestor not ready, skipping search")
            return []
        
        try:
            # Сначала получаем embedding для запроса через LLM
            # Используем простой подход - отправляем запрос напрямую
            # В production можно использовать отдельный embedding endpoint
            
            # Для MVP используем overview если embedding недоступен
            response = await self.client.get("/knowledge/overview")
            
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"Retrieved project overview: {len(data.get('modules', []))} modules")
                return self._format_overview_as_context(data)
            else:
                self.logger.warning(f"Failed to get overview: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []

    async def get_file_context(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Получить контекст конкретного файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Контекст файла (summary + chunks)
        """
        if not self.is_ready() or not self.client:
            self.logger.warning("Ingestor not ready")
            return None
        
        try:
            response = await self.client.get(f"/knowledge/file/{file_path}")
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Failed to get file context: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Get file context failed: {e}")
            return None

    async def get_project_overview(self) -> Optional[Dict[str, Any]]:
        """
        Получить обзор проекта.
        
        Returns:
            Обзор проекта (статистика + module summaries)
        """
        if not self.is_ready() or not self.client:
            self.logger.warning("Ingestor not ready")
            return None
        
        try:
            response = await self.client.get("/knowledge/overview")
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"Failed to get overview: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Get overview failed: {e}")
            return None

    async def set_llm_lock(self, locked: bool, ttl_seconds: float = 300) -> bool:
        """
        Установить/снять блокировку LLM.
        
        Args:
            locked: True для блокировки, False для разблокировки
            ttl_seconds: TTL блокировки в секундах
            
        Returns:
            True если успешно
        """
        if not self.is_ready() or not self.client:
            self.logger.warning("Ingestor not ready, cannot set lock")
            return False
        
        try:
            response = await self.client.post(
                "/system/llm_lock",
                json={"locked": locked, "ttl_seconds": ttl_seconds}
            )
            
            if response.status_code == 200:
                self.logger.info(f"LLM lock {'set' if locked else 'released'}")
                return True
            else:
                self.logger.warning(f"Failed to set lock: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Set lock failed: {e}")
            return False

    def _format_overview_as_context(self, overview: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Форматирует overview в список контекстных элементов.
        
        Args:
            overview: Данные overview от Ingestor
            
        Returns:
            Список контекстных элементов
        """
        context = []
        
        # Добавляем информацию о модулях
        for module in overview.get("modules", []):
            context.append({
                "type": "module",
                "module_path": module.get("module_path", ""),
                "summary": module.get("summary", ""),
                "files_count": module.get("files_count", 0),
            })
        
        return context

    def format_context_for_llm(self, context_items: List[Dict[str, Any]]) -> str:
        """
        Форматирует контекст для добавления в промпт LLM.
        
        Args:
            context_items: Список элементов контекста
            
        Returns:
            Отформатированная строка контекста
        """
        if not context_items:
            return ""
        
        lines = ["# Project Knowledge Context\n"]
        
        for item in context_items:
            if item.get("type") == "module":
                lines.append(f"## Module: {item.get('module_path', 'Unknown')}")
                lines.append(f"Files: {item.get('files_count', 0)}")
                if item.get("summary"):
                    lines.append(f"Summary: {item.get('summary')}")
                lines.append("")
            elif item.get("chunk_id"):
                # Это результат поиска по embedding
                lines.append(f"### {item.get('file_path', 'Unknown file')}")
                if item.get("summary"):
                    lines.append(f"Summary: {item.get('summary')}")
                if item.get("content"):
                    lines.append(f"```\n{item.get('content')}\n```")
                lines.append("")
        
        return "\n".join(lines)
