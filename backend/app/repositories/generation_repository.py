"""Repository for Generation model."""

from app.models.generation import Generation
from app.repositories.base import BaseRepository


class GenerationRepository(BaseRepository[Generation]):
    """Data access layer for Generation records."""

    model = Generation
