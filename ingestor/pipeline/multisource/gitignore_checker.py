# ingestor.pipeline.multisource/gitignore_checker.py
from pathlib import Path
from typing import Dict, Callable


class GitignoreChecker:
    """Проверяет пути по gitignore rules"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path).resolve()
        self.matchers: Dict[Path, Callable] = {}
        self._loaded = False

    def load(self) -> None:
        """Загружает все .gitignore файлы"""
        if self._loaded:
            return

        try:
            from gitignore_parser import parse_gitignore
        except ImportError:
            self.matchers = {}
            return

        for gitignore_file in self.workspace_path.rglob('.gitignore'):
            if gitignore_file.is_file():
                try:
                    matcher = parse_gitignore(
                        str(gitignore_file),
                        base_dir=str(gitignore_file.parent)
                    )
                    self.matchers[gitignore_file.parent] = matcher
                except Exception:
                    continue

        self._loaded = True

    def should_ignore(self, path: Path) -> bool:
        """True если путь должен быть проигнорирован"""
        if not self._loaded:
            self.load()

        if not self.matchers:
            return False

        abs_path = path if path.is_absolute() else self.workspace_path / path

        for gitignore_dir, matcher in self.matchers.items():
            try:
                if abs_path.is_relative_to(gitignore_dir):
                    if matcher(str(abs_path)):
                        return True
            except Exception:
                continue

        return False
