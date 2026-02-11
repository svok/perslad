from dataclasses import dataclass
from typing import Type, Callable

from ingestor.pipeline.base.base_stage import BaseStage
from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.pipeline_context import PipelineContext


@dataclass
class StageDef:
    name: str
    stage_class: Type[ProcessorStage|BaseStage]
    factory: Callable[[PipelineContext], ProcessorStage|BaseStage]
