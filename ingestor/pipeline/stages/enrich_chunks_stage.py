"""
Enriches TextNode objects with LLM-generated metadata.

Adds summary and purpose to node.metadata.
"""

import asyncio
from typing import List

from llama_index.core.schema import TextNode
from llama_index.core.llms import LLM

from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.services.lock import LLMLockManager
from ingestor.services.smart_llm import SmartLLMService

ENRICHMENT_PROMPT_TEMPLATE = """Analyze this code/documentation chunk and provide:

1. SUMMARY: 1-2 sentences describing what this code does
2. PURPOSE: The likely purpose of this code in the project

Text chunk:
{content}

Respond in this exact format:
SUMMARY: <your summary>
PURPOSE: <your purpose>

Keep it concise and factual."""


class EnrichChunksStage(ProcessorStage):
    """
    Enriches TextNode objects with LLM-generated metadata.
    """
    
    def __init__(self, llm: LLM, lock_manager: LLMLockManager, max_workers: int = 2, enable_thinking: bool = False):
        super().__init__("chunk_enrich", max_workers)
        self._llm_service = SmartLLMService(llm, max_workers=max_workers)
        self.lock_manager = lock_manager
        self._semaphore = asyncio.Semaphore(max_workers)
        self._enable_thinking = enable_thinking
    
    async def process(self, context):
        """Process file context and enrich nodes."""
        if not context.nodes:
            return context
        
        # Check LLM lock
        if await self.lock_manager.is_locked():
            self.log.info("enrich.waiting_for_llm_unlock", file_path=context.file_path)
            await self.lock_manager.wait_unlocked()
        
        # Enrich all nodes
        await self._enrich_nodes(context.nodes)
        
        return context
    
    async def _enrich_nodes(self, nodes: List[TextNode]) -> None:
        """Enrich multiple nodes with LLM, respecting semaphore."""
        tasks = []
        for node in nodes:
            task = self._enrich_node_with_semaphore(node)
            tasks.append(task)
        
        # Gather with return_exceptions to handle failures gracefully
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.log.error("enrich.node.failed", node_index=i, error=str(result))
    
    async def _enrich_node_with_semaphore(self, node: TextNode) -> None:
        """Enrich single node with semaphore protection."""
        async with self._semaphore:
            await self._enrich_node(node)
    
    async def _enrich_node(self, node: TextNode) -> None:
        """Enrich a single TextNode with summary and purpose."""
        text = node.text
        if not text or not text.strip():
            node.metadata["summary"] = ""
            node.metadata["purpose"] = ""
            return

        prompt = ENRICHMENT_PROMPT_TEMPLATE.format(content=text[:2000])

        try:
            response_text = await self._llm_service.complete(
                prompt,
                max_tokens=500,
                enable_thinking=self._enable_thinking,
            )
            self.log.debug("enrich.raw_response", response=response_text)

            summary, purpose = self._parse_llm_response(response_text)

            if not summary:
                summary = text[:100]
            if not purpose:
                purpose = "generated from content"

            node.metadata["summary"] = summary
            node.metadata["purpose"] = purpose

        except Exception as e:
            self.log.warning("enrich.llm.failed", text_preview=text[:100], error=str(e))
            node.metadata["summary"] = text[:100]
            node.metadata["purpose"] = "content excerpt"
    
    def _parse_llm_response(self, response: str) -> tuple[str, str]:
        """Parse LLM response to extract summary and purpose."""
        lines = response.strip().split('\n')
        summary_lines = []
        purpose_lines = []
        in_summary = False
        in_purpose = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            line_lower = line.lower()
            if line_lower.startswith("summary:"):
                in_summary = True
                in_purpose = False
                summary_text = line[8:].strip()
                if summary_text:
                    summary_lines.append(summary_text)
            elif line_lower.startswith("purpose:"):
                in_purpose = True
                in_summary = False
                purpose_text = line[8:].strip()
                if purpose_text:
                    purpose_lines.append(purpose_text)
            elif in_summary and not line_lower.startswith("purpose:"):
                summary_lines.append(line)
            elif in_purpose:
                purpose_lines.append(line)
        
        summary = " ".join(summary_lines) if summary_lines else ""
        purpose = " ".join(purpose_lines) if purpose_lines else ""
        
        return summary, purpose
