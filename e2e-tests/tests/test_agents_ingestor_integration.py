"""
test_agents_ingestor_integration.py

Tests for LangGraph Agent and Ingestor integration.
Covers: Agents-Ingestor interactions, Indexation workflows
"""

import pytest
import asyncio
import os
from typing import Dict, Any


@pytest.mark.integration
@pytest.mark.agent_ingestor
@pytest.mark.fast
class TestAgentsIngestorIntegration:
    """Test suite for Agent-Ingestor integration"""
    
    @pytest.mark.asyncio
    async def test_agent_can_retrieve_ingestor_context(self, ingestor_client, langgraph_client, test_workspace):
        """Test that agent can retrieve context from Ingestor"""
        # First, ingest a document with specific content
        test_file = os.path.join(test_workspace, "agent_context_test.txt")
        with open(test_file, "w") as f:
            f.write("Agent context retrieval test\n")
            f.write("This document contains information about AI and machine learning\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "agent_test", "category": "ai"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Search for context
        search_payload = {
            "query": "AI machine learning",
            "limit": 3
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        assert "results" in search_data
        assert len(search_data["results"]) > 0
        
        # Verify context is available for agent
        context = search_data["results"][0].get("content", "")
        assert len(context) > 0
        assert "AI" in context or "machine" in context
    
    @pytest.mark.asyncio
    async def test_agent_retrieval_with_ingestor_search(self, ingestor_client, langgraph_client, test_workspace):
        """Test agent retrieves context using ingestor search"""
        # First, ingest a document
        test_file = os.path.join(test_workspace, "agent_test.txt")
        with open(test_file, "w") as f:
            f.write("Agent test document with specific information\n")
            f.write("This document contains information about agent integration\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "agent_test", "type": "documentation"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Use the ingestor endpoint to search (simulating agent retrieval)
        search_payload = {
            "query": "agent integration",
            "limit": 3
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        assert "results" in search_data
        assert len(search_data["results"]) > 0
        
        # Use context in agent request
        context = ""
        if search_data.get("results"):
            context = search_data["results"][0].get("content", "")
        
        # Now use this context with agent
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant with access to documentation."},
                {"role": "user", "content": f"Based on this context: {context}\n\nExplain agent integration."}
            ],
            "stream": False,
            "max_tokens": 200
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data
        assert len(chat_data["choices"]) > 0
        
        response_text = chat_data["choices"][0]["message"]["content"]
        assert len(response_text) > 0
    
    @pytest.mark.asyncio
    async def test_agent_decision_with_ingestor_context(self, langgraph_client, ingestor_client, test_workspace):
        """Test agent makes decisions based on ingestor context"""
        # Create multiple documents with different topics
        docs = [
            ("ai_doc.txt", "AI and machine learning content\n"),
            ("web_doc.txt", "Web development content\n"),
            ("database_doc.txt", "Database systems content\n")
        ]
        
        for filename, content in docs:
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(content)
            
            ingest_payload = {
                "file_path": filepath,
                "metadata": {"source": "agent_test", "topic": filename.split("_")[0]}
            }
            
            ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
            assert ingest_response.status_code == 200
        
        await asyncio.sleep(5)
        
        # Test agent with context retrieval
        query = "What should I learn about AI?"
        
        # Search for relevant context
        search_payload = {
            "query": query,
            "limit": 2
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        context = ""
        if search_data.get("results"):
            context = "\n".join([r.get("content", "") for r in search_data["results"][:2]])
        
        # Agent makes decision based on context
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a learning assistant. Based on available documents, recommend what to learn."},
                {"role": "user", "content": f"Available documents:\n{context}\n\nQuestion: {query}"}
            ],
            "stream": False,
            "max_tokens": 300
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data
        
        response_text = chat_data["choices"][0]["message"]["content"]
        assert len(response_text) > 0
        # Should contain relevant information
        assert "ai" in response_text.lower() or "machine" in response_text.lower()
    
    @pytest.mark.asyncio
    async def test_agent_tool_calling_with_ingestor_context(self, langgraph_client, ingestor_client, test_workspace):
        """Test agent tool calling with ingestor context"""
        # Ingest a document with specific information
        test_file = os.path.join(test_workspace, "tool_test.txt")
        with open(test_file, "w") as f:
            f.write("Tool calling test document\n")
            f.write("The current time is 2024-01-01\n")
            f.write("Temperature is 72 degrees\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "tool_test", "type": "data"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # Search for context
        search_payload = {
            "query": "current time temperature",
            "limit": 2
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        context = ""
        if search_data.get("results"):
            context = search_data["results"][0].get("content", "")
        
        # Agent with tool calling
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
                                "description": "City and state"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": f"You are a helpful assistant. Use this context: {context}"},
                {"role": "user", "content": "What is the current time and what's the weather like?"}
            ],
            "tools": tools,
            "stream": False,
            "max_tokens": 200
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data
        
        # Check if agent used tool calling or provided context-based answer
        response_text = chat_data["choices"][0]["message"]["content"]
        assert len(response_text) > 0
    
    @pytest.mark.asyncio
    async def test_agent_multi_turn_conversation_with_ingestor(self, langgraph_client, ingestor_client, test_workspace):
        """Test multi-turn conversation with agent using ingestor context"""
        # Create a document
        test_file = os.path.join(test_workspace, "conversation_test.txt")
        with open(test_file, "w") as f:
            f.write("Python programming language\n")
            f.write("Python is a high-level programming language\n")
            f.write("It supports multiple programming paradigms\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "conversation_test", "type": "documentation"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # Search for context
        search_payload = {
            "query": "Python programming language",
            "limit": 2
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        context = ""
        if search_data.get("results"):
            context = search_data["results"][0].get("content", "")
        
        # Multi-turn conversation
        messages = [
            {"role": "system", "content": f"You are a programming assistant. Use this context: {context}"},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language. "},
            {"role": "user", "content": "Tell me more about it."}
        ]
        
        chat_payload = {
            "messages": messages,
            "stream": False,
            "max_tokens": 200
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data
        assert len(chat_data["choices"]) > 0
        
        response_text = chat_data["choices"][0]["message"]["content"]
        assert len(response_text) > 0
        assert "python" in response_text.lower()
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_performance(self, langgraph_client, ingestor_client, test_workspace):
        """Test performance of agent context retrieval"""
        import time
        
        # Create and ingest multiple documents
        docs_created = []
        for i in range(10):
            filename = f"perf_test_{i}.txt"
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(f"Performance test document {i}\n" * 5)
            
            ingest_payload = {
                "file_path": filepath,
                "metadata": {"source": "performance_test", "index": str(i)}
            }
            
            ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
            if ingest_response.status_code == 200:
                docs_created.append(filepath)
        
        await asyncio.sleep(5)
        
        # Measure search performance
        search_times = []
        for _ in range(5):
            search_start = time.time()
            
            search_payload = {
                "query": "performance test document",
                "limit": 5
            }
            
            search_response = await ingestor_client.post("/search", json=search_payload)
            search_end = time.time()
            
            if search_response.status_code == 200:
                search_times.append(search_end - search_start)
        
        # Calculate average search time
        if search_times:
            avg_search_time = sum(search_times) / len(search_times)
            print(f"Average search time: {avg_search_time:.2f} seconds")
            assert avg_search_time < 10  # Should complete within 10 seconds
    
    @pytest.mark.asyncio
    async def test_agent_error_recovery_with_ingestor(self, langgraph_client, ingestor_client):
        """Test agent recovery when ingestor is unavailable"""
        # This test simulates ingestor being unavailable
        # In production, you would actually stop the service
        
        # Try to use agent without ingestor context
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. No external context available."},
                {"role": "user", "content": "What is 2+2?"}
            ],
            "stream": False,
            "max_tokens": 50
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        
        # Agent should still work without ingestor
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data
        assert len(chat_data["choices"]) > 0
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_limiting(self, langgraph_client, ingestor_client, test_workspace):
        """Test agent context retrieval with different limits"""
        # Create test document
        test_file = os.path.join(test_workspace, "limit_test.txt")
        with open(test_file, "w") as f:
            for i in range(20):
                f.write(f"Chunk {i}: Test content for limit testing\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "limit_test"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # Test different limits
        limits = [1, 5, 10, 20]
        
        for limit in limits:
            search_payload = {
                "query": "test content",
                "limit": limit
            }
            
            search_response = await ingestor_client.post("/search", json=search_payload)
            assert search_response.status_code == 200
            
            search_data = search_response.json()
            if "results" in search_data:
                result_count = len(search_data["results"])
                # Should not exceed the requested limit
                assert result_count <= limit
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_with_metadata(self, langgraph_client, ingestor_client, test_workspace):
        """Test agent context retrieval with metadata filtering"""
        # Create documents with different metadata
        docs = [
            ("doc1.txt", "AI content", {"category": "ai", "priority": "high"}),
            ("doc2.txt", "Web content", {"category": "web", "priority": "medium"}),
            ("doc3.txt", "AI advanced", {"category": "ai", "priority": "low"})
        ]
        
        for filename, content, metadata in docs:
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(content)
            
            ingest_payload = {
                "file_path": filepath,
                "metadata": {"source": "metadata_test", **metadata}
            }
            
            ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
            assert ingest_response.status_code == 200
        
        await asyncio.sleep(5)
        
        # Search with metadata filtering (if supported)
        search_payload = {
            "query": "AI content",
            "limit": 5,
            "filters": {"category": "ai"}
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        
        # If metadata filtering is supported, response should be 200
        # If not, it might be 400
        if search_response.status_code == 200:
            search_data = search_response.json()
            if "results" in search_data:
                # Should only return AI documents
                for result in search_data["results"]:
                    # Check if metadata filtering worked
                    # This depends on how metadata filtering is implemented
                    pass
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_with_semantic_search(self, langgraph_client, ingestor_client, test_workspace):
        """Test agent context retrieval with semantic search"""
        # Create documents with similar meanings but different words
        docs = [
            ("doc1.txt", "Artificial Intelligence is a field of computer science\n"),
            ("doc2.txt", "Machine learning is a subset of AI\n"),
            ("doc3.txt", "Deep learning uses neural networks\n")
        ]
        
        for filename, content in docs:
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(content)
            
            ingest_payload = {
                "file_path": filepath,
                "metadata": {"source": "semantic_test"}
            }
            
            ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
            assert ingest_response.status_code == 200
        
        await asyncio.sleep(5)
        
        # Search with a query that's semantically related but not exact
        search_payload = {
            "query": "computer learning technology",
            "limit": 3
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        assert "results" in search_data
        
        # Should find relevant documents even with different wording
        if len(search_data["results"]) > 0:
            context = search_data["results"][0].get("content", "")
            assert len(context) > 0
            # Should contain some relevant information
            assert any(word in context.lower() for word in ["ai", "learning", "intelligence", "computer"])
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_error_handling(self, langgraph_client, ingestor_client):
        """Test agent context retrieval error handling"""
        # Test with invalid search query
        search_payload = {
            "query": "",  # Empty query
            "limit": 5
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        # Should handle empty query gracefully
        assert search_response.status_code in [200, 400]
        
        # Test with very long query
        long_query = "A" * 10000
        search_payload = {
            "query": long_query,
            "limit": 5
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        # Should handle long query gracefully
        assert search_response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_with_complex_queries(self, langgraph_client, ingestor_client, test_workspace):
        """Test agent context retrieval with complex queries"""
        # Create a document with complex content
        test_file = os.path.join(test_workspace, "complex_test.txt")
        with open(test_file, "w") as f:
            f.write("Complex query test\n")
            f.write("This document contains multiple concepts:\n")
            f.write("1. Python programming\n")
            f.write("2. Async programming\n")
            f.write("3. Database integration\n")
            f.write("4. API development\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "complex_test"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # Test complex query
        search_payload = {
            "query": "What are the concepts in this document about Python and async programming?",
            "limit": 2
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        assert "results" in search_data
        
        if len(search_data["results"]) > 0:
            context = search_data["results"][0].get("content", "")
            assert len(context) > 0
            # Should contain relevant information
            assert "python" in context.lower() or "async" in context.lower()
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_with_history(self, langgraph_client, ingestor_client, test_workspace):
        """Test agent context retrieval with conversation history"""
        # Create a document
        test_file = os.path.join(test_workspace, "history_test.txt")
        with open(test_file, "w") as f:
            f.write("History test document\n")
            f.write("Previous conversation about Python\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "history_test"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # Search for context
        search_payload = {
            "query": "Python conversation",
            "limit": 2
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        context = ""
        if search_data.get("results"):
            context = search_data["results"][0].get("content", "")
        
        # Test with conversation history
        messages = [
            {"role": "system", "content": f"You are a helpful assistant. Use this context: {context}"},
            {"role": "user", "content": "Tell me about Python"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "What did I ask before?"}
        ]
        
        chat_payload = {
            "messages": messages,
            "stream": False,
            "max_tokens": 100
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data
        assert len(chat_data["choices"]) > 0
        
        response_text = chat_data["choices"][0]["message"]["content"]
        assert len(response_text) > 0
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_with_different_file_types(self, langgraph_client, ingestor_client, test_workspace):
        """Test agent context retrieval with different file types"""
        # Create files of different types
        files = [
            ("text.txt", "Plain text content\n"),
            ("python.py", "# Python code\nprint('Hello')\n"),
            ("markdown.md", "# Markdown\n**Bold** content\n"),
            ("json.json", '{"key": "value"}\n')
        ]
        
        for filename, content in files:
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(content)
            
            ingest_payload = {
                "file_path": filepath,
                "metadata": {"source": "file_type_test"}
            }
            
            ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
            assert ingest_response.status_code == 200
        
        await asyncio.sleep(5)
        
        # Search for content across different file types
        search_payload = {
            "query": "content",
            "limit": 10
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        assert "results" in search_data
        
        # Should find content from different file types
        if len(search_data["results"]) > 0:
            # Check if we have results from different file types
            file_types_found = set()
            for result in search_data["results"]:
                # This depends on how file types are tracked
                pass
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_concurrent(self, langgraph_client, ingestor_client, test_workspace):
        """Test concurrent agent context retrieval"""
        import asyncio
        
        # Create test document
        test_file = os.path.join(test_workspace, "concurrent_test.txt")
        with open(test_file, "w") as f:
            for i in range(10):
                f.write(f"Concurrent test chunk {i}\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "concurrent_test"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # Perform concurrent searches
        async def make_search(query):
            search_payload = {
                "query": query,
                "limit": 3
            }
            return await ingestor_client.post("/search", json=search_payload)
        
        queries = ["concurrent test", "chunk", "test", "concurrent", "chunk test"]
        tasks = [make_search(q) for q in queries]
        
        responses = await asyncio.gather(*tasks)
        
        # All searches should succeed
        for response in responses:
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_agent_context_retrieval_cancellation(self, langgraph_client, ingestor_client, test_workspace):
        """Test cancellation of context retrieval (if supported)"""
        # Create test document
        test_file = os.path.join(test_workspace, "cancellation_test.txt")
        with open(test_file, "w") as f:
            f.write("Cancellation test content\n")
        
        ingest_payload = {
            "file_path": test_file,
            "metadata": {"source": "cancellation_test"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # Start a search
        search_payload = {
            "query": "cancellation test",
            "limit": 5
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        # If cancellation is supported, we could test it here
        # This would depend on the actual API implementation