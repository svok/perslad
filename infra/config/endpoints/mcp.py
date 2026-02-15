"""API endpoints for MCP services."""

from dataclasses import dataclass


@dataclass
class MCP:
    MCP: str = "/mcp"
    ROOT: str = "/"
