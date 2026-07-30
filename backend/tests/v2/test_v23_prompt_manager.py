"""TestGen AI v2.3 — Prompt Management System Unit Tests (Phase 4).

Verifies PromptTemplate creation, RepositoryContextSerializer formatting/truncation,
PromptRepository template registration/lookup, PromptBuilder rendering/variable substitution,
validation exception handling, PromptManager integration, PlannerAgent payload generation,
and IoC Container wiring.
"""

import pytest

from app.agents.planner import PlannerAgent
from app.container import get_container
from app.domain.prompt_template import PromptTemplate
from app.domain.v23_models import AgentWorkflowContext, GenerationRequest, PromptPayload, RepositoryContext
from app.exceptions.v23_exceptions import ValidationError
from app.infrastructure.prompts.builder import PromptBuilder
from app.infrastructure.prompts.manager import PromptManager
from app.infrastructure.prompts.repository import PromptRepository
from app.infrastructure.prompts.serializer import RepositoryContextSerializer
from app.workflows.agent_workflow import AgentWorkflow


class TestPromptTemplateDomain:
    """PromptTemplate dataclass tests."""

    def test_prompt_template_instantiation(self):
        t = PromptTemplate(
            template_id="custom_v1",
            name="Custom Template",
            version="v1.0",
            agent="planner",
            description="Custom planner prompt",
            system_prompt="System instructions",
            user_prompt="User input: {source_code}",
            required_variables=["source_code"],
        )
        assert t.template_id == "custom_v1"
        assert t.required_variables == ["source_code"]


class TestRepositoryContextSerializer:
    """RepositoryContextSerializer markdown formatting & truncation tests."""

    def test_serializer_formatting(self):
        serializer = RepositoryContextSerializer()
        ctx = RepositoryContext(
            file_path="app/main.py",
            metadata={"root_path": "/app", "source_files_count": 5},
            frameworks={"FastAPI": 1.0, "Pytest": 1.0},
            dependencies=["fastapi", "pytest"],
            classes=[{"name": "AppEngine", "bases": ["Base"]}],
            functions=[{"name": "run_app", "args": ["config"], "is_async": True}],
        )
        serialized = serializer.serialize(ctx)
        assert "Repository Context Summary" in serialized
        assert "FastAPI" in serialized
        assert "class AppEngine" in serialized
        assert "async def run_app" in serialized

    def test_serializer_truncation_limit(self):
        serializer = RepositoryContextSerializer()
        ctx = RepositoryContext(
            functions=[{"name": f"long_function_name_{i}", "args": []} for i in range(100)]
        )
        serialized = serializer.serialize(ctx, max_chars=200)
        assert len(serialized) <= 200
        assert "[Context Truncated]" in serialized


class TestPromptRepository:
    """PromptRepository lookup and registration tests."""

    def test_default_templates_registered(self):
        repo = PromptRepository()
        planner_t = repo.get_template("planner", "v2.3")
        assert planner_t.agent == "planner"
        assert "source_code" in planner_t.required_variables

        generator_t = repo.get_template("generator", "v2.3")
        assert generator_t.agent == "generator"

    def test_missing_template_raises_validation_error(self):
        repo = PromptRepository()
        with pytest.raises(ValidationError) as exc_info:
            repo.get_template("nonexistent_agent", "v9.9")
        assert "not found" in str(exc_info.value).lower()


class TestPromptBuilder:
    """PromptBuilder rendering, variable substitution, and validation tests."""

    def test_render_valid_payload(self):
        builder = PromptBuilder()
        repo = PromptRepository()
        template = repo.get_template("planner", "v2.3")

        req = GenerationRequest(source_code="def foo(): return 42")
        context = AgentWorkflowContext(request=req)

        payload = builder.build_payload(template, context)

        assert isinstance(payload, PromptPayload)
        assert payload.template_name == template.name
        assert "def foo(): return 42" in payload.rendered_user
        assert payload.agent_name == "planner"
        assert payload.estimated_tokens > 0

    def test_missing_required_variables_raises_validation_error(self):
        builder = PromptBuilder()
        template = PromptTemplate(
            template_id="broken_v1",
            name="Broken Template",
            version="v1.0",
            agent="test",
            description="Broken",
            system_prompt="Sys",
            user_prompt="User {missing_var}",
            required_variables=["missing_var"],
        )
        req = GenerationRequest(source_code="def foo(): pass")
        context = AgentWorkflowContext(request=req)

        with pytest.raises(ValidationError) as exc_info:
            builder.build_payload(template, context)
        assert "missing_var" in str(exc_info.value)

    def test_empty_prompt_raises_validation_error(self):
        builder = PromptBuilder()
        template = PromptTemplate(
            template_id="empty_v1",
            name="Empty Template",
            version="v1.0",
            agent="test",
            description="Empty",
            system_prompt="   ",
            user_prompt="User",
        )
        context = AgentWorkflowContext(request=GenerationRequest(source_code="code"))

        with pytest.raises(ValidationError) as exc_info:
            builder.build_payload(template, context)
        assert "empty prompts" in str(exc_info.value).lower()


class TestPromptManager:
    """PromptManager central entry point tests."""

    def test_prompt_manager_end_to_end(self):
        manager = PromptManager()
        req = GenerationRequest(source_code="def calc(a, b): return a + b")
        context = AgentWorkflowContext(request=req)

        payload = manager.build_prompt_payload("planner", context)

        assert isinstance(payload, PromptPayload)
        assert payload.agent_name == "planner"
        assert "def calc(a, b): return a + b" in payload.rendered_user

    def test_prompt_manager_custom_variable_override(self):
        manager = PromptManager()
        req = GenerationRequest(source_code="def calc(a, b): return a + b")
        context = AgentWorkflowContext(request=req)

        payload = manager.build_prompt_payload(
            "planner", context, custom_variables={"framework": "custom_pytest"}
        )
        assert "Framework Target: custom_pytest" in payload.rendered_user


class TestPlannerIntegrationWithPromptManager:
    """PlannerAgent integration tests with PromptManager."""

    def test_planner_agent_generates_and_attaches_prompt_payload(self):
        planner = PlannerAgent()
        req = GenerationRequest(source_code="def multiply(x, y): return x * y")
        context = AgentWorkflowContext(request=req)

        res_ctx = planner.run(context)

        assert res_ctx.prompt_payload is not None
        assert isinstance(res_ctx.prompt_payload, PromptPayload)
        assert res_ctx.prompt_payload.agent_name == "planner"
        assert "def multiply(x, y): return x * y" in res_ctx.prompt_payload.rendered_user

    def test_full_workflow_carries_prompt_payload(self):
        wf = AgentWorkflow()
        req = GenerationRequest(source_code="def divide(a, b): return a / b")
        ctx = wf.execute_workflow(req)

        assert ctx.prompt_payload is not None
        assert ctx.prompt_payload.estimated_tokens > 0


class TestIoCContainerWiring:
    """IoC container prompt management wiring tests."""

    def test_container_prompt_manager_wiring(self):
        container = get_container()
        assert isinstance(container.prompt_repository, PromptRepository)
        assert isinstance(container.prompt_builder, PromptBuilder)
        assert isinstance(container.prompt_manager, PromptManager)
