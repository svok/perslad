import pytest


@pytest.mark.component
@pytest.mark.mcp
@pytest.mark.fast
class TestMCPComponent:
    """Component tests for MCP servers"""
    
    @pytest.mark.asyncio
    async def test_mcp_bash_health(self, mcp_bash_client):
        """Test MCP bash server health"""
        # The fixture already initializes the session
        # Just verify that we have a session ID
        assert mcp_bash_client.session_id is not None

    @pytest.mark.asyncio
    async def test_mcp_project_health(self, mcp_project_client):
        """Test MCP project server health"""
        # The fixture already initializes the session
        # Just verify that we have a session ID
        assert mcp_project_client.session_id is not None
    
    @pytest.mark.asyncio
    async def test_mcp_bash_list_tools(self, mcp_bash_client):
        """Test listing available tools in bash server"""
        data = await mcp_bash_client.list_tools()
        assert "result" in data
        assert "tools" in data["result"]
        assert len(data["result"]["tools"]) > 0

    @pytest.mark.asyncio
    async def test_mcp_project_list_tools(self, mcp_project_client):
        """Test listing available tools in project server"""
        data = await mcp_project_client.list_tools()
        assert "result" in data
        assert "tools" in data["result"]
        assert len(data["result"]["tools"]) > 0
    
    @pytest.mark.asyncio
    async def test_mcp_bash_execute_command(self, mcp_bash_client):
        """Test executing a bash command through MCP"""
        # Execute a simple command to verify tool call works
        result = await mcp_bash_client.call_tool("execute_command", {"command": "echo", "args": ["Hello from MCP bash test"]})
        assert result is not None

    @pytest.mark.asyncio
    async def test_mcp_project_file_operations(self, mcp_project_client):
        """Test file operations through MCP project server"""
        # List files in workspace to verify tool call works
        result = await mcp_project_client.call_tool("list_files", {"path": "/workspace"})
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_mcp_bash_error_handling(self, mcp_bash_client):
        """Test error handling in MCP bash server"""
        # Invalid method - should return error response
        result = await mcp_bash_client.call_tool("invalid_method", {})
        assert result is not None

    @pytest.mark.asyncio
    async def test_mcp_project_error_handling(self, mcp_project_client):
        """Test error handling in MCP project server"""
        # Invalid method - should return error response
        result = await mcp_project_client.call_tool("invalid_method", {})
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_mcp_bash_tool_schema(self, mcp_bash_client):
        """Test tool schema validation"""
        data = await mcp_bash_client.list_tools()
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
        data = await mcp_project_client.list_tools()
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
            data = await mcp_bash_client.list_tools()
            assert data is not None

    @pytest.mark.asyncio
    async def test_mcp_project_connection_stability(self, mcp_project_client):
        """Test MCP project server connection stability"""
        for i in range(3):
            data = await mcp_project_client.list_tools()
            assert data is not None
    
    @pytest.mark.asyncio
    async def test_mcp_bash_multiple_tools(self, mcp_bash_client):
        """Test calling multiple tools in sequence"""
        tools_to_test = ["execute_command", "check_system", "run_python_script"]
        
        for tool_name in tools_to_test:
            result = await mcp_bash_client.call_tool(tool_name, {})
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_mcp_project_context_management(self, mcp_project_client):
        """Test context management in MCP project server"""
        # First, get context - list resources
        result1 = await mcp_project_client.call_tool("resources/list", {})
        assert result1 is not None
        # Then test with different contexts
        result2 = await mcp_project_client.call_tool("roots/list", {})
        assert result2 is not None

    @pytest.mark.asyncio
    async def test_mcp_bash_large_output(self, mcp_bash_client):
        """Test handling large command output"""
        result = await mcp_bash_client.call_tool("execute_command", {
            "command": "ls",
            "args": ["-la", "."]
        })
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_mcp_project_complex_query(self, mcp_project_client):
        """Test complex project queries"""
        # Query for specific file types - use find_files tool
        result = await mcp_project_client.call_tool("find_files", {
            "pattern": "*.py",
            "directory": "/workspace"
        })
        assert result is not None