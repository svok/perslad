import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Dict, List, Optional

from infra.logger import get_logger


@dataclass
class StageMetrics:
    """Метрики одной стадии конвейера"""
    name: str
    processed: int = 0
    filtered: int = 0
    errors: int = 0
    processing_time: float = 0.0
    queue_wait_time: float = 0.0
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def duration(self) -> float:
        """Длительность работы стадии"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def throughput(self) -> float:
        """Пропускная способность (элементы/секунду)"""
        if self.duration > 0:
            return self.processed / self.duration
        return 0.0


@dataclass
class QueueMetrics:
    """Метрики очереди"""
    name: str
    max_size: int
    current_size: int = 0
    puts: int = 0
    gets: int = 0
    full_count: int = 0
    avg_wait_time: float = 0.0


class PipelineMetrics:
    """Сбор и агрегация метрик всего конвейера"""

    def __init__(self, pipeline_name: str = "scanner_pipeline"):
        self.pipeline_name = pipeline_name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # Стадии конвейера
        self.stages: Dict[str, StageMetrics] = {}

        # Очереди
        self.queues: Dict[str, QueueMetrics] = {}

        # Общие метрики
        self.total_files_scanned: int = 0
        self.total_files_filtered: int = 0
        self.total_files_changed: int = 0
        self.total_errors: int = 0

        # События (для отладки)
        self.events: List[Dict] = []

    def start(self) -> None:
        """Начало работы конвейера"""
        self.start_time = time.time()
        self._log_event("pipeline_started", {"time": self.start_time})

    def stop(self) -> None:
        """Окончание работы конвейера"""
        self.end_time = time.time()
        self._log_event("pipeline_stopped", {"time": self.end_time})

    def add_stage(self, stage_name: str) -> StageMetrics:
        """Добавляет метрики для стадии"""
        stage_metrics = StageMetrics(name=stage_name)
        stage_metrics.start_time = time.time()
        self.stages[stage_name] = stage_metrics
        self._log_event("stage_added", {"stage": stage_name})
        return stage_metrics

    def complete_stage(self, stage_name: str) -> None:
        """Отмечает завершение стадии"""
        if stage_name in self.stages:
            self.stages[stage_name].end_time = time.time()
            self._log_event("stage_completed", {
                "stage": stage_name,
                "duration": self.stages[stage_name].duration
            })

    def add_queue(self, queue_name: str, max_size: int) -> QueueMetrics:
        """Добавляет метрики для очереди"""
        queue_metrics = QueueMetrics(name=queue_name, max_size=max_size)
        self.queues[queue_name] = queue_metrics
        return queue_metrics

    def update_queue_metrics(self, queue_name: str, current_size: int,
                             puts: int = 0, gets: int = 0) -> None:
        """Обновляет метрики очереди"""
        if queue_name in self.queues:
            queue = self.queues[queue_name]
            queue.current_size = current_size
            queue.puts += puts
            queue.gets += gets

            # Отмечаем, если очередь заполнена (>80%)
            if current_size > queue.max_size * 0.8:
                queue.full_count += 1

    def increment_processed(self, stage_name: str, count: int = 1) -> None:
        """Увеличивает счетчик обработанных элементов для стадии"""
        if stage_name in self.stages:
            self.stages[stage_name].processed += count
            self.total_files_scanned += count

    def increment_filtered(self, stage_name: str, count: int = 1) -> None:
        """Увеличивает счетчик отфильтрованных элементов"""
        if stage_name in self.stages:
            self.stages[stage_name].filtered += count
            self.total_files_filtered += count

    def increment_errors(self, stage_name: str, count: int = 1) -> None:
        """Увеличивает счетчик ошибок"""
        if stage_name in self.stages:
            self.stages[stage_name].errors += count
            self.total_errors += count

    def add_processing_time(self, stage_name: str, duration: float) -> None:
        """Добавляет время обработки для стадии"""
        if stage_name in self.stages:
            self.stages[stage_name].processing_time += duration

    def add_queue_wait_time(self, stage_name: str, duration: float) -> None:
        """Добавляет время ожидания в очереди"""
        if stage_name in self.stages:
            self.stages[stage_name].queue_wait_time += duration

    def add_batch(self, batch_size: int) -> None:
        """Добавляет информацию о батче"""
        self.total_files_changed += batch_size
        self._log_event("batch_processed", {"size": batch_size})

    def get_summary(self) -> Dict:
        """Возвращает сводку метрик"""
        if not self.start_time:
            return {}

        end_time = self.end_time or time.time()
        total_duration = end_time - self.start_time

        return {
            "pipeline": self.pipeline_name,
            "duration_seconds": total_duration,
            "throughput_files_per_second": (
                self.total_files_scanned / total_duration
                if total_duration > 0 else 0
            ),
            "total_files_scanned": self.total_files_scanned,
            "total_files_filtered": self.total_files_filtered,
            "total_files_changed": self.total_files_changed,
            "total_errors": self.total_errors,
            "stages": {
                name: {
                    "processed": stage.processed,
                    "filtered": stage.filtered,
                    "errors": stage.errors,
                    "duration": stage.duration,
                    "throughput": stage.throughput,
                    "processing_time": stage.processing_time,
                    "queue_wait_time": stage.queue_wait_time
                }
                for name, stage in self.stages.items()
            },
            "queues": {
                name: {
                    "current_size": queue.current_size,
                    "max_size": queue.max_size,
                    "utilization_percent": (
                        queue.current_size / queue.max_size * 100
                        if queue.max_size > 0 else 0
                    ),
                    "puts": queue.puts,
                    "gets": queue.gets,
                    "full_count": queue.full_count
                }
                for name, queue in self.queues.items()
            }
        }

    def print_summary(self) -> None:
        """Выводит сводку метрик в консоль"""
        summary = self.get_summary()

        print("\n" + "="*60)
        print("PIPELINE METRICS SUMMARY")
        print("="*60)

        print(f"\nPipeline: {summary['pipeline']}")
        print(f"Duration: {summary['duration_seconds']:.2f}s")
        print(f"Throughput: {summary['throughput_files_per_second']:.1f} files/sec")
        print(f"Files scanned: {summary['total_files_scanned']}")
        print(f"Files filtered: {summary['total_files_filtered']}")
        print(f"Files changed: {summary['total_files_changed']}")
        print(f"Errors: {summary['total_errors']}")

        print("\n--- STAGES ---")
        for stage_name, stage_metrics in summary['stages'].items():
            print(f"\n{stage_name}:")
            print(f"  Processed: {stage_metrics['processed']}")
            print(f"  Filtered: {stage_metrics['filtered']}")
            print(f"  Errors: {stage_metrics['errors']}")
            print(f"  Duration: {stage_metrics['duration']:.2f}s")
            print(f"  Throughput: {stage_metrics['throughput']:.1f}/s")
            print(f"  Processing time: {stage_metrics['processing_time']:.2f}s")
            print(f"  Queue wait time: {stage_metrics['queue_wait_time']:.2f}s")

        print("\n--- QUEUES ---")
        for queue_name, queue_metrics in summary['queues'].items():
            print(f"\n{queue_name}:")
            print(f"  Size: {queue_metrics['current_size']}/{queue_metrics['max_size']}")
            print(f"  Utilization: {queue_metrics['utilization_percent']:.1f}%")
            print(f"  Puts/Gets: {queue_metrics['puts']}/{queue_metrics['gets']}")
            print(f"  Full count: {queue_metrics['full_count']}")

        print("\n" + "="*60)

    def _log_event(self, event_type: str, data: Dict) -> None:
        """Логирует событие для отладки"""
        self.events.append({
            "timestamp": time.time(),
            "type": event_type,
            "data": data
        })


@asynccontextmanager
async def measure_stage(metrics: PipelineMetrics, stage_name: str):
    """Контекстный менеджер для измерения времени стадии"""
    stage_metrics = metrics.add_stage(stage_name)
    start_time = time.time()

    try:
        yield stage_metrics
    finally:
        stage_metrics.end_time = time.time()
        metrics.complete_stage(stage_name)


class MetricsCollector:
    """Сборщик метрик в реальном времени"""

    def __init__(self, pipeline_name: str = "scanner"):
        self.log = get_logger('ingestor.scanner.metrics')
        self.metrics = PipelineMetrics(pipeline_name)
        self._sampling_task: Optional[asyncio.Task] = None
        self._sampling_interval = 1.0  # секунда

    async def start_sampling(self) -> None:
        """Запускает периодический сбор метрик"""
        self._sampling_task = asyncio.create_task(self._sampling_loop())

    async def _sampling_loop(self) -> None:
        """Цикл сбора метрик"""
        while True:
            try:
                await asyncio.sleep(self._sampling_interval)
                # Здесь можно, например, отправлять метрики в мониторинг
                # или логировать состояние очередей
                pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error("Metrics sampling error", exc_info=True)
                raise

    async def stop_sampling(self) -> None:
        """Останавливает сбор метрик"""
        if self._sampling_task:
            self._sampling_task.cancel()
            try:
                await self._sampling_task
            except asyncio.CancelledError:
                pass
