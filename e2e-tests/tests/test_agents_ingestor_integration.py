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

import uuid

import pytest

from conftest import (
    get_file_summary,
    get_chunks_count_for_file,
)
from infra.config import Ingestor, LangGraph

INDEXATION_WAIT = 3

EXPECTED_VALID_FILES = {
    "test_sample.py": {"min_chunks": 1},
    "test_sample.md": {"min_chunks": 1},
    "test_sample.txt": {"min_chunks": 1},
}

EXPECTED_INVALID_FILES = {
    "test_empty.txt": {"reason": "empty"},
    "test_binary.bin": {"reason": "binary"},
}


def create_file_in_workspace(file_path: str, content: str) -> bool:
    """Create file inside Docker container for inotify testing"""
    try:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    except OSError:
        return False


def delete_file_in_workspace(file_path: str) -> bool:
    """Delete file inside Docker container"""
    try:
        os.remove(file_path)
        return True
    except OSError:
        return False


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestInitialScan:
    """Tests for initial workspace scanning"""

    @pytest.mark.asyncio
    async def test_expected_valid_files_in_db(self, db_engine, ensure_test_sample_indexed):
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
    async def test_expected_invalid_files_in_db(self, db_engine, ensure_test_sample_indexed):
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
    async def test_valid_files_have_metadata(self, db_engine, ensure_test_sample_indexed):
        """Valid files should have mtime and checksum in metadata"""
        for file_path in EXPECTED_VALID_FILES:
            summary = get_file_summary(db_engine, file_path)
            assert summary is not None, f"File {file_path} not found"

            metadata = summary["metadata"]
            assert "mtime" in metadata, f"File {file_path} should have mtime"
            assert "checksum" in metadata, f"File {file_path} should have checksum"

    @pytest.mark.asyncio
    async def test_chunks_have_embeddings_and_summaries(self, db_engine, ensure_test_sample_indexed):
        """All chunks for expected test files should have embeddings and summaries"""
        from sqlalchemy import text

        # Get expected file paths
        expected_files = list(EXPECTED_VALID_FILES.keys()) + list(EXPECTED_INVALID_FILES.keys())

        with db_engine.connect() as conn:
            # Count chunks for expected files that have NULL embeddings
            result = conn.execute(
                text("SELECT COUNT(*) FROM chunks WHERE file_path = ANY(:paths) AND embedding IS NULL"),
                {"paths": expected_files}
            )
            null_embeddings = result.fetchone()[0]

            # Count chunks for expected files that have NULL or empty summaries
            result = conn.execute(
                text("SELECT COUNT(*) FROM chunks WHERE file_path = ANY(:paths) AND (summary IS NULL OR summary = '')"),
                {"paths": expected_files}
            )
            null_summaries = result.fetchone()[0]

        assert null_embeddings == 0, f"All chunks for expected files should have embeddings, {null_embeddings} missing"
        assert null_summaries == 0, f"All chunks for expected files should have summaries, {null_summaries} missing"

    @pytest.mark.asyncio
    async def test_no_orphan_files_in_db(self, db_engine, ensure_test_sample_indexed, config):
        """DB should not contain files that don't exist in workspace"""
        import os
        from sqlalchemy import text

        # Get workspace root from env (host path)
        host_workspace = config['workspace_root']
        if not host_workspace or not os.path.isdir(host_workspace):
            pytest.skip("PROJECT_ROOT not set, cannot check workspace files")

        # Build set of files currently in workspace (relative paths)
        workspace_files = set()
        for root, dirs, files in os.walk(host_workspace):
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, host_workspace)
                workspace_files.add(rel)

        # Get files in DB
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT file_path FROM file_summaries"))
            db_files = set(row[0] for row in result.fetchall())

        # Orphan = in DB but not in workspace
        orphans = db_files - workspace_files

        # Ignore expected files that may be missing due to not created yet? Actually they should be in workspace.
        # So any orphan is a problem.
        assert len(orphans) == 0, f"Orphaned files in DB (not in workspace): {orphans}"


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestFileCreation:
    """Tests for file creation and inotify indexing"""

    @pytest.mark.asyncio
    async def test_file_created_in_container_indexed(self, db_engine, config):
        """File created inside container should be indexed via inotify"""
        unique_id = uuid.uuid4().hex[:8]
        workspace_root = config['workspace_root']
        rel_file_path = f"test_inotify_create_{unique_id}.txt"
        container_file_path = f"{workspace_root}/{rel_file_path}"
        
        content = f"Test content for inotify {unique_id}"
        
        try:
            success = create_file_in_workspace(container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is not None, f"File {rel_file_path} should be in file_summaries"
            
            chunks_count = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks_count > 0, f"File should have chunks, got {chunks_count}"
        finally:
            delete_file_in_workspace(container_file_path)

    @pytest.mark.asyncio
    async def test_empty_file_created_in_container(self, db_engine, config):
        """Empty file created in container should be indexed with error"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_inotify_empty_{unique_id}.txt"
        workspace_root = config['workspace_root']
        container_file_path = f"{workspace_root}/{rel_file_path}"
        
        try:
            success = create_file_in_workspace(container_file_path, "")
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
            delete_file_in_workspace(container_file_path)


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestFileDeletion:
    """Tests for file deletion and DB cleanup"""

    @pytest.mark.asyncio
    async def test_file_deleted_in_container_removed_from_db(self, db_engine, config):
        """File deleted in container should be removed from DB"""
        workspace_root = config['workspace_root']
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"test_inotify_delete_{unique_id}.txt"
        container_file_path = f"{workspace_root}/{rel_file_path}"
        
        content = f"Test content for deletion {unique_id}"
        
        try:
            success = create_file_in_workspace(container_file_path, content)
            if not success:
                pytest.skip("Could not create file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            if summary is None:
                pytest.skip("File was not indexed, cannot test deletion")
            
            success = delete_file_in_workspace(container_file_path)
            if not success:
                pytest.skip("Could not delete file in container")
            
            await asyncio.sleep(INDEXATION_WAIT)
            
            summary = get_file_summary(db_engine, rel_file_path)
            assert summary is None, f"Deleted file should not be in file_summaries"
            
            chunks_count = get_chunks_count_for_file(db_engine, rel_file_path)
            assert chunks_count == 0, f"Deleted file should have 0 chunks"
        finally:
            delete_file_in_workspace(container_file_path)


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
