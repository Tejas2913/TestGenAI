"""TestGen AI v2.3 — PlannerAgent Intelligence

Cognitive AI Agent responsible for converting RepositoryContext and GenerationRequest
into a structured TestPlan domain object through the Multi-LLM Provider Framework.
Implements automatic single-attempt repair on malformed LLM outputs.
"""

from typing import Any, Dict, Optional
import structlog

from app.agents.base import BaseAgent
from app.domain.planner_schema import map_json_to_test_plan, validate_planner_json
from app.domain.v23_models import AgentWorkflowContext, ProviderDecision, TestPlan
from app.exceptions.v23_exceptions import ValidationError
from app.infrastructure.indexers.repository_index import RepositoryContextIndex
from app.infrastructure.prompts.manager import PromptManager
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.states import WorkflowState

logger = structlog.get_logger()


class PlannerAgent(BaseAgent):
    """AI Cognitive Agent generating structured TestPlans via multi-provider routing and validation."""

    def __init__(
        self,
        repository_index: Optional[RepositoryContextIndex] = None,
        prompt_manager: Optional[PromptManager] = None,
        provider_router: Optional[LLMProviderRouter] = None,
    ) -> None:
        super().__init__(agent_name="PlannerAgent", target_state=WorkflowState.PLANNING)
        self.repository_index = repository_index or RepositoryContextIndex()
        self.prompt_manager = prompt_manager or PromptManager()
        self.provider_router = provider_router or LLMProviderRouter()

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Index repository, construct prompt payload, execute LLM call, validate & repair JSON, and map TestPlan.

        Args:
            context: Shared AgentWorkflowContext.

        Returns:
            Updated AgentWorkflowContext containing repository_context, test_plan, prompt_payload, provider_decision.
        """
        source_input = context.request.source_code

        # 1. Index source code / workspace directory
        repo_ctx = self.repository_index.build_context(source_input)
        context.repository_context = repo_ctx

        # 2. Build provider-agnostic PromptPayload via PromptManager
        prompt_payload = self.prompt_manager.build_prompt_payload(
            agent_name="planner",
            context=context,
        )
        context.prompt_payload = prompt_payload

        # 3. Execute initial LLM call via Provider Router
        provider_response = self.provider_router.execute_prompt(prompt_payload)

        # 4. Store ProviderDecision in AgentWorkflowContext
        decision = ProviderDecision(
            selected_provider=provider_response.provider_name,
            strategy_used="BalancedStrategy",
            estimated_cost=provider_response.estimated_cost,
            latency_ms=provider_response.latency_ms,
        )
        context.provider_decision = decision

        # 5. Validate & Repair Structured JSON Output
        raw_output = provider_response.response_text
        validated_data: Dict[str, Any] = {}
        repair_attempted = False

        try:
            validated_data = validate_planner_json(raw_output)
        except ValidationError as val_err:
            self.logger.warning(
                "planner_json_validation_failed_attempting_repair",
                error=str(val_err),
                raw_preview=raw_output[:150],
            )
            repair_attempted = True

            # Attempt 1 automatic repair prompt
            repair_payload = self.prompt_manager.build_prompt_payload(
                agent_name="planner_repair",
                context=context,
                custom_variables={"raw_output": raw_output, "error_message": str(val_err)},
            )
            repair_response = self.provider_router.execute_prompt(repair_payload)
            validated_data = validate_planner_json(repair_response.response_text)

        # 6. Map validated JSON to TestPlan domain model
        test_plan = map_json_to_test_plan(validated_data)
        context.test_plan = test_plan

        # 7. Record Reasoning Trace
        confidence = validated_data.get("confidence", 0.90)
        repair_msg = " (repaired after 1 attempt)" if repair_attempted else ""
        stats_summary = f"Planned {len(test_plan.target_functions)} functions, {len(test_plan.test_cases)} test cases via {provider_response.provider_name}{repair_msg}. Confidence: {confidence}."
        
        context.add_reasoning_trace(
            agent_name=self.agent_name,
            step_action="ai_driven_test_planning",
            rationale_summary=f"Populated RepositoryContext and generated structured TestPlan using {provider_response.provider_name}. {stats_summary}",
        )
        return context
