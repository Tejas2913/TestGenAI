"""TestGen AI v2.3 — RepairAgent Intelligence Unit Tests (Phase 9).

Verifies Markdown fence stripping, JSON schema validation, missing key detection,
duplicate test name rejection, GeneratedTest & RepairAction domain mapping,
conditional execution (skips when approved, executes when unapproved),
RepairAgent AI execution with mock providers, 1-attempt repair flow, unrepairable error handling,
and Planner -> Generator -> Reviewer -> Repair full workflow integration.
"""

import json
import pytest

from app.agents.generator import GeneratorAgent
from app.agents.planner import PlannerAgent
from app.agents.repair import RepairAgent
from app.agents.reviewer import ReviewerAgent
from app.domain.provider_response import ProviderResponse
from app.domain.repair_schema import map_json_to_repaired_tests, validate_repair_json
from app.domain.v23_models import AgentWorkflowContext, GeneratedTest, GenerationRequest, RepairAction, ReviewReport
from app.exceptions.v23_exceptions import AgentExecutionError, ValidationError
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.agent_workflow import AgentWorkflow

VALID_REPAIR_JSON = json.dumps({
    "repaired_tests": [
        {
            "test_name": "test_add_positive_numbers",
            "target_function": "add",
            "test_code": "def test_add_positive_numbers():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n",
            "repair_reason": "Added missing negative boundary assertion",
            "fixed_issues": ["Missing negative assertion"],
            "confidence": 0.96,
        }
    ]
})


class TestRepairSchemaAndValidation:
    """Tests for Repair JSON validation and domain model mapping."""

    def test_validate_valid_repair_json(self):
        data = validate_repair_json(VALID_REPAIR_JSON)
        assert "repaired_tests" in data
        assert len(data["repaired_tests"]) == 1
        assert data["repaired_tests"][0]["test_name"] == "test_add_positive_numbers"

    def test_validate_fenced_repair_json(self):
        fenced_json = f"```json\n{VALID_REPAIR_JSON}\n```"
        data = validate_repair_json(fenced_json)
        assert len(data["repaired_tests"]) == 1

    def test_validate_malformed_json_raises_validation_error(self):
        malformed = "{broken_repair_json: true"
        with pytest.raises(ValidationError) as exc_info:
            validate_repair_json(malformed)
        assert "Malformed JSON" in str(exc_info.value)

    def test_validate_missing_root_key_raises_validation_error(self):
        incomplete = json.dumps({"wrong_key": []})
        with pytest.raises(ValidationError) as exc_info:
            validate_repair_json(incomplete)
        assert "missing required root key" in str(exc_info.value).lower()

    def test_validate_empty_repaired_tests_raises_validation_error(self):
        empty_list_json = json.dumps({"repaired_tests": []})
        with pytest.raises(ValidationError) as exc_info:
            validate_repair_json(empty_list_json)
        assert "must not be empty" in str(exc_info.value).lower()

    def test_validate_duplicate_test_names_raises_validation_error(self):
        duplicate_json = json.dumps({
            "repaired_tests": [
                {
                    "test_name": "test_dup",
                    "test_code": "def test_dup(): pass",
                    "repair_reason": "fix 1",
                },
                {
                    "test_name": "test_dup",
                    "test_code": "def test_dup(): pass",
                    "repair_reason": "fix 2",
                },
            ]
        })
        with pytest.raises(ValidationError) as exc_info:
            validate_repair_json(duplicate_json)
        assert "Duplicate repaired test name" in str(exc_info.value)

    def test_map_json_to_repaired_tests(self):
        data = json.loads(VALID_REPAIR_JSON)
        existing = [
            GeneratedTest(
                test_name="test_add_positive_numbers",
                test_code="def test_add_positive_numbers(): assert add(2, 3) == 5",
                target_function="add",
            )
        ]
        updated, actions = map_json_to_repaired_tests(data, existing)

        assert len(updated) == 1
        assert "assert add(-1, 1) == 0" in updated[0].test_code
        assert len(actions) == 1
        assert isinstance(actions[0], RepairAction)
        assert actions[0].repair_type == "AIRefinementRepair"
        assert "Added missing negative" in actions[0].reason


class TestRepairAgentExecution:
    """Tests for RepairAgent AI execution, conditional skipping, repair flow, and router integration."""

    def test_repair_agent_skips_when_review_approved(self):
        repair_agent = RepairAgent()
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.review_report = ReviewReport(is_approved=True)

        res_ctx = repair_agent.run(ctx)

        assert len(res_ctx.repair_history) == 0
        assert res_ctx.reasoning_traces[-1].step_action == "skip_repair"

    def test_repair_agent_executes_when_review_unapproved(self):
        class ValidMockProvider(BaseLLMProvider):
            def __init__(self):
                super().__init__("ValidMock", "mock-v1")

            def generate(self, prompt_payload, options=None):
                return ProviderResponse(
                    provider_name="ValidMock",
                    model_name="mock-v1",
                    response_text=VALID_REPAIR_JSON,
                    latency_ms=10.0,
                    estimated_cost=0.0001,
                )

        router = LLMProviderRouter(mock_mode=True)
        router.register_provider(ValidMockProvider())

        repair_agent = RepairAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.review_report = ReviewReport(is_approved=False, flaws=["Missing negative assertion"])
        ctx.generated_tests = [
            GeneratedTest(
                test_name="test_add_positive_numbers",
                test_code="def test_add_positive_numbers(): assert add(2, 3) == 5",
                target_function="add",
            )
        ]

        res_ctx = repair_agent.run(ctx)

        assert len(res_ctx.repair_history) == 1
        assert isinstance(res_ctx.repair_history[0], RepairAction)
        assert "assert add(-1, 1) == 0" in res_ctx.generated_tests[0].test_code
        assert res_ctx.reasoning_traces[-1].step_action == "ai_driven_test_repair"

    def test_repair_agent_repair_flow(self):
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
                        response_text="{broken_repair_json: 123",
                    )
                # Return valid JSON on repair attempt
                return ProviderResponse(
                    provider_name="RepairableMock",
                    model_name="mock-v1",
                    response_text=VALID_REPAIR_JSON,
                )

        router = LLMProviderRouter(mock_mode=True)
        router._providers.clear()
        router.register_provider(RepairableMockProvider())

        repair_agent = RepairAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.review_report = ReviewReport(is_approved=False, flaws=["Missing boundary assertion"])

        res_ctx = repair_agent.run(ctx)

        assert attempt_count == 2
        assert len(res_ctx.repair_history) == 1
        assert "repaired json" in res_ctx.reasoning_traces[0].rationale_summary.lower()

    def test_repair_agent_unrepairable_raises_validation_error(self):
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

        repair_agent = RepairAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.review_report = ReviewReport(is_approved=False, flaws=["Missing check"])

        with pytest.raises((ValidationError, AgentExecutionError)) as exc_info:
            repair_agent.run(ctx)
        assert "Malformed JSON" in str(exc_info.value)

    def test_full_workflow_planner_generator_reviewer_repair_integration(self):
        wf = AgentWorkflow()
        req = GenerationRequest(source_code="def multiply(x, y): return x * y")
        ctx = wf.execute_workflow(req)

        assert ctx.test_plan is not None
        assert ctx.generated_tests is not None
        assert ctx.review_report is not None
        assert len(ctx.reasoning_traces) == 4
