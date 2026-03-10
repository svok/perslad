import asyncio
from typing import List, Dict, Any, Callable
from infra.logger import get_logger

log = get_logger("infra.registry")

class ToolRegistry:
    def __init__(self, mcp):
        self.mcp = mcp
        self._mcp_tools = []
        self._local_tools = {}
        self._request_tools = {}

    def register_local_tool(self, name: str, description: str, schema: Dict, handler: Callable):
        self._local_tools[name] = {
            "handler": handler,
            "description": description,
            "inputSchema": schema
        }
        log.info(f"Registered local tool: {name}")

    def register_request_tools(self, tools: List[Dict[str, Any]]) -> None:
        """Register temporary request-provided tools."""
        self._request_tools.clear()
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name")
            if name:
                self._request_tools[name] = {
                    "description": func.get("description", ""),
                    "inputSchema": func.get("parameters", {})
                }
                log.info(f"Registered request tool: {name}")
        log.info(f"Registered {len(self._request_tools)} request tools")

    def _create_request_tool_handler(self, name: str, args: Dict[str, Any]) -> Any:
        """Create a handler for request tools based on their name."""
        name_lower = name.lower()
        
        if name_lower == "add" or name_lower == "sum":
            a = args.get("a", 0)
            b = args.get("b", 0)
            return {"result": a + b, "operation": "add", "a": a, "b": b}
        
        if name_lower == "subtract" or name_lower == "sub":
            a = args.get("a", 0)
            b = args.get("b", 0)
            return {"result": a - b, "operation": "subtract", "a": a, "b": b}
        
        if name_lower == "multiply" or name_lower == "mul":
            a = args.get("a", 1)
            b = args.get("b", 1)
            return {"result": a * b, "operation": "multiply", "a": a, "b": b}
        
        if name_lower == "divide" or name_lower == "div":
            a = args.get("a", 1)
            b = args.get("b", 1)
            if b == 0:
                return {"error": "Division by zero"}
            return {"result": a / b, "operation": "divide", "a": a, "b": b}
        
        if name_lower == "echo":
            text = args.get("text", "")
            return {"result": text}
        
        if name_lower == "uppercase":
            text = args.get("text", "")
            return {"result": text.upper()}
        
        if name_lower == "lowercase":
            text = args.get("text", "")
            return {"result": text.lower()}
        
        if name_lower == "length":
            text = args.get("text", "")
            return {"result": len(text)}
        
        return None

    def clear_request_tools(self) -> None:
        """Clear temporary request-provided tools."""
        self._request_tools.clear()

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
        if name in self._request_tools:
            log.info(f"Executing request tool: {name} with args: {args}")
            handler_result = self._create_request_tool_handler(name, args)
            if handler_result is not None:
                return handler_result
            return {
                "error": f"Request tool '{name}' is not implemented. "
                         f"Available built-in: add, subtract, multiply, divide, echo, uppercase, lowercase, length"
            }

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
