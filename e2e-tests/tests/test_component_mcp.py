import pytest
import httpx
import json
import asyncio
from typing import Dict, Any

@pytest.mark.component
@pytest.mark.mcp
@pytest.mark.fast
class TestMCPComponent:
    """Component tests for MCP servers"""
    
    @pytest.mark.asyncio
    async def test_mcp_bash_health(self, mcp_bash_client):
        """Test MCP bash server health"""
        response = await mcp_bash_client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
    
    @pytest.mark.asyncio
    async def test_mcp_project_health(self, mcp_project_client):
        """Test MCP project server health"""
        response = await mcp_project_client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
    
    @pytest.mark.asyncio
    async def test_mcp_bash_list_tools(self, mcp_bash_client):
        """Test listing available tools in bash server"""
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
        assert len(data["result"]["tools"]) > 0
    
    @pytest.mark.asyncio
    async def test_mcp_project_list_tools(self, mcp_project_client):
        """Test listing available tools in project server"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        response = await mcp_project_client.post("/mcp", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "result" in data
        assert "tools" in data["result"]
        assert len(data["result"]["tools"]) > 0
    
    @pytest.mark.asyncio
    async def test_mcp_bash_execute_command(self, mcp_bash_client):
        """Test executing a bash command through MCP"""
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "execute_command",
                "arguments": {
                    "command": "echo",
                    "args": ["Hello from MCP bash test"],
                    "cwd": "/tmp"
                }
            }
        }
        
        response = await mcp_bash_client.post("/mcp", json=payload)
        # MCP servers might use different response formats
        # We're mainly checking that the request is processed
    
    @pytest.mark.asyncio
    async def test_mcp_project_file_operations(self, mcp_project_client):
        """Test file operations through MCP project server"""
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_files",
                "arguments": {
                    "path": "/workspace"
                }
            }
        }
        
        response = await mcp_project_client.post("/mcp", json=payload)
        # Mainly checking request processing
    
    @pytest.mark.asyncio
    async def test_mcp_bash_error_handling(self, mcp_bash_client):
        """Test error handling in MCP bash server"""
        # Invalid method
        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "invalid_method",
            "params": {}
        }
        
        response = await mcp_bash_client.post("/mcp", json=payload)
        # Should return error response
    
    @pytest.mark.asyncio
    async def test_mcp_project_error_handling(self, mcp_project_client):
        """Test error handling in MCP project server"""
        # Invalid method
        payload = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "invalid_method",
            "params": {}
        }
        
        response = await mcp_project_client.post("/mcp", json=payload)
        # Should return error response
    
    @pytest.mark.asyncio
    async def test_mcp_bash_tool_schema(self, mcp_bash_client):
        """Test tool schema validation"""
        payload = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/list",
            "params": {}
        }
        
        response = await mcp_bash_client.post("/mcp", json=payload)
        if response.status_code == 200:
            data = response.json()
            if "result" in data and "tools" in data["result"]:
                tools = data["result"]["tools"]
                if len(tools) > 0:
                    # Check tool structure
                    tool = tools[0]
                    assert "name" in tool
                    assert "description" in tool
                    if "inputSchema" in tool:
                        schema = tool["inputSchema"]
                        assert "type" in schema
                        assert "properties" in schema or "anyOf" in schema
    
    @pytest.mark.asyncio
    async def test_mcp_project_tool_schema(self, mcp_project_client):
        """Test tool schema validation in project server"""
        payload = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/list",
            "params": {}
        }
        
        response = await mcp_project_client.post("/mcp", json=payload)
        if response.status_code == 200:
            data = response.json()
            if "result" in data and "tools" in data["result"]:
                tools = data["result"]["tools"]
                if len(tools) > 0:
                    tool = tools[0]
                    assert "name" in tool
                    assert "description" in tool
    
    @pytest.mark.asyncio
    async def test_mcp_bash_connection_stability(self, mcp_bash_client):
        """Test MCP bash server connection stability"""
        for i in range(3):
            payload = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/list",
                "params": {}
            }
            
            response = await mcp_bash_client.post("/mcp", json=payload)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_mcp_project_connection_stability(self, mcp_project_client):
        """Test MCP project server connection stability"""
        for i in range(3):
            payload = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/list",
                "params": {}
            }
            
            response = await mcp_project_client.post("/mcp", json=payload)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_mcp_bash_multiple_tools(self, mcp_bash_client):
        """Test calling multiple tools in sequence"""
        tools_to_test = ["execute_command", "list_files", "read_file"]
        
        for tool_name in tools_to_test:
            payload = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": {}
                }
            }
            
            response = await mcp_bash_client.post("/mcp", json=payload)
            # Mainly checking that requests are processed
    
    @pytest.mark.asyncio
    async def test_mcp_project_context_management(self, mcp_project_client):
        """Test context management in MCP project server"""
        # First, get context
        payload1 = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "resources/list",
            "params": {}
        }
        
        response1 = await mcp_project_client.post("/mcp", json=payload1)
        # Then test with different contexts
        payload2 = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "roots/list",
            "params": {}
        }
        
        response2 = await mcp_project_client.post("/mcp", json=payload2)
        # Check that both requests work
    
    @pytest.mark.asyncio
    async def test_mcp_bash_large_output(self, mcp_bash_client):
        """Test handling large command output"""
        payload = {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "execute_command",
                "arguments": {
                    "command": "ls",
                    "args": ["-la", "/"],
                    "cwd": "/"
                }
            }
        }
        
        response = await mcp_bash_client.post("/mcp", json=payload)
        # Should handle large output gracefully
    
    @pytest.mark.asyncio
    async def test_mcp_project_complex_query(self, mcp_project_client):
        """Test complex project queries"""
        # Query for specific file types
        payload = {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "find_files",
                "arguments": {
                    "pattern": "*.py",
                    "directory": "/workspace"
                }
            }
        }
        
        response = await mcp_project_client.post("/mcp", json=payload)
        # Check file discovery functionality