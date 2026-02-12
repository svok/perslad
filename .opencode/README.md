# OpenCode Configuration for Perslad

## Overview

This directory contains OpenCode skills configuration for the Perslad project - an AI-powered autonomous development
system.

## Directory Structure

```
.opencode/
├── skills/                    # Skills for AI agents
│   ├── perslad/              # Core development skills
│   ├── ingestor/             # RAG and indexing skills
│   ├── infra/                # Infrastructure skills
│   ├── agents/               # Agent integration skills
│   ├── database/             # Database skills
│   ├── testing/              # Testing skills
│   ├── devops/               # DevOps skills
│   └── docs/                 # Documentation skills
├── skills.yaml               # Skills configuration
├── AGENTS.md                 # Development rules
├── workspace/                # Development workspace
├── plans/                    # Task plans
└── README.md                 # This file
```

## Quick Start

### 1. Review Development Rules

```bash
cat .opencode/AGENTS.md
```

### 2. Check Skills Configuration

```bash
cat .opencode/skills.yaml
```

### 3. Start Development

```bash
# Start Docker Compose services
docker-compose up -d

# Check service status
python -c "from skills.devops.docker import check_docker_status; print(check_docker_status())"
```

### 4. Use Skills

```python
from skills.ingestor.inotify import setup_incremental_mode
from pathlib import Path

config = setup_incremental_mode(
    watch_paths=[Path("/workspace")],
    recursive=True
)
```

## Available Skills

### Priority 1 (Current Tasks)

1. **INotify Incremental Mode** (`ingestor/inotify.py`)
    - File system event handling
    - Incremental indexing
    - Batch processing

2. **Infrastructure Unification** (`infra/unification.py`)
    - Component analysis
    - Shared pattern identification
    - Migration planning

3. **External Tools Integration** (`agents/external_tools.py`)
    - opencode integration
    - Continue extension integration
    - MCP tool configuration

### Priority 2 (Future Tasks)

4. **Fact Graph Building** (`ingestor/graph_builder.py`)
    - RDF/OWL ontology
    - Knowledge graph construction
    - Graph queries

5. **Database Table Filling** (`ingestor/db_filling.py`)
    - ETL processes
    - Data validation
    - Index optimization

6. **Multi-Database Storage** (`database/multi_storage.py`)
    - PostgreSQL adapter
    - StarRocks adapter
    - NebulaGraph adapter

### Supporting Skills

7. **Docker Management** (`devops/docker.py`)
8. **Integration Testing** (`testing/integration.py`)
9. **Documentation** (`docs/generator.py` - planned)

## Development Workflow

### For OpenCode Agents

1. **Analyze** the current task using available skills
2. **Plan** implementation using planning skills
3. **Implement** using specific skill functions
4. **Test** using testing skills
5. **Document** using documentation skills

### Example Workflow

```python
# 1. Analyze current state
from skills.ingestor.inotify import check_inotify_status

status = check_inotify_status(config)

# 2. Implement solution
from skills.ingestor.inotify import setup_incremental_mode

config = setup_incremental_mode(watch_paths=[...])

# 3. Test implementation
from skills.testing.integration import run_unit_tests

results = run_unit_tests("inotify")

# 4. Document changes
from skills.docs.generator import update_skill_documentation

update_skill_documentation("inotify", changes)
```

## Configuration

### Skills Configuration (skills.yaml)

- Available skills and their priorities
- Test configuration
- Integration settings
- Quality gates

### Development Rules (AGENTS.md)

- Code quality standards
- Architecture principles
- Docker workflow
- Security guidelines

### Environment Configuration (.env)

- Model configuration
- Database connection strings
- Service endpoints
- Security settings

## Testing

### Run All Tests

```bash
# Run all skill tests
pytest .opencode/skills/ -v

# Run specific skill tests
pytest .opencode/skills/ingestor/tests/ -v
pytest .opencode/skills/infra/tests/ -v
pytest .opencode/skills/agents/tests/ -v
```

### Test Coverage

```bash
# Run with coverage
pytest --cov=.opencode/skills/ .opencode/skills/

# Generate coverage report
pytest --cov-report=html .opencode/skills/
```

## Docker Compose Services

| Service         | Port | Description              |
|-----------------|------|--------------------------|
| llm-engine      | 8000 | LLM inference engine     |
| emb-engine      | 8001 | Embedding model engine   |
| langgraph-agent | 8123 | LangGraph orchestration  |
| ingestor        | 8124 | RAG engine               |
| mcp-bash        | 8081 | Shell tool               |
| mcp-sql         | 8082 | SQL tool                 |
| mcp-project     | 8083 | Project navigation       |
| postgres        | 5432 | PostgreSQL with pgvector |

### Check Service Health

```bash
# Health endpoints
curl http://localhost:8123/health
curl http://localhost:8124/health
```

## Current Status

### Completed

- ✅ Skills directory structure created
- ✅ Core skills implemented (Priority 1)
- ✅ Supporting skills added
- ✅ Tests created for core skills
- ✅ AGENTS.md with development rules
- ✅ skills.yaml configuration

### In Progress

- 🔄 Comprehensive test coverage
- 🔄 Documentation for all skills
- 🔄 Integration tests for all components
- 🔄 Performance tests

### Planned

- 📋 CI/CD pipeline configuration
- 📋 Monitoring and logging setup
- 📋 Example usage scripts
- 📋 API documentation

## Project Information

**Project**: Perslad - Personal Local Assistant for Developer
**Status**: Active Development
**Architecture**: Multi-Agent + RAG + MCP
**Deployment**: Docker Compose
**Local Models**: Qwen2.5-7B-Instruct-AWQ, Llama, DeepSeek

## Support

- **Documentation**: Check `.opencode/skills/README.md` for detailed skill documentation
- **Issues**: https://github.com/svok/perslad/issues
- **Discussions**: https://github.com/svok/perslad/discussions

## Next Steps

1. Complete Priority 2 skills implementation
2. Add comprehensive test coverage
3. Create example usage documentation
4. Set up monitoring and logging
5. Consider CI/CD pipeline for future development

---

**Last Updated**: 2026-02-12
**Version**: 1.0
**Maintainer**: Single Developer (current)