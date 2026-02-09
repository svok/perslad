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
from ingestor.core.models.chunk import Chunk
from ingestor.app.llm_lock import LLMLockManager

log = get_logger("ingestor.pipeline.enrich")


ENRICHMENT_PROMPT_TEMPLATE = """You are analyzing a code/documentation chunk.

File: {file_path}
Type: {chunk_type}

Content:
```
{content}
```

Provide a brief analysis using the following format:
Summary: <1-2 sentences describing what this code does>
Purpose: <what is the purpose of this code/function?>

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
        if not chunks:
            return []

        log.info("enrich.start", chunks_count=len(chunks))

        # Проверка лока раз в файл/группу файлов
        if await self.lock_manager.is_locked():
            log.info("enrich.llm_locked.waiting")
            await self.lock_manager.wait_unlocked()

        # Запускаем все чанки из этого сообщения параллельно
        tasks = [self._enrich_chunk(chunk) for chunk in chunks]

        # Обязательно добавляем timeout, чтобы LLM не вешала пайплайн навсегда
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            log.error(f"Critical error in gather: {e}")

        return chunks

    async def _enrich_chunk(self, chunk: Chunk) -> None:
        prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
            file_path=chunk.file_path,
            chunk_type=chunk.chunk_type,
            content=chunk.content[:1000],
        )

        async def _call(model):
            # Если используете LangChain или OpenAI SDK:
            # response.content — это уже готовая Unicode строка.
            response = await model.ainvoke(prompt)
            return response.content

        # ВАЖНО: Проверьте, что call_raw возвращает чистую строку
        result = await self.llm.call_raw(_call)

        # Если result пришел как байты, декодируем их ОДИН раз
        if isinstance(result, bytes):
            result = result.decode('utf-8')

        # УБИРАЕМ любые .encode().decode('unicode-escape'),
        # если данные уже в нормальном UTF-8.
        log.info("enrich.chunk.raw_response", chunk_id=chunk.id, response=result[:200])

        # Парсим результат
        lines = result.strip().split("\n")

        summary_lines = []
        purpose_lines = []
        in_summary_section = False
        in_purpose_section = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Если строка начинается с "Summary:" - начинаем секцию summary
            if line.lower().startswith("summary:"):
                in_summary_section = True
                in_purpose_section = False
                # Извлекаем текст summary (убираем префикс "Summary:")
                summary_text = line.replace("Summary:", "", 1).strip()
                if summary_text:
                    summary_lines.append(summary_text)
                continue

            # Если строка начинается с "Purpose:" - начинаем секцию purpose
            elif line.lower().startswith("purpose:"):
                in_purpose_section = True
                in_summary_section = False
                # Извлекаем текст purpose (убираем префикс "Purpose:")
                purpose_text = line.replace("Purpose:", "", 1).strip()
                if purpose_text:
                    purpose_lines.append(purpose_text)
                continue

            # Если мы внутри секции, добавляем строку
            if in_summary_section:
                summary_lines.append(line)
            elif in_purpose_section:
                purpose_lines.append(line)

        # Если не найден отдельный purpose, берем первый line summary как purpose
        chunk.summary = " ".join(summary_lines) if summary_lines else None
        chunk.purpose = " ".join(purpose_lines) if purpose_lines else (summary_lines[0] if summary_lines else None)

        log.info("enrich.chunk.parsed",
                  chunk_id=chunk.id,
                  summary_len=len(chunk.summary) if chunk.summary else 0,
                  purpose_len=len(chunk.purpose) if chunk.purpose else 0,
                  summary_preview=chunk.summary[:100] if chunk.summary else None,
                  purpose_preview=chunk.purpose[:100] if chunk.purpose else None)
