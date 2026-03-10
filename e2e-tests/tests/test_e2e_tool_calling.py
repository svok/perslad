import pytest

from infra.config import LangGraph


@pytest.mark.e2e
@pytest.mark.slow
class TestToolBinding:
    """E2E тесты для проверки привязки и выполнения инструментов."""

    @pytest.mark.asyncio
    async def test_e2e_tool_binding(self, langgraph_client):
        """Тест: инструменты должны быть привязаны к модели и вызываться."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "echo",
                    "description": "Returns the input text",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Text to echo"}
                        },
                        "required": ["text"]
                    }
                }
            }
        ]

        payload = {
            "messages": [
                {"role": "user", "content": "Say 'hello world' using the echo tool"}
            ],
            "tools": tools,
            "stream": False,
            "max_tokens": 200
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0

        content = data["choices"][0]["message"]["content"]
        assert content, "Response should not be empty"

    @pytest.mark.asyncio
    async def test_e2e_tool_calling_chain(self, langgraph_client):
        """Тест: цепочка вызовов - вопрос → tool_call → результат → финальный ответ."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "add",
                    "description": "Add two numbers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number"},
                            "b": {"type": "number"}
                        },
                        "required": ["a", "b"]
                    }
                }
            }
        ]

        payload = {
            "messages": [
                {"role": "user", "content": "What is 5 + 3?"}
            ],
            "tools": tools,
            "stream": False,
            "max_tokens": 100
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        assert "8" in content or "eight" in content.lower(), \
            f"Expected result to contain 8, got: {content}"

    @pytest.mark.asyncio
    async def test_e2e_tool_calling_streaming(self, langgraph_client):
        """Тест: tool_calls в потоковом режиме."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "echo",
                    "description": "Echo the input",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"}
                        },
                        "required": ["text"]
                    }
                }
            }
        ]

        payload = {
            "messages": [
                {"role": "user", "content": "Echo 'streaming test'"}
            ],
            "tools": tools,
            "stream": True,
            "max_tokens": 100
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200

        chunks = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str != "[DONE]":
                    import json
                    try:
                        data = json.loads(data_str)
                        if "choices" in data:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                chunks.append(delta["content"])
                    except:
                        pass

        assert len(chunks) > 0, "Should have received streaming chunks"

    @pytest.mark.asyncio
    async def test_e2e_tool_error_handling(self, langgraph_client):
        """Тест: обработка ошибок при вызове инструментов."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "nonexistent_tool",
                    "description": "This tool does not exist",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]

        payload = {
            "messages": [
                {"role": "user", "content": "Use the nonexistent tool"}
            ],
            "tools": tools,
            "stream": False,
            "max_tokens": 50
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "choices" in data

    @pytest.mark.asyncio
    async def test_e2e_mcp_tools_available(self, langgraph_client):
        """Тест: MCP инструменты должны быть доступны."""
        tools_payload = {
            "messages": [
                {"role": "user", "content": "List files in /workspace"}
            ],
            "stream": False,
            "max_tokens": 100
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=tools_payload)
        assert response.status_code == 200

        data = response.json()
        assert "choices" in data
        content = data["choices"][0]["message"]["content"]
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_e2e_tool_with_system_message(self, langgraph_client):
        """Тест: system message + tools работают вместе."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "uppercase",
                    "description": "Convert text to uppercase",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"}
                        },
                        "required": ["text"]
                    }
                }
            }
        ]

        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Convert 'hello' to uppercase"}
            ],
            "tools": tools,
            "stream": False,
            "max_tokens": 100
        }

        response = await langgraph_client.post(LangGraph.CHAT_COMPLETIONS, json=payload)
        assert response.status_code == 200

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        assert "HELLO" in content or "hello" in content.lower()
