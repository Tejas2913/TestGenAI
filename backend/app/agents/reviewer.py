"""TestGen AI v2.3 — ReviewerAgent Intelligence

Cognitive AI Agent responsible for reviewing GeneratedTest domain objects, TestPlan,
and RepositoryContext to produce a structured ReviewReport through the Multi-LLM Provider Framework.
Implements automatic single-attempt repair on malformed LLM outputs.
"""

from typing import Any, Dict, Optional
import structlog

from app.agents.base import BaseAgent
from app.domain.reviewer_schema import map_json_to_review_report, validate_review_json
from app.domain.v23_models import AgentWorkflowContext, ProviderDecision, ReviewReport
from app.exceptions.v23_exceptions import ValidationError
from app.infrastructure.prompts.manager import PromptManager
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.states import WorkflowState

logger = structlog.get_logger()


class ReviewerAgent(BaseAgent):
    """AI Cognitive Agent reviewing candidate test code quality via multi-provider routing and validation."""

    def __init__(
        self,
        prompt_manager: Optional[PromptManager] = None,
        provider_router: Optional[LLMProviderRouter] = None,
    ) -> None:
        super().__init__(agent_name="ReviewerAgent", target_state=WorkflowState.REVIEWING)
        self.prompt_manager = prompt_manager or PromptManager()
        self.provider_router = provider_router or LLMProviderRouter()

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Construct prompt payload, execute LLM call, validate & repair JSON, and map ReviewReport model.

        Args:
            context: Shared AgentWorkflowContext containing generated_tests & repository_context.

        Returns:
            Updated AgentWorkflowContext containing review_report & reasoning trace.
        """
        # Format candidate code from generated_tests / candidate_tests for evaluation
        candidate_snippets = []
        tests = context.generated_tests or context.candidate_tests
        for test in tests:
            code = getattr(test, "test_code", str(test))
            candidate_snippets.append(code)
        
        candidate_code = "\n\n".join(candidate_snippets) if candidate_snippets else "# No candidate tests generated"

        # 1. Build provider-agnostic PromptPayload via PromptManager
        prompt_payload = self.prompt_manager.build_prompt_payload(
            agent_name="reviewer",
            context=context,
            custom_variables={"candidate_code": candidate_code},
        )
        context.prompt_payload = prompt_payload

        # 2. Execute initial LLM call via Provider Router
        provider_response = self.provider_router.execute_prompt(prompt_payload)

        # 3. Store ProviderDecision in AgentWorkflowContext
        decision = ProviderDecision(
            selected_provider=provider_response.provider_name,
            strategy_used="BalancedStrategy",
            estimated_cost=provider_response.estimated_cost,
            latency_ms=provider_response.latency_ms,
        )
        context.provider_decision = decision

        # 4. Validate & Repair Structured JSON Output
        raw_output = provider_response.response_text
        validated_data: Dict[str, Any] = {}
        repair_attempted = False

        try:
            validated_data = validate_review_json(raw_output)
        except ValidationError as val_err:
            self.logger.warning(
                "reviewer_json_validation_failed_attempting_repair",
                error=str(val_err),
                raw_preview=raw_output[:150],
            )
            repair_attempted = True

            # Attempt 1 automatic repair prompt
            repair_payload = self.prompt_manager.build_prompt_payload(
                agent_name="reviewer_repair",
                context=context,
                custom_variables={"raw_output": raw_output, "error_message": str(val_err)},
            )
            repair_response = self.provider_router.execute_prompt(repair_payload)
            validated_data = validate_review_json(repair_response.response_text)

        # 5. Map validated JSON to ReviewReport domain model
        review_report = map_json_to_review_report(validated_data)
        context.review_report = review_report

        # 6. Record Reasoning Trace
        repair_msg = " (repaired after 1 attempt)" if repair_attempted else ""
        stats_summary = f"Review score: {review_report.overall_score}/100. Approved: {review_report.is_approved}. Issues: {len(review_report.issues)}{repair_msg}."

        context.add_reasoning_trace(
            agent_name=self.agent_name,
            step_action="ai_driven_test_review",
            rationale_summary=f"Evaluated generated_tests using {provider_response.provider_name}. {stats_summary}",
        )
        return context
