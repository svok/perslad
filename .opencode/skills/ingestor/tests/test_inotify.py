"""Tests for INotify incremental indexing skill."""

import pytest
from pathlib import Path
from skills.ingestor.inotify import (
    setup_incremental_mode,
    check_inotify_status,
    handle_file_event,
    FileEvent,
    FileEventType,
    InotifyConfig
)


def test_setup_incremental_mode():
    """Test setting up incremental mode."""
    config = setup_incremental_mode(
        watch_paths=[Path("/workspace")],
        recursive=True,
        exclude_patterns=["__pycache__", ".git"]
    )
    
    assert config.watch_paths == [Path("/workspace")]
    assert config.recursive is True
    assert config.exclude_patterns is not None
    assert "__pycache__" in config.exclude_patterns


def test_check_inotify_status():
    """Test checking INotify status."""
    config = InotifyConfig(
        watch_paths=[Path("/workspace")],
        exclude_patterns=[".git"]
    )
    
    status = check_inotify_status(config)
    
    assert "watch_paths" in status
    assert "exclude_patterns" in status
    assert isinstance(status["watch_paths"], list)


def test_handle_file_event():
    """Test handling file events."""
    event = FileEvent(
        event_type=FileEventType.CREATE,
        file_path=Path("/workspace/test.py"),
        timestamp=1234567890.0
    )
    
    config = InotifyConfig(watch_paths=[Path("/workspace")])
    result = handle_file_event(event, config)
    
    assert "status" in result
    assert "action" in result


def test_file_event_types():
    """Test different file event types."""
    events = [
        FileEvent(FileEventType.CREATE, Path("/test"), 1234567890.0),
        FileEvent(FileEventType.MODIFY, Path("/test"), 1234567890.0),
        FileEvent(FileEventType.DELETE, Path("/test"), 1234567890.0),
        FileEvent(FileEventType.MOVE, Path("/test"), 1234567890.0),
    ]
    
    config = InotifyConfig(watch_paths=[Path("/")])
    
    for event in events:
        result = handle_file_event(event, config)
        assert "status" in result


def test_exclusion_patterns():
    """Test exclusion patterns functionality."""
    config = InotifyConfig(
        watch_paths=[Path("/workspace")],
        exclude_patterns=["__pycache__", ".git"]
    )
    
    # Test file that should be excluded
    event = FileEvent(
        event_type=FileEventType.CREATE,
        file_path=Path("/workspace/__pycache__/test.pyc"),
        timestamp=1234567890.0
    )
    
    result = handle_file_event(event, config)
    assert result["status"] == "ignored"


def test_invalid_config():
    """Test validation of invalid configurations."""
    from skills.ingestor.inotify import validate_inotify_config
    
    # Test empty watch paths
    config = InotifyConfig(watch_paths=[])
    errors = validate_inotify_config(config)
    assert len(errors) > 0
    
    # Test negative batch size
    config = InotifyConfig(watch_paths=[Path("/")], batch_size=-1)
    errors = validate_inotify_config(config)
    assert len(errors) > 0


def test_incremental_stats():
    """Test getting incremental statistics."""
    from skills.ingestor.inotify import get_incremental_stats
    
    config = InotifyConfig(
        watch_paths=[Path("/workspace")],
        exclude_patterns=[".git"],
        batch_size=50,
        debounce_ms=300
    )
    
    stats = get_incremental_stats(config)
    
    assert stats["watched_paths"] == 1
    assert stats["exclusion_patterns"] == 1
    assert stats["batch_size"] == 50
    assert stats["debounce_ms"] == 300