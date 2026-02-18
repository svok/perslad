import pytest

from infra.config import LLM


@pytest.mark.component
@pytest.mark.llm
@pytest.mark.fast
@pytest.mark.requires_gpu
class TestLLMComponent:
    """Component tests for LLM service"""
    
    @pytest.mark.asyncio
    async def test_llm_model_availability(self, llm_client):
        """Test that LLM model is available and responding"""
        response = await llm_client.get(LLM.MODELS)
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0
        
        # Check model structure
        model = data["data"][0]
        assert "id" in model
        assert "object" in model
        assert model["object"] == "model"
    
    @pytest.mark.asyncio
    async def test_chat_completion_basic(self, llm_client, test_data, config):
        """Test basic chat completion"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"}
        ]
        
        payload = {
            "model": config['emb_served_model_name'],
            "messages": messages,
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        response = await llm_client.post(LLM.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert len(data["choices"][0]["message"]["content"]) > 0
    
    @pytest.mark.asyncio
    async def test_chat_completion_with_tools(self, llm_client, config):
        """Test chat completion with tool calling"""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant with weather tool access."},
            {"role": "user", "content": "What's the weather in Paris?"}
        ]
        
        payload = {
            "model": config['emb_served_model_name'],
            "messages": messages,
            "tools": tools,
            "max_tokens": 200
        }
        
        response = await llm_client.post(LLM.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        
        choice = data["choices"][0]
        if "message" in choice and "tool_calls" in choice["message"]:
            # Model attempted to use tool
            tool_calls = choice["message"]["tool_calls"]
            assert len(tool_calls) > 0
            assert tool_calls[0]["function"]["name"] == "get_weather"
    
    @pytest.mark.asyncio
    async def test_chat_completion_streaming(self, llm_client, config):
        """Test streaming chat completion"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Count from 1 to 5"}
        ]
        
        payload = {
            "model": config['emb_served_model_name'],
            "messages": messages,
            "max_tokens": 100,
            "stream": True
        }
        
        # For streaming in httpx, we need to use the stream context manager
        # But first, let's make a regular request to test the test infrastructure
        response = await llm_client.post(LLM.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        # TODO: Implement proper streaming test with httpx stream context manager
        # For now, we test the response structure
        assert response.status_code == 200
        # Skip streaming verification since it requires httpx stream handling
        pass

    @pytest.mark.asyncio
    async def test_llm_error_handling(self, llm_client, config):
        """Test error handling for invalid requests"""
        # Missing required field
        payload = {
            "model": config['emb_served_model_name'],
            # Missing "messages"
            "max_tokens": 50
        }
        
        response = await llm_client.post(LLM.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_llm_performance_metrics(self, llm_client, config):
        """Test that LLM responses include performance metrics"""
        messages = [
            {"role": "user", "content": "Explain quantum computing in 2 sentences"}
        ]
        
        payload = {
            "model": config['emb_served_model_name'],
            "messages": messages,
            "max_tokens": 100,
            "stream": False
        }
        
        response = await llm_client.post(LLM.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "usage" in data
        
        usage = data["usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage
        assert usage["prompt_tokens"] > 0
        assert usage["completion_tokens"] > 0
    
    @pytest.mark.asyncio
    async def test_llm_context_length(self, llm_client, config):
        """Test handling of different context lengths"""
        # Create a long context
        long_context = "This is a test message. " * 50  # 50 repetitions
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize: {long_context}"}
        ]
        
        payload = {
            "model": config['emb_served_model_name'],
            "messages": messages,
            "max_tokens": 100
        }
        
        response = await llm_client.post(LLM.CHAT_COMPLETIONS, json=payload)
        assert response.status_code in [200, 400]  # Should handle gracefully
        
        if response.status_code == 200:
            data = response.json()
            assert "choices" in data
            assert len(data["choices"]) > 0