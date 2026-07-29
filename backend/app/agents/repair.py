"""TestGen AI v2.3 — RepairAgent Skeleton

Initial cognitive agent skeleton responsible for test repair.
Appends RepairAction objects into AgentWorkflowContext if review report is unapproved.
"""

from app.agents.base import BaseAgent
from app.domain.v23_models import AgentWorkflowContext
from app.workflows.states import WorkflowState


class RepairAgent(BaseAgent):
    """Cognitive agent responsible for repairing failing or unapproved test code."""

    def __init__(self) -> None:
        super().__init__(agent_name="RepairAgent", target_state=WorkflowState.REPAIRING)

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Inspect ReviewReport and execute repair actions if unapproved."""
        if context.review_report and not context.review_report.is_approved:
            context.add_repair_action(
                repair_type="StaticSmellRepair",
                original_code="bad_code",
                repaired_code="repaired_code",
                reason="Fixed static review flaws.",
            )
            context.add_reasoning_trace(
                agent_name=self.agent_name,
                step_action="repair_test_code",
                rationale_summary="Applied surgical repair actions based on review feedback.",
            )
        else:
            context.add_reasoning_trace(
                agent_name=self.agent_name,
                step_action="skip_repair",
                rationale_summary="Test suite approved; no repair action required.",
            )
        return context
