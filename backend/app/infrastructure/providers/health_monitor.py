"""TestGen AI v2.4.0 — Provider Health Monitor

In-process, thread-safe health tracking for all LLM providers.

State resets on application restart (v2.4 scope).
Persistence can be added in v3.0 if needed.

Usage:
    monitor = ProviderHealthMonitor()
    monitor.record_outcome("Gemini", success=True, latency_ms=320.0)
    summary = monitor.get_summary("Gemini")
"""

import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Per-provider statistics bucket (mutable, protected by lock)
# ---------------------------------------------------------------------------

class _ProviderStats:
    """Mutable statistics bucket for a single provider."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.timeouts: int = 0
        self.authentication_errors: int = 0
        self.rate_limit_errors: int = 0
        self._latencies: List[float] = []   # last N latency samples
        self.last_failure: Optional[datetime] = None
        self.last_success: Optional[datetime] = None
        self.last_error_message: str = ""

    _MAX_LATENCY_SAMPLES = 200   # rolling window

    def record(
        self,
        success: bool,
        latency_ms: float,
        error_type: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self.total_requests += 1
            if success:
                self.successful_requests += 1
                self.last_success = now
            else:
                self.failed_requests += 1
                self.last_failure = now
                if error_type == "timeout":
                    self.timeouts += 1
                elif error_type == "authentication":
                    self.authentication_errors += 1
                elif error_type == "rate_limit":
                    self.rate_limit_errors += 1

            # Maintain rolling latency window
            self._latencies.append(latency_ms)
            if len(self._latencies) > self._MAX_LATENCY_SAMPLES:
                self._latencies.pop(0)

    @property
    def average_latency_ms(self) -> float:
        with self._lock:
            if not self._latencies:
                return 0.0
            return round(sum(self._latencies) / len(self._latencies), 2)

    @property
    def p95_latency_ms(self) -> float:
        with self._lock:
            if not self._latencies:
                return 0.0
            sorted_lat = sorted(self._latencies)
            idx = math.ceil(0.95 * len(sorted_lat)) - 1
            return round(sorted_lat[max(0, idx)], 2)

    @property
    def uptime_percentage(self) -> float:
        with self._lock:
            if self.total_requests == 0:
                return 100.0
            return round(100.0 * self.successful_requests / self.total_requests, 2)

    @property
    def failure_rate(self) -> float:
        with self._lock:
            if self.total_requests == 0:
                return 0.0
            return round(self.failed_requests / self.total_requests, 4)

    @property
    def health_score(self) -> float:
        """Composite 0.0–1.0 score combining uptime and latency.

        Score formula:
          0.7 × uptime_pct/100 + 0.3 × latency_factor
          where latency_factor = 1 - clamp(avg_latency / 5000, 0, 1)
        """
        uptime = self.uptime_percentage / 100.0
        avg = self.average_latency_ms
        latency_factor = max(0.0, 1.0 - avg / 5_000.0)
        return round(0.7 * uptime + 0.3 * latency_factor, 4)

    def snapshot(self) -> dict:
        """Return a JSON-serialisable snapshot."""
        with self._lock:
            return {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "timeouts": self.timeouts,
                "authentication_errors": self.authentication_errors,
                "rate_limit_errors": self.rate_limit_errors,
                "average_latency_ms": self.average_latency_ms,
                "p95_latency_ms": self.p95_latency_ms,
                "uptime_percentage": self.uptime_percentage,
                "failure_rate": self.failure_rate,
                "health_score": self.health_score,
                "last_failure": self.last_failure.isoformat() if self.last_failure else None,
                "last_success": self.last_success.isoformat() if self.last_success else None,
                "last_error_message": self.last_error_message,
            }


# ---------------------------------------------------------------------------
# Public ProviderHealthMonitor
# ---------------------------------------------------------------------------

@dataclass
class ProviderHealthSummary:
    """Snapshot of a provider's health metrics."""
    provider_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    timeouts: int
    authentication_errors: int
    rate_limit_errors: int
    average_latency_ms: float
    p95_latency_ms: float
    uptime_percentage: float
    failure_rate: float
    health_score: float
    last_failure: Optional[str]
    last_success: Optional[str]
    last_error_message: str


class ProviderHealthMonitor:
    """In-process health monitor for all registered LLM providers.

    Thread-safe. State is in-memory only and resets on restart (v2.4).

    Usage:
        monitor = ProviderHealthMonitor()
        monitor.record_outcome("Gemini", success=True, latency_ms=310.0)
        summary = monitor.get_summary("Gemini")
        score = monitor.health_score("Gemini")   # 0.0 – 1.0
    """

    def __init__(self) -> None:
        self._stats: Dict[str, _ProviderStats] = {}
        self._meta_lock = threading.Lock()

    def _get_or_create(self, provider_name: str) -> _ProviderStats:
        with self._meta_lock:
            if provider_name not in self._stats:
                self._stats[provider_name] = _ProviderStats()
            return self._stats[provider_name]

    def record_outcome(
        self,
        provider_name: str,
        success: bool,
        latency_ms: float,
        error_type: Optional[str] = None,
        error_message: str = "",
    ) -> None:
        """Record the outcome of a provider invocation.

        Args:
            provider_name: e.g. "Gemini"
            success: True if the call succeeded.
            latency_ms: Total wall-clock time for the call in milliseconds.
            error_type: One of "timeout", "authentication", "rate_limit", or None.
            error_message: Human-readable error string (stored for debugging).
        """
        stats = self._get_or_create(provider_name)
        stats.record(success=success, latency_ms=latency_ms, error_type=error_type)
        if not success and error_message:
            stats.last_error_message = error_message

    def health_score(self, provider_name: str) -> float:
        """Return composite health score 0.0 – 1.0 for the provider."""
        stats = self._stats.get(provider_name)
        if stats is None:
            return 1.0   # Unknown → assume healthy
        return stats.health_score

    def is_healthy(
        self,
        provider_name: str,
        failure_threshold: float = 0.5,
        latency_threshold_ms: float = 10_000.0,
    ) -> bool:
        """Return True if provider is within acceptable thresholds."""
        stats = self._stats.get(provider_name)
        if stats is None:
            return True  # No data = assume healthy
        return (
            stats.failure_rate <= failure_threshold
            and stats.average_latency_ms <= latency_threshold_ms
        )

    def get_summary(self, provider_name: str) -> ProviderHealthSummary:
        """Return a structured health summary for a provider."""
        stats = self._get_or_create(provider_name)
        snap = stats.snapshot()
        return ProviderHealthSummary(
            provider_name=provider_name,
            **snap,
        )

    def get_all_summaries(self) -> Dict[str, ProviderHealthSummary]:
        """Return health summaries for all providers that have been observed."""
        return {name: self.get_summary(name) for name in list(self._stats.keys())}

    def reset(self, provider_name: Optional[str] = None) -> None:
        """Reset stats. Pass provider_name to reset one, or None to reset all."""
        with self._meta_lock:
            if provider_name:
                self._stats.pop(provider_name, None)
            else:
                self._stats.clear()
