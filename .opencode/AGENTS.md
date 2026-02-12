# AGENTS.md - Rules for OpenCode Agents in Perslad Project

## Overview

This file contains rules and guidelines for AI agents (OpenCode) working on the Perslad project - an AI-powered
autonomous development system based on local LLMs.

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
- Use `typing` module: `Dict`, `List`, `Optional`, `Any`
- Use `dataclasses` for data structures
- Use `Enum` for enumerations

#### Naming Conventions

- **snake_case** for variables and functions
- **CamelCase** for classes
- **UPPER_CASE** for constants
- **kebab-case** for file names (e.g., `external-tools.py`)

#### Documentation

- **Complete docstrings** for all public functions
- Follow Google style: Args, Returns, Raises
- Include type information in docstrings
- Example usage in function docstrings

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

- **All development in Docker containers**
- No local installations (Python, Node, etc.)
- Use `.env` for configuration
- Services run on specific ports:
    - LLM Engine: 8000
    - Emb Engine: 8001
    - LangGraph Agent: 8123
    - Ingestor: 8124
    - MCP Servers: 8081 (bash), 8082 (sql), 8083 (project)

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
├── agents/           # LangGraph agent orchestration
│   ├── app/          # Application logic
│   └── main.py       # FastAPI entry point
├── ingestor/         # RAG engine and indexing
│   ├── services/     # Business logic
│   └── adapters/     # Database adapters
│   └── main.py       # FastAPI entry point
├── infra/            # Shared infrastructure
│   ├── managers      # Various managers
│   └── *             # To be refactored
├── servers/          # MCP servers
│   ├── mcp_bash.py   # Shell tool
│   ├── mcp_sql.py    # Database tool
│   └── mcp_project.py # Project navigation
└── workspace/        # Development workspace
```

#### Component Rules

1. **infra/** - Shared infrastructure (LLM, HTTP, logging)
2. **agents/** - Agent orchestration and business logic
3. **ingestor/** - RAG, knowledge graphs and indexing pipeline
4. **servers/** - MCP tool implementations

### 6. Integration Standards

#### MCP (Model Context Protocol)

- Tools expose capabilities to LangGraph agents
- Each tool is a separate MCP server
- Standard interface: `execute_command(command, args)`
- Return structured responses with status and data

#### External Tools Integration

- **opencode**: Integrate via MCP tools (bash, project, sql)
- **Continue**: Configure as OpenAI-compatible endpoint
- **Other IDEs**: Use MCP or REST API

#### OpenAPI/REST API

- All services expose REST APIs
- Use FastAPI for Python services
- Document endpoints with OpenAPI specs
- Use consistent error responses

### 7. Database & Storage

#### PostgreSQL with pgvector

- Primary storage for RAG (vector embeddings)
- Connection: `postgresql://rag:rag@postgres:5432/rag`
- Tables:
    - `documents` - Document metadata
    - `chunks` - Text chunks with embeddings
    - `relationships` - Document relationships
    - `facts` - Extracted facts (graph nodes)
    - `edges` - Fact relationships (graph edges)

#### Multi-Database Support

- **PostgreSQL**: Primary RAG storage
- **StarRocks**: Analytics and queries
- **NebulaGraph**: Graph relationships
- **Adapter Pattern**: Unified interface

### 8. Testing Strategy

#### Test Types

1. **Unit Tests**: Test individual functions/classes
2. **Integration Tests**: Test component interactions
3. **End-to-End Tests**: Test full workflow
4. **Performance Tests**: Test LLM and RAG performance

#### Test Coverage

- **Minimum 80% coverage** for critical components
- **Integration tests** for all MCP tools
- **Mock LLM responses** for predictable testing
- **Docker-based test environments**

#### Test Commands

```bash
# Run all tests
pytest .opencode/skills/ -v

# Run specific skill tests
pytest .opencode/skills/ingestor/tests/ -v

# Integration tests
pytest .opencode/skills/testing/integration/ -v
```

### 9. Documentation Standards

#### Required Documentation

1. **README.md**: Project overview and quick start
2. **API Documentation**: OpenAPI specs for all endpoints
3. **Skill Documentation**: Each skill has README.md
4. **Architecture Diagrams**: Mermaid diagrams in docs
5. **Example Usage**: Code examples and tutorials

#### Documentation Format

- **Markdown** for all documentation
- **Mermaid** for diagrams
- **Code examples** in fenced blocks
- **Link to related documentation**

### 10. Task Management

#### Task Breakdown

1. **Analyze**: Understand requirements and constraints
2. **Plan**: Create implementation plan
3. **Implement**: Write code following standards
4. **Test**: Verify functionality
5. **Document**: Create/update documentation
6. **Review**: Self-review and improvements

#### Priority Order

1. **Critical**: System breaking issues
2. **High**: Feature implementation
3. **Medium**: Improvements and refactoring
4. **Low**: Documentation and nice-to-haves

### 11. Error Handling

#### Error Types

- **Validation Errors**: User input validation
- **Runtime Errors**: System errors during execution
- **Integration Errors**: External service failures
- **Configuration Errors**: Invalid configuration

#### Error Response Format

```python
{
    "status": "error",
    "error_type": "validation",
    "message": "Description of error",
    "details": {...},
    "suggestion": "How to fix"
}
```

### 12. Performance Guidelines

#### LLM Performance

- **Context Window**: Monitor token usage
- **Temperature**: Use 0.1 for deterministic responses
- **Batch Processing**: Group similar operations
- **Caching**: Cache frequent queries

#### Database Performance

- **Indexing**: Use appropriate indexes
- **Query Optimization**: Avoid N+1 queries
- **Connection Pooling**: Reuse database connections
- **Vector Search**: Optimize pgvector queries

### 13. Version Control

#### Git Workflow

- **Main branch**: Stable releases
- **Feature branches**: `feature/<description>`
- **Commit messages**: `type: description` (e.g., `feat: add INotify incremental mode`)
- **No direct commits to main** without review

#### Branch Naming

- `feature/<feature-name>` - New features
- `fix/<bug-description>` - Bug fixes
- `refactor/<component>` - Code refactoring
- `docs/<documentation>` - Documentation updates

### 14. Development Environment

#### Required Tools

- **Docker** (version 20+)
- **Docker Compose** (version 2+)
- **Git** (for version control)
- **Python 3.12+** (if running locally for debugging)

#### IDE Configuration

- **VS Code**: Use Python extension with type checking
- **PyCharm**: Enable Python inspections
- **IntelliJ IDEA**: Configure Python SDK

### 15. Security Checklist

#### Before Committing

- [ ] No secrets or API keys in code
- [ ] All paths use environment variables
- [ ] Input validation implemented
- [ ] Error messages don't leak sensitive info
- [ ] Sandbox execution for external commands

#### For External Integrations

- [ ] Rate limiting implemented
- [ ] API key rotation configured
- [ ] Audit logging enabled
- [ ] Permission boundaries enforced
- [ ] Data encryption configured

## Quick Reference

### Common Commands

```bash
# Development
docker compose up -d
docker compose logs -f <service>

# Testing
pytest .opencode/skills/ -v

# Code Quality
ruff check .
black .
mypy .

# Documentation
mkdocs serve  # if using MkDocs
```

### Key Endpoints

- **LangGraph Agent**: http://localhost:8123
- **LLM Engine**: http://localhost:8000
- **Ingestor**: http://localhost:8124
- **MCP Bash**: http://localhost:8081
- **MCP SQL**: http://localhost:8082
- **MCP Project**: http://localhost:8083

### Configuration Files

- `.env`: Environment variables
- `docker-compose.yml`: Service definitions
- `.opencode/skills.yaml`: Skills configuration
- `.opencode/AGENTS.md`: This file

## Contact & Support

- **GitHub Issues**: https://github.com/svok/perslad/issues
- **Discussions**: https://github.com/svok/perslad/discussions
- **Documentation**: Check project README.md

---

**Last Updated**: 2026-02-12
**Version**: 1.0
**Maintainer**: Single Developer (current)