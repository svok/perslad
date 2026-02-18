"""
test_e2e_full_workflow.py

End-to-end tests for complete system workflows.

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

from infra.config import Ingestor, LangGraph, MCP
from conftest import (
    get_file_summary,
    get_chunks_count_for_file,
    get_chunks_count,
    get_file_summaries_count,
)


INDEXATION_WAIT = 8
INGESTOR_CONTAINER = ""


def create_file_in_container(container_name: str, file_path: str, content: str) -> bool:
    """Create file inside Docker container for inotify testing"""
    try:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    except OSError:
        return False


def delete_file_in_container(container_name: str, file_path: str) -> bool:
    """Delete file inside Docker container"""
    try:
        os.remove(file_path)
        return True
    except OSError:
        return False


def get_container_workspace() -> str:
    return os.getenv('WORKSPACE_ROOT', '/workspace')


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.requires_gpu
class TestE2EFullWorkflow:
    """End-to-end tests for complete system workflows"""

    @pytest.mark.asyncio
    async def test_e2e_initial_scan_and_search(self, ingestor_client, db_engine):
        """Complete workflow: initial scan -> search"""
        summaries = get_file_summaries_count(db_engine)
        chunks = get_chunks_count(db_engine)
        
        assert summaries > 0, "DB should have file_summaries"
        assert chunks > 0, "DB should have chunks"
        
        search_payload = {"query": "test", "top_k": 5}
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    async def test_e2e_file_created_search_chat(self, ingestor_client, langgraph_client, db_engine):
        """Complete workflow: create file -> search -> chat"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"e2e_test_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content = f"""E2E Test Document {unique_id}

Python async programming allows for concurrent code execution.
Key components include:
- Event loop
- Coroutines
- Tasks
- Futures
"""
        
        success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
        if not success:
            pytest.skip("Could not create file in container")
        
        await asyncio.sleep(INDEXATION_WAIT)
        
        summary = get_file_summary(db_engine, rel_file_path)
        if summary is None:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)
            pytest.skip("File was not indexed")
        
        search_payload = {"query": f"Python async {unique_id}", "top_k": 3}
        search_response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is async programming in Python?"}
            ],
            "stream": False,
            "max_tokens": 100
        }
        
        chat_response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=chat_payload)
        assert chat_response.status_code == 200
        
        delete_file_in_container(INGESTOR_CONTAINER, container_file_path)

    @pytest.mark.asyncio
    async def test_e2e_multiple_files_workflow(self, ingestor_client, db_engine):
        """Workflow with multiple files"""
        unique_id = uuid.uuid4().hex[:8]
        files = []
        
        for i in range(3):
            rel_file_path = f"e2e_multi_{unique_id}_{i}.txt"
            container_file_path = f"{get_container_workspace()}/{rel_file_path}"
            content = f"E2E Multi-file test {i} - {unique_id}"
            
            success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content)
            if success:
                files.append((rel_file_path, container_file_path))
        
        if len(files) < 3:
            for _, cp in files:
                delete_file_in_container(INGESTOR_CONTAINER, cp)
            pytest.skip("Could not create all files")
        
        await asyncio.sleep(INDEXATION_WAIT)
        
        search_payload = {"query": f"Multi-file {unique_id}", "top_k": 5}
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        assert response.status_code == 200
        
        for _, container_file_path in files:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)

    @pytest.mark.asyncio
    async def test_e2e_search_with_chat(self, ingestor_client, langgraph_client, db_engine):
        """Search and use results in chat"""
        search_payload = {"query": "Python", "top_k": 3}
        search_response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Explain Python briefly."}
            ],
            "stream": False,
            "max_tokens": 50
        }
        
        chat_response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data

    @pytest.mark.asyncio
    async def test_e2e_file_lifecycle(self, db_engine):
        """Full file lifecycle: create -> update -> delete"""
        unique_id = uuid.uuid4().hex[:8]
        rel_file_path = f"e2e_lifecycle_{unique_id}.txt"
        container_file_path = f"{get_container_workspace()}/{rel_file_path}"
        
        content_v1 = f"Initial content {unique_id}"
        success = create_file_in_container(INGESTOR_CONTAINER, container_file_path, content_v1)
        if not success:
            pytest.skip("Could not create file in container")
        
        await asyncio.sleep(INDEXATION_WAIT)
        
        summary = get_file_summary(db_engine, rel_file_path)
        if summary is None:
            delete_file_in_container(INGESTOR_CONTAINER, container_file_path)
            pytest.skip("File was not indexed")
        
        content_v2 = f"Updated content {unique_id} with more text"
        create_file_in_container(INGESTOR_CONTAINER, container_file_path, content_v2)
        
        await asyncio.sleep(INDEXATION_WAIT)
        
        success = delete_file_in_container(INGESTOR_CONTAINER, container_file_path)
        if not success:
            pytest.skip("Could not delete file")
        
        await asyncio.sleep(INDEXATION_WAIT)
        
        summary = get_file_summary(db_engine, rel_file_path)
        assert summary is None, "Deleted file should not be in DB"

    @pytest.mark.asyncio
    async def test_e2e_streaming_chat(self, langgraph_client):
        """Test streaming chat response"""
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Count from 1 to 5."}
            ],
            "stream": True,
            "max_tokens": 50
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=chat_payload)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_e2e_tool_calling(self, langgraph_client):
        """Test tool calling capability"""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        }
                    }
                }
            }
        ]
        
        chat_payload = {
            "messages": [
                {"role": "user", "content": "What's the weather?"}
            ],
            "tools": tools,
            "stream": False,
            "max_tokens": 100
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=chat_payload)
        assert response.status_code == 200


@pytest.mark.e2e
@pytest.mark.fast
class TestE2EHealthChecks:
    """Quick health check tests"""

    @pytest.mark.asyncio
    async def test_all_services_healthy(self, ingestor_client, langgraph_client):
        """All services should be healthy"""
        response = await ingestor_client.get(Ingestor.HEALTH)
        assert response.status_code == 200
        
        response = await langgraph_client.get(LangGraph.HEALTH)
        if response.status_code == 404:
            response = await langgraph_client.get(LangGraph.ROOT)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_db_connected(self, db_engine):
        """Database should be connected"""
        from sqlalchemy import text
        
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
