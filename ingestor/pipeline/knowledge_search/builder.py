from typing import List

from ingestor.pipeline.models.stage_def import StageDef


class KnowledgeSearchPipelineBuilder:
    """Билдер пайплайна поиска (DEPRECATED - use KnowledgeIndex instead)"""
    
    @staticmethod
    def get_default_definitions() -> List[StageDef]:
        """
        DEPRECATED: This builder is no longer used.
        KnowledgeSearchPipeline has been replaced by KnowledgeIndex.
        Returning empty list to avoid import errors.
        """
        return []
