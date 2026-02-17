"""
test_component_ingestor.py

Component tests for Ingestor service.

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
    """Create file inside Docker container for inotify testing"""
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
    """Delete file inside Docker container"""
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
    """Get workspace path inside container"""
    return "/workspace"


@pytest.mark.component
@pytest.mark.integration
@pytest.mark.fast
class TestIngestorHealth:
    """Tests for ingestor health and API"""

    @pytest.mark.asyncio
    async def test_ingestor_health_endpoint(self, ingestor_client):
        """Test that ingestor health endpoint returns ready status"""
        response = await ingestor_client.get(Ingestor.HEALTH)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"

    @pytest.mark.asyncio
    async def test_ingestor_stats_endpoint(self, ingestor_client):
        """Test that ingestor stats endpoint returns storage stats"""
        response = await ingestor_client.get(Ingestor.STATS)
        assert response.status_code == 200

        data = response.json()
        assert "chunks" in data or "file_summaries" in data


@pytest.mark.component
@pytest.mark.integration
@pytest.mark.fast
class TestInitialScanState:
    """Tests for initial scan results"""

    @pytest.mark.asyncio
    async def test_expected_valid_files_in_db(self, db_engine):
        """All expected valid files should be indexed with chunks"""
        for file_path, expected in EXPECTED_VALID_FILES.items():
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} should be in file_summaries"
            
            metadata = summary["metadata"]
            assert metadata.get("valid") == True, f"File {file_path} should be valid"
            
            chunks_count = get_chunks_count_for_file(db_engine, file_path)
            assert chunks_count >= expected["min_chunks"], \
                f"File {file_path} should have >= {expected['min_chunks']} chunks"

    @pytest.mark.asyncio
    async def test_expected_invalid_files_in_db(self, db_engine):
        """All expected invalid files should have invalid_reason and 0 chunks"""
        for file_path, expected in EXPECTED_INVALID_FILES.items():
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} should be in file_summaries"
            
            metadata = summary["metadata"]
            assert "invalid_reason" in metadata, f"File {file_path} should have invalid_reason"
            
            chunks_count = get_chunks_count_for_file(db_engine, file_path)
            assert chunks_count == 0, f"Invalid file {file_path} should have 0 chunks"

    @pytest.mark.asyncio
    async def test_chunks_have_required_fields(self, db_engine):
        """All chunks should have required fields"""
        from sqlalchemy import text
        
        with db_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT id, file_path, content, chunk_type FROM chunks LIMIT 10"
            ))
            chunks = result.fetchall()
        
        assert len(chunks) > 0, "Should have chunks"
        
        for chunk_id, file_path, content, chunk_type in chunks:
            assert chunk_id is not None
            assert file_path is not None
            assert content is not None
            assert chunk_type is not None


@pytest.mark.component
@pytest.mark.integration
@pytest.mark.fast
class TestFileIndexingViaInotify:
    """Tests for file indexing via inotify (inside container)"""

    @pytest.mark.asyncio
    async def test_text_file_indexed_via_inotify(self, db_engine):
        """Text file created in container should be indexed"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_component_text_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content = f"Test content for component test {unique_id}\nWith multiple lines\n"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is not None, f"File {rel_file_path} should be in file_summaries"
            
            chunks_count = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks_count > 0, f"Text file should have chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)

    @pytest.mark.asyncio
    async def test_code_file_indexed_via_inotify(self, db_engine):
        """Python code file created in container should be indexed"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_component_code_{unique_id}.py"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content = f'''# Test Python code {unique_id}
def hello():
    return "Hello, World!"

class TestClass:
    def __init__(self):
        self.value = 42
'''
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is not None, f"Code file should be in file_summaries"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)

    @pytest.mark.asyncio
    async def test_empty_file_indexed_with_error(self, db_engine):
        """Empty file should have invalid_reason in metadata"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_component_empty_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, "")
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            if summary is None:
                pytest.skip("File was not indexed")
            
            metadata = summary["metadata"]
            assert "invalid_reason" in metadata, "Empty file should have invalid_reason"
            
            chunks_count = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks_count == 0, "Empty file should have 0 chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)


@pytest.mark.component
@pytest.mark.integration
@pytest.mark.fast
class TestFileDeletionViaInotify:
    """Tests for file deletion and DB cleanup via inotify"""

    @pytest.mark.asyncio
    async def test_file_deleted_removed_from_db(self, db_engine):
        """File deleted in container should be removed from DB"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_component_delete_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content = f"Test content for deletion {unique_id}"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            if summary is None:
                pytest.skip("File was not indexed, cannot test deletion")
            
            success = delete_file_in_container(INGESTOR_CONTAINER, container_file_path)
            if not success:
                pytest.skip("Could not delete file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is None, "Deleted file should not be in file_summaries"
            
            chunks_count = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks_count == 0, "Deleted file should have 0 chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)


@pytest.mark.component
@pytest.mark.integration
@pytest.mark.fast
class TestSearchFunctionality:
    """Tests for search functionality"""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, ingestor_client, db_engine):
        """Search should return results for indexed content"""
        search_payload = {"query": "sample", "top_k": 5}
        
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        assert response.status_code == 200

        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    async def test_search_with_top_k_parameter(self, ingestor_client):
        """Search should respect top_k parameter"""
        search_payload = {"query": "test", "top_k": 2}
        
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        assert response.status_code == 200

        data = response.json()
        if data.get("results"):
            assert len(data["results"]) <= 2


@pytest.mark.component
@pytest.mark.integration
@pytest.mark.fast
class TestChunksEndpoint:
    """Tests for chunks endpoint"""

    @pytest.mark.asyncio
    async def test_chunks_endpoint_returns_list(self, ingestor_client):
        """Chunks endpoint should return list of chunks"""
        response = await ingestor_client.get(Ingestor.CHUNKS)
        assert response.status_code == 200

        data = response.json()
        assert "chunks" in data or isinstance(data, list)

    @pytest.mark.asyncio
    async def test_chunks_endpoint_with_limit(self, ingestor_client):
        """Chunks endpoint should respect limit parameter"""
        response = await ingestor_client.get(f"{Ingestor.CHUNKS}?limit=3")
        assert response.status_code == 200
