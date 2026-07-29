"""TestGen AI v2.3 — ReviewerAgent Skeleton

Initial cognitive agent skeleton responsible for static test code review.
Outputs a deterministic ReviewReport object into AgentWorkflowContext.
"""

from app.agents.base import BaseAgent
from app.domain.v23_models import AgentWorkflowContext, ReviewReport
from app.workflows.states import WorkflowState


class ReviewerAgent(BaseAgent):
    """Cognitive agent responsible for reviewing CandidateTest code quality statically."""

    def __init__(self) -> None:
        super().__init__(agent_name="ReviewerAgent", target_state=WorkflowState.REVIEWING)

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Create deterministic default ReviewReport and update context."""
        report = ReviewReport(
            is_approved=True,
            flaws=[],
            missing_assertions=[],
            smell_diagnostics=[],
        )
        context.review_report = report
        context.add_reasoning_trace(
            agent_name=self.agent_name,
            step_action="review_candidate_tests",
            rationale_summary="Reviewed candidate test suite; approved without flaws.",
        )
        return context
