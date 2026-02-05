import threading
from typing import Generic, TypeVar, Optional
import asyncio
import time

T = TypeVar('T')


class ThrottledQueue(Generic[T]):
    """Очередь с обратным давлением и метриками"""

    def __init__(
            self,
            maxsize: int = 1000,
            throttle_delay: float = 0.001,
            name: str = "queue"
    ):
        from infra.logger import get_logger
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.maxsize = maxsize
        self.throttle_delay = throttle_delay
        self.name = name
        self.log = get_logger(f'ingestor.queue.{name}')

        self.metrics = {
            'put_count': 0,
            'get_count': 0,
            'max_wait_time': 0.0,
            'last_throttle': 0.0,
            'get_start_time': 0.0
        }

    async def put(self, item: Optional[T]) -> None:
        """Добавляет элемент с обратным давлением"""
        start = time.time()
        loop_id = id(asyncio.get_running_loop())
        # self.log.info(f"[{self.name}] PUT queue_id={id(self.queue)} loop_id={loop_id} thread={threading.get_ident()} loop_thread={self.queue._loop}")

        # Обратное давление при заполнении очереди
        if self.qsize > self.maxsize * 0.8:
            await asyncio.sleep(self.throttle_delay)
            self.metrics['last_throttle'] = time.time()

        print("PUT queue_id =", id(self.queue), loop_id)
        await self.queue.put(item)
        print("PUT-x")
        self.metrics['put_count'] += 1
        self.metrics['max_wait_time'] = max(
            self.metrics['max_wait_time'],
            time.time() - start
        )

    async def get(self) -> Optional[T]:
        """Берет элемент из очереди"""
        # self.log.info(f"[{self.name}] get() thread={threading.get_ident()} loop_thread={self.queue._loop}")
        loop_id = id(asyncio.get_running_loop())
        self.metrics['get_start_time'] = time.time()
        print("GET queue_id =", id(self.queue), loop_id)
        item = await self.queue.get()
        print("GET-x")


        self.metrics['get_count'] += 1
        self.metrics['max_wait_time'] = max(
            self.metrics['max_wait_time'],
            time.time() - self.metrics.get('get_start_time', 0)
        )
        return item

    def get_nowait(self) -> Optional[T]:
        """Неблокирующее извлечение элемента"""
        try:
            item = self.queue.get_nowait()
            self.metrics['get_count'] += 1
            return item
        except asyncio.QueueEmpty:
            raise  # Пробрасываем оригинальное исключение для совместимости с asyncio.Queue

    def task_done(self) -> None:
        """Отмечает задачу выполненной"""
        self.queue.task_done()

    @property
    def qsize(self) -> int:
        """Текущий размер очереди"""
        return self.queue.qsize()

    @property
    def is_full(self) -> bool:
        """Заполнена ли очередь на 80%"""
        return self.qsize > self.maxsize * 0.8
