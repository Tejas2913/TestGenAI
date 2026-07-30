"""TestGen AI v2.3 — ReviewerAgent Intelligence Unit Tests (Phase 8).

Verifies Markdown fence stripping, JSON schema validation, missing key detection,
invalid score boundaries, duplicate issue rejection, ReviewReport mapping,
ReviewerAgent AI execution with mock providers, 1-attempt repair flow, unrepairable error handling,
and Planner -> Generator -> Reviewer workflow integration.
"""

import json
import pytest

from app.agents.generator import GeneratorAgent
from app.agents.planner import PlannerAgent
from app.agents.reviewer import ReviewerAgent
from app.domain.provider_response import ProviderResponse
from app.domain.reviewer_schema import map_json_to_review_report, validate_review_json
from app.domain.v23_models import AgentWorkflowContext, GeneratedTest, GenerationRequest, ReviewReport
from app.exceptions.v23_exceptions import AgentExecutionError, ValidationError
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.agent_workflow import AgentWorkflow

VALID_REVIEW_JSON = json.dumps({
    "overall_score": 92.5,
    "approved": True,
    "summary": "High quality unit test suite.",
    "coverage_analysis": "All priority target functions covered.",
    "issues": [
        {
            "severity": "medium",
            "category": "assertion",
            "description": "Missing negative assertion for invalid input",
            "recommendation": "Add pytest.raises(ValueError) test case",
        }
    ],
    "strengths": ["Clean pytest assertions", "No test smells"],
    "recommendations": ["Add edge case test for negative numbers"],
    "confidence": 0.95,
})


class TestReviewerSchemaAndValidation:
    """Tests for Reviewer JSON validation and ReviewReport domain mapping."""

    def test_validate_valid_review_json(self):
        data = validate_review_json(VALID_REVIEW_JSON)
        assert data["overall_score"] == 92.5
        assert data["approved"] is True
        assert len(data["issues"]) == 1
        assert data["issues"][0]["severity"] == "medium"

    def test_validate_fenced_review_json(self):
        fenced_json = f"```json\n{VALID_REVIEW_JSON}\n```"
        data = validate_review_json(fenced_json)
        assert data["approved"] is True

    def test_validate_malformed_json_raises_validation_error(self):
        malformed = "{broken_review_json: true"
        with pytest.raises(ValidationError) as exc_info:
            validate_review_json(malformed)
        assert "Malformed JSON" in str(exc_info.value)

    def test_validate_missing_required_keys_raises_validation_error(self):
        incomplete = json.dumps({"overall_score": 90, "summary": "test"})
        with pytest.raises(ValidationError) as exc_info:
            validate_review_json(incomplete)
        assert "missing required reviewer keys" in str(exc_info.value).lower()

    def test_validate_out_of_bounds_score_raises_validation_error(self):
        invalid_score_json = json.dumps({
            "overall_score": 150,
            "approved": True,
            "summary": "invalid score",
            "issues": [],
        })
        with pytest.raises(ValidationError) as exc_info:
            validate_review_json(invalid_score_json)
        assert "between 0 and 100" in str(exc_info.value)

    def test_validate_invalid_severity_enum_raises_validation_error(self):
        invalid_severity_json = json.dumps({
            "overall_score": 80,
            "approved": True,
            "summary": "test",
            "issues": [
                {
                    "severity": "catastrophic",
                    "category": "syntax",
                    "description": "broken",
                }
            ],
        })
        with pytest.raises(ValidationError) as exc_info:
            validate_review_json(invalid_severity_json)
        assert "invalid severity" in str(exc_info.value).lower()

    def test_validate_duplicate_issues_raises_validation_error(self):
        duplicate_issues_json = json.dumps({
            "overall_score": 75,
            "approved": False,
            "summary": "duplicates",
            "issues": [
                {
                    "severity": "high",
                    "category": "assertion",
                    "description": "Missing null check",
                },
                {
                    "severity": "high",
                    "category": "assertion",
                    "description": "Missing null check",
                },
            ],
        })
        with pytest.raises(ValidationError) as exc_info:
            validate_review_json(duplicate_issues_json)
        assert "Duplicate issue detected" in str(exc_info.value)

    def test_map_json_to_review_report(self):
        data = json.loads(VALID_REVIEW_JSON)
        report = map_json_to_review_report(data)

        assert isinstance(report, ReviewReport)
        assert report.is_approved is True
        assert report.approved is True
        assert report.overall_score == 92.5
        assert len(report.issues) == 1
        assert len(report.flaws) == 1
        assert "assertion: Missing negative assertion" in report.flaws[0]
        assert report.missing_assertions == ["Missing negative assertion for invalid input"]


class TestReviewerAgentExecution:
    """Tests for ReviewerAgent AI execution, repair flow, and router integration."""

    def test_reviewer_agent_execution_with_valid_mock_provider(self):
        class ValidMockProvider(BaseLLMProvider):
            def __init__(self):
                super().__init__("ValidMock", "mock-v1")

            def generate(self, prompt_payload, options=None):
                return ProviderResponse(
                    provider_name="ValidMock",
                    model_name="mock-v1",
                    response_text=VALID_REVIEW_JSON,
                    latency_ms=8.0,
                    estimated_cost=0.0001,
                )

        router = LLMProviderRouter(mock_mode=True)
        router._providers.clear()
        router.register_provider(ValidMockProvider())

        reviewer = ReviewerAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.generated_tests = [
            GeneratedTest(
                test_name="test_add",
                test_code="def test_add(): assert add(1, 2) == 3",
                target_function="add",
            )
        ]

        res_ctx = reviewer.run(ctx)

        assert res_ctx.review_report is not None
        assert isinstance(res_ctx.review_report, ReviewReport)
        assert res_ctx.review_report.is_approved is True
        assert res_ctx.review_report.overall_score == 92.5

    def test_reviewer_agent_repair_flow(self):
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
                        response_text="{broken_review_json: 123",
                    )
                # Return valid JSON on repair attempt
                return ProviderResponse(
                    provider_name="RepairableMock",
                    model_name="mock-v1",
                    response_text=VALID_REVIEW_JSON,
                )

        router = LLMProviderRouter(mock_mode=True)
        router._providers.clear()
        router.register_provider(RepairableMockProvider())

        reviewer = ReviewerAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)

        res_ctx = reviewer.run(ctx)

        assert attempt_count == 2
        assert res_ctx.review_report is not None
        assert res_ctx.review_report.overall_score == 92.5
        assert "repaired" in res_ctx.reasoning_traces[0].rationale_summary.lower()

    def test_reviewer_agent_unrepairable_raises_validation_error(self):
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

        reviewer = ReviewerAgent(provider_router=router)
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)

        with pytest.raises((ValidationError, AgentExecutionError)) as exc_info:
            reviewer.run(ctx)
        assert "Malformed JSON" in str(exc_info.value)

    def test_full_workflow_planner_generator_reviewer_integration(self):
        wf = AgentWorkflow()
        req = GenerationRequest(source_code="def multiply(x, y): return x * y")
        ctx = wf.execute_workflow(req)

        assert ctx.test_plan is not None
        assert ctx.generated_tests is not None
        assert ctx.review_report is not None
        assert isinstance(ctx.review_report, ReviewReport)
        assert ctx.review_report.overall_score == 95.0
