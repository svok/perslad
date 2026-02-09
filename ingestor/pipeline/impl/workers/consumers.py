"""
Consumers for pipeline stages.
"""

import asyncio
from infra.logger import get_logger
from ingestor.pipeline.impl.workers.collector import EnrichCollector

log = get_logger("ingestor.pipeline.consumers")

class PipelineConsumers:
    def __init__(self, parse_stage, enrich_stage, embed_stage):
        self.parse_stage = parse_stage
        self.enrich_stage = enrich_stage
        self.embed_stage = embed_stage

    async def parse_enrich_consumer(self, files_queue: asyncio.Queue, enriched_queue: asyncio.Queue) -> None:
        log.info("parse_enrich_consumer.starting")
        enriched_count = 0
        sentinel_received = False
        files_processed = 0

        while True:
            log.info("parse_enrich_consumer.waiting_for_file")
            file = await files_queue.get()

            files_processed += 1
            log.info("parse_enrich_consumer.received_file", 
                     file_name=file.relative_path if hasattr(file, 'relative_path') else str(file)[:50], 
                     files_processed=files_processed)
            if file is None:
                sentinel_received = True
                log.info("parse_enrich_consumer.received_sentinel")
                break

            chunks = await self.parse_stage.run([file])

            if not chunks:
                continue

            enriched = await self.enrich_stage.run(chunks)
            enriched_count += len(enriched)

            for i, chunk in enumerate(enriched):
                await enriched_queue.put(chunk)

        if sentinel_received:
            log.info("parse_enrich_consumer.send_enriched_sentinel", total_enriched=enriched_count)
            await enriched_queue.put(None)
        log.info("parse_enrich_consumer.finished", total_enriched=enriched_count, sentinel_received=sentinel_received, files_processed=files_processed)

    async def embed_consumer(self, enriched_queue: asyncio.Queue, embedded_queue: asyncio.Queue) -> None:
        log.info("embed_consumer.starting")
        if not self.embed_stage:
            log.warning("embed_stage.not_configured, skipping embeddings")
            while True:
                chunk = await enriched_queue.get()
                await embedded_queue.put(chunk)
                if chunk is None:
                    break
            return

        embedded_count = 0
        total_enriched = 0

        while True:
            chunk = await enriched_queue.get()
            if chunk is None:
                log.info("embed_consumer.received_sentinel", total_enriched=total_enriched)
                break

            total_enriched += 1

            try:
                log.info("embed_consumer.processing", chunk_id=chunk.id[:20], file_path=chunk.file_path[:50] if chunk.file_path else None)
                await self.embed_stage.run([chunk])
                embedded_count += 1
                log.info("embed_consumer.embedded", chunk_id=chunk.id[:20], embedded=embedded_count)
            except Exception as e:
                log.error("embed_consumer.embedding_failed", chunk_id=chunk.id[:20], error=str(e))
                embedded_count += 1

            await embedded_queue.put(chunk)

        log.info("embed_consumer.finished", embedded=embedded_count, total_enriched=total_enriched)

    async def save_consumer(self, queue: asyncio.Queue, collector: EnrichCollector) -> None:
        log.info("save_consumer.starting")
        enriched_chunks_passed = 0
        chunks_sent = 0

        while True:
            chunk = await queue.get()
            if chunk is None:
                log.info("save_consumer.received sentinel")
                break

            enriched_chunks_passed += 1
            await collector.add(chunk)
            chunks_sent += 1

        log.info("save_consumer.finished", enriched_chunks_passed=enriched_chunks_passed, chunks_sent=chunks_sent)
        await collector.wait_done()
