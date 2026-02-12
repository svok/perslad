# OpenCode Skills for Perslad Project

## Overview

This directory contains skills for OpenCode AI agents working on the Perslad project - an AI-powered autonomous development system.

## Project Structure

```
.opencode/
├── skills/                    # Skills directory
│   ├── perslad/              # Core Perslad development skills
│   ├── ingestor/             # RAG engine and indexing skills
│   ├── infra/                # Infrastructure unification skills
│   ├── agents/               # Agent integration skills
│   ├── database/             # Multi-database storage skills
│   ├── testing/              # Testing and QA skills
│   ├── devops/               # Docker and deployment skills
│   └── docs/                 # Documentation skills
├── skills.yaml               # Skills configuration
├── AGENTS.md                 # Development rules
├── workspace/                # Development workspace
└── plans/                    # Task plans
```

## Available Skills

### Priority 1 (Current Tasks)

#### 1. INotify Incremental Mode (`ingestor/inotify.py`)
**Purpose**: Handle file system events and incremental updates for ingestor

**Key Functions**:
- `check_inotify_status()` - Check current configuration
- `setup_incremental_mode()` - Configure incremental indexing
- `handle_file_event()` - Process individual file events
- `incremental_index_update()` - Update index for single file
- `process_batch_events()` - Process batch of events

**Usage Example**:
```python
from pathlib import Path
from skills.ingestor.inotify import setup_incremental_mode

config = setup_incremental_mode(
    watch_paths=[Path("/workspace")],
    recursive=True,
    exclude_patterns=["__pycache__", ".git"]
)
```

#### 2. Infrastructure Unification (`infra/unification.py`)
**Purpose**: Unify agents with ingestor in infrastructure layer

**Key Functions**:
- `analyze_infra_structure()` - Analyze current structure
- `identify_shared_components()` - Find shared components
- `plan_unification()` - Plan unification strategy
- `implement_shared_patterns()` - Implement shared patterns

**Usage Example**:
```python
from skills.infra.unification import analyze_infra_structure

analysis = analyze_infra_structure(Path("/sda/sokatov/own/perslad"))
print(f"Total components: {analysis['total_components']}")
```

#### 3. External Tools Integration (`agents/external_tools.py`)
**Purpose**: Integration with opencode and Continue via MCP

**Key Functions**:
- `setup_opencode_integration()` - Configure opencode integration
- `setup_continue_integration()` - Configure Continue extension
- `configure_mcp_tools()` - Configure MCP tools
- `create_opencode_config()` - Create opencode configuration

**Usage Example**:
```python
from skills.agents.external_tools import setup_opencode_integration

config = setup_opencode_integration()
print(f"Endpoint: {config['endpoint']}")
```

### Priority 2 (Future Tasks)

#### 4. Fact Graph Building (`ingestor/graph_builder.py`)
**Purpose**: RDF/OWL ontology and knowledge graph construction

**Key Functions**:
- `setup_graph_schema()` - Configure graph schema
- `build_fact_graph()` - Build fact graph from ingested data
- `query_fact_graph()` - Query the fact graph
- `visualize_graph()` - Visualize graph structure

#### 5. Database Table Filling (`ingestor/db_filling.py`)
**Purpose**: Complete ETL processes and table filling for ingestor

**Key Functions**:
- `get_table_schema()` - Get database schema
- `fill_missing_tables()` - Fill all missing tables
- `validate_data_integrity()` - Validate data across tables
- `optimize_table_indexes()` - Optimize database indexes

#### 6. Multi-Database Storage (`database/multi_storage.py`)
**Purpose**: Adapt storage for PostgreSQL, StarRocks, NebulaGraph

**Key Functions**:
- `setup_postgres_adapter()` - Configure PostgreSQL adapter
- `setup_starrocks_adapter()` - Configure StarRocks adapter
- `setup_nebulagraph_adapter()` - Configure NebulaGraph adapter
- `migrate_schema_between_dbs()` - Migrate between databases

### Supporting Skills

#### 7. Docker Management (`devops/docker.py`)
**Purpose**: Docker Compose management and monitoring

**Key Functions**:
- `check_docker_status()` - Check service status
- `rebuild_service()` - Rebuild specific service
- `view_logs()` - View service logs
- `setup_dev_environment()` - Setup development environment

#### 8. Integration Testing (`testing/integration.py`)
**Purpose**: Comprehensive testing for all components

**Key Functions**:
- `run_unit_tests()` - Run unit tests
- `run_integration_tests()` - Run integration tests
- `run_performance_tests()` - Run performance tests
- `run_security_tests()` - Run security tests

## Usage Patterns

### For OpenCode Agents

1. **Analyze the Task**
   ```python
   from skills.ingestor.inotify import check_inotify_status
   status = check_inotify_status(config)
   ```

2. **Implement Solution**
   ```python
   from skills.ingestor.inotify import setup_incremental_mode
   config = setup_incremental_mode(watch_paths=[...])
   ```

3. **Test Implementation**
   ```python
   from skills.testing.integration import run_unit_tests
   results = run_unit_tests("inotify")
   ```

4. **Document Changes**
   ```python
   from skills.docs.generator import update_skill_documentation
   update_skill_documentation("inotify", changes)
   ```

### For Development

#### Start Development
```bash
# 1. Start Docker Compose
docker-compose up -d

# 2. Check service status
python -c "from skills.devops.docker import check_docker_status; print(check_docker_status())"

# 3. Use skills in your code
from skills.agents.external_tools import setup_opencode_integration
config = setup_opencode_integration()
```

#### Testing
```bash
# Run tests for skills
pytest .opencode/skills/ -v

# Run specific skill tests
pytest .opencode/skills/ingestor/tests/ -v
pytest .opencode/skills/infra/tests/ -v
pytest .opencode/skills/agents/tests/ -v
```

## Development Guidelines

### Code Standards
- **Maximum 150 lines per file**
- **Type hints everywhere** (using `typing` module)
- **Complete docstrings** for all public functions
- **Single responsibility** for each function/class

### Testing Standards
- **Unit tests** for all skills
- **Integration tests** for component interactions
- **Mock LLM responses** for predictable testing
- **Docker-based test environments**

### Documentation Standards
- **README.md** for each skill
- **Code examples** in docstrings
- **Architecture diagrams** using Mermaid
- **API documentation** for all interfaces

## Configuration

### OpenCode Configuration
Check `.opencode/skills.yaml` for:
- Available skills and their priorities
- Test configuration
- Integration settings
- Quality gates

### Environment Configuration
Check `.env` for:
- Model configuration
- Database connection strings
- Service endpoints
- Security settings

## Current Status

### Completed Skills (Priority 1)
- ✅ `ingestor/inotify.py` - INotify incremental indexing
- ✅ `infra/unification.py` - Infrastructure unification
- ✅ `agents/external_tools.py` - External tools integration

### In Progress (Priority 2)
- 🔄 `ingestor/graph_builder.py` - Fact graph building
- 🔄 `ingestor/db_filling.py` - Database table filling
- 🔄 `database/multi_storage.py` - Multi-database storage

### Supporting Skills
- ✅ `devops/docker.py` - Docker management
- ✅ `testing/integration.py` - Integration testing
- 📝 `docs/generator.py` - Documentation (planned)

## Getting Started

1. **Review AGENTS.md** for development rules
2. **Check skills.yaml** for current priorities
3. **Start with Priority 1 tasks** (listed above)
4. **Run tests** after each implementation
5. **Update documentation** for new skills

## Next Steps

1. Complete Priority 2 skills implementation
2. Add comprehensive test coverage
3. Create example usage scripts
4. Set up CI/CD pipeline (when ready)
5. Add monitoring and logging

## Support

- **Project Documentation**: `/sda/sokatov/own/perslad/README.md`
- **Development Rules**: `.opencode/AGENTS.md`
- **Skills Configuration**: `.opencode/skills.yaml`
- **GitHub Issues**: https://github.com/svok/perslad/issues

---

**Last Updated**: 2026-02-12
**Version**: 1.0
**Status**: Active Development