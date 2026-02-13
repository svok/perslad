import pytest
import httpx
import json
import asyncio
import os
import tempfile
from typing import Dict, Any

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.requires_gpu
class TestE2EFullWorkflow:
    """End-to-end tests for complete system workflows"""
    
    @pytest.mark.asyncio
    async def test_e2e_file_ingestion_to_search(self, ingestor_client, langgraph_client, test_workspace, clean_database):
        """Complete workflow: ingest file -> search -> chat with context"""
        
        # 1. Create a test document with specific content
        test_file = os.path.join(test_workspace, "programming_guide.md")
        content = """
# Python Programming Guide

## Async Programming
Python's asyncio module provides a framework for asynchronous programming.
It uses the async/await syntax for writing coroutines.

Key components:
- Event loop
- Coroutines
- Tasks
- Futures

## Example: Async HTTP Request
```python
import aiohttp
import asyncio

async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()
```

## Database Integration
When working with databases, you can use asyncpg for PostgreSQL:
- Connection pooling
- Prepared statements
- Async operations
"""
        
        with open(test_file, "w") as f:
            f.write(content)
        
        # 2. Ingest the file
        ingest_payload = {
            "file_path": test_file,
            "metadata": {
                "source": "e2e_test",
                "category": "programming",
                "language": "python"
            }
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        ingest_data = ingest_response.json()
        job_id = ingest_data.get("job_id")
        assert job_id
        
        # 3. Wait for ingestion to complete
        await asyncio.sleep(5)
        
        # 4. Search for the ingested content
        search_payload = {
            "query": "Python async programming asyncio",
            "limit": 5
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        assert "results" in search_data
        
        # Should find relevant chunks
        assert len(search_data["results"]) > 0
        
        # 5. Use search results in chat conversation
        context = ""
        if search_data["results"]:
            # Use first result as context
            context = search_data["results"][0].get("content", "")
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant with access to documentation."},
                {"role": "user", "content": f"Based on this context: {context}\n\nHow do I start with async programming in Python?"}
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
        # Should contain relevant information
        assert "async" in response_text.lower() or "await" in response_text.lower()
    
    @pytest.mark.asyncio
    async def test_e2e_code_analysis_workflow(self, ingestor_client, langgraph_client, test_workspace, clean_database):
        """Complete workflow: ingest code -> analyze -> generate documentation"""
        
        # 1. Create a Python module
        code_file = os.path.join(test_workspace, "user_manager.py")
        code_content = '''
class UserManager:
    """User management class"""
    
    def __init__(self):
        self.users = {}
    
    def add_user(self, user_id, name, email):
        """Add a new user"""
        if user_id in self.users:
            return False
        self.users[user_id] = {
            "name": name,
            "email": email,
            "created_at": "2024-01-01"
        }
        return True
    
    def get_user(self, user_id):
        """Get user by ID"""
        return self.users.get(user_id)
    
    def list_users(self):
        """List all users"""
        return list(self.users.values())
'''
        
        with open(code_file, "w") as f:
            f.write(code_content)
        
        # 2. Ingest the code
        ingest_payload = {
            "file_path": code_file,
            "metadata": {
                "source": "e2e_test",
                "type": "code",
                "language": "python"
            }
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        # 3. Wait for processing
        await asyncio.sleep(3)
        
        # 4. Search for code patterns
        search_payload = {
            "query": "UserManager class methods",
            "limit": 3
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        
        # 5. Generate documentation using found code
        context = ""
        if search_data.get("results"):
            context = "\n".join([r.get("content", "") for r in search_data["results"][:2]])
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a technical documentation writer. Generate clear documentation."},
                {"role": "user", "content": f"Generate documentation for this code:\n{context}"}
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
        
        # Should contain documentation elements
        assert "UserManager" in response_text or "user" in response_text.lower()
    
    @pytest.mark.asyncio
    async def test_e2e_multi_component_interaction(self, ingestor_client, langgraph_client, mcp_bash_client, test_workspace, clean_database):
        """Test interaction between multiple components"""
        
        # 1. Create multiple file types
        files_created = []
        
        # Python file
        py_file = os.path.join(test_workspace, "math_utils.py")
        with open(py_file, "w") as f:
            f.write('''
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
''')
        files_created.append(py_file)
        
        # Markdown file
        md_file = os.path.join(test_workspace, "readme.md")
        with open(md_file, "w") as f:
            f.write("# Math Utilities\n\nBasic arithmetic operations.\n")
        files_created.append(md_file)
        
        # 2. Ingest all files
        for filepath in files_created:
            ingest_payload = {
                "file_path": filepath,
                "metadata": {"source": "e2e_test"}
            }
            
            response = await ingestor_client.post("/ingest", json=ingest_payload)
            assert response.status_code == 200
        
        # 3. Wait for ingestion
        await asyncio.sleep(4)
        
        # 4. Search for mathematical operations
        search_payload = {
            "query": "mathematical operations addition multiplication",
            "limit": 3
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        
        # 5. Use MCP to check file system
        mcp_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "list_files",
                "arguments": {
                    "path": test_workspace
                }
            }
        }
        
        mcp_response = await mcp_bash_client.post("/mcp", json=mcp_payload)
        # Mainly checking interaction doesn't break
        
        # 6. Chat with context from both search and MCP
        context = ""
        if search_data.get("results"):
            context = search_data["results"][0].get("content", "")
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant with access to math utilities documentation."},
                {"role": "user", "content": f"Based on available math functions: {context}\n\nHow do I multiply numbers?"}
            ],
            "stream": False,
            "max_tokens": 150
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        assert chat_response.status_code == 200
        
        chat_data = chat_response.json()
        assert "choices" in chat_data
        assert len(chat_data["choices"]) > 0
    
    @pytest.mark.asyncio
    async def test_e2e_rag_workflow(self, ingestor_client, langgraph_client, test_workspace, clean_database):
        """Test RAG (Retrieval-Augmented Generation) workflow"""
        
        # 1. Create technical documentation
        tech_doc = os.path.join(test_workspace, "tech_doc.md")
        content = """
# System Architecture

## Components

### LLM Engine
The LLM engine uses vLLM for efficient inference.
It supports:
- Batch processing
- Model parallelism
- Streaming responses

### Embedding Engine
The embedding engine generates vector representations.
Models: BGE, OpenAI embeddings

### Vector Database
We use PostgreSQL with pgvector for:
- Similarity search
- Metadata storage
- Filtering capabilities

## API Endpoints

### Chat Completions
`POST /v1/chat/completions`
- Supports streaming
- Tool calling
- Multi-turn conversations

### Embeddings
`POST /v1/embeddings`
- Batch processing
- Multiple models
"""
        
        with open(tech_doc, "w") as f:
            f.write(content)
        
        # 2. Ingest documentation
        ingest_payload = {
            "file_path": tech_doc,
            "metadata": {
                "source": "e2e_test",
                "category": "technical",
                "topic": "architecture"
            }
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        # 3. Wait for processing
        await asyncio.sleep(5)
        
        # 4. RAG Query: Complex question
        query = "How does the system handle batch processing and what database is used for vector storage?"
        
        # First, search for relevant information
        search_payload = {
            "query": query,
            "limit": 5
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        assert "results" in search_data
        assert len(search_data["results"]) > 0
        
        # 5. Build RAG context
        context_parts = []
        for result in search_data["results"][:3]:
            content = result.get("content", "")
            if content:
                context_parts.append(content)
        
        rag_context = "\n\n".join(context_parts)
        
        # 6. Generate answer with RAG context
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer the question."},
                {"role": "user", "content": f"Context:\n{rag_context}\n\nQuestion: {query}"}
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
        assert ("batch" in response_text.lower() or "processing" in response_text.lower())
        assert ("database" in response_text.lower() or "postgresql" in response_text.lower() or "pgvector" in response_text.lower())
    
    @pytest.mark.asyncio
    async def test_e2e_workflow_with_streaming(self, ingestor_client, langgraph_client, test_workspace, clean_database):
        """Test end-to-end workflow with streaming responses"""
        
        # 1. Create a document
        doc_file = os.path.join(test_workspace, "streaming_test.md")
        with open(doc_file, "w") as f:
            f.write("# Streaming Test\n\nThis document tests streaming workflows.\n")
        
        # 2. Ingest
        ingest_payload = {
            "file_path": doc_file,
            "metadata": {"source": "e2e_test"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        assert ingest_response.status_code == 200
        
        await asyncio.sleep(3)
        
        # 3. Search
        search_payload = {"query": "streaming test", "limit": 2}
        search_response = await ingestor_client.post("/search", json=search_payload)
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        
        # 4. Stream chat response
        context = ""
        if search_data.get("results"):
            context = search_data["results"][0].get("content", "")
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are helpful assistant."},
                {"role": "user", "content": f"Explain streaming based on: {context}"}
            ],
            "stream": True,
            "max_tokens": 200
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        # TODO: Implement proper streaming test with httpx stream context manager
        assert chat_response.status_code == 200
        
        # TODO: Implement proper streaming test with httpx stream context manager
        # For now, we test the response structure
        # Skip streaming verification for now
    
    @pytest.mark.asyncio
    async def test_e2e_error_recovery(self, ingestor_client, langgraph_client, test_workspace):
        """Test system recovery from errors"""
        
        # 1. Try to ingest non-existent file
        bad_payload = {
            "file_path": "/nonexistent/file.txt",
            "metadata": {"source": "e2e_test"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=bad_payload)
        # Should handle gracefully
        assert ingest_response.status_code in [400, 404]
        
        # 2. Create a file with problematic content
        problematic_file = os.path.join(test_workspace, "problematic.txt")
        with open(problematic_file, "w") as f:
            f.write("Test content with special characters: \n\t\r\0")
        
        # 3. Ingest problematic file
        ingest_payload = {
            "file_path": problematic_file,
            "metadata": {"source": "e2e_test"}
        }
        
        ingest_response = await ingestor_client.post("/ingest", json=ingest_payload)
        # Should handle special characters
        assert ingest_response.status_code == 200
        
        # 4. Try invalid search query
        search_payload = {
            "query": "",  # Empty query
            "limit": 5
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        # Should handle empty query
        assert search_response.status_code in [200, 400]
        
        # 5. Try chat with empty messages
        chat_payload = {
            "messages": [],
            "stream": False
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        # Should handle empty messages
        assert chat_response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_e2e_performance_benchmark(self, ingestor_client, langgraph_client, test_workspace, clean_database):
        """Benchmark end-to-end workflow performance"""
        import time
        
        # 1. Create test data
        test_files = []
        for i in range(5):
            filename = f"benchmark_{i}.md"
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(f"# Benchmark Document {i}\n\n")
                f.write(f"This is test document number {i} for performance benchmarking.\n")
                f.write("It contains multiple paragraphs of text.\n" * 5)
            test_files.append(filepath)
        
        # 2. Ingest all files and measure time
        ingest_times = []
        for filepath in test_files:
            start = time.time()
            
            ingest_payload = {
                "file_path": filepath,
                "metadata": {"source": "benchmark", "index": str(test_files.index(filepath))}
            }
            
            response = await ingestor_client.post("/ingest", json=ingest_payload)
            end = time.time()
            
            assert response.status_code == 200
            ingest_times.append(end - start)
        
        # 3. Wait for processing
        await asyncio.sleep(10)
        
        # 4. Search and measure
        search_query = "benchmark document test"
        search_start = time.time()
        
        search_payload = {
            "query": search_query,
            "limit": 5
        }
        
        search_response = await ingestor_client.post("/search", json=search_payload)
        search_end = time.time()
        
        assert search_response.status_code == 200
        
        search_time = search_end - search_start
        
        # 5. Chat with context
        search_data = search_response.json()
        context = ""
        if search_data.get("results"):
            context = search_data["results"][0].get("content", "")
        
        chat_start = time.time()
        
        chat_payload = {
            "messages": [
                {"role": "system", "content": "You are helpful assistant."},
                {"role": "user", "content": f"Summarize this: {context}"}
            ],
            "stream": False,
            "max_tokens": 100
        }
        
        chat_response = await langgraph_client.post("/v1/chat/completions", json=chat_payload)
        chat_end = time.time()
        
        assert chat_response.status_code == 200
        chat_time = chat_end - chat_start
        
        # Log performance metrics
        print(f"Ingest times: {ingest_times}")
        print(f"Search time: {search_time}")
        print(f"Chat time: {chat_time}")
        
        # Should complete within reasonable time
        assert search_time < 30, f"Search took {search_time} seconds"
        assert chat_time < 60, f"Chat took {chat_time} seconds"
        
        # Check response quality
        chat_data = chat_response.json()
        if "choices" in chat_data and len(chat_data["choices"]) > 0:
            response_text = chat_data["choices"][0]["message"]["content"]
            assert len(response_text) > 10  # Reasonable response length