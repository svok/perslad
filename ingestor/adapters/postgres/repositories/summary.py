"""
FileSummary and ModuleSummary repositories for PostgreSQL.
"""

from typing import List, Optional, Dict
import json
from ingestor.core.models.file_summary import FileSummary
from ingestor.core.models.module_summary import ModuleSummary
from ingestor.adapters.postgres.connection import PostgresConnection
from ingestor.adapters.postgres.mappers import PostgresMapper
from infra.logger import get_logger

log = get_logger("ingestor.storage.postgres.summaries")


class FileSummaryRepository:
    def __init__(self, connection: PostgresConnection):
        self._conn = connection

    async def save(self, summary: FileSummary) -> None:
        metadata = summary.metadata
        
        query = """
            INSERT INTO file_summaries (file_path, summary, chunk_ids, metadata, mtime, checksum)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (file_path) DO UPDATE SET
                summary = EXCLUDED.summary,
                chunk_ids = EXCLUDED.chunk_ids,
                metadata = EXCLUDED.metadata,
                mtime = EXCLUDED.mtime,
                checksum = EXCLUDED.checksum
        """

        await self._conn.execute_query(
            query,
            summary.file_path,        # $1
            summary.summary,          # $2
            summary.chunk_ids,        # $3
            json.dumps(summary.metadata), # $4
            metadata.get("mtime", 0), # $5
            metadata.get("checksum", ""), # $6
            fetch=None
        )

    async def get(self, file_path: str) -> Optional[FileSummary]:
        row = await self._conn.execute_query(
            "SELECT * FROM file_summaries WHERE file_path = $1",
            file_path,
            fetch='row'
        )
        if not row:
            return None
        return PostgresMapper.map_file_summary(row)

    async def get_all(self) -> List[FileSummary]:
        log.info("postgres.get_all_file_summaries.start")
        rows = await self._conn.execute_query(
            "SELECT file_path, summary, chunk_ids, metadata::text as metadata_json, mtime, checksum FROM file_summaries",
            fetch='all',
            timeout=5.0
        )
        log.info("postgres.get_all_file_summaries.fetched", count=len(rows))
        
        results = []
        for row in rows:
            try:
                # Manually map here because the query casts metadata to text
                meta = json.loads(row["metadata_json"]) if row.get("metadata_json") else {}
                if "mtime" in row:
                    meta["mtime"] = row["mtime"]
                if "checksum" in row:
                    meta["checksum"] = row["checksum"]
                    
                results.append(FileSummary(
                    file_path=row["file_path"],
                    summary=row["summary"],
                    chunk_ids=list(row["chunk_ids"]) if row["chunk_ids"] else [],
                    metadata=meta,
                ))
            except Exception as e:
                log.warning("postgres.map_file_summary.failed", file=row.get("file_path"), error=str(e))
                continue
        
        return results

    async def delete_by_files(self, file_paths: List[str]) -> None:
        await self._conn.execute_query(
            "DELETE FROM file_summaries WHERE file_path = ANY($1)",
            file_paths
        )
        log.info("postgres.delete_file_summaries", paths=file_paths)

    async def update_metadata(self, file_path: str, mtime: float, checksum: str) -> None:
        meta = {
            "mtime": mtime,
            "checksum": checksum,
            "size": 0 
        }
        await self._conn.execute_query(
             """
            INSERT INTO file_summaries (file_path, summary, chunk_ids, metadata, mtime, checksum)
            VALUES ($1, '', '{}', $2, $3, $4)
            ON CONFLICT (file_path) DO UPDATE SET
                metadata = file_summaries.metadata || $2,
                mtime = EXCLUDED.mtime,
                checksum = EXCLUDED.checksum
            """,
            file_path,
            json.dumps(meta),
            mtime,
            checksum
        )

    async def get_metadata(self, file_path: str) -> Optional[Dict]:
        row = await self._conn.execute_query(
            "SELECT * FROM file_summaries WHERE file_path = $1",
            file_path,
            fetch='row'
        )
        if not row:
            return None
        
        return {
            "file_path": row["file_path"],
            "mtime": row.get("mtime", 0),
            "checksum": row.get("checksum", ""),
            "size": 0,
        }

    async def get_batch_metadata(self, file_paths: List[str]) -> Dict[str, Dict]:
        if not file_paths:
            return {}
        
        rows = await self._conn.execute_query(
            "SELECT file_path, mtime, checksum FROM file_summaries WHERE file_path = ANY($1)",
            file_paths,
            fetch='all'
        )
        
        return {
            row["file_path"]: {
                "file_path": row["file_path"],
                "mtime": row.get("mtime", 0),
                "checksum": row.get("checksum", ""),
                "size": 0,
            }
            for row in rows
        }


class ModuleSummaryRepository:
    def __init__(self, connection: PostgresConnection):
        self._conn = connection

    async def save(self, summary: ModuleSummary) -> None:
        # Stub implementation as per original file
        pass

    async def get(self, module_path: str) -> Optional[ModuleSummary]:
        return None

    async def get_all(self) -> List[ModuleSummary]:
        return []
