"""Database models.

Importing every model here ensures SQLAlchemy registers them with
Base.metadata. Both main.py and alembic/env.py import this module
with ``import app.models  # noqa: F401``.

V1 models:
  Generation — test generation records (frozen baseline)

V2.1 models (Phase 1):
  GenerationJob — async job lifecycle and checkpoint state
  User          — registered user identity
  ApiKey        — hashed personal API keys

V2.1 models (Phase 4):
  CacheEntry    — persistent L2 cache entries
"""

from app.models.api_key import ApiKey
from app.models.cache_entry import CacheEntry
from app.models.generation import Generation
from app.models.job import GenerationJob
from app.models.user import User

__all__ = ["Generation", "GenerationJob", "User", "ApiKey", "CacheEntry"]
