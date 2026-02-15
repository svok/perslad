"""API endpoints for Embedding service."""

from dataclasses import dataclass


@dataclass
class Embedding:
    EMBEDDINGS: str = "/v1/embeddings"
