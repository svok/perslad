import asyncio
from typing import List, Dict, Any, Callable
from infra.logger import get_logger

log = get_logger("infra.registry")

class ToolRegistry:
    def __init__(self, mcp):
        self.mcp = mcp
        self._mcp_tools = []
        self._local_tools = {}

    def register_local_tool(self, name: str, description: str, schema: Dict, handler: Callable):
        self._local_tools[name] = {
            "handler": handler,
            "description": description,
            "inputSchema": schema
        }
        log.info(f"Registered local tool: {name}")

    async def initialize(self) -> bool:
        try:
            await asyncio.sleep(1) # Give MCP some time
            try:
                self._mcp_tools = await self.mcp.get_all_tools()
            except Exception:
                pass
            return True
        except Exception as e:
            log.error(f"Error initializing registry: {e}")
            return False

    async def get_tools(self) -> List[Dict[str, Any]]:
        try:
            self._mcp_tools = await self.mcp.get_all_tools()
        except Exception:
            pass

        all_tools = []
        for name, data in self._local_tools.items():
            all_tools.append({
                "name": name,
                "description": data["description"],
                "inputSchema": data["inputSchema"]
            })
        all_tools.extend(self._mcp_tools)
        return all_tools

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name in self._local_tools:
            try:
                handler = self._local_tools[name]["handler"]
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**args)
                else:
                    result = handler(**args)
                return result
            except Exception as e:
                log.error(f"Local tool {name} failed: {e}")
                raise e
        
        return await self.mcp.call_tool(name, args)

    def get_count(self) -> int:
        return len(self._local_tools) + len(self._mcp_tools)

    async def close(self):
        self._local_tools.clear()
        self._mcp_tools.clear()
