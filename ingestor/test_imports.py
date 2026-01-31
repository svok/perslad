"""
Simple import test to verify all modules load correctly.
"""

import sys
import logging

from infra.logger import setup_logging, get_logger

# Настройка логирования для теста
setup_logging(env="test")
log = get_logger("test_imports")


def test_imports():
    """Test that all ingestor modules can be imported."""
    
    log.info("test_imports.start")
    
    try:
        # Core modules
        from ingestor.app import config
        log.info("test_imports.success", module="config")
        
        from ingestor.app import storage
        log.info("test_imports.success", module="storage")
        
        from ingestor.app import llm_lock
        log.info("test_imports.success", module="llm_lock")
        
        from ingestor.app import knowledge_port
        log.info("test_imports.success", module="knowledge_port")
        
        from ingestor.app import api
        log.info("test_imports.success", module="api")
        
        # Pipeline stages
        from ingestor.app.pipeline import scan
        log.info("test_imports.success", module="pipeline.scan")
        
        from ingestor.app.pipeline import parse
        log.info("test_imports.success", module="pipeline.parse")
        
        from ingestor.app.pipeline import enrich
        log.info("test_imports.success", module="pipeline.enrich")
        
        from ingestor.app.pipeline import embed
        log.info("test_imports.success", module="pipeline.embed")
        
        from ingestor.app.pipeline import persist
        log.info("test_imports.success", module="pipeline.persist")
        
        from ingestor.app.pipeline import orchestrator
        log.info("test_imports.success", module="pipeline.orchestrator")
        
        # Adapters
        from ingestor.adapters import llama_llm
        log.info("test_imports.success", module="adapters.llama_llm")
        
        log.info("test_imports.complete", status="success", modules_count=12)
        return True
        
    except Exception as e:
        log.error("test_imports.failed", error=str(e), exc_info=True)
        return False


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
