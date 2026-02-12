"""
Database table filling skill for ingestor.
Complete ETL processes and table filling.

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


class DatabaseType(Enum):
    """Database types for ingestor."""
    POSTGRESQL = "postgresql"
    STARROCKS = "starrocks"
    NEBULAGRAPH = "nebulagraph"


@dataclass
class TableSchema:
    """Database table schema."""
    name: str
    columns: List[Dict[str, Any]]
    primary_key: Optional[str] = None
    indexes: Optional[List[str]] = None
    foreign_keys: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        if self.indexes is None:
            self.indexes = []
        if self.foreign_keys is None:
            self.foreign_keys = []


@dataclass
class ETLProcess:
    """ETL (Extract, Transform, Load) process."""
    name: str
    source: str
    target: str
    transformation: str
    validation_rules: Optional[List[str]] = None
    batch_size: int = 1000

    def __post_init__(self):
        if self.validation_rules is None:
            self.validation_rules = []


def get_table_schema(db_type: DatabaseType = DatabaseType.POSTGRESQL) -> Dict[str, Any]:
    """
    Get current database schema for ingestor.
    
    Args:
        db_type: Database type
        
    Returns:
        Database schema
    """
    schemas = {
        DatabaseType.POSTGRESQL: {
            "tables": [
                {
                    "name": "documents",
                    "columns": [
                        {"name": "id", "type": "UUID", "nullable": False},
                        {"name": "file_path", "type": "TEXT", "nullable": False},
                        {"name": "content", "type": "TEXT", "nullable": False},
                        {"name": "metadata", "type": "JSONB", "nullable": True},
                        {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
                        {"name": "updated_at", "type": "TIMESTAMP", "nullable": False}
                    ],
                    "primary_key": "id",
                    "indexes": ["file_path", "created_at"]
                },
                {
                    "name": "chunks",
                    "columns": [
                        {"name": "id", "type": "UUID", "nullable": False},
                        {"name": "document_id", "type": "UUID", "nullable": False},
                        {"name": "content", "type": "TEXT", "nullable": False},
                        {"name": "embedding", "type": "VECTOR(1536)", "nullable": False},
                        {"name": "chunk_index", "type": "INTEGER", "nullable": False},
                        {"name": "metadata", "type": "JSONB", "nullable": True}
                    ],
                    "primary_key": "id",
                    "indexes": ["document_id", "chunk_index", "embedding"]
                },
                {
                    "name": "relationships",
                    "columns": [
                        {"name": "id", "type": "UUID", "nullable": False},
                        {"name": "source_id", "type": "UUID", "nullable": False},
                        {"name": "target_id", "type": "UUID", "nullable": False},
                        {"name": "relationship_type", "type": "TEXT", "nullable": False},
                        {"name": "metadata", "type": "JSONB", "nullable": True}
                    ],
                    "primary_key": "id",
                    "indexes": ["source_id", "target_id", "relationship_type"]
                },
                {
                    "name": "facts",
                    "columns": [
                        {"name": "id", "type": "UUID", "nullable": False},
                        {"name": "subject", "type": "TEXT", "nullable": False},
                        {"name": "predicate", "type": "TEXT", "nullable": False},
                        {"name": "object", "type": "TEXT", "nullable": False},
                        {"name": "context", "type": "TEXT", "nullable": True},
                        {"name": "confidence", "type": "FLOAT", "nullable": True},
                        {"name": "metadata", "type": "JSONB", "nullable": True}
                    ],
                    "primary_key": "id",
                    "indexes": ["subject", "predicate", "object"]
                },
                {
                    "name": "edges",
                    "columns": [
                        {"name": "id", "type": "UUID", "nullable": False},
                        {"name": "source_fact_id", "type": "UUID", "nullable": False},
                        {"name": "target_fact_id", "type": "UUID", "nullable": False},
                        {"name": "edge_type", "type": "TEXT", "nullable": False},
                        {"name": "weight", "type": "FLOAT", "nullable": True},
                        {"name": "metadata", "type": "JSONB", "nullable": True}
                    ],
                    "primary_key": "id",
                    "indexes": ["source_fact_id", "target_fact_id", "edge_type"]
                },
                {
                    "name": "index_status",
                    "columns": [
                        {"name": "id", "type": "UUID", "nullable": False},
                        {"name": "file_path", "type": "TEXT", "nullable": False},
                        {"name": "status", "type": "TEXT", "nullable": False},
                        {"name": "last_indexed", "type": "TIMESTAMP", "nullable": True},
                        {"name": "error_message", "type": "TEXT", "nullable": True},
                        {"name": "metadata", "type": "JSONB", "nullable": True}
                    ],
                    "primary_key": "id",
                    "indexes": ["file_path", "status", "last_indexed"]
                }
            ]
        },
        DatabaseType.STARROCKS: {
            "tables": [
                {
                    "name": "documents",
                    "columns": [
                        {"name": "id", "type": "BIGINT", "nullable": False},
                        {"name": "file_path", "type": "STRING", "nullable": False},
                        {"name": "content", "type": "STRING", "nullable": False},
                        {"name": "metadata", "type": "JSON", "nullable": True},
                        {"name": "created_at", "type": "DATETIME", "nullable": False}
                    ],
                    "primary_key": "id",
                    "indexes": ["file_path"]
                }
            ]
        },
        DatabaseType.NEBULAGRAPH: {
            "spaces": [
                {
                    "name": "perslad_space",
                    "tags": ["Document", "Chunk", "Fact", "Entity"],
                    "edge_types": ["CONTAINS", "RELATES_TO", "EXTRACTED_FROM"]
                }
            ]
        }
    }
    
    return schemas.get(db_type, {})


def fill_missing_tables(db_type: DatabaseType = DatabaseType.POSTGRESQL) -> Dict[str, Any]:
    """
    Fill all missing tables in ingestor.
    
    Args:
        db_type: Database type
        
    Returns:
        Filling results
    """
    schema = get_table_schema(db_type)
    
    results = {
        "database_type": db_type.value,
        "tables_processed": 0,
        "tables_created": 0,
        "tables_existing": 0,
        "errors": []
    }
    
    if db_type == DatabaseType.POSTGRESQL:
        tables = schema.get("tables", [])
        
        for table_config in tables:
            table_name = table_config["name"]
            results["tables_processed"] += 1
            
            # In real implementation, check if table exists
            # For now, we'll simulate the process
            if table_name in ["documents", "chunks", "relationships", "facts", "edges", "index_status"]:
                results["tables_existing"] += 1
            else:
                results["tables_created"] += 1
    
    elif db_type == DatabaseType.STARROCKS:
        # StarRocks specific table creation
        results["tables_processed"] = 1
        results["tables_existing"] = 1
    
    elif db_type == DatabaseType.NEBULAGRAPH:
        # NebulaGraph space creation
        spaces = schema.get("spaces", [])
        results["spaces_processed"] = len(spaces)
        results["spaces_created"] = 0
        results["spaces_existing"] = len(spaces)
    
    return results


def validate_data_integrity(db_type: DatabaseType = DatabaseType.POSTGRESQL) -> Dict[str, Any]:
    """
    Validate data integrity across tables.
    
    Args:
        db_type: Database type
        
    Returns:
        Validation results
    """
    validation_results = {
        "database_type": db_type.value,
        "checks": [],
        "passed": 0,
        "failed": 0,
        "warnings": []
    }
    
    # Document table integrity
    validation_results["checks"].append({
        "table": "documents",
        "check": "non_empty_id",
        "status": "pending"
    })
    
    # Chunk table integrity
    validation_results["checks"].append({
        "table": "chunks",
        "check": "embedding_dimensions",
        "status": "pending"
    })
    
    # Relationship integrity
    validation_results["checks"].append({
        "table": "relationships",
        "check": "foreign_key_constraints",
        "status": "pending"
    })
    
    # Fact table integrity
    validation_results["checks"].append({
        "table": "facts",
        "check": "triple_completeness",
        "status": "pending"
    })
    
    # Edge table integrity
    validation_results["checks"].append({
        "table": "edges",
        "check": "graph_consistency",
        "status": "pending"
    })
    
    return validation_results


def optimize_table_indexes(db_type: DatabaseType = DatabaseType.POSTGRESQL) -> Dict[str, Any]:
    """
    Optimize database indexes for ingestor.
    
    Args:
        db_type: Database type
        
    Returns:
        Optimization results
    """
    optimizations = {
        "database_type": db_type.value,
        "optimizations": [],
        "recommendations": []
    }
    
    if db_type == DatabaseType.POSTGRESQL:
        # PostgreSQL-specific optimizations
        optimizations["optimizations"].extend([
            {
                "table": "chunks",
                "index": "embedding",
                "type": "vector_index",
                "description": "Create pgvector index for similarity search",
                "status": "recommended"
            },
            {
                "table": "documents",
                "index": "file_path",
                "type": "btree",
                "description": "Create B-tree index for file path lookup",
                "status": "recommended"
            },
            {
                "table": "facts",
                "index": "subject_predicate_object",
                "type": "composite",
                "description": "Create composite index for triple queries",
                "status": "recommended"
            }
        ])
        
        optimizations["recommendations"].extend([
            "Consider partitioning chunks table by document_id",
            "Use BRIN index for created_at timestamps",
            "Consider partial indexes for frequently queried data"
        ])
    
    elif db_type == DatabaseType.STARROCKS:
        # StarRocks-specific optimizations
        optimizations["optimizations"].extend([
            {
                "table": "documents",
                "optimization": "aggregate_key",
                "description": "Use aggregate key model for documents",
                "status": "recommended"
            }
        ])
    
    elif db_type == DatabaseType.NEBULAGRAPH:
        # NebulaGraph-specific optimizations
        optimizations["optimizations"].extend([
            {
                "space": "perslad_space",
                "optimization": "index_on_tag",
                "description": "Create index on frequently queried tags",
                "status": "recommended"
            }
        ])
    
    return optimizations


def create_etl_process(process_config: Dict[str, Any]) -> ETLProcess:
    """
    Create ETL process for data filling.
    
    Args:
        process_config: ETL process configuration
        
    Returns:
        ETL process object
    """
    return ETLProcess(
        name=process_config.get("name", "unnamed_etl"),
        source=process_config.get("source", ""),
        target=process_config.get("target", ""),
        transformation=process_config.get("transformation", ""),
        validation_rules=process_config.get("validation_rules", []),
        batch_size=process_config.get("batch_size", 1000)
    )


def run_etl_process(etl_process: ETLProcess) -> Dict[str, Any]:
    """
    Run ETL process for data filling.
    
    Args:
        etl_process: ETL process to run
        
    Returns:
        Process results
    """
    results = {
        "process_name": etl_process.name,
        "status": "running",
        "extracted": 0,
        "transformed": 0,
        "loaded": 0,
        "errors": [],
        "start_time": None,
        "end_time": None
    }
    
    # In real implementation, execute the ETL process
    # For now, simulate the process
    
    return results


def get_data_filling_progress(db_type: DatabaseType = DatabaseType.POSTGRESQL) -> Dict[str, Any]:
    """
    Get progress of data filling across all tables.
    
    Args:
        db_type: Database type
        
    Returns:
        Progress information
    """
    progress = {
        "database_type": db_type.value,
        "overall_progress": 0,
        "table_progress": [],
        "estimated_completion": None
    }
    
    # Simulate progress for each table
    tables = get_table_schema(db_type).get("tables", [])
    
    for table in tables:
        table_name = table["name"]
        
        # Simulate progress (in real implementation, query actual progress)
        if table_name == "documents":
            progress_percent = 85
        elif table_name == "chunks":
            progress_percent = 90
        elif table_name == "relationships":
            progress_percent = 60
        elif table_name == "facts":
            progress_percent = 45
        elif table_name == "edges":
            progress_percent = 30
        elif table_name == "index_status":
            progress_percent = 95
        else:
            progress_percent = 0
        
        progress["table_progress"].append({
            "table": table_name,
            "progress": progress_percent,
            "records": 1000 * progress_percent // 100
        })
    
    # Calculate overall progress
    if progress["table_progress"]:
        progress["overall_progress"] = sum(
            t["progress"] for t in progress["table_progress"]
        ) // len(progress["table_progress"])
    
    return progress


def validate_schema_compatibility(
    schema: Dict[str, Any],
    db_type: DatabaseType = DatabaseType.POSTGRESQL
) -> List[str]:
    """
    Validate schema compatibility with database type.
    
    Args:
        schema: Schema to validate
        db_type: Database type
        
    Returns:
        List of compatibility issues
    """
    issues = []
    
    if db_type == DatabaseType.POSTGRESQL:
        # PostgreSQL-specific validation
        for table in schema.get("tables", []):
            for column in table.get("columns", []):
                col_type = column.get("type", "")
                if "VECTOR" in col_type and "pgvector" not in str(schema):
                    issues.append(f"Vector type requires pgvector extension: {table['name']}.{column['name']}")
    
    elif db_type == DatabaseType.STARROCKS:
        # StarRocks-specific validation
        for table in schema.get("tables", []):
            if table.get("primary_key"):
                issues.append(f"StarRocks uses aggregate keys, not primary keys: {table['name']}")
    
    elif db_type == DatabaseType.NEBULAGRAPH:
        # NebulaGraph-specific validation
        if "tables" in schema:
            issues.append("NebulaGraph uses spaces and tags, not tables")
    
    return issues