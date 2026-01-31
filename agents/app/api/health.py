# FILE: agentnet/agents/app/api/health.py
from typing import Dict, Any
import time

from ..managers.system import SystemManager  # Импортируем SystemManager

class HealthHandler:
    def __init__(self, system: SystemManager):
        self.system = system

    def get_status(self) -> Dict[str, Any]:
        system_status = self.system.get_status()

        # Определяем общий статус
        overall = "healthy" if system_status["llm_ready"] else "unhealthy"

        return {
            "status": overall,
            "ready": system_status["llm_ready"],
            "timestamp": int(time.time()),
            "components": {
                "llm": {
                    "ready": system_status["llm_ready"],
                    "details": system_status["llm_status"]
                },
                "mcp": {
                    "ready": system_status["mcp_ready"],
                    "details": system_status["mcp_status"],
                    "tools_count": system_status["tools_count"]
                }
            },
            "degraded": not system_status["mcp_ready"]
        }
