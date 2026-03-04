# AGENTS.md - Rules for OpenCode Agents in Perslad Project

## Overview

This file contains rules and guidelines for AI agents (OpenCode) working on the Perslad project - an AI-powered autonomous development system based on local LLMs.

**Key Terms**:
- **MCP**: Model Context Protocol - standard for extending LLM capabilities with tools
- **RAG**: Retrieval-Augmented Generation - architecture combining LLM with knowledge retrieval
- **LangGraph**: Framework for building stateful, multi-agent applications with LLMs

## Project Context

**Perslad**: Personal Local Assistant for Developer

- AI-powered autonomous development system
- Runs on local models (Qwen, Llama, DeepSeek)
- Multi-agent architecture with LangGraph
- RAG-powered knowledge storage with both SQL and graph DB
- MCP (Model Context Protocol) tools for extensibility

## Development Rules

### 1. Code Quality Standards

#### File Size

- **Maximum 150 lines per file** (excluding imports and comments)
- Each class must be in its own separate file
- Functions must be kept short and focused

#### Type Hints

- **Required everywhere** - all functions, parameters, and return types
- Use Python 3.12+ built-in generic types: `dict`, `list`, `set`, `tuple`
- Use union syntax: `str | None` instead of `Optional[str]`
- Use `typing` module only for: `Protocol`, `TypeVar`, `Generic`, `Final`, `Literal`
- **PROHIBITED**: Using `Any` without explicit justification comment
- Use `dataclasses` for data structures
- Use `Enum` or `StrEnum` for enumerations

**Examples**:
```python
# CORRECT
def process_items(items: list[str]) -> dict[str, int | None]: ...

# WRONG
def process_items(items: List[Any]) -> Dict[str, Optional[int]]: ...
```

#### Constants

- **Use `enum.StrEnum`** for grouped related constants (endpoints, modes, statuses)
- **Use module-level constants** with `Final` type hint for single values
- **PROHIBITED**: Using dictionaries for constants (e.g., `ENDPOINTS = {"key": "value"}`)
- **PROHIBITED**: Using dataclasses for constants (creates unnecessary overhead)

**CORRECT**:
```python
from enum import StrEnum
from typing import Final

class LLMEndpoint(StrEnum):
    MODELS = "/v1/models"
    CHAT_COMPLETIONS = "/v1/chat/completions"

MAX_RETRIES: Final[int] = 3
DEFAULT_TEMPERATURE: Final[float] = 0.1
```

**WRONG**:
```python
# PROHIBITED - dict constants
ENDPOINTS = {
    "models": "/v1/models",
    "chat_completions": "/v1/chat/completions",
}

# PROHIBITED - dataclass for constants
from dataclasses import dataclass

@dataclass
class LLM:
    MODELS: str = "/v1/models"
```

#### Naming Conventions

- **snake_case** for variables, functions, modules, and file names
- **CamelCase** for classes
- **UPPER_CASE** for constants and Enum members
- **snake_case** for package directories

**Examples**:
```python
# File: external_tools.py (NOT external-tools.py)
# Class: class DocumentProcessor:
# Function: def process_document():
# Constant: MAX_CHUNK_SIZE: Final[int] = 512
```

#### Documentation

- **Complete docstrings** for all public functions, classes, and modules
- Follow Google style: Args, Returns, Raises, Examples
- Include type information in docstrings only for complex types
- Example usage in function docstrings for non-obvious cases

**Example**:
```python
def retrieve_context(query: str, top_k: int = 5) -> list[ContextChunk]:
    """Retrieve relevant context chunks for a query.
    
    Args:
        query: Search query text
        top_k: Number of chunks to retrieve (default: 5)
        
    Returns:
        List of context chunks sorted by relevance score
        
    Raises:
        ValueError: If query is empty or top_k <= 0
        
    Example:
        >>> chunks = retrieve_context("Python async", top_k=3)
        >>> print(chunks[0].content)
    """
```

### 2. Architecture Principles

#### SOLID Principles

- **Single Responsibility**: One class/function does one thing
- **Open/Closed**: Open for extension, closed for modification
- **Liskov Substitution**: Base classes replaceable by derived classes
- **Interface Segregation**: No client depends on interfaces it doesn't use
- **Dependency Inversion**: Depend on abstractions, not concretions

#### Design Patterns

- **DRY** (Don't Repeat Yourself)
- **KISS** (Keep It Short and Simple)
- **YAGNI** (You Aren't Gonna Need It)
- **Separation of Concerns**

### 3. Docker & Development Environment

#### Docker Compose Workflow

- **All development MUST be in Docker containers**
- No local installations (Python, Node, etc.) for production code
- Use `.env` for configuration
- Services run on specific ports:
  - LLM Engine: 8000
  - Emb Engine: 8001
  - LangGraph Agent: 8123
  - Ingestor: 8124
  - MCP Servers: 8081 (bash), 8082 (sql), 8083 (project)

#### Local Development Exception

Local Python 3.12+ installation allowed ONLY for:
- IDE type checking and autocomplete
- Running linters (ruff, mypy) locally for faster feedback
- Unit tests debugging with breakpoints
- **NEVER** for running production services or integration tests

#### Environment Management

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f <service_name>

# Rebuild specific service
docker compose up -d --build <service_name>

# Stop all services
docker compose down

# Run tests in container
docker compose exec ingestor pytest /app/tests -v
```

### 4. Security Guidelines

#### Local Models Only

- **Default to local LLM models** (Qwen2.5-7B-Instruct-AWQ, etc.)
- Use cloud models only for complex queries (explicit approval needed)
- Never expose API keys in code
- Use environment variables for configuration

#### Sandbox Execution

- **Sandbox external tools** using Docker
- Validate all commands before execution
- Implement resource limits (CPU, memory, duration)
- Use read-only permissions where possible

#### Data Privacy

- **All data stays local** (no external transmission)
- Encrypt sensitive data at rest
- Validate and sanitize all inputs
- Log all operations for audit trail

### 5. Component Architecture

#### Component Structure

```
perslad/
├── agents/              # LangGraph agent orchestration
│   ├── core/            # Core agent logic and state management
│   ├── nodes/           # Individual LangGraph nodes
│   ├── edges/           # Edge conditions and routing
│   ├── tools/           # Agent-specific tools
│   └── main.py          # FastAPI entry point
├── ingestor/            # RAG engine and indexing
│   ├── chunkers/        # Text chunking strategies
│   ├── embedders/       # Embedding model adapters
│   ├── retrievers/      # Retrieval strategies
│   ├── services/        # Business logic
│   ├── adapters/        # Database adapters
│   └── main.py          # FastAPI entry point
├── infra/               # Shared infrastructure
│   ├── llm/             # LLM client abstractions
│   ├── database/        # Database connection management
│   ├── logging/         # Structured logging configuration
│   └── observability/   # Metrics and tracing
├── servers/             # MCP servers
│   ├── mcp_bash.py      # Shell tool
│   ├── mcp_sql.py       # Database tool
│   └── mcp_project.py   # Project navigation
└── workspace/           # Development workspace
```

#### Component Rules

1. **infra/** - Shared infrastructure (LLM clients, database connections, logging, observability)
2. **agents/** - Agent orchestration, state management, and business logic
3. **ingestor/** - RAG pipeline: chunking, embedding, retrieval, knowledge graphs
4. **servers/** - MCP tool implementations exposing capabilities to agents

### 6. LangGraph Standards

#### State Management

- **Use TypedDict** for state definition with `total=False` for optional fields
- **Single state class per workflow** in `agents/core/state.py`
- **Immutable state updates** - always return new state, never modify in place

**Example**:
```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    context: list[ContextChunk]
    next_node: str | None
    error_count: int
```

#### Node Naming Conventions

- **Format**: `verb_noun` or `action_target`
- **Examples**: `retrieve_context`, `generate_response`, `validate_input`, `check_completion`
- **File naming**: Match node name with `.py` extension in `agents/nodes/`

#### Edge Naming Conventions

- **Conditional edges**: `should_<action>`, `is_<condition>`, `has_<state>`
- **Examples**: `should_continue`, `is_complete`, `has_error`, `needs_clarification`
- **Return values**: Use `StrEnum` for routing decisions

```python
class Route(StrEnum):
    CONTINUE = "continue"
    END = "end"
    CLARIFY = "clarify"

def should_continue(state: AgentState) -> Route:
    if state.get("error_count", 0) > 3:
        return Route.END
    return Route.CONTINUE
```

#### Graph Construction

- **Define graph in `agents/core/graph.py`**
- **Use constants for node names** to avoid string typos
- **Always set entry point explicitly**
- **Compile graph once** at module level or in lifespan handler

```python
from langgraph.graph import StateGraph, END

class NodeName(StrEnum):
    RETRIEVE = "retrieve_context"
    GENERATE = "generate_response"

def build_graph() -> CompiledGraph:
    workflow = StateGraph(AgentState)
    
    workflow.add_node(NodeName.RETRIEVE, retrieve_context)
    workflow.add_node(NodeName.GENERATE, generate_response)
    
    workflow.set_entry_point(NodeName.RETRIEVE)
    workflow.add_edge(NodeName.RETRIEVE, NodeName.GENERATE)
    workflow.add_conditional_edges(
        NodeName.GENERATE,
        should_continue,
        {Route.CONTINUE: NodeName.RETRIEVE, Route.END: END}
    )
    
    return workflow.compile()
```

#### Interrupts and Human-in-the-Loop

- **Use `interrupt` function** for human approval points
- **Document all interrupt points** in node docstrings
- **Implement timeout handling** for interrupts
- **Store interrupt state** in checkpoint for recovery

### 7. RAG Standards (Ingestor)

#### Chunking Strategies

- **Default**: Recursive character splitting with overlap
- **Configure via constants**:
```python
class ChunkingConfig:
    CHUNK_SIZE: Final[int] = 512
    CHUNK_OVERLAP: Final[int] = 50
    SEPARATORS: Final[list[str]] = ["\n\n", "\n", ". ", " ", ""]
```

#### Embedding Models

- **Default**: Local embedding model (BGE-small-en-v1.5 or similar)
- **Dimension**: 384 or 768 (must match pgvector column)
- **Batch size**: 32-64 for optimal throughput
- **Cache embeddings** for duplicate content

#### Retrieval Strategies

1. **Similarity Search**: Default for most queries
2. **MMR (Maximal Marginal Relevance)**: For diverse results
3. **Hybrid Search**: Combine vector + keyword (if implemented)
4. **Reranking**: Cross-encoder for top-100 chunks

#### Prompt Templates

- **Store in `ingestor/prompts/`** as `.txt` or `.j2` files
- **Version control prompts** separately from code
- **Use Jinja2** for dynamic content
- **Include context formatting** instructions

### 8. Integration Standards

#### MCP (Model Context Protocol)

- Tools expose capabilities to LangGraph agents
- Each tool is a separate MCP server
- Standard interface: `execute_command(command: str, args: dict) -> dict`
- Return structured responses with status and data

**Response format**:
```json
{
    "status": "success" | "error",
    "data": {...},
    "error": null | {"type": "...", "message": "..."},
    "metadata": {"execution_time_ms": 123}
}
```

#### External Tools Integration

- **OpenCode**: Integrate via MCP tools (bash, project, sql)
- **Continue**: Configure as OpenAI-compatible endpoint
- **Other IDEs**: Use MCP or REST API

#### OpenAPI/REST API

- All services expose REST APIs
- Use FastAPI for Python services
- Document endpoints with OpenAPI specs
- Use consistent error responses

### 9. Database & Storage

#### PostgreSQL with pgvector

- Primary storage for RAG (vector embeddings)
- Connection: `postgresql://rag:rag@postgres:5432/rag`
- Tables:
  - `documents` - Document metadata
  - `chunks` - Text chunks with embeddings (vector(384) or vector(768))
  - `relationships` - Document relationships
  - `facts` - Extracted facts (graph nodes)
  - `edges` - Fact relationships (graph edges)

#### Multi-Database Support

- **PostgreSQL**: Primary RAG storage
- **StarRocks**: Analytics and queries
- **NebulaGraph**: Graph relationships
- **Adapter Pattern**: Unified interface in `infra/database/adapters/`

### 10. Configuration Management

#### Pydantic Settings

- **Use `pydantic-settings`** for all configuration
- **Environment prefix** per component: `PERSLAD_AGENTS_`, `PERSLAD_INGESTOR_`
- **Secrets handling**: Use `SecretStr` for API keys
- **Validation**: Validate on startup, fail fast

**Example**:
```python
from pydantic_settings import BaseSettings
from pydantic import SecretStr, Field

class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PERSLAD_LLM_")
    
    base_url: str = "http://localhost:8000"
    api_key: SecretStr = Field(default=SecretStr("dummy"))
    timeout: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
```

#### Configuration Hierarchy

1. Default values in code
2. `.env` file (gitignored, per environment)
3. Environment variables (highest priority)

### 11. Observability and Logging

#### Structured Logging

- **Use `structlog`** for JSON-formatted logs
- **Correlation ID**: Propagate `x-correlation-id` header through all services
- **Log levels**:
  - DEBUG: Detailed debugging (disabled in production)
  - INFO: Standard operations
  - WARNING: Recoverable issues
  - ERROR: Failures requiring attention

**Example**:
```python
import structlog

logger = structlog.get_logger()

def process_request(request_id: str) -> None:
    logger.info(
        "processing_request",
        request_id=request_id,
        component="ingestor",
        operation="chunk_document"
    )
```

#### Tracing

- **LangSmith integration** (optional, configurable)
- **OpenTelemetry** for distributed tracing
- **Trace IDs** in all log entries
- **Span naming**: `<component>.<operation>` (e.g., `ingestor.chunk_document`)

#### Metrics

- **Prometheus metrics** exposed on `/metrics`
- **Key metrics**:
  - Request latency (histogram)
  - LLM token usage (counter)
  - RAG retrieval time (histogram)
  - Error rates (counter)

### 12. Testing Strategy

#### Test Types

1. **Unit Tests**: Test individual functions/classes (mock external deps)
2. **Integration Tests**: Test component interactions (with test DB)
3. **End-to-End Tests**: Test full workflow (Docker environment)
4. **Performance Tests**: Test LLM and RAG performance

#### Test Structure

```
perslad/
├── agents/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── conftest.py
├── ingestor/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── conftest.py
```

#### Test Coverage

- **Minimum 80% coverage** for critical components
- **Integration tests** for all MCP tools
- **Mock LLM responses** for predictable testing
- **Docker-based test environments** for E2E tests

#### Test Commands

```bash
# Run all tests in container
docker compose exec agents pytest /app/tests -v

# Run specific test file
docker compose exec ingestor pytest /app/tests/unit/test_chunker.py -v

# With coverage
docker compose exec agents pytest /app/tests --cov=app --cov-report=html
```

### 13. Documentation Standards

#### Required Documentation

1. **README.md**: Project overview and quick start
2. **API Documentation**: OpenAPI specs for all endpoints
3. **Component README**: Each component has README.md
4. **Architecture Decision Records (ADRs)**: In `docs/adr/`
5. **Example Usage**: Code examples and tutorials

#### Documentation Format

- **Markdown** for all documentation
- **Mermaid** for diagrams
- **Code examples** in fenced blocks with language tags
- **Link to related documentation**

### 14. Task Management

#### Task Breakdown

1. **Analyze**: Understand requirements and constraints
2. **Plan**: Create implementation plan
3. **Implement**: Write code following standards
4. **Test**: Verify functionality
5. **Document**: Create/update documentation
6. **Review**: Self-review against this checklist

#### Definition of Done

- [ ] Code follows style guidelines (ruff, black, mypy pass)
- [ ] Tests written and passing (unit + integration)
- [ ] Documentation updated
- [ ] No secrets in code
- [ ] Docker compose works: `docker compose up -d`
- [ ] Logs are structured and informative
- [ ] Error handling follows standards

### 15. Error Handling

#### Error Types

- **Validation Errors**: User input validation (400)
- **Runtime Errors**: System errors during execution (500)
- **Integration Errors**: External service failures (503)
- **Configuration Errors**: Invalid configuration (500 on startup)

#### Error Response Format

```json
{
    "status": "error",
    "error_type": "validation",
    "message": "Description of error",
    "details": {"field": "specific issue"},
    "suggestion": "How to fix",
    "correlation_id": "uuid-for-tracing"
}
```

#### Exception Hierarchy

```python
# infra/exceptions.py
class PersladError(Exception):
    """Base exception for all project errors."""
    def __init__(self, message: str, correlation_id: str | None = None): ...

class ValidationError(PersladError): ...
class IntegrationError(PersladError): ...
class ConfigurationError(PersladError): ...
```

### 16. Performance Guidelines

#### LLM Performance

- **Context Window**: Monitor token usage, trim history when needed
- **Temperature**: Use 0.1 for deterministic responses, 0.7 for creative
- **Batch Processing**: Group similar operations
- **Caching**: Cache frequent queries (Redis or in-memory with TTL)

#### Database Performance

- **Indexing**: Use appropriate indexes (GIN for full-text, ivfflat for vectors)
- **Query Optimization**: Avoid N+1 queries, use joins
- **Connection Pooling**: Reuse database connections (asyncpg pool)
- **Vector Search**: Use `pgvector` with `ivfflat` or `hnsw` indexes

### 17. Version Control

#### Git Workflow

- **Main branch**: Stable releases, protected
- **Feature branches**: `feature/<description>` (e.g., `feature/add-mcp-sql-tool`)
- **Commit messages**: Conventional Commits format
  - `feat: add INotify incremental mode`
  - `fix: resolve race condition in chunker`
  - `refactor: split ingestor into services`
  - `docs: update API examples`
- **No direct commits to main** - PR required with self-review

#### Branch Naming

- `feature/<feature-name>` - New features
- `fix/<bug-description>` - Bug fixes
- `refactor/<component>` - Code refactoring
- `docs/<documentation>` - Documentation updates
- `chore/<maintenance>` - Dependency updates, tooling

### 18. Development Environment

#### Required Tools

- **Docker** (version 24+)
- **Docker Compose** (version 2.20+)
- **Git** (version 2.40+)
- **Make** (for convenience commands)

#### IDE Configuration

- **VS Code**: Use Python extension, enable strict type checking
- **PyCharm**: Enable Python inspections, configure Docker interpreter
- **Ruff**: Enable as default linter/formatter
- **Mypy**: Strict mode enabled

#### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
```

### 19. Security Checklist

#### Before Committing

- [ ] No secrets or API keys in code (use `git-secrets` or similar)
- [ ] All paths use environment variables or Path configuration
- [ ] Input validation implemented for all external inputs
- [ ] Error messages don't leak sensitive info (no stack traces to user)
- [ ] Sandbox execution for external commands (Docker or restricted env)

#### For External Integrations

- [ ] Rate limiting implemented (slowapi or nginx)
- [ ] API key rotation configured (if cloud LLM used)
- [ ] Audit logging enabled for sensitive operations
- [ ] Permission boundaries enforced (file system access)
- [ ] Data encryption configured for sensitive data at rest

## Quick Reference

### Common Commands

```bash
# Development
docker compose up -d
docker compose logs -f <service>

# Testing
docker compose exec <service> pytest /app/tests -v

# Code Quality
docker compose exec <service> ruff check .
docker compose exec <service> ruff format .
docker compose exec <service> mypy .

# Database
docker compose exec postgres psql -U rag -d rag
```

### Key Endpoints

- **LangGraph Agent**: http://localhost:8123
- **LLM Engine**: http://localhost:8000
- **Ingestor**: http://localhost:8124
- **MCP Bash**: http://localhost:8081
- **MCP SQL**: http://localhost:8082
- **MCP Project**: http://localhost:8083

### Configuration Files

- `.env`: Environment variables (copy from `.env.example`)
- `docker-compose.yml`: Service definitions
- `pyproject.toml`: Python dependencies and tool config
- `AGENTS.md`: This file

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-12 | Initial version |
| 1.1 | 2026-02-23 | Fixed constants rule (dataclass→Enum), added LangGraph/RAG standards, added observability section, fixed naming conventions |

## Contact & Support

- **GitHub Issues**: https://github.com/svok/perslad/issues
- **Discussions**: https://github.com/svok/perslad/discussions
- **Documentation**: Check project README.md

---

**Last Updated**: 2026-02-23
**Version**: 1.1
**Maintainer**: Single Developer (current)
