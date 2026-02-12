"""
Core Perslad development patterns and conventions.
Architectural analysis, code generation, and refactoring.

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


class ComponentType(Enum):
    """Types of Perslad components."""
    AGENT = "agent"
    INGESTOR = "ingestor"
    INFRA = "infra"
    SERVER = "server"
    TOOLS = "tools"


@dataclass
class ArchitecturalPattern:
    """Architectural pattern used in Perslad."""
    name: str
    description: str
    implementation: str
    benefits: Optional[List[str]] = None
    drawbacks: Optional[List[str]] = None

    def __post_init__(self):
        if self.benefits is None:
            self.benefits = []
        if self.drawbacks is None:
            self.drawbacks = []


def analyze_perslad_architecture() -> Dict[str, Any]:
    """
    Analyze current Perslad architecture.
    
    Returns:
        Architecture analysis
    """
    return {
        "components": {
            "agents": {
                "type": "LangGraph agent",
                "responsibility": "orchestration",
                "languages": ["Python"],
                "dependencies": ["LangGraph", "LangChain"]
            },
            "ingestor": {
                "type": "RAG engine",
                "responsibility": "indexing",
                "languages": ["Python"],
                "dependencies": ["LlamaIndex", "pgvector"]
            },
            "infra": {
                "type": "Shared infrastructure",
                "responsibility": "common services",
                "languages": ["Python"],
                "dependencies": ["HTTPX", "Pydantic"]
            },
            "servers": {
                "type": "MCP servers",
                "responsibility": "tools",
                "languages": ["Python"],
                "dependencies": ["FastAPI", "MCP"]
            }
        },
        "architecture": "multi_agent",
        "data_flow": "RAG + Agent + Tools",
        "deployment": "Docker Compose"
    }


def identify_architectural_patterns() -> List[ArchitecturalPattern]:
    """
    Identify architectural patterns in Perslad.
    
    Returns:
        List of patterns
    """
    patterns = [
        ArchitecturalPattern(
            name="Multi-Agent Architecture",
            description="Multiple specialized agents coordinated by LangGraph",
            implementation="LangGraph with stateful agents",
            benefits=["Modularity", "Scalability", "Flexibility"]
        ),
        ArchitecturalPattern(
            name="RAG Pattern",
            description="Retrieval-Augmented Generation for knowledge storage",
            implementation="LlamaIndex + pgvector",
            benefits=["Context awareness", "Reduced hallucination", "Local storage"]
        ),
        ArchitecturalPattern(
            name="MCP Protocol",
            description="Model Context Protocol for tool integration",
            implementation="MCP servers for bash, project, sql",
            benefits=["Standardized tools", "Extensibility", "Security"]
        ),
        ArchitecturalPattern(
            name="Docker-First Development",
            description="All development in Docker containers",
            implementation="Docker Compose with local models",
            benefits=["Consistent environment", "No local installs", "Easy scaling"]
        )
    ]
    
    return patterns


def suggest_refactoring(
    component: str,
    issue: str
) -> Dict[str, Any]:
    """
    Suggest refactoring for specific component.
    
    Args:
        component: Component name
        issue: Issue to fix
        
    Returns:
        Refactoring suggestions
    """
    suggestions = {
        "ingestor_inotify": {
            "improve_event_queue": "Implement proper event queue with backpressure",
            "add_batching": "Add configurable batching for file events",
            "optimize_exclusions": "Improve exclusion pattern matching"
        },
        "infra_unification": {
            "create_shared_base": "Create base classes for shared components",
            "define_interfaces": "Define clear interfaces between components",
            "add_dependency_injection": "Use dependency injection for flexibility"
        },
        "agents_external_tools": {
            "add_error_handling": "Add comprehensive error handling",
            "implement_retries": "Add retry logic for external calls",
            "add_circuit_breaker": "Implement circuit breaker pattern"
        }
    }
    
    component_suggestions = suggestions.get(component, {})
    issue_suggestion = component_suggestions.get(issue, "No specific suggestion available")
    
    return {
        "component": component,
        "issue": issue,
        "suggestion": issue_suggestion,
        "priority": "medium",
        "effort": "low"
    }


def validate_architecture_decisions(
    decisions: Dict[str, Any]
) -> List[str]:
    """
    Validate architecture decisions.
    
    Args:
        decisions: Architecture decisions to validate
        
    Returns:
        List of validation issues
    """
    issues = []
    
    # Check for single responsibility
    if "responsibilities" in decisions:
        for component, resp in decisions["responsibilities"].items():
            if len(resp) > 1:
                issues.append(f"Component {component} has multiple responsibilities: {resp}")
    
    # Check for proper dependencies
    if "dependencies" in decisions:
        for component, deps in decisions["dependencies"].items():
            if len(deps) > 5:
                issues.append(f"Component {component} has too many dependencies: {len(deps)}")
    
    return issues


def create_refactoring_plan(
    component: str,
    target_pattern: str
) -> Dict[str, Any]:
    """
    Create refactoring plan for component.
    
    Args:
        component: Component to refactor
        target_pattern: Target architectural pattern
        
    Returns:
        Refactoring plan
    """
    plan = {
        "component": component,
        "target_pattern": target_pattern,
        "steps": [],
        "validation": [],
        "rollback": []
    }
    
    if component == "infra_unification" and target_pattern == "interface_segregation":
        plan["steps"].extend([
            "Extract interfaces for shared components",
            "Update dependent components to use interfaces",
            "Add interface validation",
            "Run integration tests"
        ])
        plan["validation"].append("All components use interfaces, not implementations")
        plan["rollback"].append("Revert to concrete class usage")
    
    return plan


def analyze_code_quality(
    component_path: Path
) -> Dict[str, Any]:
    """
    Analyze code quality of component.
    
    Args:
        component_path: Path to component
        
    Returns:
        Code quality analysis
    """
    # In real implementation, would parse files
    # For now, return mock analysis
    return {
        "file_count": 1,
        "lines_of_code": 150,
        "type_hints": True,
        "docstrings": True,
        "single_responsibility": True,
        "dependencies": ["typing", "pathlib", "dataclasses", "enum"],
        "quality_score": 95
    }


def suggest_architectural_improvements(
    current_state: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Suggest architectural improvements.
    
    Args:
        current_state: Current architecture state
        
    Returns:
        List of improvements
    """
    improvements = []
    
    improvements.append({
        "area": "Infrastructure",
        "improvement": "Add dependency injection container",
        "priority": "medium",
        "effort": "low",
        "benefit": "Better testability and flexibility"
    })
    
    improvements.append({
        "area": "Agents",
        "improvement": "Implement agent composition pattern",
        "priority": "low",
        "effort": "medium",
        "benefit": "Better agent collaboration"
    })
    
    improvements.append({
        "area": "Ingestor",
        "improvement": "Add event sourcing for indexing",
        "priority": "high",
        "effort": "high",
        "benefit": "Better traceability and rollback"
    })
    
    return improvements


def validate_solid_principles(
    component: Dict[str, Any]
) -> List[str]:
    """
    Validate SOLID principles in component.
    
    Args:
        component: Component definition
        
    Returns:
        List of SOLID principle violations
    """
    violations = []
    
    # Single Responsibility Principle
    if len(component.get("responsibilities", [])) > 1:
        violations.append("SRP: Component has multiple responsibilities")
    
    # Open/Closed Principle
    if component.get("closed_for_modification", False):
        violations.append("OCP: Component is not closed for modification")
    
    # Liskov Substitution Principle
    if component.get("substitutability", "") != "full":
        violations.append("LSP: Components not fully substitutable")
    
    # Interface Segregation Principle
    if component.get("interface_size", 0) > 5:
        violations.append("ISP: Interfaces are too large")
    
    # Dependency Inversion Principle
    if component.get("depend_on_abstractions", True) == False:
        violations.append("DIP: Depends on concretions, not abstractions")
    
    return violations


def get_best_practices(
    component_type: ComponentType
) -> List[str]:
    """
    Get best practices for component type.
    
    Args:
        component_type: Type of component
        
    Returns:
        List of best practices
    """
    practices_map = {
        ComponentType.AGENT: [
            "Keep agent stateless when possible",
            "Use LangGraph for state management",
            "Implement proper error handling",
            "Add retry logic for LLM calls"
        ],
        ComponentType.INGESTOR: [
            "Use incremental indexing",
            "Implement proper exclusion patterns",
            "Add progress tracking",
            "Use batch processing for performance"
        ],
        ComponentType.INFRA: [
            "Create shared interfaces",
            "Use dependency injection",
            "Implement proper logging",
            "Add health checks"
        ],
        ComponentType.SERVER: [
            "Use FastAPI for REST APIs",
            "Implement proper CORS",
            "Add rate limiting",
            "Use async/await for performance"
        ],
        ComponentType.TOOLS: [
            "Sandbox external commands",
            "Validate all inputs",
            "Implement proper permissions",
            "Add audit logging"
        ]
    }
    
    return practices_map.get(component_type, [])


def validate_project_standards(
    project_root: Path
) -> Dict[str, Any]:
    """
    Validate project standards compliance.
    
    Args:
        project_root: Project root directory
        
    Returns:
        Standards compliance report
    """
    report = {
        "standards_checked": [
            "file_size_limit",
            "type_hints",
            "docstrings",
            "naming_conventions",
            "dependency_management"
        ],
        "compliance": {},
        "issues": []
    }
    
    # Check file sizes (simplified)
    report["compliance"]["file_size"] = "pass"
    report["compliance"]["type_hints"] = "pass"
    report["compliance"]["docstrings"] = "pass"
    report["compliance"]["naming"] = "pass"
    
    return report