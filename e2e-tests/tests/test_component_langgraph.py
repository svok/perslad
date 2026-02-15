import asyncio

import pytest

from infra.config import LangGraph


@pytest.mark.component
@pytest.mark.integration
@pytest.mark.fast
class TestLangGraphComponent:
    """Component tests for LangGraph agent service"""
    
    @pytest.mark.asyncio
    async def test_langgraph_health(self, langgraph_client):
        """Test that langgraph agent is healthy"""
        response = await langgraph_client.get(LangGraph.HEALTH)
        if response.status_code == 404:
            # Try alternative health endpoint
            response = await langgraph_client.get(LangGraph.ROOT)
        
        assert response.status_code == 200
        
        # Check response structure
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            if "status" in data:
                assert data["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_langgraph_chat_completion(self, langgraph_client):
        """Test basic chat completion through langgraph agent"""
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
        
        message = data["choices"][0]["message"]
        assert message["role"] == "assistant"
        assert len(message["content"]) > 0
    
    @pytest.mark.asyncio
    async def test_langgraph_streaming_chat(self, langgraph_client):
        """Test streaming chat completion"""
        payload = {
            "messages": [
                {"role": "user", "content": "Count from 1 to 3"}
            ],
            "stream": True,
            "max_tokens": 50
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        # TODO: Implement proper streaming test with httpx stream context manager
        assert response.status_code == 200
        # Skip streaming verification for now
    
    @pytest.mark.asyncio
    async def test_langgraph_with_tools(self, langgraph_client):
        """Test langgraph agent with tool usage"""
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant with file system access."},
                {"role": "user", "content": "List files in /workspace directory"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "list_files",
                        "description": "List files in a directory",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "directory": {
                                    "type": "string",
                                    "description": "Directory path"
                                }
                            },
                            "required": ["directory"]
                        }
                    }
                }
            ],
            "stream": False
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
    
    @pytest.mark.asyncio
    async def test_langgraph_multi_turn_conversation(self, langgraph_client):
        """Test multi-turn conversation"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "Why is it popular?"}
        ]
        
        payload = {
            "messages": messages,
            "stream": False
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
    
    @pytest.mark.asyncio
    async def test_langgraph_system_message(self, langgraph_client):
        """Test with custom system message"""
        payload = {
            "messages": [
                {"role": "system", "content": "You are a technical writer. Write concise explanations."},
                {"role": "user", "content": "Explain quantum computing"}
            ],
            "max_tokens": 100
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        
        content = data["choices"][0]["message"]["content"]
        assert len(content) > 0
    
    @pytest.mark.asyncio
    async def test_langgraph_temperature_control(self, langgraph_client):
        """Test different temperature settings"""
        messages = [
            {"role": "user", "content": "Write a creative story about a robot"}
        ]
        
        # Low temperature (deterministic)
        payload_low = {
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 100
        }
        
        response_low = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload_low)
        assert response_low.status_code == 200
        
        # High temperature (creative)
        payload_high = {
            "messages": messages,
            "temperature": 0.9,
            "max_tokens": 100
        }
        
        response_high = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload_high)
        assert response_high.status_code == 200
    
    @pytest.mark.asyncio
    async def test_langgraph_max_tokens(self, langgraph_client):
        """Test max tokens limit"""
        payload = {
            "messages": [
                {"role": "user", "content": "Write a long explanation of machine learning"}
            ],
            "max_tokens": 50,
            "stream": False
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        
        content = data["choices"][0]["message"]["content"]
        # Check that response is reasonably short
        assert len(content.split()) < 20  # Rough estimate
    
    @pytest.mark.asyncio
    async def test_langgraph_error_handling(self, langgraph_client):
        """Test error handling for invalid requests"""
        # Missing messages
        payload = {
            "stream": False
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code in [400, 422]
        
        # Empty messages
        payload = {
            "messages": [],
            "stream": False
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_langgraph_performance(self, langgraph_client):
        """Test response time performance"""
        import time
        
        messages = [
            {"role": "user", "content": "What is 1+1?"}
        ]
        
        payload = {
            "messages": messages,
            "stream": False,
            "max_tokens": 50
        }
        
        start_time = time.time()
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        
        # Should respond within reasonable time (adjust threshold as needed)
        assert response_time < 60, f"Response took {response_time} seconds"
    
    @pytest.mark.asyncio
    async def test_langgraph_context_window(self, langgraph_client):
        """Test handling of different context lengths"""
        # Create a long context
        long_context = "This is a test message. " * 20  # 20 repetitions
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize the following: {long_context}"}
        ]
        
        payload = {
            "messages": messages,
            "max_tokens": 100,
            "stream": False
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        # Should handle gracefully - either success or meaningful error
        assert response.status_code in [200, 400, 413]
    
    @pytest.mark.asyncio
    async def test_langgraph_usage_metrics(self, langgraph_client):
        """Test that usage metrics are returned"""
        payload = {
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "stream": False
        }
        
        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        if "usage" in data:
            usage = data["usage"]
            assert "prompt_tokens" in usage
            assert "completion_tokens" in usage
            assert "total_tokens" in usage
    
    @pytest.mark.asyncio
    async def test_langgraph_parallel_requests(self, langgraph_client):
        """Test handling multiple parallel requests"""
        async def make_request(index):
            payload = {
                "messages": [
                    {"role": "user", "content": f"Test message {index}"}
                ],
                "stream": False,
                "max_tokens": 20
            }
            
            return await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        
        # Make multiple concurrent requests
        tasks = [make_request(i) for i in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # Check all succeeded
        for response in responses:
            assert response.status_code == 200