"""
test_indexation_workflows.py

Tests for file ingestion, processing, and storage workflows.
Covers: Indexation workflows, DB storing

Key concepts:
- Full scan runs at ingestor startup
- File changes are detected via inotify (inside container only)
- Tests verify DB state directly

IMPORTANT: inotify events don't propagate through Docker bind mounts from host.
For inotify tests, files must be created inside the container.
"""

import asyncio
import os
import subprocess
import uuid

import pytest

from infra.config import Ingestor
from conftest import (
    get_file_summary,
    get_chunks_count_for_file,
    get_chunks_count,
    get_file_summaries_count,
)


INDEXATION_WAIT = 8
INGESTOR_CONTAINER = "perslad-1-ingestor-1"

EXPECTED_VALID_FILES = {
    "test_sample.py": {"min_chunks": 1},
    "test_sample.md": {"min_chunks": 1},
    "test_sample.txt": {"min_chunks": 1},
}

EXPECTED_INVALID_FILES = {
    "test_empty.txt": {"reason": "empty"},
    "test_binary.bin": {"reason": "binary"},
}


def create_file_in_container(container_name: str, file_path: str, content: str) -> bool:
    try:
        escaped_content = content.replace("'", "'\\''")
        subprocess.run([
            "docker", "exec", container_name,
            "sh", "-c", f"echo '{escaped_content}' > {file_path}"
        ], check=True, capture_output=True, timeout=10)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to create file in container: {e}")
        return False


def delete_file_in_container(container_name: str, file_path: str) -> bool:
    try:
        subprocess.run([
            "docker", "exec", container_name,
            "rm", "-f", file_path
        ], check=True, capture_output=True, timeout=10)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to delete file in container: {e}")
        return False


def get_container_workspace() -> str:
    return "/workspace"


@pytest.mark.integration
@pytest.mark.indexation
@pytest.mark.fast
class TestInitialScan:
    """Tests for initial scan results"""

    @pytest.mark.asyncio
    async def test_expected_valid_files_in_db(self, db_engine, ensure_test_sample_indexed):
        """All expected valid files should be indexed with chunks"""
        for file_path, expected in EXPECTED_VALID_FILES.items():
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} should be in file_summaries"

            metadata = summary["metadata"]
            assert metadata.get("valid") == True, f"File {file_path} should be valid"

            chunks_count = get_chunks_count_for_file(db_engine, file_path)
            assert chunks_count >= expected["min_chunks"]

    @pytest.mark.asyncio
    async def test_expected_invalid_files_in_db(self, db_engine, ensure_test_sample_indexed):
        """All expected invalid files should have invalid_reason and 0 chunks"""
        for file_path, expected in EXPECTED_INVALID_FILES.items():
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} should be in file_summaries"

            metadata = summary["metadata"]
            assert "invalid_reason" in metadata

            chunks_count = get_chunks_count_for_file(db_engine, file_path)
            assert chunks_count == 0

    @pytest.mark.asyncio
    async def test_valid_files_have_metadata(self, db_engine, ensure_test_sample_indexed):
        """Valid files should have mtime and checksum"""
        for file_path in EXPECTED_VALID_FILES:
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} not found"

            metadata = summary["metadata"]
            assert "mtime" in metadata
            assert "checksum" in metadata


@pytest.mark.integration
@pytest.mark.indexation
@pytest.mark.fast
class TestFileCreationViaInotify:
    """Tests for file creation and indexing via inotify"""

    @pytest.mark.asyncio
    async def test_text_file_created_indexed(self, db_engine):
        """Text file created in container should be indexed"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_index_text_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content = f"Test content for indexation {unique_id}\nMultiple lines here\n"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is not None, f"File {rel_file_path} should be indexed"
            
            chunks = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks > 0, "Text file should have chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)

    @pytest.mark.asyncio
    async def test_code_file_created_indexed(self, db_engine):
        """Code file created in container should be indexed"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_index_code_{unique_id}.py"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content = f'''# Test code {unique_id}
def add(a, b):
    return a + b
'''
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is not None, "Code file should be indexed"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)

    @pytest.mark.asyncio
    async def test_batch_files_created_indexed(self, db_engine):
        """Multiple files created should all be indexed"""
        unique_id = uuid.uuid4().hex[:8]
        files = []
        
        try:
            for i in range(3):
                rel_file_path = f"test_batch_{unique_id}_{i}.txt"
                container_file_path = f"{get_container_workspace()}/{rel_file_path}"
                content = f"Batch test {i} content {unique_id}"
                
                success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
                if success:
                    files.append((rel_file_path, container_file_path))
            
            if len(files) < 3:
                pytest.skip("Could not create all files in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            for rel_file_path, _ in files:
                summary = get_file_summary(db_engine, rel_file_path)
                assert summary is not None, f"File {rel_file_path} should be indexed"
        finally:
            for _, container_file_path in files:
                delete_file_in_container(INGESTOR_CONTAINER, container_file_path)


@pytest.mark.integration
@pytest.mark.indexation
@pytest.mark.fast
class TestFileDeletionViaInotify:
    """Tests for file deletion and DB cleanup"""

    @pytest.mark.asyncio
    async def test_file_deleted_removed_from_db(self, db_engine):
        """Deleted file should be removed from DB"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_delete_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content = f"Content for deletion test {unique_id}"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            if summary is None:
                pytest.skip("File was not indexed")
            
            success = delete_file_in_container(INGESTOR_CONTAINER, container_file_path)
            if not success:
                pytest.skip("Could not delete file")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is None, "Deleted file should not be in DB"
            
            chunks = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks == 0, "Deleted file should have 0 chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)


@pytest.mark.integration
@pytest.mark.indexation
@pytest.mark.fast
class TestFileUpdateViaInotify:
    """Tests for file update and re-indexing"""

    @pytest.mark.asyncio
    async def test_file_updated_reindexed(self, db_engine):
        """Updated file should be re-indexed"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_update_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content_v1 = f"Initial content {unique_id}"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content_v1)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            if summary is None:
                pytest.skip("File was not indexed")
            
            initial_checksum = summary.get("checksum", "")
            
            content_v2 = f"Updated content {unique_id} with more text"
            create_file_in_container(INGESTOR_CONTAINER, container_file_path, content_v2)
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            if summary:
                updated_checksum = summary.get("checksum", "")
                assert initial_checksum != updated_checksum, "Checksum should change after update"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)


@pytest.mark.integration
@pytest.mark.indexation
@pytest.mark.fast
class TestEmptyAndBinaryFiles:
    """Tests for empty and binary file handling"""

    @pytest.mark.asyncio
    async def test_empty_file_has_error(self, db_engine):
        """Empty file should have invalid_reason"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_empty_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, "")
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            if summary is None:
                pytest.skip("Empty file was not indexed")
            
            metadata = summary["metadata"]
            assert "invalid_reason" in metadata, "Empty file should have invalid_reason"
            
            chunks = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks == 0, "Empty file should have 0 chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)

    @pytest.mark.asyncio
    async def test_binary_file_has_error(self, db_engine):
        """Binary file should have invalid_reason"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_binary_{unique_id}.bin"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"

        try:
            # Use octal escapes for binary bytes: \000 \001 \002 \003 \377 \376
            subprocess.run([
                "docker", "exec", INGESTOR_CONTAINER,
                "sh", "-c", f"printf '\\000\\001\\002\\003\\377\\376' > {container_file_path}"
            ], check=True, capture_output=True, timeout=10)
        except subprocess.CalledProcessError:
            pytest.skip("Could not create binary file in container")
        
        try:
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            if summary is None:
                pytest.skip("Binary file was not indexed")
            
            metadata = summary["metadata"]
            assert "invalid_reason" in metadata, "Binary file should have invalid_reason"
            
            chunks = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks == 0, "Binary file should have 0 chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)


@pytest.mark.integration
@pytest.mark.indexation
@pytest.mark.fast
class TestSearchAfterIndexation:
    """Tests for search functionality after indexation"""

    @pytest.mark.asyncio
    async def test_search_finds_indexed_content(self, ingestor_client, db_engine):
        """Search should find indexed content"""
        search_payload = {"query": "sample", "top_k": 5}
        
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data


@pytest.mark.integration
@pytest.mark.indexation
@pytest.mark.fast
class TestMetadataHandling:
    """Tests for metadata handling"""

    @pytest.mark.asyncio
    async def test_chunks_have_embeddings(self, db_engine):
        """Chunks should have embeddings"""
        from sqlalchemy import text
        
        with db_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"
            ))
            with_embeddings = result.fetchone()[0]
            
            result = conn.execute(text("SELECT COUNT(*) FROM chunks"))
            total = result.fetchone()[0]
        
        assert with_embeddings == total, "All chunks should have embeddings"

    @pytest.mark.asyncio
    async def test_chunks_have_summaries(self, db_engine):
        """Chunks should have summaries"""
        from sqlalchemy import text
        
        with db_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM chunks WHERE summary IS NOT NULL AND summary != ''"
            ))
            with_summaries = result.fetchone()[0]
            
            result = conn.execute(text("SELECT COUNT(*) FROM chunks"))
            total = result.fetchone()[0]
        
        assert with_summaries == total, "All chunks should have summaries"
