"""TestGen AI v2.3 — PromptManager Implementation

Central coordinator for the Prompt Management System.
Acts as the single entry point for agents requesting rendered, validated PromptPayloads.
"""

from typing import Any, Dict, Optional
import structlog

from app.domain.prompt_template import PromptTemplate
from app.domain.v23_models import AgentWorkflowContext, PromptPayload
from app.infrastructure.prompts.builder import PromptBuilder
from app.infrastructure.prompts.repository import PromptRepository

logger = structlog.get_logger()


class PromptManager:
    """Central entry point manager for prompt selection, validation, and rendering."""

    def __init__(
        self,
        repository: Optional[PromptRepository] = None,
        builder: Optional[PromptBuilder] = None,
    ) -> None:
        self.repository = repository or PromptRepository()
        self.builder = builder or PromptBuilder()
        self.logger = logger.bind(component="PromptManager")

    def load_template(self, agent_name: str, version: str = "v2.3") -> PromptTemplate:
        """Fetch versioned PromptTemplate by agent name."""
        return self.repository.get_template(agent_name=agent_name, version=version)

    def build_prompt_payload(
        self,
        agent_name: str,
        context: AgentWorkflowContext,
        version: str = "v2.3",
        custom_variables: Optional[Dict[str, Any]] = None,
    ) -> PromptPayload:
        """Fetch template, validate, and render provider-agnostic PromptPayload.

        Args:
            agent_name: Name of agent requesting prompt (planner, generator, reviewer, repair).
            context: Shared AgentWorkflowContext.
            version: Template version string (default: "v2.3").
            custom_variables: Optional variable overrides.

        Returns:
            Rendered PromptPayload object.
        """
        self.logger.info("prompt_request_received", agent=agent_name, version=version)
        template = self.load_template(agent_name=agent_name, version=version)
        return self.builder.build_payload(template=template, context=context, custom_variables=custom_variables)

    def get_prompt(
        self,
        template_name: str,
        repository_context: Optional[Any] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> PromptPayload:
        """Backward compatibility helper for scaffolding tests."""
        from app.domain.v23_models import AgentWorkflowContext, RepositoryContext
        repo_ctx = repository_context if isinstance(repository_context, RepositoryContext) else RepositoryContext()
        dummy_context = AgentWorkflowContext(request=None, repository_context=repo_ctx)
        agent_key = template_name if template_name.lower() in ("planner", "generator", "reviewer", "repair") else "planner"
        return self.build_prompt_payload(agent_name=agent_key, context=dummy_context, custom_variables=variables)
