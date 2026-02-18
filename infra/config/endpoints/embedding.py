"""API endpoints for Embedding service."""

from dataclasses import dataclass


@dataclass
class Embedding:
    MODELS: str = "/models"
    EMBEDDINGS: str = "/embeddings"
