"""Tests for Multi-database storage adaptation skill."""

import pytest
from skills.database.multi_storage import (
    setup_postgres_adapter,
    setup_starrocks_adapter,
    setup_nebulagraph_adapter,
    migrate_schema_between_dbs,
    sync_data_across_dbs,
    DatabaseConfig,
    DatabaseType,
    validate_adapter_config
)


def test_setup_postgres_adapter():
    """Test setting up PostgreSQL adapter."""
    config = DatabaseConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user"
    )
    
    result = setup_postgres_adapter(config)
    
    assert result["type"] == "postgresql"
    assert "connection" in result
    assert "vector_support" in result
    assert result["vector_support"]["enabled"] is True


def test_setup_starrocks_adapter():
    """Test setting up StarRocks adapter."""
    config = DatabaseConfig(
        database_type=DatabaseType.STARROCKS,
        host="localhost",
        port=9030,
        database="test_db",
        username="test_user"
    )
    
    result = setup_starrocks_adapter(config)
    
    assert result["type"] == "starrocks"
    assert "connection" in result
    assert "model_type" in result
    assert result["model_type"] == "aggregate"


def test_setup_nebulagraph_adapter():
    """Test setting up NebulaGraph adapter."""
    config = DatabaseConfig(
        database_type=DatabaseType.NEBULAGRAPH,
        host="localhost",
        port=9669,
        database="test_db",
        username="test_user"
    )
    
    result = setup_nebulagraph_adapter(config)
    
    assert result["type"] == "nebulagraph"
    assert "connection" in result
    assert "space" in result
    assert result["space"] == "perslad_space"


def test_migrate_schema_between_dbs():
    """Test schema migration between databases."""
    source_config = DatabaseConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="source_db",
        username="test_user"
    )
    
    target_config = DatabaseConfig(
        database_type=DatabaseType.STARROCKS,
        host="localhost",
        port=9030,
        database="target_db",
        username="test_user"
    )
    
    plan = migrate_schema_between_dbs(source_config, target_config)
    
    assert plan.source_type == DatabaseType.POSTGRESQL
    assert plan.target_type == DatabaseType.STARROCKS
    assert len(plan.steps) > 0
    assert len(plan.validation_checks) > 0


def test_sync_data_across_dbs():
    """Test data synchronization across multiple databases."""
    source_config = DatabaseConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="source_db",
        username="test_user"
    )
    
    target_configs = [
        DatabaseConfig(
            database_type=DatabaseType.STARROCKS,
            host="localhost",
            port=9030,
            database="target1",
            username="test_user"
        ),
        DatabaseConfig(
            database_type=DatabaseType.NEBULAGRAPH,
            host="localhost",
            port=9669,
            database="target2",
            username="test_user"
        )
    ]
    
    results = sync_data_across_dbs(source_config, target_configs, "incremental")
    
    assert results["source"] == "postgresql"
    assert len(results["targets"]) == 2
    assert results["strategy"] == "incremental"
    assert "operations" in results


def test_validate_adapter_config():
    """Test adapter configuration validation."""
    # Valid config
    config = DatabaseConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user"
    )
    
    errors = validate_adapter_config(config)
    assert len(errors) == 0
    
    # Invalid config (missing host)
    config = DatabaseConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="",
        port=5432,
        database="test_db",
        username="test_user"
    )
    
    errors = validate_adapter_config(config)
    assert len(errors) > 0


def test_get_adapter_capabilities():
    """Test getting adapter capabilities."""
    from skills.database.multi_storage import get_adapter_capabilities
    
    pg_caps = get_adapter_capabilities(DatabaseType.POSTGRESQL)
    assert pg_caps["vector_search"] is True
    assert pg_caps["json_support"] is True
    
    starrocks_caps = get_adapter_capabilities(DatabaseType.STARROCKS)
    assert starrocks_caps["vector_search"] is False
    assert starrocks_caps["scalability"] == "horizontal"
    
    nebulagraph_caps = get_adapter_capabilities(DatabaseType.NEBULAGRAPH)
    assert nebulagraph_caps["scalability"] == "distributed"
    assert nebulagraph_caps["use_cases"] == ["graph_queries", "relationship_analysis"]


def test_unified_query_layer():
    """Test unified query layer creation."""
    from skills.database.multi_storage import create_unified_query_layer
    
    adapters = {
        DatabaseType.POSTGRESQL: {"type": "postgresql"},
        DatabaseType.STARROCKS: {"type": "starrocks"}
    }
    
    result = create_unified_query_layer(adapters)
    
    assert "query_router" in result
    assert "data_federation" in result
    assert result["query_router"]["enabled"] is True


def test_performance_optimization():
    """Test performance optimization for multi-database setup."""
    from skills.database.multi_storage import optimize_multi_db_performance
    
    configs = [
        DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="test_db",
            username="test_user"
        )
    ]
    
    result = optimize_multi_db_performance(configs)
    
    assert "caching" in result
    assert "connection_management" in result
    assert "query_optimization" in result
    assert result["caching"]["enabled"] is True