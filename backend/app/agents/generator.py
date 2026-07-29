"""TestGen AI v2.3 — GeneratorAgent Skeleton

Initial cognitive agent skeleton responsible for test case code generation.
Outputs a deterministic CandidateTest list into AgentWorkflowContext.
"""

from app.agents.base import BaseAgent
from app.domain.v23_models import AgentWorkflowContext, CandidateTest
from app.workflows.states import WorkflowState


class GeneratorAgent(BaseAgent):
    """Cognitive agent responsible for transforming a TestPlan into CandidateTest code."""

    def __init__(self) -> None:
        super().__init__(agent_name="GeneratorAgent", target_state=WorkflowState.GENERATING)

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Create deterministic default CandidateTest list and update context."""
        candidate = CandidateTest(
            test_name="test_sample_function_success",
            test_code="def test_sample_function_success():\n    assert True\n",
            target_function="sample_function",
            imports=["pytest"],
        )
        context.candidate_tests = [candidate]
        context.add_reasoning_trace(
            agent_name=self.agent_name,
            step_action="generate_candidate_tests",
            rationale_summary="Generated initial candidate test suite.",
        )
        return context
