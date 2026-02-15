# FILE: agentnet/agents/main.py
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException

from infra.config.endpoints import LangGraph, LLM
from .app.api.chat import ChatHandler
from .app.api.health import HealthHandler
from .app.logger import logger, setup_logging
from .app.managers.system import SystemManager
from .app.models import ChatRequest

# Настраиваем логирование
setup_logging()

# Единый менеджер системы
system = SystemManager()
chat_handler = ChatHandler(system)
health_handler = HealthHandler(system)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("🚀 Starting Agent System")
    logger.info("=" * 50)

    await system.initialize()

    # Ждем подключения MCP
    logger.info("⏳ Waiting for MCP connections...")
    max_wait = 30
    for i in range(max_wait):
        tools = await system.tools.get_tools()
        if tools:
            logger.info(f"✅ MCP connected with {len(tools)} tools")
            break
        logger.info(f"⌛ Waiting for MCP... ({i+1}/{max_wait})")
        await asyncio.sleep(1)
    else:
        logger.error("❌ MCP connection timeout!")

    logger.info(f"✅ System initialized")
    logger.info(f"  LLM: {'Connected' if system.llm.is_ready() else '❌ Failed'}")
    logger.info(f"  MCP: {'Connected' if system.mcp.is_ready() else '❌ Failed'}")
    logger.info(f"  Tools: {system.tools.get_count()} available")

    yield

    logger.info("🛑 Stopping system...")
    await system.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root() -> Dict[str, Any]:
    status = system.get_status()
    return {
        "service": "Agent System",
        "status": status
    }

@app.get(LangGraph.HEALTH)
async def health_check() -> Dict[str, Any]:
    return health_handler.get_status()

@app.get(LLM.MODELS)
async def list_models() -> Dict[str, Any]:
    return {"object": "list", "data": [{"id": "langgraph-agent", "object": "model"}]}

@app.post(LangGraph.CHAT_COMPLETIONS)
async def chat_completions(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages are required")

    logger.info(f"Chat request: {len(request.messages)} messages, stream={request.stream}")

    if request.stream:
        return await chat_handler.stream_response(request.messages)
    return await chat_handler.direct_response(request.messages)

@app.get("/debug/tools")
async def debug_tools() -> Dict[str, Any]:
    """Отладочная информация о инструментах."""
    tools = await system.tools.get_tools()
    return {
        "tools_count": len(tools),
        "tools": [{"name": t["name"], "description": t.get("description", "")[:100]} for t in tools],
        "llm_has_tools": system.llm.model is not None and hasattr(system.llm.model, 'bind_tools'),
        "mcp_ready": system.mcp.is_ready()
    }
