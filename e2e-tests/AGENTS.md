# E2E Test Development Guide

## Quick Reference

### Run Tests
```bash
# From project root
./run_e2e_tests.sh

# From e2e-tests directory
./scripts/run_e2e_tests.sh all --parallel=4

# Using Makefile
make test          # All tests
make test-component # Component tests
make test-e2e      # E2E tests
make test-coverage # With coverage
```

### Test Environment
```bash
# Start services
docker-compose -f docker-compose.yml up -d

# Stop services
docker-compose -f docker-compose.yml down

# Check health
make health
```

## Test Structure

### Component Tests
- `test_component_llm.py` - LLM Engine tests
- `test_component_ingestor.py` - Ingestor service tests
- `test_component_mcp.py` - MCP server tests
- `test_component_langgraph.py` - LangGraph agent tests

### E2E Tests
- `test_e2e_full_workflow.py` - Complete system workflows
- Test scenarios: ingestion → search → chat → RAG

### Fixtures (conftest.py)
- `llm_client` - Async HTTP client for LLM service
- `emb_client` - Async HTTP client for embedding service
- `ingestor_client` - Async HTTP client for ingestor service
- `langgraph_client` - Async HTTP client for langgraph agent
- `mcp_*_client` - Async HTTP clients for MCP servers
- `test_workspace` - Test workspace directory
- `clean_database` - Database cleanup fixture
- `test_data` - Test data fixtures

## Writing New Tests

### Component Test Template
```python
import pytest

@pytest.mark.component
@pytest.mark.fast
class TestNewComponent:
    
    @pytest.mark.asyncio
    async def test_basic_functionality(self, client):
        """Test basic functionality"""
        response = await client.get("/endpoint")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_error_handling(self, client):
        """Test error handling"""
        response = await client.get("/invalid")
        assert response.status_code in [400, 404]
```

### E2E Test Template
```python
import pytest

@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteWorkflow:
    
    @pytest.mark.asyncio
    async def test_workflow(self, ingestor_client, langgraph_client, test_workspace):
        # 1. Setup
        file_path = create_test_file(test_workspace)
        
        # 2. Act
        ingest_response = await ingestor_client.post("/ingest", ...)
        search_response = await ingestor_client.post("/search", ...)
        chat_response = await langgraph_client.post("/v1/chat/completions", ...)
        
        # 3. Assert
        assert ingest_response.status_code == 200
        assert search_response.status_code == 200
        assert chat_response.status_code == 200
```

## Test Markers

Use pytest markers to categorize tests:

- `@pytest.mark.component` - Component-level tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.fast` - Tests under 30 seconds
- `@pytest.mark.slow` - Tests over 30 seconds
- `@pytest.mark.smoke` - Basic smoke tests
- `@pytest.mark.requires_gpu` - GPU-dependent tests
- `@pytest.mark.performance` - Performance benchmarks

## Test Data

### Test Files Created
- `test_document.md` - Markdown documentation
- `test_code.py` - Python code example
- `test_config.json` - JSON configuration
- `test_file_*.txt` - Text files for batch processing

### Test Workspace
- Located at: `/workspace-test` (inside containers)
- Files created: `test_document.md`, `test_code.py`, `test_config.json`
- Cleanup: Automatic after each test (via `test_workspace` fixture)

## Service URLs

All service URL are set in throught .env variables. Agents can see its content in `.env.example`.

## Common Test Patterns

### Health Check
```python
@pytest.mark.asyncio
async def test_service_health(self, client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
```

### Error Handling
```python
@pytest.mark.asyncio
async def test_error_handling(self, client):
    # Test with invalid input
    response = await client.post("/endpoint", json={"invalid": "data"})
    assert response.status_code in [400, 422]
    
    # Test with missing required fields
    response = await client.post("/endpoint", json={})
    assert response.status_code in [400, 422]
```

### Async Testing
```python
import asyncio

@pytest.mark.asyncio
async def test_concurrent_requests(self, client):
    async def make_request(i):
        return await client.get(f"/endpoint/{i}")
    
    tasks = [make_request(i) for i in range(5)]
    responses = await asyncio.gather(*tasks)
    
    for response in responses:
        assert response.status_code == 200
```

### Streaming Responses
```python
@pytest.mark.asyncio
async def test_streaming(self, client):
    response = await client.post("/endpoint", json=data, stream=True)
    chunks = []
    
    async for chunk in response.aiter_lines():
        if chunk.startswith("data: "):
            data_str = chunk[6:]
            if data_str != "[DONE]":
                data = json.loads(data_str)
                if "choices" in data:
                    delta = data["choices"][0].get("delta", {})
                    if "content" in delta:
                        chunks.append(delta["content"])
    
    assert len(chunks) > 0
```

## Debugging Tests

### Enable Debug Mode
```bash
./scripts/run_e2e_tests.sh all --debug
```

### Run Specific Test
```bash
python3 -m pytest tests/test_component_llm.py::TestLLMComponent::test_chat_completion_basic -v
```

### Check Service Logs
```bash
docker-compose -f docker-compose.yml logs llm-test
docker-compose -f docker-compose.yml logs ingestor-test
```

### Manual API Testing
```bash
# Test LLM
curl http://localhost:8002/v1/models

# Test Ingestor
curl http://localhost:8125/

# Test MCP
curl http://localhost:8082/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Performance Considerations

### Test Speed Optimization
1. Use `--parallel=4` for parallel execution
2. Run `fast` tests for quick validation
3. Skip `coverage` during development
4. Use `-m fast` to filter tests

### Resource Usage
- **GPU**: Required for LLM/Embedding tests
- **CPU**: 4+ cores for parallel execution
- **Memory**: ~8GB base + 4GB per worker
- **Storage**: ~10GB for model cache

### CI/CD Integration
```bash
# CI mode (minimal parallelism)
./scripts/run_e2e_tests.sh all --parallel=2

# Generate reports for CI
./scripts/run_e2e_tests.sh all --coverage --parallel=4
```

## Troubleshooting

### Common Issues

1. **Services Not Starting**
   ```bash
   docker-compose -f docker-compose.yml down --volumes
   docker-compose -f docker-compose.yml up -d
   ```

2. **GPU Memory Exhaustion**
   - Reduce `MAX_MODEL_LEN` in .env
   - Use smaller models
   - Disable parallel execution

3. **Test Failures**
   - Check service health first
   - Review service logs
   - Run smoke tests to verify setup

4. **Import Errors**
   - Ensure `PYTHONPATH=/workspace` is set
   - Check that all services are built
   - Verify Python dependencies are installed

## Maintenance

### Update Test Dependencies
```bash
cd e2e-tests
pip install --upgrade -r requirements-test.txt
```

### Clean Test Environment
```bash
cd e2e-tests
make clean
```

### Generate Reports
```bash
cd e2e-tests
make reports
```

## Test Coverage Goals

### Component Tests: 90%
- Each component should have comprehensive tests
- Test both success and failure paths
- Cover edge cases and error conditions

### Integration Tests: 80%
- Test component interactions
- Verify data flow between services
- Test error propagation

### E2E Tests: 100% critical paths
- Complete user workflows
- Performance benchmarks
- Error recovery scenarios

## Test Data Management

### Test Data Lifecycle
1. **Setup**: Create test files in `test_workspace`
2. **Execution**: Ingest, search, chat operations
3. **Cleanup**: Database truncated, files cleaned up
4. **Verification**: Results validated

### Test Data Types
- **Text files**: Documentation, READMEs
- **Code files**: Python, JavaScript, etc.
- **Config files**: JSON, YAML
- **Media files**: Images, PDFs (future)

## Continuous Improvement

### Test Categories to Add
1. **Security Tests**: Input validation, injection prevention
2. **Performance Tests**: Load testing, scalability
3. **Compatibility Tests**: Different model versions
4. **Recovery Tests**: Service restart, network failures

### Test Quality Metrics
- **Execution Time**: < 5 minutes for full suite
- **Flakiness**: < 5% failure rate
- **Coverage**: > 80% code coverage
- **Performance**: Consistent response times

## See Also

- [README.md](README.md) - Main documentation
- [pytest.ini](pytest.ini) - Test configuration
- [docker-compose.yml](docker-compose.yml) - Test environment
- [Makefile](Makefile) - Build and test commands