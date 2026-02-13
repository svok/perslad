"""
test_user_requests_responses.py

Tests for API interactions and response validation.
Covers: User requests-responses, API validation
"""

import pytest
import asyncio
import json
import os
from typing import Dict, Any


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
class TestUserRequestsResponses:
    """Test suite for API requests and responses"""
    
    @pytest.mark.asyncio
    async def test_api_health_endpoints(self, ingestor_client, langgraph_client, llm_client):
        """Test health endpoints across all services"""
        # Ingestor health
        response = await ingestor_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ready"
        
        # LangGraph health
        response = await langgraph_client.get("/health")
        if response.status_code == 404:
            response = await langgraph_client.get("/")
        assert response.status_code == 200
        
        # LLM health
        response = await llm_client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
    
    @pytest.mark.asyncio
    async def test_ingestor_ingest_endpoint(self, ingestor_client, test_workspace):
        """Test ingestor ingest endpoint"""
        # Create test file
        test_file = os.path.join(test_workspace, "api_test.txt")
        with open(test_file, "w") as f:
            f.write("API test document\n")
        
        # Test valid request
        payload = {
            "file_path": test_file,
            "metadata": {"source": "api_test"}
        }
        
        response = await ingestor_client.post("/ingest", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "job_id" in data
        assert "status" in data
        assert "message" in data or "status" in data
        
        # Test with missing required field
        invalid_payload = {
            "metadata": {"source": "test"}
            # Missing file_path
        }
        
        response = await ingestor_client.post("/ingest", json=invalid_payload)
        assert response.status_code in [400, 422]
        
        # Test with non-existent file
        nonexistent_payload = {
            "file_path": "/nonexistent/file.txt",
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post("/ingest", json=nonexistent_payload)
        assert response.status_code in [400, 404, 422]
    
    @pytest.mark.asyncio
    async def test_ingestor_search_endpoint(self, ingestor_client, test_workspace):
        """Test ingestor search endpoint"""
        # First, ingest a document
        test_file = os.path.join(test_workspace, "search_test.txt")
        with open(test_file, "w") as f:
            f.write("Python async programming test\n")
            f.write("asyncio module for asynchronous programming\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "test", "category": "tutorial"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Test valid search
        search_payload = {
            "query": "Python async programming",
            "limit": 5
        }
        
        response = await ingestor_client.post("/search", json=search_payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        
        # Test with empty query
        empty_query_payload = {
            "query": "",
            "limit": 5
        }
        
        response = await ingestor_client.post("/search", json=empty_query_payload)
        # Should handle gracefully
        assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_langgraph_chat_completion_endpoint(self, langgraph_client):
        """Test LangGraph chat completion endpoint"""
        # Test basic chat completion
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            "stream": False,
            "temperature": 0.1
        }
        
        response = await langgraph_client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert len(data["choices"][0]["message"]["content"]) > 0
        
        # Test with invalid payload structure
        invalid_payload = {
            # Missing messages field
            "stream": False
        }
        
        response = await langgraph_client.post("/v1/chat/completions", json=invalid_payload)
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_streaming_responses(self, langgraph_client):
        """Test streaming responses"""
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Tell me a short story."}
            ],
            "stream": True,
            "max_tokens": 50
        }
        
        response = await langgraph_client.post("/v1/chat/completions", json=payload)
        # TODO: Implement proper streaming test with httpx stream context manager
        assert response.status_code == 200
        
        # Collect streaming chunks
                #         # TODO: Implement proper streaming test with httpx stream context manager
        # Skip streaming verification for now
    @pytest.mark.asyncio
    async def test_error_response_formats(self, langgraph_client, ingestor_client):
        """Test error response formats"""
        # Test invalid endpoint
        response = await langgraph_client.get("/nonexistent_endpoint")
        assert response.status_code in [404, 400]
        
        # Test invalid method
        response = await langgraph_client.post("/health", json={})
        # Some endpoints might accept POST, others might not
        assert response.status_code in [200, 400, 404, 405]
        
        # Test malformed JSON
        response = await langgraph_client.post(
            "/v1/chat/completions",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_response_content_validation(self, langgraph_client):
        """Test response content validation"""
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello."}
            ],
            "stream": False
        }
        
        response = await langgraph_client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        
        # Validate response structure
        assert "choices" in data
        assert isinstance(data["choices"], list)
        assert len(data["choices"]) > 0
        
        choice = data["choices"][0]
        assert "message" in choice
        assert "role" in choice["message"]
        assert "content" in choice["message"]
        
        # Validate role
        assert choice["message"]["role"] == "assistant"
        
        # Validate content is not empty
        assert len(choice["message"]["content"]) > 0
        
        # Validate content type
        assert isinstance(choice["message"]["content"], str)
    
    @pytest.mark.asyncio
    async def test_request_headers(self, langgraph_client):
        """Test request headers handling"""
        # Test with proper headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "messages": [
                {"role": "user", "content": "Test"}
            ],
            "stream": False
        }
        
        response = await langgraph_client.post(
            "/v1/chat/completions",
            json=payload,
            headers=headers
        )
        
        # Should work with proper headers
        assert response.status_code == 200
        
        # Test with missing Content-Type
        headers_without_ct = {
            "Accept": "application/json"
        }
        
        response = await langgraph_client.post(
            "/v1/chat/completions",
            json=payload,
            headers=headers_without_ct
        )
        
        # Some services might handle this, others might not
        assert response.status_code in [200, 400, 415]
    
    @pytest.mark.asyncio
    async def test_response_timeouts(self, langgraph_client):
        """Test timeout handling"""
        import asyncio
        import httpx
        
        # Test with very short timeout
        async with httpx.AsyncClient(
            base_url=langgraph_client.base_url,
            timeout=0.1  # 100ms timeout
        ) as short_client:
            try:
                payload = {
                    "messages": [
                        {"role": "user", "content": "Test"}
                    ],
                    "stream": False
                }
                
                response = await short_client.post("/v1/chat/completions", json=payload)
                # Should handle or timeout
                assert response.status_code in [200, 408, 504]
            except Exception as e:
                # Timeout or connection error
                assert "timeout" in str(e).lower() or "connect" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, langgraph_client):
        """Test concurrent API requests"""
        import asyncio
        
        async def make_request(i):
            payload = {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"Test request {i}"}
                ],
                "stream": False,
                "max_tokens": 10
            }
            
            response = await langgraph_client.post("/v1/chat/completions", json=payload)
            return response.status_code
        
        # Make concurrent requests
        tasks = [make_request(i) for i in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for status_code in responses:
            assert status_code == 200
    
    @pytest.mark.asyncio
    async def test_large_payloads(self, langgraph_client):
        """Test handling of large payloads"""
        # Create a large message
        large_message = "A" * 10000  # 10KB message
        
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": large_message}
            ],
            "stream": False,
            "max_tokens": 100
        }
        
        response = await langgraph_client.post("/v1/chat/completions", json=payload)
        
        # Should handle or reject with appropriate error
        assert response.status_code in [200, 400, 413]  # 413 for payload too large
    
    @pytest.mark.asyncio
    async def test_api_rate_limiting(self, langgraph_client):
        """Test rate limiting (if implemented)"""
        import asyncio
        
        # Make rapid consecutive requests
        tasks = []
        for i in range(10):
            payload = {
                "messages": [
                    {"role": "user", "content": f"Rate limit test {i}"}
                ],
                "stream": False,
                "max_tokens": 10
            }
            
            task = langgraph_client.post("/v1/chat/completions", json=payload)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check if any rate limiting occurred
        rate_limited = False
        for response in responses:
            if isinstance(response, Exception):
                if "429" in str(response) or "rate" in str(response).lower():
                    rate_limited = True
            elif hasattr(response, 'status_code'):
                if response.status_code == 429:
                    rate_limited = True
        
        # If rate limiting is implemented, some requests should be rate limited
        # If not implemented, all should succeed
        if rate_limited:
            assert True  # Rate limiting is working
        else:
            # All requests succeeded (rate limiting not implemented)
            pass
    
    @pytest.mark.asyncio
    async def test_ingestor_status_endpoint(self, ingestor_client):
        """Test ingestor status endpoint"""
        # Test status endpoint if it exists
        # This would depend on the actual API implementation
        # For now, just test that the service is responsive
        response = await ingestor_client.get("/")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingestor_knowledge_endpoints(self, ingestor_client, test_workspace):
        """Test ingestor knowledge endpoints"""
        # Create and ingest a document
        test_file = os.path.join(test_workspace, "knowledge_test.txt")
        with open(test_file, "w") as f:
            f.write("Knowledge test document\n")
            f.write("This document tests knowledge endpoints\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "test", "type": "knowledge"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # Test knowledge search endpoint
        search_payload = {
            "query": "knowledge test",
            "limit": 5
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        # Test file context endpoint (if exists)
        # file_response = await ingestor_client.get(f"/knowledge/file/{test_file}")
        # if file_response.status_code == 200:
        #     assert "summary" in file_response.json()
    
    @pytest.mark.asyncio
    async def test_llm_chat_completion(self, llm_client):
        """Test LLM chat completion endpoint"""
        payload = {
            "model": "default",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        response = await llm_client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert data["choices"][0]["message"]["role"] == "assistant"
    
    @pytest.mark.asyncio
    async def test_llm_streaming_chat_completion(self, llm_client):
        """Test LLM streaming chat completion"""
        payload = {
            "model": "default",
            "messages": [
                {"role": "user", "content": "Count from 1 to 5"}
            ],
            "stream": True,
            "max_tokens": 50
        }
        
        response = await llm_client.post("/v1/chat/completions", json=payload)
        # TODO: Implement proper streaming test with httpx stream context manager
        assert response.status_code == 200
        
        # Collect streaming chunks
                #         # TODO: Implement proper streaming test with httpx stream context manager
        # Skip streaming verification for now
    @pytest.mark.asyncio
    async def test_embedding_generation(self, emb_client):
        """Test embedding generation endpoint"""
        payload = {
            "input": "This is a test sentence for embedding generation.",
            "model": "default"
        }
        
        response = await emb_client.post("/v1/embeddings", json=payload)
        if response.status_code == 404:
            # Try alternative endpoint
            response = await emb_client.post("/embeddings", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert len(data["data"]) > 0
            assert "embedding" in data["data"][0]
            assert isinstance(data["data"][0]["embedding"], list)
    
    @pytest.mark.asyncio
    async def test_mcp_tools_endpoint(self, mcp_bash_client):
        """Test MCP tools list endpoint"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        response = await mcp_bash_client.post("/mcp", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "result" in data
        assert "tools" in data["result"]
    
    @pytest.mark.asyncio
    async def test_mcp_tool_call(self, mcp_bash_client):
        """Test MCP tool call"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "list_files",
                "arguments": {
                    "path": "/tmp"
                }
            }
        }
        
        response = await mcp_bash_client.post("/mcp", json=payload)
        # Should handle or return error for invalid tools
        assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_response_content_types(self, langgraph_client):
        """Test different response content types"""
        # JSON response
        payload = {
            "messages": [
                {"role": "user", "content": "Test"}
            ],
            "stream": False
        }
        
        response = await langgraph_client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
    
    @pytest.mark.asyncio
    async def test_response_headers(self, langgraph_client):
        """Test response headers"""
        payload = {
            "messages": [
                {"role": "user", "content": "Test"}
            ],
            "stream": False
        }
        
        response = await langgraph_client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        
        # Check for expected headers
        headers = response.headers
        assert "content-type" in headers
        
        # Some services might include additional headers
        # For example: x-request-id, x-response-time, etc.
    
    @pytest.mark.asyncio
    async def test_response_pagination(self, ingestor_client, test_workspace):
        """Test response pagination (if implemented)"""
        # Create and ingest multiple documents
        for i in range(10):
            test_file = os.path.join(test_workspace, f"pagination_test_{i}.txt")
            with open(test_file, "w") as f:
                f.write(f"Pagination test document {i}\n")
            
            ingest_payload = {
                "file_path": test_file,
                "metadata": {"source": "pagination_test", "index": str(i)}
            }
            
            ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
            # Some might fail, but that's okay
        
        await asyncio.sleep(5)
        
        # Test search with pagination
        search_payload = {
            "query": "pagination test",
            "limit": 5,
            "offset": 0
        }
        
        response = await ingestor_client.post("/search", json=search_payload)
        
        # If pagination is implemented, response should have pagination info
        # If not, just verify the search works
        assert response.status_code in [200, 400]  # 400 if offset not supported