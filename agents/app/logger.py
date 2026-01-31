# FILE: agentnet/agents/app/logger.py
import logging
import sys

def setup_logging():
    """Настройка централизованного логирования."""
    logger = logging.getLogger("agentnet")
    logger.setLevel(logging.INFO)

    # Очищаем существующие обработчики
    logger.handlers.clear()

    # Консольный обработчик
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)

    # Формат без временных меток (Docker добавит свои)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Отключаем логирование от внешних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    return logger

# Глобальный логгер
logger = setup_logging()
