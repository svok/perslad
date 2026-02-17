"""Sample Python module for testing initial scan."""

import os
from typing import List, Optional


def calculate_sum(numbers: List[int]) -> int:
    """Calculate sum of a list of numbers.
    
    Args:
        numbers: List of integers to sum
        
    Returns:
        Sum of all numbers
    """
    return sum(numbers)


def greet(name: str) -> str:
    """Generate a greeting message.
    
    Args:
        name: Name to greet
        
    Returns:
        Greeting message
    """
    return f"Hello, {name}!"


class DataProcessor:
    """Process and transform data."""
    
    def __init__(self, name: str):
        self.name = name
        self._data: List[dict] = []
    
    def add_item(self, item: dict) -> None:
        """Add item to processed data."""
        self._data.append(item)
    
    def get_items(self) -> List[dict]:
        """Get all processed items."""
        return self._data.copy()
    
    def count(self) -> int:
        """Get count of processed items."""
        return len(self._data)


if __name__ == "__main__":
    processor = DataProcessor("test")
    processor.add_item({"key": "value"})
    print(f"Items: {processor.count()}")
