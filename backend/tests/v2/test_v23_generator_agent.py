"""TestGen AI v2.3 — GeneratorAgent Intelligence Unit Tests (Phase 7).

Verifies Markdown fence stripping, JSON schema validation, missing key detection,
duplicate test name rejection, GeneratedTest mapping, GeneratorAgent AI execution with mock providers,
1-attempt repair flow, unrepairable error handling, and Planner -> Generator workflow integration.
"""

import json
import pytest

from app.agents.generator import GeneratorAgent
from app.agents.planner import PlannerAgent
from app.domain.generator_schema import map_json_to_generated_tests, validate_generator_json
from app.domain.provider_response import ProviderResponse
from app.domain.v23_models import AgentWorkflowContext, GeneratedTest, GenerationRequest, TestPlan
from app.exceptions.v23_exceptions import AgentExecutionError, ValidationError
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.agent_workflow import AgentWorkflow

VALID_GENERATOR_JSON = json.dumps({
    "generated_tests": [
        {
            "target_module": "math_utils",
            "target_function": "add",
            "framework": "pytest",
            "imports": ["pytest", "from app.math_utils import add"],
            "fixtures": [],
            "mocks": [],
            "test_name": "test_add_positive_numbers",
            "setup": "",
            "test_code": "def test_add_positive_numbers():\n    assert add(2, 3) == 5\n",
            "assertions": ["assert add(2, 3) == 5"],
            "confidence": 0.96,
        }
    ]
})


class TestGeneratorSchemaAndValidation:
    """Tests for Generator JSON validation and GeneratedTest domain mapping."""

    def test_validate_valid_generator_json(self):
        data = validate_generator_json(VALID_GENERATOR_JSON)
        assert "generated_tests" in data
        assert len(data["generated_tests"]) == 1
        assert data["generated_tests"][0]["test_name"] == "test_add_positive_numbers"

    def test_validate_fenced_generator_json(self):
        fenced_json = f"```json\n{VALID_GENERATOR_JSON}\n```"
        data = validate_generator_json(fenced_json)
        assert len(data["generated_tests"]) == 1

    def test_validate_malformed_json_raises_validation_error(self):
        malformed = "{broken_generator_json: true"
        with pytest.raises(ValidationError) as exc_info:
            validate_generator_json(malformed)
        assert "Malformed JSON" in str(exc_info.value)

    def test_validate_missing_root_key_raises_validation_error(self):
        incomplete = json.dumps({"wrong_key": []})
        with pytest.raises(ValidationError) as exc_info:
            validate_generator_json(incomplete)
        assert "missing required root key" in str(exc_info.value).lower()

    def test_validate_empty_tests_list_raises_validation_error(self):
        empty_list_json = json.dumps({"generated_tests": []})
        with pytest.raises(ValidationError) as exc_info:
            validate_generator_json(empty_list_json)
        assert "must not be empty" in str(exc_info.value).lower()

    def test_validate_duplicate_test_names_raises_validation_error(self):
        duplicate_json = json.dumps({
            "generated_tests": [
                {
                    "test_name": "test_duplicate",
                    "test_code": "def test_duplicate(): pass",
                    "target_function": "foo",
                },
                {
                    "test_name": "test_duplicate",
                    "test_code": "def test_duplicate(): pass",
                    "target_function": "bar",
                },
            ]
        })
        with pytest.raises(ValidationError) as exc_info:
            validate_generator_json(duplicate_json)
        assert "Duplicate test name detected" in str(exc_info.value)

    def test_validate_empty_test_code_raises_validation_error(self):
        empty_code_json = json.dumps({
            "generated_tests": [
                {
                    "test_name": "test_empty_code",
                    "test_code": "   ",
                    "target_function": "foo",
                }
            ]
        })
        with pytest.raises(ValidationError) as exc_info:
            validate_generator_json(empty_code_json)
        assert "has empty 'test_code'" in str(exc_info.value)

    def test_map_json_to_generated_tests(self):
        data = json.loads(VALID_GENERATOR_JSON)
        tests = map_json_to_generated_tests(data)

        assert len(tests) == 1
        gt = tests[0]
        assert isinstance(gt, GeneratedTest)
        assert gt.test_name == "test_add_positive_numbers"
        assert gt.target_function == "add"
        assert gt.confidence == 0.96


class TestGeneratorAgentExecution:
    """Tests for GeneratorAgent AI execution, repair flow, and router integration."""

    def test_generator_agent_execution_with_valid_mock_provider(self):
        class ValidMockProvider(BaseLLMProvider):
            def __init__(self):
                super().__init__("ValidMock", "mock-v1")

            def generate(self, prompt_payload, options=None):
                return ProviderResponse(
                    provider_name="ValidMock",
                    model_name="mock-v1",
                    response_text=VALID_GENERATOR_JSON,
                    latency_ms=12.0,
                    estimated_cost=0.0002,
                )

        router = LLMProviderRouter(mock_mode=True)
        router.register_provider(ValidMockProvider())

        generator = GeneratorAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.test_plan = TestPlan(target_functions=["add"])

        res_ctx = generator.run(ctx)

        assert res_ctx.generated_tests is not None
        assert len(res_ctx.generated_tests) == 1
        assert isinstance(res_ctx.generated_tests[0], GeneratedTest)
        assert res_ctx.generated_tests[0].test_name == "test_add_positive_numbers"
        assert len(res_ctx.candidate_tests) == 1

    def test_generator_agent_repair_flow(self):
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
                        response_text="{broken_generator_json: 123",
                    )
                # Return valid JSON on repair attempt
                return ProviderResponse(
                    provider_name="RepairableMock",
                    model_name="mock-v1",
                    response_text=VALID_GENERATOR_JSON,
                )

        router = LLMProviderRouter(mock_mode=True)
        router._providers.clear()
        router.register_provider(RepairableMockProvider())

        generator = GeneratorAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.test_plan = TestPlan(target_functions=["add"])

        res_ctx = generator.run(ctx)

        assert attempt_count == 2
        assert len(res_ctx.generated_tests) == 1
        assert "repaired" in res_ctx.reasoning_traces[0].rationale_summary.lower()

    def test_generator_agent_unrepairable_raises_validation_error(self):
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

        generator = GeneratorAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)

        with pytest.raises((ValidationError, AgentExecutionError)) as exc_info:
            generator.run(ctx)
        assert "Malformed JSON" in str(exc_info.value)

    def test_full_workflow_planner_to_generator_integration(self):
        wf = AgentWorkflow()
        req = GenerationRequest(source_code="def multiply(x, y): return x * y")
        ctx = wf.execute_workflow(req)

        assert ctx.test_plan is not None
        assert ctx.generated_tests is not None
        assert len(ctx.generated_tests) >= 1
        assert isinstance(ctx.generated_tests[0], GeneratedTest)
