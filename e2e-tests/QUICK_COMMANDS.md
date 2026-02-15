# Quick Command Reference

## 🚀 **Quick Start Commands**

### From Project Root
```bash
# Run all tests
./run_e2e_tests.sh all --parallel=4

# Run specific categories
./run_e2e_tests.sh component
./run_e2e_tests.sh e2e
./run_e2e_tests.sh integration

# Run with coverage
./run_e2e_tests.sh all --coverage

# Check services
./run_e2e_tests.sh health
```

### From e2e-tests Directory
```bash
# Start services
docker-compose -f docker-compose.yml up -d

# Check health
make health

# Run tests
make test
make test-component
make test-e2e
make test-coverage
make test-parallel

# Stop services
docker-compose -f docker-compose.yml down
make stop

# Clean environment
make clean

# View results
make results
make reports
make logs
```

## 🔧 **Service Management**

### Start Services
```bash
cd /sda/sokatov/own/perslad-1/e2e-tests
docker-compose -f docker-compose.yml up -d
```

### Check Service Health
```bash
# Using make
make health

# Manual check
curl http://localhost:8002/v1/models
curl http://localhost:8125/
curl http://localhost:8126/health
```

### Stop Services
```bash
# Using make
make stop

# Manual
docker-compose -f docker-compose.yml down
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.yml logs -f

# Specific service
docker-compose -f docker-compose.yml logs -f llm-test
```

## 🧪 **Test Execution**

### Run All Tests
```bash
# From project root
./run_e2e_tests.sh all --parallel=4

# From e2e-tests
./scripts/run_e2e_tests.sh all --parallel=4
```

### Run Specific Test Files
```bash
# Infrastructure only
python3 -m pytest tests/test_infrastructure.py -v

# Indexation workflows
python3 -m pytest tests/test_indexation_workflows.py -v

# Database operations
python3 -m pytest tests/test_db_operations.py -v

# API tests
python3 -m pytest tests/test_user_requests_responses.py -v

# Integration tests
python3 -m pytest tests/test_agents_ingestor_integration.py -v

# Component tests
python3 -m pytest tests/test_component_*.py -v

# E2E tests
python3 -m pytest tests/test_e2e_*.py -v
```

### Run with Markers
```bash
# Component tests only
python3 -m pytest tests/ -m component -v

# Integration tests only
python3 -m pytest tests/ -m integration -v

# Fast tests only
python3 -m pytest tests/ -m fast -v

# Slow tests only
python3 -m pytest tests/ -m slow -v

# Combination
python3 -m pytest tests/ -m "component or integration" -v
```

### Run Specific Test
```bash
# Single test function
python3 -m pytest tests/test_indexation_workflows.py::TestIndexationWorkflows::test_file_type_detection -v

# Single test class
python3 -m pytest tests/test_indexation_workflows.py::TestIndexationWorkflows -v
```

### Parallel Execution
```bash
# Auto-detect cores
python3 -m pytest tests/ -n auto -v

# Specific number of workers
python3 -m pytest tests/ -n 4 -v

# Parallel with markers
python3 -m pytest tests/ -m fast -n auto -v
```

### Coverage Reports
```bash
# HTML coverage
python3 -m pytest tests/ --cov --cov-report=html -v

# XML coverage (for CI)
python3 -m pytest tests/ --cov --cov-report=xml -v

# Terminal coverage
python3 -m pytest tests/ --cov --cov-report=term-missing -v

# Specific modules
python3 -m pytest tests/ --cov=../agents --cov=../ingestor --cov-report=html -v
```

## 📊 **Results and Reports**

### Check Test Results
```bash
# Summary (from e2e-tests)
make results

# Detailed output
python3 -m pytest tests/ -v --tb=short

# Full tracebacks
python3 -m pytest tests/ -v --tb=long

# Only failures
python3 -m pytest tests/ -v --tb=no -q
```

### View Reports
```bash
# Open coverage report (if exists)
open reports/coverage/index.html
# or
xdg-open reports/coverage/index.html

# View JUnit XML
open reports/junit.xml
# or
cat reports/junit.xml | xmllint --format - | head -50
```

### Performance Metrics
```bash
# Benchmark tests
python3 -m pytest tests/ -m performance --benchmark-only -v

# Profile tests
python3 -m pytest tests/test_e2e_full_workflow.py --profile -v
```

## 🛠 **Troubleshooting**

### Services Won't Start
```bash
# Clean and restart
cd e2e-tests
docker-compose -f docker-compose.yml down --volumes
./scripts/setup_test_environment.sh
docker-compose -f docker-compose.yml up -d
```

### Tests Fail Due to Connection Errors
```bash
# Check if services are running
docker-compose -f docker-compose.yml ps

# Check specific service
curl http://localhost:8125/

# View service logs
docker-compose -f docker-compose.yml logs llm-test
```

### GPU Memory Issues
```bash
# Check GPU memory
nvidia-smi

# Reduce model size in .env
# Edit: MAX_MODEL_LEN=2048

# Run fewer parallel tests
./run_e2e_tests.sh all --parallel=2
```

### Import Errors
```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Set PYTHONPATH
export PYTHONPATH=/workspace

# Run with explicit path
cd e2e-tests
python3 -m pytest tests/ -v --tb=short
```

### Streaming Test Issues
```bash
# Streaming tests are currently bypassed
# They make regular requests instead
# This is a known limitation
# TODO: Implement proper httpx stream handling
```

## 📈 **Performance Testing**

### Quick Performance Test
```bash
# Run performance tests
python3 -m pytest tests/ -m performance -v

# Run with time measurement
python3 -m pytest tests/test_indexation_workflows.py::TestIndexationWorkflows::test_ingestion_performance_metrics -v --durations=10
```

### Load Testing
```bash
# Concurrent requests test
python3 -m pytest tests/test_user_requests_responses.py::TestUserRequestsResponses::test_concurrent_api_requests -v

# Large payload test
python3 -m pytest tests/test_user_requests_responses.py::TestUserRequestsResponses::test_large_payloads -v
```

## 🔒 **Security Testing**

### Run Security Tests (if added)
```bash
# Security tests would be in test_security.py
python3 -m pytest tests/test_security.py -v

# Input validation tests
python3 -m pytest tests/ -m security -v
```

## 📝 **Test Writing Commands**

### Check Test Syntax
```bash
# Validate Python syntax
python3 -m py_compile tests/test_new.py

# Run syntax check
python3 -c "import tests.test_new"
```

### Run New Test
```bash
# Test your new test file
python3 -m pytest tests/test_new.py -v

# Test specific function
python3 -m pytest tests/test_new.py::TestClass::test_function -v
```

### Debug Test
```bash
# Run with debug output
python3 -m pytest tests/test_new.py -v -s

# Run with pdb
python3 -m pytest tests/test_new.py -v --pdb
```

## 📋 **CI/CD Commands**

### GitHub Actions Example
```bash
# Minimal test run for CI
./run_e2e_tests.sh all --parallel=2

# Generate reports for CI
./run_e2e_tests.sh all --parallel=2 --coverage

# Check test results
make results

# Exit with test result code
python3 -m pytest tests/ -v --tb=short || exit 1
```

### Docker in CI
```bash
# Start services in CI
docker-compose -f docker-compose.yml up -d

# Wait for services
sleep 30

# Run tests
./run_e2e_tests.sh all --parallel=2

# Stop services
docker-compose -f docker-compose.yml down
```

## 🎯 **Makefile Commands**

### All Commands
```bash
# Setup
make setup          # Setup environment
make start          # Start services
make stop           # Stop services
make restart        # Restart services

# Testing
make test           # All tests
make test-component # Component tests
make test-e2e       # E2E tests
make test-integration # Integration tests
make test-coverage  # With coverage
make test-parallel  # Parallel execution

# Maintenance
make clean          # Clean environment
make reports        # Generate reports
make logs           # View logs
make health         # Check services
make results        # View test results
```

## 🔍 **Debugging Commands**

### Service Debugging
```bash
# Check service status
docker-compose -f docker-compose.yml ps

# Check service logs
docker-compose -f docker-compose.yml logs service-name

# Check service health
curl -s http://localhost:8125/ | python3 -m json.tool
```

### Test Debugging
```bash
# Run with verbose output
python3 -m pytest tests/test_new.py -v -s

# Run with print statements visible
python3 -m pytest tests/test_new.py -v -s --tb=short

# Run specific test with debug
python3 -m pytest tests/test_new.py::TestClass::test_function -v -s
```

### Database Debugging
```bash
# Connect to test database
psql -h localhost -p 5433 -U rag_test -d rag_test

# Check tables
psql -h localhost -p 5433 -U rag_test -d rag_test -c "\dt"

# Check table sizes
psql -h localhost -p 5433 -U rag_test -d rag_test -c "SELECT table_name, n_live_tup FROM pg_stat_user_tables;"
```

## 📊 **Monitoring Commands**

### Resource Usage
```bash
# Check CPU/Memory
htop

# Check GPU usage
watch -n 1 nvidia-smi

# Check disk space
df -h

# Check network
netstat -tulpn | grep :8
```

### Docker Resource Usage
```bash
# Container stats
docker stats

# Container logs with timestamps
docker-compose -f docker-compose.yml logs -f --timestamps

# Container resource limits
docker-compose -f docker-compose.yml top
```

## 📚 **Help Commands**

### Pytest Help
```bash
# Pytest help
python3 -m pytest --help

# Marker help
python3 -m pytest --markers

# Configuration help
python3 -m pytest --version
```

### Makefile Help
```bash
# Makefile help
make help

# Makefile targets
make -n  # Show what would be executed
```

### Environment Variables
```bash
# List relevant environment variables
env | grep -E "(TEST|LLM|INGEST|DB|PROJECT)"

# Set environment variables
export TEST_MODE=true
export LOG_LEVEL=DEBUG
export PYTHONPATH=/workspace
```

## 🎉 **Quick Reference Summary**

### **Essential Commands**
1. **Start services**: `docker-compose -f docker-compose.yml up -d`
2. **Check health**: `make health`
3. **Run tests**: `./run_e2e_tests.sh all --parallel=4`
4. **View results**: `make results`
5. **Clean up**: `make clean`

### **Test Categories**
- **Component**: `make test-component`
- **Integration**: `make test-integration`
- **E2E**: `make test-e2e`
- **All**: `make test`

### **Reports**
- **Coverage**: `open reports/coverage/index.html`
- **JUnit**: `open reports/junit.xml`
- **Logs**: `make logs`

### **Troubleshooting**
- **Service issues**: `docker-compose -f docker-compose.yml logs`
- **Test failures**: `python3 -m pytest -v --tb=short`
- **Connection errors**: `make health`

### **Performance**
- **Parallel**: `--parallel=4`
- **Fast tests**: `-m fast`
- **Coverage**: `--cov --cov-report=html`

---

**Ready to test!** 🚀

The test framework is complete and ready for use. Just start the services and run the tests!