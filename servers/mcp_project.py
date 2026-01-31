#!/usr/bin/env python3
"""
MCP Project Server - "УМНАЯ" ВЕРСИЯ
Исправлены описания инструментов для корректной работы LLM-агента.
Использует FastMCP.
"""
import os
import re
import structlog
from pathlib import Path
from typing import List, Tuple

from fastmcp import FastMCP

# Настройка логирования с JSON форматом
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
log = structlog.get_logger("mcp_project")

# ==================== ИНИЦИАЛИЗАЦИЯ СЕРВЕРА ====================
mcp = FastMCP("mcp-project")

# ==================== КОНФИГУРАЦИЯ ====================
WORKSPACE = "/workspace"
HOST = "0.0.0.0"
PORT = 8083

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def find_python_files(root_path: str) -> List[Tuple[str, str]]:
    """Рекурсивно находит все .py файлы."""
    py_files = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Фильтруем файлы
        filenames = [f for f in filenames if not f.startswith('.') and f != '__pycache__']

        # Фильтруем директории (модифицируем список in-place, чтобы os.walk не заходил туда)
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']

        for filename in filenames:
            if filename.endswith('.py'):
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root_path)
                py_files.append((full_path, rel_path))
    return py_files

def safe_join(base: str, target: str) -> str:
    """Безопасное объединение путей."""
    base_path = Path(base).resolve()
    target_path = (base_path / target).resolve()

    if not target_path.is_relative_to(base_path):
        raise ValueError(f"Path traversal attempt: {target}")
    return str(target_path)

def format_directory_listing(items: List[Path], max_items: int = 50) -> Tuple[List[str], int, int]:
    """Форматирует список элементов директории с ограничением."""
    dirs = []
    files = []

    for item in items:
        if item.is_dir():
            dirs.append(item)
        else:
            files.append(item)

    dirs.sort(key=lambda x: x.name.lower())
    files.sort(key=lambda x: x.name.lower())

    all_items = dirs + files
    total_items = len(all_items)
    display_items = all_items[:max_items]

    lines = []
    for item in display_items:
        if item.is_dir():
            lines.append(f"📁 {item.name}/")
        else:
            # Добавляем размер для файлов
            try:
                size = item.stat().st_size
                size_str = f" ({size:,} B)" if size < 1024 else f" ({size/1024:.1f} KB)"
            except:
                size_str = ""
            lines.append(f"📄 {item.name}{size_str}")

    return lines, len(display_items), total_items

# ==================== ИНСТРУМЕНТЫ (MCP TOOLS) ====================

@mcp.tool()
def search_symbol(symbol: str, search_type: str = "partial") -> str:
    """
    Ищет определения функций или классов в проекте по имени или смысловому ключевому слову.

    ИСПОЛЬЗУЙ ЭТОТ ИНСТРУМЕНТ, КОГДА ПОЛЬЗОВАТЕЛЬ ПРОСИТ:
    - "Найди функцию расчета..." -> ищи слово "расчет" или "calculate"
    - "Где реализован модуль пополнения..." -> ищи "пополнение" или "replenishment"
    - "Найди файл с математической моделью..." -> ищи "model" или "math"

    Args:
        symbol (str): Имя функции/класса ИЛИ ключевое слово для поиска (напр. 'auth', 'model').
        search_type (str): 'partial' (по умолчанию) ищет частичное совпадение, 'exact' - полное.
    """
    # Нормализация запроса
    clean_symbol = symbol.strip()
    if not clean_symbol:
        return "❌ Пустой запрос для поиска."

    results = []
    py_files = find_python_files(WORKSPACE)

    # Регулярное выражение для поиска
    # Ищем только в начале строки def или class, чтобы не перегружать результат
    if search_type == "exact":
        pattern = re.compile(rf'^\s*(def|class)\s+{re.escape(clean_symbol)}\b', re.MULTILINE)
    else:
        # Partial: ищем def ClassName или def function_name
        pattern = re.compile(rf'^\s*(def|class)\s+.*{re.escape(clean_symbol)}.*\b', re.MULTILINE)

    for full_path, rel_path in py_files:
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Быстрая проверка наличия строки вообще
            if clean_symbol.lower() in content.lower():
                # Если есть, то точечный поиск через regex
                matches = pattern.findall(content)
                if matches:
                    results.append(f"✅ {rel_path} (найдено совпадение)")

        except Exception as e:
            # Игнорируем ошибки чтения бинарных или странных файлов
            continue

    if results:
        return f"🔍 Поиск по '{clean_symbol}' (тип: {search_type}):\n" + "\n".join(results)
    else:
        return (f"❌ Определения с именем или ключевым словом '{clean_symbol}' не найдены.\n"
                f"💡 Совет: Попробуйте использовать более общее слово (например, 'model' вместо 'math model') "
                f"или воспользуйтесь 'project_structure' для просмотра файлов.")

@mcp.tool()
def read_file(path: str, line_start: int = None, line_end: int = None) -> str:
    """
    Читает содержимое файла по указанному пути.

    ИСПОЛЬЗУЙ, КОГДА НУЖНО ПРОАНАЛИЗИРОВАТЬ КОД ИЛИ КОНСТАНТЫ.

    Args:
        path (str): Путь к файлу относительно корня проекта (напр., 'src/main.py').
        line_start (int, optional): Номер строки начала чтения.
        line_end (int, optional): Номер строки конца чтения.
    """
    try:
        full_path = safe_join(WORKSPACE, path)

        if not os.path.exists(full_path):
            return f"❌ Файл не найден: {path}"
        if not os.path.isfile(full_path):
            return f"❌ Указанный путь не является файлом: {path}"

        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total_lines = len(lines)

        if line_start is not None and line_end is not None:
            start = max(0, line_start - 1)
            end = min(total_lines, line_end)
            selected = lines[start:end]
            range_info = f" (строки {line_start}-{line_end})"
        elif line_start is not None:
            start = max(0, line_start - 1)
            # Читаем блок 50 строк
            end = min(total_lines, start + 50)
            selected = lines[start:end]
            range_info = f" (строки {line_start}-{end})"
        else:
            selected = lines
            range_info = ""

        content = "".join(selected)
        file_size = os.path.getsize(full_path)

        return (f"📄 Файл: {path}{range_info}\n"
                f"📊 Размер: {file_size:,} байт\n"
                f"🔢 Строк в файле: {total_lines}\n"
                f"{'='*50}\n"
                f"{content}")

    except ValueError as e:
        return f"❌ Ошибка безопасности: {str(e)}"
    except Exception as e:
        return f"❌ Ошибка чтения: {str(e)}"

@mcp.tool()
def project_structure(max_depth: int = 1, path: str = ".", max_items_per_level: int = 250) -> str:
    """
    Выводит древовидную структуру проекта (файлы и папки).

    ИСПОЛЬЗУЙ ДЛЯ НАВИГАЦИИ или если нужно найти путь к файлу,
    но точное название неизвестно.

    Args:
        max_depth (int): Глубина сканирования (рекурсии). По умолчанию 1.
        path (str): Относительный путь к директории. "." - это корень проекта.
        max_items_per_level (int): Лимит файлов на одну папку (чтобы не заспамить вывод).
    """
    target_path = Path(WORKSPACE) / path if path != "." else Path(WORKSPACE)

    if not target_path.exists():
        return f"❌ Путь не существует: {path}"
    if not target_path.is_dir():
        return f"❌ Указанный путь не является директорией: {path}"

    def build_tree(dir_path: Path, current_depth: int = 0, prefix: str = "") -> List[str]:
        if current_depth >= max_depth:
            return []

        lines = []
        try:
            items = list(dir_path.iterdir())
            formatted_lines, displayed_count, total_count = format_directory_listing(items, max_items_per_level)

            for i, line in enumerate(formatted_lines):
                is_last = (i == len(formatted_lines) - 1)
                # Извлекаем имя из строки (формат "📁 name" или "📄 name (size)")
                name_part = line.split()[1].replace('/', '')
                item_path = dir_path / name_part

                item_prefix = "└── " if is_last else "├── "
                lines.append(f"{prefix}{item_prefix}{line}")

                # Рекурсия
                if line.startswith("📁") and current_depth + 1 < max_depth:
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    lines.extend(build_tree(item_path, current_depth + 1, new_prefix))

            if total_count > displayed_count:
                lines.append(f"{prefix}└── ... и ещё {total_count - displayed_count} элементов")

        except PermissionError:
            lines.append(f"{prefix}└── ⚠️  [нет доступа]")
        except Exception as e:
            lines.append(f"{prefix}└── ⚠️  [ошибка: {str(e)[:30]}]")

        return lines

    tree_lines = build_tree(target_path)

    # Заголовок
    header = (f"📁 Папка: {path if path != '.' else 'ROOT'}\n"
              f"📏 Глубина: {max_depth} | 📏 Лимит на уровень: {max_items_per_level}\n\n")

    if tree_lines:
        return header + "\n".join(tree_lines)
    else:
        return header + "📭 Папка пуста или не содержит файлов."

# ==================== ЗАПУСК СЕРВЕРА ====================
if __name__ == "__main__":
    log.info("mcp_project.start", host=HOST, port=PORT, workspace=WORKSPACE)

    # Используем HTTP транспорт для работы в Docker
    mcp.run(
        transport="http",
        host=HOST,
        port=PORT,
        log_level="info"
    )
