"""
Stage 1: Scan

Задача: пройтись по репозиторию и собрать список файлов.
NO LLM.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass

from gitignore_parser import parse_gitignore
from infra.logger import get_logger

log = get_logger("ingestor.pipeline.scan")


@dataclass
class ScannedFile:
    """Результат сканирования одного файла."""
    path: str
    relative_path: str
    size_bytes: int
    extension: str


class ScanStage:
    """
    Сканирует workspace и возвращает список файлов для обработки.
    БЕРЕТ ИЗ .gitignore - не хардкодит списки.
    Поддерживает множественные .gitignore файлы в поддиректориях.
    """

    # Максимальный размер файла (10 MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    def __init__(self, workspace_path: str) -> None:
        self.workspace_path = Path(workspace_path).resolve()

        if not self.workspace_path.exists():
            raise ValueError(f"Workspace path does not exist: {workspace_path}")

        # Загрузить все gitignore файлы из workspace
        self.gitignore_matchers: Dict[Path, Callable] = self._load_all_gitignores()

    def _load_all_gitignores(self) -> Dict[Path, Callable]:
        """
        Загружает все .gitignore файлы из workspace и его поддиректорий.
        Возвращает словарь {directory: gitignore_matcher}.
        """
        matchers = {}
        
        for root, dirs, files in os.walk(self.workspace_path):
            root_path = Path(root)
            gitignore_path = root_path / ".gitignore"
            
            if gitignore_path.exists() and gitignore_path.is_file():
                try:
                    # parse_gitignore принимает путь к .gitignore файлу
                    # и base_dir для резолва относительных путей
                    matcher = parse_gitignore(str(gitignore_path), base_dir=str(root_path))
                    matchers[root_path] = matcher
                    log.info(
                        "scan.gitignore.loaded",
                        path=str(gitignore_path.relative_to(self.workspace_path))
                    )
                except Exception as e:
                    log.warning(
                        "scan.gitignore.load_failed",
                        path=str(gitignore_path.relative_to(self.workspace_path)),
                        error=str(e)
                    )
        
        if not matchers:
            log.warning("scan.gitignore.none_found", workspace=str(self.workspace_path))
        
        return matchers

    def _should_ignore_path(self, path: Path) -> bool:
        """
        Проверяет, нужно ли игнорировать путь на основе .gitignore паттернов.
        Проверяет все .gitignore файлы от корня до родительской директории файла.
        """
        if not self.gitignore_matchers:
            return False

        # Получаем абсолютный путь
        abs_path = path if path.is_absolute() else self.workspace_path / path
        
        # Проверяем каждый .gitignore matcher
        # Начинаем с самого специфичного (ближайшего к файлу)
        for gitignore_dir, matcher in self.gitignore_matchers.items():
            # Проверяем, находится ли путь в поддереве этого .gitignore
            try:
                # Если путь находится в поддереве gitignore_dir
                if abs_path.is_relative_to(gitignore_dir):
                    # Проверяем, игнорируется ли путь
                    if matcher(str(abs_path)):
                        return True
            except (ValueError, Exception):
                # is_relative_to может выбросить ValueError если пути не связаны
                continue
        
        return False

    def _is_binary_file(self, file_path: Path) -> bool:
        """
        Проверяет, является ли файл бинарным.
        Читает первые 8192 байта и проверяет на наличие нулевых байтов.
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)
                # Проверяем на нулевые байты (признак бинарного файла)
                if b'\x00' in chunk:
                    return True
                # Дополнительная проверка: пытаемся декодировать как UTF-8
                try:
                    chunk.decode('utf-8')
                    return False
                except UnicodeDecodeError:
                    return True
        except Exception:
            # Если не можем прочитать, считаем бинарным
            return True

    async def run(self) -> List[ScannedFile]:
        """
        Сканирует workspace и возвращает список файлов.
        БЕРЕТ фильтрацию ТОЛЬКО из .gitignore и расширений.
        """
        log.info("scan.start", workspace=str(self.workspace_path))

        files: List[ScannedFile] = []

        for root, dirs, filenames in os.walk(self.workspace_path):
            root_path = Path(root)
            
            # Фильтруем директории с помощью .gitignore
            # Важно: используем полные пути относительно workspace
            filtered_dirs = []
            for d in dirs:
                dir_path = root_path / d
                relative_dir = dir_path.relative_to(self.workspace_path)
                
                if not self._should_ignore_path(dir_path):
                    filtered_dirs.append(d)
                else:
                    log.debug("scan.dir.ignored", dir=str(relative_dir))
            
            # Обновляем список директорий для os.walk
            dirs[:] = filtered_dirs

            for filename in filenames:
                file_path = root_path / filename
                
                try:
                    relative_path = file_path.relative_to(self.workspace_path)
                except ValueError:
                    # Файл вне workspace
                    continue
                
                relative_str = str(relative_path)

                # Пропускаем директории (на всякий случай)
                if file_path.is_dir():
                    continue

                # Исключаем файлы по .gitignore
                if self._should_ignore_path(file_path):
                    log.debug("scan.file.ignored", file=relative_str)
                    continue

                # Проверяем расширение - оставляем только файлы с расширением
                # (игнорируем безрасширения и бинарные файлы)
                if not file_path.suffix:
                    log.debug("scan.file.no_extension", file=relative_str)
                    continue

                # Проверяем, не является ли файл бинарным
                if self._is_binary_file(file_path):
                    log.debug("scan.file.binary", file=relative_str)
                    continue

                # Проверяем размер
                try:
                    size = file_path.stat().st_size
                    if size > self.MAX_FILE_SIZE:
                        log.debug(
                            "scan.file.too_large",
                            file=relative_str,
                            size=size,
                        )
                        continue
                    
                    # Пропускаем пустые файлы
                    if size == 0:
                        log.debug("scan.file.empty", file=relative_str)
                        continue
                        
                except OSError as e:
                    log.warning("scan.file.error", file=relative_str, error=str(e))
                    continue

                # Добавляем файл
                files.append(
                    ScannedFile(
                        path=str(file_path),
                        relative_path=str(relative_path),
                        size_bytes=size,
                        extension=file_path.suffix,
                    )
                )

        log.info("scan.complete", files_count=len(files))

        # Статистика по расширениям
        ext_stats = {}
        for f in files:
            ext_stats[f.extension] = ext_stats.get(f.extension, 0) + 1

        log.info("scan.stats", extensions=ext_stats)

        return files
