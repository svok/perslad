"""
Fact graph building skill for ingestor.
RDF/OWL ontology and knowledge graph construction.

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


class GraphType(Enum):
    """Types of knowledge graphs."""
    RDF = "rdf"           # Resource Description Framework
    OWL = "owl"           # Web Ontology Language
    RDF_STAR = "rdf_star" # RDF* extension
    PROPERTY_GRAPH = "property_graph"  # Property graph (NebulaGraph)


@dataclass
class RDFTriple:
    """RDF triple (subject, predicate, object)."""
    subject: str
    predicate: str
    object: str
    graph: Optional[str] = None
    context: Optional[str] = None


@dataclass
class OntologyClass:
    """OWL ontology class."""
    name: str
    parent_classes: Optional[List[str]] = None
    properties: Optional[List[str]] = None
    description: Optional[str] = None

    def __post_init__(self):
        if self.parent_classes is None:
            self.parent_classes = []
        if self.properties is None:
            self.properties = []


@dataclass
class OntologyProperty:
    """OWL ontology property."""
    name: str
    domain: Optional[List[str]] = None
    range: Optional[List[str]] = None
    is_functional: bool = False
    is_inverse_functional: bool = False
    description: Optional[str] = None

    def __post_init__(self):
        if self.domain is None:
            self.domain = []
        if self.range is None:
            self.range = []


@dataclass
class GraphSchema:
    """Graph schema configuration."""
    graph_type: GraphType
    base_uri: str
    default_graph: str
    enable_inference: bool = False
    inference_rules: Optional[List[str]] = None

    def __post_init__(self):
        if self.inference_rules is None:
            self.inference_rules = []


def setup_graph_schema(schema_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Configure graph schema for facts.
    
    Args:
        schema_config: Schema configuration
        
    Returns:
        Schema setup result
    """
    graph_type = GraphType(schema_config.get("type", "rdf"))
    
    schema = GraphSchema(
        graph_type=graph_type,
        base_uri=schema_config.get("base_uri", "http://perslad.local/ontology/"),
        default_graph=schema_config.get("default_graph", "main"),
        enable_inference=schema_config.get("enable_inference", False),
        inference_rules=schema_config.get("inference_rules", [])
    )
    
    return {
        "status": "configured",
        "graph_type": schema.graph_type.value,
        "base_uri": schema.base_uri,
        "default_graph": schema.default_graph,
        "inference_enabled": schema.enable_inference
    }


def build_fact_graph(
    ingested_data: Dict[str, Any],
    schema: GraphSchema,
    ontology_classes: Optional[List[OntologyClass]] = None,
    ontology_properties: Optional[List[OntologyProperty]] = None
) -> Dict[str, Any]:
    """
    Build fact graph from ingested data.
    
    Args:
        ingested_data: Data from ingestor pipeline
        schema: Graph schema configuration
        ontology_classes: Optional ontology classes
        ontology_properties: Optional ontology properties
        
    Returns:
        Graph construction results
    """
    triples = []
    entities = set()
    relations = set()
    
    # Extract entities and relations from ingested data
    for item in ingested_data.get("chunks", []):
        # Extract entities from text (simplified - would use NER in real implementation)
        item_entities = extract_entities(item.get("content", ""))
        
        for entity in item_entities:
            entities.add(entity)
            
            # Create triples based on entity type
            if "function" in entity.lower():
                triples.append(RDFTriple(
                    subject=entity,
                    predicate="rdf:type",
                    object="Function",
                    graph=schema.default_graph
                ))
            elif "class" in entity.lower():
                triples.append(RDFTriple(
                    subject=entity,
                    predicate="rdf:type",
                    object="Class",
                    graph=schema.default_graph
                ))
    
    # Add ontology-based triples
    if ontology_classes:
        for cls in ontology_classes:
            triples.append(RDFTriple(
                subject=f"{schema.base_uri}{cls.name}",
                predicate="rdf:type",
                object="owl:Class",
                graph=schema.default_graph
            ))
            
            # Ensure parent_classes list exists
            parents = cls.parent_classes if cls.parent_classes is not None else []
            for parent in parents:
                triples.append(RDFTriple(
                    subject=f"{schema.base_uri}{cls.name}",
                    predicate="rdfs:subClassOf",
                    object=f"{schema.base_uri}{parent}",
                    graph=schema.default_graph
                ))
    
    return {
        "status": "built",
        "triples_count": len(triples),
        "entities_count": len(entities),
        "relations_count": len(relations),
        "triples": triples,
        "schema": {
            "type": schema.graph_type.value,
            "base_uri": schema.base_uri
        }
    }


def query_fact_graph(query: Dict[str, Any], graph_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query the fact graph.
    
    Args:
        query: Query parameters (SPARQL-like)
        graph_data: Graph data
        
    Returns:
        Query results
    """
    query_type = query.get("type", "select")
    sparql = query.get("sparql")
    
    if query_type == "select":
        # Simplified SPARQL-like query processing
        results = []
        for triple in graph_data.get("triples", []):
            # Check if triple matches query pattern
            if matches_pattern(triple, query.get("pattern", {})):
                results.append({
                    "subject": triple.subject,
                    "predicate": triple.predicate,
                    "object": triple.object
                })
        
        return {
            "type": "select",
            "results": results,
            "count": len(results)
        }
    
    elif query_type == "ask":
        # Boolean query
        matches = any(
            matches_pattern(triple, query.get("pattern", {}))
            for triple in graph_data.get("triples", [])
        )
        return {
            "type": "ask",
            "result": matches
        }
    
    elif query_type == "construct":
        # Construct new graph from query
        new_triples = []
        for triple in graph_data.get("triples", []):
            if matches_pattern(triple, query.get("pattern", {})):
                new_triples.append(triple)
        
        return {
            "type": "construct",
            "triples": new_triples,
            "count": len(new_triples)
        }
    
    else:
        return {"error": f"Unsupported query type: {query_type}"}


def visualize_graph(graph_data: Dict[str, Any], format: str = "mermaid") -> Dict[str, Any]:
    """
    Visualize fact graph.
    
    Args:
        graph_data: Graph data to visualize
        format: Output format
        
    Returns:
        Visualization data
    """
    if format == "mermaid":
        # Generate Mermaid diagram
        mermaid_lines = ["graph TD"]
        
        entities = set()
        for triple in graph_data.get("triples", []):
            entities.add(triple.subject)
            entities.add(triple.object)
        
        # Add nodes
        for entity in sorted(entities):
            safe_entity = entity.replace(":", "_")
            mermaid_lines.append(f'    {safe_entity}["{entity}"]')
        
        # Add edges
        for triple in graph_data.get("triples", []):
            safe_subject = triple.subject.replace(":", "_")
            safe_object = triple.object.replace(":", "_")
            mermaid_lines.append(f'    {safe_subject} -->|{triple.predicate}| {safe_object}')
        
        return {
            "format": "mermaid",
            "diagram": "\n".join(mermaid_lines),
            "entities": list(entities),
            "edges": len(graph_data.get("triples", []))
        }
    
    elif format == "json":
        # Return JSON representation
        return {
            "format": "json",
            "data": graph_data,
            "triples": graph_data.get("triples", [])
        }
    
    else:
        return {"error": f"Unsupported format: {format}"}


def extract_entities(text: str) -> List[str]:
    """
    Extract entities from text (simplified).
    
    Args:
        text: Text to extract entities from
        
    Returns:
        List of entity names
    """
    # Simplified entity extraction - in real implementation, use NER
    words = text.split()
    entities = []
    
    # Simple heuristic: capitalize words might be entities
    for word in words:
        word = word.strip('.,;:()[]{}')
        if len(word) > 3 and word[0].isupper() and word[1:].islower():
            entities.append(word)
    
    return entities


def matches_pattern(triple: RDFTriple, pattern: Dict[str, Any]) -> bool:
    """
    Check if triple matches query pattern.
    
    Args:
        triple: RDF triple
        pattern: Query pattern
        
    Returns:
        True if matches
    """
    subject_match = pattern.get("subject") is None or pattern["subject"] in triple.subject
    predicate_match = pattern.get("predicate") is None or pattern["predicate"] in triple.predicate
    object_match = pattern.get("object") is None or pattern["object"] in triple.object
    
    return subject_match and predicate_match and object_match


def add_inference_rules(schema: GraphSchema, rules: List[str]) -> Dict[str, Any]:
    """
    Add inference rules to graph schema.
    
    Args:
        schema: Graph schema
        rules: Inference rules
        
    Returns:
        Updated schema
    """
    if schema.inference_rules is None:
        schema.inference_rules = []
    schema.inference_rules.extend(rules)
    schema.enable_inference = True
    
    return {
        "status": "rules_added",
        "rule_count": len(rules),
        "inference_enabled": schema.enable_inference
    }


def validate_graph_schema(schema: Dict[str, Any]) -> List[str]:
    """
    Validate graph schema configuration.
    
    Args:
        schema: Schema configuration
        
    Returns:
        List of validation errors
    """
    errors = []
    
    if not schema.get("type"):
        errors.append("Graph type is required")
    
    if not schema.get("base_uri"):
        errors.append("Base URI is required")
    
    valid_types = [t.value for t in GraphType]
    if schema.get("type") not in valid_types:
        errors.append(f"Invalid graph type. Must be one of: {valid_types}")
    
    return errors


def export_graph(graph_data: Dict[str, Any], format: str = "turtle") -> Dict[str, Any]:
    """
    Export graph in various formats.
    
    Args:
        graph_data: Graph data to export
        format: Export format
        
    Returns:
        Export results
    """
    if format == "turtle":
        # Export as Turtle RDF format
        lines = []
        lines.append("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
        lines.append("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
        lines.append("@prefix owl: <http://www.w3.org/2002/07/owl#> .")
        lines.append("")
        
        for triple in graph_data.get("triples", []):
            lines.append(f'<{triple.subject}> <{triple.predicate}> <{triple.object}> .')
        
        return {
            "format": "turtle",
            "content": "\n".join(lines),
            "triples": len(graph_data.get("triples", []))
        }
    
    elif format == "json-ld":
        # Export as JSON-LD
        json_ld = {
            "@context": {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "owl": "http://www.w3.org/2002/07/owl#"
            },
            "@graph": []
        }
        
        for triple in graph_data.get("triples", []):
            json_ld["@graph"].append({
                "@id": triple.subject,
                triple.predicate: {"@id": triple.object}
            })
        
        return {
            "format": "json-ld",
            "data": json_ld,
            "triples": len(graph_data.get("triples", []))
        }
    
    else:
        return {"error": f"Unsupported export format: {format}"}