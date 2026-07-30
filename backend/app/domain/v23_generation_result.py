"""TestGen AI v2.3 — GenerationResult Domain Model

Comprehensive end-to-end pipeline result containing all workflow artifacts,
analytics, provider decisions, quality metrics, and execution metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class WorkflowStageLatency:
    """Per-agent latency counters collected during workflow execution."""

    repository_context_ms: float = 0.0
    planning_ms: float = 0.0
    generation_ms: float = 0.0
    review_ms: float = 0.0
    repair_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class WorkflowAnalytics:
    """Aggregated analytics collected across the full multi-agent workflow."""

    latency: WorkflowStageLatency = field(default_factory=WorkflowStageLatency)

    # Provider telemetry
    provider_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Quality & Repair metrics
    review_score: float = 0.0
    approved: bool = True
    repair_count: int = 0
    generated_test_count: int = 0
    issue_count: int = 0


@dataclass
class V23GenerationResult:
    """Final output of the complete TestGen AI v2.3 multi-agent pipeline.

    Aggregates all workflow artifacts, quality metrics, provider decisions,
    analytics telemetry, and structured representations of generated tests.
    """

    # Identity
    workflow_id: str
    request_id: str
    status: str  # "completed" | "failed" | "partial"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Core Pipeline Outputs
    source_code_summary: str = ""
    repository_metadata: Dict[str, Any] = field(default_factory=dict)
    test_plan_summary: Dict[str, Any] = field(default_factory=dict)

    # Generated Tests
    generated_tests: List[Dict[str, Any]] = field(default_factory=list)
    generated_test_count: int = 0

    # Review Feedback
    review_report: Optional[Dict[str, Any]] = None

    # Repair History
    repair_history: List[Dict[str, Any]] = field(default_factory=list)
    repair_count: int = 0

    # Provider Decisions
    provider_decisions: List[Dict[str, Any]] = field(default_factory=list)

    # Analytics
    analytics: WorkflowAnalytics = field(default_factory=WorkflowAnalytics)

    # Token Usage
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # Execution Time
    total_execution_ms: float = 0.0
    workflow_status: str = "completed"

    # Failure Information
    failure_reason: Optional[str] = None
    failure_agent: Optional[str] = None

    # Reasoning Traces
    reasoning_traces: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to JSON-compatible dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "request_id": self.request_id,
            "status": self.status,
            "created_at": self.created_at,
            "source_code_summary": self.source_code_summary,
            "repository_metadata": self.repository_metadata,
            "test_plan_summary": self.test_plan_summary,
            "generated_tests": self.generated_tests,
            "generated_test_count": self.generated_test_count,
            "review_report": self.review_report,
            "repair_history": self.repair_history,
            "repair_count": self.repair_count,
            "provider_decisions": self.provider_decisions,
            "analytics": {
                "latency": {
                    "planning_ms": self.analytics.latency.planning_ms,
                    "generation_ms": self.analytics.latency.generation_ms,
                    "review_ms": self.analytics.latency.review_ms,
                    "repair_ms": self.analytics.latency.repair_ms,
                    "total_ms": self.analytics.latency.total_ms,
                },
                "provider_used": self.analytics.provider_used,
                "prompt_tokens": self.analytics.prompt_tokens,
                "completion_tokens": self.analytics.completion_tokens,
                "total_tokens": self.analytics.total_tokens,
                "estimated_cost_usd": self.analytics.estimated_cost_usd,
                "review_score": self.analytics.review_score,
                "approved": self.analytics.approved,
                "repair_count": self.analytics.repair_count,
                "generated_test_count": self.analytics.generated_test_count,
                "issue_count": self.analytics.issue_count,
            },
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "total_execution_ms": self.total_execution_ms,
            "workflow_status": self.workflow_status,
            "failure_reason": self.failure_reason,
            "failure_agent": self.failure_agent,
            "reasoning_traces": self.reasoning_traces,
        }
