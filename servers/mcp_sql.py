#!/usr/bin/env python3
"""
MCP SQL Server для работы с базами данных StarRocks/PostgreSQL
Реализует Streamable HTTP транспорт согласно спецификации MCP
"""

import asyncio
import json
import uuid
import os
import structlog
from typing import AsyncGenerator, Dict, Any, List, Tuple

from mcp.server import Server
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
import uvicorn
import aiomysql

# Настройка логирования с JSON форматом
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(structlog.stdlib.filtering.WARNING),
    cache_logger_on_first_use=True,
)
log = structlog.get_logger("mcp_sql")

# ============================================
# 1. ИНИЦИАЛИЗАЦИЯ MCP СЕРВЕРА
# ============================================
app = Server("mcp-sql")

# ============================================
# 2. БИЗНЕС-ЛОГИКА: РАБОТА С БАЗАМИ ДАННЫХ
# ============================================

# Конфигурация подключения
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", ""),
    "database": os.getenv("DB_NAME", ""),
    "autocommit": False,
    "charset": "utf8mb4"
}

async def get_connection():
    """Создает асинхронное подключение к базе данных."""
    try:
        return await aiomysql.connect(**DB_CONFIG)
    except Exception as e:
        raise Exception(f"Ошибка подключения к БД: {str(e)}")

async def execute_sql_query(connection, sql: str) -> Tuple[List[Tuple], List[str]]:
    """Выполняет SQL запрос и возвращает результаты и метаданные."""
    cursor = None
    try:
        cursor = await connection.cursor()
        await cursor.execute(sql)

        if sql.strip().lower().startswith("select"):
            rows = await cursor.fetchall()
            # Получаем имена колонок
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
            else:
                columns = []
            return rows, columns
        else:
            await connection.commit()
            return [], ["affected_rows", "last_insert_id"]

    except Exception as e:
        await connection.rollback()
        raise e
    finally:
        if cursor:
            await cursor.close()

def format_query_results(rows: List[Tuple], columns: List[str]) -> str:
    """Форматирует результаты SQL запроса для читаемого вывода."""
    if not rows:
        return "📭 Запрос не вернул данных"

    result_lines = []

    if columns:
        # Форматируем заголовки таблицы
        header = " | ".join(columns)
        separator = "-" * len(header)
        result_lines.append(header)
        result_lines.append(separator)

    # Форматируем строки
    for row in rows[:100]:  # Ограничиваем вывод 100 строками
        row_str = " | ".join(str(cell) if cell is not None else "NULL" for cell in row)
        result_lines.append(row_str)

    if len(rows) > 100:
        result_lines.append(f"\n📊 ... и еще {len(rows) - 100} строк")

    result_lines.append(f"\n✅ Всего строк: {len(rows)}")

    return "\n".join(result_lines)

@app.list_tools()
async def list_tools() -> list[Tool]:
    """Возвращает список доступных инструментов для работы с БД."""
    return [
        Tool(
            name="execute_query",
            description="Выполняет SQL запрос к базе данных StarRocks/PostgreSQL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL запрос для выполнения (SELECT, INSERT, UPDATE, DELETE, CREATE, etc.)"
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="list_tables",
            description="Показывает список таблиц в базе данных.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "description": "Имя схемы/базы данных (по умолчанию используется текущая БД)",
                        "default": ""
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="describe_table",
            description="Показывает структуру таблицы (колонки, типы, ограничения).",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Имя таблицы для описания"
                    }
                },
                "required": ["table_name"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Обрабатывает вызовы инструментов для работы с базой данных."""

    try:
        if name == "execute_query":
            sql = arguments["sql"].strip()
            if not sql:
                return [TextContent(
                    type="text",
                    text="❌ Ошибка: SQL запрос не может быть пустым"
                )]

            connection = await get_connection()
            try:
                rows, columns = await execute_sql_query(connection, sql)

                if sql.lower().startswith("select"):
                    formatted_results = format_query_results(rows, columns)
                    response = f"✅ Результаты запроса:\n\n{formatted_results}"
                else:
                    # Для не-SELECT запросов
                    response = f"✅ Запрос выполнен успешно\n\n📝 Запрос: {sql}"

                return [TextContent(type="text", text=response)]

            finally:
                await connection.close()

        elif name == "list_tables":
            schema = arguments.get("schema", "")
            connection = await get_connection()
            try:
                cursor = await connection.cursor()

                if schema:
                    await cursor.execute(f"SHOW TABLES FROM `{schema}`")
                else:
                    await cursor.execute("SHOW TABLES")

                tables = await cursor.fetchall()

                if tables:
                    table_list = "\n".join([f"• {table[0]}" for table in tables])
                    response = f"📋 Таблицы в базе данных:\n\n{table_list}\n\nВсего таблиц: {len(tables)}"
                else:
                    response = "📭 В базе данных нет таблиц"

                return [TextContent(type="text", text=response)]

            finally:
                await connection.close()

        elif name == "describe_table":
            table_name = arguments["table_name"]
            connection = await get_connection()
            try:
                cursor = await connection.cursor()

                # Получаем структуру таблицы
                await cursor.execute(f"DESCRIBE `{table_name}`")
                columns = await cursor.fetchall()

                if columns:
                    column_info = []
                    for col in columns:
                        col_name = col[0]
                        col_type = col[1]
                        col_null = "NULL" if col[2] == "YES" else "NOT NULL"
                        col_key = col[3] if col[3] else ""
                        col_default = col[4] if col[4] else "NULL"
                        col_extra = col[5] if col[5] else ""

                        column_info.append(
                            f"• {col_name}: {col_type} ({col_null}) "
                            f"[Key: {col_key}, Default: {col_default}, Extra: {col_extra}]"
                        )

                    response = f"📊 Структура таблицы '{table_name}':\n\n" + "\n".join(column_info)
                else:
                    response = f"❌ Таблица '{table_name}' не найдена или не имеет колонок"

                return [TextContent(type="text", text=response)]

            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"❌ Ошибка при описании таблицы: {str(e)}"
                )]
            finally:
                await connection.close()

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"❌ Ошибка выполнения инструмента '{name}': {str(e)}"
        )]

    return [TextContent(type="text", text="❌ Неизвестный инструмент")]

# ============================================
# 3. ТРАНСПОРТ: STREAMABLE HTTP
# ============================================

_sessions: Dict[str, Dict[str, Any]] = {}

async def handle_sse_get(request: Request) -> StreamingResponse:
    """GET /mcp - устанавливает SSE соединение по спецификации MCP."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "created_at": asyncio.get_event_loop().time(),
        "client_info": dict(request.headers)
    }

    async def event_generator() -> AsyncGenerator[str, None]:
        """Генератор событий SSE."""
        try:
            # 1. Отправляем обязательное endpoint событие
            endpoint_data = {
                "uri": f"http://127.0.0.1:8082/mcp",
                "sessionId": session_id
            }
            yield f"event: endpoint\ndata: {json.dumps(endpoint_data)}\n\n"

            # 2. Отправляем событие server_ready
            yield f"event: server_ready\ndata: {{}}\n\n"

            # 3. Поддерживаем соединение
            while True:
                await asyncio.sleep(30)
                yield ": ping\n\n"

        except asyncio.CancelledError:
            if session_id in _sessions:
                del _sessions[session_id]
        except Exception as e:
            log.error("sse.error", session_id=session_id, error=str(e))
            if session_id in _sessions:
                del _sessions[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

async def handle_post(request: Request) -> JSONResponse:
    """POST /mcp - обработка JSON-RPC запросов."""
    try:
        body_bytes = await request.body()

        try:
            request_data = json.loads(body_bytes)
        except json.JSONDecodeError:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error: Invalid JSON"
                }
            }, status_code=400)

        if not isinstance(request_data, dict) or request_data.get("jsonrpc") != "2.0":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_data.get("id") if isinstance(request_data, dict) else None,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: Not JSON-RPC 2.0"
                }
            }, status_code=400)

        session_id = request.headers.get("mcp-session-id")
        if session_id and session_id in _sessions:
            request_data["session_id"] = session_id

        try:
            response_data = await app.handle_request(request_data)
        except Exception as e:
            log.error("mcp.handle_request.error", error=str(e))
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status_code=500)

        headers = {}
        if session_id:
            headers["mcp-session-id"] = session_id

        return JSONResponse(response_data, headers=headers)

    except Exception as e:
        log.error("http.post.error", error=str(e))
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": "Internal server error"
            }
        }, status_code=500)

# ============================================
# 4. СОЗДАНИЕ И ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================

starlette_app = Starlette(
    debug=False,
    routes=[
        Route("/mcp", endpoint=handle_sse_get, methods=["GET"]),
        Route("/mcp", endpoint=handle_post, methods=["POST"]),
        Route("/health", endpoint=lambda r: JSONResponse({
            "status": "ok",
            "service": "mcp-sql",
            "db_config": {k: "***" if k == "password" else v for k, v in DB_CONFIG.items()}
        }), methods=["GET"]),
    ]
)

if __name__ == "__main__":
    log.info("mcp_sql.start", port=8082, db_host=DB_CONFIG['host'], db_port=DB_CONFIG['port'])

    config = uvicorn.Config(
        app=starlette_app,
        host="127.0.0.1",
        port=8082,
        log_level="info",
        access_log=True,
        timeout_keep_alive=300,
    )

    server = uvicorn.Server(config)

    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        log.info("mcp_sql.shutdown", reason="keyboard_interrupt")
    except Exception as e:
        log.error("mcp_sql.start.failed", error=str(e))
        exit(1)
