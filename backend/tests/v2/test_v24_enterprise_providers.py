"""TestGen AI v2.4.0 — Enterprise Provider Intelligence Test Suite

Comprehensive offline unit tests covering all v2.4 components.
No internet access required — all tests run in mock mode.

Coverage:
  - ProviderMetadata registry
  - ProviderRegistry capability lookup / filtering / ranking
  - ProviderHealthMonitor: recording, scoring, thresholds
  - ProviderCostTracker: cumulative, daily, monthly, workflow
  - ProviderFailoverManager: retry, non-retryable, fallback
  - StreamChunk and stream_generate() fallback
  - New routing strategies (FastestStrategy, LowestCostStrategy, etc.)
  - LLMProviderRouter v2.4 enterprise wiring
  - All 5 providers in mock mode
  - analytics_models serialization
"""

import time
import pytest
from unittest.mock import MagicMock, patch

# ─── Domain models ────────────────────────────────────────────────────────────
from app.domain.v23_models import PromptPayload, ProviderDecision

# ─── Provider metadata ────────────────────────────────────────────────────────
from app.infrastructure.providers.provider_metadata import (
    PROVIDER_METADATA, get_metadata, list_providers, filter_by_capability,
)

# ─── Provider registry ────────────────────────────────────────────────────────
from app.infrastructure.providers.provider_registry import (
    ProviderCapability, ProviderRegistry, GLOBAL_REGISTRY,
)

# ─── Health monitor ───────────────────────────────────────────────────────────
from app.infrastructure.providers.health_monitor import ProviderHealthMonitor

# ─── Cost tracker ─────────────────────────────────────────────────────────────
from app.infrastructure.providers.cost_tracker import ProviderCostTracker

# ─── Failover manager ─────────────────────────────────────────────────────────
from app.infrastructure.providers.failover import ProviderFailoverManager
from app.exceptions.v23_exceptions import (
    ProviderAuthenticationError, ProviderRateLimitError,
    ProviderTimeoutError, ProviderUnavailableError,
)

# ─── Streaming ────────────────────────────────────────────────────────────────
from app.infrastructure.providers.streaming import (
    StreamChunk, stream_from_response, collect_stream,
)

# ─── Extended routing strategies ──────────────────────────────────────────────
from app.infrastructure.routing_strategies.extended_strategies import (
    FastestStrategy, LowestCostStrategy, HighestQualityStrategy,
    ReasoningStrategy, HealthAwareStrategy,
)

# ─── Analytics models ─────────────────────────────────────────────────────────
from app.infrastructure.providers.analytics_models import (
    ProviderHealthSummary, ProviderUsageSummary, ProviderCostSummary,
    ProviderLatencySummary, WorkflowProviderTrace, ProviderAnalyticsDashboard,
)

# ─── Providers ────────────────────────────────────────────────────────────────
from app.infrastructure.providers.gemini import GeminiProvider
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.infrastructure.providers.claude import ClaudeProvider
from app.infrastructure.providers.groq_provider import GroqProvider
from app.infrastructure.providers.openrouter_provider import OpenRouterProvider
from app.infrastructure.providers.router import LLMProviderRouter

# ─── Shared fixtures ──────────────────────────────────────────────────────────

ALL_PROVIDERS = ["Gemini", "OpenAI", "Claude", "Groq", "OpenRouter"]
AVAILABLE = ALL_PROVIDERS.copy()


@pytest.fixture
def payload():
    return PromptPayload(
        template_name="test",
        rendered_system="You are a test assistant.",
        rendered_user="Generate a unit test.",
        agent_name="planner",
        estimated_tokens=100,
    )


@pytest.fixture
def mock_router():
    return LLMProviderRouter(mock_mode=True)


# =============================================================================
# Phase 2 — ProviderMetadata
# =============================================================================

class TestProviderMetadata:
    def test_all_five_providers_registered(self):
        for name in ALL_PROVIDERS:
            assert name in PROVIDER_METADATA, f"{name} missing from PROVIDER_METADATA"

    def test_list_providers_returns_sorted_names(self):
        names = list_providers()
        assert names == sorted(names)
        assert set(ALL_PROVIDERS).issubset(set(names))

    def test_get_metadata_returns_correct_object(self):
        meta = get_metadata("Gemini")
        assert meta.provider_name == "Gemini"
        assert meta.context_window > 0
        assert meta.max_output_tokens > 0
        assert 0.0 <= meta.quality_score <= 1.0

    def test_get_metadata_raises_for_unknown_provider(self):
        with pytest.raises(KeyError):
            get_metadata("UnknownProvider")

    def test_filter_by_capability_streaming(self):
        streaming = filter_by_capability("supports_streaming")
        # All 5 providers declare streaming support
        for name in ALL_PROVIDERS:
            assert name in streaming

    def test_filter_by_capability_reasoning(self):
        reasoning = filter_by_capability("supports_reasoning")
        # At minimum Gemini, OpenAI, Claude, OpenRouter support reasoning
        assert "Gemini" in reasoning
        assert "Claude" in reasoning
        assert "OpenRouter" in reasoning

    def test_groq_has_lowest_typical_latency(self):
        groq_meta = get_metadata("Groq")
        # Groq is known for extremely fast inference
        assert groq_meta.typical_latency_ms < get_metadata("Claude").typical_latency_ms

    def test_metadata_fields_are_valid(self):
        for name, meta in PROVIDER_METADATA.items():
            assert meta.estimated_input_cost >= 0
            assert meta.estimated_output_cost >= 0
            assert meta.context_window > 0
            assert meta.max_output_tokens > 0
            assert meta.availability in ("production", "beta", "experimental")


# =============================================================================
# Phase 2 — ProviderRegistry
# =============================================================================

class TestProviderRegistry:
    def setup_method(self):
        self.registry = ProviderRegistry()

    def test_get_returns_capability_for_known_provider(self):
        cap = self.registry.get("Gemini")
        assert cap is not None
        assert isinstance(cap, ProviderCapability)
        assert cap.provider_name == "Gemini"

    def test_get_returns_none_for_unknown_provider(self):
        assert self.registry.get("Mistral") is None

    def test_get_or_raise_raises_for_unknown(self):
        with pytest.raises(KeyError):
            self.registry.get_or_raise("Mistral")

    def test_all_providers_returns_sorted_list(self):
        names = self.registry.all_providers()
        assert names == sorted(names)

    def test_filter_capable_streaming(self):
        streaming = self.registry.filter_capable(AVAILABLE, "supports_streaming")
        assert set(streaming).issubset(set(AVAILABLE))
        assert len(streaming) == len(AVAILABLE)  # all 5 support streaming

    def test_filter_capable_excludes_unsupported(self):
        # Groq does not support vision
        vision = self.registry.filter_capable(AVAILABLE, "supports_vision")
        assert "Groq" not in vision
        assert "OpenRouter" not in vision

    def test_rank_by_latency_ascending(self):
        ranked = self.registry.rank_by(AVAILABLE, "typical_latency_ms", ascending=True)
        # Groq should be first (lowest latency)
        assert ranked[0] == "Groq"

    def test_rank_by_quality_descending(self):
        ranked = self.registry.rank_by(AVAILABLE, "quality_score", ascending=False)
        # Claude has highest quality score in metadata
        assert ranked[0] == "Claude"

    def test_rank_by_cost_ascending(self):
        ranked = self.registry.rank_by(AVAILABLE, "estimated_input_cost", ascending=True)
        assert len(ranked) == len(AVAILABLE)
        # Gemini or Groq should be cheapest
        assert ranked[0] in ("Gemini", "Groq", "OpenRouter")

    def test_supports_returns_true_for_valid_capability(self):
        assert self.registry.supports("Gemini", "supports_streaming") is True

    def test_supports_returns_false_for_unsupported(self):
        assert self.registry.supports("Groq", "supports_vision") is False

    def test_supports_returns_false_for_unknown_provider(self):
        assert self.registry.supports("Mistral", "supports_streaming") is False

    def test_capabilities_for_available_returns_all(self):
        caps = self.registry.capabilities_for_available(AVAILABLE)
        assert set(caps.keys()) == set(AVAILABLE)

    def test_global_registry_singleton_is_provider_registry(self):
        assert isinstance(GLOBAL_REGISTRY, ProviderRegistry)


# =============================================================================
# Phase 3 — ProviderHealthMonitor
# =============================================================================

class TestProviderHealthMonitor:
    def setup_method(self):
        self.monitor = ProviderHealthMonitor()

    def test_initial_health_score_is_1_for_unknown_provider(self):
        assert self.monitor.health_score("Gemini") == 1.0

    def test_record_success_increments_counters(self):
        self.monitor.record_outcome("Gemini", success=True, latency_ms=300.0)
        summary = self.monitor.get_summary("Gemini")
        assert summary.total_requests == 1
        assert summary.successful_requests == 1
        assert summary.failed_requests == 0

    def test_record_failure_increments_failure_counter(self):
        self.monitor.record_outcome("OpenAI", success=False, latency_ms=500.0, error_type="timeout")
        summary = self.monitor.get_summary("OpenAI")
        assert summary.failed_requests == 1
        assert summary.timeouts == 1

    def test_failure_rate_calculation(self):
        self.monitor.record_outcome("Claude", success=True, latency_ms=200.0)
        self.monitor.record_outcome("Claude", success=False, latency_ms=400.0)
        summary = self.monitor.get_summary("Claude")
        assert summary.failure_rate == pytest.approx(0.5, abs=0.01)

    def test_uptime_percentage(self):
        for _ in range(8):
            self.monitor.record_outcome("Groq", success=True, latency_ms=100.0)
        for _ in range(2):
            self.monitor.record_outcome("Groq", success=False, latency_ms=200.0)
        summary = self.monitor.get_summary("Groq")
        assert summary.uptime_percentage == pytest.approx(80.0, abs=0.1)

    def test_average_latency_calculation(self):
        for ms in [100.0, 200.0, 300.0]:
            self.monitor.record_outcome("OpenRouter", success=True, latency_ms=ms)
        summary = self.monitor.get_summary("OpenRouter")
        assert summary.average_latency_ms == pytest.approx(200.0, abs=1.0)

    def test_p95_latency_with_multiple_samples(self):
        for i in range(20):
            self.monitor.record_outcome("Gemini", success=True, latency_ms=float(i * 10))
        summary = self.monitor.get_summary("Gemini")
        assert summary.p95_latency_ms >= 150.0  # approximately 95th percentile

    def test_health_score_decreases_after_failures(self):
        for _ in range(10):
            self.monitor.record_outcome("OpenAI", success=False, latency_ms=5000.0)
        score = self.monitor.health_score("OpenAI")
        assert score < 0.5

    def test_is_healthy_returns_true_for_clean_provider(self):
        self.monitor.record_outcome("Gemini", success=True, latency_ms=300.0)
        assert self.monitor.is_healthy("Gemini") is True

    def test_is_healthy_returns_false_for_degraded_provider(self):
        for _ in range(10):
            self.monitor.record_outcome("Claude", success=False, latency_ms=500.0, error_type="rate_limit")
        assert self.monitor.is_healthy("Claude", failure_threshold=0.3) is False

    def test_get_all_summaries_returns_observed_providers(self):
        self.monitor.record_outcome("Gemini", success=True, latency_ms=300.0)
        self.monitor.record_outcome("Groq", success=True, latency_ms=150.0)
        summaries = self.monitor.get_all_summaries()
        assert "Gemini" in summaries
        assert "Groq" in summaries

    def test_reset_clears_all_stats(self):
        self.monitor.record_outcome("Gemini", success=True, latency_ms=300.0)
        self.monitor.reset()
        assert self.monitor.health_score("Gemini") == 1.0  # unknown = healthy

    def test_rate_limit_error_type_recorded(self):
        self.monitor.record_outcome("Groq", success=False, latency_ms=100.0, error_type="rate_limit")
        summary = self.monitor.get_summary("Groq")
        assert summary.rate_limit_errors == 1

    def test_auth_error_type_recorded(self):
        self.monitor.record_outcome("Claude", success=False, latency_ms=10.0, error_type="authentication")
        summary = self.monitor.get_summary("Claude")
        assert summary.authentication_errors == 1


# =============================================================================
# Phase 6 — ProviderCostTracker
# =============================================================================

class TestProviderCostTracker:
    def setup_method(self):
        self.tracker = ProviderCostTracker()

    def test_initial_total_cost_is_zero(self):
        assert self.tracker.total_cost() == 0.0

    def test_record_accumulates_cost(self):
        self.tracker.record("Gemini", 100, 50, 0.00012)
        assert self.tracker.total_cost("Gemini") == pytest.approx(0.00012, rel=1e-5)

    def test_multiple_records_accumulate(self):
        self.tracker.record("Gemini", 100, 50, 0.00012)
        self.tracker.record("Gemini", 200, 80, 0.00025)
        assert self.tracker.total_cost("Gemini") == pytest.approx(0.00037, rel=1e-4)

    def test_daily_cost_accumulates(self):
        self.tracker.record("OpenAI", 100, 50, 0.001)
        self.tracker.record("OpenAI", 100, 50, 0.001)
        assert self.tracker.daily_cost("OpenAI") == pytest.approx(0.002, rel=1e-5)

    def test_monthly_cost_accumulates(self):
        self.tracker.record("Claude", 200, 100, 0.005)
        assert self.tracker.monthly_cost("Claude") == pytest.approx(0.005, rel=1e-5)

    def test_workflow_cost_tracking(self):
        wf_id = "wf-abc-123"
        self.tracker.record("Groq", 100, 50, 0.0001, workflow_id=wf_id)
        self.tracker.record("Groq", 100, 50, 0.0001, workflow_id=wf_id)
        assert self.tracker.workflow_cost(wf_id) == pytest.approx(0.0002, rel=1e-5)

    def test_average_cost_per_request(self):
        self.tracker.record("OpenRouter", 100, 50, 0.0006)
        self.tracker.record("OpenRouter", 100, 50, 0.0004)
        avg = self.tracker.average_cost_per_request("OpenRouter")
        assert avg == pytest.approx(0.0005, rel=1e-4)

    def test_grand_total_across_all_providers(self):
        self.tracker.record("Gemini", 100, 50, 0.0001)
        self.tracker.record("OpenAI", 100, 50, 0.001)
        assert self.tracker.total_cost() == pytest.approx(0.0011, rel=1e-4)

    def test_get_summary_structure(self):
        self.tracker.record("Gemini", 100, 50, 0.0001)
        summary = self.tracker.get_summary()
        assert "grand_total_usd" in summary
        assert "per_provider" in summary
        assert "Gemini" in summary["per_provider"]

    def test_reset_clears_all_tracking(self):
        self.tracker.record("Gemini", 100, 50, 0.001)
        self.tracker.reset()
        assert self.tracker.total_cost() == 0.0

    def test_unknown_workflow_cost_is_zero(self):
        assert self.tracker.workflow_cost("nonexistent") == 0.0


# =============================================================================
# Phase 5 — ProviderFailoverManager
# =============================================================================

class TestProviderFailoverManager:
    def setup_method(self):
        self.failover = ProviderFailoverManager(
            max_retries=1,
            base_backoff_ms=1.0,  # tiny backoff for tests
        )
        self.monitor = ProviderHealthMonitor()
        self.tracker = ProviderCostTracker()
        self.payload = PromptPayload(
            template_name="t", rendered_system="s", rendered_user="u",
            agent_name="planner", estimated_tokens=50,
        )

    def _mock_provider(self, name="Gemini", side_effect=None, response=None):
        from app.domain.provider_response import ProviderResponse
        p = MagicMock()
        p.provider_name = name
        p.health_check.return_value = True
        if side_effect:
            p.generate.side_effect = side_effect
        else:
            if response is None:
                response = ProviderResponse(
                    provider_name=name, model_name="test",
                    response_text="ok", prompt_tokens=50, completion_tokens=20,
                    total_tokens=70, latency_ms=100.0, estimated_cost=0.00005,
                )
            p.generate.return_value = response
        return p

    def test_successful_call_returns_response(self):
        p = self._mock_provider()
        result = self.failover.execute_with_fallback(
            [p], self.payload, health_monitor=self.monitor, cost_tracker=self.tracker
        )
        assert result.response_text == "ok"

    def test_failover_to_second_provider_on_error(self):
        from app.domain.provider_response import ProviderResponse
        p1 = self._mock_provider("Gemini", side_effect=ProviderRateLimitError("Gemini", "rate limited"))
        p2 = self._mock_provider("OpenAI")
        result = self.failover.execute_with_fallback(
            [p1, p2], self.payload, health_monitor=self.monitor, cost_tracker=self.tracker
        )
        assert result.provider_name == "OpenAI"

    def test_auth_error_skips_retry_immediately(self):
        from app.domain.provider_response import ProviderResponse
        p1 = self._mock_provider("Gemini", side_effect=ProviderAuthenticationError("Gemini", "bad key"))
        p2 = self._mock_provider("Groq")
        result = self.failover.execute_with_fallback(
            [p1, p2], self.payload, health_monitor=self.monitor
        )
        # Auth error → skip immediately to p2
        assert result.provider_name == "Groq"
        # p1 called only once (no retry)
        assert p1.generate.call_count == 1

    def test_all_providers_fail_raises_unavailable(self):
        p1 = self._mock_provider("Gemini", side_effect=ProviderRateLimitError("Gemini", "rl"))
        p2 = self._mock_provider("OpenAI", side_effect=ProviderRateLimitError("OpenAI", "rl"))
        with pytest.raises(ProviderUnavailableError):
            self.failover.execute_with_fallback(
                [p1, p2], self.payload, health_monitor=self.monitor
            )

    def test_health_monitor_records_success(self):
        p = self._mock_provider("Gemini")
        self.failover.execute_with_fallback(
            [p], self.payload, health_monitor=self.monitor
        )
        summary = self.monitor.get_summary("Gemini")
        assert summary.successful_requests == 1

    def test_health_monitor_records_failure(self):
        p = self._mock_provider("Claude", side_effect=ProviderRateLimitError("Claude", "rl"))
        p2 = self._mock_provider("Groq")
        self.failover.execute_with_fallback(
            [p, p2], self.payload, health_monitor=self.monitor
        )
        summary = self.monitor.get_summary("Claude")
        assert summary.failed_requests >= 1

    def test_cost_tracker_records_on_success(self):
        p = self._mock_provider("OpenRouter")
        self.failover.execute_with_fallback(
            [p], self.payload, cost_tracker=self.tracker
        )
        assert self.tracker.total_cost("OpenRouter") >= 0.0

    def test_timeout_error_is_retried(self):
        from app.domain.provider_response import ProviderResponse
        success_resp = ProviderResponse(
            provider_name="Gemini", model_name="test",
            response_text="ok", prompt_tokens=50, completion_tokens=20,
            total_tokens=70, latency_ms=100.0, estimated_cost=0.00005,
        )
        p = MagicMock()
        p.provider_name = "Gemini"
        p.health_check.return_value = True
        p.generate.side_effect = [
            ProviderTimeoutError("Gemini", "timeout"),
            success_resp,
        ]
        result = self.failover.execute_with_fallback([p], self.payload)
        assert result.response_text == "ok"
        assert p.generate.call_count == 2


# =============================================================================
# Phase 1 — Streaming
# =============================================================================

class TestStreaming:
    def setup_method(self):
        self.payload = PromptPayload(
            template_name="t", rendered_system="s", rendered_user="u",
            agent_name="planner", estimated_tokens=50,
        )

    def test_stream_chunk_is_dataclass(self):
        chunk = StreamChunk(provider_name="Gemini", model_name="gemini", delta="hello")
        assert chunk.delta == "hello"
        assert chunk.is_final is False

    def test_stream_from_response_yields_single_final_chunk(self):
        from app.domain.provider_response import ProviderResponse
        resp = ProviderResponse(
            provider_name="Gemini", model_name="test",
            response_text="test response",
            prompt_tokens=50, completion_tokens=30, total_tokens=80,
            latency_ms=200.0, estimated_cost=0.0001,
        )
        chunks = list(stream_from_response(resp))
        assert len(chunks) == 1
        assert chunks[0].is_final is True
        assert chunks[0].accumulated == "test response"
        assert chunks[0].metadata.get("streaming_fallback") is True

    def test_collect_stream_returns_full_text(self):
        from app.domain.provider_response import ProviderResponse
        resp = ProviderResponse(
            provider_name="Gemini", model_name="test",
            response_text="hello world",
        )
        text = collect_stream(stream_from_response(resp))
        assert text == "hello world"

    def test_all_providers_stream_generate_in_mock_mode(self):
        providers = [
            GeminiProvider(mock_mode=True),
            OpenAIProvider(mock_mode=True),
            ClaudeProvider(mock_mode=True),
            GroqProvider(mock_mode=True),
            OpenRouterProvider(mock_mode=True),
        ]
        for provider in providers:
            chunks = list(provider.stream_generate(self.payload))
            assert len(chunks) >= 1
            final_chunks = [c for c in chunks if c.is_final]
            assert len(final_chunks) >= 1
            assert all(isinstance(c, StreamChunk) for c in chunks)

    def test_stream_generate_accumulated_text_grows(self):
        provider = GeminiProvider(mock_mode=True)
        chunks = list(provider.stream_generate(self.payload))
        if len(chunks) > 1:
            for i in range(1, len(chunks)):
                assert len(chunks[i].accumulated) >= len(chunks[i - 1].accumulated)

    def test_base_stream_generate_fallback_yields_chunks(self):
        """BaseLLMProvider.stream_generate() should yield at least one chunk via fallback."""
        provider = GeminiProvider(mock_mode=True)
        chunks = list(provider.stream_generate(self.payload))
        assert len(chunks) >= 1


# =============================================================================
# Phase 4 — Extended Routing Strategies
# =============================================================================

class TestExtendedRoutingStrategies:
    def test_fastest_strategy_selects_groq(self):
        strategy = FastestStrategy()
        decision = strategy.select_provider(AVAILABLE, {})
        # Groq has lowest typical_latency_ms
        assert decision.selected_provider == "Groq"
        assert decision.strategy_used == "FastestStrategy"

    def test_lowest_cost_strategy_selects_cheapest(self):
        strategy = LowestCostStrategy()
        decision = strategy.select_provider(AVAILABLE, {})
        assert decision.selected_provider in AVAILABLE
        assert decision.strategy_used == "LowestCostStrategy"

    def test_highest_quality_strategy_selects_claude(self):
        strategy = HighestQualityStrategy()
        decision = strategy.select_provider(AVAILABLE, {})
        # Claude has highest quality_score in metadata
        assert decision.selected_provider == "Claude"
        assert decision.strategy_used == "HighestQualityStrategy"

    def test_reasoning_strategy_selects_reasoning_capable(self):
        strategy = ReasoningStrategy()
        decision = strategy.select_provider(AVAILABLE, {})
        # Should pick a reasoning-capable provider
        capable = filter_by_capability("supports_reasoning")
        assert decision.selected_provider in capable
        assert decision.strategy_used == "ReasoningStrategy"

    def test_health_aware_strategy_avoids_degraded(self):
        strategy = HealthAwareStrategy(failure_threshold=0.3)
        metrics = {
            "health_scores": {"Gemini": 0.9, "OpenAI": 0.4, "Claude": 0.8, "Groq": 0.95, "OpenRouter": 0.7},
            "failure_rates": {"Gemini": 0.1, "OpenAI": 0.6, "Claude": 0.1, "Groq": 0.05, "OpenRouter": 0.2},
            "avg_latencies": {},
        }
        decision = strategy.select_provider(AVAILABLE, metrics)
        # OpenAI has failure_rate=0.6 > threshold=0.3, should not be selected
        assert decision.selected_provider != "OpenAI"
        assert decision.strategy_used == "HealthAwareStrategy"

    def test_health_aware_strategy_falls_back_when_all_degraded(self):
        strategy = HealthAwareStrategy(failure_threshold=0.1)
        # All providers degraded
        metrics = {
            "health_scores": {n: 0.3 for n in AVAILABLE},
            "failure_rates": {n: 0.9 for n in AVAILABLE},
            "avg_latencies": {},
        }
        decision = strategy.select_provider(AVAILABLE, metrics)
        # Should still return something (fallback to full list)
        assert decision.selected_provider in AVAILABLE

    def test_strategies_handle_empty_provider_list_gracefully(self):
        for StrategyClass in [FastestStrategy, LowestCostStrategy, HighestQualityStrategy,
                               ReasoningStrategy, HealthAwareStrategy]:
            strategy = StrategyClass()
            # Empty list — should return default without crashing
            decision = strategy.select_provider([], {})
            assert isinstance(decision, ProviderDecision)

    def test_strategies_work_with_single_provider(self):
        for StrategyClass in [FastestStrategy, LowestCostStrategy, HighestQualityStrategy,
                               ReasoningStrategy, HealthAwareStrategy]:
            strategy = StrategyClass()
            decision = strategy.select_provider(["Gemini"], {})
            assert decision.selected_provider == "Gemini"


# =============================================================================
# LLMProviderRouter v2.4
# =============================================================================

class TestLLMProviderRouterV24:
    def test_router_instantiates_with_5_providers(self, mock_router):
        assert len(mock_router.providers) == 5

    def test_router_has_health_monitor(self, mock_router):
        assert isinstance(mock_router.health_monitor, ProviderHealthMonitor)

    def test_router_has_cost_tracker(self, mock_router):
        assert isinstance(mock_router.cost_tracker, ProviderCostTracker)

    def test_router_has_failover_manager(self, mock_router):
        assert isinstance(mock_router.failover_manager, ProviderFailoverManager)

    def test_execute_prompt_returns_provider_response(self, mock_router, payload):
        from app.domain.provider_response import ProviderResponse
        response = mock_router.execute_prompt(payload)
        assert isinstance(response, ProviderResponse)
        assert response.response_text

    def test_execute_prompt_records_health_metrics(self, mock_router, payload):
        mock_router.execute_prompt(payload)
        # At least one provider should have been recorded
        summaries = mock_router.health_monitor.get_all_summaries()
        assert len(summaries) >= 1

    def test_execute_prompt_records_cost(self, mock_router, payload):
        mock_router.execute_prompt(payload)
        assert mock_router.cost_tracker.total_cost() >= 0.0

    def test_stream_execute_prompt_yields_chunks(self, mock_router, payload):
        chunks = list(mock_router.stream_execute_prompt(payload))
        assert len(chunks) >= 1
        assert all(isinstance(c, StreamChunk) for c in chunks)

    def test_stream_execute_final_chunk_is_marked(self, mock_router, payload):
        chunks = list(mock_router.stream_execute_prompt(payload))
        final = [c for c in chunks if c.is_final]
        assert len(final) >= 1

    def test_get_analytics_returns_dict(self, mock_router, payload):
        mock_router.execute_prompt(payload)
        analytics = mock_router.get_analytics()
        assert "health" in analytics
        assert "cost" in analytics
        assert "registered_providers" in analytics
        assert "generated_at" in analytics

    def test_router_with_fastest_strategy(self, mock_router, payload):
        strategy = FastestStrategy()
        response = mock_router.execute_prompt(payload, strategy=strategy)
        assert response is not None

    def test_router_with_health_aware_strategy(self, mock_router, payload):
        strategy = HealthAwareStrategy()
        response = mock_router.execute_prompt(payload, strategy=strategy)
        assert response is not None


# =============================================================================
# Phase 7 — Analytics Models
# =============================================================================

class TestAnalyticsModels:
    def test_provider_health_summary_to_dict(self):
        s = ProviderHealthSummary(provider_name="Gemini", health_score=0.95)
        d = s.to_dict()
        assert d["provider_name"] == "Gemini"
        assert d["health_score"] == 0.95

    def test_provider_cost_summary_to_dict(self):
        s = ProviderCostSummary(provider_name="OpenAI", cumulative_cost_usd=1.23)
        d = s.to_dict()
        assert d["cumulative_cost_usd"] == 1.23

    def test_provider_usage_summary_to_dict(self):
        s = ProviderUsageSummary(provider_name="Groq", model_name="llama-3.3-70b-versatile")
        d = s.to_dict()
        assert d["provider_name"] == "Groq"

    def test_workflow_provider_trace_to_dict(self):
        trace = WorkflowProviderTrace(
            workflow_id="wf-1",
            request_id="req-1",
            timestamp="2026-01-01T00:00:00Z",
            selected_provider="Gemini",
            fallback_provider=None,
            routing_strategy="BalancedStrategy",
            total_latency_ms=310.0,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.00012,
        )
        d = trace.to_dict()
        assert d["workflow_id"] == "wf-1"
        assert d["selected_provider"] == "Gemini"

    def test_analytics_dashboard_to_dict(self):
        dashboard = ProviderAnalyticsDashboard(generated_at="2026-01-01T00:00:00Z")
        d = dashboard.to_dict()
        assert "generated_at" in d
        assert "health_summaries" in d
        assert "cost_summaries" in d


# =============================================================================
# All 5 providers — mock mode correctness
# =============================================================================

class TestAllProvidersMockMode:
    PROVIDER_CLASSES = [
        GeminiProvider, OpenAIProvider, ClaudeProvider,
        GroqProvider, OpenRouterProvider,
    ]
    AGENT_NAMES = ["planner", "generator", "reviewer", "repair", "unknown"]

    @pytest.mark.parametrize("ProviderClass", PROVIDER_CLASSES)
    def test_mock_generate_returns_response(self, ProviderClass):
        provider = ProviderClass(mock_mode=True)
        payload = PromptPayload(
            template_name="t", rendered_system="s", rendered_user="u",
            agent_name="planner", estimated_tokens=100,
        )
        resp = provider.generate(payload)
        assert resp.response_text
        assert resp.provider_name == provider.provider_name
        assert resp.total_tokens > 0
        assert resp.estimated_cost >= 0.0
        assert resp.metadata.get("mock") is True

    @pytest.mark.parametrize("ProviderClass", PROVIDER_CLASSES)
    @pytest.mark.parametrize("agent_name", AGENT_NAMES)
    def test_mock_generate_handles_all_agents(self, ProviderClass, agent_name):
        provider = ProviderClass(mock_mode=True)
        payload = PromptPayload(
            template_name="t", rendered_system="s", rendered_user="u",
            agent_name=agent_name, estimated_tokens=50,
        )
        resp = provider.generate(payload)
        assert resp.response_text is not None

    @pytest.mark.parametrize("ProviderClass", PROVIDER_CLASSES)
    def test_mock_health_check_returns_true(self, ProviderClass):
        provider = ProviderClass(mock_mode=True)
        assert provider.health_check() is True

    @pytest.mark.parametrize("ProviderClass", PROVIDER_CLASSES)
    def test_supports_capability_uses_registry(self, ProviderClass):
        provider = ProviderClass(mock_mode=True)
        # All 5 support streaming per metadata
        assert provider.supports_capability("supports_streaming") is True

    @pytest.mark.parametrize("ProviderClass", PROVIDER_CLASSES)
    def test_estimate_tokens_positive(self, ProviderClass):
        provider = ProviderClass(mock_mode=True)
        assert provider.estimate_tokens("hello world") > 0

    @pytest.mark.parametrize("ProviderClass", PROVIDER_CLASSES)
    def test_estimate_cost_positive(self, ProviderClass):
        provider = ProviderClass(mock_mode=True)
        assert provider.estimate_cost(100, 50) >= 0.0
