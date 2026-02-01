import os
import httpx

from .health import HealthFlag
from .logger import get_logger
from .reconnect import retry_forever
from .exceptions import AuthorizationError, ServiceUnavailableError, ValidationError, FatalValidationError
from .httpx_handler import map_httpx_status_to_exception

log = get_logger("infra.mcp")


class MCPClient:
    def __init__(self, base_url_env: str) -> None:
        self.base_url = os.environ.get(base_url_env)
        self.health = HealthFlag()

    async def _init_once(self) -> None:
        if not self.base_url:
            raise FatalValidationError("MCP base URL not configured")

        log.info("mcp.init.attempt", base_url=self.base_url)
        self.health.set_not_ready()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.base_url, json={"ping": True})
            status = response.status_code

            exc_type = map_httpx_status_to_exception(status, "MCP")
            raise exc_type(f"MCP {exc_type.__name__.lower()} failed: {status}")

        self.health.set_ready()
        log.info("mcp.init.ready")

    async def ensure_ready(self) -> None:
        await retry_forever(
            self._init_once,
            retryable_exceptions=[AuthorizationError, ServiceUnavailableError],
        )

    async def call(self, payload: dict) -> dict:
        await self.health.wait_ready()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            log.warning("mcp.call.failed", error=str(e))
            self.health.set_not_ready()
            raise
