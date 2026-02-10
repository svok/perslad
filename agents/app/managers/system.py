# FILE: agentnet/agents/app/managers/system.py
import time
from typing import Dict, Any
from infra.managers.llm import LLMManager
from infra.managers.mcp import MCPManager
from infra.managers.registry import ToolRegistry
from ..config import Config
from .ingestor import IngestorManager

class SystemManager:
    """Менеджер всей системы с правильной логикой готовности."""

    def __init__(self):
        self.llm = LLMManager(
            api_base=Config.LLM_API_BASE,
            api_key=Config.LLM_API_KEY,
            model_name=Config.LLM_MODEL
        )

        # Подготавливаем конфиг для MCP
        mcp_configs = []
        for name, data in Config.get_mcp_servers().items():
            mcp_configs.append({
                "name": name,
                "url": data["url"],
                "enabled": data.get("enabled", True)
            })

        self.mcp = MCPManager(mcp_configs)
        self.tools = ToolRegistry(self.mcp)
        self.ingestor = IngestorManager()
        self._start_time = time.time()

    async def initialize(self):
        """Инициализация всей системы."""
        await self.llm.initialize()
        await self.mcp.initialize()
        await self.tools.initialize()
        await self.ingestor.initialize()

    async def close(self):
        """Остановка всей системы."""
        await self.tools.close()
        await self.mcp.close()
        await self.llm.close()
        await self.ingestor.close()

    def is_system_ready(self) -> bool:
        """Система готова, если LLM подключен."""
        return self.llm.is_ready()

    def is_mcp_ready(self) -> bool:
        """MCP готов, если есть хотя бы одно соединение."""
        return self.mcp.is_ready()
    
    def is_ingestor_ready(self) -> bool:
        """Ingestor готов."""
        return self.ingestor.is_ready()

    def get_status(self) -> Dict[str, Any]:
        """Полный статус системы."""
        return {
            "system_ready": self.is_system_ready(),
            "llm_ready": self.llm.is_ready(),
            "mcp_ready": self.mcp.is_ready(),
            "ingestor_ready": self.ingestor.is_ready(),
            "tools_count": self.tools.get_count(),
            "llm_status": self.llm.get_status(),
            "mcp_status": self.mcp.get_status(),
            "ingestor_status": self.ingestor.get_status()
        }

    def get_uptime(self) -> float:
        """Время работы системы."""
        return time.time() - self._start_time
