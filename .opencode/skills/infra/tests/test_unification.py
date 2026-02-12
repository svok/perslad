"""Tests for Infrastructure unification skill."""

import pytest
from pathlib import Path
from skills.infra.unification import (
    analyze_infra_structure,
    identify_shared_components,
    plan_unification,
    Component,
    ComponentType
)


def test_analyze_infra_structure():
    """Test analyzing infrastructure structure."""
    # Use current project directory for testing
    base_path = Path("/sda/sokatov/own/perslad")
    
    result = analyze_infra_structure(base_path)
    
    assert "total_components" in result
    assert "components_by_type" in result
    assert isinstance(result["total_components"], int)


def test_identify_shared_components():
    """Test identifying shared components between agents and ingestor."""
    # Create test components
    agent_comp = Component(
        name="test_manager",
        file_path=Path("/agents/infra/test_manager.py"),
        component_type=ComponentType.MANAGER,
        dependencies=["utils"],
        is_shared=False
    )
    
    ingestor_comp = Component(
        name="test_manager",
        file_path=Path("/ingestor/infra/test_manager.py"),
        component_type=ComponentType.MANAGER,
        dependencies=["utils"],
        is_shared=False
    )
    
    shared = identify_shared_components([agent_comp], [ingestor_comp])
    
    assert len(shared) == 1
    assert shared[0].name == "test_manager"


def test_plan_unification():
    """Test planning unification strategy."""
    shared_components = [
        Component(
            name="shared_manager",
            file_path=Path("/shared/infra/shared_manager.py"),
            component_type=ComponentType.MANAGER,
            dependencies=["utils"]
        )
    ]
    
    plan = plan_unification(shared_components, Path("/shared"))
    
    assert len(plan.components_to_unify) == 1
    assert len(plan.migration_steps) > 0
    assert plan.testing_strategy is not None


def test_component_determination():
    """Test component type determination."""
    from skills.infra.unification import determine_component_type
    
    # Test manager
    manager_file = Path("/path/to/my_manager.py")
    assert determine_component_type(manager_file) == ComponentType.MANAGER
    
    # Test adapter
    adapter_file = Path("/path/to/my_adapter.py")
    assert determine_component_type(adapter_file) == ComponentType.ADAPTER
    
    # Test service
    service_file = Path("/path/to/my_service.py")
    assert determine_component_type(service_file) == ComponentType.SERVICE


def test_function_extraction():
    """Test function extraction from Python files."""
    from skills.infra.unification import extract_functions_from_file
    
    # Create test file
    test_file = Path("/tmp/test_extraction.py")
    test_content = """
def test_function1():
    pass

def test_function2():
    pass

class TestClass:
    def method(self):
        pass
"""
    test_file.write_text(test_content)
    
    functions = extract_functions_from_file(test_file)
    
    assert len(functions) >= 2
    assert "test_function1" in functions
    assert "test_function2" in functions
    
    # Cleanup
    test_file.unlink()


def test_dependency_finding():
    """Test finding dependencies in Python files."""
    from skills.infra.unification import find_dependencies
    
    # Create test file with imports
    test_file = Path("/tmp/test_dependencies.py")
    test_content = """
from pathlib import Path
from typing import Dict, List
import os
from . import local_module
"""
    test_file.write_text(test_content)
    
    deps = find_dependencies(test_file)
    
    assert len(deps) >= 3
    assert "pathlib" in deps
    assert "typing" in deps
    
    # Cleanup
    test_file.unlink()