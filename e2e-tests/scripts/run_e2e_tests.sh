#!/bin/bash
set -e

# E2E Tests Runner Script
# This script runs end-to-end tests on the docker-compose test environment

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$E2E_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="${1:-all}"
COVERAGE="${2:-false}"
PARALLEL="${3:-auto}"
REPORT_DIR="${4:-reports}"
DEBUG="${5:-false}"

# Parse arguments
for arg in "$@"; do
    case $arg in
        --type=*)
            TEST_TYPE="${arg#*=}"
            ;;
        --coverage)
            COVERAGE=true
            ;;
        --parallel=*)
            PARALLEL="${arg#*=}"
            ;;
        --reports=*)
            REPORT_DIR="${arg#*=}"
            ;;
        --debug)
            DEBUG=true
            ;;
        --help|-h)
            echo "Usage: $0 [TEST_TYPE] [COVERAGE] [PARALLEL] [REPORT_DIR] [DEBUG]"
            echo ""
            echo "Examples:"
            echo "  $0 all                    # Run all tests"
            echo "  $0 component              # Run component tests only"
            echo "  $0 e2e                    # Run e2e tests only"
            echo "  $0 --coverage             # Run with coverage"
            echo "  $0 --parallel=4           # Run with 4 parallel workers"
            echo "  $0 --reports=/tmp/reports # Specify reports directory"
            echo "  $0 --debug                # Debug mode"
            echo ""
            echo "Available test types:"
            echo "  all, component, e2e, integration, smoke, fast, slow"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}Starting E2E Tests...${NC}"
echo "Test type: $TEST_TYPE"
echo "Coverage: $COVERAGE"
echo "Parallel: $PARALLEL"
echo "Reports directory: $REPORT_DIR"
echo "Debug: $DEBUG"

# Create reports directory
mkdir -p "$REPORT_DIR"
mkdir -p "$REPORT_DIR/coverage"
mkdir -p "$REPORT_DIR/logs"

# Set debug options
DEBUG_OPTS=""
if [ "$DEBUG" = true ]; then
    DEBUG_OPTS="--log-cli-level=DEBUG --capture=no"
fi

# Set coverage options
COVERAGE_OPTS=""
if [ "$COVERAGE" = true ]; then
    COVERAGE_OPTS="--cov=../agents --cov=../ingestor --cov=../infra --cov-report=html:$REPORT_DIR/coverage --cov-report=xml:$REPORT_DIR/coverage.xml --cov-report=term-missing"
fi

# Set parallel options
PARALLEL_OPTS=""
if [ "$PARALLEL" != "false" ]; then
    # Check if pytest-xdist is available
    if python3 -c "import xdist" 2>/dev/null; then
        if [ "$PARALLEL" = "auto" ]; then
            PARALLEL_OPTS="-n auto"
        else
            PARALLEL_OPTS="-n $PARALLEL"
        fi
    else
        echo -e "${YELLOW}Warning: pytest-xdist not installed, running sequentially${NC}"
        # Fall back to no parallel execution
        PARALLEL_OPTS=""
    fi
fi

# Build test type selector
TYPE_OPTS=""
case $TEST_TYPE in
    component)
        TYPE_OPTS="-m component"
        ;;
    e2e)
        TYPE_OPTS="-m e2e"
        ;;
    integration)
        TYPE_OPTS="-m integration"
        ;;
    smoke)
        TYPE_OPTS="-m smoke"
        ;;
    fast)
        TYPE_OPTS="-m fast"
        ;;
    slow)
        TYPE_OPTS="-m slow"
        ;;
    all)
        # No type filter, run all
        ;;
    *)
        echo -e "${RED}Unknown test type: $TEST_TYPE${NC}"
        echo "Available types: all, component, e2e, integration, smoke, fast, slow"
        exit 1
        ;;
esac

# Set environment variables
export TEST_MODE=true
export LOG_LEVEL=DEBUG
export PYTHONPATH="/workspace:$PYTHONPATH"

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
echo "Command: pytest $TYPE_OPTS $PARALLEL_OPTS $COVERAGE_OPTS $DEBUG_OPTS"

# Run pytest with timeout
timeout 3600 pytest \
    $TYPE_OPTS \
    $PARALLEL_OPTS \
    $COVERAGE_OPTS \
    $DEBUG_OPTS \
    --junitxml="$REPORT_DIR/junit.xml" \
    --tb=short \
    --strict-markers \
    --strict-config \
    --disable-warnings \
    -v

# Check exit code
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
elif [ $EXIT_CODE -eq 124 ]; then
    echo -e "${RED}✗ Tests timed out after 1 hour${NC}"
    EXIT_CODE=1
else
    echo -e "${RED}✗ Tests failed with exit code $EXIT_CODE${NC}"
fi

# Generate summary report
if [ -f "$REPORT_DIR/junit.xml" ]; then
    echo -e "${BLUE}Generating test summary...${NC}"
    python3 << EOF
import xml.etree.ElementTree as ET
import sys

try:
    tree = ET.parse('$REPORT_DIR/junit.xml')
    root = tree.getroot()
    
    tests = int(root.get('tests', 0))
    failures = int(root.get('failures', 0))
    errors = int(root.get('errors', 0))
    skipped = int(root.get('skipped', 0))
    
    print(f"Test Summary:")
    print(f"  Total:    {tests}")
    print(f"  Passed:   {tests - failures - errors - skipped}")
    print(f"  Failed:   {failures}")
    print(f"  Errors:   {errors}")
    print(f"  Skipped:  {skipped}")
    
    if failures + errors > 0:
        print(f"\\n{failures + errors} test(s) failed!")
        sys.exit(1)
    else:
        print(f"\\nAll tests passed!")
        sys.exit(0)
        
except Exception as e:
    print(f"Error parsing results: {e}")
    sys.exit(1)
EOF
fi

exit $EXIT_CODE