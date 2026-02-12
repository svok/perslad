"""Tests for Docker Compose management skill."""

import pytest
from skills.devops.docker import (
    check_docker_status,
    rebuild_service,
    view_logs,
    setup_dev_environment,
    get_service_health,
    check_docker_prerequisites
)


def test_check_docker_status():
    """Test checking Docker Compose status."""
    status = check_docker_status()
    
    assert "services" in status
    assert "total" in status
    assert "running" in status
    assert "stopped" in status
    
    # Check that all services are present
    service_names = [s["name"] for s in status["services"]]
    expected_services = ["llm-engine", "langgraph-agent", "ingestor", "postgres"]
    
    for expected in expected_services:
        assert expected in service_names


def test_rebuild_service():
    """Test rebuilding a service."""
    result = rebuild_service("test-service")
    
    assert result["service"] == "test-service"
    assert result["action"] == "rebuild"
    assert result["status"] == "success"


def test_view_logs():
    """Test viewing service logs."""
    logs = view_logs("test-service", lines=10)
    
    assert logs["service"] == "test-service"
    assert "lines" in logs
    assert "total_lines" in logs
    assert "showing" in logs
    
    # Check log content
    if logs["lines"]:
        assert "Starting" in logs["lines"][0]


def test_setup_dev_environment():
    """Test setting up development environment."""
    setup = setup_dev_environment()
    
    assert setup["status"] == "setup_complete"
    assert "steps" in setup
    assert "verification" in setup
    
    # Check for critical steps
    steps = setup["steps"]
    assert any("docker-compose" in step.lower() for step in steps)
    assert any("env" in step.lower() for step in steps)


def test_get_service_health():
    """Test getting service health."""
    health = get_service_health("llm-engine")
    
    assert "endpoint" in health
    assert "status" in health
    assert "response_time" in health
    
    # Check health status
    assert health["status"] == "healthy"


def test_check_docker_prerequisites():
    """Test checking Docker prerequisites."""
    checks = check_docker_prerequisites()
    
    assert "checks" in checks
    assert "total" in checks
    assert "critical" in checks
    assert "recommended" in checks
    
    # Check that Docker is listed as critical
    docker_check = next(
        (c for c in checks["checks"] if "Docker" in c["name"]),
        None
    )
    assert docker_check is not None
    assert docker_check["status"] == "required"