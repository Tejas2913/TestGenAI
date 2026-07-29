"""L1 In-Memory Cache — Phase 4.

Thread-safe LRU + TTL in-memory cache implemented with:
  - collections.OrderedDict for O(1) LRU access tracking.
  - threading.RLock for thread safety (re-entrant to allow nested calls).
  - Lazy expiration: entries are checked on access, not on a background timer.
  - Bounded size: when the cache reaches max_size, the least-recently-used
    entry is evicted before inserting the new one.

Architecture requirements:
  - Thread-safe implementation.
  - Configurable maximum size.
  - Configurable TTL.
  - Automatic expiration.
  - Cache key based on the architecture-defined request fingerprint.

Cache value schema (dict):
  {
    "generated_tests_json": str,
    "generated_tests_code": str,
    "validation_warnings": list[str],
    "raw_response": str,
    "prompt_hash": str,
  }

Usage:
    cache = L1Cache(max_size=256, ttl_seconds=3600)
    cache.set("abc123", {"generated_tests_json": "...", ...})
    value = cache.get("abc123")   # None if expired or missing
"""

import time
from collections import OrderedDict
from threading import RLock
from typing import Any


class L1Cache:
    """Thread-safe in-memory LRU/TTL cache for deterministic generation results.

    Entries expire after `ttl_seconds`. When the cache reaches `max_size`,
    the least-recently-used entry is evicted to make room for the new one.

    All public methods are protected by a re-entrant lock so the cache is
    safe to call from multiple threads simultaneously (including the
    FastAPI background task thread pool used by the async job engine).
    """

    def __init__(
        self,
        max_size: int = 256,
        ttl_seconds: int = 3600,
    ) -> None:
        """Initialise the L1 cache.

        Args:
            max_size:    Maximum number of entries before LRU eviction.
            ttl_seconds: Seconds until an entry is considered expired.
        """
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        if ttl_seconds < 1:
            raise ValueError(f"ttl_seconds must be >= 1, got {ttl_seconds}")

        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._store: OrderedDict[str, tuple[dict, float]] = OrderedDict()
        self._lock = RLock()

        # Internal statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> dict | None:
        """Retrieve a cached value by key.

        Marks the entry as recently used (moves to end of OrderedDict).
        Returns None if the key does not exist or the entry has expired.

        Args:
            key: The 64-character SHA-256 cache key.

        Returns:
            The cached dict or None.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            value, expire_at = entry
            if time.monotonic() > expire_at:
                # Lazy expiration: remove stale entry
                del self._store[key]
                self._misses += 1
                self._expirations += 1
                return None

            # Move to end (most recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: dict) -> None:
        """Insert or update a cache entry.

        If the cache is at capacity the least-recently-used entry is
        evicted before the new entry is inserted.

        Args:
            key:   The 64-character SHA-256 cache key.
            value: The generation result dict to cache.
        """
        with self._lock:
            expire_at = time.monotonic() + self._ttl_seconds

            if key in self._store:
                # Update in place, move to end
                self._store[key] = (value, expire_at)
                self._store.move_to_end(key)
                return

            # Evict LRU entry if at capacity
            if len(self._store) >= self._max_size:
                self._store.popitem(last=False)
                self._evictions += 1

            self._store[key] = (value, expire_at)

    def invalidate(self, key: str) -> bool:
        """Remove a specific cache entry by key.

        Args:
            key: The cache key to remove.

        Returns:
            True if the key was present and removed; False otherwise.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._expirations = 0

    def size(self) -> int:
        """Return the current number of entries (including potentially expired ones)."""
        with self._lock:
            return len(self._store)

    def stats(self) -> dict[str, Any]:
        """Return a snapshot of cache statistics.

        Returns:
            Dict with keys: size, max_size, ttl_seconds, hits, misses,
            evictions, expirations, hit_rate.
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total > 0 else 0.0
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expirations": self._expirations,
                "hit_rate": round(hit_rate, 4),
            }

    def purge_expired(self) -> int:
        """Eagerly remove all expired entries.

        This is a maintenance operation — expiration is normally lazy
        (entries are expired on access). Call this to reclaim memory
        proactively.

        Returns:
            Number of entries purged.
        """
        now = time.monotonic()
        with self._lock:
            expired_keys = [
                k for k, (_, expire_at) in self._store.items()
                if now > expire_at
            ]
            for k in expired_keys:
                del self._store[k]
                self._expirations += 1
            return len(expired_keys)
