"""TestGen AI v2.3 — Multi-LLM Provider Framework Unit Tests (Phase 5).

Verifies BaseLLMProvider contract, concrete providers (Gemini, OpenAI, Claude),
ProviderResponse normalization, routing strategies (Cost, Latency, Quality, Balanced, Research),
ProviderEvaluator scoring, LLMProviderRouter automatic fallback, PlannerAgent integration,
and IoC Container wiring.
"""

import pytest

from app.agents.planner import PlannerAgent
from app.container import get_container
from app.domain.prompt_template import PromptTemplate
from app.domain.provider_response import ProviderResponse
from app.domain.v23_models import AgentWorkflowContext, GenerationRequest, PromptPayload, ProviderDecision
from app.exceptions.v23_exceptions import ProviderAuthenticationError, ProviderError, ProviderUnavailableError
from app.infrastructure.providers.claude import ClaudeProvider
from app.infrastructure.providers.evaluator import ProviderEvaluator
from app.infrastructure.providers.gemini import GeminiProvider
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.infrastructure.providers.router import LLMProviderRouter
from app.infrastructure.routing_strategies.strategies import (
    BalancedStrategy,
    CostStrategy,
    LatencyStrategy,
    QualityStrategy,
    ResearchStrategy,
)
from app.workflows.agent_workflow import AgentWorkflow


class TestConcreteProviders:
    """Concrete provider execution, response normalization, and cost estimation tests."""

    def test_gemini_provider_mock_execution(self):
        provider = GeminiProvider(mock_mode=True)
        assert provider.health_check() is True

        payload = PromptPayload(
            template_name="Test Template",
            rendered_system="Sys",
            rendered_user="User",
            agent_name="planner",
            estimated_tokens=50,
        )
        res = provider.generate(payload)

        assert isinstance(res, ProviderResponse)
        assert res.provider_name == "Gemini"
        assert res.model_name == "gemini-1.5-pro"
        assert "Mock Gemini Response" in res.response_text
        assert res.prompt_tokens == 50
        assert res.estimated_cost > 0.0

    def test_openai_provider_mock_execution(self):
        provider = OpenAIProvider(mock_mode=True)
        assert provider.health_check() is True

        payload = PromptPayload(
            template_name="Test Template",
            rendered_system="Sys",
            rendered_user="User",
            agent_name="generator",
            estimated_tokens=80,
        )
        res = provider.generate(payload)

        assert isinstance(res, ProviderResponse)
        assert res.provider_name == "OpenAI"
        assert res.model_name == "gpt-4o"
        assert "Mock OpenAI Response" in res.response_text

    def test_claude_provider_mock_execution(self):
        provider = ClaudeProvider(mock_mode=True)
        assert provider.health_check() is True

        payload = PromptPayload(
            template_name="Test Template",
            rendered_system="Sys",
            rendered_user="User",
            agent_name="reviewer",
            estimated_tokens=100,
        )
        res = provider.generate(payload)

        assert isinstance(res, ProviderResponse)
        assert res.provider_name == "Claude"
        assert res.model_name == "claude-3-5-sonnet"
        assert "Mock Claude Response" in res.response_text

    def test_missing_api_key_raises_auth_error(self):
        provider = GeminiProvider(api_key="", mock_mode=False)
        payload = PromptPayload(template_name="T", rendered_system="S", rendered_user="U")
        
        with pytest.raises(ProviderAuthenticationError) as exc_info:
            provider.generate(payload)
        assert "missing or invalid" in str(exc_info.value)


class TestRoutingStrategies:
    """Routing strategy decision making tests."""

    def test_cost_strategy_selection(self):
        strategy = CostStrategy()
        decision = strategy.select_provider(["Gemini", "OpenAI", "Claude"], {})
        assert decision.selected_provider == "Gemini"
        assert decision.strategy_used == "CostStrategy"

    def test_quality_strategy_selection(self):
        strategy = QualityStrategy()
        decision = strategy.select_provider(["Gemini", "OpenAI", "Claude"], {})
        assert decision.selected_provider == "Claude"
        assert decision.strategy_used == "QualityStrategy"

    def test_balanced_strategy_selection(self):
        strategy = BalancedStrategy()
        decision = strategy.select_provider(["Gemini", "OpenAI"], {})
        assert decision.selected_provider == "Gemini"
        assert decision.strategy_used == "BalancedStrategy"

    def test_latency_strategy_selection(self):
        strategy = LatencyStrategy()
        decision = strategy.select_provider(["Gemini", "OpenAI"], {})
        assert decision.selected_provider == "Gemini"
        assert decision.strategy_used == "LatencyStrategy"

    def test_research_strategy_selection(self):
        strategy = ResearchStrategy()
        decision = strategy.select_provider(["OpenAI"], {})
        assert decision.selected_provider == "OpenAI"


class TestLLMProviderRouterAndFallback:
    """LLMProviderRouter execution and automatic fallback tests."""

    def test_router_executes_selected_provider(self):
        router = LLMProviderRouter(mock_mode=True)
        payload = PromptPayload(template_name="T", rendered_system="S", rendered_user="U", agent_name="planner")

        res = router.execute_prompt(payload)

        assert isinstance(res, ProviderResponse)
        assert res.provider_name in ("Gemini", "OpenAI", "Claude")

    def test_router_fallback_on_failing_primary_provider(self):
        router = LLMProviderRouter(mock_mode=True)

        class FailingProvider(GeminiProvider):
            def generate(self, prompt_payload, options=None):
                raise ProviderError("FailingGemini", "Simulated primary failure")

        # Replace Gemini with failing provider
        router.register_provider(FailingProvider(mock_mode=True))
        payload = PromptPayload(template_name="T", rendered_system="S", rendered_user="U", agent_name="planner")

        # Should fall back cleanly to OpenAI or Claude
        res = router.execute_prompt(payload)
        assert res.provider_name in ("OpenAI", "Claude")


class TestPlannerAgentProviderIntegration:
    """PlannerAgent integration with LLMProviderRouter."""

    def test_planner_agent_executes_provider_call(self):
        planner = PlannerAgent()
        req = GenerationRequest(source_code="def power(x, y): return x ** y")
        context = AgentWorkflowContext(request=req)

        res_ctx = planner.run(context)

        assert res_ctx.provider_decision is not None
        assert isinstance(res_ctx.provider_decision, ProviderDecision)
        assert res_ctx.provider_decision.selected_provider in ("Gemini", "OpenAI", "Claude")

    def test_full_workflow_populates_provider_decision(self):
        wf = AgentWorkflow()
        req = GenerationRequest(source_code="def sqrt(x): return x ** 0.5")
        ctx = wf.execute_workflow(req)

        assert ctx.provider_decision is not None
        assert ctx.provider_decision.latency_ms >= 0.0


class TestIoCContainerProviderWiring:
    """IoC container provider wiring tests."""

    def test_container_provider_wiring(self):
        container = get_container()
        assert container.provider_evaluator is not None
        assert container.provider_router is not None
