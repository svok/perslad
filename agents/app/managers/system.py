# FILE: agentnet/agents/app/managers/system.py
import time
from typing import Dict, Any
from .llm import LLMManager
from .mcp import MCPManager
from .registry import ToolRegistry

class SystemManager:
    """Менеджер всей системы с правильной логикой готовности."""

    def __init__(self):
        self.llm = LLMManager()
        self.mcp = MCPManager()
        self.tools = ToolRegistry(self.mcp)
        self._start_time = time.time()

    async def initialize(self):
        """Инициализация всей системы."""
        await self.llm.initialize()
        await self.mcp.initialize()
        await self.tools.initialize()

    async def close(self):
        """Остановка всей системы."""
        await self.tools.close()
        await self.mcp.close()
        await self.llm.close()

    def is_system_ready(self) -> bool:
        """Система готова, если LLM подключен."""
        return self.llm.is_ready()

    def is_mcp_ready(self) -> bool:
        """MCP готов, если есть хотя бы одно соединение."""
        return self.mcp.is_ready()

    def get_status(self) -> Dict[str, Any]:
        """Полный статус системы."""
        return {
            "system_ready": self.is_system_ready(),
            "llm_ready": self.llm.is_ready(),
            "mcp_ready": self.mcp.is_ready(),
            "tools_count": self.tools.get_count(),
            "llm_status": self.llm.get_status(),
            "mcp_status": self.mcp.get_status()
        }

    def get_uptime(self) -> float:
        """Время работы системы."""
        return time.time() - self._start_time
