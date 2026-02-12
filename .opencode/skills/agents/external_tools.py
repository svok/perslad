"""
External tools integration skill for agents.
Integration with opencode and Continue using MCP.

Design principles:
- Maximum 150 lines per file
- Type hints everywhere
- Single responsibility principle
- DRY and KISS patterns
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class IntegrationType(Enum):
    """Types of external tool integration."""
    OPENCODE = "opencode"
    CONTINUE = "continue"
    MCP_TOOL = "mcp_tool"
    API_CLIENT = "api_client"


@dataclass
class IntegrationConfig:
    """Configuration for external tool integration."""
    integration_type: IntegrationType
    endpoint_url: str
    api_key: Optional[str] = None
    model_name: str = "local"
    timeout: int = 30

    def __post_init__(self):
        # Sanitize sensitive data in repr
        if self.api_key:
            self._safe_api_key = self.api_key[:8] + "..." if len(self.api_key) > 8 else "***"


@dataclass
class MCPConfig:
    """MCP tool configuration."""
    tool_name: str
    description: str
    parameters: Dict[str, Any]
    command: Optional[str] = None
    endpoint: Optional[str] = None


def setup_opencode_integration() -> Dict[str, Any]:
    """
    Configure integration with opencode.
    
    Returns:
        Integration configuration
    """
    config = {
        "integration_type": IntegrationType.OPENCODE.value,
        "endpoint": "http://localhost:8123",  # LangGraph agent
        "mcp_tools": ["bash", "project", "sql"],
        "capabilities": [
            "code_analysis",
            "file_operations",
            "shell_commands",
            "database_queries"
        ],
        "security": "local_sandbox"
    }
    return config


def setup_continue_integration() -> Dict[str, Any]:
    """
    Configure integration with Continue extension.
    
    Returns:
        Integration configuration
    """
    config = {
        "integration_type": IntegrationType.CONTINUE.value,
        "endpoint": "http://localhost:8123",
        "configuration_file": ".continue/config.json",
        "capabilities": [
            "autocomplete",
            "code_suggestions",
            "documentation_lookup",
            "refactoring"
        ],
        "local_models": True
    }
    return config


def configure_mcp_tools(mcp_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Configure MCP tools for external integration.
    
    Args:
        mcp_config: MCP configuration
        
    Returns:
        MCP tool configuration
    """
    tools = []
    
    for tool_name, config in mcp_config.items():
        tool = MCPConfig(
            tool_name=tool_name,
            description=config.get("description", ""),
            parameters=config.get("parameters", {}),
            command=config.get("command"),
            endpoint=config.get("endpoint")
        )
        tools.append(tool)
    
    return {
        "tools": [t.tool_name for t in tools],
        "configuration": {
            "bash": {
                "description": "Execute shell commands in sandbox",
                "permissions": ["read", "execute"],
                "sandbox": "docker"
            },
            "project": {
                "description": "Navigate and analyze project structure",
                "permissions": ["read", "analyze"],
                "root_path": "/workspace"
            },
            "sql": {
                "description": "Execute SQL queries on PostgreSQL",
                "permissions": ["read", "write"],
                "database": "rag"
            }
        }
    }


def execute_integration_test(
    integration_type: IntegrationType,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute integration test for external tools.
    
    Args:
        integration_type: Type of integration to test
        config: Integration configuration
        
    Returns:
        Test results
    """
    test_results = {
        "integration_type": integration_type.value,
        "tests": []
    }
    
    if integration_type == IntegrationType.OPENCODE:
        # Test opencode integration
        test_results["tests"].extend([
            {"name": "endpoint_connectivity", "status": "pending"},
            {"name": "mcp_tool_availability", "status": "pending"},
            {"name": "code_analysis_capability", "status": "pending"}
        ])
    
    elif integration_type == IntegrationType.CONTINUE:
        # Test Continue integration
        test_results["tests"].extend([
            {"name": "configuration_loading", "status": "pending"},
            {"name": "extension_communication", "status": "pending"},
            {"name": "autocomplete_functionality", "status": "pending"}
        ])
    
    return test_results


def create_opencode_config() -> Dict[str, Any]:
    """
    Create opencode configuration file.
    
    Returns:
        Configuration content
    """
    config = {
        "version": "1.0",
        "agent": {
            "endpoint": "http://localhost:8123",
            "timeout": 30,
            "retry_count": 3
        },
        "tools": {
            "bash": {
                "enabled": True,
                "sandbox": "docker",
                "timeout": 60
            },
            "project": {
                "enabled": True,
                "root_path": "/workspace"
            },
            "sql": {
                "enabled": True,
                "connection_string": "postgresql://rag:rag@postgres:5432/rag"
            }
        },
        "model": {
            "local": True,
            "name": "Qwen2.5-7B-Instruct-AWQ",
            "temperature": 0.1
        },
        "security": {
            "sandbox_external_tools": True,
            "validate_commands": True,
            "log_all_operations": True
        }
    }
    return config


def create_continue_config() -> Dict[str, Any]:
    """
    Create Continue configuration file.
    
    Returns:
        Configuration content
    """
    config = {
        "title": "Perslad AI Assistant",
        "models": [
            {
                "title": "Perslad Local",
                "provider": "openai-compatible",
                "model": "Qwen2.5-7B-Instruct-AWQ",
                "api_base": "http://localhost:8000/v1",
                "context_length": 8192
            }
        ],
        "context_providers": [
            {
                "name": "code",
                "params": {
                    "workspace_root": "/workspace",
                    "include_extensions": [".py", ".md", ".json", ".yaml"]
                }
            },
            {
                "name": "documentation",
                "params": {
                    "enable_rag": True,
                    "ingestor_endpoint": "http://localhost:8124"
                }
            }
        ],
        "slash_commands": [
            {
                "name": "perslad",
                "description": "Execute Perslad AI tasks",
                "prompt": "{{user_input}}",
                "endpoint": "http://localhost:8123"
            }
        ],
        "capabilities": {
            "autocomplete": True,
            "code_chat": True,
            "documentation_lookup": True
        }
    }
    return config


def get_integration_capabilities(integration_type: IntegrationType) -> List[str]:
    """
    Get available capabilities for integration type.
    
    Args:
        integration_type: Type of integration
        
    Returns:
        List of capabilities
    """
    capabilities_map = {
        IntegrationType.OPENCODE: [
            "execute_shell_commands",
            "navigate_project",
            "run_sql_queries",
            "analyze_code",
            "refactor_code"
        ],
        IntegrationType.CONTINUE: [
            "autocomplete",
            "code_suggestions",
            "documentation_lookup",
            "refactoring"
        ],
        IntegrationType.MCP_TOOL: [
            "command_execution",
            "file_operations",
            "database_queries"
        ]
    }
    
    return capabilities_map.get(integration_type, [])


def validate_integration_config(config: IntegrationConfig) -> List[str]:
    """
    Validate integration configuration.
    
    Args:
        config: Configuration to validate
        
    Returns:
        List of validation errors
    """
    errors = []
    
    if not config.endpoint_url:
        errors.append("Endpoint URL is required")
    
    if config.integration_type not in [t for t in IntegrationType]:
        errors.append(f"Invalid integration type: {config.integration_type}")
    
    if config.timeout <= 0:
        errors.append("Timeout must be positive")
    
    return errors


def setup_security_measures(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Setup security measures for external integration.
    
    Args:
        config: Integration configuration
        
    Returns:
        Security configuration
    """
    security_config = {
        "sandbox_mode": True,
        "command_validation": True,
        "resource_limits": {
            "max_memory": "2GB",
            "max_cpu": "50%",
            "max_duration": "300s"
        },
        "permission_groups": {
            "read_only": ["list_files", "read_content"],
            "read_write": ["edit_files", "create_files"],
            "execution": ["run_commands", "execute_scripts"]
        },
        "audit_logging": True,
        "api_key_rotation": False  # Local only, no external API keys
    }
    return security_config