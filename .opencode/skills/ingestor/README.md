# Ingestor Skills

## Skills for ingestor component development

### Available Skills

#### 1. inotify.py - INotify Incremental Indexing
**Purpose**: Handle file system events and incremental updates for ingestor

**Key Functions**:
- `check_inotify_status()` - Check current configuration
- `setup_incremental_mode()` - Configure incremental indexing
- `handle_file_event()` - Process individual file events
- `incremental_index_update()` - Update index for single file
- `process_batch_events()` - Process batch of events
- `get_incremental_stats()` - Get indexing statistics
- `validate_inotify_config()` - Validate configuration

**Design Principles**:
- Maximum 150 lines per file
- Type hints everywhere
- Single responsibility
- DRY and KISS patterns

**Usage Example**:
```python
from pathlib import Path
from .inotify import setup_incremental_mode, check_inotify_status

# Configure INotify
config = setup_incremental_mode(
    watch_paths=[Path("/workspace")],
    recursive=True,
    exclude_patterns=["__pycache__", ".git"]
)

# Check status
status = check_inotify_status(config)
print(f"Ready: {status['ready']}")
```

### Architecture

```
Ingestor
├── File System Events
│   ├── CREATE
│   ├── MODIFY
│   ├── DELETE
│   └── MOVE
├── INotify Config
│   ├── Watch Paths
│   ├── Recursive
│   ├── Exclusions
│   └── Batch Size
└── Incremental Processing
    ├── Queue Events
    ├── Process Batches
    └── Update Index
```

### Integration with Perslad

1. **Agent Integration**: Skills integrate with LangGraph agent
2. **MCP Tools**: Can be exposed as MCP tools for agent usage
3. **RAG Storage**: Results stored in PostgreSQL/pgvector
4. **Ingestor Pipeline**: Part of scan → parse → embed → persist pipeline

### Development Guidelines

1. **File Size**: Maximum 150 lines per file
2. **Type Hints**: Required for all functions and variables
3. **Documentation**: Complete docstrings for all public functions
4. **Testing**: Each skill must have corresponding tests
5. **Security**: Never expose secrets or sensitive paths

### Testing

```bash
# Run tests for ingestor skills
pytest .opencode/skills/ingestor/tests/ -v

# Integration test with ingestor
pytest .opencode/skills/ingestor/tests/integration/ -v
```

### Next Steps

1. Add graph building capabilities
2. Implement database table filling
3. Add multi-database support
4. Create integration tests
5. Add documentation examples