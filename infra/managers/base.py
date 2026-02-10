import logging
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set

class BaseManager(ABC):
    """Базовый класс менеджера с правильной логикой повторных подключений."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agentnet.{name}")
        self._connections: Dict[str, bool] = {}
        self._initialized = False
        self._stop_requested = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._errors: Dict[str, str] = {}
        self._connection_attempts: Dict[str, int] = {}
        self._start_time = time.time()

    @abstractmethod
    async def _connect_all(self) -> Set[str]:
        pass

    @abstractmethod
    async def _disconnect_all(self):
        pass

    async def initialize(self) -> bool:
        if self._initialized:
            return self.is_ready()

        self.logger.info("Starting manager")
        self._initialized = True
        self._stop_requested = False

        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        return True

    async def _reconnect_loop(self):
        """Бесконечный цикл переподключений с улучшенной логикой."""
        while not self._stop_requested:
            connected_servers = await self._connect_all()

            # Обновляем статусы подключений
            for server_name in self._connections.keys():
                was_connected = self._connections.get(server_name, False)
                is_connected = server_name in connected_servers

                if not was_connected and is_connected:
                    self.logger.info(f"✅ {server_name} - Подключено успешно")
                    self._connection_attempts[server_name] = 0
                    self._errors.pop(server_name, None)
                elif was_connected and not is_connected:
                    self.logger.warning(f"⚠️ {server_name} - Подключение потеряно")
                    self._connection_attempts[server_name] = 1

                self._connections[server_name] = is_connected

            # Если все подключено - ждем долго перед следующей проверкой
            if self.is_ready():
                await asyncio.sleep(300)  # 5 минут между проверками при успешном подключении
                continue

            # Иначе вычисляем задержку для следующей попытки
            max_delay = 30
            has_errors = False

            for server_name, connected in self._connections.items():
                if not connected:
                    attempts = self._connection_attempts.get(server_name, 0) + 1
                    self._connection_attempts[server_name] = attempts

                    # Экспоненциальная задержка: 2^attempts, но не более 60 секунд
                    delay = min(2 ** min(attempts, 5), 60)
                    max_delay = min(max_delay, delay)

                    error_msg = self._errors.get(server_name, "неизвестная ошибка")
                    self.logger.info(f"🔄 {server_name} - Следующая попытка через {delay}с (попытка {attempts}, ошибка: {error_msg})")
                    has_errors = True

            if not has_errors and self.is_ready():
                # Все подключено, ждем 5 минут
                await asyncio.sleep(300)
            else:
                await asyncio.sleep(max_delay)

    async def close(self):
        self.logger.info("Stopping manager")
        self._stop_requested = True

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        await self._disconnect_all()
        self._connections.clear()
        self._initialized = False

    def is_ready(self) -> bool:
        return all(self._connections.values())

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ready": self.is_ready(),
            "initialized": self._initialized,
            "connections": {
                name: {
                    "connected": connected,
                    "attempts": self._connection_attempts.get(name, 0),
                    "error": self._errors.get(name)
                }
                for name, connected in self._connections.items()
            }
        }
