from typing import Any

from ingestor.pipeline.base.sink_stage import SinkStage


class IndexerSinkStage(SinkStage):
    def __init__(self, max_workers: int = 1):
        super().__init__("indexer_sink", max_workers)

    async def consume(self, item: Any) -> None:
        try:
            item_str = str(item)

            # Обрезаем, если текст слишком длинный
            if len(item_str) > 300:
                item_str = item_str[:300] + "..."
        except Exception as e:
            # На случай совсем странных объектов (например, с бинарными данными)
            item_str = f"<serialization error: {e}>"

        self.log.info(
            f"IndexerSink.consume(): type={type(item).__name__}, "
            f"content={item_str}"
        )
        
        # # Try to get length if it's a list/tuple/set
        # if isinstance(item, (list, tuple)):  # Fixed: only list and tuple are indexable
        #     self.log.info(f"IndexerSink.consume(): item is a collection with {len(item)} elements: {item}")
        #     # for i, elem in enumerate(item[:3]):  # Log first 3 elements
        #     #     try:
        #     #         elem_str = str(elem)
        #     #         if len(elem_str) > 100:
        #     #             elem_str = elem_str[:100] + "..."
        #     #         self.log.info(f"IndexerSink.consume(): [{i}] {type(elem).__name__}: {elem_str}")
        #     #     except:
        #     #         self.log.info(f"IndexerSink.consume(): [{i}] {type(elem).__name__}: <cannot convert>")
        #     # if len(item) > 3:
        #     #     self.log.info(f"IndexerSink.consume(): ... and {len(item) - 3} more elements")
        #
        # # Try to access specific attributes if it's a dataclass/object
        # elif hasattr(item, '__dict__'):
        #     self.log.info(f"IndexerSink.consume(): item has __dict__: {item}")
        #     # for key, value in item.__dict__.items():
        #     #     try:
        #     #         value_str = str(value)
        #     #         if len(value_str) > 100:
        #     #             value_str = value_str[:100] + "..."
        #     #         self.log.info(f"IndexerSink.consume(): {key} = {value_str}")
        #     #     except:
        #     #         self.log.info(f"IndexerSink.consume(): {key} = <cannot convert>")
        #
        # # Try to get name attribute (common for some types)
        # elif hasattr(item, 'name'):
        #     self.log.info(f"IndexerSink.consume(): item.name = {item.name}")
        #
        # self.log.info(f"IndexerSink.consume(): --- end of item details ---")
