"""
Module Summary Aggregation Stage.

Aggregates file summaries within a module (directory) and generates a module-level summary.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

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
        Process a file and generate/update module summaries.
        
        A module is a directory containing __init__.py indicating it's a Python package.
        """
        file_path = str(context.file_path)

        # Skip on delete or errors
        if context.event_type == "delete" or context.has_errors:
            return context

        try:
            # Determine module path using discovery algorithm
            module_path = self._discover_module(file_path)
            if not module_path:
                self.log.debug(f"No module found for file: {file_path}")
                return context

            # Get file summaries for this module
            module_file_summaries = await self._get_module_file_summaries(module_path)

            if not module_file_summaries:
                # No valid file summaries yet for this module
                return context

            # Generate module summary using aggregated file summaries
            module_summary_text = await self.summary_generator.generate_module_summary(
                file_summaries=module_file_summaries
            )

            if not module_summary_text:
                return context

            # Save module summary with timestamp
            module_summary = ModuleSummary(
                module_path=module_path,
                summary=module_summary_text,
                file_paths=[fs.file_path for fs in module_file_summaries],
                metadata={
                    "file_count": len(module_file_summaries),
                    "last_summarized_at": asyncio.get_running_loop().time(),
                }
            )

            await self.storage.save_module_summary(module_summary)
            self.log.info(f"ModuleSummary updated: {module_path} (files={len(module_file_summaries)})")

        except Exception as e:
            self.log.error(f"Error in ModuleSummaryStage for {file_path}: {e}", exc_info=True)

        return context

    def _discover_module(self, file_path: str) -> Optional[str]:
        """
        Discover module path using __init__.py detection.
        
        Returns the relative path to the module directory, or None if no __init__.py found.
        """
        path_obj = Path(file_path)
        
        # Traverse up to find __init__.py
        current_path = path_obj.parent
        while current_path != current_path.parent:  # Stop at root
            if (current_path / "__init__.py").exists():
                module_path = str(current_path.relative_to(self.workspace_path))
                return module_path
            
            current_path = current_path.parent
        
        return None

    async def _get_module_file_summaries(self, module_path: str) -> List[Dict[str, Any]]:
        """
        Get file summaries for all files in a module.
        
        Only returns summaries for files marked as valid and with actual content.
        """
        all_summaries = await self.storage.get_all_file_summaries()
        
        # Filter by module path and valid files
        module_file_summaries = [
            {"file_path": fs.file_path, "summary": fs.summary}
            for fs in all_summaries
            if fs.file_path.startswith(module_path + "/") and fs.summary
        ]
        
        return module_file_summaries
