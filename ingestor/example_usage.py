"""
Example usage of Ingestor components.

Демонстрирует как использовать ingestor программно
(без запуска полного HTTP сервера).
"""

import asyncio
import os
from pathlib import Path

from infra.logger import setup_logging, get_logger
from ingestor.adapters.memory.storage import MemoryStorage as InMemoryStorage
from infra.managers.llm import LLMManager
from ingestor.services.lock import LLMLockManager
from ingestor.services.knowledge import KnowledgePort
from ingestor.pipeline.impl.orchestrator import PipelineOrchestrator


log = get_logger("example_usage")

async def example_basic_pipeline():
    """
    Пример: запуск базового pipeline без embeddings.
    """
    setup_logging()
    log = get_logger("example")
    
    log.info("example.basic_pipeline.start", workspace=str(Path(__file__).parent.parent))
    
    # Компоненты
    llm = LLMManager(
        api_base=os.environ.get("OPENAI_API_BASE", "http://localhost:8000/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", "dummy"),
        model_name="default-model"
    )
    lock_manager = LLMLockManager()
    storage = InMemoryStorage()
    
    # Pipeline без embeddings
    pipeline = PipelineOrchestrator(
        workspace_path=str(Path(__file__).parent.parent),
        llm=llm,
        lock_manager=lock_manager,
        storage=storage,
        embed_url="http://emb:8001/v1",
        embed_api_key="sk-dummy",
    )
    
    # Запускаем LLM reconnect
    await llm.initialize()
    
    # Ждём готовности
    log.info("example.basic_pipeline.waiting_for_llm")
    await llm.wait_ready()
    
    # Запускаем pipeline
    log.info("example.basic_pipeline.running")
    await pipeline.run_full_pipeline()
    
    # Статистика
    stats = await storage.get_stats()
    log.info("example.basic_pipeline.complete", stats=stats)
    
    return storage


async def example_knowledge_port(storage: InMemoryStorage):
    """
    Пример: использование Knowledge Port.
    """
    log = get_logger("example")
    
    log.info("example.knowledge_port.start")
    
    knowledge_port = KnowledgePort(storage)
    
    # Получаем обзор проекта
    overview = await knowledge_port.get_project_overview()
    log.info("example.knowledge_port.overview", stats=overview["stats"])
    
    # Получаем контекст файла (если есть)
    chunks = await storage.get_all_chunks()
    if chunks:
        first_file = chunks[0].file_path
        context = await knowledge_port.get_file_context(first_file)
        log.info(
            "example.knowledge_port.file_context",
            file=first_file,
            chunks_count=len(context["chunks"]),
        )


async def example_llm_lock():
    """
    Пример: управление LLM lock.
    """
    log = get_logger("example")
    
    log.info("example.llm_lock.start")
    
    lock_manager = LLMLockManager()
    
    # Устанавливаем блокировку
    await lock_manager.set_lock(locked=True, ttl_seconds=10)
    status = lock_manager.get_status()
    log.info("example.llm_lock.set", status=status)
    
    # Проверяем блокировку
    is_locked = await lock_manager.is_locked()
    log.info("example.llm_lock.is_locked", locked=is_locked)
    
    # Ждём разблокировки (с timeout)
    log.info("example.llm_lock.waiting_for_unlock", timeout_seconds=11)
    await asyncio.sleep(11)  # Ждём истечения TTL
    
    is_locked = await lock_manager.is_locked()
    log.info("example.llm_lock.after_ttl", locked=is_locked)
    
    # Разблокируем вручную
    await lock_manager.set_lock(locked=False)
    status = lock_manager.get_status()
    log.info("example.llm_lock.released", status=status)


async def main():
    """
    Запускает все примеры.
    """
    # Настраиваем окружение
    os.environ.setdefault("OPENAI_API_BASE", "http://localhost:8000/v1")
    os.environ.setdefault("OPENAI_API_KEY", "dummy")
    
    try:
        # 1. LLM Lock
        await example_llm_lock()
        
        # 2. Basic Pipeline (закомментировано, т.к. требует LLM)
        # storage = await example_basic_pipeline()
        
        # 3. Knowledge Port (закомментировано, т.к. требует storage)
        # await example_knowledge_port(storage)
        
        log.info("example.completed", status="success")
        
    except Exception as e:
        log.error("example.failed", error=str(e), exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
