"""Phase 4 tests — Caching, Context Provider & Quality Evaluation.

Test coverage:
  TestL1CacheBasics       — get, set, miss, hit, size tracking
  TestL1CacheTTL          — expiration via time.monotonic patching
  TestL1CacheMaxSize      — LRU eviction at capacity
  TestL1CacheThreadSafety — concurrent get/set from multiple threads
  TestL1CacheInvalidate   — explicit invalidation and clear
  TestL1CacheStats        — stats snapshot and hit_rate calculation
  TestL1CachePurge        — purge_expired removes only stale entries
  TestCacheKeys           — compute_cache_key determinism, uniqueness
  TestPromptHash          — compute_prompt_hash determinism
  TestCacheManager        — L1 hit fast path, L1 miss → L2 hit (L1 populated)
  TestCacheManagerSet     — write both tiers; L2 failure does not raise
  TestL2CacheRepository   — upsert, get_by_key, increment_hit, delete_by_key,
                            delete_expired, delete_by_prompt_hash
  TestContextProvider     — DefaultContextProvider returns "", factory function
  TestContextInjection    — GenerationService propagates context to prompt builder
  TestConfidenceSignals   — all sandbox_signal branch values
  TestConfidenceValidation — all validation_signal branch values
  TestConfidenceTestCount — all test_count_signal branch values
  TestConfidenceGrades    — HIGH / MEDIUM / LOW grade thresholds
  TestConfidenceOverall   — weighted combination math
  TestConfidenceEdgeCases — zero tests, 0 warnings + sandbox
  TestGoldenDatasetRecord — GoldenRecord.from_dict, defaults
  TestGoldenDatasetLoad   — load_golden_dataset valid / error paths
  TestGoldenEvaluator     — pass/fail criteria, report aggregation
  TestGoldenEvaluatorDict — evaluate_dict path
  TestCacheFallback       — no cache_manager → pipeline runs normally
"""

import json
import os
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# TestL1CacheBasics
# ===========================================================================

class TestL1CacheBasics:
    def _make(self, max_size=10, ttl=600):
        from app.cache.l1_cache import L1Cache
        return L1Cache(max_size=max_size, ttl_seconds=ttl)

    def test_get_miss_returns_none(self):
        c = self._make()
        assert c.get("nonexistent") is None

    def test_set_then_get_returns_value(self):
        c = self._make()
        c.set("k1", {"data": "hello"})
        result = c.get("k1")
        assert result == {"data": "hello"}

    def test_set_updates_existing_key(self):
        c = self._make()
        c.set("k1", {"v": 1})
        c.set("k1", {"v": 2})
        assert c.get("k1") == {"v": 2}

    def test_size_reflects_entries(self):
        c = self._make()
        assert c.size() == 0
        c.set("a", {})
        c.set("b", {})
        assert c.size() == 2

    def test_invalid_max_size_raises(self):
        from app.cache.l1_cache import L1Cache
        with pytest.raises(ValueError):
            L1Cache(max_size=0, ttl_seconds=60)

    def test_invalid_ttl_raises(self):
        from app.cache.l1_cache import L1Cache
        with pytest.raises(ValueError):
            L1Cache(max_size=10, ttl_seconds=0)

    def test_get_increments_hit_stat(self):
        c = self._make()
        c.set("x", {})
        c.get("x")
        c.get("x")
        assert c.stats()["hits"] == 2

    def test_miss_increments_miss_stat(self):
        c = self._make()
        c.get("nope")
        assert c.stats()["misses"] == 1


# ===========================================================================
# TestL1CacheTTL
# ===========================================================================

class TestL1CacheTTL:
    def test_entry_valid_within_ttl(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=60)
        c.set("k", {"val": 1})
        assert c.get("k") is not None

    def test_entry_expired_after_ttl(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=1)
        # Patch monotonic so the entry appears already expired
        with patch("app.cache.l1_cache.time") as t:
            t.monotonic.side_effect = [
                0.0,    # set: expire_at = 0.0 + 1 = 1.0
                2.0,    # get: now=2.0 > 1.0 → expired
            ]
            c.set("k", {"v": 1})
            result = c.get("k")
        assert result is None

    def test_expired_entry_removed_from_store(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=1)
        with patch("app.cache.l1_cache.time") as t:
            t.monotonic.side_effect = [0.0, 10.0]
            c.set("k", {})
            c.get("k")  # triggers expiry
        assert c.size() == 0

    def test_expiration_increments_expirations_stat(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=1)
        with patch("app.cache.l1_cache.time") as t:
            t.monotonic.side_effect = [0.0, 10.0]
            c.set("k", {})
            c.get("k")
        assert c.stats()["expirations"] == 1


# ===========================================================================
# TestL1CacheMaxSize
# ===========================================================================

class TestL1CacheMaxSize:
    def test_evicts_lru_when_full(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=3, ttl_seconds=3600)
        c.set("a", {"v": 1})
        c.set("b", {"v": 2})
        c.set("c", {"v": 3})
        # Access 'a' to make it recently used; LRU is now 'b'
        c.get("a")
        # Insert 'd' → 'b' should be evicted
        c.set("d", {"v": 4})
        assert c.size() == 3
        assert c.get("b") is None     # evicted
        assert c.get("a") is not None # still present
        assert c.get("c") is not None
        assert c.get("d") is not None

    def test_eviction_increments_evictions_stat(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=2, ttl_seconds=3600)
        c.set("a", {})
        c.set("b", {})
        c.set("c", {})  # evicts 'a'
        assert c.stats()["evictions"] == 1


# ===========================================================================
# TestL1CacheThreadSafety
# ===========================================================================

class TestL1CacheThreadSafety:
    def test_concurrent_writes_no_exception(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=100, ttl_seconds=3600)
        errors = []

        def worker(idx):
            try:
                for i in range(20):
                    c.set(f"key_{idx}_{i}", {"v": i})
                    c.get(f"key_{idx}_{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert not errors, f"Thread-safety errors: {errors}"

    def test_size_consistent_after_concurrent_writes(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=50, ttl_seconds=3600)
        threads = [
            threading.Thread(target=lambda: [c.set(f"k{i}", {}) for i in range(50)])
            for _ in range(4)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert c.size() <= 50  # max_size respected


# ===========================================================================
# TestL1CacheInvalidate
# ===========================================================================

class TestL1CacheInvalidate:
    def test_invalidate_existing_key_returns_true(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=3600)
        c.set("k", {})
        assert c.invalidate("k") is True
        assert c.get("k") is None

    def test_invalidate_missing_key_returns_false(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=3600)
        assert c.invalidate("missing") is False

    def test_clear_removes_all_entries(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=3600)
        c.set("a", {})
        c.set("b", {})
        c.clear()
        assert c.size() == 0
        assert c.stats()["hits"] == 0

    def test_clear_resets_stats(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=3600)
        c.set("a", {})
        c.get("a")
        c.clear()
        assert c.stats()["hits"] == 0
        assert c.stats()["misses"] == 0


# ===========================================================================
# TestL1CacheStats
# ===========================================================================

class TestL1CacheStats:
    def test_stats_contains_required_keys(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=5, ttl_seconds=60)
        s = c.stats()
        for key in ("size", "max_size", "ttl_seconds", "hits", "misses",
                    "evictions", "expirations", "hit_rate"):
            assert key in s

    def test_hit_rate_zero_when_no_accesses(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=60)
        assert c.stats()["hit_rate"] == 0.0

    def test_hit_rate_1_when_all_hits(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=60)
        c.set("k", {})
        c.get("k")
        c.get("k")
        assert c.stats()["hit_rate"] == 1.0

    def test_hit_rate_half_when_equal_hits_misses(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=60)
        c.set("k", {})
        c.get("k")     # hit
        c.get("nope")  # miss
        assert c.stats()["hit_rate"] == 0.5


# ===========================================================================
# TestL1CachePurge
# ===========================================================================

class TestL1CachePurge:
    def test_purge_removes_only_expired(self):
        from app.cache.l1_cache import L1Cache
        c = L1Cache(max_size=10, ttl_seconds=1)
        with patch("app.cache.l1_cache.time") as t:
            # set two entries
            t.monotonic.return_value = 0.0
            c.set("fresh", {})
            t.monotonic.return_value = 0.0
            c.set("stale", {})

            # make stale's expire_at appear in the past
            # (entry's expire_at = 0 + 1 = 1.0)
            t.monotonic.return_value = 5.0  # now > expire_at for stale

        # Do it properly: set fresh with large TTL, stale already expired
        c2 = L1Cache(max_size=10, ttl_seconds=3600)
        c2.set("fresh", {})
        # Manually put an expired entry
        import time as real_time
        c2._store["stale"] = ({}, real_time.monotonic() - 10)

        purged = c2.purge_expired()
        assert purged == 1
        assert c2.get("fresh") is not None
        assert c2.get("stale") is None


# ===========================================================================
# TestCacheKeys
# ===========================================================================

class TestCacheKeys:
    def test_same_inputs_produce_same_key(self):
        from app.cache.keys import compute_cache_key
        k1 = compute_cache_key("def f(): pass", None, "python", "pytest", "v1")
        k2 = compute_cache_key("def f(): pass", None, "python", "pytest", "v1")
        assert k1 == k2

    def test_different_source_code_produces_different_key(self):
        from app.cache.keys import compute_cache_key
        k1 = compute_cache_key("def a(): pass", None, "python", "pytest", "v1")
        k2 = compute_cache_key("def b(): pass", None, "python", "pytest", "v1")
        assert k1 != k2

    def test_different_specification_produces_different_key(self):
        from app.cache.keys import compute_cache_key
        k1 = compute_cache_key("code", "spec A", "python", "pytest", "v1")
        k2 = compute_cache_key("code", "spec B", "python", "pytest", "v1")
        assert k1 != k2

    def test_none_vs_empty_spec_same(self):
        from app.cache.keys import compute_cache_key
        k1 = compute_cache_key("code", None, "python", "pytest", "v1")
        k2 = compute_cache_key("code", "", "python", "pytest", "v1")
        # None is normalised to "" so they should match
        assert k1 == k2

    def test_key_is_64_chars(self):
        from app.cache.keys import compute_cache_key
        k = compute_cache_key("code", None, "python", "pytest", "v1")
        assert len(k) == 64

    def test_key_is_lowercase_hex(self):
        from app.cache.keys import compute_cache_key
        k = compute_cache_key("code", None, "python", "pytest", "v1")
        assert all(c in "0123456789abcdef" for c in k)

    def test_prompt_version_change_changes_key(self):
        from app.cache.keys import compute_cache_key
        k1 = compute_cache_key("code", None, "python", "pytest", "v1")
        k2 = compute_cache_key("code", None, "python", "pytest", "v2")
        assert k1 != k2


# ===========================================================================
# TestPromptHash
# ===========================================================================

class TestPromptHash:
    def test_same_version_same_hash(self):
        from app.cache.keys import compute_prompt_hash
        assert compute_prompt_hash("v1") == compute_prompt_hash("v1")

    def test_different_versions_different_hash(self):
        from app.cache.keys import compute_prompt_hash
        assert compute_prompt_hash("v1") != compute_prompt_hash("v2")

    def test_hash_is_64_chars(self):
        from app.cache.keys import compute_prompt_hash
        assert len(compute_prompt_hash("v1")) == 64


# ===========================================================================
# TestCacheManager (unit — mocked repo)
# ===========================================================================

class TestCacheManager:
    def _make(self, l1=None, repo=None):
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager
        l1 = l1 or L1Cache(max_size=10, ttl_seconds=3600)
        return CacheManager(l1=l1, cache_repo=repo), l1

    def test_l1_hit_returns_value_without_repo(self):
        mgr, l1 = self._make()
        value = {"generated_tests_json": '{"test_cases": []}', "generated_tests_code": "pass"}
        l1.set("key123", value)

        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = True
            s.ENABLE_L2_CACHE = False
            result = mgr.get("key123")
        assert result == value

    def test_l1_miss_with_no_l2_returns_none(self):
        mgr, _ = self._make()
        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = True
            s.ENABLE_L2_CACHE = False
            result = mgr.get("missing")
        assert result is None

    def test_l2_hit_populates_l1(self):
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager

        l1 = L1Cache(max_size=10, ttl_seconds=3600)
        mock_repo = MagicMock()
        mock_entry = MagicMock()
        mock_entry.expires_at = None
        mock_entry.generated_tests_json = '{"test_cases": []}'
        mock_entry.generated_tests_code = "# tests"
        mock_entry.prompt_hash = "abc" * 21 + "a"
        mock_repo.get_by_key.return_value = mock_entry

        mgr = CacheManager(l1=l1, cache_repo=mock_repo)

        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = True
            s.ENABLE_L2_CACHE = True
            result = mgr.get("testkey")

        assert result is not None
        assert result["generated_tests_json"] == '{"test_cases": []}'
        # L1 should now have this entry
        assert l1.get("testkey") is not None

    def test_l2_hit_increments_hit_count(self):
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager

        l1 = L1Cache(max_size=10, ttl_seconds=3600)
        mock_repo = MagicMock()
        mock_entry = MagicMock()
        mock_entry.expires_at = None
        mock_entry.generated_tests_json = "{}"
        mock_entry.generated_tests_code = ""
        mock_entry.prompt_hash = "x" * 64
        mock_repo.get_by_key.return_value = mock_entry

        mgr = CacheManager(l1=l1, cache_repo=mock_repo)
        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = False
            s.ENABLE_L2_CACHE = True
            mgr.get("k")

        mock_repo.increment_hit.assert_called_once_with("k")

    def test_l2_expired_entry_returns_none(self):
        from datetime import datetime, timezone
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager

        l1 = L1Cache(max_size=10, ttl_seconds=3600)
        mock_repo = MagicMock()
        mock_entry = MagicMock()
        # expires_at in the past
        mock_entry.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        mock_repo.get_by_key.return_value = mock_entry

        mgr = CacheManager(l1=l1, cache_repo=mock_repo)
        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = False
            s.ENABLE_L2_CACHE = True
            result = mgr.get("stale_key")

        assert result is None

    def test_full_miss_returns_none(self):
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager

        l1 = L1Cache(max_size=10, ttl_seconds=3600)
        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        mgr = CacheManager(l1=l1, cache_repo=mock_repo)
        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = True
            s.ENABLE_L2_CACHE = True
            result = mgr.get("miss")

        assert result is None


# ===========================================================================
# TestCacheManagerSet
# ===========================================================================

class TestCacheManagerSet:
    def test_set_writes_to_l1_when_enabled(self):
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager

        l1 = L1Cache(max_size=10, ttl_seconds=3600)
        mgr = CacheManager(l1=l1, cache_repo=None)
        value = {"generated_tests_json": "{}", "generated_tests_code": "pass"}

        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = True
            s.ENABLE_L2_CACHE = False
            mgr.set("k", "ph", value, "python", "pytest")

        assert l1.get("k") == value

    def test_set_writes_to_l2_when_enabled(self):
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager

        l1 = L1Cache(max_size=10, ttl_seconds=3600)
        mock_repo = MagicMock()
        mgr = CacheManager(l1=l1, cache_repo=mock_repo)

        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = False
            s.ENABLE_L2_CACHE = True
            s.L2_CACHE_TTL_SECONDS = 86400
            mgr.set("k", "ph", {}, "python", "pytest")

        mock_repo.upsert.assert_called_once()

    def test_l2_write_failure_does_not_raise(self):
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager

        l1 = L1Cache(max_size=10, ttl_seconds=3600)
        mock_repo = MagicMock()
        mock_repo.upsert.side_effect = RuntimeError("DB down")
        mgr = CacheManager(l1=l1, cache_repo=mock_repo)

        with patch("app.cache.manager.settings") as s:
            s.ENABLE_L1_CACHE = False
            s.ENABLE_L2_CACHE = True
            s.L2_CACHE_TTL_SECONDS = 86400
            # Must not raise even when L2 fails
            mgr.set("k", "ph", {}, "python", "pytest")


# ===========================================================================
# TestL2CacheRepository
# ===========================================================================

class TestL2CacheRepository:
    """Integration tests against the in-memory SQLite test DB."""

    def _make_repo(self, db_session):
        from app.repositories.cache_repository import CacheRepository
        return CacheRepository(db_session)

    def test_upsert_creates_new_entry(self, db_session):
        repo = self._make_repo(db_session)
        entry = repo.upsert(
            cache_key="a" * 64,
            prompt_hash="b" * 64,
            generated_tests_json='{"test_cases": []}',
            generated_tests_code="pass",
            language="python",
            framework="pytest",
            expires_at=None,
        )
        assert entry.id is not None
        assert entry.cache_key == "a" * 64
        assert entry.hit_count == 0

    def test_get_by_key_returns_entry(self, db_session):
        repo = self._make_repo(db_session)
        repo.upsert("k" * 64, "p" * 64, "{}", "pass", "python", "pytest", None)
        found = repo.get_by_key("k" * 64)
        assert found is not None
        assert found.cache_key == "k" * 64

    def test_get_by_key_missing_returns_none(self, db_session):
        repo = self._make_repo(db_session)
        assert repo.get_by_key("z" * 64) is None

    def test_upsert_updates_existing_entry(self, db_session):
        repo = self._make_repo(db_session)
        repo.upsert("k" * 64, "p" * 64, "{}", "old", "python", "pytest", None)
        repo.upsert("k" * 64, "p" * 64, "{}", "new", "python", "pytest", None)
        found = repo.get_by_key("k" * 64)
        assert found.generated_tests_code == "new"

    def test_increment_hit_increases_count(self, db_session):
        repo = self._make_repo(db_session)
        repo.upsert("k" * 64, "p" * 64, "{}", "pass", "python", "pytest", None)
        repo.increment_hit("k" * 64)
        repo.increment_hit("k" * 64)
        found = repo.get_by_key("k" * 64)
        assert found.hit_count == 2

    def test_delete_by_key_returns_true(self, db_session):
        repo = self._make_repo(db_session)
        repo.upsert("k" * 64, "p" * 64, "{}", "pass", "python", "pytest", None)
        removed = repo.delete_by_key("k" * 64)
        assert removed is True
        assert repo.get_by_key("k" * 64) is None

    def test_delete_by_key_missing_returns_false(self, db_session):
        repo = self._make_repo(db_session)
        assert repo.delete_by_key("z" * 64) is False

    def test_delete_expired_removes_past_entries(self, db_session):
        from datetime import datetime, timezone
        repo = self._make_repo(db_session)
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        repo.upsert("a" * 64, "p" * 64, "{}", "pass", "python", "pytest", past)
        repo.upsert("b" * 64, "p" * 64, "{}", "pass", "python", "pytest", future)
        deleted = repo.delete_expired()
        assert deleted == 1
        assert repo.get_by_key("a" * 64) is None
        assert repo.get_by_key("b" * 64) is not None

    def test_delete_expired_skips_null_expires(self, db_session):
        repo = self._make_repo(db_session)
        repo.upsert("k" * 64, "p" * 64, "{}", "pass", "python", "pytest", None)
        deleted = repo.delete_expired()
        assert deleted == 0
        assert repo.get_by_key("k" * 64) is not None

    def test_delete_by_prompt_hash(self, db_session):
        repo = self._make_repo(db_session)
        repo.upsert("a" * 64, "p" * 64, "{}", "pass", "python", "pytest", None)
        repo.upsert("b" * 64, "p" * 64, "{}", "pass", "python", "pytest", None)
        repo.upsert("c" * 64, "q" * 64, "{}", "pass", "python", "pytest", None)
        deleted = repo.delete_by_prompt_hash("p" * 64)
        assert deleted == 2
        assert repo.get_by_key("c" * 64) is not None


# ===========================================================================
# TestContextProvider
# ===========================================================================

class TestContextProvider:
    def test_default_provider_returns_empty_string(self):
        from app.context.provider import DefaultContextProvider
        provider = DefaultContextProvider()
        assert provider.get_context("def f(): pass", None) == ""

    def test_default_provider_returns_empty_for_spec(self):
        from app.context.provider import DefaultContextProvider
        provider = DefaultContextProvider()
        assert provider.get_context("code", "spec") == ""

    def test_default_provider_name(self):
        from app.context.provider import DefaultContextProvider
        assert DefaultContextProvider().provider_name == "default"

    def test_factory_returns_default_provider_for_default_class(self):
        from app.context.provider import get_context_provider, DefaultContextProvider
        from app.core.config import settings
        orig = settings.CONTEXT_PROVIDER_CLASS
        try:
            settings.CONTEXT_PROVIDER_CLASS = "default"
            p = get_context_provider()
            assert isinstance(p, DefaultContextProvider)
        finally:
            settings.CONTEXT_PROVIDER_CLASS = orig

    def test_factory_returns_default_for_unknown_class(self):
        from app.context.provider import get_context_provider, DefaultContextProvider
        from app.core.config import settings
        orig = settings.CONTEXT_PROVIDER_CLASS
        try:
            settings.CONTEXT_PROVIDER_CLASS = "nonexistent_future_provider"
            p = get_context_provider()
            assert isinstance(p, DefaultContextProvider)
        finally:
            settings.CONTEXT_PROVIDER_CLASS = orig

    def test_provider_is_abstract(self):
        from app.context.provider import ContextProvider
        with pytest.raises(TypeError):
            ContextProvider()  # type: ignore


# ===========================================================================
# TestContextInjection
# ===========================================================================

class TestContextInjection:
    """Verify GenerationService correctly passes context to PromptBuilder."""

    def _make_service_with_mock_context(self, context_str=""):
        from app.context.provider import ContextProvider
        from app.services.generation_service import GenerationService

        mock_repo = MagicMock()
        mock_repo.create.return_value = MagicMock(id="gen-1")
        mock_repo.get_by_id.return_value = MagicMock(id="gen-1")

        mock_provider = MagicMock()

        class FakeContextProvider(ContextProvider):
            def get_context(self, sc, spec):
                return context_str
            @property
            def provider_name(self):
                return "test"

        return GenerationService(
            repository=mock_repo,
            llm_provider=mock_provider,
            context_provider=FakeContextProvider(),
        )

    def test_empty_context_does_not_modify_spec(self):
        svc = self._make_service_with_mock_context("")
        # No exception — context provider is wired
        assert svc._context_provider.provider_name == "test"
        assert svc._context_provider.get_context("", None) == ""

    def test_non_empty_context_appended_to_spec(self):
        from app.context.provider import ContextProvider
        from app.services.generation_service import GenerationService
        from app.domain.test_suite import TestSuite

        class ContextWith(ContextProvider):
            def get_context(self, sc, spec):
                return "Extra context here."
            @property
            def provider_name(self):
                return "with_ctx"

        captured_specs = []

        class FakeBuilder:
            _version = "v1"

            def build(self, metadata, specification=None):
                captured_specs.append(specification)
                from app.domain.prompt_payload import PromptPayload
                return PromptPayload(
                    system_prompt="s",
                    developer_prompt="d",
                    user_prompt="",
                )

        fake_test_suite = TestSuite(
            function_name="f",
            test_cases=[],
            imports=[],
            setup_code=None,
        )

        svc = GenerationService(
            repository=MagicMock(),
            llm_provider=MagicMock(),
            context_provider=ContextWith(),
        )
        svc._prompt_builder = FakeBuilder()
        svc._analyser = MagicMock()
        svc._analyser.analyse.return_value = MagicMock(function_name="f")
        svc._llm_provider.generate.return_value = (
            '{"function_name":"f","test_cases":[],"imports":[],"setup_code":null}'
        )
        # Return a real TestSuite so GenerationResult validation passes
        real_parser = MagicMock()
        real_parser.parse.return_value = fake_test_suite
        svc._response_parser = real_parser
        svc._schema_validator = MagicMock(); svc._schema_validator.validate.return_value = []
        svc._semantic_validator = MagicMock(); svc._semantic_validator.validate.return_value = []
        svc._business_validator = MagicMock(); svc._business_validator.validate.return_value = []
        svc._code_generator = MagicMock(); svc._code_generator.generate.return_value = "# code"

        import structlog
        svc._run_pipeline("def f(): pass", "base spec", "pytest",
                          log=structlog.get_logger())

        assert len(captured_specs) == 1
        assert "Additional Context:" in captured_specs[0]
        assert "Extra context here." in captured_specs[0]

    def test_default_context_provider_injected_when_none_given(self):
        from app.context.provider import DefaultContextProvider
        from app.services.generation_service import GenerationService
        svc = GenerationService(
            repository=MagicMock(),
            llm_provider=MagicMock(),
        )
        assert isinstance(svc._context_provider, DefaultContextProvider)


# ===========================================================================
# TestConfidenceSignals
# ===========================================================================

class TestConfidenceSignals:
    def test_sandbox_exit_0_signal_is_1(self):
        from app.evaluation.confidence import _sandbox_signal
        assert _sandbox_signal(0) == 1.0

    def test_sandbox_exit_1_signal_is_0_5(self):
        from app.evaluation.confidence import _sandbox_signal
        assert _sandbox_signal(1) == 0.5

    def test_sandbox_exit_minus1_signal_is_0(self):
        from app.evaluation.confidence import _sandbox_signal
        assert _sandbox_signal(-1) == 0.0

    def test_sandbox_none_signal_is_neutral(self):
        from app.evaluation.confidence import _sandbox_signal
        val = _sandbox_signal(None)
        assert 0.5 <= val <= 0.65  # neutral range

    def test_sandbox_other_code_signal_is_0(self):
        from app.evaluation.confidence import _sandbox_signal
        assert _sandbox_signal(127) == 0.0


# ===========================================================================
# TestConfidenceValidation
# ===========================================================================

class TestConfidenceValidation:
    def test_zero_warnings_signal_is_1(self):
        from app.evaluation.confidence import _validation_signal
        assert _validation_signal(0) == 1.0

    def test_one_warning_signal_is_0_8(self):
        from app.evaluation.confidence import _validation_signal
        assert _validation_signal(1) == 0.80

    def test_two_warnings_signal_is_0_6(self):
        from app.evaluation.confidence import _validation_signal
        assert _validation_signal(2) == 0.60

    def test_three_warnings_signal_is_0_4(self):
        from app.evaluation.confidence import _validation_signal
        assert _validation_signal(3) == 0.40

    def test_four_warnings_signal_is_0_2(self):
        from app.evaluation.confidence import _validation_signal
        assert _validation_signal(4) == 0.20

    def test_five_or_more_warnings_signal_is_0(self):
        from app.evaluation.confidence import _validation_signal
        assert _validation_signal(5) == 0.0
        assert _validation_signal(100) == 0.0


# ===========================================================================
# TestConfidenceTestCount
# ===========================================================================

class TestConfidenceTestCount:
    def test_ideal_range_6_to_12_is_1(self):
        from app.evaluation.confidence import _test_count_signal
        for n in range(6, 13):
            assert _test_count_signal(n) == 1.0, f"failed for count={n}"

    def test_acceptable_range_3_to_5_is_0_7(self):
        from app.evaluation.confidence import _test_count_signal
        for n in (3, 4, 5):
            assert _test_count_signal(n) == 0.70

    def test_acceptable_range_13_to_20_is_0_7(self):
        from app.evaluation.confidence import _test_count_signal
        for n in (13, 20):
            assert _test_count_signal(n) == 0.70

    def test_sparse_range_1_2_is_0_4(self):
        from app.evaluation.confidence import _test_count_signal
        assert _test_count_signal(1) == 0.40
        assert _test_count_signal(2) == 0.40

    def test_bloated_range_21_to_30_is_0_4(self):
        from app.evaluation.confidence import _test_count_signal
        assert _test_count_signal(25) == 0.40

    def test_zero_tests_is_0(self):
        from app.evaluation.confidence import _test_count_signal
        assert _test_count_signal(0) == 0.0

    def test_over_30_is_0(self):
        from app.evaluation.confidence import _test_count_signal
        assert _test_count_signal(31) == 0.0


# ===========================================================================
# TestConfidenceGrades
# ===========================================================================

class TestConfidenceGrades:
    def test_score_0_9_is_high(self):
        from app.evaluation.confidence import _grade
        assert _grade(0.90) == "HIGH"

    def test_score_0_8_is_high_boundary(self):
        from app.evaluation.confidence import _grade
        assert _grade(0.80) == "HIGH"

    def test_score_0_79_is_medium(self):
        from app.evaluation.confidence import _grade
        assert _grade(0.79) == "MEDIUM"

    def test_score_0_55_is_medium_boundary(self):
        from app.evaluation.confidence import _grade
        assert _grade(0.55) == "MEDIUM"

    def test_score_0_54_is_low(self):
        from app.evaluation.confidence import _grade
        assert _grade(0.54) == "LOW"

    def test_score_0_is_low(self):
        from app.evaluation.confidence import _grade
        assert _grade(0.0) == "LOW"


# ===========================================================================
# TestConfidenceOverall
# ===========================================================================

class TestConfidenceOverall:
    def test_perfect_score_is_1(self):
        from app.evaluation.confidence import calculate_confidence
        score = calculate_confidence(
            test_count=8,
            validation_warnings=[],
            sandbox_exit_code=0,
        )
        assert score.overall == pytest.approx(1.0)
        assert score.grade == "HIGH"

    def test_all_zero_score_is_0(self):
        from app.evaluation.confidence import calculate_confidence
        score = calculate_confidence(
            test_count=0,
            validation_warnings=["w"] * 10,
            sandbox_exit_code=-1,
        )
        assert score.overall == pytest.approx(0.0)
        assert score.grade == "LOW"

    def test_weighted_combination(self):
        from app.evaluation.confidence import calculate_confidence
        # sandbox=1.0 (0.40), validation=1.0 (0.30), test_count=1.0 (0.30)
        score = calculate_confidence(
            test_count=8,
            validation_warnings=[],
            sandbox_exit_code=0,
        )
        expected = 0.40 * 1.0 + 0.30 * 1.0 + 0.30 * 1.0
        assert score.overall == pytest.approx(expected)

    def test_result_is_immutable(self):
        from app.evaluation.confidence import calculate_confidence
        score = calculate_confidence(8, [], 0)
        with pytest.raises((AttributeError, TypeError)):
            score.overall = 0.5  # type: ignore

    def test_to_dict_contains_required_keys(self):
        from app.evaluation.confidence import calculate_confidence
        score = calculate_confidence(8, [], 0)
        d = score.to_dict()
        assert "overall" in d
        assert "grade" in d
        assert "signals" in d
        assert "metadata" in d

    def test_score_clamped_to_0_1(self):
        from app.evaluation.confidence import calculate_confidence
        score = calculate_confidence(8, [], 0)
        assert 0.0 <= score.overall <= 1.0

    def test_deterministic_same_inputs_same_output(self):
        from app.evaluation.confidence import calculate_confidence
        a = calculate_confidence(6, ["warn1"], 1)
        b = calculate_confidence(6, ["warn1"], 1)
        assert a.overall == b.overall
        assert a.grade == b.grade


# ===========================================================================
# TestConfidenceEdgeCases
# ===========================================================================

class TestConfidenceEdgeCases:
    def test_no_sandbox_partial_score(self):
        from app.evaluation.confidence import calculate_confidence
        score = calculate_confidence(8, [], None)
        # sandbox_signal=0.60, validation=1.0, test_count=1.0
        expected = 0.40 * 0.60 + 0.30 * 1.0 + 0.30 * 1.0
        assert score.overall == pytest.approx(expected)

    def test_metadata_preserved(self):
        from app.evaluation.confidence import calculate_confidence
        score = calculate_confidence(5, ["w1", "w2"], 1)
        assert score.test_count == 5
        assert score.warning_count == 2
        assert score.sandbox_exit_code == 1


# ===========================================================================
# TestGoldenDatasetRecord
# ===========================================================================

class TestGoldenDatasetRecord:
    def test_from_dict_minimal(self):
        from app.evaluation.golden_dataset import GoldenRecord
        r = GoldenRecord.from_dict({"name": "my_func"})
        assert r.name == "my_func"
        assert r.min_test_count == 4
        assert r.max_test_count == 20
        assert r.required_categories == []
        assert r.required_test_names == []

    def test_from_dict_full(self):
        from app.evaluation.golden_dataset import GoldenRecord
        r = GoldenRecord.from_dict({
            "name": "calc",
            "min_test_count": 3,
            "max_test_count": 10,
            "required_categories": ["happy_path"],
            "required_test_names": ["test_basic"],
            "notes": "Check rounding",
        })
        assert r.min_test_count == 3
        assert r.max_test_count == 10
        assert r.required_categories == ["happy_path"]
        assert r.required_test_names == ["test_basic"]
        assert r.notes == "Check rounding"

    def test_from_dict_missing_name_raises(self):
        from app.evaluation.golden_dataset import GoldenRecord
        with pytest.raises((KeyError, TypeError)):
            GoldenRecord.from_dict({"min_test_count": 4})


# ===========================================================================
# TestGoldenDatasetLoad
# ===========================================================================

class TestGoldenDatasetLoad:
    def test_load_valid_file(self):
        from app.evaluation.golden_dataset import load_golden_dataset
        data = [{"name": "my_func", "required_categories": ["happy_path"]}]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name
        try:
            records = load_golden_dataset(path)
            assert len(records) == 1
            assert records[0].name == "my_func"
        finally:
            os.unlink(path)

    def test_load_missing_file_raises(self):
        from app.evaluation.golden_dataset import load_golden_dataset
        with pytest.raises(FileNotFoundError):
            load_golden_dataset("/nonexistent/path/golden.json")

    def test_load_non_array_raises(self):
        from app.evaluation.golden_dataset import load_golden_dataset
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"name": "oops"}, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="JSON array"):
                load_golden_dataset(path)
        finally:
            os.unlink(path)

    def test_load_invalid_record_raises(self):
        from app.evaluation.golden_dataset import load_golden_dataset
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump([{"not_a_name_field": True}], f)
            path = f.name
        try:
            with pytest.raises(ValueError):
                load_golden_dataset(path)
        finally:
            os.unlink(path)


# ===========================================================================
# TestGoldenEvaluator
# ===========================================================================

class TestGoldenEvaluator:
    def _make_mock_result(
        self,
        test_cases=None,
        warnings=None,
        sandbox_exit=None,
    ):
        """Create a duck-type compatible result object."""
        class TC:
            def __init__(self, name, category):
                self.name = name
                self.category = category

        class TS:
            def __init__(self, cases):
                self.test_cases = cases

        class SR:
            def __init__(self, code):
                self.exit_code = code

        class Result:
            def __init__(self, tc, w, se):
                self.test_suite = TS([TC(n, c) for n, c in tc])
                self.validation_warnings = w or []
                self.sandbox_result = SR(se) if se is not None else None

        tc = test_cases or [
            ("test_happy", "happy_path"),
            ("test_edge", "edge_case"),
            ("test_basic", "happy_path"),
            ("test_boundary", "boundary"),
            ("test_error", "error_handling"),
            ("test_zero", "boundary"),
            ("test_neg", "edge_case"),
            ("test_max", "happy_path"),
        ]
        return Result(tc, warnings, sandbox_exit)

    def _make_golden(self, **kwargs):
        from app.evaluation.golden_dataset import GoldenRecord
        return GoldenRecord(name="test_func", **kwargs)

    def test_all_criteria_pass(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator
        result = self._make_mock_result()
        golden = self._make_golden(
            min_test_count=4,
            max_test_count=12,
            required_categories=["happy_path", "edge_case"],
            required_test_names=["test_happy"],
        )
        evaluator = GoldenDatasetEvaluator([golden])
        report = evaluator.evaluate(result)
        assert report.total == 1
        assert report.passed == 1
        assert report.failed == 0
        assert report.pass_rate == 1.0
        assert report.results[0].passed is True

    def test_count_too_low_fails(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator, GoldenRecord
        result = self._make_mock_result(test_cases=[("test_a", "happy_path")])
        golden = GoldenRecord(name="f", min_test_count=5, max_test_count=20)
        evaluator = GoldenDatasetEvaluator([golden])
        report = evaluator.evaluate(result)
        assert report.results[0].passed is False
        assert not report.results[0].count_in_range

    def test_missing_required_category_fails(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator, GoldenRecord
        result = self._make_mock_result(
            test_cases=[("t1", "happy_path")] * 6
        )
        golden = GoldenRecord(
            name="f",
            min_test_count=1,
            max_test_count=20,
            required_categories=["edge_case"],  # not in result
        )
        evaluator = GoldenDatasetEvaluator([golden])
        report = evaluator.evaluate(result)
        assert not report.results[0].passed
        assert "edge_case" in report.results[0].missing_categories

    def test_missing_required_name_fails(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator, GoldenRecord
        result = self._make_mock_result()
        golden = GoldenRecord(
            name="f",
            min_test_count=1,
            max_test_count=20,
            required_test_names=["test_nonexistent"],
        )
        evaluator = GoldenDatasetEvaluator([golden])
        report = evaluator.evaluate(result)
        assert not report.results[0].passed
        assert "test_nonexistent" in report.results[0].missing_required_names

    def test_report_aggregate_multiple_golden_records(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator, GoldenRecord
        result = self._make_mock_result()
        golden_pass = GoldenRecord(name="pass", min_test_count=1, max_test_count=20)
        golden_fail = GoldenRecord(name="fail", min_test_count=100, max_test_count=200)
        evaluator = GoldenDatasetEvaluator([golden_pass, golden_fail])
        report = evaluator.evaluate(result)
        assert report.total == 2
        assert report.passed == 1
        assert report.failed == 1
        assert report.pass_rate == 0.5

    def test_report_to_dict_structure(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator, GoldenRecord
        result = self._make_mock_result()
        golden = GoldenRecord(name="f", min_test_count=1, max_test_count=20)
        evaluator = GoldenDatasetEvaluator([golden])
        report = evaluator.evaluate(result)
        d = report.to_dict()
        assert "total" in d
        assert "passed" in d
        assert "failed" in d
        assert "pass_rate" in d
        assert "results" in d
        assert "summary" in d

    def test_summary_contains_confidence(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator, GoldenRecord
        result = self._make_mock_result()
        evaluator = GoldenDatasetEvaluator([GoldenRecord(name="f")])
        report = evaluator.evaluate(result)
        assert "confidence_score" in report.summary
        assert "confidence_grade" in report.summary

    def test_empty_golden_records(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator
        result = self._make_mock_result()
        evaluator = GoldenDatasetEvaluator([])
        report = evaluator.evaluate(result)
        assert report.total == 0
        assert report.pass_rate == 0.0


# ===========================================================================
# TestGoldenEvaluatorDict
# ===========================================================================

class TestGoldenEvaluatorDict:
    def test_evaluate_dict_pass(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator, GoldenRecord
        golden = GoldenRecord(name="f", min_test_count=2, max_test_count=10,
                              required_categories=["happy_path"])
        evaluator = GoldenDatasetEvaluator([golden])
        artifacts = {
            "test_cases": [
                {"name": "test_a", "category": "happy_path"},
                {"name": "test_b", "category": "edge_case"},
                {"name": "test_c", "category": "happy_path"},
            ],
            "validation_warnings": [],
            "sandbox_exit_code": 0,
        }
        report = evaluator.evaluate_dict(artifacts)
        assert report.results[0].passed is True

    def test_evaluate_dict_fail_count(self):
        from app.evaluation.golden_dataset import GoldenDatasetEvaluator, GoldenRecord
        golden = GoldenRecord(name="f", min_test_count=10, max_test_count=20)
        evaluator = GoldenDatasetEvaluator([golden])
        artifacts = {"test_cases": [{"name": "t", "category": "happy_path"}],
                     "validation_warnings": [], "sandbox_exit_code": None}
        report = evaluator.evaluate_dict(artifacts)
        assert not report.results[0].passed


# ===========================================================================
# TestCacheFallback
# ===========================================================================

class TestCacheFallback:
    """Verify that GenerationService works correctly when no cache_manager is set."""

    def test_no_cache_manager_runs_pipeline(self):
        """Without cache_manager, generate() always runs the pipeline."""
        from app.services.generation_service import GenerationService

        mock_repo = MagicMock()
        record = MagicMock()
        record.id = "gen-abc"
        mock_repo.create.return_value = record
        mock_repo.get_by_id.return_value = record
        mock_repo.update.return_value = record

        svc = GenerationService(
            repository=mock_repo,
            llm_provider=MagicMock(),
            cache_manager=None,       # explicitly no cache
        )
        svc._analyser = MagicMock()
        svc._analyser.analyse.return_value = MagicMock(function_name="f")
        svc._prompt_builder = MagicMock()
        from app.domain.prompt_payload import PromptPayload
        svc._prompt_builder.build.return_value = PromptPayload(
            system_prompt="s", developer_prompt="d", user_prompt=""
        )
        svc._llm_provider.generate.return_value = (
            '{"function_name":"f","test_cases":[],"imports":[],"setup_code":null}'
        )
        from app.domain.test_suite import TestSuite
        fake_ts = TestSuite(function_name="f", test_cases=[], imports=[], setup_code=None)
        svc._response_parser = MagicMock()
        svc._response_parser.parse.return_value = fake_ts
        svc._schema_validator = MagicMock(); svc._schema_validator.validate.return_value = []
        svc._semantic_validator = MagicMock(); svc._semantic_validator.validate.return_value = []
        svc._business_validator = MagicMock(); svc._business_validator.validate.return_value = []
        svc._code_generator = MagicMock(); svc._code_generator.generate.return_value = "# code"

        with patch("app.services.generation_service.settings") as s:
            s.MAX_SOURCE_CODE_SIZE = 100000
            s.MAX_SPECIFICATION_SIZE = 10000
            s.PROMPT_VERSION = "v1"
            s.ARCHITECTURE_VERSION = "2.1"
            s.ENABLE_SANDBOX = False
            s.ENABLE_L1_CACHE = False
            s.ENABLE_L2_CACHE = False
            result = svc.generate("def f(): pass")

        # LLM provider was called (pipeline ran)
        svc._llm_provider.generate.assert_called_once()

    def test_cache_manager_with_hit_skips_pipeline(self):
        """With cache_manager returning a hit, LLM is never called."""
        from app.cache.l1_cache import L1Cache
        from app.cache.manager import CacheManager
        from app.cache.keys import compute_cache_key
        from app.services.generation_service import GenerationService
        from app.core.config import settings as real_settings

        l1 = L1Cache(max_size=10, ttl_seconds=3600)
        mgr = CacheManager(l1=l1, cache_repo=None)

        mock_repo = MagicMock()
        record = MagicMock(); record.id = "gen-xyz"
        mock_repo.create.return_value = record
        mock_repo.get_by_id.return_value = record

        mock_llm = MagicMock()

        svc = GenerationService(
            repository=mock_repo,
            llm_provider=mock_llm,
            cache_manager=mgr,
        )

        # Seed L1 using real settings.PROMPT_VERSION (same value used by generate())
        cache_key = compute_cache_key(
            "def f(): pass", None, "python", "pytest",
            real_settings.PROMPT_VERSION,
        )
        l1.set(cache_key, {
            "generated_tests_json": '{"test_cases":[]}',
            "generated_tests_code": "# cached",
        })

        # Patch settings in BOTH modules that read it during this call
        with patch("app.services.generation_service.settings") as svc_s, \
             patch("app.cache.manager.settings") as mgr_s:
            svc_s.MAX_SOURCE_CODE_SIZE = 100000
            svc_s.MAX_SPECIFICATION_SIZE = 10000
            svc_s.PROMPT_VERSION = real_settings.PROMPT_VERSION
            svc_s.ARCHITECTURE_VERSION = "2.1"
            svc_s.ENABLE_L1_CACHE = True
            svc_s.ENABLE_L2_CACHE = False
            mgr_s.ENABLE_L1_CACHE = True
            mgr_s.ENABLE_L2_CACHE = False
            svc.generate("def f(): pass")

        # LLM must NOT have been called
        mock_llm.generate.assert_not_called()

