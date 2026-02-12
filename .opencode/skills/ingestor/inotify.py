"""
INotify incremental indexing skill for ingestor.
Handles file system events and incremental updates.

Design principles:
- Maximum 150 lines per file
- Type hints everywhere
- Single responsibility principle
- DRY and KISS patterns
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class FileEventType(Enum):
    """File system event types."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    MOVE = "move"


@dataclass
class FileEvent:
    """File system event data."""
    event_type: FileEventType
    file_path: Path
    timestamp: float
    is_directory: bool = False
    source_path: Optional[Path] = None


@dataclass
class InotifyConfig:
    """INotify configuration for incremental indexing."""
    watch_paths: List[Path]
    recursive: bool = True
    exclude_patterns: Optional[List[str]] = None
    batch_size: int = 100
    debounce_ms: int = 500

    def __post_init__(self):
        if self.exclude_patterns is None:
            self.exclude_patterns = []


def check_inotify_status(config: InotifyConfig) -> Dict[str, Any]:
    """
    Check current INotify configuration and status.
    
    Args:
        config: Current INotify configuration
        
    Returns:
        Dict with status information
    """
    patterns = config.exclude_patterns if config.exclude_patterns is not None else []
    watch_paths = config.watch_paths if config.watch_paths is not None else []
    status = {
        "watch_paths": [str(p) for p in watch_paths],
        "recursive": config.recursive,
        "exclude_patterns": patterns,
        "batch_size": config.batch_size,
        "debounce_ms": config.debounce_ms,
        "ready": all(p.exists() for p in watch_paths) if watch_paths else False
    }
    return status


def setup_incremental_mode(
    watch_paths: List[Path],
    recursive: bool = True,
    exclude_patterns: Optional[List[str]] = None
) -> InotifyConfig:
    """
    Configure INotify for incremental indexing.
    
    Args:
        watch_paths: Paths to watch for changes
        recursive: Watch subdirectories recursively
        exclude_patterns: Patterns to exclude from watching
        
    Returns:
        Configured InotifyConfig
    """
    patterns = exclude_patterns if exclude_patterns is not None else []
    paths = watch_paths if watch_paths is not None else []
    config = InotifyConfig(
        watch_paths=paths,
        recursive=recursive,
        exclude_patterns=patterns
    )
    return config


def handle_file_event(event: FileEvent, config: InotifyConfig) -> Dict[str, Any]:
    """
    Process individual file system event.
    
    Args:
        event: File system event to process
        config: Current INotify configuration
        
    Returns:
        Processing result
    """
    # Check exclusions
    for pattern in config.exclude_patterns:
        if pattern in str(event.file_path):
            return {"status": "ignored", "reason": f"Matched exclusion pattern: {pattern}"}

    # Process based on event type
    if event.event_type == FileEventType.CREATE:
        return {"status": "queued", "action": "index_new_file"}
    elif event.event_type == FileEventType.MODIFY:
        return {"status": "queued", "action": "reindex_file"}
    elif event.event_type == FileEventType.DELETE:
        return {"status": "queued", "action": "remove_from_index"}
    elif event.event_type == FileEventType.MOVE:
        return {"status": "queued", "action": "update_file_path"}
    
    return {"status": "unknown", "reason": "Unhandled event type"}


def incremental_index_update(file_path: Path, config: InotifyConfig) -> Dict[str, Any]:
    """
    Update index incrementally for single file.
    
    Args:
        file_path: Path to file to update
        config: Current INotify configuration
        
    Returns:
        Update result
    """
    if not file_path.exists():
        return {"status": "error", "reason": "File does not exist"}

    # Determine operation based on file state
    operation = "index" if file_path.is_file() else "skip"
    
    return {
        "status": "success",
        "operation": operation,
        "file": str(file_path),
        "timestamp": file_path.stat().st_mtime
    }


def process_batch_events(events: List[FileEvent], config: InotifyConfig) -> Dict[str, Any]:
    """
    Process batch of file system events.
    
    Args:
        events: List of file system events
        config: Current INotify configuration
        
    Returns:
        Batch processing results
    """
    results = []
    for event in events:
        result = handle_file_event(event, config)
        results.append(result)
    
    processed_count = len([r for r in results if r.get("status") == "queued"])
    ignored_count = len([r for r in results if r.get("status") == "ignored"])
    
    return {
        "total_events": len(events),
        "processed": processed_count,
        "ignored": ignored_count,
        "details": results
    }


def get_incremental_stats(config: InotifyConfig) -> Dict[str, Any]:
    """
    Get statistics for incremental indexing.
    
    Args:
        config: Current INotify configuration
        
    Returns:
        Statistics dictionary
    """
    patterns = config.exclude_patterns if config.exclude_patterns is not None else []
    paths = config.watch_paths if config.watch_paths is not None else []
    stats = {
        "watched_paths": len(paths),
        "exclusion_patterns": len(patterns),
        "batch_size": config.batch_size,
        "debounce_ms": config.debounce_ms,
        "recursive": config.recursive
    }
    return stats


def validate_inotify_config(config: InotifyConfig) -> List[str]:
    """
    Validate INotify configuration.
    
    Args:
        config: Configuration to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    if not config.watch_paths:
        errors.append("No watch paths specified")
    
    for path in config.watch_paths:
        if not path.exists():
            errors.append(f"Watch path does not exist: {path}")
    
    if config.batch_size <= 0:
        errors.append("Batch size must be positive")
    
    if config.debounce_ms < 0:
        errors.append("Debounce time cannot be negative")
    
    return errors