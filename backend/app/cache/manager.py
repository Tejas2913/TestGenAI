"""Cache Manager — Phase 4.

Orchestrates the two-tier cache (L1 in-memory + L2 database).

Lookup order:
  1. L1 (in-memory)  — fast, bounded, ephemeral.
  2. L2 (DB)         — persistent, checked only after L1 miss.
      On L2 hit: populate L1 so subsequent accesses are fast.
  3. Miss            — caller must run the pipeline and then call set().

Write order:
  On pipeline completion, both tiers are written atomically:
  L1.set() is always called.
  L2 write is attempted if ENABLE_L2_CACHE is True and a repo is provided.

Architecture requirements fulfilled:
  - L2 consulted only after L1 miss.
  - L1 populated from L2 hits.
  - Repository abstraction (L2 operations via CacheRepository).
  - Configurable enable/disable per tier.

CacheManager is session-aware: the caller must pass a fresh
CacheRepository bound to an open DB session. This keeps the manager
compatible with both sync (V1) and threadpool (V3 background tasks)
execution contexts.
"""

from __future__ import annotations

import structlog
from datetime import datetime, timedelta, timezone

from app.cache.l1_cache import L1Cache
from app.core.config import settings

logger = structlog.get_logger(__name__)


class CacheManager:
    """Two-tier cache orchestrator for deterministic generation results.

    Args:
        l1:        The shared L1 in-memory cache instance.
        cache_repo: Optional repository bound to an open DB session.
                    Required for L2 reads/writes. None disables L2.
    """

    def __init__(
        self,
        l1: L1Cache,
        cache_repo=None,
    ) -> None:
        self._l1 = l1
        self._repo = cache_repo

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def get(self, cache_key: str) -> dict | None:
        """Two-tier cache lookup.

        Returns the cached generation artifacts or None on full miss.
        On L2 hit, the L1 cache is populated so the next access is instant.

        Args:
            cache_key: 64-char SHA-256 hex key from compute_cache_key().

        Returns:
            Artifact dict or None.
        """
        # Tier 1: L1 in-memory
        if settings.ENABLE_L1_CACHE:
            cached = self._l1.get(cache_key)
            if cached is not None:
                logger.debug("cache_l1_hit", cache_key=cache_key[:8])
                return cached

        # Tier 2: L2 DB
        if settings.ENABLE_L2_CACHE and self._repo is not None:
            entry = self._repo.get_by_key(cache_key)
            if entry is not None:
                # Check explicit expiry timestamp
                if entry.expires_at is not None:
                    now = datetime.now(tz=timezone.utc)
                    expires = entry.expires_at
                    # Make expires_at offset-aware if it isn't already
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if now > expires:
                        logger.debug("cache_l2_expired", cache_key=cache_key[:8])
                        return None

                value = {
                    "generated_tests_json": entry.generated_tests_json,
                    "generated_tests_code": entry.generated_tests_code,
                    "validation_warnings": [],
                    "raw_response": "",
                    "prompt_hash": entry.prompt_hash,
                    "from_cache": True,
                }

                # Populate L1 from L2 hit
                if settings.ENABLE_L1_CACHE:
                    self._l1.set(cache_key, value)

                # Increment hit counter
                try:
                    self._repo.increment_hit(cache_key)
                except Exception as exc:
                    logger.warning("cache_l2_hit_count_failed", error=str(exc))

                logger.debug("cache_l2_hit", cache_key=cache_key[:8])
                return value

        return None

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def set(
        self,
        cache_key: str,
        prompt_hash: str,
        value: dict,
        language: str,
        framework: str,
    ) -> None:
        """Write a generation result to both cache tiers.

        Args:
            cache_key:  64-char SHA-256 hex key.
            prompt_hash: SHA-256 of the prompt template version.
            value:      Artifact dict to cache.
            language:   Programming language (e.g. "python").
            framework:  Test framework (e.g. "pytest").
        """
        # Always write L1 when enabled
        if settings.ENABLE_L1_CACHE:
            self._l1.set(cache_key, value)
            logger.debug("cache_l1_write", cache_key=cache_key[:8])

        # Write L2 when enabled and repo available
        if settings.ENABLE_L2_CACHE and self._repo is not None:
            expires_at = datetime.now(tz=timezone.utc) + timedelta(
                seconds=settings.L2_CACHE_TTL_SECONDS
            )
            try:
                self._repo.upsert(
                    cache_key=cache_key,
                    prompt_hash=prompt_hash,
                    generated_tests_json=value.get("generated_tests_json", ""),
                    generated_tests_code=value.get("generated_tests_code", ""),
                    language=language,
                    framework=framework,
                    expires_at=expires_at,
                )
                logger.debug("cache_l2_write", cache_key=cache_key[:8])
            except Exception as exc:
                # L2 write failure must never break the caller
                logger.warning("cache_l2_write_failed", cache_key=cache_key[:8], error=str(exc))

    def invalidate(self, cache_key: str) -> None:
        """Remove an entry from both cache tiers.

        Args:
            cache_key: 64-char SHA-256 hex key to remove.
        """
        if settings.ENABLE_L1_CACHE:
            self._l1.invalidate(cache_key)

        if settings.ENABLE_L2_CACHE and self._repo is not None:
            try:
                self._repo.delete_by_key(cache_key)
            except Exception as exc:
                logger.warning("cache_l2_invalidate_failed", cache_key=cache_key[:8], error=str(exc))
