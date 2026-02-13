#!/bin/bash
set -e

# Setup script for E2E test environment
# This script prepares the test environment before running tests

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$E2E_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up E2E test environment...${NC}"

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p data/postgres
mkdir -p data/workspace
mkdir -p reports
mkdir -p model_cache

# Check if PROJECT_ROOT is set
if [ -z "$PROJECT_ROOT" ]; then
    export PROJECT_ROOT="/workspace"
    echo -e "${YELLOW}Setting PROJECT_ROOT to /workspace${NC}"
fi

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker not found. Please install Docker to run the tests.${NC}"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    if docker compose version &> /dev/null; then
        echo -e "${YELLOW}Using docker compose (v2 syntax)${NC}"
        DOCKER_COMPOSE_CMD="docker compose"
    else
        echo -e "${YELLOW}Docker compose not found. Please install docker-compose to run the tests.${NC}"
        exit 1
    fi
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

# Check if .env file exists
if [ ! -f "../.env" ]; then
    echo -e "${YELLOW}No .env file found. Creating default .env file...${NC}"
    cat > ../.env << EOF
# LLM Configuration
MODEL_NAME=Qwen/Qwen2-7B-Instruct
EMB_MODEL_NAME=BAAI/bge-m3
QUANTIZATION=
MAX_MODEL_LEN=4096
CONTEXT_SIZE=4096

# API Keys
OPENAI_API_KEY=test-key-12345
WEBUI_SECRET_KEY=change-me-in-production

# Storage
PGVECTOR_ENABLED=true
EOF
    echo -e "${GREEN}Created default .env file${NC}"
fi

# Check if models are available (optional)
echo -e "${YELLOW}Model Configuration${NC}"
echo "LLM Model: ${MODEL_NAME:-Qwen/Qwen2-7B-Instruct}"
echo "Embedding Model: ${EMB_MODEL_NAME:-BAAI/bge-m3}"
echo ""
echo "Note: Models will be downloaded on first run if not cached."

# Check Python dependencies
echo -e "${YELLOW}Checking Python dependencies...${NC}"
python3 -c "import pytest, httpx, asyncio" 2>/dev/null || {
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install -r requirements-test.txt
}

# Build test containers (if needed)
echo -e "${YELLOW}Building test containers...${NC}"
$DOCKER_COMPOSE_CMD -f docker-compose.yml build llm-test emb-test

# Create test workspace files
echo -e "${YELLOW}Creating test workspace files...${NC}"
cat > data/workspace/test_document.md << EOF
# Test Document for E2E Tests

This document is used for testing the end-to-end workflow.

## Sections

### Section 1
Content for section 1.

### Section 2
Content for section 2.

## Code Example
\`\`\`python
def hello():
    print("Hello from test document!")
\`\`\`
EOF

cat > data/workspace/test_code.py << EOF
# Test Python code for E2E tests

def add(a, b):
    """Add two numbers"""
    return a + b

def multiply(a, b):
    """Multiply two numbers"""
    return a * b

class Calculator:
    """Simple calculator class"""
    
    def __init__(self):
        self.result = 0
    
    def add_to_result(self, value):
        self.result += value
        return self.result
EOF

cat > data/workspace/test_config.json << EOF
{
  "test": true,
  "version": "1.0.0",
  "features": ["testing", "e2e"],
  "settings": {
    "debug": true,
    "timeout": 30
  }
}
EOF

# Create test data directory
mkdir -p data/test_files
for i in {1..5}; do
    cat > data/test_files/test_file_$i.txt << EOF
Test file $i for E2E testing
This file is part of a test batch.
Line 3 of file $i.
EOF
done

echo -e "${GREEN}Test workspace files created${NC}"

# Display summary
echo ""
echo -e "${BLUE}=== E2E Test Environment Setup Complete ===${NC}"
echo ""
echo "Directories created:"
echo "  - data/postgres (ephemeral database storage)"
echo "  - data/workspace (test workspace)"
echo "  - reports (test reports and coverage)"
echo "  - model_cache (model cache directory)"
echo ""
echo "Test files created:"
echo "  - test_document.md"
echo "  - test_code.py"
echo "  - test_config.json"
echo "  - 5 test files in test_files/"
echo ""
echo "To start the test environment:"
echo "  $ $DOCKER_COMPOSE_CMD -f docker-compose.yml up -d"
echo ""
echo "To run tests:"
echo "  $ ./scripts/run_e2e_tests.sh"
echo ""
echo "To stop the test environment:"
echo "  $ $DOCKER_COMPOSE_CMD -f docker-compose.yml down"
echo ""
echo -e "${GREEN}Environment ready for testing!${NC}"