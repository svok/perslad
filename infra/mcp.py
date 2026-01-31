import os
import aiohttp

from .health import HealthFlag
from .logger import get_logger
from .reconnect import retry_forever

log = get_logger("infra.mcp")


class MCPClient:
    def __init__(self, base_url_env: str) -> None:
        self.base_url = os.environ.get(base_url_env)
        self.health = HealthFlag()

    async def _probe(self) -> None:
        if not self.base_url:
            raise RuntimeError("MCP base URL not configured")

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, json={"ping": True}) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"MCP probe failed: {resp.status}")

    async def _init_once(self) -> None:
        log.info("mcp.init.attempt", base_url=self.base_url)
        self.health.set_not_ready()
        await self._probe()
        self.health.set_ready()
        log.info("mcp.init.ready")

    async def ensure_ready(self) -> None:
        await retry_forever(self._init_once)

    async def call(self, payload: dict) -> dict:
        await self.health.wait_ready()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except Exception as e:
            # КЛЮЧЕВОЕ МЕСТО
            log.warning("mcp.call.failed", error=str(e))
            self.health.set_not_ready()
            raise
