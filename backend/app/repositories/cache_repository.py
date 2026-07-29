"""CacheRepository — Phase 4 L2 Cache.

Provides CRUD and domain-specific operations for CacheEntry records.

Inherits standard create / get_by_id / update / get_all from BaseRepository.

Domain-specific methods:
  get_by_key()       — Look up a cache entry by its 64-char SHA-256 key.
  increment_hit()    — Atomically increment the hit_count for an entry.
  upsert()           — Insert new entry or update existing if key exists.
  delete_by_key()    — Remove a single entry by key.
  delete_expired()   — Bulk-delete all entries past their expires_at.
  delete_by_prompt_hash() — Bulk-delete all entries for a given prompt version.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.models.cache_entry import CacheEntry
from app.repositories.base import BaseRepository


class CacheRepository(BaseRepository[CacheEntry]):
    """Data access layer for L2 persistent cache entries.

    All write methods use SQLAlchemy ORM. Bulk operations (increment_hit,
    delete_expired) use raw SQL for efficiency.
    """

    model = CacheEntry

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_key(self, cache_key: str) -> CacheEntry | None:
        """Return the cache entry for the given SHA-256 key, or None.

        Args:
            cache_key: 64-char SHA-256 hex string from compute_cache_key().

        Returns:
            CacheEntry or None if not found.
        """
        return (
            self._session.query(CacheEntry)
            .filter(CacheEntry.cache_key == cache_key)
            .first()
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def increment_hit(self, cache_key: str) -> None:
        """Atomically increment the hit_count for the given cache key.

        Uses a single SQL UPDATE for efficiency — avoids a read-modify-write
        cycle that would require additional locking.

        Args:
            cache_key: 64-char SHA-256 hex string.
        """
        self._session.execute(
            text(
                "UPDATE cache_entries "
                "SET hit_count = hit_count + 1 "
                "WHERE cache_key = :key"
            ),
            {"key": cache_key},
        )
        self._session.commit()

    def upsert(
        self,
        cache_key: str,
        prompt_hash: str,
        generated_tests_json: str,
        generated_tests_code: str,
        language: str,
        framework: str,
        expires_at: datetime | None,
    ) -> CacheEntry:
        """Insert a new cache entry, or update the existing one if the key exists.

        On update, the artifacts and expires_at are refreshed; hit_count is
        preserved.

        Args:
            cache_key:             64-char SHA-256 hex key.
            prompt_hash:           SHA-256 of the prompt version string.
            generated_tests_json:  Generated test suite JSON.
            generated_tests_code:  Rendered pytest source code.
            language:              Programming language.
            framework:             Test framework.
            expires_at:            UTC expiry datetime (None = never).

        Returns:
            The inserted or updated CacheEntry.
        """
        existing = self.get_by_key(cache_key)
        if existing is not None:
            existing.prompt_hash = prompt_hash
            existing.generated_tests_json = generated_tests_json
            existing.generated_tests_code = generated_tests_code
            existing.language = language
            existing.framework = framework
            existing.expires_at = expires_at
            self._session.commit()
            self._session.refresh(existing)
            return existing

        entry = CacheEntry(
            cache_key=cache_key,
            prompt_hash=prompt_hash,
            generated_tests_json=generated_tests_json,
            generated_tests_code=generated_tests_code,
            language=language,
            framework=framework,
            hit_count=0,
            expires_at=expires_at,
        )
        self._session.add(entry)
        self._session.commit()
        self._session.refresh(entry)
        return entry

    def delete_by_key(self, cache_key: str) -> bool:
        """Remove a single entry by its cache key.

        Args:
            cache_key: 64-char SHA-256 hex string.

        Returns:
            True if a row was deleted; False if not found.
        """
        result = self._session.execute(
            text("DELETE FROM cache_entries WHERE cache_key = :key"),
            {"key": cache_key},
        )
        self._session.commit()
        return result.rowcount > 0  # type: ignore[union-attr]

    def delete_expired(self) -> int:
        """Bulk-delete all entries whose expires_at is in the past.

        Entries with expires_at = NULL are never deleted (they never expire).

        Returns:
            Number of rows deleted.
        """
        now_utc = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        result = self._session.execute(
            text(
                "DELETE FROM cache_entries "
                "WHERE expires_at IS NOT NULL "
                "AND expires_at < :now"
            ),
            {"now": now_utc},
        )
        self._session.commit()
        return result.rowcount  # type: ignore[return-value]

    def delete_by_prompt_hash(self, prompt_hash: str) -> int:
        """Bulk-delete all entries created by a specific prompt template version.

        Useful for invalidating the entire L2 cache after a template upgrade.

        Args:
            prompt_hash: SHA-256 hex of the prompt version string.

        Returns:
            Number of rows deleted.
        """
        result = self._session.execute(
            text(
                "DELETE FROM cache_entries "
                "WHERE prompt_hash = :hash"
            ),
            {"hash": prompt_hash},
        )
        self._session.commit()
        return result.rowcount  # type: ignore[return-value]
