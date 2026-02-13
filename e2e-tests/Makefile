# Makefile for E2E Tests
# This Makefile provides convenient commands for running E2E tests

.PHONY: help setup start stop restart test test-component test-e2e test-integration test-fast test-slow test-smoke test-coverage clean reports logs

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target
help:
	@echo -e "${BLUE}E2E Test Suite - Available Commands${NC}"
	@echo ""
	@echo -e "${YELLOW}Setup & Environment${NC}"
	@echo "  make setup       - Setup test environment"
	@echo "  make start       - Start test services"
	@echo "  make stop        - Stop test services"
	@echo "  make restart     - Restart test services"
	@echo ""
	@echo -e "${YELLOW}Testing${NC}"
	@echo "  make test        - Run all tests"
	@echo "  make test-component - Run component tests"
	@echo "  make test-e2e    - Run end-to-end tests"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-fast   - Run fast tests only"
	@echo "  make test-slow   - Run slow tests only"
	@echo "  make test-smoke  - Run smoke tests"
	@echo "  make test-coverage - Run with coverage"
	@echo "  make test-parallel - Run in parallel (4 workers)"
	@echo ""
	@echo -e "${YELLOW}Maintenance${NC}"
	@echo "  make clean       - Clean up test environment"
	@echo "  make reports     - Generate test reports"
	@echo "  make logs        - Show service logs"
	@echo "  make health      - Check service health"
	@echo ""
	@echo -e "${YELLOW}Examples${NC}"
	@echo "  make test-e2e    # Run e2e tests"
	@echo "  make test-coverage # Run with coverage"
	@echo "  make clean start test # Clean, start, test"

# Setup
setup:
	@echo -e "${YELLOW}Setting up test environment...${NC}"
	@./scripts/setup_test_environment.sh

# Start services
start:
	@echo -e "${YELLOW}Starting test services...${NC}"
	@docker-compose -f docker-compose.yml up -d
	@echo -e "${YELLOW}Waiting for services to be ready...${NC}"
	@sleep 10
	@$(MAKE) health

# Stop services
stop:
	@echo -e "${YELLOW}Stopping test services...${NC}"
	@docker-compose -f docker-compose.yml down

# Restart services
restart: stop start

# Run all tests
test:
	@echo -e "${YELLOW}Running all tests...${NC}"
	@./scripts/run_e2e_tests.sh all

# Component tests
test-component:
	@echo -e "${YELLOW}Running component tests...${NC}"
	@./scripts/run_e2e_tests.sh component

# E2E tests
test-e2e:
	@echo -e "${YELLOW}Running E2E tests...${NC}"
	@./scripts/run_e2e_tests.sh e2e

# Integration tests
test-integration:
	@echo -e "${YELLOW}Running integration tests...${NC}"
	@./scripts/run_e2e_tests.sh integration

# Fast tests
test-fast:
	@echo -e "${YELLOW}Running fast tests...${NC}"
	@./scripts/run_e2e_tests.sh all --parallel=4
	@echo -e "${YELLOW}Note: Fast tests are filtered by marker${NC}"

# Slow tests
test-slow:
	@echo -e "${YELLOW}Running slow tests...${NC}"
	@./scripts/run_e2e_tests.sh slow

# Smoke tests
test-smoke:
	@echo -e "${YELLOW}Running smoke tests...${NC}"
	@./scripts/run_e2e_tests.sh smoke

# Test with coverage
test-coverage:
	@echo -e "${YELLOW}Running tests with coverage...${NC}"
	@./scripts/run_e2e_tests.sh all --coverage

# Parallel test execution
test-parallel:
	@echo -e "${YELLOW}Running tests in parallel (4 workers)...${NC}"
	@./scripts/run_e2e_tests.sh all --parallel=4

# Clean up
clean:
	@echo -e "${YELLOW}Cleaning up test environment...${NC}"
	@docker-compose -f docker-compose.yml down --volumes
	@rm -rf reports/*
	@rm -rf data/*
	@rm -rf model_cache/*
	@echo -e "${GREEN}Cleanup complete${NC}"

# Generate reports
reports:
	@echo -e "${YELLOW}Generating test reports...${NC}"
	@mkdir -p reports
	@echo "HTML Coverage Report: reports/coverage/index.html"
	@echo "JUnit XML Report: reports/junit.xml"
	@echo "Coverage XML: reports/coverage.xml"

# Show logs
logs:
	@echo -e "${YELLOW}Showing service logs (Ctrl+C to exit)...${NC}"
	@docker-compose -f docker-compose.yml logs -f

# Health check
health:
	@echo -e "${YELLOW}Checking service health...${NC}"
	@echo "LLM Service:"
	@curl -s http://localhost:8002/v1/models | python3 -m json.tool 2>/dev/null || echo "  ❌ Not available"
	@echo ""
	@echo "Embedding Service:"
	@curl -s http://localhost:8003/v1/models | python3 -m json.tool 2>/dev/null || echo "  ❌ Not available"
	@echo ""
	@echo "Ingestor Service:"
	@curl -s http://localhost:8125/ 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Not available"
	@echo ""
	@echo "LangGraph Agent:"
	@curl -s http://localhost:8126/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Not available"
	@echo ""
	@echo "MCP Bash Server:"
	@curl -s http://localhost:8082/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Not available"
	@echo ""
	@echo "MCP Project Server:"
	@curl -s http://localhost:8084/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Not available"

# Test specific component
test-%:
	@echo -e "${YELLOW}Testing component: $*${NC}"
	@./scripts/run_e2e_tests.sh component
	@echo -e "${YELLOW}Note: Component name is passed to pytest as marker${NC}"

# View test results
results:
	@if [ -f reports/junit.xml ]; then \
		echo -e "${YELLOW}Test Results Summary${NC}"; \
		python3 << EOF \
		import xml.etree.ElementTree as ET; \
		import sys; \
		tree = ET.parse('reports/junit.xml'); \
		root = tree.getroot(); \
		tests = int(root.get('tests', 0)); \
		failures = int(root.get('failures', 0)); \
		errors = int(root.get('errors', 0)); \
		skipped = int(root.get('skipped', 0)); \
		print(f"Total: {tests}"); \
		print(f"Passed: {tests - failures - errors - skipped}"); \
		print(f"Failed: {failures}"); \
		print(f"Errors: {errors}"); \
		print(f"Skipped: {skipped}"); \
		if failures + errors > 0: \
			sys.exit(1); \
		EOF \
	else \
		echo -e "${RED}No test results found. Run tests first.${NC}"; \
	fi

# Run a specific test file
test-file-%:
	@echo -e "${YELLOW}Running test file: $*${NC}"
	@python3 -m pytest tests/$*.py -v --tb=short

# Interactive shell with test environment
shell:
	@echo -e "${YELLOW}Starting test runner container...${NC}"
	@docker-compose -f docker-compose.yml run --rm test-runner bash

# Update test dependencies
update-deps:
	@echo -e "${YELLOW}Updating test dependencies...${NC}"
	@pip install --upgrade -r requirements-test.txt

# Run smoke tests with health check
smoke-with-check:
	@echo -e "${YELLOW}Running smoke tests with health check...${NC}"
	@$(MAKE) health
	@sleep 5
	@./scripts/run_e2e_tests.sh smoke

# CI/CD mode (no interactive)
ci:
	@echo -e "${YELLOW}Running in CI mode...${NC}"
	@./scripts/run_e2e_tests.sh all --parallel=2
	@$(MAKE) results

# Benchmark mode
benchmark:
	@echo -e "${YELLOW}Running performance benchmarks...${NC}"
	@python3 -m pytest tests/ -m performance -v --tb=short --benchmark-only

# Quick validation
quick:
	@echo -e "${YELLOW}Quick validation (fast tests only)...${NC}"
	@./scripts/run_e2e_tests.sh all --parallel=4
	@$(MAKE) results

# Help for specific target
%-help:
	@echo -e "${BLUE}Help for target: $*${NC}"
	@echo ""
	@if [ "$*" = "setup" ]; then \
		echo "Sets up the test environment by creating directories and configuration files."; \
	elif [ "$*" = "start" ]; then \
		echo "Starts all test services using docker-compose."; \
	elif [ "$*" = "test" ]; then \
		echo "Runs all tests (component, integration, and e2e)."; \
	elif [ "$*" = "clean" ]; then \
		echo "Stops all services and cleans up all test data."; \
	else \
		echo "Run 'make help' for available commands."; \
	fi