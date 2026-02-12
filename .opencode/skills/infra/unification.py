"""
Infrastructure unification skill for agents with ingestor.
Shared components and patterns across infrastructure layer.

Design principles:
- Maximum 150 lines per file
- Type hints everywhere
- Single responsibility principle
- DRY and KISS patterns
"""

from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class ComponentType(Enum):
    """Types of infrastructure components."""
    MANAGER = "manager"
    ADAPTER = "adapter"
    CLIENT = "client"
    SERVICE = "service"
    UTIL = "util"


@dataclass
class Component:
    """Infrastructure component information."""
    name: str
    file_path: Path
    component_type: ComponentType
    dependencies: List[str]
    is_shared: bool = False
    functions: Optional[List[str]] = None

    def __post_init__(self):
        if self.functions is None:
            self.functions = []


@dataclass
class UnificationPlan:
    """Plan for infrastructure unification."""
    components_to_unify: List[Component]
    shared_components: List[Component]
    migration_steps: List[str]
    testing_strategy: str
    rollback_plan: str


def analyze_infra_structure(base_path: Path) -> Dict[str, Any]:
    """
    Analyze current infrastructure structure.
    
    Args:
        base_path: Base path to analyze (agents/infra, ingestor/infra)
        
    Returns:
        Analysis results
    """
    components = []
    
    # Find all Python files in infra directories
    for infra_dir in base_path.rglob("infra"):
        for py_file in infra_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
                
            # Determine component type from file name and content
            comp_type = determine_component_type(py_file)
            
            # Extract functions from file (simplified - would parse AST in real implementation)
            functions = extract_functions_from_file(py_file)
            
            # Find dependencies (imports)
            deps = find_dependencies(py_file)
            
            component = Component(
                name=py_file.stem,
                file_path=py_file,
                component_type=comp_type,
                dependencies=deps,
                functions=functions if functions else []
            )
            components.append(component)
    
    return {
        "total_components": len(components),
        "components_by_type": count_by_type(components),
        "shared_candidates": find_shared_candidates(components),
        "structure": components
    }


def identify_shared_components(
    agents_components: List[Component],
    ingestor_components: List[Component]
) -> List[Component]:
    """
    Find components that can be unified.
    
    Args:
        agents_components: Components from agents/infra
        ingestor_components: Components from ingestor/infra
        
    Returns:
        List of shared components
    """
    shared = []
    
    # Group by component type and name
    agents_by_type = group_by_type(agents_components)
    ingestor_by_type = group_by_type(ingestor_components)
    
    for comp_type in ComponentType:
        agents_list = agents_by_type.get(comp_type, [])
        ingestor_list = ingestor_by_type.get(comp_type, [])
        
        # Find common names
        agent_names = {c.name for c in agents_list}
        ingestor_names = {c.name for c in ingestor_list}
        
        common_names = agent_names.intersection(ingestor_names)
        
        for name in common_names:
            # Find components with this name
            agent_comp = next((c for c in agents_list if c.name == name), None)
            ingestor_comp = next((c for c in ingestor_list if c.name == name), None)
            
            if agent_comp and ingestor_comp:
                # Mark as shared
                agent_comp.is_shared = True
                ingestor_comp.is_shared = True
                shared.append(agent_comp)
    
    return shared


def plan_unification(
    shared_components: List[Component],
    base_path: Path
) -> UnificationPlan:
    """
    Plan unification strategy.
    
    Args:
        shared_components: Components to unify
        base_path: Base path for shared components
        
    Returns:
        Unification plan
    """
    migration_steps = []
    
    for component in shared_components:
        step = f"Move {component.name} to shared location: {base_path}/shared/{component.component_type.value}"
        migration_steps.append(step)
        
        step = f"Update imports in agents/infra and ingestor/infra"
        migration_steps.append(step)
        
        step = f"Update type hints and interfaces"
        migration_steps.append(step)
    
    plan = UnificationPlan(
        components_to_unify=shared_components,
        shared_components=[],
        migration_steps=migration_steps,
        testing_strategy="Run integration tests for both agents and ingestor",
        rollback_plan="Revert to original locations if tests fail"
    )
    
    return plan


def implement_shared_patterns(
    plan: UnificationPlan,
    base_path: Path
) -> Dict[str, Any]:
    """
    Implement shared infrastructure patterns.
    
    Args:
        plan: Unification plan
        base_path: Base path for shared components
        
    Returns:
        Implementation results
    """
    results = []
    
    for component in plan.components_to_unify:
        # Create shared directory structure
        shared_dir = base_path / "shared" / component.component_type.value
        shared_dir.mkdir(parents=True, exist_ok=True)
        
        # Create unified component
        unified_file = shared_dir / f"{component.name}.py"
        
        result = {
            "component": component.name,
            "unified_path": str(unified_file),
            "status": "created"
        }
        results.append(result)
    
    return {
        "total_unified": len(results),
        "components": results,
        "shared_base": str(base_path / "shared")
    }


def determine_component_type(file_path: Path) -> ComponentType:
    """
    Determine component type from file path and content.
    
    Args:
        file_path: Path to component file
        
    Returns:
        Component type
    """
    name_lower = file_path.stem.lower()
    
    if "manager" in name_lower:
        return ComponentType.MANAGER
    elif "adapter" in name_lower or "client" in name_lower:
        return ComponentType.ADAPTER
    elif "service" in name_lower:
        return ComponentType.SERVICE
    elif "util" in name_lower or "helper" in name_lower:
        return ComponentType.UTIL
    else:
        return ComponentType.SERVICE


def extract_functions_from_file(file_path: Path) -> List[str]:
    """
    Extract function names from Python file (simplified).
    
    Args:
        file_path: Path to Python file
        
    Returns:
        List of function names
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        functions = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('def '):
                # Extract function name
                func_name = line[4:].split('(')[0].strip()
                functions.append(func_name)
        
        return functions
    except Exception:
        return []


def find_dependencies(file_path: Path) -> List[str]:
    """
    Find imports/dependencies from Python file.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        List of dependency names
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        dependencies = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith(('from ', 'import ')):
                # Simple extraction of module names
                dep = line.split()[1]
                if dep != '.':
                    dependencies.append(dep)
        
        return dependencies
    except Exception:
        return []


def count_by_type(components: List[Component]) -> Dict[str, int]:
    """Count components by type."""
    counts = {}
    for comp in components:
        comp_type = comp.component_type.value
        counts[comp_type] = counts.get(comp_type, 0) + 1
    return counts


def group_by_type(components: List[Component]) -> Dict[ComponentType, List[Component]]:
    """Group components by type."""
    groups = {}
    for comp in components:
        if comp.component_type not in groups:
            groups[comp.component_type] = []
        groups[comp.component_type].append(comp)
    return groups


def find_shared_candidates(components: List[Component]) -> List[Component]:
    """Find components that could be shared."""
    candidates = []
    
    # Count occurrences of component names
    name_counts = {}
    for comp in components:
        name_counts[comp.name] = name_counts.get(comp.name, 0) + 1
    
    # Components with multiple occurrences are candidates
    for name, count in name_counts.items():
        if count > 1:
            candidate = next((c for c in components if c.name == name), None)
            if candidate:
                candidates.append(candidate)
    
    return candidates


def validate_unification_plan(plan: UnificationPlan) -> List[str]:
    """
    Validate unification plan.
    
    Args:
        plan: Plan to validate
        
    Returns:
        List of validation errors
    """
    errors = []
    
    if not plan.components_to_unify:
        errors.append("No components selected for unification")
    
    if not plan.migration_steps:
        errors.append("No migration steps specified")
    
    if not plan.testing_strategy:
        errors.append("No testing strategy defined")
    
    if not plan.rollback_plan:
        errors.append("No rollback plan defined")
    
    return errors