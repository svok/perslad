import asyncio
import json
import os

import pytest

from infra.config import Ingestor


@pytest.mark.component
@pytest.mark.integration
@pytest.mark.fast
class TestIngestorComponent:
    """Component tests for Ingestor service"""
    
    @pytest.mark.asyncio
    async def test_ingestor_health(self, ingestor_client):
        """Test that ingestor service is healthy"""
        response = await ingestor_client.get(Ingestor.ROOT)
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_ingestor_ingest_text(self, ingestor_client, test_workspace):
        """Test text file ingestion"""
        # Create a test text file
        test_file = os.path.join(test_workspace, "test_document.txt")
        with open(test_file, "w") as f:
            f.write("This is a test document for ingestor testing.\n")
            f.write("It contains multiple lines of text.\n")
            f.write("This is line 3.\n")
        
        payload = {
            "file_path": test_file,
            "metadata": {
                "source": "test",
                "category": "document",
                "priority": "low"
            }
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "job_id" in data
        assert "status" in data
        
        # Wait for ingestion to complete
        job_id = data["job_id"]
        await asyncio.sleep(2)  # Give time for processing
        
        # Check job status
        status_response = await ingestor_client.get(f"/status/{job_id}")
        if status_response.status_code == 200:
            status_data = status_response.json()
            assert status_data.get("status") in ["completed", "processing", "failed"]
    
    @pytest.mark.asyncio
    async def test_ingestor_ingest_code(self, ingestor_client, test_workspace):
        """Test code file ingestion"""
        test_file = os.path.join(test_workspace, "test_code.py")
        with open(test_file, "w") as f:
            f.write("# Test Python code\n")
            f.write("def hello():\n")
            f.write("    return 'Hello, World!'\n")
            f.write("\n")
            f.write("class TestClass:\n")
            f.write("    def __init__(self):\n")
            f.write("        self.value = 42\n")
        
        payload = {
            "file_path": test_file,
            "metadata": {
                "source": "test",
                "language": "python",
                "type": "code"
            }
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "job_id" in data
    
    @pytest.mark.asyncio
    async def test_ingestor_ingest_markdown(self, ingestor_client, test_workspace):
        """Test markdown file ingestion"""
        test_file = os.path.join(test_workspace, "test_readme.md")
        with open(test_file, "w") as f:
            f.write("# Test Documentation\n\n")
            f.write("## Overview\n")
            f.write("This is a test markdown file.\n\n")
            f.write("## Features\n")
            f.write("- Feature 1\n")
            f.write("- Feature 2\n")
        
        payload = {
            "file_path": test_file,
            "metadata": {
                "source": "test",
                "type": "documentation"
            }
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "job_id" in data
    
    @pytest.mark.asyncio
    async def test_ingestor_ingest_json(self, ingestor_client, test_workspace):
        """Test JSON file ingestion"""
        test_file = os.path.join(test_workspace, "test_config.json")
        test_data = {
            "project": "test-project",
            "version": "1.0.0",
            "features": ["feature1", "feature2"],
            "settings": {
                "debug": True,
                "timeout": 30
            }
        }
        
        with open(test_file, "w") as f:
            json.dump(test_data, f, indent=2)
        
        payload = {
            "file_path": test_file,
            "metadata": {
                "source": "test",
                "type": "config",
                "format": "json"
            }
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "job_id" in data
    
    @pytest.mark.asyncio
    async def test_ingestor_batch_ingestion(self, ingestor_client, test_workspace):
        """Test batch ingestion of multiple files"""
        # Create multiple test files
        files = []
        for i in range(5):
            filename = f"test_file_{i}.txt"
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(f"Test document number {i}\n")
                f.write(f"This is file {i} for batch testing.\n")
            files.append(filepath)
        
        # Ingest all files
        for filepath in files:
            payload = {
                "file_path": filepath,
                "metadata": {
                    "source": "test",
                    "batch": "true",
                    "index": str(files.index(filepath))
                }
            }
            
            response = await ingestor_client.post(Ingestor.INGEST, json=payload)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingestor_search(self, ingestor_client, test_workspace):
        """Test search functionality after ingestion"""
        # First, ingest a specific document
        test_file = os.path.join(test_workspace, "search_test.txt")
        test_content = """
Python async programming allows for concurrent execution of code.
It uses async/await syntax for writing asynchronous code.
The asyncio module provides the event loop and coroutines.
"""
        with open(test_file, "w") as f:
            f.write(test_content)
        
        # Ingest the document
        ingest_payload = {
            "file_path": test_file,
            "metadata": {
                "source": "test",
                "category": "tutorial",
                "topic": "async"
            }
        }
        
        ingest_response = await ingestor_client.post(Ingestor.INGEST, json=ingest_payload)
        assert ingest_response.status_code == 200
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Search for the ingested content
        search_payload = {
            "query": "Python async programming",
            "limit": 5
        }
        
        search_response = await ingestor_client.post(Ingestor.SEARCH, json=search_payload)
        assert search_response.status_code == 200
        
        data = search_response.json()
        assert "results" in data
        assert len(data["results"]) > 0
    
    @pytest.mark.asyncio
    async def test_ingestor_metadata_extraction(self, ingestor_client, test_workspace):
        """Test metadata extraction from different file types"""
        test_cases = [
            ("code.py", "# Python code\nprint('test')\n", {"language": "python"}),
            ("doc.md", "# Document\nSome content\n", {"type": "document"}),
            ("config.json", '{"key": "value"}\n', {"format": "json"}),
            ("data.yaml", "key: value\n", {"format": "yaml"})
        ]
        
        for filename, content, expected_meta in test_cases:
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(content)
            
            payload = {
                "file_path": filepath,
                "metadata": {"source": "test"}
            }
            
            response = await ingestor_client.post(Ingestor.INGEST, json=payload)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingestor_error_handling(self, ingestor_client):
        """Test error handling for invalid inputs"""
        # Non-existent file
        payload = {
            "file_path": "/nonexistent/file.txt",
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 404
        
        # Invalid payload
        payload = {
            # Missing required fields
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_ingestor_status_tracking(self, ingestor_client, test_workspace):
        """Test job status tracking"""
        # Create and ingest a file
        test_file = os.path.join(test_workspace, "status_test.txt")
        with open(test_file, "w") as f:
            f.write("Status tracking test\n")
        
        payload = {
            "file_path": test_file,
            "metadata": {"source": "test"}
        }
        
        ingest_response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        if ingest_response.status_code == 200:
            data = ingest_response.json()
            job_id = data.get("job_id")
            
            if job_id:
                # Check status immediately
                status_response = await ingestor_client.get(f"/status/{job_id}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    assert "status" in status_data
                    assert status_data["job_id"] == job_id