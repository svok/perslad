from llama_index.core.schema import TextNode
from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.pipeline_file_context import PipelineFileContext
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper


class ParseProcessorStage(ProcessorStage):
    """
    Parse file and convert to TextNode objects.
    """
    
    def __init__(self, max_workers: int = 4, text_splitter_helper: TextSplitterHelper = None):
        super().__init__("parse", max_workers)
        self.helper = text_splitter_helper or TextSplitterHelper()
    
    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        if not context.abs_path or not context.abs_path.exists():
            context.mark_skipped("file not found")
            return context
        
        try:
            # Get TextNode objects from file
            nodes, error = await self.helper.chunk_file(
                file_path=str(context.abs_path),
                relative_path=str(context.file_path),
                extension=context.abs_path.suffix,
            )
            
            if error:
                self.log.error(f"Failed to parse file {context.file_path}: {error}")
                context.has_errors = True
                context.errors.append(f"parse error: {error}")
                context.nodes = []
                return context
            
            if not nodes:
                self.log.warning(f"No nodes generated for {context.file_path} (binary or empty)")
                context.has_errors = True
                context.errors.append("no nodes generated (binary or empty)")
                context.nodes = []
                return context
            
            # Filter out empty nodes
            valid_nodes = [node for node in nodes if node.text and node.text.strip()]
            
            if len(valid_nodes) < len(nodes):
                self.log.warning(f"Some nodes had empty text for {context.file_path}")
            
            if not valid_nodes:
                context.has_errors = True
                context.errors.append("all nodes empty")
                context.nodes = []
                return context
            
            context.nodes = valid_nodes
            context.mark_success()
            return context
            
        except Exception as e:
            self.log.error(f"Critical parse error for {context.file_path}: {e}", exc_info=True)
            context.has_errors = True
            context.errors.append(f"parse error: {str(e)}")
            context.nodes = []
            return context
