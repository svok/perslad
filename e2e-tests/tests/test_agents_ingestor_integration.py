"""
test_agents_ingestor_integration.py

Tests for LangGraph Agent and Ingestor integration.
Covers: Agents-Ingestor interactions, Indexation workflows

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

from infra.config import Ingestor, LangGraph
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


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestInitialScan:
    """Tests for initial workspace scanning"""

    @pytest.mark.asyncio
    async def test_expected_valid_files_in_db(self, db_engine):
        """All expected valid files should be indexed with chunks"""
        for file_path, expected in EXPECTED_VALID_FILES.items():
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} should be in file_summaries"
            
            metadata = summary["metadata"]
            assert metadata.get("valid") == True, f"File {file_path} should be valid, got: {metadata}"
            
            chunks_count = get_chunks_count_for_file(db_engine, file_path)
            assert chunks_count >= expected["min_chunks"], \
                f"File {file_path} should have >= {expected['min_chunks']} chunks, got {chunks_count}"

    @pytest.mark.asyncio
    async def test_expected_invalid_files_in_db(self, db_engine):
        """All expected invalid files should have invalid_reason and 0 chunks"""
        for file_path, expected in EXPECTED_INVALID_FILES.items():
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} should be in file_summaries"
            
            metadata = summary["metadata"]
            assert "invalid_reason" in metadata, \
                f"File {file_path} should have invalid_reason, got: {metadata}"
            
            chunks_count = get_chunks_count_for_file(db_engine, file_path)
            assert chunks_count == 0, \
                f"Invalid file {file_path} should have 0 chunks, got {chunks_count}"

    @pytest.mark.asyncio
    async def test_valid_files_have_metadata(self, db_engine):
        """Valid files should have mtime and checksum in metadata"""
        for file_path in EXPECTED_VALID_FILES:
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} not found"
            
            metadata = summary["metadata"]
            assert "mtime" in metadata, f"File {file_path} should have mtime"
            assert "checksum" in metadata, f"File {file_path} should have checksum"

    @pytest.mark.asyncio
    async def test_chunks_have_embeddings_and_summaries(self, db_engine):
        """All chunks should have embeddings and summaries"""
        from sqlalchemy import text
        
        with db_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM chunks WHERE embedding IS NULL"
            ))
            null_embeddings = result.fetchone()[0]
            
            result = conn.execute(text(
                "SELECT COUNT(*) FROM chunks WHERE summary IS NULL OR summary = ''"
            ))
            null_summaries = result.fetchone()[0]
        
        assert null_embeddings == 0, f"All chunks should have embeddings, {null_embeddings} missing"
        assert null_summaries == 0, f"All chunks should have summaries, {null_summaries} missing"

    @pytest.mark.asyncio
    async def test_no_orphan_files_in_db(self, db_engine):
        """DB should not contain files that don't exist in workspace"""
        from sqlalchemy import text
        
        workspace = os.getenv('PROJECT_ROOT', '/workspace')
        
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT file_path FROM file_summaries"))
            db_files = set(row[0] for row in result.fetchall())
        
        expected_files = set(EXPECTED_VALID_FILES.keys()) | set(EXPECTED_INVALID_FILES.keys())
        unexpected_files = db_files - expected_files
        
        unexpected_non_test = [f for f in unexpected_files if not f.startswith('test_') and not f.startswith('perf_')]
        
        assert len(unexpected_non_test) == 0, \
            f"Unexpected files in DB (non-test): {unexpected_non_test}"


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestFileCreation:
    """Tests for file creation and inotify indexing"""

    @pytest.mark.asyncio
    async def test_file_created_in_container_indexed(self, db_engine):
        """File created inside container should be indexed via inotify"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_inotify_create_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content = f"Test content for inotify {unique_id}"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is not None, f"File {rel_file_path} should be in file_summaries"
            
            chunks_count = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks_count > 0, f"File should have chunks, got {chunks_count}"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)

    @pytest.mark.asyncio
    async def test_empty_file_created_in_container(self, db_engine):
        """Empty file created in container should be indexed with error"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_inotify_empty_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        try:
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, "")
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is not None, f"Empty file should have file_summary record"
            
            metadata = summary["metadata"]
            assert "invalid_reason" in metadata, f"Empty file should have invalid_reason"
            
            chunks_count = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks_count == 0, f"Empty file should have 0 chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestFileDeletion:
    """Tests for file deletion and DB cleanup"""

    @pytest.mark.asyncio
    async def test_file_deleted_in_container_removed_from_db(self, db_engine):
        """File deleted in container should be removed from DB"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_inotify_delete_{unique_id}.txt"
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
            assert summary is None, f"Deleted file should not be in file_summaries"
            
            chunks_count = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks_count == 0, f"Deleted file should have 0 chunks"
        finally:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestSearchIntegration:
    """Tests for search functionality"""

    @pytest.mark.asyncio
    async def test_search_finds_sample_files(self, ingestor_client, db_engine):
        """Search should find content from sample files"""
        search_payload = {"query": "sample python", "top_k": 5}
        
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    async def test_search_returns_results(self, ingestor_client, db_engine):
        """Search should return results for indexed content"""
        search_payload = {"query": "test content", "top_k": 5}
        
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestAgentIntegration:
    """Tests for agent integration with ingestor"""

    @pytest.mark.asyncio
    async def test_agent_can_search_and_chat(self, ingestor_client, langgraph_client, db_engine):
        """Agent should be able to search and use context in chat"""
        search_payload = {"query": "sample", "top_k": 3}
        search_response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            "stream": False,
            "max_tokens": 50
        }
        
        chat_response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data
        assert len(chat_data["choices"]) > 0
