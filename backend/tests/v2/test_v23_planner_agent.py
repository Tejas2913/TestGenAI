"""TestGen AI v2.3 — PlannerAgent Intelligence Unit Tests (Phase 6).

Verifies Markdown fence stripping, JSON validation, missing key detection,
TestPlan mapping, PlannerAgent AI execution with mock providers, 1-attempt repair flow,
unrepairable error handling, and AgentWorkflow integration.
"""

import json
import pytest

from app.agents.planner import PlannerAgent
from app.domain.planner_schema import map_json_to_test_plan, strip_markdown_fences, validate_planner_json
from app.domain.provider_response import ProviderResponse
from app.domain.v23_models import AgentWorkflowContext, GenerationRequest, ProviderDecision, TestPlan
from app.exceptions.v23_exceptions import ValidationError
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.agent_workflow import AgentWorkflow

VALID_PLANNER_JSON = json.dumps({
    "repository_summary": "Calculates math operations.",
    "priority_modules": ["math_utils"],
    "recommended_test_types": ["unit"],
    "target_functions": ["add", "subtract"],
    "test_cases": [
        {
            "case_id": 1,
            "description": "Test addition of two positive numbers",
            "target_function": "add",
            "test_type": "unit",
            "expected_behavior": "Returns sum of inputs",
        }
    ],
    "required_mocks": [],
    "required_fixtures": ["sample_numbers"],
    "edge_cases": ["Negative inputs", "Zero addition"],
    "confidence": 0.98,
})


class TestPlannerSchemaAndValidation:
    """Tests for markdown fence stripping, JSON validation, and schema checking."""

    def test_strip_markdown_fences(self):
        fenced = "```json\n{\"key\": \"value\"}\n```"
        assert strip_markdown_fences(fenced) == "{\"key\": \"value\"}"

    def test_validate_valid_planner_json(self):
        data = validate_planner_json(VALID_PLANNER_JSON)
        assert data["repository_summary"] == "Calculates math operations."
        assert "add" in data["target_functions"]
        assert len(data["test_cases"]) == 1

    def test_validate_fenced_planner_json(self):
        fenced_json = f"```json\n{VALID_PLANNER_JSON}\n```"
        data = validate_planner_json(fenced_json)
        assert "add" in data["target_functions"]

    def test_validate_malformed_json_raises_validation_error(self):
        malformed = "{broken_json: true"
        with pytest.raises(ValidationError) as exc_info:
            validate_planner_json(malformed)
        assert "Malformed JSON" in str(exc_info.value)

    def test_validate_missing_required_keys_raises_validation_error(self):
        incomplete = json.dumps({"target_functions": ["foo"]})
        with pytest.raises(ValidationError) as exc_info:
            validate_planner_json(incomplete)
        assert "missing required planner keys" in str(exc_info.value).lower()

    def test_map_json_to_test_plan(self):
        data = json.loads(VALID_PLANNER_JSON)
        plan = map_json_to_test_plan(data)

        assert isinstance(plan, TestPlan)
        assert plan.target_functions == ["add", "subtract"]
        assert len(plan.test_cases) == 1
        assert plan.edge_cases == ["Negative inputs", "Zero addition"]


class TestPlannerAgentExecution:
    """Tests for PlannerAgent AI execution, repair flow, and router integration."""

    def test_planner_agent_execution_with_valid_mock_provider(self):
        class ValidMockProvider(BaseLLMProvider):
            def __init__(self):
                super().__init__("ValidMock", "mock-v1")

            def generate(self, prompt_payload, options=None):
                return ProviderResponse(
                    provider_name="ValidMock",
                    model_name="mock-v1",
                    response_text=VALID_PLANNER_JSON,
                    latency_ms=10.0,
                    estimated_cost=0.0001,
                )

        router = LLMProviderRouter(mock_mode=True)
        router.register_provider(ValidMockProvider())

        planner = PlannerAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)

        res_ctx = planner.run(ctx)

        assert res_ctx.test_plan is not None
        assert isinstance(res_ctx.test_plan, TestPlan)
        assert "add" in res_ctx.test_plan.target_functions
        assert res_ctx.provider_decision is not None

    def test_planner_agent_repair_flow(self):
        attempt_count = 0

        class RepairableMockProvider(BaseLLMProvider):
            def __init__(self):
                super().__init__("RepairableMock", "mock-v1")

            def generate(self, prompt_payload, options=None):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count == 1:
                    # Return malformed JSON on first attempt
                    return ProviderResponse(
                        provider_name="RepairableMock",
                        model_name="mock-v1",
                        response_text="{broken_json: 123",
                    )
                # Return valid JSON on repair attempt
                return ProviderResponse(
                    provider_name="RepairableMock",
                    model_name="mock-v1",
                    response_text=VALID_PLANNER_JSON,
                )

        router = LLMProviderRouter(mock_mode=True)
        router._providers.clear()
        router.register_provider(RepairableMockProvider())

        planner = PlannerAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)

        res_ctx = planner.run(ctx)

        assert attempt_count == 2
        assert res_ctx.test_plan is not None
        assert "add" in res_ctx.test_plan.target_functions
        assert "repaired" in res_ctx.reasoning_traces[0].rationale_summary.lower()

    def test_planner_agent_unrepairable_raises_validation_error(self):
        class UnrepairableMockProvider(BaseLLMProvider):
            def __init__(self):
                super().__init__("UnrepairableMock", "mock-v1")

            def generate(self, prompt_payload, options=None):
                return ProviderResponse(
                    provider_name="UnrepairableMock",
                    model_name="mock-v1",
                    response_text="{broken_json_always: true",
                )

        router = LLMProviderRouter(mock_mode=True)
        router._providers.clear()
        router.register_provider(UnrepairableMockProvider())

        planner = PlannerAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)

        from app.exceptions.v23_exceptions import AgentExecutionError

        with pytest.raises((ValidationError, AgentExecutionError)) as exc_info:
            planner.run(ctx)
        assert "Malformed JSON" in str(exc_info.value)

    def test_full_workflow_carries_ai_planned_test_plan(self):
        wf = AgentWorkflow()
        req = GenerationRequest(source_code="def multiply(x, y): return x * y")
        ctx = wf.execute_workflow(req)

        assert ctx.test_plan is not None
        assert isinstance(ctx.test_plan, TestPlan)
        assert ctx.provider_decision is not None
