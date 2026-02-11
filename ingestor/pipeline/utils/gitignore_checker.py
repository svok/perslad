from pathlib import Path
from typing import Dict

import pathspec


class GitignoreChecker:
    """Проверяет пути по правилам .gitignore с поддержкой вложенности."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path).resolve()
        # Словарь: {путь_к_директории: PathSpec}
        self.specs: Dict[Path, pathspec.PathSpec] = {}

    def load_spec_for_dir(self, dir_path: Path) -> None:
        """Загружает .gitignore конкретной директории, если он существует."""
        gitignore_file = dir_path / '.gitignore'
        if gitignore_file.is_file():
            try:
                with open(gitignore_file, 'r', encoding='utf-8') as f:
                    spec = pathspec.PathSpec.from_lines(
                        pathspec.patterns.GitWildMatchPattern,
                        f
                    )
                    self.specs[dir_path] = spec
            except Exception:
                pass

    def should_ignore(self, path: Path, is_dir: bool = False) -> bool:
        """
        Проверяет, должен ли быть проигнорирован путь.
        Учитывает все применимые спецификации от корня до текущей папки.
        """
        abs_path = path if path.is_absolute() else self.workspace_path / path

        # Базовая проверка системных папок git
        if '.git' in abs_path.parts:
            return True

        # Проверяем путь всеми загруженными спецификациями,
        # которые являются родительскими для данного пути
        for gi_dir, spec in self.specs.items():
            if abs_path.is_relative_to(gi_dir):
                # Для корректного матчинга директорий в gitignore
                # путь должен заканчиваться на слэш
                rel_path = str(abs_path.relative_to(gi_dir))
                if is_dir and not rel_path.endswith('/'):
                    rel_path += '/'

                if spec.match_file(rel_path):
                    return True
        return False
