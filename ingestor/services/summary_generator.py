"""
Summary Generation Service using LLM.

Provides file summarization and module aggregation with caching and rate limiting.
"""

import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from llama_index.core.llms import LLM
from infra.logger import get_logger
from ingestor.services.lock import LLMLockManager


logger = get_logger("ingestor.summary")


# === Prompts ===

FILE_SUMMARY_PROMPT = """Summarize this file in 1-2 sentences, focusing on its purpose and key functionality.

File content:
{content}

Guidelines:
- Be concise and factual
- Mention the main purpose
- Note key functions/classes if relevant
- Avoid generic statements

Respond with only the summary text, no labels."""

MODULE_SUMMARY_PROMPT = """Create a concise module-level summary based on these file summaries:

{file_summaries}

Guidelines:
- 2-3 sentences describing the module's overall purpose
- Mention key components and their relationships
- Be factual and avoid generic statements

Respond with only the summary text, no labels."""


# === Caching ===

@dataclass
class SummaryCache:
    """Simple in-memory cache for file summaries."""
    _cache: Dict[str, str] = None  # key: content_hash -> summary
    
    def __post_init__(self):
        if self._cache is None:
            self._cache = {}
    
    def get(self, content_hash: str) -> Optional[str]:
        return self._cache.get(content_hash)
    
    def set(self, content_hash: str, summary: str) -> None:
        self._cache[content_hash] = summary
    
    def clear(self) -> None:
        self._cache.clear()


class SummaryGenerator:
    """
    Generates file and module summaries using LLM with caching and rate limiting.
    
    This service is used by FileSummaryStage and ModuleSummaryStage.
    """
    
    def __init__(self, llm: LLM, lock_manager: LLMLockManager):
        self.llm = llm
        self.lock_manager = lock_manager
        self.log = get_logger("ingestor.summary_generator")
        self._cache = SummaryCache()
    
    async def generate_file_summary(
        self, 
        content: str, 
        metadata: Dict[str, Any],
        use_cache: bool = True
    ) -> str:
        """
        Generate a concise summary for a file.
        
        Args:
            content: Full file content (or concatenated chunks)
            metadata: File metadata (extension, chunk_type, etc.)
            use_cache: Whether to use cached result if available
            
        Returns:
            Generated summary string (1-2 sentences)
        """
        # Create cache key from content hash
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        
        if use_cache:
            cached = self._cache.get(content_hash)
            if cached:
                self.log.debug("summary.cache_hit", content_hash=content_hash)
                return cached
        
        # Wait for LLM lock if needed
        if await self.lock_manager.is_locked():
            self.log.info("summary.waiting_for_llm_unlock")
            await self.lock_manager.wait_unlocked()
        
        # Generate summary
        prompt = FILE_SUMMARY_PROMPT.format(content=content[:4000])  # Limit content length
        
        try:
            response = await self.llm.acomplete(prompt)
            summary = response.text.strip()
            
            # Cache the result
            self._cache.set(content_hash, summary)
            self.log.debug("summary.generated", content_hash=content_hash, summary_length=len(summary))
            
            return summary
        except Exception as e:
            self.log.error("summary.generation_failed", error=str(e))
            return ""  # Return empty summary on failure
    
    async def generate_module_summary(
        self, 
        file_summaries: List[Dict[str, Any]],
        use_cache: bool = True
    ) -> str:
        """
        Aggregate multiple file summaries into a module-level summary.
        
        Args:
            file_summaries: List of dicts with 'file_path' and 'summary' keys
            use_cache: Whether to use cached result
            
        Returns:
            Module summary string (2-3 sentences)
        """
        if not file_summaries:
            return ""
        
        # Create cache key from sorted file paths
        paths_sorted = sorted(fs['file_path'] for fs in file_summaries if fs.get('summary'))
        cache_key = hashlib.md5("|".join(paths_sorted).encode()).hexdigest()[:16]
        
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached:
                self.log.debug("module_summary.cache_hit", cache_key=cache_key)
                return cached
        
        # Wait for LLM lock
        if await self.lock_manager.is_locked():
            self.log.info("module_summary.waiting_for_llm_unlock")
            await self.lock_manager.wait_unlocked()
        
        # Format file summaries for prompt
        summaries_text = "\n".join([
            f"File: {fs['file_path']}\nSummary: {fs.get('summary', 'N/A')}\n"
            for fs in file_summaries if fs.get('summary')
        ])
        
        if not summaries_text:
            return ""
        
        prompt = MODULE_SUMMARY_PROMPT.format(file_summaries=summaries_text[:8000])
        
        try:
            response = await self.llm.acomplete(prompt)
            summary = response.text.strip()
            
            # Cache result
            self._cache.set(cache_key, summary)
            self.log.debug("module_summary.generated", cache_key=cache_key, summary_length=len(summary))
            
            return summary
        except Exception as e:
            self.log.error("module_summary.generation_failed", error=str(e))
            return ""
    
    def clear_cache(self) -> None:
        """Clear the summary cache."""
        self._cache.clear()
        self.log.info("summary.cache_cleared")