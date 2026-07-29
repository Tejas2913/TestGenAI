"""TestGen AI v2.3 — PlannerAgent Skeleton

Initial cognitive agent skeleton responsible for test planning.
Outputs a deterministic default TestPlan object into AgentWorkflowContext.
"""

from app.agents.base import BaseAgent
from app.domain.v23_models import AgentWorkflowContext, TestPlan
from app.workflows.states import WorkflowState


class PlannerAgent(BaseAgent):
    """Cognitive agent responsible for creating a structured TestPlan."""

    def __init__(self) -> None:
        super().__init__(agent_name="PlannerAgent", target_state=WorkflowState.PLANNING)

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Create deterministic default TestPlan and update context."""
        plan = TestPlan(
            target_functions=["sample_function"],
            test_cases=[{"case_id": 1, "description": "Test normal execution path"}],
            mock_requirements=[],
            edge_cases=["Empty input validation"],
        )
        context.test_plan = plan
        context.add_reasoning_trace(
            agent_name=self.agent_name,
            step_action="create_test_plan",
            rationale_summary="Formulated deterministic initial test planning blueprint.",
        )
        return context
