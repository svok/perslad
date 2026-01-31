import asyncio
from typing import List, Dict, Any

from infra.logger import get_logger

log = get_logger("agents.registry")

class ToolRegistry:
    """Реестр инструментов для работы с MCP."""

    def __init__(self, mcp):
        self.mcp = mcp
        self._tools: List[Dict[str, Any]] = []

    async def initialize(self) -> bool:
        """Инициализация реестра инструментов."""
        try:
            await asyncio.sleep(2)
            self._tools = await self.mcp.get_all_tools()

            if self._tools:
                log.info("registry.tools.loaded", count=len(self._tools))
            else:
                log.warning("registry.tools.no_tools")

            return True
        except Exception as e:
            log.error("registry.tools.error", error=str(e))
            return False

    async def get_tools(self) -> List[Dict[str, Any]]:
        """Получить все инструменты."""
        if not self._tools:
            try:
                self._tools = await self.mcp.get_all_tools()
            except:
                pass
        return self._tools.copy()

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить инструмент через MCP менеджер."""
        try:
            result = await self.mcp.call_tool(name, args)
            return {
                "success": True,
                "result": result,
                "tool": name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": name
            }

    async def list_tools(self) -> Dict[str, Any]:
        """Список всех инструментов."""
        tools = await self.get_tools()
        return {
            "tools": tools,
            "count": len(tools),
            "sources": list(self.mcp.clients.keys()) if hasattr(self.mcp, 'clients') else []
        }

    def get_count(self) -> int:
        """Количество инструментов."""
        return len(self._tools)

    async def close(self):
        """Закрытие реестра."""
        self._tools.clear()
