"""
test_user_requests_responses.py

Tests for API interactions and response validation.
Covers: User requests-responses, API validation

Key concepts:
- Full scan runs at ingestor startup
- File changes are detected via inotify (inside container only)
- Tests verify DB state directly
"""

import asyncio
import os
import subprocess
import uuid

import pytest

from infra.config import LLM, Ingestor, LangGraph, MCP, Embedding
from conftest import (
    get_file_summary,
    get_chunks_count,
    get_file_summaries_count,
)


INDEXATION_WAIT = 8
INGESTOR_CONTAINER = "perslad-1-ingestor-1"


def create_file_in_container(container_name: str, file_path: str, content: str) -> bool:
    try:
        escaped_content = content.replace("'", "'\\''")
        subprocess.run([
            "docker", "exec", container_name,
            "sh", "-c", f"echo '{escaped_content}' > {file_path}"
        ], check=True, capture_output=True, timeout=10)
        return True
    except subprocess.CalledProcessError:
        return False


def delete_file_in_container(container_name: str, file_path: str) -> bool:
    try:
        subprocess.run([
            "docker", "exec", container_name,
            "rm", "-f", file_path
        ], check=True, capture_output=True, timeout=10)
        return True
    except subprocess.CalledProcessError:
        return False


def get_container_workspace() -> str:
    return "/workspace"


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestHealthEndpoints:
    """Tests for service health endpoints"""

    @pytest.mark.asyncio
    async def test_ingestor_health(self, ingestor_client):
        response = await ingestor_client.get(Ingestor.HEALTH)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    @pytest.mark.asyncio
    async def test_langgraph_health(self, langgraph_client):
        response = await langgraph_client.get(LangGraph.HEALTH)
        if response.status_code == 404:
            response = await langgraph_client.get(LangGraph.ROOT)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_llm_health(self, llm_client):
        response = await llm_client.get(LLM.MODELS)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestSearchEndpoints:
    """Tests for search API endpoints"""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, ingestor_client, db_engine):
        summaries = get_file_summaries_count(db_engine)
        assert summaries > 0, "Need indexed content for search"
        
        search_payload = {"query": "test", "top_k": 5}
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    async def test_search_with_top_k(self, ingestor_client):
        search_payload = {"query": "test", "top_k": 2}
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        
        assert response.status_code == 200
        data = response.json()
        if data.get("results"):
            assert len(data["results"]) <= 2

    @pytest.mark.asyncio
    async def test_search_empty_query(self, ingestor_client):
        search_payload = {"query": "", "top_k": 5}
        response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        assert response.status_code in [200, 400]


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestChatEndpoints:
    """Tests for chat completion API endpoints"""

    @pytest.mark.asyncio
    async def test_chat_completion_basic(self, langgraph_client):
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            "stream": False,
            "temperature": 0.1
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert data["choices"][0]["message"]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_chat_completion_invalid_payload(self, langgraph_client):
        payload = {"stream": False}
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_chat_streaming(self, langgraph_client):
        payload = {
            "messages": [
                {"role": "user", "content": "Tell me a short story."}
            ],
            "stream": True,
            "max_tokens": 50
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_with_tools(self, langgraph_client):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Get current time",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        
        payload = {
            "messages": [{"role": "user", "content": "What time is it?"}],
            "tools": tools,
            "stream": False,
            "max_tokens": 100
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestLLMEndpoints:
    """Tests for LLM API endpoints"""

    @pytest.mark.asyncio
    async def test_llm_chat_completion(self, llm_client):
        payload = {
            "model": "default",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        response = await llm_client.post(LLM.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert data["choices"][0]["message"]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_llm_streaming(self, llm_client):
        payload = {
            "model": "default",
            "messages": [{"role": "user", "content": "Count from 1 to 5"}],
            "stream": True,
            "max_tokens": 50
        }
        
        response = await llm_client.post(LLM.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestEmbeddingEndpoints:
    """Tests for embedding API endpoints"""

    @pytest.mark.asyncio
    async def test_embedding_generation(self, emb_client):
        payload = {
            "input": "This is a test sentence for embedding.",
            "model": "default"
        }
        
        response = await emb_client.post(Embedding.EMBEDDINGS, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert len(data["data"]) > 0
            assert "embedding" in data["data"][0]
            assert isinstance(data["data"][0]["embedding"], list)


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestMCPEndpoints:
    """Tests for MCP API endpoints"""

    @pytest.mark.asyncio
    async def test_mcp_tools_list(self, mcp_bash_client):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }

        response = await mcp_bash_client.post(MCP.MCP, json=payload)
        assert response.status_code == 200

        # MCP returns Server-Sent Events, parse the data line
        data = mcp_bash_client._parse_sse_response(response.text)
        assert "result" in data
        assert "tools" in data["result"]

    @pytest.mark.asyncio
    async def test_mcp_tool_call(self, mcp_bash_client):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "list_files",
                "arguments": {"path": "/tmp"}
            }
        }
        
        response = await mcp_bash_client.post(MCP.MCP, json=payload)
        assert response.status_code in [200, 400]


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestStatsEndpoints:
    """Tests for stats and overview endpoints"""

    @pytest.mark.asyncio
    async def test_ingestor_stats(self, ingestor_client):
        response = await ingestor_client.get(Ingestor.STATS)
        assert response.status_code == 200
        
        data = response.json()
        assert "chunks" in data or "file_summaries" in data

    @pytest.mark.asyncio
    async def test_ingestor_chunks_list(self, ingestor_client):
        response = await ingestor_client.get(Ingestor.CHUNKS)
        assert response.status_code == 200
        
        data = response.json()
        assert "chunks" in data or "total" in data

    @pytest.mark.asyncio
    async def test_ingestor_chunks_with_limit(self, ingestor_client):
        response = await ingestor_client.get(f"{Ingestor.CHUNKS}?limit=3")
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestErrorHandling:
    """Tests for API error handling"""

    @pytest.mark.asyncio
    async def test_invalid_endpoint(self, langgraph_client):
        response = await langgraph_client.get("/nonexistent_endpoint")
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_invalid_method(self, langgraph_client):
        response = await langgraph_client.post(LangGraph.HEALTH, json={})
        assert response.status_code in [200, 400, 404, 405]

    @pytest.mark.asyncio
    async def test_malformed_json(self, langgraph_client):
        response = await langgraph_client.post(
            LLM.CHAT_COMPLETIONS,
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_large_payload(self, langgraph_client):
        large_message = "A" * 10000
        
        payload = {
            "messages": [
                {"role": "user", "content": large_message}
            ],
            "stream": False,
            "max_tokens": 100
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code in [200, 400, 413]


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestConcurrentRequests:
    """Tests for concurrent API requests"""

    @pytest.mark.asyncio
    async def test_concurrent_chat_requests(self, langgraph_client):
        async def make_request(i):
            payload = {
                "messages": [
                    {"role": "user", "content": f"Test request {i}"}
                ],
                "stream": False,
                "max_tokens": 10
            }
            response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
            return response.status_code
        
        tasks = [make_request(i) for i in range(3)]
        responses = await asyncio.gather(*tasks)
        
        for status_code in responses:
            assert status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_search_requests(self, ingestor_client):
        async def make_search(q):
            payload = {"query": q, "top_k": 3}
            response = await ingestor_client.post(Ingestor.SEARCH, json=payload)
            return response.status_code
        
        queries = ["test", "python", "code"]
        tasks = [make_search(q) for q in queries]
        responses = await asyncio.gather(*tasks)
        
        for status_code in responses:
            assert status_code == 200
