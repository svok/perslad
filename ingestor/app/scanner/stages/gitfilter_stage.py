from pathlib import Path
from typing import Optional, Dict, Callable

from ingestor.app.scanner.file_event import FileEvent
from ingestor.app.scanner.stages.processor_stage import ProcessorStage


class GitignoreFilterStage(ProcessorStage):
    """Фильтрует файлы по .gitignore"""

    def __init__(self, gitignore_matchers: Dict[Path, Callable], max_workers: int = 2):
        super().__init__("gitignore_filter", max_workers)
        self.matchers = gitignore_matchers

    async def process(self, event: FileEvent) -> Optional[FileEvent]:
        """Пропускает событие если НЕ игнорируется gitignore"""
        if not self.matchers:
            return event

        abs_path = event.abs_path
        if not abs_path:
            self.log.warning(f"No abs_path for {event.path}, skipping")
            return None

        # Проверяем все матчеры
        for gitignore_dir, matcher in self.matchers.items():
            try:
                # Проверяем, относится ли файл к этой gitignore-директории
                if self._is_in_dir(abs_path, gitignore_dir):
                    # Проверяем матчер
                    is_ignored = matcher(str(abs_path))
                    if is_ignored:
                        self.log.debug(f"Ignored by {gitignore_dir}: {abs_path.name}")
                        return None  # Фильтруем
            except Exception as e:
                self.log.warning(f"Matcher error for {abs_path}: {e}")
                continue

        # Не проигнорирован — пропускаем дальше
        self.log.debug(f"Passed filter: {abs_path.name}")
        return event

    def _is_in_dir(self, path: Path, directory: Path) -> bool:
        """Проверяет, находится ли path внутри directory"""
        try:
            path.relative_to(directory)
            return True
        except ValueError:
            return False
