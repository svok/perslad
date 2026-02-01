import os
import aiohttp

from .health import HealthFlag
from .logger import get_logger
from .reconnect import retry_forever
from .exceptions import AuthorizationError, ServiceUnavailableError, ValidationError, FatalValidationError

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
        if not self.base_url:
            raise FatalValidationError("MCP base URL not configured")

        log.info("mcp.init.attempt", base_url=self.base_url)
        self.health.set_not_ready()
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, json={"ping": True}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                status = resp.status
                match status:
                    case 401 | 403:
                        raise AuthorizationError(f"MCP authentication failed: {status}")
                    case 500 | 502 | 503 | 504:
                        raise ServiceUnavailableError(f"MCP service unavailable: {status}")
                    case 404:
                        raise FatalValidationError(f"MCP endpoint not found: {status}")
                    case 405:
                        raise FatalValidationError(f"MCP method not allowed: {status}")
                    case 429:
                        raise ServiceUnavailableError(f"MCP rate limit exceeded: {status}")
                    case 400:
                        raise FatalValidationError(f"MCP bad request: {status}")
                    case 200:
                        pass
                    case _:
                        raise ValidationError(f"MCP probe failed: {status}")
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
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except Exception as e:
            log.warning("mcp.call.failed", error=str(e))
            self.health.set_not_ready()
            raise
