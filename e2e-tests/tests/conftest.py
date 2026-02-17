import logging
import os

import pytest
import pytest_asyncio
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables from .env file
load_dotenv(dotenv_path=".env.local", override=False)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import endpoint constants
from infra.config import Timeouts


# =====================
# DB Helper Functions
# =====================

def get_relative_path(file_path: str, project_root: str) -> str:
    """Конвертировать абсолютный путь в относительный для БД"""
    if file_path.startswith(project_root):
        rel_path = os.path.relpath(file_path, project_root)
        return rel_path
    return file_path


def get_file_summary(db_engine, file_path: str, project_root: str | None = None) -> dict | None:
    """Получить file_summary с метаданными"""
    if project_root is not None:
        file_path = get_relative_path(file_path, project_root)
    with db_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT file_path, summary, metadata, mtime, checksum FROM file_summaries WHERE file_path = :path"
        ), {"path": file_path})
        row = result.fetchone()
        if row:
            metadata = row[2]
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            return {
                "file_path": row[0],
                "summary": row[1],
                "metadata": metadata,
                "mtime": row[3],
                "checksum": row[4]
            }
        return None


def get_chunks_count_for_file(db_engine, file_path: str, project_root: str | None = None) -> int:
    """Количество chunks для файла"""
    if project_root is not None:
        file_path = get_relative_path(file_path, project_root)
    with db_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM chunks WHERE file_path = :path"
        ), {"path": file_path})
        return result.fetchone()[0]


def get_chunks_count(db_engine, file_pattern: str | None = None) -> int:
    """Подсчитать chunks в БД"""
    with db_engine.connect() as conn:
        if file_pattern:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM chunks WHERE file_path LIKE :pattern"
            ), {"pattern": f"%{file_pattern}%"})
        else:
            result = conn.execute(text("SELECT COUNT(*) FROM chunks"))
        return result.fetchone()[0]


def get_file_summaries_count(db_engine) -> int:
    """Подсчитать file_summaries в БД"""
    with db_engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM file_summaries"))
        return result.fetchone()[0]


def assert_file_indexed_successfully(db_engine, file_path: str, project_root: str | None = None) -> None:
    """Проверить что файл успешно проиндексирован"""
    summary = get_file_summary(db_engine, file_path, project_root)
    assert summary is not None, f"File {file_path} not found in file_summaries"
    
    metadata = summary["metadata"]
    assert metadata.get("valid") == True, f"File should be valid, got metadata: {metadata}"
    
    chunks_count = get_chunks_count_for_file(db_engine, file_path, project_root)
    assert chunks_count > 0, f"Valid file should have chunks, got {chunks_count}"


def assert_file_indexed_with_error(db_engine, file_path: str, project_root: str | None = None, expected_reason: str | None = None) -> None:
    """Проверить что файл проиндексирован с ошибкой"""
    summary = get_file_summary(db_engine, file_path, project_root)
    assert summary is not None, f"File {file_path} not found in file_summaries"
    
    metadata = summary["metadata"]
    assert "invalid_reason" in metadata, f"File should have invalid_reason, got metadata: {metadata}"
    
    if expected_reason:
        assert expected_reason.lower() in metadata["invalid_reason"].lower(), \
            f"Expected '{expected_reason}' in reason, got: {metadata['invalid_reason']}"
    
    chunks_count = get_chunks_count_for_file(db_engine, file_path, project_root)
    assert chunks_count == 0, f"Invalid file should have 0 chunks, got {chunks_count}"

# Configuration from environment
import tempfile
TEST_CONFIG = {
    'llm_url': os.getenv('LLM_URL', 'http://localhost:8000/v1'),
    'llm_served_model_name': os.getenv('LLM_SERVED_MODEL_NAME', 'default-model'),
    'emb_url': os.getenv('EMB_URL', 'http://localhost:8001/v1'),
    'emb_served_model_name': os.getenv('EMB_SERVED_MODEL_NAME', 'embed-model'),
    'pg_url': os.getenv('PG_URL', 'postgresql://rag:rag@postgres:5432/rag'),
    'pgvector_dimensions': int(os.getenv('PGVECTOR_DIMENSIONS', '768')),
    'ingestor_url': os.getenv('INGESTOR_URL', 'http://localhost:8124'),
    'langgraph_url': os.getenv('LANGGRAPH_AGENT_URL', 'http://localhost:8123/v1'),
    'mcp_bash_url': os.getenv('MCP_BASH_URL', 'http://localhost:8081/mcp'),
    'mcp_project_url': os.getenv('MCP_PROJECT_URL', 'http://localhost:8083/mcp'),
    'test_mode': os.getenv('TEST_MODE', 'true').lower() == 'true',
    'workspace_root': os.getenv('PROJECT_ROOT', '/workspace'),
    'test_workspace': os.path.join(tempfile.gettempdir(), 'workspace-test')
}

@pytest.fixture(scope="session")
def config():
    """Global test configuration"""
    return TEST_CONFIG

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# For pytest-asyncio 1.x, we need to override the event loop policy
@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    """Set event loop policy for session"""
    import asyncio
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    return None

@pytest_asyncio.fixture(scope="function")
async def llm_client(config):
    """Async HTTP client for LLM service"""
    async with httpx.AsyncClient(
        base_url=config['llm_url'],
        timeout=httpx.Timeout(Timeouts.STANDARD)
    ) as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def emb_client(config):
    """Async HTTP client for embedding service"""
    async with httpx.AsyncClient(
        base_url=config['emb_url'],
        timeout=httpx.Timeout(Timeouts.STANDARD)
    ) as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def ingestor_client(config):
    """Async HTTP client for ingestor service"""
    async with httpx.AsyncClient(
        base_url=config['ingestor_url'],
        timeout=httpx.Timeout(Timeouts.LONG)
    ) as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def langgraph_client(config):
    """Async HTTP client for langgraph agent service"""
    async with httpx.AsyncClient(
        base_url=config['langgraph_url'],
        timeout=httpx.Timeout(Timeouts.VERY_LONG)
    ) as client:
        yield client

import pytest
import asyncio
import httpx
import json
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


# MCP Client class for handling SSE connections
@dataclass
class MCPClientsession:
    """Manages MCP server session with SSE"""
    
    base_url: str
    client: httpx.AsyncClient
    session_id: Optional[str] = None
    
    def _parse_sse_response(self, text: str) -> dict:
        """Parse SSE (Server-Sent Events) format response and extract JSON"""
        # Handle Windows-style line endings
        lines = text.replace('\r\n', '\n').split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('data:'):
                try:
                    return json.loads(line[5:].strip())
                except json.JSONDecodeError as e:
                    continue
        raise ValueError("No valid JSON data found in SSE response")
    
    async def initialize(self) -> str:
        """Initialize MCP session and return session ID"""
        # Try POST with initialize method (JSON-RPC)
        payload = {
            "jsonrpc": "2.0",
            "id": str(int(datetime.now().timestamp() * 1000000)),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0"
                }
            }
        }
        
        response = await self.client.post(
            "/",
            json=payload,
            headers={
                "Accept": "application/json, text/event-stream"
            }
        )
        
        if response.status_code == 200:
            # Session ID should be in header
            self.session_id = response.headers.get("mcp-session-id")
            
            if not self.session_id:
                raise Exception("Failed to get session ID from MCP server")
            
            return self.session_id
        else:
            # Try fallback: GET request with Accept header
            response = await self.client.get(
                "/",
                headers={"Accept": "application/json, text/event-stream"}
            )
            
            if response.status_code == 200:
                self.session_id = response.headers.get("mcp-session-id")
                
                if not self.session_id:
                    raise Exception("Failed to get session ID from MCP server")
                
                return self.session_id
            else:
                raise Exception(f"Failed to initialize MCP session: {response.status_code} - {response.text}")
    
    async def get(self, path: str, **kwargs):
        """Proxy HTTP GET requests to underlying client with session ID"""
        headers = kwargs.pop('headers', {})
        # Always include session ID if available
        if self.session_id:
            headers['mcp-session-id'] = self.session_id
        return await self.client.get(path, headers=headers, **kwargs)
    
    async def post(self, path: str, **kwargs):
        """Proxy HTTP POST requests to underlying client with session ID"""
        headers = kwargs.pop('headers', {})
        # Always include session ID if available
        if self.session_id:
            headers['mcp-session-id'] = self.session_id
        # Always include required Accept header for MCP
        if 'Accept' not in headers:
            headers['Accept'] = 'application/json, text/event-stream'
        return await self.client.post(path, headers=headers, **kwargs)
    
    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> dict:
        """Call a single tool"""
        if not self.session_id:
            await self.initialize()
        
        payload = {
            "jsonrpc": "2.0",
            "id": str(int(datetime.now().timestamp() * 1000000)),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }
        
        response = await self.client.post(
            "/",
            json=payload,
            headers={
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": self.session_id
            }  # type: ignore
        )
        
        if response.status_code == 200:
            return self._parse_sse_response(response.text)
        else:
            raise Exception(f"Tool call failed: {response.status_code} - {response.text}")
    
    async def list_tools(self) -> dict:
        """List all available tools"""
        if not self.session_id:
            await self.initialize()
        
        payload = {
            "jsonrpc": "2.0",
            "id": str(int(datetime.now().timestamp() * 1000000)),
            "method": "tools/list",
            "params": {}
        }
        
        response = await self.client.post(
            "/",
            json=payload,
            headers={
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": self.session_id
            }  # type: ignore
        )
        
        if response.status_code == 200:
            # Debug: print response text for troubleshooting
            # print(f"DEBUG list_tools response text: {response.text[:200]}")
            return self._parse_sse_response(response.text)
        else:
            raise Exception(f"List tools failed: {response.status_code} - {response.text}")
    
    async def close(self):
        """Close MCP session"""
        await self.client.aclose()

@pytest.fixture(scope="function")
async def mcp_bash_client(config):
    """Async MCP client for bash server with session management"""
    client = httpx.AsyncClient(
        base_url=config['mcp_bash_url'],
        timeout=httpx.Timeout(30.0),
        follow_redirects=True
    )
    
    # Create MCP session wrapper
    mcp_client = MCPClientsession(
        base_url=config['mcp_bash_url'],
        client=client
    )
    
    # Initialize session on fixture creation
    try:
        await mcp_client.initialize()
        yield mcp_client
    finally:
        await mcp_client.close()

@pytest.fixture(scope="function")
async def mcp_project_client(config):
    """Async MCP client for project server with session management"""
    client = httpx.AsyncClient(
        base_url=config['mcp_project_url'],
        timeout=httpx.Timeout(30.0),
        follow_redirects=True
    )
    
    # Create MCP session wrapper
    mcp_client = MCPClientsession(
        base_url=config['mcp_project_url'],
        client=client
    )
    
    # Initialize session on fixture creation
    try:
        await mcp_client.initialize()
        yield mcp_client
    finally:
        await mcp_client.close()

@pytest.fixture(scope="session")
def project_root(config):
    """Путь к workspace для создания файлов (видимый ингестором)"""
    return config.get('workspace_root', config.get('test_workspace', '/workspace'))


@pytest.fixture(scope="function")
def db_engine(config):
    """Database engine for direct DB queries"""
    engine = create_engine(config['pg_url'])
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_workspace(config):
    """Create test workspace directory"""
    import os
    workspace = config['test_workspace']
    os.makedirs(workspace, exist_ok=True)
    
    # Create some test files
    test_files = [
        "test_python.py",
        "test_readme.md",
        "test_config.json"
    ]
    
    for filename in test_files:
        filepath = os.path.join(workspace, filename)
        with open(filepath, 'w') as f:
            if filename.endswith('.py'):
                f.write("# Test Python file\nprint('Hello from test!')\n")
            elif filename.endswith('.md'):
                f.write("# Test README\nThis is a test file for e2e tests.\n")
            elif filename.endswith('.json'):
                f.write('{"test": true, "value": 42}\n')
    
    return workspace

@pytest.fixture(scope="function")
async def clean_database(config):
    """Clean database before each test"""
    from sqlalchemy import create_engine

    engine = create_engine(config['pg_url'])
    dimensions = config['pgvector_dimensions']
    
    with engine.connect() as conn:
        # Create schema if not exists
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                content TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                chunk_type TEXT NOT NULL,
                summary TEXT,
                purpose TEXT,
                embedding vector({dimensions})
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path);
        """))
        conn.commit()

        # Drop tables if exist
        try:
            conn.execute(text("DROP TABLE IF EXISTS stats CASCADE"))
        except:
            pass
        try:
            conn.execute(text("DROP TABLE IF EXISTS module_summaries CASCADE"))
        except:
            pass
        try:
            conn.execute(text("DROP TABLE IF EXISTS file_summaries CASCADE"))
        except:
            pass
        try:
            conn.execute(text("DROP TABLE IF EXISTS chunks CASCADE"))
        except:
            pass
        conn.commit()

    engine.dispose()
    return True

@pytest.fixture(scope="function")
async def test_cleanup():
    """Cleanup resources after each test"""
    yield
    
    # Cleanup code here if needed
    pass

@pytest.fixture(scope="session")
def test_data():
    """Provide test data for various scenarios"""
    return {
        'simple_code': '''
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
''',
        'complex_code': '''
import asyncio
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str

class UserManager:
    def __init__(self):
        self.users: Dict[int, User] = {}
    
    async def add_user(self, user: User) -> bool:
        if user.id in self.users:
            return False
        self.users[user.id] = user
        return True
    
    async def get_user(self, user_id: int) -> User:
        return self.users.get(user_id)

async def main():
    manager = UserManager()
    user = User(id=1, name="Test", email="test@example.com")
    await manager.add_user(user)
    result = await manager.get_user(1)
    print(f"Found user: {result}")
''',
        'documentation': '''
# Project Documentation

## Overview
This project implements an advanced agent system with RAG capabilities.

## Features
- LLM integration
- Embedding engine
- Vector database storage
- MCP servers for tool execution

## API Endpoints
- `/v1/chat/completions` - Chat completion endpoint
- `/v1/embeddings` - Embedding generation endpoint
- `/ingest` - File ingestion endpoint

## Configuration
Set environment variables in `.env` file:
- `MODEL_NAME` - LLM model name
- `EMB_MODEL_NAME` - Embedding model name
''',
        'json_config': '''
{
  "project": "test-project",
  "version": "1.0.0",
  "features": ["rag", "agent", "ingestion"],
  "settings": {
    "max_tokens": 4096,
    "temperature": 0.7,
    "top_p": 0.9
  },
  "endpoints": {
    "llm": "http://localhost:8000",
    "embeddings": "http://localhost:8001",
    "postgres": "postgresql://localhost:5432"
  }
}
''',
        'user_query': '''
I need to search for information about Python async programming and how to implement a file ingestion system.
Can you also explain how to use the embedding model for semantic search?
'''
    }

# Health check fixture
@pytest.fixture(scope="session")
async def health_check(config):
    """Check that all services are healthy before running tests"""
    services = [
        ('LLM', config['llm_url']),
        ('Embedding', config['emb_url']),
        ('Ingestor', config['ingestor_url']),
        ('LangGraph', config['langgraph_url']),
        ('MCP Bash', config['mcp_bash_url']),
        ('MCP Project', config['mcp_project_url'])
    ]
    
    for name, base_url in services:
        try:
            # Remove /v1 or /mcp from URL for health check
            response = requests.get(base_url, timeout=Timeouts.STANDARD)
            if response.status_code != 200:
                logger.warning(f"{name} health check returned {response.status_code}")
        except Exception as e:
            logger.error(f"Failed health check for {name}: {e}")
            raise
    
    logger.info("All services are healthy")
    return True

# Custom markers
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests for complete workflows"
    )
    config.addinivalue_line(
        "markers", "component: Component-level tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests between components"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take more than 30 seconds"
    )
    config.addinivalue_line(
        "markers", "requires_gpu: Tests that require GPU resources"
    )
    config.addinivalue_line(
        "markers", "requires_model: Tests that require specific models"
    )