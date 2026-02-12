"""
Multi-database storage adaptation skill.
Support for PostgreSQL, StarRocks, NebulaGraph adapters.

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
    """Supported database types."""
    POSTGRESQL = "postgresql"
    STARROCKS = "starrocks"
    NEBULAGRAPH = "nebulagraph"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    database_type: DatabaseType
    host: str
    port: int
    database: str
    username: str
    password: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


@dataclass
class MigrationPlan:
    """Schema migration plan between databases."""
    source_type: DatabaseType
    target_type: DatabaseType
    steps: List[str]
    validation_checks: List[str]
    rollback_steps: List[str]


def setup_postgres_adapter(config: DatabaseConfig) -> Dict[str, Any]:
    """
    Configure PostgreSQL adapter with pgvector.
    
    Args:
        config: Database configuration
        
    Returns:
        Adapter setup result
    """
    if config.database_type != DatabaseType.POSTGRESQL:
        return {"error": f"Invalid database type: {config.database_type}"}
    
    adapter_config = {
        "type": "postgresql",
        "connection": {
            "host": config.host,
            "port": config.port,
            "database": config.database,
            "username": config.username
        },
        "extensions": ["pgvector"],
        "connection_pool": {
            "min_size": 2,
            "max_size": 10,
            "max_queries": 10000,
            "max_inactive_connection_lifetime": 300
        },
        "vector_support": {
            "enabled": True,
            "dimensions": 1536,
            "index_type": "ivfflat",
            "metric": "cosine"
        },
        "schema_management": {
            "auto_migrate": True,
            "create_extensions": True,
            "validate_schema": True
        }
    }
    
    return adapter_config


def setup_starrocks_adapter(config: DatabaseConfig) -> Dict[str, Any]:
    """
    Configure StarRocks adapter.
    
    Args:
        config: Database configuration
        
    Returns:
        Adapter setup result
    """
    if config.database_type != DatabaseType.STARROCKS:
        return {"error": f"Invalid database type: {config.database_type}"}
    
    adapter_config = {
        "type": "starrocks",
        "connection": {
            "host": config.host,
            "port": config.port,
            "database": config.database,
            "username": config.username
        },
        "model_type": "aggregate",
        "partitioning": {
            "enabled": True,
            "strategy": "date",
            "column": "created_at"
        },
        "indexing": {
            "aggregate_keys": ["id"],
            "duplicate_keys": ["file_path"],
            "unique_keys": []
        },
        "optimization": {
            "bitmap_index": True,
            "zone_map": True,
            "bloom_filter": True
        }
    }
    
    return adapter_config


def setup_nebulagraph_adapter(config: DatabaseConfig) -> Dict[str, Any]:
    """
    Configure NebulaGraph adapter.
    
    Args:
        config: Database configuration
        
    Returns:
        Adapter setup result
    """
    if config.database_type != DatabaseType.NEBULAGRAPH:
        return {"error": f"Invalid database type: {config.database_type}"}
    
    adapter_config = {
        "type": "nebulagraph",
        "connection": {
            "host": config.host,
            "port": config.port
        },
        "space": "perslad_space",
        "schema": {
            "tags": ["Document", "Chunk", "Fact", "Entity"],
            "edge_types": ["CONTAINS", "RELATES_TO", "EXTRACTED_FROM"],
            "indexes": {
                "Document": ["file_path"],
                "Fact": ["subject", "predicate", "object"],
                "Entity": ["name", "type"]
            }
        },
        "query_optimization": {
            "enable_storage": True,
            "enable_audit": True,
            "enable_memory_tracker": True
        }
    }
    
    return adapter_config


def migrate_schema_between_dbs(
    source_config: DatabaseConfig,
    target_config: DatabaseConfig
) -> MigrationPlan:
    """
    Migrate schema between different databases.
    
    Args:
        source_config: Source database configuration
        target_config: Target database configuration
        
    Returns:
        Migration plan
    """
    migration_steps = []
    validation_checks = []
    rollback_steps = []
    
    # Migration steps based on source and target types
    if source_config.database_type == DatabaseType.POSTGRESQL:
        if target_config.database_type == DatabaseType.STARROCKS:
            migration_steps.extend([
                "Export data from PostgreSQL as CSV",
                "Transform schema to StarRocks aggregate model",
                "Load data into StarRocks using Stream Load",
                "Validate data integrity"
            ])
            validation_checks.extend([
                "Check row counts match",
                "Verify data types",
                "Test query performance"
            ])
            rollback_steps.extend([
                "Restore from backup",
                "Drop StarRocks tables",
                "Revert to PostgreSQL"
            ])
        
        elif target_config.database_type == DatabaseType.NEBULAGRAPH:
            migration_steps.extend([
                "Extract triples from PostgreSQL facts table",
                "Create NebulaGraph space and schema",
                "Import data using nGQL",
                "Validate graph relationships"
            ])
            validation_checks.extend([
                "Check node counts",
                "Verify edge relationships",
                "Test graph traversal queries"
            ])
            rollback_steps.extend([
                "Drop NebulaGraph space",
                "Restore PostgreSQL backup"
            ])
    
    plan = MigrationPlan(
        source_type=source_config.database_type,
        target_type=target_config.database_type,
        steps=migration_steps,
        validation_checks=validation_checks,
        rollback_steps=rollback_steps
    )
    
    return plan


def sync_data_across_dbs(
    source_config: DatabaseConfig,
    target_configs: List[DatabaseConfig],
    sync_strategy: str = "incremental"
) -> Dict[str, Any]:
    """
    Synchronize data across multiple databases.
    
    Args:
        source_config: Source database configuration
        target_configs: List of target database configurations
        sync_strategy: Synchronization strategy
        
    Returns:
        Synchronization results
    """
    results = {
        "source": source_config.database_type.value,
        "targets": [t.database_type.value for t in target_configs],
        "strategy": sync_strategy,
        "status": "pending",
        "operations": []
    }
    
    for target_config in target_configs:
        operation = {
            "target": target_config.database_type.value,
            "sync_type": sync_strategy,
            "status": "pending"
        }
        
        if sync_strategy == "incremental":
            operation["method"] = "change_data_capture"
            operation["frequency"] = "real_time"
        
        elif sync_strategy == "batch":
            operation["method"] = "scheduled_replication"
            operation["frequency"] = "daily"
        
        elif sync_strategy == "full":
            operation["method"] = "full_refresh"
            operation["frequency"] = "weekly"
        
        results["operations"].append(operation)
    
    return results


def get_adapter_capabilities(db_type: DatabaseType) -> Dict[str, Any]:
    """
    Get capabilities for specific database adapter.
    
    Args:
        db_type: Database type
        
    Returns:
        Capabilities
    """
    capabilities_map = {
        DatabaseType.POSTGRESQL: {
            "vector_search": True,
            "full_text_search": True,
            "json_support": True,
            "transaction_support": True,
            "scalability": "vertical",
            "use_cases": ["primary_rag_storage", "complex_queries"]
        },
        DatabaseType.STARROCKS: {
            "vector_search": False,
            "full_text_search": False,
            "json_support": True,
            "transaction_support": "limited",
            "scalability": "horizontal",
            "use_cases": ["analytics", "real_time_queries"]
        },
        DatabaseType.NEBULAGRAPH: {
            "vector_search": False,
            "full_text_search": False,
            "json_support": True,
            "transaction_support": False,
            "scalability": "distributed",
            "use_cases": ["graph_queries", "relationship_analysis"]
        }
    }
    
    return capabilities_map.get(db_type, {})


def validate_adapter_config(config: DatabaseConfig) -> List[str]:
    """
    Validate database adapter configuration.
    
    Args:
        config: Database configuration
        
    Returns:
        List of validation errors
    """
    errors = []
    
    if not config.host:
        errors.append("Host is required")
    
    if config.port <= 0:
        errors.append("Port must be positive")
    
    if not config.database:
        errors.append("Database name is required")
    
    if not config.username:
        errors.append("Username is required")
    
    # Check adapter-specific requirements
    if config.database_type == DatabaseType.NEBULAGRAPH:
        if config.port not in [9669, 19669]:
            errors.append("NebulaGraph typically uses port 9669 or 19669")
    
    return errors


def create_unified_query_layer(
    adapters: Dict[DatabaseType, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create unified query layer for multi-database setup.
    
    Args:
        adapters: Dictionary of database adapters
        
    Returns:
        Unified query layer configuration
    """
    unified_config = {
        "query_router": {
            "enabled": True,
            "rules": [
                {
                    "query_type": "vector_similarity",
                    "target": "postgresql"
                },
                {
                    "query_type": "analytics",
                    "target": "starrocks"
                },
                {
                    "query_type": "graph_traversal",
                    "target": "nebulagraph"
                }
            ]
        },
        "data_federation": {
            "enabled": True,
            "virtual_tables": ["unified_documents", "unified_facts"],
            "join_rules": {
                "cross_database_joins": False,
                "cache_layer": "redis"
            }
        },
        "consistency_model": "eventual",
        "fallback_strategy": "degrade_gracefully"
    }
    
    return unified_config


def optimize_multi_db_performance(
    db_configs: List[DatabaseConfig]
) -> Dict[str, Any]:
    """
    Optimize performance for multi-database setup.
    
    Args:
        db_configs: List of database configurations
        
    Returns:
        Performance optimization recommendations
    """
    optimizations = {
        "caching": {
            "enabled": True,
            "type": "redis",
            "ttl": 300,
            "cache_queries": ["frequent", "expensive"]
        },
        "connection_management": {
            "pooling": True,
            "persistent_connections": True,
            "health_checks": True
        },
        "query_optimization": {
            "explain_plans": True,
            "index_analysis": True,
            "slow_query_log": True
        },
        "monitoring": {
            "metrics": ["query_latency", "throughput", "error_rates"],
            "alerts": ["high_latency", "connection_pool_exhaustion"]
        }
    }
    
    return optimizations