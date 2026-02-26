"""
Module Summary Aggregation Stage.

Aggregates file summaries within a module (directory) and generates a module-level summary.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any

from ingestor.adapters import BaseStorage
from ingestor.core.models.module_summary import ModuleSummary
from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.pipeline_file_context import PipelineFileContext
from ingestor.services.summary_generator import SummaryGenerator
from infra.logger import get_logger


class ModuleSummaryStage(ProcessorStage):
    """
    Aggregates file summaries to create module-level summaries.
    
    A module is typically a directory containing related files.
    This stage runs after all files in a directory have been processed.
    """
    
    def __init__(
        self,
        storage: BaseStorage,
        workspace_path: Path,
        llm,  # LLM instance
        lock_manager,  # LLMLockManager
        max_workers: int = 2
    ):
        super().__init__("module_summary", max_workers)
        self.storage = storage
        self.workspace_path = Path(workspace_path)
        self.summary_generator = SummaryGenerator(llm, lock_manager)
        self.log = get_logger("ingestor.module_summary_stage")
    
    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        """
        Process a file and update module summaries as needed.
        
        For simplicity, we'll generate/update module summary for the file's parent directory
        whenever a file is processed (after file_summary stage).
        """
        file_path = str(context.file_path)
        
        # Skip on delete or errors
        if context.event_type == "delete" or context.has_errors:
            return context
        
        try:
            # Determine module path (parent directory)
            path_obj = Path(file_path)
            if len(path_obj.parts) <= 1:
                # File at root, no module
                return context
            
            module_path = str(path_obj.parent)
            
            # Get all file summaries for this module (all files in directory)
            all_summaries = await self.storage.get_all_file_summaries()
            module_file_summaries = [
                {"file_path": fs.file_path, "summary": fs.summary}
                for fs in all_summaries
                if fs.file_path.startswith(module_path + "/") and fs.summary
            ]
            
            if not module_file_summaries:
                # No valid file summaries yet for this module
                return context
            
            # Generate module summary
            module_summary_text = await self.summary_generator.generate_module_summary(
                file_summaries=module_file_summaries
            )
            
            if not module_summary_text:
                return context
            
            # Save module summary
            module_summary = ModuleSummary(
                module_path=module_path,
                summary=module_summary_text,
                file_paths=[fs["file_path"] for fs in module_file_summaries],
                metadata={
                    "file_count": len(module_file_summaries),
                }
            )
            
            await self.storage.save_module_summary(module_summary)
            self.log.info(f"ModuleSummary updated: {module_path} (files={len(module_file_summaries)})")
            
        except Exception as e:
            self.log.error(f"Error in ModuleSummaryStage for {file_path}: {e}", exc_info=True)
        
        return context
