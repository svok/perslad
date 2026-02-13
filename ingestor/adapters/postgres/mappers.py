"""
Mappers for PostgreSQL rows to domain models.
"""

from typing import Any
import json
from ingestor.core.models.chunk import Chunk
from ingestor.core.models.file_summary import FileSummary
from ingestor.core.models.module_summary import ModuleSummary


class PostgresMapper:
    @staticmethod
    def map_chunk(row: Any) -> Chunk:
        embedding = row["embedding"]
        if embedding is not None:
            # Handle string representation (e.g. from asyncpg without register_vector)
            if isinstance(embedding, str):
                # pgvector string format: "[1.0,2.0,3.0]"
                cleaned = embedding.strip("[]")
                if not cleaned:
                    embedding = []
                else:
                    embedding = [float(x) for x in cleaned.split(",")]

            # Convert numpy array or other iterables to list of standard floats
            elif hasattr(embedding, "tolist"):
                embedding = embedding.tolist()
            else:
                embedding = list(embedding)

            # Ensure elements are float, not numpy.float32
            embedding = [float(x) for x in embedding]

        return Chunk(
            id=row["id"],
            file_path=row["file_path"],
            content=row["content"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            chunk_type=row["chunk_type"],
            summary=row["summary"],
            purpose=row["purpose"],
            embedding=embedding,
            metadata={},
        )

    @staticmethod
    def map_file_summary(row: Any) -> FileSummary:
        meta = row["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        elif meta is None:
            meta = {}

        # Ensure mtime/checksum are in metadata if present in columns
        if "mtime" in row:
            meta["mtime"] = row["mtime"]
        if "checksum" in row:
            meta["checksum"] = row["checksum"]

        return FileSummary(
            file_path=row["file_path"],
            summary=row["summary"],
            chunk_ids=list(row["chunk_ids"]) if row["chunk_ids"] else [],
            metadata=meta,
        )

    @staticmethod
    def map_module_summary(row: Any) -> ModuleSummary:
        return ModuleSummary(
            module_path=row["module_path"],
            summary=row["summary"],
            file_paths=list(row["file_paths"]) if row["file_paths"] else [],
            metadata={},
        )
