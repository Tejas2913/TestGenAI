"""TestGen AI v2.3 — Architecture Scaffolding Unit Tests (Phase 1).

Verifies object creation, domain model contracts, AgentWorkflowContext flow,
infrastructure service construction, routing strategies, and IoC container wiring.
Zero behavioral testing of un-implemented logic.
"""

import pytest
from app.agents.base import BaseAgent
from app.container import ApplicationContainer, get_container
from app.domain.v23_models import (
    AgentWorkflowContext,
    CandidateTest,
    GenerationRequest,
    PromptPayload,
    ProviderDecision,
    QualityReport,
    ReasoningTrace,
    RepairAction,
    RepositoryContext,
    ReviewReport,
    TestPlan,
    TokenUsage,
)
from app.infrastructure.indexers.base import BaseContextIndexer
from app.infrastructure.indexers.repository_index import RepositoryContextIndex
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.routing_strategies.base import BaseRoutingStrategy
from app.infrastructure.routing_strategies.strategies import (
    BalancedStrategy,
    CostStrategy,
    LatencyStrategy,
    QualityStrategy,
    ResearchStrategy,
)
from app.infrastructure.services import (
    ContextCache,
    LLMProviderRouter,
    PromptBuilder,
    PromptManager,
    PromptRepository,
    ProviderEvaluator,
    ReasoningTraceLogger,
    TokenCostTracker,
)
from app.quality.rules.base import BaseQualityRule
from app.workflows.agent_workflow import AgentWorkflow
from app.workflows.states import WorkflowState


class DummyAgent(BaseAgent):
    """Concrete test implementation of BaseAgent for contract verification."""

    def __init__(self) -> None:
        super().__init__(agent_name="DummyAgent", target_state=WorkflowState.PLANNING)

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        context.add_reasoning_trace(
            agent_name=self.agent_name,
            step_action="dummy_step",
            rationale_summary="Executed dummy agent step",
        )
        return context


class DummyProvider(BaseLLMProvider):
    """Concrete test implementation of BaseLLMProvider."""

    def __init__(self) -> None:
        super().__init__(provider_name="DummyProvider", model_name="dummy-v1")

    def generate_text(self, prompt, options=None):
        return "def test_dummy(): pass"


class DummyIndexer(BaseContextIndexer):
    """Concrete test implementation of BaseContextIndexer."""

    def __init__(self) -> None:
        super().__init__(indexer_name="DummyIndexer")

    def build_context(self, source_code, file_path=None):
        return RepositoryContext(file_path=file_path)


class DummyQualityRule(BaseQualityRule):
    """Concrete test implementation of BaseQualityRule."""

    def __init__(self) -> None:
        super().__init__(rule_name="DummyQualityRule", weight=1.0)

    def evaluate(self, test_code, context):
        return {"passed": True}


class TestV23DomainModels:
    """Domain model construction & immutability tests."""

    def test_generation_request_creation(self):
        req = GenerationRequest(source_code="def foo(): pass", user_id="usr-123")
        assert req.source_code == "def foo(): pass"
        assert req.language == "python"
        assert req.framework == "pytest"
        assert req.user_id == "usr-123"

    def test_repository_context_defaults(self):
        ctx = RepositoryContext()
        assert ctx.imports == []
        assert ctx.pytest_fixtures == []

    def test_test_plan_creation(self):
        plan = TestPlan(target_functions=["foo", "bar"])
        assert len(plan.target_functions) == 2

    def test_agent_workflow_context_initialization(self):
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        wf_ctx = AgentWorkflowContext(request=req)

        assert wf_ctx.request == req
        assert isinstance(wf_ctx.repository_context, RepositoryContext)
        assert wf_ctx.candidate_tests == []
        assert wf_ctx.repair_history == []
        assert wf_ctx.reasoning_traces == []

    def test_agent_workflow_context_append_methods(self):
        req = GenerationRequest(source_code="def sub(a, b): return a - b")
        wf_ctx = AgentWorkflowContext(request=req)

        wf_ctx.add_reasoning_trace("PlannerAgent", "plan", "Created initial plan")
        assert len(wf_ctx.reasoning_traces) == 1
        assert wf_ctx.reasoning_traces[0].agent_name == "PlannerAgent"

        wf_ctx.add_repair_action("SyntaxRepair", "bad_code", "good_code", "Fixed syntax")
        assert len(wf_ctx.repair_history) == 1
        assert wf_ctx.repair_history[0].repair_type == "SyntaxRepair"


class TestV23AgentFramework:
    """BaseAgent & AgentWorkflow tests."""

    def test_base_agent_contract(self):
        agent = DummyAgent()
        assert agent.agent_name == "DummyAgent"

        req = GenerationRequest(source_code="def calc(): pass")
        ctx = AgentWorkflowContext(request=req)
        updated_ctx = agent.execute(ctx)

        assert len(updated_ctx.reasoning_traces) == 1
        assert updated_ctx.reasoning_traces[0].agent_name == "DummyAgent"

    def test_agent_workflow_registration_and_execution(self):
        workflow = AgentWorkflow(agents=[])
        agent = DummyAgent()
        workflow.register_agent(agent)

        req = GenerationRequest(source_code="def main(): pass")
        ctx = workflow.execute_workflow(req)

        assert len(ctx.reasoning_traces) == 1


class TestV23RoutingStrategies:
    """BaseRoutingStrategy implementations tests."""

    def test_all_strategies_instantiation(self):
        strategies = [
            CostStrategy(),
            QualityStrategy(),
            BalancedStrategy(),
            LatencyStrategy(),
            ResearchStrategy(),
        ]
        for strat in strategies:
            assert isinstance(strat, BaseRoutingStrategy)
            decision = strat.select_provider(["gemini", "claude"], {})
            assert isinstance(decision, ProviderDecision)
            assert decision.strategy_used == strat.strategy_name


class TestV23InfrastructureServices:
    """Infrastructure component construction tests."""

    def test_prompt_infrastructure(self):
        repo = PromptRepository()
        builder = PromptBuilder(repo)
        manager = PromptManager(repo, builder)

        ctx = RepositoryContext()
        payload = manager.get_prompt("test_template", ctx)
        assert isinstance(payload, PromptPayload)

    def test_provider_router_and_evaluator(self):
        evaluator = ProviderEvaluator(strategy=BalancedStrategy())
        router = LLMProviderRouter(provider_evaluator=evaluator)
        provider = DummyProvider()
        router.register_provider("dummy", provider)

        assert "dummy" in router.providers

    def test_analytics_and_cache(self):
        tracker = TokenCostTracker()
        usage = tracker.record_usage("gemini", 100, 50)
        assert isinstance(usage, TokenUsage)
        assert usage.total_tokens == 150

        trace_logger = ReasoningTraceLogger()
        trace = trace_logger.log_trace("Agent", "Action", "Rationale")
        assert isinstance(trace, ReasoningTrace)

        cache = ContextCache()
        cache.set("key1", "val1")
        assert cache.get("key1") == "val1"


class TestV23AbstractBaseClasses:
    """BaseLLMProvider, BaseContextIndexer, BaseQualityRule tests."""

    def test_provider_abstract_class(self):
        provider = DummyProvider()
        output = provider.generate_text(PromptPayload("t", "sys", "usr"))
        assert "def test_dummy" in output

    def test_indexer_abstract_class(self):
        indexer = DummyIndexer()
        ctx = indexer.build_context("code", "file.py")
        assert ctx.file_path == "file.py"

    def test_quality_rule_abstract_class(self):
        rule = DummyQualityRule()
        result = rule.evaluate("test_code", {})
        assert result["passed"] is True


class TestV23ContainerDependencyInjection:
    """ApplicationContainer singleton wiring tests."""

    def test_container_singleton(self):
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2
        assert isinstance(c1.agent_workflow, AgentWorkflow)
        assert isinstance(c1.prompt_manager, PromptManager)
        assert isinstance(c1.provider_router, LLMProviderRouter)
