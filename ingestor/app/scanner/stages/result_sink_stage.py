from typing import Any, Callable, Awaitable, List

from infra.logger import get_logger
from ingestor.app.scanner.stages.sink_stage import SinkStage


class ResultSinkStage(SinkStage):
    """Финальная стадия — обработка результатов сканирования"""

    def __init__(
            self,
            on_files_changed: Callable[[List[Any]], Awaitable[None]],
            metrics: Any,  # PipelineMetrics
            max_workers: int = 1,
            name: str = "result"
    ):
        super().__init__(name, max_workers)
        self.on_files_changed = on_files_changed
        self.metrics = metrics
        self.log = get_logger(f'ingestor.scanner.{self.__class__.__name__}')

    async def consume(self, item: Any) -> None:
        """Обрабатывает батч результатов"""
        # Пока просто логируем
        self.log.info(f"Received batch: {len(item) if isinstance(item, list) else 1} items")

        if isinstance(item, list):
            for i, sub_item in enumerate(item[:3]):
                self.log.info(f"  [{i}] {type(sub_item).__name__}: {str(sub_item)[:100]}")
            if len(item) > 3:
                self.log.info(f"  ... and {len(item) - 3} more")
        else:
            self.log.info(f"  {type(item).__name__}: {str(item)[:200]}")

        # TODO: здесь будет вызов on_files_changed и обновление metrics
        # summaries = self._convert_to_summaries(item)
        # await self.on_files_changed(summaries)
        # self.metrics.add_batch(len(summaries))
