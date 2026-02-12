"""Tests for Integration testing skill."""

import pytest
from skills.testing.integration import (
    create_test_suite,
    run_unit_tests,
    run_integration_tests,
    run_performance_tests,
    run_security_tests,
    run_e2e_tests,
    generate_coverage_report,
    compare_test_results,
    validate_test_coverage,
    setup_mock_llm_responses,
    create_test_data,
    TestCase,
    TestType
)


def test_create_test_suite():
    """Test creating test suite for component."""
    suite = create_test_suite("test_component", [TestType.UNIT, TestType.INTEGRATION])
    
    assert suite["component"] == "test_component"
    assert "test_types" in suite
    assert "test_cases" in suite
    assert suite["total"] > 0


def test_run_unit_tests():
    """Test running unit tests."""
    results = run_unit_tests("test_component")
    
    assert results["component"] == "test_component"
    assert results["test_type"] == "unit"
    assert "results" in results
    assert "summary" in results
    assert results["summary"]["total"] >= 0


def test_run_integration_tests():
    """Test running integration tests."""
    results = run_integration_tests("test_component", ["dep1", "dep2"])
    
    assert results["component"] == "test_component"
    assert results["test_type"] == "integration"
    assert "dependencies" in results
    assert len(results["dependencies"]) == 2


def test_run_performance_tests():
    """Test running performance tests."""
    results = run_performance_tests("test_component")
    
    assert results["component"] == "test_component"
    assert results["test_type"] == "performance"
    assert "metrics" in results
    assert "results" in results
    assert "thresholds" in results


def test_run_security_tests():
    """Test running security tests."""
    results = run_security_tests("test_component")
    
    assert results["component"] == "test_component"
    assert results["test_type"] == "security"
    assert "checks" in results
    assert "results" in results
    assert "vulnerabilities" in results


def test_run_e2e_tests():
    """Test running end-to-end tests."""
    results = run_e2e_tests("test_workflow")
    
    assert results["workflow"] == "test_workflow"
    assert results["test_type"] == "e2e"
    assert "steps" in results
    assert "results" in results
    assert "summary" in results
    assert results["summary"]["total"] > 0


def test_generate_coverage_report():
    """Test generating coverage report."""
    test_results = {
        "summary": {
            "total": 10,
            "passed": 8,
            "failed": 2,
            "skipped": 0
        }
    }
    
    coverage = generate_coverage_report("test_component", test_results)
    
    assert coverage["component"] == "test_component"
    assert "lines_covered" in coverage
    assert "lines_total" in coverage
    assert "percentage" in coverage
    assert coverage["percentage"] >= 0


def test_compare_test_results():
    """Test comparing test results with baseline."""
    baseline = {
        "summary": {
            "total": 10,
            "passed": 9,
            "failed": 1,
            "skipped": 0
        }
    }
    
    current = {
        "summary": {
            "total": 12,
            "passed": 10,
            "failed": 2,
            "skipped": 0
        }
    }
    
    comparison = compare_test_results(baseline, current)
    
    assert "baseline" in comparison
    assert "current" in comparison
    assert "differences" in comparison
    assert "trends" in comparison


def test_validate_test_coverage():
    """Test test coverage validation."""
    coverage = {
        "percentage": 75,
        "threshold": 80,
        "files": [
            {"file": "main.py", "coverage": 70}
        ]
    }
    
    issues = validate_test_coverage("test_component", coverage)
    
    # Should have issues because coverage is below threshold
    assert len(issues) > 0


def test_setup_mock_llm_responses():
    """Test setting up mock LLM responses."""
    mock_config = setup_mock_llm_responses()
    
    assert mock_config["provider"] == "mock"
    assert "responses" in mock_config
    assert "latency_ms" in mock_config
    assert "random_failure_rate" in mock_config


def test_create_test_data():
    """Test creating test data."""
    test_data = create_test_data("inotify")
    
    assert test_data["component"] == "inotify"
    assert "fixtures" in test_data
    assert "mock_data" in test_data
    assert "test_cases" in test_data
    
    # Check that fixtures were created for inotify
    if test_data["fixtures"]:
        assert "file_events" in test_data["fixtures"][0]


def test_test_case_creation():
    """Test creating test cases."""
    test_case = TestCase(
        name="test_case_1",
        test_type=TestType.UNIT,
        component="test_component",
        description="Test description",
        assertions=["assert True"]
    )
    
    assert test_case.name == "test_case_1"
    assert test_case.test_type == TestType.UNIT
    assert test_case.component == "test_component"
    assert test_case.assertions is not None
    assert len(test_case.assertions) == 1