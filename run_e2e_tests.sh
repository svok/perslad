#!/bin/bash
set -e

# Wrapper script to run E2E tests from project root
# This script ensures proper environment setup and runs tests in the e2e-tests subproject

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E2E_DIR="$SCRIPT_DIR/e2e-tests"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}E2E Test Runner - Project Wrapper${NC}"
echo ""

# Check if e2e-tests directory exists
if [ ! -d "$E2E_DIR" ]; then
    echo -e "${RED}Error: E2E tests directory not found at $E2E_DIR${NC}"
    echo "Please create the e2e-tests subproject first."
    exit 1
fi

# Check if docker-compose exists in e2e-tests
if [ ! -f "$E2E_DIR/docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found in e2e-tests directory${NC}"
    exit 1
fi

# Set environment variables
export PROJECT_ROOT="$SCRIPT_DIR"

# Check if services are already running
echo -e "${YELLOW}Checking if test services are running...${NC}"
cd "$E2E_DIR"
RUNNING_SERVICES=$(docker compose -f docker-compose.yml ps --services 2>/dev/null | wc -l)
if [ "$RUNNING_SERVICES" -eq 0 ]; then
    echo -e "${YELLOW}No test services running. Starting them...${NC}"
    docker compose -f docker-compose.yml up -d
    
    # Wait for services to be initially created
    echo -e "${YELLOW}Waiting for containers to initialize...${NC}"
    sleep 5
else
    echo -e "${GREEN}Test services are already running ($RUNNING_SERVICES services)${NC}"
fi

# Health check
echo -e "${YELLOW}Performing health checks for all services (this may take several minutes)...${NC}"
# Increase iterations to 300 (approx 10 minutes) for heavy models
for i in {1..300}; do
    READY=true
    # Check LLM service
    if ! curl -s http://localhost:8002/v1/models > /dev/null 2>&1; then
        READY=false
    fi
    # Check Embedding service
    if ! curl -s http://localhost:8003/v1/models > /dev/null 2>&1; then
        READY=false
    fi
    # Check Ingestor service
    if ! curl -s http://localhost:8125/ > /dev/null 2>&1; then
        READY=false
    fi
    
    if [ "$READY" = true ]; then
        echo -e "${GREEN}All services are ready!${NC}"
        break
    fi
    
    if [ $i -eq 300 ]; then
        echo -e "${RED}Error: Services are not ready after 10 minutes. Aborting.${NC}"
        exit 1
    else
        echo -n "."
        sleep 2
    fi
done
echo ""

# Run the tests
echo -e "${YELLOW}Running E2E tests...${NC}"
echo ""

# Pass all arguments to the test runner
cd "$E2E_DIR"
./scripts/run_e2e_tests.sh "$@"

EXIT_CODE=$?

# Show next steps
echo ""
echo -e "${BLUE}Test run complete${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
fi

echo ""
echo "To view results:"
echo "  open $E2E_DIR/reports/coverage/index.html  # Coverage report"
echo "  open $E2E_DIR/reports/junit.xml           # Test results"
echo ""
echo "To stop services:"
echo "  docker compose -f $E2E_DIR/docker-compose.yml down"
echo ""
echo "For more commands:"
echo "  cd $E2E_DIR && make help"

exit $EXIT_CODE