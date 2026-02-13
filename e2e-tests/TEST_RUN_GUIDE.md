# Test Run Guide

## Quick Start

### Prerequisites
1. Ensure test environment is running:
   ```bash
   cd /sda/sokatov/own/perslad-1/e2e-tests
   docker-compose -f docker-compose.yml up -d
   ```

2. Verify services are healthy:
   ```bash
   make health
   ```

## Running Tests

### 1. Run Indexation Workflows Tests
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/test_indexation_workflows.py -v
```

**What it tests:**
- File ingestion (text, code, markdown, JSON, YAML)
- Batch file ingestion
- Metadata extraction
- Error handling
- Large file handling
- Concurrent operations
- Special characters
- File encoding

### 2. Run Database Operations Tests
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/test_db_operations.py -v
```

**What it tests:**
- Database connection
- Schema validation
- Chunk storage/retrieval
- File/module summary storage
- Query execution
- Transaction handling
- Concurrent operations
- Performance queries

### 3. Run User API Tests
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/test_user_requests_responses.py -v
```

**What it tests:**
- API health endpoints
- Ingestor endpoints (ingest, search)
- LangGraph chat completion
- Streaming responses
- Error handling
- Request/response validation
- Rate limiting
- MCP tools

### 4. Run Agent-Ingestor Integration Tests
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/test_agents_ingestor_integration.py -v
```

**What it tests:**
- Agent context retrieval from Ingestor
- Agent decision making with context
- Tool calling with context
- Multi-turn conversations
- Performance and error handling
- Semantic search
- Metadata filtering

## Run All Tests

### Run All New Tests
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/test_indexation_workflows.py tests/test_db_operations.py tests/test_user_requests_responses.py tests/test_agents_ingestor_integration.py -v
```

### Run All Integration Tests
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest -m integration -v
```

### Run All Tests in e2e-tests
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/ -v
```

## Test Options

### Run with Coverage
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/ --cov --cov-report=html -v
```

### Run in Parallel (Faster)
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/ --parallel=4 -v
```

### Run Only Fast Tests
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest -m fast -v
```

### Run Specific Test
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
python3 -m pytest tests/test_indexation_workflows.py::TestIndexationWorkflows::test_single_file_ingestion_text -v
```

### Run with Markers
```bash
# Run indexation tests only
python3 -m pytest -m indexation -v

# Run database tests only
python3 -m pytest -m database -v

# Run API tests only
python3 -m pytest -m api -v

# Run agent-ingestor tests only
python3 -m pytest -m agent_ingestor -v
```

## Using Makefile (Alternative)

```bash
cd /sda/sokatov/own/perslad-1/e2e-tests

# Run all tests
make test

# Run component tests only
make test-component

# Run E2E tests only
make test-e2e

# Run with coverage
make test-coverage

# Run in parallel
make test-parallel

# Run specific test
make test-quick test_indexation_workflows
```

## Using Wrapper Script

```bash
cd /sda/sokatov/own/perslad-1

# Run all tests
./run_e2e_tests.sh all --parallel=4

# Run only new integration tests
./run_e2e_tests.sh integration --parallel=2

# Run with coverage
./run_e2e_tests.sh all --coverage --parallel=4

# Debug mode
./run_e2e_tests.sh all --debug
```

## Test Results

### View Test Output
- Console output shows real-time test progress
- Failed tests show detailed error messages
- Use `-v` for verbose output
- Use `--tb=short` for shorter tracebacks

### Test Reports Location
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests/reports/
```

**Files:**
- `junit.xml` - JUnit XML format (CI/CD compatible)
- `coverage/` - HTML coverage reports
- `allure-results/` - Rich test reports (if using Allure)

### View Coverage Report
```bash
# After running with --cov
cd /sda/sokatov/own/perslad-1/e2e-tests/reports/coverage/
# Open index.html in browser
```

## Troubleshooting

### Tests Fail Due to Service Not Running
```bash
# Check service status
make health

# Start services
docker-compose -f docker-compose.yml up -d

# View logs
make logs

# Restart services
docker-compose -f docker-compose.yml down
docker-compose -f docker-compose.yml up -d
```

### Database Connection Issues
```bash
# Test database connection
psql -h localhost -U rag_test -d rag_test -p 5433

# Check PostgreSQL status
docker-compose -f docker-compose.yml ps postgres-test
```

### GPU Memory Issues
```bash
# Reduce parallel execution
python3 -m pytest tests/ --parallel=2 -v

# Run only non-GPU tests
python3 -m pytest -m "not requires_gpu" -v

# Check GPU memory
nvidia-smi
```

### Import Errors
```bash
# Ensure Python path is set
export PYTHONPATH=/workspace

# Check Python version
python3 --version

# Install test dependencies
pip install -r requirements-test.txt
```

## Test Data Management

### Test Workspace Location
```bash
/workspace-test  # Inside containers
/sda/sokatov/own/perslad-1/e2e-tests/data/  # On host (if mapped)
```

### Clean Test Data
```bash
# Clean workspace
rm -rf /workspace-test/*

# Clean database
# Tests automatically clean database between tests
```

### Test File Generation
The tests automatically create:
- Text files with various content
- Code files (Python)
- Markdown documentation
- JSON configuration files
- Large files for performance testing
- Files with special characters
- Empty files
- Binary files (for rejection testing)

## Performance Tips

### Speed Up Test Execution
1. Use parallel execution (`--parallel=4`)
2. Run only fast tests (`-m fast`)
3. Run specific test files instead of all tests
4. Use `--cov` only when needed (slows down execution)

### Memory Management
1. Run tests in batches if memory is limited
2. Use `--parallel=2` on systems with < 8GB RAM
3. Close browser tabs and other applications

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Setup Docker
        run: sudo systemctl start docker
      - name: Run Tests
        run: |
          cd e2e-tests
          docker-compose -f docker-compose.yml up -d
          python3 -m pytest tests/ --parallel=2 --cov --junitxml=reports/junit.xml
          docker-compose -f docker-compose.yml down
      - name: Upload Test Results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: e2e-tests/reports/
```

## Test Output Examples

### Successful Test Run
```
============================= test session starts ==============================
platform linux -- Python 3.13.0, pytest-8.0.0, pytest-asyncio-0.21.0, pluggy-1.0.0
rootdir: /sda/sokatov/own/perslad-1/e2e-tests
collected 20 items

tests/test_indexation_workflows.py::TestIndexationWorkflows::test_single_file_ingestion_text PASSED [  5%]
tests/test_indexation_workflows.py::TestIndexationWorkflows::test_batch_file_ingestion PASSED [ 10%]
...
======================== 20 passed in 12.34s ========================
```

### Failed Test Run
```
============================= test session starts ==============================
platform linux -- Python 3.13.0, pytest-8.0.0, pytest-asyncio-0.21.0, pluggy-1.0.0
rootdir: /sda/sokatov/own/perslad-1/e2e-tests
collected 20 items

tests/test_indexation_workflows.py::TestIndexationWorkflows::test_single_file_ingestion_text FAILED [  5%]

=================================== FAILURES ===================================
____________ TestIndexationWorkflows.test_single_file_ingestion_text ____________

    @pytest.mark.asyncio
    async def test_single_file_ingestion_text(self, ingestor_client, test_workspace):
>       response = await ingestor_client.post("/ingest", json=payload)
E       assert 500 == 200

tests/test_indexation_workflows.py:50: AssertionError
======================== 1 failed in 2.34s =========================
```

## Best Practices

### Test Naming
- Use descriptive names: `test_action_condition_result`
- Include what is being tested
- Be specific about expected behavior

### Test Organization
- Group related tests in classes
- Use appropriate markers
- Add docstrings to all tests

### Test Cleanup
- Use `test_workspace` fixture for file creation
- Use `clean_database` fixture for database cleanup
- Clean up test data in fixtures

### Test Assertions
- Use specific assertions
- Check both success and failure paths
- Test edge cases
- Verify error messages

## Getting Help

### Run `make help`
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
make help
```

### Check Documentation
- `/sda/sokatov/own/perslad-1/e2e-tests/START_HERE.md`
- `/sda/sokatov/own/perslad-1/e2e-tests/AGENTS.md`
- `/sda/sokatov/own/perslad-1/e2e-tests/TEST_IMPLEMENTATION_SUMMARY.md`

### Check Service Logs
```bash
# View all service logs
make logs

# View specific service logs
docker-compose -f docker-compose.yml logs -f ingestor-test
```

## Quick Commands Reference

### Run Tests
```bash
# Single test file
python3 -m pytest tests/test_indexation_workflows.py -v

# All integration tests
python3 -m pytest -m integration -v

# With coverage
python3 -m pytest tests/ --cov --cov-report=html -v

# Parallel execution
python3 -m pytest tests/ --parallel=4 -v

# Specific test
python3 -m pytest tests/test_indexation_workflows.py::TestIndexationWorkflows::test_single_file_ingestion_text -v
```

### Environment Management
```bash
# Start services
docker-compose -f docker-compose.yml up -d

# Stop services
docker-compose -f docker-compose.yml down

# Check health
make health

# View logs
make logs

# Clean environment
make clean
```

### Makefile Commands
```bash
make test          # Run all tests
make test-component # Component tests
make test-e2e      # E2E tests
make test-coverage # With coverage
make test-parallel # Parallel execution
make health        # Check service health
make logs          # View service logs
make clean         # Clean environment
make results       # Show test results
```

---

**Happy Testing!** 🚀

**Next Steps:**
1. Run the tests using the commands above
2. Fix any failures based on error messages
3. Add more test scenarios based on actual API implementation
4. Run with coverage to identify gaps
5. Integrate into CI/CD pipeline