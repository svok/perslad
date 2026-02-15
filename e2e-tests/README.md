# E2E Tests Subproject

This subproject contains end-to-end tests for the entire system, testing both individual components and their complete interactions.

## Overview

The E2E test suite provides:

1. **Component Tests** - Testing individual components in isolation
2. **Integration Tests** - Testing interactions between components
3. **End-to-End Tests** - Testing complete user workflows
4. **Performance Tests** - Benchmarking system performance

## Architecture

### Test Environment

- **Docker Compose** - Isolated test environment based on production docker-compose.yml
- **Ephemeral Storage** - All data is temporary and cleaned up after tests
- **Test Workspace** - Dedicated workspace for test files
- **Test Database** - Separate PostgreSQL instance with pgvector

### Components Tested

1. **LLM Engine** - Chat completion, streaming, tool calling
2. **Embedding Engine** - Text embedding generation
3. **Ingestor Service** - File ingestion, processing, search
4. **LangGraph Agent** - Orchestration and agent functionality
5. **MCP Servers** - Tool execution and file operations
6. **Database** - Vector storage and search

## Quick Start

### 1. Setup Environment

```bash
cd e2e-tests
./scripts/setup_test_environment.sh
```

### 2. Start Test Services

```bash
docker-compose -f docker-compose.yml up -d
```

### 3. Run Tests

```bash
# Run all tests
./scripts/run_e2e_tests.sh

# Run component tests only
./scripts/run_e2e_tests.sh component

# Run e2e tests only
./scripts/run_e2e_tests.sh e2e

# Run with coverage
./scripts/run_e2e_tests.sh all --coverage

# Run in parallel (4 workers)
./scripts/run_e2e_tests.sh all --parallel=4
```

### 4. View Results

```bash
# Test reports are in reports/ directory
open reports/index.html  # Coverage report
open reports/junit.xml   # Test results
```

### 5. Clean Up

```bash
docker-compose -f docker-compose.yml down
```

## Test Types

### Component Tests (`test_component_*.py`)
- **LLM Engine** - Chat completion, embeddings, streaming
- **Embedding Engine** - Embedding generation, consistency
- **Ingestor** - File ingestion, metadata extraction, search
- **MCP Servers** - Tool listing, execution, error handling
- **LangGraph Agent** - Chat completion, streaming, multi-turn

### Integration Tests (`test_integration_*.py`)
- LLM + Embedding interactions
- Ingestor + Database interactions
- Agent + Tool interactions

### End-to-End Tests (`test_e2e_*.py`)
- Complete workflow: Ingestion → Search → Chat
- Code analysis workflows
- RAG (Retrieval-Augmented Generation) workflows
- Multi-component interactions
- Performance benchmarks

## Test Structure

```
e2e-tests/
├── docker-compose.yml          # Test environment definition
├── pytest.ini                  # Test configuration
├── requirements-test.txt       # Test dependencies
├── entrypoints/               # Docker entrypoints
│   ├── entrypoint_llm_test.sh
│   └── entrypoint_emb_test.sh
├── scripts/                   # Helper scripts
│   ├── run_e2e_tests.sh
│   └── setup_test_environment.sh
├── tests/                     # Test files
│   ├── conftest.py           # Fixtures and configuration
│   ├── test_component_llm.py
│   ├── test_component_ingestor.py
│   ├── test_component_mcp.py
│   ├── test_component_langgraph.py
│   └── test_e2e_full_workflow.py
├── data/                      # Ephemeral test data
├── reports/                   # Test reports and coverage
└── model_cache/               # Model cache (optional)
```

## Configuration

### Environment Variables

All services are configured via the parent `.env` file. Key variables:

```bash
# LLM Configuration
MODEL_NAME=Qwen/Qwen2-7B-Instruct
EMB_MODEL_NAME=BAAI/bge-m3
MAX_MODEL_LEN=4096

# API Keys
OPENAI_API_KEY=test-key-12345

# Test Mode
TEST_MODE=true
```

### Test Markers

Use pytest markers to run specific test categories:

```bash
pytest -m component      # Component tests
pytest -m e2e            # End-to-end tests
pytest -m integration    # Integration tests
pytest -m fast           # Fast tests (<30s)
pytest -m slow           # Slow tests (>30s)
pytest -m smoke          # Smoke tests
pytest -m requires_gpu   # GPU-dependent tests
```

## Test Data

The test environment creates sample files in `/workspace-test`:

- `test_document.md` - Markdown documentation
- `test_code.py` - Python code example
- `test_config.json` - JSON configuration
- `test_file_*.txt` - Text files for batch processing

## Performance Considerations

### Test Speed
- **Component tests**: ~30 seconds each
- **Integration tests**: ~1-2 minutes each
- **E2E tests**: ~2-5 minutes each
- **Full test suite**: ~10-15 minutes

### Resource Usage
- **GPU**: Required for LLM/Embedding tests (1 GPU recommended)
- **CPU**: Multiple cores for parallel test execution
- **Memory**: ~8GB for base services + 4GB per parallel worker
- **Storage**: ~10GB for model cache (downloaded on first run)

### Optimization Tips
1. Use `--parallel=4` for faster execution on multi-core systems
2. Run component tests first to ensure basic functionality
3. Use `--coverage` only when needed (slows down execution)
4. Use `-m fast` for quick validation during development

## Debugging

### Enable Debug Mode
```bash
./scripts/run_e2e_tests.sh all --debug
```

### Check Service Health
```bash
# Check all services
docker-compose -f docker-compose.yml ps

# Check specific service logs
docker-compose -f docker-compose.yml logs llm-test
docker-compose -f docker-compose.yml logs ingestor-test
```

### Manual Service Testing
```bash
# Test LLM service
curl http://localhost:8002/v1/models

# Test Ingestor service
curl http://localhost:8125/

# Test MCP servers
curl http://localhost:8082/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Setup Docker
        run: |
          sudo systemctl start docker
      - name: Run E2E Tests
        run: |
          cd e2e-tests
          ./scripts/setup_test_environment.sh
          docker-compose -f docker-compose.yml up -d
          ./scripts/run_e2e_tests.sh all --parallel=2
          docker-compose -f docker-compose.yml down
```

### Test Report Generation
```bash
# Generate HTML coverage report
pytest --cov-report=html:reports/coverage

# Generate JUnit XML for CI
pytest --junitxml=reports/junit.xml

# Generate allure reports
pytest --alluredir=reports/allure
```

## Troubleshooting

### Common Issues

1. **GPU Memory Exhaustion**
   - Reduce `MAX_MODEL_LEN` in .env
   - Use smaller models
   - Disable parallel execution

2. **Docker Compose Errors**
   - Ensure Docker is running
   - Check port availability (8002, 8125, etc.)
   - Clean up old containers: `docker-compose down --volumes`

3. **Test Failures**
   - Check service logs for errors
   - Verify services are healthy
   - Run health check: `pytest -m smoke`

4. **Slow Test Execution**
   - Use parallel execution
   - Run only required test types
   - Consider using test tags for CI

## Contributing

### Adding New Tests
1. Create test file in `tests/` directory
2. Use appropriate markers (`@pytest.mark.component`, etc.)
3. Add fixtures to `conftest.py` if needed
4. Follow naming convention: `test_{type}_{component}.py`

### Test Guidelines
- Tests must be idempotent (can run multiple times)
- Clean up resources after each test
- Use descriptive test names
- Add proper error handling
- Test both success and failure scenarios

### Performance Benchmarks
- Document baseline performance
- Track performance over time
- Alert on significant regressions

## License

This test suite is part of the main project and follows the same license.