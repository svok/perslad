from typing import Dict, List, Any, Set

from fastmcp import Client

from infra.logger import get_logger
from .base import BaseManager

log = get_logger("infra.mcp")

class MCPManager(BaseManager):
    """Менеджер MCP с множественными необязательными соединениями."""

    def __init__(self, servers_config: List[Dict[str, Any]]):
        """
        Args:
            servers_config: List of dicts with keys: name, url, enabled (optional)
        """
        super().__init__("mcp")
        self.clients: Dict[str, Client] = {}
        self.tools: List[Dict[str, Any]] = []
        self._configs = servers_config

        # Инициализируем соединения для всех серверов
        for config in self._configs:
            if config.get("enabled", True):
                self._connections[config["name"]] = False

    async def _connect_all(self) -> Set[str]:
        """Попытка подключения ко всем MCP серверам."""
        log.info("mcp.connect.start")

        connected = set()

        for config in self._configs:
            if not config.get("enabled", True):
                continue

            name = config["name"]
            url = config["url"]

            try:
                log.debug("mcp.connect.server", server=name, url=url)

                client = Client(url)

                async with client:
                    tools_response = await client.list_tools()

                    tools = []
                    for tool_info in tools_response:
                        # Получаем имя и описание
                        t_name = tool_info.name
                        # Используем inputSchema с большой буквы, как положено в MCP/FastMCP
                        t_schema = getattr(tool_info, 'inputSchema', {})
                        t_desc = getattr(tool_info, 'description', '')

                        tool_data = {
                            "name": t_name,
                            "description": t_desc,
                            "inputSchema": t_schema,
                            "source": name
                        }
                        tools.append(tool_data)

                    persistent_client = Client(url)
                    await persistent_client.__aenter__()

                    self.clients[name] = persistent_client

                    # Обновляем инструменты
                    self.tools = [t for t in self.tools if t.get("source") != name]
                    self.tools.extend(tools)

                    connected.add(name)
                    self._errors.pop(name, None)

                    log.info("mcp.connect.success", server=name, tools_count=len(tools))

            except Exception as e:
                error_type = type(e).__name__
                log.error("mcp.connect.failed", server=name, error=error_type)
                self._errors[name] = error_type

        return connected

    async def _disconnect_all(self):
        """Отключение от всех MCP серверов."""
        log.info("mcp.disconnect.start")

        for name, client in list(self.clients.items()):
            try:
                await client.__aexit__(None, None, None)
            except Exception:
                pass

        self.clients.clear()
        self.tools.clear()

        # Сбрасываем статусы соединений
        for name in self._connections.keys():
            self._connections[name] = False

    def is_ready(self) -> bool:
        """MCP готов, если хотя бы одно соединение установлено (они необязательные)."""
        return any(self._connections.values())

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Вызов инструмента через FastMCP Client."""
        if not self.clients:
            raise ValueError("No MCP servers connected")

        for name, client in self.clients.items():
            try:
                result = await client.call_tool(tool_name, arguments)
                return result
            except Exception:
                continue

        raise ValueError(f"Tool '{tool_name}' not available on connected servers")

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Получение всех инструментов."""
        return self.tools.copy()

    def get_status(self) -> Dict[str, Any]:
        """Статус MCP."""
        base = super().get_status()

        base.update({
            "total_tools": len(self.tools),
            "connected_servers": list(self.clients.keys())
        })

        return base
