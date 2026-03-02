# AGENTS.md - Guidelines for AI Agents Working on Perslad Project

## Overview
Perslad is an AI-powered autonomous development system based on local LLMs, using LangGraph for multi-agent orchestration, RAG for knowledge storage, and MCP tools for extensibility.

## Development Commands
### Docker Workflow
```bash
# Start all services
docker compose up -d

# View logs for a service
docker compose logs -f <service_name>

# Rebuild a specific service
docker compose up -d --build <service_name>

# Stop all services
docker compose down
```

### Testing
```bash
# Run all tests for a service
docker compose exec <service> pytest /app/tests -v

# Run a single test file
docker compose exec <service> pytest /app/tests/unit/test_chunker.py -v

# Run a single test function
docker compose exec <service> pytest /app/tests/unit/test_chunker.py::test_chunk_document -v

# Run tests with coverage
docker compose exec <service> pytest /app/tests --cov=app --cov-report=html
```

### Code Quality
```bash
# Lint code with ruff
docker compose exec <service> ruff check .

# Format code with ruff
docker compose exec <service> ruff format .

# Type check with mypy
docker compose exec <service> mypy .
```

### Database
```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U rag -d rag
```

## Code Style Guidelines
### Type Hints
- Required everywhere for functions, parameters, and returns
- Use Python 3.12+ built-in generics: `list[str]`, `dict[str, int]`
- Use union syntax: `str | None` instead of `Optional[str]`
- Only use `typing` module for `Protocol`, `TypeVar`, `Generic`, `Final`, `Literal`
- Prohibit `Any` without explicit justification
- Use `dataclasses` for data structures, `StrEnum` for constants

### Naming Conventions
- `snake_case`: variables, functions, modules, files, directories
- `CamelCase`: classes
- `UPPER_CASE`: constants and Enum members

### Documentation
- Google-style docstrings for all public functions/classes/modules
- Include Args, Returns, Raises, and examples for non-trivial code

### Error Handling
- Use base `PersladError` in `infra/exceptions.py` for all project errors
- Follow standard error response format with status, error_type, message, and correlation_id
- Never expose sensitive information in error messages

## Architecture Guidelines
- Follow SOLID principles
- Keep files under 150 lines (excluding imports/comments)
- Each class in its own file
- Use LangGraph with TypedDict for state management
- Organize code into `agents/`, `ingestor/`, `infra/`, `servers/` directories

## Testing Strategy
- Unit tests: mock external dependencies, test individual functions
- Integration tests: test component interactions with test DB
- End-to-end tests: test full workflows in Docker environment
- Minimum 80% test coverage for critical components

## Version Control
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`
- Branch naming: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- No direct commits to main - use PRs
