# E2E Tests - Start Here

This is the entry point for the E2E test subproject. Follow these steps to get started quickly.

## 🚀 Quick Start (5 minutes)

### Step 1: Setup (1 minute)
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
./scripts/setup_test_environment.sh
```

### Step 2: Run Tests (3 minutes)
```bash
# From project root
cd /sda/sokatov/own/perslad-1
./run_e2e_tests.sh all --parallel=4

# Or directly from e2e-tests
cd e2e-tests
./scripts/run_e2e_tests.sh all --parallel=4
```

### Step 3: View Results (1 minute)
```bash
# Check summary
make results

# View coverage report
open reports/coverage/index.html

# View test results
open reports/junit.xml
```

## 📋 What's Included

### Test Environment
- **Isolated Docker Compose setup** based on production
- **Ephemeral storage** - all data cleaned up automatically
- **Test workspace** with sample files
- **Test database** with pgvector for RAG testing

### Test Coverage
- **Component tests**: LLM, Embeddings, Ingestor, MCP, LangGraph
- **Integration tests**: Component interactions
- **End-to-end tests**: Complete workflows (ingest → search → chat)
- **Performance benchmarks**: System performance measurement

### Tools & Utilities
- **Makefile** - Easy command execution
- **Wrapper script** - Run from project root
- **Health checks** - Verify services are ready
- **Debug mode** - Detailed logging

## 🎯 Test Types

### Component Tests (`test_component_*.py`)
Test individual components in isolation:
- LLM Engine: Chat completion, streaming, embeddings
- Embedding Engine: Text embedding generation
- Ingestor: File ingestion, search, metadata
- MCP Servers: Tool execution, file operations
- LangGraph Agent: Orchestration, multi-turn conversations

### Integration Tests (marked with `@pytest.mark.integration`)
Test component interactions:
- LLM + Embedding interactions
- Ingestor + Database interactions
- Agent + Tool interactions

### End-to-End Tests (`test_e2e_*.py`)
Complete user workflows:
- File ingestion → Search → Chat with context
- Code analysis workflows
- RAG (Retrieval-Augmented Generation)
- Multi-component interactions
- Performance benchmarks

## 📊 Test Execution Options

### Run All Tests
```bash
./run_e2e_tests.sh all
```

### Run Specific Categories
```bash
# Component tests only
./run_e2e_tests.sh component

# E2E tests only  
./run_e2e_tests.sh e2e

# Integration tests only
./run_e2e_tests.sh integration

# Fast tests (under 30 seconds)
./run_e2e_tests.sh all --parallel=4

# Slow tests (over 30 seconds)
./run_e2e_tests.sh slow

# Smoke tests
./run_e2e_tests.sh smoke
```

### Run with Coverage
```bash
./run_e2e_tests.sh all --coverage
```

### Run in Parallel
```bash
./run_e2e_tests.sh all --parallel=4  # 4 parallel workers
./run_e2e_tests.sh all --parallel=8  # 8 parallel workers
```

### Debug Mode
```bash
./run_e2e_tests.sh all --debug
```

## 🔧 Makefile Commands

```bash
cd e2e-tests

# Setup & Environment
make setup       # Setup test environment
make start       # Start test services
make stop        # Stop test services
make restart     # Restart test services
make health      # Check service health

# Testing
make test        # Run all tests
make test-component # Component tests
make test-e2e    # E2E tests
make test-integration # Integration tests
make test-coverage # With coverage
make test-parallel # Parallel execution

# Maintenance
make clean       # Clean up environment
make reports     # Generate reports
make logs        # Show service logs
make results     # Show test results
```

## 🌐 Service URLs

| Service | Test URL | Port |
|---------|----------|------|
| LLM Engine | http://localhost:8002/v1 | 8002 |
| Embedding Engine | http://localhost:8003/v1 | 8003 |
| Ingestor | http://localhost:8125 | 8125 |
| LangGraph Agent | http://localhost:8126 | 8126 |
| MCP Bash | http://localhost:8082/mcp | 8082 |
| MCP Project | http://localhost:8084/mcp | 8084 |
| PostgreSQL | localhost:5433 | 5433 |

## 📁 Directory Structure

```
e2e-tests/
├── docker-compose.yml          # Test environment
├── pytest.ini                  # Test configuration
├── requirements-test.txt       # Test dependencies
├── Makefile                    # Build commands
├── README.md                   # Main documentation
├── START_HERE.md              # This file
├── AGENTS.md                  # Development guide
├── entrypoints/               # Docker entrypoints
│   ├── entrypoint_llm_test.sh
│   └── entrypoint_emb_test.sh
├── scripts/                   # Helper scripts
│   ├── run_e2e_tests.sh       # Main test runner
│   └── setup_test_environment.sh
├── tests/                     # Test files
│   ├── conftest.py           # Fixtures
│   ├── test_component_llm.py
│   ├── test_component_ingestor.py
│   ├── test_component_mcp.py
│   ├── test_component_langgraph.py
│   └── test_e2e_full_workflow.py
├── data/                      # Ephemeral test data
├── reports/                   # Test reports
└── model_cache/               # Model cache
```

## 📈 Test Results

### Test Execution Time
- **Component tests**: ~30 seconds each
- **Integration tests**: ~1-2 minutes each
- **E2E tests**: ~2-5 minutes each
- **Full suite**: ~10-15 minutes (parallel)

### Resource Requirements
- **GPU**: Required for LLM/Embedding tests
- **CPU**: 4+ cores recommended
- **Memory**: ~8GB base + 4GB per parallel worker
- **Storage**: ~10GB for model cache

## 🔍 Troubleshooting

### Services Won't Start
```bash
# Clean and restart
cd e2e-tests
docker-compose -f docker-compose.yml down --volumes
./scripts/setup_test_environment.sh
docker-compose -f docker-compose.yml up -d
```

### Tests Fail
```bash
# Check service health
make health

# View logs
make logs

# Run smoke tests
./scripts/run_e2e_tests.sh smoke
```

### GPU Memory Issues
1. Reduce `MAX_MODEL_LEN` in `.env`
2. Use smaller models
3. Disable parallel execution: `--parallel=false`
4. Run fewer tests at a time

## 🚀 Advanced Usage

### CI/CD Integration
```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests
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
      - name: Run E2E Tests
        run: |
          cd e2e-tests
          ./scripts/setup_test_environment.sh
          docker-compose -f docker-compose.yml up -d
          ./scripts/run_e2e_tests.sh all --parallel=2
          docker-compose -f docker-compose.yml down
```

### Manual API Testing
```bash
# Test LLM service
curl http://localhost:8002/v1/models

# Test Ingestor service
curl http://localhost:8125/

# Test MCP servers
curl http://localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Performance Profiling
```bash
# Run performance benchmarks
cd e2e-tests
python3 -m pytest tests/ -m performance --benchmark-only

# Profile with cProfile
python3 -m pytest tests/test_e2e_full_workflow.py -v --profile
```

## 📚 Additional Resources

- **Main README**: `/sda/sokatov/own/perslad-1/README.md`
- **E2E Tests README**: `/sda/sokatov/own/perslad-1/e2e-tests/README.md`
- **Development Guide**: `/sda/sokatov/own/perslad-1/e2e-tests/AGENTS.md`
- **Makefile Help**: `cd e2e-tests && make help`

## 🎯 Next Steps

1. **Read the main documentation** → [README.md](README.md)
2. **Review the development guide** → [AGENTS.md](AGENTS.md)
3. **Explore test examples** → `tests/test_component_llm.py`
4. **Run tests** → `./run_e2e_tests.sh all`
5. **View results** → `make results`

## 💡 Tips

1. **Start with component tests** to verify individual components
2. **Use parallel execution** for faster test runs
3. **Run smoke tests** for quick validation
4. **Enable coverage** for code quality analysis
5. **Use Makefile** for convenient command execution

## 📝 Test File Naming

- `test_component_*.py` - Component tests
- `test_integration_*.py` - Integration tests
- `test_e2e_*.py` - End-to-end tests
- `test_*.py` - General tests

## 🤝 Contributing

1. Add new tests to appropriate category
2. Use proper pytest markers
3. Follow test patterns in existing files
4. Add fixtures to `conftest.py` if needed
5. Update documentation

## 🆘 Getting Help

1. Check `AGENTS.md` for development guide
2. Review `README.md` for main documentation
3. Use `make help` for available commands
4. Check service logs with `make logs`
5. Review test output for specific errors

---

**Ready to test?** Run `./run_e2e_tests.sh all` and see the magic happen! ✨