#!/usr/bin/env python3
"""
MCP Bash Server - "УМНАЯ" ВЕРСИЯ
Управление терминалом и системными операциями.
Обновлены описания инструментов для корректной работы LLM-агента.
"""
import asyncio
import os
import sys
import subprocess
import structlog
from typing import List, Optional
from fastmcp import FastMCP

# Инициализация метрик (если настроено)
try:
    from infra.metrics import metrics_manager
    metrics_manager.initialize(service_name="perslad-mcp-bash")
except ImportError:
    pass

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
log = structlog.get_logger("mcp_bash")

# ==================== ИНИЦИАЛИЗАЦИЯ СЕРВЕРА ====================
mcp = FastMCP("mcp-bash")

# ==================== КОНФИГУРАЦИЯ ====================
WORKSPACE = "/workspace"
HOST = "0.0.0.0"
PORT = 8081

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def execute_shell_command(cmd: str, timeout: int = 30) -> dict:
    """Выполняет shell команду с таймаутом и возвращает структурированный результат."""
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKSPACE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            exit_code = process.returncode
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "success": False,
                "error": f"Таймаут команды ({timeout} секунд)",
                "exit_code": -1,
                "stdout": "",
                "stderr": ""
            }

        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()

        return {
            "success": exit_code == 0,
            "exit_code": exit_code,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "command": cmd
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "exit_code": -1,
            "stdout": "",
            "stderr": ""
        }

def format_command_result(result: dict) -> str:
    """Форматирует результат выполнения команды."""
    lines = []

    if result.get("success", False):
        lines.append("✅ Команда выполнена успешно")
    else:
        lines.append("❌ Ошибка выполнения команды")

    lines.append(f"📝 Команда: {result.get('command', 'N/A')}")
    lines.append(f"🔢 Код завершения: {result.get('exit_code', 'N/A')}")

    if "error" in result and result["error"]:
        lines.append(f"🚨 Ошибка: {result['error']}")

    stdout = result.get("stdout", "")
    if stdout:
        lines.append(f"\n📤 STDOUT:\n{stdout}")

    stderr = result.get("stderr", "")
    if stderr:
        lines.append(f"\n📥 STDERR:\n{stderr}")

    return "\n".join(lines)

# ==================== ИНСТРУМЕНТЫ (MCP TOOLS) ====================

@mcp.tool()
async def execute_command(cmd: str, timeout: int = 30) -> str:
    """
    Выполняет произвольную shell команду (bash) в рабочей директории (/workspace).

    ИСПОЛЬЗУЙ ЭТОТ ИНСТРУМЕНТ ДЛЯ:
    - Операций с файловой системой (ls, mv, cp, mkdir)
    - Системной диагностики (ps, top, uptime)
    - Поиска по содержимому файлов (grep, find)
    - Сборки проектов (make, npm install, etc.)

    ВАЖНО: Если нужно запустить конкретный Python файл, лучше используй run_python_script.

    Args:
        cmd (str): Полная команда для выполнения (напр., 'ls -la', 'grep "TODO" src/').
        timeout (int): Максимальное время выполнения в секундах (по умолчанию 30).
    """
    if not cmd or not cmd.strip():
        return "❌ Ошибка: Команда не может быть пустой"

    # Базовая защита
    dangerous_patterns = ['rm -rf /', 'dd if=', 'mkfs', ':(){:|:&};:', 'chmod 777 /']
    for pattern in dangerous_patterns:
        if pattern in cmd:
            return f"❌ Отклонено: Обнаружена потенциально опасная команда"

    log.debug("bash.execute", command=cmd)
    result = await execute_shell_command(cmd, timeout)
    return format_command_result(result)

@mcp.tool()
async def check_system(check_type: str = "overview") -> str:
    """
    Проверяет состояние системы, диска, памяти или Docker контейнеров.

    ИСПОЛЬЗУЙ, КОГДА ПОЛЬЗОВАТЕЛЬ СПРАШИВАЕТ:
    - "Сколько места на диске?" -> check_type='disk'
    - "Какие контейнеры запущены?" -> check_type='docker'
    - "Что с памятью?" -> check_type='memory'
    - "Статус сервера" -> check_type='overview'

    Args:
        check_type (str): Тип диагностики. Допустимые значения:
            - 'overview': Общая информация (ОС, диск, память)
            - 'disk': Детальное использование диска
            - 'memory': Использование RAM/Swap
            - 'processes': Топ процессов по нагрузке CPU
            - 'docker': Список запущенных контейнеров
            - 'workspace': Размер директории проекта
    """
    log.debug("bash.check", check_type=check_type)

    commands = {
        "overview": "echo '=== Обзор ===' && uname -a && echo '---' && df -h /workspace && echo '---' && free -h",
        "disk": "df -h",
        "memory": "free -h",
        "processes": "ps aux --sort=-%cpu | head -20",
        "docker": "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'",
        "workspace": f"ls -lah {WORKSPACE} && echo '--- Top sizes ---' && du -sh {WORKSPACE}/* 2>/dev/null | sort -hr | head -10"
    }

    if check_type not in commands:
        available = ", ".join(commands.keys())
        return f"❌ Неизвестный тип проверки. Доступно: {available}"

    result = await execute_shell_command(commands[check_type], timeout=15)

    if result["success"]:
        titles = {
            "overview": "📊 Обзор системы",
            "disk": "💾 Использование диска",
            "memory": "🧠 Использование памяти",
            "processes": "⚙️ Топ-20 процессов по CPU",
            "docker": "🐳 Запущенные Docker контейнеры",
            "workspace": "📁 Содержимое workspace и размеры"
        }
        title = titles.get(check_type, "Системная информация")
        return f"{title}:\n\n{result['stdout']}"
    else:
        return f"❌ Ошибка проверки:\n{result.get('stderr', 'Неизвестная ошибка')}"

@mcp.tool()
async def run_python_script(script: str, args: str = "") -> str:
    """
    Выполняет Python скрипт, находящийся в рабочей директории (/workspace).

    ИСПОЛЬЗУЙ ДЛЯ:
    - Запуска тестов (python -m pytest)
    - Запуска конкретных утилит (python utils/generate_data.py)
    - Быстрого выполнения скрипта

    Args:
        script (str): Имя файла или путь к скрипту (напр., 'main.py', 'scripts/check.py').
        args (str): Аргументы командной строки, передаваемые скрипту.
    """
    script_path = os.path.join(WORKSPACE, script.strip())

    if not os.path.exists(script_path):
        return f"❌ Файл не найден: {script}"

    if not script_path.endswith('.py'):
        # Позволяем запускать python -m, если пользователь пишет `-m module`
        if not script.startswith("-m"):
            return f"❌ Не Python файл: {script}"

    cmd = f"cd {WORKSPACE} && python {script} {args}"
    log.debug("bash.python", script=script, args=args)

    result = await execute_shell_command(cmd, timeout=60)
    return format_command_result(result)

@mcp.tool()
async def git_operation(operation: str, path: str = ".", args: str = "") -> str:
    """
    Выполняет команды контроля версий Git в указанной директории.

    ИСПОЛЬЗУЙ ДЛЯ:
    - Просмотра изменений (status, diff)
    - Просмотра истории (log)
    - Информации о ветках (branch)

    Args:
        operation (str): Тип операции. Доступные значения:
            - 'status': Статус изменений (Modified, Untracked files)
            - 'log': История коммитов (последние 10)
            - 'diff': Различия между версиями
            - 'branch': Список веток
            - 'pull': Получение изменений из удаленного репозитория
        path (str): Относительный путь к репозиторию (по умолчанию '.').
        args (str): Дополнительные флаги git (напр., '--graph' для log).
    """
    repo_path = os.path.join(WORKSPACE, path.strip())

    if not os.path.exists(repo_path):
        return f"❌ Путь не существует: {path}"

    operations = {
        "status": "status -s",
        "pull": "pull",
        "log": "log --oneline -10",
        "diff": "diff HEAD~1",
        "branch": "branch -a",
        "remote": "remote -v"
    }

    if operation not in operations:
        available = ", ".join(operations.keys())
        return f"❌ Неизвестная операция. Доступно: {available}"

    cmd = f"cd {repo_path} && git {operations[operation]} {args}"
    log.debug("bash.git", operation=operation, path=path)

    result = await execute_shell_command(cmd, timeout=30)

    if result["success"]:
        output = result["stdout"] or "✅ Операция выполнена (нет вывода)"
        return f"🔧 Git {operation}:\n\n{output}"
    else:
        error = result["stderr"] or "Неизвестная ошибка Git"
        # Часто ошибка Git 'not a git repository' приходит в stderr
        return f"❌ Ошибка Git {operation}:\n{error}"

# ==================== ЗАПУСК СЕРВЕРА ====================
if __name__ == "__main__":
    log.info("mcp_bash.start", host=HOST, port=PORT, workspace=WORKSPACE)

    # Instrument the FastAPI app if possible
    try:
        from infra.metrics import metrics_manager
        if metrics_manager.is_enabled():
            try:
                # Try to access internal FastAPI app (fastmcp v2+)
                if hasattr(mcp, 'app'):
                    metrics_manager.instrument_fastapi(mcp.app)
                else:
                    log.warning("Could not find FastAPI app to instrument in FastMCP")
            except Exception as e:
                log.warning(f"Failed to instrument FastMCP app: {e}")
    except ImportError:
        pass

    mcp.run(
        transport="http",
        host=HOST,
        port=PORT,
        log_level="info"
    )
