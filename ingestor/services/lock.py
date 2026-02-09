"""
LLM Lock Handler - координация доступа к LLM между agent и ingestor.

Принцип:
- Agent активно управляет блокировкой (push-модель)
- Ingestor приостанавливает LLM-зависимые операции при блокировке
- TTL защищает от deadlock при падении агента
"""

import asyncio
import time
from dataclasses import dataclass

from infra.logger import get_logger

log = get_logger("ingestor.llm_lock")


@dataclass
class LockState:
    locked: bool = False
    ttl_seconds: float = 0
    locked_at: float = 0


class LLMLockManager:
    """
    Управляет блокировкой LLM со стороны ingestor.
    """

    def __init__(self) -> None:
        self._state = LockState()
        self._lock = asyncio.Lock()

    async def set_lock(self, locked: bool, ttl_seconds: float = 300) -> None:
        """
        Устанавливает состояние блокировки.
        Вызывается через HTTP endpoint от агента.
        """
        async with self._lock:
            self._state.locked = locked
            self._state.ttl_seconds = ttl_seconds
            self._state.locked_at = time.time() if locked else 0

            log.info(
                "llm_lock.updated",
                locked=locked,
                ttl=ttl_seconds if locked else None,
            )

    async def is_locked(self) -> bool:
        """
        Проверяет, заблокирован ли LLM.
        Учитывает TTL для автоматической разблокировки.
        """
        async with self._lock:
            if not self._state.locked:
                return False

            # Проверяем TTL
            elapsed = time.time() - self._state.locked_at
            if elapsed > self._state.ttl_seconds:
                log.info(
                    "llm_lock.ttl_expired",
                    elapsed=elapsed,
                    ttl=self._state.ttl_seconds,
                )
                self._state.locked = False
                return False

            return True

    async def wait_unlocked(self, check_interval: float = 1.0) -> None:
        """
        Ждёт разблокировки LLM.
        Используется в pipeline перед LLM-зависимыми операциями.
        """
        while await self.is_locked():
            log.debug("llm_lock.waiting")
            await asyncio.sleep(check_interval)

    def get_status(self) -> dict:
        """
        Возвращает текущее состояние блокировки для отладки.
        """
        return {
            "locked": self._state.locked,
            "ttl_seconds": self._state.ttl_seconds,
            "locked_at": self._state.locked_at,
            "elapsed": time.time() - self._state.locked_at if self._state.locked else 0,
        }
