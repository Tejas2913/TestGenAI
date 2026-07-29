"""Phase 4 — Caching package.

Provides two cache tiers:
  L1 (app/cache/l1_cache.py) — Thread-safe in-memory LRU/TTL cache.
  L2 (via app/repositories/cache_repository.py) — Persistent SQLite/Postgres cache.

The CacheManager (app/cache/manager.py) orchestrates both tiers:
  - L1 is checked first (fast path).
  - L2 is consulted on L1 miss.
  - L1 is populated from L2 hits.
  - Both tiers are written on pipeline completion.

Cache key computation lives in app/cache/keys.py.
"""

from app.cache.keys import compute_cache_key, compute_prompt_hash
from app.cache.l1_cache import L1Cache
from app.cache.manager import CacheManager

__all__ = ["L1Cache", "CacheManager", "compute_cache_key", "compute_prompt_hash"]
