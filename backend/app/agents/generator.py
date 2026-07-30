"""TestGen AI v2.3 — GeneratorAgent Intelligence

Cognitive AI Agent responsible for converting validated TestPlan and RepositoryContext
into structured GeneratedTest domain objects through the Multi-LLM Provider Framework.
Implements automatic single-attempt repair on malformed LLM outputs.
"""

from typing import Any, Dict, Optional
import structlog

from app.agents.base import BaseAgent
from app.domain.generator_schema import map_json_to_generated_tests, validate_generator_json
from app.domain.v23_models import AgentWorkflowContext, CandidateTest, ProviderDecision, TestPlan
from app.exceptions.v23_exceptions import ValidationError
from app.infrastructure.prompts.manager import PromptManager
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.states import WorkflowState

logger = structlog.get_logger()


class GeneratorAgent(BaseAgent):
    """AI Cognitive Agent generating structured unit test code via multi-provider routing and validation."""

    def __init__(
        self,
        prompt_manager: Optional[PromptManager] = None,
        provider_router: Optional[LLMProviderRouter] = None,
    ) -> None:
        super().__init__(agent_name="GeneratorAgent", target_state=WorkflowState.GENERATING)
        self.prompt_manager = prompt_manager or PromptManager()
        self.provider_router = provider_router or LLMProviderRouter()

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Construct prompt payload, execute LLM call, validate & repair JSON, and map GeneratedTest models.

        Args:
            context: Shared AgentWorkflowContext containing repository_context & test_plan.

        Returns:
            Updated AgentWorkflowContext containing generated_tests list & reasoning trace.
        """
        plan = context.test_plan or TestPlan()
        plan_repr = str(plan)

        # 1. Build provider-agnostic PromptPayload via PromptManager
        prompt_payload = self.prompt_manager.build_prompt_payload(
            agent_name="generator",
            context=context,
            custom_variables={"test_plan": plan_repr},
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
            validated_data = validate_generator_json(raw_output)
        except ValidationError as val_err:
            self.logger.warning(
                "generator_json_validation_failed_attempting_repair",
                error=str(val_err),
                raw_preview=raw_output[:150],
            )
            repair_attempted = True

            # Attempt 1 automatic repair prompt
            repair_payload = self.prompt_manager.build_prompt_payload(
                agent_name="generator_repair",
                context=context,
                custom_variables={"raw_output": raw_output, "error_message": str(val_err)},
            )
            repair_response = self.provider_router.execute_prompt(repair_payload)
            validated_data = validate_generator_json(repair_response.response_text)

        # 5. Map validated JSON to GeneratedTest & CandidateTest domain models
        generated_tests = map_json_to_generated_tests(validated_data)
        context.generated_tests = generated_tests

        # Populate candidate_tests for complete backward compatibility
        candidate_list = [
            CandidateTest(
                test_name=gt.test_name,
                test_code=gt.test_code,
                target_function=gt.target_function,
                imports=gt.imports,
            )
            for gt in generated_tests
        ]
        context.candidate_tests = candidate_list

        # 6. Record Reasoning Trace
        repair_msg = " (repaired after 1 attempt)" if repair_attempted else ""
        stats_summary = f"Generated {len(generated_tests)} structured unit test(s) via {provider_response.provider_name}{repair_msg}."

        context.add_reasoning_trace(
            agent_name=self.agent_name,
            step_action="ai_driven_test_generation",
            rationale_summary=f"Populated generated_tests using {provider_response.provider_name}. {stats_summary}",
        )
        return context
