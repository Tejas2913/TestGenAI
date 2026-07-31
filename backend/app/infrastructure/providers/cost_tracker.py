"""TestGen AI v2.4.0 — Provider Cost Tracker

In-process, thread-safe cost accumulation for all LLM providers.

Tracks:
  - Per-provider cumulative cost
  - Daily cost (resets at UTC midnight)
  - Monthly cost (resets at UTC month boundary)
  - Per-workflow cost
  - Average cost per request

State resets on application restart (v2.4 scope).
"""

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class CostRecord:
    """Atomic record for a single provider invocation's cost."""
    provider_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    timestamp: datetime
    workflow_id: Optional[str] = None


class ProviderCostTracker:
    """In-process cost tracker for all LLM providers.

    Thread-safe. All state is in-memory only (v2.4 scope).

    Usage:
        tracker = ProviderCostTracker()
        tracker.record("Gemini", prompt_tokens=200, completion_tokens=150, cost_usd=0.00012)
        summary = tracker.get_summary()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # provider_name → cumulative totals
        self._cumulative_cost: Dict[str, float] = defaultdict(float)
        self._cumulative_prompt_tokens: Dict[str, int] = defaultdict(int)
        self._cumulative_completion_tokens: Dict[str, int] = defaultdict(int)
        self._cumulative_requests: Dict[str, int] = defaultdict(int)
        # daily / monthly accumulators
        self._daily_cost: Dict[str, float] = defaultdict(float)
        self._monthly_cost: Dict[str, float] = defaultdict(float)
        self._daily_date: Optional[str] = None       # "YYYY-MM-DD"
        self._monthly_month: Optional[str] = None    # "YYYY-MM"
        # per-workflow cost
        self._workflow_costs: Dict[str, float] = defaultdict(float)
        # history (last 1000 records)
        self._history: list = []
        self._MAX_HISTORY = 1_000

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        provider_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        workflow_id: Optional[str] = None,
    ) -> None:
        """Record cost for a single provider invocation."""
        now = datetime.now(timezone.utc)
        total_tokens = prompt_tokens + completion_tokens

        with self._lock:
            self._maybe_reset_daily(now)
            self._maybe_reset_monthly(now)

            self._cumulative_cost[provider_name] += cost_usd
            self._cumulative_prompt_tokens[provider_name] += prompt_tokens
            self._cumulative_completion_tokens[provider_name] += completion_tokens
            self._cumulative_requests[provider_name] += 1
            self._daily_cost[provider_name] += cost_usd
            self._monthly_cost[provider_name] += cost_usd

            if workflow_id:
                self._workflow_costs[workflow_id] += cost_usd

            record = CostRecord(
                provider_name=provider_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                timestamp=now,
                workflow_id=workflow_id,
            )
            self._history.append(record)
            if len(self._history) > self._MAX_HISTORY:
                self._history.pop(0)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def total_cost(self, provider_name: Optional[str] = None) -> float:
        """Return cumulative cost for one provider or all providers."""
        with self._lock:
            if provider_name:
                return round(self._cumulative_cost.get(provider_name, 0.0), 8)
            return round(sum(self._cumulative_cost.values()), 8)

    def daily_cost(self, provider_name: Optional[str] = None) -> float:
        """Return today's cost for one provider or all providers."""
        with self._lock:
            if provider_name:
                return round(self._daily_cost.get(provider_name, 0.0), 8)
            return round(sum(self._daily_cost.values()), 8)

    def monthly_cost(self, provider_name: Optional[str] = None) -> float:
        """Return this month's cost for one provider or all providers."""
        with self._lock:
            if provider_name:
                return round(self._monthly_cost.get(provider_name, 0.0), 8)
            return round(sum(self._monthly_cost.values()), 8)

    def workflow_cost(self, workflow_id: str) -> float:
        """Return total cost for a specific workflow run."""
        with self._lock:
            return round(self._workflow_costs.get(workflow_id, 0.0), 8)

    def average_cost_per_request(self, provider_name: Optional[str] = None) -> float:
        """Return average cost per request for one or all providers."""
        with self._lock:
            if provider_name:
                total = self._cumulative_cost.get(provider_name, 0.0)
                count = self._cumulative_requests.get(provider_name, 0)
                return round(total / count, 8) if count > 0 else 0.0
            total = sum(self._cumulative_cost.values())
            count = sum(self._cumulative_requests.values())
            return round(total / count, 8) if count > 0 else 0.0

    def get_summary(self) -> dict:
        """Return full cost summary across all providers."""
        with self._lock:
            providers = sorted(set(
                list(self._cumulative_cost.keys()) +
                list(self._daily_cost.keys())
            ))
            per_provider = {}
            for name in providers:
                reqs = self._cumulative_requests.get(name, 0)
                cum = self._cumulative_cost.get(name, 0.0)
                per_provider[name] = {
                    "total_requests": reqs,
                    "cumulative_cost_usd": round(cum, 8),
                    "daily_cost_usd": round(self._daily_cost.get(name, 0.0), 8),
                    "monthly_cost_usd": round(self._monthly_cost.get(name, 0.0), 8),
                    "avg_cost_per_request_usd": round(cum / reqs, 8) if reqs > 0 else 0.0,
                    "total_prompt_tokens": self._cumulative_prompt_tokens.get(name, 0),
                    "total_completion_tokens": self._cumulative_completion_tokens.get(name, 0),
                }
            return {
                "grand_total_usd": round(sum(self._cumulative_cost.values()), 8),
                "daily_total_usd": round(sum(self._daily_cost.values()), 8),
                "monthly_total_usd": round(sum(self._monthly_cost.values()), 8),
                "total_requests": sum(self._cumulative_requests.values()),
                "per_provider": per_provider,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_reset_daily(self, now: datetime) -> None:
        today = now.strftime("%Y-%m-%d")
        if self._daily_date != today:
            self._daily_cost.clear()
            self._daily_date = today

    def _maybe_reset_monthly(self, now: datetime) -> None:
        month = now.strftime("%Y-%m")
        if self._monthly_month != month:
            self._monthly_cost.clear()
            self._monthly_month = month

    def reset(self) -> None:
        """Reset all tracked costs. Useful for tests."""
        with self._lock:
            self._cumulative_cost.clear()
            self._cumulative_prompt_tokens.clear()
            self._cumulative_completion_tokens.clear()
            self._cumulative_requests.clear()
            self._daily_cost.clear()
            self._monthly_cost.clear()
            self._workflow_costs.clear()
            self._history.clear()
            self._daily_date = None
            self._monthly_month = None
