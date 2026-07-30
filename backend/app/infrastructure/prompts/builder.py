from typing import TYPE_CHECKING, Any, Dict, Optional
import time
import structlog

from app.domain.prompt_template import PromptTemplate
from app.domain.v23_models import AgentWorkflowContext, PromptPayload, RepositoryContext
from app.exceptions.v23_exceptions import ValidationError
from app.infrastructure.prompts.serializer import RepositoryContextSerializer

if TYPE_CHECKING:
    from app.infrastructure.prompts.repository import PromptRepository

logger = structlog.get_logger()


class PromptBuilder:
    """Renders versioned PromptTemplate models into provider-agnostic PromptPayloads."""

    def __init__(
        self,
        serializer: Optional[Any] = None,
        repository: Optional["PromptRepository"] = None,
    ) -> None:
        from app.infrastructure.prompts.repository import PromptRepository
        if isinstance(serializer, PromptRepository):
            self.repository = serializer
            self.serializer = RepositoryContextSerializer()
        else:
            self.serializer = serializer or RepositoryContextSerializer()
            self.repository = repository
        self.logger = logger.bind(component="PromptBuilder")

    def build_payload(
        self,
        template: PromptTemplate,
        context: AgentWorkflowContext,
        custom_variables: Optional[Dict[str, Any]] = None,
    ) -> PromptPayload:
        """Render PromptTemplate using context and variables.

        Args:
            template: PromptTemplate domain model to render.
            context: Shared AgentWorkflowContext.
            custom_variables: Additional variable overrides.

        Returns:
            Provider-agnostic PromptPayload object.

        Raises:
            ValidationError: If required variables are missing or template is invalid.
        """
        start_time = time.perf_counter()

        if not template.system_prompt.strip() or not template.user_prompt.strip():
            raise ValidationError("template", f"PromptTemplate '{template.name}' contains empty prompts.")

        # Serialize repository context
        repo_summary = self.serializer.serialize(context.repository_context)

        # Prepare variable substitution dictionary
        var_dict: Dict[str, Any] = {
            "source_code": context.request.source_code if context.request else "",
            "repository_context": repo_summary,
            "language": context.request.language if context.request else "python",
            "framework": context.request.framework if context.request else "pytest",
            "test_plan": str(context.test_plan) if context.test_plan else "",
            "candidate_code": context.candidate_tests[0].test_code if context.candidate_tests else "",
            "flaws": str(context.review_report.flaws) if context.review_report else "",
        }

        if custom_variables:
            var_dict.update(custom_variables)

        # Validate required variables
        missing_vars = [var for var in template.required_variables if var not in var_dict or var_dict[var] is None]
        if missing_vars:
            raise ValidationError("required_variables", f"Missing required prompt variables: {missing_vars}")

        # Render system and user prompts
        try:
            rendered_system = template.system_prompt.format(**var_dict)
            rendered_user = template.user_prompt.format(**var_dict)
        except KeyError as ke:
            raise ValidationError("template_rendering", f"Invalid placeholder variable in prompt: {ke}") from ke

        # Estimate tokens (approximation: 1 token ~ 4 characters)
        total_chars = len(rendered_system) + len(rendered_user)
        estimated_tokens = max(1, total_chars // 4)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        self.logger.info(
            "prompt_payload_rendered",
            template_id=template.template_id,
            agent=template.agent,
            estimated_tokens=estimated_tokens,
            elapsed_ms=elapsed_ms,
        )

        return PromptPayload(
            template_name=template.name,
            rendered_system=rendered_system,
            rendered_user=rendered_user,
            version=template.version,
            agent_name=template.agent,
            repository_summary=repo_summary[:200] + "...",
            prompt_version=template.version,
            estimated_tokens=estimated_tokens,
            metadata={
                "template_id": template.template_id,
                "render_duration_ms": elapsed_ms,
                "required_variables": template.required_variables,
            },
        )
