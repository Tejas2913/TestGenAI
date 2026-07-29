"""CacheEntry ORM model — Phase 4 L2 Cache.

Stores serialised generation artifacts so the pipeline can skip the
expensive LLM call on duplicate requests.

Architecture requirements:
  - Stores: request fingerprint, prompt hash, generated artifacts,
    metadata, timestamps.
  - cache_key: SHA-256 hex (64 chars), unique, indexed.
  - prompt_hash: SHA-256 of the prompt template version.
  - expires_at: nullable — when NULL, entry never expires.
  - hit_count: incremented on every L2 cache hit.

Table: cache_entries
Migration: c3d4e5f6a7b8_v2_1_phase4_add_cache_entries.py
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class CacheEntry(BaseModel):
    """Persistent L2 cache entry for a deterministic generation result.

    Fields:
        cache_key:             64-char SHA-256 hex of the request fingerprint.
        prompt_hash:           SHA-256 of the active prompt template version.
        generated_tests_json:  Generated test suite as JSON text.
        generated_tests_code:  Rendered pytest source code.
        language:              Source language (e.g. "python").
        framework:             Test framework (e.g. "pytest").
        hit_count:             Number of times this entry was served from cache.
        expires_at:            UTC expiry datetime. NULL = never expires.
        created_at:            Auto-populated from BaseModel.
    """

    __tablename__ = "cache_entries"

    __table_args__ = (
        # Fast lookup by the primary cache key
        Index("ix_cache_entries_cache_key", "cache_key", unique=True),
        # Allow filtering by prompt version (for bulk invalidation on upgrade)
        Index("ix_cache_entries_prompt_hash", "prompt_hash"),
        # Allow efficient purge of expired entries
        Index("ix_cache_entries_expires_at", "expires_at"),
    )

    # ----------------------------------------------------------------
    # Request identity
    # ----------------------------------------------------------------
    cache_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="SHA-256 hex of (source_code|specification|language|framework|prompt_version)",
    )
    prompt_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 of the active prompt template version string",
    )

    # ----------------------------------------------------------------
    # Generated artifacts
    # ----------------------------------------------------------------
    generated_tests_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Raw JSON of the generated test suite",
    )
    generated_tests_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Rendered pytest source code",
    )

    # ----------------------------------------------------------------
    # Request metadata
    # ----------------------------------------------------------------
    language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="python",
    )
    framework: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pytest",
    )

    # ----------------------------------------------------------------
    # Cache management
    # ----------------------------------------------------------------
    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Incremented each time this entry is served from L2 cache",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="UTC expiry. NULL = entry never expires.",
    )
