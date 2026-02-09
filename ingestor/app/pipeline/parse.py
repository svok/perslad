"""
Stage 2: Parse + Split

Задача: превратить файлы в структурированные чанки.
NO LLM.

Использует LlamaIndex loaders и splitters.
"""

import hashlib
from typing import List

from llama_index.core.node_parser import CodeSplitter, MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import Document

from infra.logger import get_logger
from ingestor.app.pipeline.scan import ScannedFile
from ingestor.app.storage import Chunk

log = get_logger("ingestor.pipeline.parse")


class ParseStage:
    """
    Парсит файлы и разбивает на чанки.
    """

    def __init__(self) -> None:
        # Splitters для разных типов файлов
        self.code_splitter = CodeSplitter(
            language="python",
            chunk_lines=40,
            chunk_lines_overlap=15,
            max_chars=1500,
        )
        
        self.markdown_splitter = MarkdownNodeParser()
        
        self.text_splitter = SentenceSplitter(
            chunk_size=512,
            chunk_overlap=50,
        )

    async def run(self, files: List[ScannedFile]) -> List[Chunk]:
        """
        Парсит файлы и возвращает список чанков.
        """
        log.info("parse.start", files_count=len(files))
        
        all_chunks: List[Chunk] = []
        success_count = 0
        failed_count = 0
        
        for i, file in enumerate(files):
            try:
                chunks = await self._parse_file(file)
                all_chunks.extend(chunks)
                success_count += 1
            except Exception as e:
                failed_count += 1
                log.error(
                    "parse.file.failed",
                    index=i,
                    total=len(files),
                    file=file.relative_path,
                    error=str(e),
                    exc_info=True,
                )
        
        log.info("parse.complete", files_count=len(files), success_count=success_count, failed_count=failed_count, chunks_count=len(all_chunks))
        return all_chunks

    async def _parse_file(self, file: ScannedFile) -> List[Chunk]:
        """
        Парсит один файл.
        """
        # Читаем содержимое с обработкой различных кодировок
        content = self._read_file_content(file.path, file.relative_path)
        if content is None:
            return []

        # Определяем тип и splitter
        chunk_type, splitter = self._get_splitter(file.extension)

        # Создаём Document для LlamaIndex
        doc = Document(
            text=content,
            metadata={
                "file_path": file.relative_path,
                "extension": file.extension,
            },
        )

        # Разбиваем на nodes
        try:
            nodes = splitter.get_nodes_from_documents([doc])
        except Exception as e:
            log.error(
                "parse.split.failed",
                file=file.relative_path,
                error=str(e),
                exc_info=True,
            )
            return []

        # Конвертируем в наши Chunks
        chunks = []
        for idx, node in enumerate(nodes):
            chunk_id = self._generate_chunk_id(file.relative_path, idx)

            chunk = Chunk(
                id=chunk_id,
                file_path=file.relative_path,
                # ИСПОЛЬЗУЕМ .text вместо .get_content()
                content=node.text,
                start_line=node.metadata.get("start_line", 0),
                end_line=node.metadata.get("end_line", 0),
                chunk_type=chunk_type,
                metadata={
                    "extension": file.extension,
                    "chunk_index": idx,
                },
            )
            chunks.append(chunk)

        return chunks

    def _read_file_content(self, file_path: str, relative_path: str) -> str | None:
        """
        Читает содержимое файла с обработкой различных кодировок.
        Пытается несколько кодировок в порядке приоритета.
        """
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, errors='strict') as f:
                    content = f.read()

                return content

            except UnicodeDecodeError:
                continue
            except Exception as e:
                log.warning(
                    "parse.read.failed",
                    file=relative_path,
                    encoding=encoding,
                    error=str(e),
                )
                return None
        
        # Если ни одна кодировка не подошла, пробуем с игнорированием ошибок
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            log.warning(
                "parse.read.encoding_fallback",
                file=relative_path,
                message="Used UTF-8 with errors ignored",
            )
            return content
            
        except Exception as e:
            log.warning(
                "parse.read.failed",
                file=relative_path,
                error=str(e),
            )
            return None

    def _get_splitter(self, extension: str):
        """
        Возвращает (chunk_type, splitter) для расширения.
        """
        if extension == ".py":
            return "code", self.code_splitter
        elif extension == ".md":
            return "doc", self.markdown_splitter
        elif extension in {".yaml", ".yml", ".toml"}:
            return "config", self.text_splitter
        else:
            return "text", self.text_splitter

    def _generate_chunk_id(self, file_path: str, index: int) -> str:
        """
        Генерирует детерминированный ID для чанка.
        """
        content = f"{file_path}::{index}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
