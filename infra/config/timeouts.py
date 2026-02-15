"""Timeout values in seconds."""

from dataclasses import dataclass


@dataclass
class Timeouts:
    STANDARD: int = 30
    LONG: int = 60
    VERY_LONG: int = 120
