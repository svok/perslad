"""
Stage 3: Chunk Enrichment

Задача: обогатить каждый чанк кратким объяснением.
USES LOCAL LLM.

Уважает LLM lock от агента.
"""

from typing import List
import asyncio

from infra.logger import get_logger
from infra.llm import LLMClient
from ingestor.app.storage import Chunk
from ingestor.app.llm_lock import LLMLockManager

log = get_logger("ingestor.pipeline.enrich")


ENRICHMENT_PROMPT_TEMPLATE = """You are analyzing a code/documentation chunk.

File: {file_path}
Type: {chunk_type}

Content:
```
{content}
```

Provide a brief analysis:
1. Summary (1-2 sentences)
2. Purpose (what does it do?)

Keep it concise and factual.
"""


class EnrichStage:
    """
    Обогащает чанки с помощью локальной LLM.
    """

    def __init__(
        self,
        llm: LLMClient,
        lock_manager: LLMLockManager,
    ) -> None:
        self.llm = llm
        self.lock_manager = lock_manager

    async def run(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Обогащает чанки summaries с параллелизмом.
        """
        log.info("enrich.start", chunks_count=len(chunks))
        
        enriched = 0
        skipped = 0
        
        # Process chunks in batches to respect LLM lock
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            
            log.info("enrich.batch.start", batch_num=batch_num, total_batches=total_batches, batch_size=len(batch))
            
            # Check lock once per batch
            if await self.lock_manager.is_locked():
                log.info("enrich.llm_locked.waiting")
                await self.lock_manager.wait_unlocked()
            
            tasks = [self._enrich_chunk(chunk) for chunk in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for chunk, result in zip(batch, results):
                if isinstance(result, Exception):
                    log.error(
                        "enrich.chunk.failed",
                        chunk_id=chunk.id,
                        error=str(result),
                        file_path=chunk.file_path[:50] if chunk.file_path else None
                    )
                    skipped += 1
                else:
                    enriched += 1
            
            log.info("enrich.batch.complete", batch_num=batch_num, enriched_in_batch=len(batch) - skipped)
        
        log.info(
            "enrich.complete",
            enriched=enriched,
            skipped=skipped,
        )
        
        return chunks

    async def _enrich_chunk(self, chunk: Chunk) -> None:
        """
        Обогащает один чанк.
        """
        # Формируем prompt
        prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
            file_path=chunk.file_path,
            chunk_type=chunk.chunk_type,
            content=chunk.content[:1000],  # Ограничиваем для локальной LLM
        )
        
        # Вызываем LLM
        async def _call(model):
            response = await model.ainvoke(prompt)
            return response.content
        
        result = await self.llm.call_raw(_call)
        
        # Парсим результат (упрощённо)
        # В production можно использовать structured output
        lines = result.strip().split("\n")
        
        summary_lines = []
        purpose_lines = []
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if "summary" in line.lower():
                current_section = "summary"
                continue
            elif "purpose" in line.lower():
                current_section = "purpose"
                continue
            
            if current_section == "summary":
                summary_lines.append(line)
            elif current_section == "purpose":
                purpose_lines.append(line)
        
        chunk.summary = " ".join(summary_lines) if summary_lines else result[:200]
        chunk.purpose = " ".join(purpose_lines) if purpose_lines else None
        
        log.debug("enrich.chunk.complete", chunk_id=chunk.id)
