"""Tests for External tools integration skill."""

import pytest
from skills.agents.external_tools import (
    setup_opencode_integration,
    setup_continue_integration,
    configure_mcp_tools,
    execute_integration_test,
    create_opencode_config,
    create_continue_config,
    IntegrationType,
    validate_integration_config,
    IntegrationConfig
)


def test_setup_opencode_integration():
    """Test setting up opencode integration."""
    config = setup_opencode_integration()
    
    assert "integration_type" in config
    assert "endpoint" in config
    assert "mcp_tools" in config
    assert config["integration_type"] == "opencode"


def test_setup_continue_integration():
    """Test setting up Continue integration."""
    config = setup_continue_integration()
    
    assert "integration_type" in config
    assert "endpoint" in config
    assert "capabilities" in config
    assert config["integration_type"] == "continue"


def test_configure_mcp_tools():
    """Test configuring MCP tools."""
    mcp_config = {
        "bash": {"description": "Shell commands", "permissions": ["read", "execute"]},
        "sql": {"description": "Database queries", "permissions": ["read", "write"]}
    }
    
    result = configure_mcp_tools(mcp_config)
    
    assert "tools" in result
    assert "bash" in result["tools"]
    assert "sql" in result["tools"]


def test_external_integration_testing():
    """Test external integration testing."""
    # Test opencode integration
    result = execute_integration_test(IntegrationType.OPENCODE, {})
    
    assert result["integration_type"] == "opencode"
    assert "tests" in result
    assert len(result["tests"]) > 0
    
    # Test Continue integration
    result = execute_integration_test(IntegrationType.CONTINUE, {})
    
    assert result["integration_type"] == "continue"
    assert "tests" in result


def test_create_opencode_config():
    """Test creating opencode configuration."""
    config = create_opencode_config()
    
    assert "version" in config
    assert "agent" in config
    assert "tools" in config
    assert "security" in config


def test_create_continue_config():
    """Test creating Continue configuration."""
    config = create_continue_config()
    
    assert "title" in config
    assert "models" in config
    assert "context_providers" in config
    assert "slash_commands" in config


def test_integration_config_validation():
    """Test integration configuration validation."""
    # Valid config
    config = IntegrationConfig(
        integration_type=IntegrationType.OPENCODE,
        endpoint_url="http://localhost:8123"
    )
    
    errors = validate_integration_config(config)
    assert len(errors) == 0
    
    # Invalid config (no endpoint)
    config = IntegrationConfig(
        integration_type=IntegrationType.OPENCODE,
        endpoint_url=""
    )
    
    errors = validate_integration_config(config)
    assert len(errors) > 0


def test_security_measures():
    """Test security configuration."""
    from skills.agents.external_tools import setup_security_measures
    
    config = {"endpoint": "http://localhost:8123"}
    security = setup_security_measures(config)
    
    assert "sandbox_mode" in security
    assert "command_validation" in security
    assert "resource_limits" in security
    assert security["sandbox_mode"] is True


def test_capabilities_mapping():
    """Test capabilities for different integration types."""
    from skills.agents.external_tools import get_integration_capabilities
    
    opencode_caps = get_integration_capabilities(IntegrationType.OPENCODE)
    assert len(opencode_caps) > 0
    assert "execute_shell_commands" in opencode_caps
    
    continue_caps = get_integration_capabilities(IntegrationType.CONTINUE)
    assert len(continue_caps) > 0
    assert "autocomplete" in continue_caps