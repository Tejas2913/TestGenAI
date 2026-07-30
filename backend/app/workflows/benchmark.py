"""TestGen AI v2.3 — Benchmark Utility

Measures workflow throughput, average latencies, token usage, repair frequency,
approval rates, and provider utilization across multiple pipeline executions.
"""

import statistics
import time
from dataclasses import dataclass, field
from typing import List, Optional
import structlog

from app.domain.v23_generation_result import V23GenerationResult
from app.domain.v23_models import GenerationRequest
from app.workflows.v23_pipeline import V23Pipeline

logger = structlog.get_logger()

BENCHMARK_SOURCE = """\
def add(a: int, b: int) -> int:
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Both arguments must be integers")
    return a + b

def divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b

def find_max(values: list) -> float:
    if not values:
        raise ValueError("Input list is empty")
    return max(values)
"""


@dataclass
class BenchmarkResult:
    """Container for aggregated benchmark metrics across N runs."""

    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    # Latency (ms)
    avg_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0

    # Throughput
    throughput_rps: float = 0.0

    # Token Usage
    avg_prompt_tokens: float = 0.0
    avg_completion_tokens: float = 0.0
    avg_total_tokens: float = 0.0
    total_estimated_cost_usd: float = 0.0

    # Quality
    avg_review_score: float = 0.0
    approval_rate_pct: float = 0.0
    avg_repair_count: float = 0.0
    repair_frequency_pct: float = 0.0
    avg_generated_tests: float = 0.0

    # Provider utilization
    provider_utilization: dict = field(default_factory=dict)

    # Raw results list (not serialised in report by default)
    raw_results: List[V23GenerationResult] = field(default_factory=list)


class WorkflowBenchmark:
    """Benchmarks the TestGen AI v2.3 multi-agent pipeline."""

    def __init__(self, pipeline: Optional[V23Pipeline] = None) -> None:
        self.pipeline = pipeline or V23Pipeline()
        self.log = logger.bind(component="WorkflowBenchmark")

    def run(self, n_runs: int = 5, source_code: Optional[str] = None) -> BenchmarkResult:
        """Execute N pipeline runs and collect aggregate performance metrics.

        Args:
            n_runs: Number of benchmark iterations.
            source_code: Optional custom source code; defaults to BENCHMARK_SOURCE.

        Returns:
            BenchmarkResult with aggregate statistics.
        """
        src = source_code or BENCHMARK_SOURCE
        results: List[V23GenerationResult] = []
        latencies: List[float] = []

        self.log.info("benchmark_started", n_runs=n_runs)
        wall_start = time.perf_counter()

        for i in range(n_runs):
            req = GenerationRequest(source_code=src, user_id=f"benchmark-run-{i}")
            try:
                result = self.pipeline.run(req, request_id=f"bench-{i}")
                results.append(result)
                latencies.append(result.total_execution_ms)
            except Exception as exc:
                self.log.warning("benchmark_run_failed", run=i, error=str(exc))

        total_wall_ms = (time.perf_counter() - wall_start) * 1000

        if not results:
            self.log.error("benchmark_all_runs_failed")
            return BenchmarkResult(run_count=n_runs, failure_count=n_runs)

        success_count = len([r for r in results if r.status == "completed"])
        failure_count = n_runs - success_count

        # Latency stats
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else max_latency
        throughput = round(success_count / (total_wall_ms / 1000), 2) if total_wall_ms > 0 else 0.0

        # Token stats
        avg_prompt_tok = statistics.mean(r.total_prompt_tokens for r in results) if results else 0
        avg_comp_tok = statistics.mean(r.total_completion_tokens for r in results) if results else 0
        avg_total_tok = statistics.mean(r.total_tokens for r in results) if results else 0
        total_cost = sum(r.estimated_cost_usd for r in results)

        # Quality stats
        avg_score = statistics.mean(r.analytics.review_score for r in results) if results else 0.0
        approved_count = sum(1 for r in results if r.analytics.approved)
        approval_rate = round(approved_count / len(results) * 100, 1) if results else 0.0
        avg_repair = statistics.mean(r.repair_count for r in results) if results else 0.0
        repaired_count = sum(1 for r in results if r.repair_count > 0)
        repair_freq = round(repaired_count / len(results) * 100, 1) if results else 0.0
        avg_tests = statistics.mean(r.generated_test_count for r in results) if results else 0.0

        # Provider utilization
        provider_util: dict = {}
        for r in results:
            prov = r.analytics.provider_used
            provider_util[prov] = provider_util.get(prov, 0) + 1

        bm = BenchmarkResult(
            run_count=n_runs,
            success_count=success_count,
            failure_count=failure_count,
            avg_latency_ms=round(avg_latency, 2),
            min_latency_ms=round(min_latency, 2),
            max_latency_ms=round(max_latency, 2),
            p95_latency_ms=round(p95_latency, 2),
            throughput_rps=throughput,
            avg_prompt_tokens=round(avg_prompt_tok, 1),
            avg_completion_tokens=round(avg_comp_tok, 1),
            avg_total_tokens=round(avg_total_tok, 1),
            total_estimated_cost_usd=round(total_cost, 6),
            avg_review_score=round(avg_score, 2),
            approval_rate_pct=approval_rate,
            avg_repair_count=round(avg_repair, 2),
            repair_frequency_pct=repair_freq,
            avg_generated_tests=round(avg_tests, 2),
            provider_utilization=provider_util,
            raw_results=results,
        )

        self.log.info(
            "benchmark_completed",
            n_runs=n_runs,
            success_count=success_count,
            avg_latency_ms=bm.avg_latency_ms,
            throughput_rps=bm.throughput_rps,
            avg_review_score=bm.avg_review_score,
        )
        return bm

    def generate_report(self, result: BenchmarkResult) -> str:
        """Generate a human-readable benchmark report string."""
        lines = [
            "=" * 60,
            "  TestGen AI v2.3 — Workflow Benchmark Report",
            "=" * 60,
            f"  Runs:              {result.run_count}",
            f"  Success:           {result.success_count}",
            f"  Failures:          {result.failure_count}",
            "",
            "  Latency (ms)",
            f"    Average:         {result.avg_latency_ms} ms",
            f"    Min:             {result.min_latency_ms} ms",
            f"    Max:             {result.max_latency_ms} ms",
            f"    P95:             {result.p95_latency_ms} ms",
            "",
            "  Throughput",
            f"    Requests/sec:    {result.throughput_rps}",
            "",
            "  Token Usage (avg per run)",
            f"    Prompt Tokens:   {result.avg_prompt_tokens}",
            f"    Completion Tok:  {result.avg_completion_tokens}",
            f"    Total Tokens:    {result.avg_total_tokens}",
            f"    Total Cost USD:  ${result.total_estimated_cost_usd:.6f}",
            "",
            "  Quality",
            f"    Avg Review Score: {result.avg_review_score}/100",
            f"    Approval Rate:    {result.approval_rate_pct}%",
            f"    Repair Frequency: {result.repair_frequency_pct}%",
            f"    Avg Tests/Run:    {result.avg_generated_tests}",
            "",
            "  Provider Utilization",
        ]
        for prov, count in result.provider_utilization.items():
            pct = round(count / result.run_count * 100, 1)
            lines.append(f"    {prov}: {count} runs ({pct}%)")
        lines.append("=" * 60)
        return "\n".join(lines)
