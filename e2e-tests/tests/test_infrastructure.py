"""
Test infrastructure and fixtures.

Tests that verify the test infrastructure works correctly
without requiring external services.
"""

import pytest
import asyncio
import os
import tempfile
from pathlib import Path


@pytest.mark.component
@pytest.mark.fast
class TestInfrastructure:
    """Test test infrastructure itself"""
    
    @pytest.mark.asyncio
    async def test_async_test_execution(self):
        """Test that async tests can execute"""
        # Simple async operation
        result = await asyncio.sleep(0.01)
        # Should not raise
        assert result is None
    
    def test_fixture_access(self, config):
        """Test that config fixture is accessible"""
        assert config is not None
        assert isinstance(config, dict)
        assert 'llm_url' in config
        assert 'ingestor_url' in config
    
    @pytest.mark.asyncio
    async def test_async_fixture_access(self, llm_client):
        """Test that async fixtures are accessible"""
        # This test will fail if services aren't running, but infrastructure should work
        # The important thing is that the fixture can be accessed
        assert llm_client is not None
    
    def test_test_workspace(self, test_workspace):
        """Test that test_workspace fixture works"""
        assert test_workspace is not None
        assert os.path.exists(test_workspace)
        assert os.path.isdir(test_workspace)
    
    def test_test_data(self, test_data):
        """Test that test_data fixture works"""
        assert test_data is not None
        assert isinstance(test_data, dict)
        assert 'simple_code' in test_data
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async function support"""
        # This should run as an async test
        await asyncio.sleep(0.01)
        assert True
    
    def test_marked_functions(self):
        """Test marker support"""
        # Test should be marked as component and fast
        assert True
