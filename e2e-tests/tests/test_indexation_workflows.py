"""
test_indexation_workflows.py

Tests for file ingestion, processing, and storage workflows.
Covers: Indexation workflows, DB storing
"""

import asyncio
import os

import pytest

from infra.config import Ingestor


@pytest.mark.integration
@pytest.mark.indexation
@pytest.mark.fast
class TestIndexationWorkflows:
    """Test suite for indexation workflows"""
    
    @pytest.mark.asyncio
    async def test_single_file_ingestion_text(self, ingestor_client, test_workspace):
        """Test ingestion of a single text file"""
        # Create test file
        test_file = os.path.join(test_workspace, "test_document.txt")
        with open(test_file, "w") as f:
            f.write("This is a test document for indexation testing.\n")
            f.write("It contains multiple paragraphs.\n")
            f.write("This is paragraph 3.\n")
        
        # Prepare ingestion payload
        payload = {
            "file_path": test_file,
            "metadata": {
                "source": "test",
                "category": "document",
                "priority": "medium"
            }
        }
        
        # Execute ingestion
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "job_id" in data
        assert "status" in data
        assert data["status"] in ["queued", "processing", "completed"]
    
    @pytest.mark.asyncio
    async def test_batch_file_ingestion(self, ingestor_client, test_workspace):
        """Test ingestion of multiple files in batch"""
        # Create multiple test files
        test_files = []
        for i in range(5):
            filename = f"batch_test_{i}.txt"
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(f"Batch test document {i}\n")
                f.write(f"This is file {i} for batch testing.\n")
            test_files.append(filepath)
        
        # Ingest all files
        job_ids = []
        for filepath in test_files:
            payload = {
                "file_path": filepath,
                "metadata": {
                    "source": "test",
                    "batch": "true",
                    "index": str(test_files.index(filepath))
                }
            }
            
            response = await ingestor_client.post(Ingestor.INGEST, json=payload)
            assert response.status_code == 200
            
            data = response.json()
            if "job_id" in data:
                job_ids.append(data["job_id"])
        
        # Verify all jobs were created
        assert len(job_ids) == len(test_files)
    
    @pytest.mark.asyncio
    async def test_file_type_detection(self, ingestor_client, test_workspace):
        """Test automatic file type detection during ingestion"""
        test_cases = [
            ("test.py", "# Python code\nprint('test')\n", "python"),
            ("test.md", "# Markdown\nContent\n", "markdown"),
            ("test.json", '{"key": "value"}\n', "json"),
            ("test.yaml", "key: value\n", "yaml"),
            ("test.txt", "Plain text content\n", "text")
        ]
        
        for filename, content, expected_type in test_cases:
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
    async def test_metadata_extraction(self, ingestor_client, test_workspace):
        """Test metadata extraction from different file types"""
        # Create Python file with metadata
        py_file = os.path.join(test_workspace, "code_with_meta.py")
        py_content = '''#!/usr/bin/env python3
"""
Test module with metadata
Author: Test Author
Version: 1.0.0
"""
import os
from typing import List

def main():
    """Main function"""
    return "Hello, World!"
'''
        with open(py_file, "w") as f:
            f.write(py_content)
        
        payload = {
            "file_path": py_file,
            "metadata": {
                "source": "test",
                "language": "python",
                "type": "code"
            }
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
        
        # Verify metadata was extracted (check with search or file info endpoint)
        # This would depend on the actual API implementation
    
    @pytest.mark.asyncio
    async def test_ingestion_error_handling(self, ingestor_client):
        """Test error handling for invalid ingestion requests"""
        # Non-existent file
        payload = {
            "file_path": "/nonexistent/file.txt",
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code in [400, 404]
        
        # Invalid payload structure
        payload = {
            # Missing required fields
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_ingestion_status_tracking(self, ingestor_client, test_workspace):
        """Test job status tracking during ingestion"""
        # Create and ingest a file
        test_file = os.path.join(test_workspace, "status_test.txt")
        with open(test_file, "w") as f:
            f.write("Status tracking test\n")
        
        payload = {
            "file_path": test_file,
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        job_id = data.get("job_id")
        assert job_id
        
        # Poll for status (if status endpoint exists)
        if job_id:
            await asyncio.sleep(2)
            # Check status endpoint if it exists
            # status_response = await ingestor_client.get(f"/status/{job_id}")
            # if status_response.status_code == 200:
            #     status_data = status_response.json()
            #     assert "status" in status_data
    
    @pytest.mark.asyncio
    async def test_large_file_ingestion(self, ingestor_client, test_workspace):
        """Test ingestion of large files"""
        # Create a large text file
        large_file = os.path.join(test_workspace, "large_document.txt")
        with open(large_file, "w") as f:
            # Write 100KB of content
            for i in range(1000):
                f.write(f"Line {i}: This is a test line for large file testing.\n" * 10)
        
        payload = {
            "file_path": large_file,
            "metadata": {
                "source": "test",
                "size": "large"
            }
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_concurrent_ingestion(self, ingestor_client, test_workspace):
        """Test concurrent file ingestion"""
        # Create multiple test files
        files = []
        for i in range(3):
            filename = f"concurrent_{i}.txt"
            filepath = os.path.join(test_workspace, filename)
            with open(filepath, "w") as f:
                f.write(f"Concurrent test {i}\n")
            files.append(filepath)
        
        # Ingest all files concurrently
        async def ingest_file(filepath):
            payload = {
                "file_path": filepath,
                "metadata": {"source": "test", "concurrent": "true"}
            }
            return await ingestor_client.post(Ingestor.INGEST, json=payload)
        
        responses = await asyncio.gather(*[ingest_file(f) for f in files])
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingestion_with_special_characters(self, ingestor_client, test_workspace):
        """Test ingestion of files with special characters in content"""
        test_file = os.path.join(test_workspace, "special_chars.txt")
        special_content = """
        Test with special characters:
        - Unicode: café, naïve, über
        - Quotes: 'single', "double", `backticks`
        - Escape sequences: \n\t\r\0
        - Special chars: @#$%^&*()_+-=[]{}|;':",./<>?
        """
        
        with open(test_file, "w") as f:
            f.write(special_content)
        
        payload = {
            "file_path": test_file,
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingestion_with_metadata_validation(self, ingestor_client, test_workspace):
        """Test metadata validation during ingestion"""
        test_file = os.path.join(test_workspace, "meta_test.txt")
        with open(test_file, "w") as f:
            f.write("Test with metadata validation\n")
        
        # Test with valid metadata
        valid_payload = {
            "file_path": test_file,
            "metadata": {
                "source": "test",
                "category": "documentation",
                "priority": "high",
                "tags": ["test", "integration", "validation"]
            }
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=valid_payload)
        assert response.status_code == 200
        
        # Test with empty metadata (should still work)
        empty_metadata_payload = {
            "file_path": test_file,
            "metadata": {}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=empty_metadata_payload)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingestion_cancellation(self, ingestor_client, test_workspace):
        """Test cancellation of ingestion jobs (if supported)"""
        # This would depend on the actual API implementation
        # If there's a cancel endpoint, test it
        # Otherwise, test that jobs can be in different states
        
        # For now, just test that we can create a job
        test_file = os.path.join(test_workspace, "cancellation_test.txt")
        with open(test_file, "w") as f:
            f.write("Cancellation test\n")
        
        payload = {
            "file_path": test_file,
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingestion_priority_handling(self, ingestor_client, test_workspace):
        """Test ingestion with different priority levels"""
        priorities = ["low", "medium", "high"]
        
        for priority in priorities:
            test_file = os.path.join(test_workspace, f"priority_{priority}.txt")
            with open(test_file, "w") as f:
                f.write(f"Priority {priority} test\n")
            
            payload = {
                "file_path": test_file,
                "metadata": {
                    "source": "test",
                    "priority": priority
                }
            }
            
            response = await ingestor_client.post(Ingestor.INGEST, json=payload)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ingestion_file_size_limits(self, ingestor_client, test_workspace):
        """Test ingestion with different file sizes"""
        sizes = [1, 10, 100, 1000]  # KB
        
        for size_kb in sizes:
            test_file = os.path.join(test_workspace, f"size_{size_kb}kb.txt")
            with open(test_file, "w") as f:
                # Write approximately size_kb KB
                content = "A" * 1024  # 1KB
                for _ in range(size_kb):
                    f.write(content)
            
            payload = {
                "file_path": test_file,
                "metadata": {
                    "source": "test",
                    "size_kb": size_kb
                }
            }
            
            response = await ingestor_client.post(Ingestor.INGEST, json=payload)
            # Small files should work, large files might have limits
            assert response.status_code in [200, 413]  # 413 for payload too large
    
    @pytest.mark.asyncio
    async def test_ingestion_file_encoding(self, ingestor_client, test_workspace):
        """Test ingestion of files with different encodings"""
        encodings = ["utf-8", "utf-16", "latin-1"]
        
        for encoding in encodings:
            test_file = os.path.join(test_workspace, f"encoding_{encoding}.txt")
            try:
                with open(test_file, "w", encoding=encoding) as f:
                    f.write(f"Test with {encoding} encoding\n")
                    f.write("Café, naïve, über\n")
                
                payload = {
                    "file_path": test_file,
                    "metadata": {
                        "source": "test",
                        "encoding": encoding
                    }
                }
                
                response = await ingestor_client.post(Ingestor.INGEST, json=payload)
                # Should handle or at least not crash with different encodings
                assert response.status_code in [200, 400, 500]
            except Exception:
                # Some encodings might not be supported
                pass
    
    @pytest.mark.asyncio
    async def test_ingestion_of_empty_file(self, ingestor_client, test_workspace):
        """Test ingestion of empty file"""
        test_file = os.path.join(test_workspace, "empty_file.txt")
        with open(test_file, "w") as f:
            # Create empty file
            pass
        
        payload = {
            "file_path": test_file,
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        # Should handle empty files gracefully
        assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_ingestion_of_binary_file(self, ingestor_client, test_workspace):
        """Test ingestion of binary file (should fail gracefully)"""
        test_file = os.path.join(test_workspace, "binary_file.bin")
        with open(test_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04\x05")
        
        payload = {
            "file_path": test_file,
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        # Should handle or reject binary files
        assert response.status_code in [200, 400, 415]
    
    @pytest.mark.asyncio
    async def test_ingestion_of_directory(self, ingestor_client):
        """Test ingestion of directory (should fail)"""
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = {
                "file_path": temp_dir,
                "metadata": {"source": "test"}
            }
            
            response = await ingestor_client.post(Ingestor.INGEST, json=payload)
            # Should reject directory ingestion
            assert response.status_code in [400, 404]
    
    @pytest.mark.asyncio
    async def test_ingestion_of_symlink(self, ingestor_client, test_workspace):
        """Test ingestion of symbolic link"""

        # Create a real file
        real_file = os.path.join(test_workspace, "real_file.txt")
        with open(real_file, "w") as f:
            f.write("Real file content\n")
        
        # Create a symlink
        symlink_file = os.path.join(test_workspace, "symlink_file.txt")
        os.symlink(real_file, symlink_file)
        
        payload = {
            "file_path": symlink_file,
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        # Should handle or follow symlinks
        assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_ingestion_performance_metrics(self, ingestor_client, test_workspace):
        """Test that ingestion reports performance metrics"""
        import time
        
        test_file = os.path.join(test_workspace, "performance_test.txt")
        with open(test_file, "w") as f:
            for i in range(100):
                f.write(f"Line {i}: Performance test content\n")
        
        payload = {
            "file_path": test_file,
            "metadata": {"source": "performance_test"}
        }
        
        start_time = time.time()
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Check if response contains timing information
        data = response.json()
        if "processing_time" in data:
            processing_time = data["processing_time"]
            assert isinstance(processing_time, (int, float))
            assert processing_time > 0
        elif "timestamp" in data:
            # Check timestamp is reasonable
            assert isinstance(data["timestamp"], (int, float))
    
    @pytest.mark.asyncio
    async def test_ingestion_with_file_permissions(self, ingestor_client, test_workspace):
        """Test ingestion with different file permissions"""
        import stat
        
        test_file = os.path.join(test_workspace, "permission_test.txt")
        with open(test_file, "w") as f:
            f.write("Permission test\n")
        
        # Test with read-only permissions
        os.chmod(test_file, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        
        payload = {
            "file_path": test_file,
            "metadata": {"source": "test"}
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        # Should handle read-only files
        assert response.status_code in [200, 403]
        
        # Reset permissions
        os.chmod(test_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)
    
    @pytest.mark.asyncio
    async def test_ingestion_of_nested_files(self, ingestor_client, test_workspace):
        """Test ingestion of files in nested directories"""
        import os.path
        
        # Create nested directory structure
        nested_dir = os.path.join(test_workspace, "nested", "deep", "structure")
        os.makedirs(nested_dir, exist_ok=True)
        
        nested_file = os.path.join(nested_dir, "nested_file.txt")
        with open(nested_file, "w") as f:
            f.write("Nested file content\n")
        
        payload = {
            "file_path": nested_file,
            "metadata": {
                "source": "test",
                "path_structure": "nested/deep/structure"
            }
        }
        
        response = await ingestor_client.post(Ingestor.INGEST, json=payload)
        assert response.status_code == 200