"""
File Sources Base Class

Базовый класс с .gitignore фильтрацией
"""

from abc import ABC
from pathlib import Path

from gitignore_parser import parse_gitignore

from ingestor.app.storage import FileSummary


class BaseFileSource(ABC):
    """
    Базовый класс для источников файлов с .gitignore поддержкой
    """

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path).resolve()
        self.gitignore_matchers: dict = {}

    def _load_gitignore_matchers(self) -> None:
        """
        Загружает все .gitignore файлы из workspace и его поддиректорий
        """
        for root, dirs, files in self.workspace_path.rglob('*'):
            gitignore_path = root / ".gitignore"
            if gitignore_path.exists() and gitignore_path.is_file():
                try:
                    matcher = parse_gitignore(str(gitignore_path), base_dir=str(root))
                    self.gitignore_matchers[root] = matcher
                except Exception as e:
                    print(f"Failed to load .gitignore: {e}")

    def _should_ignore_path(self, path: Path) -> bool:
        """
        Проверяет, нужно ли игнорировать путь на основе всех .gitignore
        """
        abs_path = path if path.is_absolute() else self.workspace_path / path

        for gitignore_dir, matcher in self.gitignore_matchers.items():
            if abs_path.is_relative_to(gitignore_dir):
                try:
                    if matcher(str(abs_path)):
                        return True
                except (ValueError, Exception):
                    continue

        return False

    def _calculate_file_metadata(self, file_path: Path) -> FileSummary:
        """
        Расчитывает метаданные файла (mtime, checksum, размер)
        """
        mtime = file_path.stat().st_mtime

        # Расчитываем MD5
        import hashlib
        checksum = ""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_md5.update(chunk)
            checksum = hash_md5.hexdigest()
        except Exception:
            pass

        return FileSummary(
            file_path=str(file_path.relative_to(self.workspace_path)),
            summary="",
            chunk_ids=[],
            metadata={
                "mtime": mtime,
                "checksum": checksum,
                "size": file_path.stat().st_size,
            }
        )
