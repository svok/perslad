"""Tests for Fact graph building skill."""

import pytest
from skills.ingestor.graph_builder import (
    setup_graph_schema,
    build_fact_graph,
    query_fact_graph,
    visualize_graph,
    export_graph,
    validate_graph_schema,
    extract_entities,
    GraphType,
    GraphSchema,
    RDFTriple
)


def test_setup_graph_schema():
    """Test setting up graph schema."""
    schema_config = {
        "type": "rdf",
        "base_uri": "http://test.local/",
        "default_graph": "test_graph",
        "enable_inference": False
    }
    
    result = setup_graph_schema(schema_config)
    
    assert result["status"] == "configured"
    assert result["graph_type"] == "rdf"
    assert result["base_uri"] == "http://test.local/"


def test_build_fact_graph():
    """Test building fact graph from ingested data."""
    ingested_data = {
        "chunks": [
            {"content": "Function1 is a function"},
            {"content": "Class1 is a class"}
        ]
    }
    
    schema = GraphSchema(
        graph_type=GraphType.RDF,
        base_uri="http://test.local/",
        default_graph="test"
    )
    
    result = build_fact_graph(ingested_data, schema)
    
    assert result["status"] == "built"
    assert result["triples_count"] > 0
    assert "triples" in result


def test_query_fact_graph():
    """Test querying fact graph."""
    # Create RDFTriple objects
    triples = [
        RDFTriple(subject="Function1", predicate="rdf:type", object="Function"),
        RDFTriple(subject="Class1", predicate="rdf:type", object="Class")
    ]
    
    graph_data = {"triples": triples}
    
    query = {
        "type": "select",
        "pattern": {"predicate": "rdf:type"}
    }
    
    result = query_fact_graph(query, graph_data)
    
    assert result["type"] == "select"
    assert result["count"] >= 0


def test_visualize_graph():
    """Test graph visualization."""
    # Create RDFTriple objects
    triples = [
        RDFTriple(subject="A", predicate="relatesTo", object="B"),
        RDFTriple(subject="B", predicate="relatesTo", object="C")
    ]
    
    graph_data = {"triples": triples}
    
    result = visualize_graph(graph_data, format="mermaid")
    
    assert result["format"] == "mermaid"
    assert "diagram" in result
    assert "entities" in result


def test_export_graph():
    """Test graph export functionality."""
    # Create RDFTriple objects
    triples = [
        RDFTriple(subject="A", predicate="p", object="B")
    ]
    
    graph_data = {"triples": triples}
    
    # Test Turtle export
    result = export_graph(graph_data, format="turtle")
    assert result["format"] == "turtle"
    assert "content" in result
    
    # Test JSON-LD export
    result = export_graph(graph_data, format="json-ld")
    assert result["format"] == "json-ld"
    assert "data" in result


def test_schema_validation():
    """Test graph schema validation."""
    from skills.ingestor.graph_builder import validate_graph_schema
    
    valid_schema = {
        "type": "rdf",
        "base_uri": "http://test.local/"
    }
    
    errors = validate_graph_schema(valid_schema)
    assert len(errors) == 0
    
    invalid_schema = {
        "type": "invalid_type"
    }
    
    errors = validate_graph_schema(invalid_schema)
    assert len(errors) > 0


def test_entity_extraction():
    """Test entity extraction from text."""
    from skills.ingestor.graph_builder import extract_entities
    
    text = "Function1 calls Class2 from Module3"
    entities = extract_entities(text)
    
    assert isinstance(entities, list)
    # Simple test - should find capitalized words
    assert len(entities) >= 1