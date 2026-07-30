"""TestGen AI v2.3 — RepairAgent Intelligence

Cognitive AI Agent responsible for surgically improving GeneratedTest objects using
ReviewReport feedback through the Multi-LLM Provider Framework.
Executes ONLY when ReviewReport is unapproved and implements automatic single-attempt repair.
"""

from typing import Any, Dict, Optional
import structlog

from app.agents.base import BaseAgent
from app.domain.repair_schema import map_json_to_repaired_tests, validate_repair_json
from app.domain.v23_models import AgentWorkflowContext, CandidateTest, ProviderDecision
from app.exceptions.v23_exceptions import ValidationError
from app.infrastructure.prompts.manager import PromptManager
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.states import WorkflowState

logger = structlog.get_logger()


class RepairAgent(BaseAgent):
    """AI Cognitive Agent repairing unapproved test code via multi-provider routing and validation."""

    def __init__(
        self,
        prompt_manager: Optional[PromptManager] = None,
        provider_router: Optional[LLMProviderRouter] = None,
    ) -> None:
        super().__init__(agent_name="RepairAgent", target_state=WorkflowState.REPAIRING)
        self.prompt_manager = prompt_manager or PromptManager()
        self.provider_router = provider_router or LLMProviderRouter()

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Inspect ReviewReport and execute AI repair ONLY if unapproved.

        Args:
            context: Shared AgentWorkflowContext containing review_report & generated_tests.

        Returns:
            Updated AgentWorkflowContext containing repaired generated_tests & repair_history.
        """
        review = context.review_report

        # 1. Conditional Execution: Skip repair if review is approved or missing
        if not review or review.is_approved:
            self.logger.info("repair_skipped_test_suite_approved")
            context.add_reasoning_trace(
                agent_name=self.agent_name,
                step_action="skip_repair",
                rationale_summary="Test suite approved; no repair action required.",
            )
            return context

        # 2. Extract flaws and candidate code for repair prompt
        flaws_text = str(review.flaws or review.issues or ["Unapproved static review flaws"])
        candidate_snippets = [gt.test_code for gt in context.generated_tests] if context.generated_tests else [ct.test_code for ct in context.candidate_tests]
        candidate_code = "\n\n".join(candidate_snippets) if candidate_snippets else "# No test code provided"

        # 3. Build provider-agnostic PromptPayload via PromptManager
        prompt_payload = self.prompt_manager.build_prompt_payload(
            agent_name="repair",
            context=context,
            custom_variables={
                "candidate_code": candidate_code,
                "flaws": flaws_text,
            },
        )
        context.prompt_payload = prompt_payload

        # 4. Execute initial LLM call via Provider Router
        provider_response = self.provider_router.execute_prompt(prompt_payload)

        # 5. Store ProviderDecision in AgentWorkflowContext
        decision = ProviderDecision(
            selected_provider=provider_response.provider_name,
            strategy_used="BalancedStrategy",
            estimated_cost=provider_response.estimated_cost,
            latency_ms=provider_response.latency_ms,
        )
        context.provider_decision = decision

        # 6. Validate & Repair Structured JSON Output
        raw_output = provider_response.response_text
        validated_data: Dict[str, Any] = {}
        repair_attempted = False

        try:
            validated_data = validate_repair_json(raw_output)
        except ValidationError as val_err:
            self.logger.warning(
                "repair_json_validation_failed_attempting_repair",
                error=str(val_err),
                raw_preview=raw_output[:150],
            )
            repair_attempted = True

            # Attempt 1 automatic repair prompt
            repair_payload = self.prompt_manager.build_prompt_payload(
                agent_name="repair_repair",
                context=context,
                custom_variables={"raw_output": raw_output, "error_message": str(val_err)},
            )
            repair_response = self.provider_router.execute_prompt(repair_payload)
            validated_data = validate_repair_json(repair_response.response_text)

        # 7. Map validated JSON to updated GeneratedTest and RepairAction list
        updated_tests, repair_actions = map_json_to_repaired_tests(
            data=validated_data,
            existing_tests=context.generated_tests,
        )
        context.generated_tests = updated_tests

        # Populate candidate_tests for complete backward compatibility
        context.candidate_tests = [
            CandidateTest(
                test_name=gt.test_name,
                test_code=gt.test_code,
                target_function=gt.target_function,
                imports=gt.imports,
            )
            for gt in updated_tests
        ]

        # Append RepairActions to context repair_history
        for action in repair_actions:
            context.repair_history.append(action)

        # 8. Record Reasoning Trace
        repair_msg = " (repaired JSON after 1 attempt)" if repair_attempted else ""
        stats_summary = f"Applied surgical repair using {provider_response.provider_name}. Repaired {len(repair_actions)} test(s){repair_msg}."

        context.add_reasoning_trace(
            agent_name=self.agent_name,
            step_action="ai_driven_test_repair",
            rationale_summary=f"Surgically repaired generated_tests using {provider_response.provider_name}. {stats_summary}",
        )
        return context
