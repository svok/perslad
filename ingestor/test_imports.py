"""
Simple import test to verify all modules load correctly.
"""

import sys

from infra.logger import setup_logging, get_logger

# Настройка логирования для теста
setup_logging(env="test")
log = get_logger("test_imports")


def test_imports():
    """Test that all ingestor modules can be imported."""
    
    log.info("test_imports.start")
    
    try:
        # Core modules
        from ingestor.config import runtime
        log.info("test_imports.success", module="runtime")
        
        from ingestor.adapters.postgres import storage
        log.info("test_imports.success", module="storage")
        
        from ingestor.services import lock
        log.info("test_imports.success", module="lock")
        
        from ingestor.services import knowledge
        log.info("test_imports.success", module="knowledge")
        
        from ingestor.api.requests import llm_lock_request
        log.info("test_imports.success", module="api")
        
        # Pipeline stages
        from ingestor.pipeline.impl import scan
        log.info("test_imports.success", module="pipeline.scan")
        
        from ingestor.pipeline.impl import parse
        log.info("test_imports.success", module="pipeline.parse")
        
        from ingestor.pipeline.impl import enrich
        log.info("test_imports.success", module="pipeline.enrich")
        
        from ingestor.pipeline.impl import embed
        log.info("test_imports.success", module="pipeline.embed")
        
        from ingestor.pipeline.impl import persist
        log.info("test_imports.success", module="pipeline.persist")
        
        from ingestor.pipeline.impl import orchestrator
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
