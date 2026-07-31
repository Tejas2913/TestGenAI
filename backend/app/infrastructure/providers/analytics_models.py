"""TestGen AI v2.4.0 — Provider Analytics Domain Models

Serializable models for dashboard and reporting use.
No frontend required — these are data models only.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ProviderHealthSummary:
    """Per-provider health snapshot."""
    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    authentication_errors: int = 0
    rate_limit_errors: int = 0
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    uptime_percentage: float = 100.0
    failure_rate: float = 0.0
    health_score: float = 1.0
    last_failure: Optional[str] = None
    last_success: Optional[str] = None
    last_error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProviderUsageSummary:
    """Per-provider usage statistics."""
    provider_name: str
    model_name: str
    total_requests: int = 0
    successful_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    average_latency_ms: float = 0.0
    selection_count: int = 0   # how many times routing chose this provider

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProviderCostSummary:
    """Per-provider cost accounting."""
    provider_name: str
    cumulative_cost_usd: float = 0.0
    daily_cost_usd: float = 0.0
    monthly_cost_usd: float = 0.0
    avg_cost_per_request_usd: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_requests: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProviderLatencySummary:
    """Per-provider latency statistics."""
    provider_name: str
    average_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class WorkflowProviderTrace:
    """Full per-workflow provider execution trace."""
    workflow_id: str
    request_id: str
    timestamp: str
    selected_provider: str
    fallback_provider: Optional[str]
    routing_strategy: str
    total_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    retry_count: int = 0
    success: bool = True
    error_message: str = ""
    agent_name: str = ""
    mock_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProviderAnalyticsDashboard:
    """Aggregate analytics dashboard model for all providers."""
    generated_at: str
    total_requests: int = 0
    total_cost_usd: float = 0.0
    daily_cost_usd: float = 0.0
    monthly_cost_usd: float = 0.0
    average_latency_ms: float = 0.0
    overall_success_rate: float = 1.0
    health_summaries: List[ProviderHealthSummary] = field(default_factory=list)
    usage_summaries: List[ProviderUsageSummary] = field(default_factory=list)
    cost_summaries: List[ProviderCostSummary] = field(default_factory=list)
    latency_summaries: List[ProviderLatencySummary] = field(default_factory=list)
    recent_traces: List[WorkflowProviderTrace] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_requests": self.total_requests,
            "total_cost_usd": self.total_cost_usd,
            "daily_cost_usd": self.daily_cost_usd,
            "monthly_cost_usd": self.monthly_cost_usd,
            "average_latency_ms": self.average_latency_ms,
            "overall_success_rate": self.overall_success_rate,
            "health_summaries": [h.to_dict() for h in self.health_summaries],
            "usage_summaries": [u.to_dict() for u in self.usage_summaries],
            "cost_summaries": [c.to_dict() for c in self.cost_summaries],
            "latency_summaries": [l.to_dict() for l in self.latency_summaries],
            "recent_traces": [t.to_dict() for t in self.recent_traces],
        }
