"""TestGen AI v2.3 — Core Execution Engine Unit Tests (Phase 2).

Verifies AgentWorkflow execution lifecycle, state machine transitions, BaseAgent lifecycle hooks,
context propagation, error wrapping, structured logging, and dependency injection wiring.
"""

import pytest
from app.agents.base import BaseAgent
from app.agents.generator import GeneratorAgent
from app.agents.planner import PlannerAgent
from app.agents.repair import RepairAgent
from app.agents.reviewer import ReviewerAgent
from app.container import ApplicationContainer, get_container
from app.domain.v23_models import (
    AgentWorkflowContext,
    CandidateTest,
    GenerationRequest,
    RepairAction,
    ReviewReport,
    TestPlan,
)
from app.exceptions.v23_exceptions import (
    AgentExecutionError,
    ValidationError,
    WorkflowExecutionError,
    WorkflowStateError,
)
from app.workflows.agent_workflow import AgentWorkflow
from app.workflows.states import WorkflowState, WorkflowStateMachine


class FaultyAgent(BaseAgent):
    """Agent designed to simulate runtime failures for error handling tests."""

    def __init__(self) -> None:
        super().__init__(agent_name="FaultyAgent")

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        raise RuntimeError("Simulated agent failure")


class UnapprovedReviewerAgent(BaseAgent):
    """ReviewerAgent designed to output an unapproved ReviewReport to trigger RepairAgent."""

    def __init__(self) -> None:
        super().__init__(agent_name="UnapprovedReviewerAgent", target_state=WorkflowState.REVIEWING)

    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        context.review_report = ReviewReport(
            is_approved=False,
            flaws=["Duplicate assertions detected"],
        )
        return context


class TestWorkflowInitialization:
    """Workflow creation and initial state tests."""

    def test_workflow_instantiation_defaults(self):
        wf = AgentWorkflow()
        assert wf.workflow_id is not None
        assert wf.current_state == WorkflowState.INITIALIZED
        assert len(wf.agents) == 4
        assert isinstance(wf.agents[0], PlannerAgent)
        assert isinstance(wf.agents[1], GeneratorAgent)
        assert isinstance(wf.agents[2], ReviewerAgent)
        assert isinstance(wf.agents[3], RepairAgent)

    def test_agent_registration(self):
        wf = AgentWorkflow(agents=[])
        assert len(wf.agents) == 0
        agent = PlannerAgent()
        wf.register_agent(agent)
        assert len(wf.agents) == 1


class TestStateMachineTransitions:
    """WorkflowStateMachine validity and transition tests."""

    def test_valid_sequential_transitions(self):
        sm = WorkflowStateMachine()
        assert sm.current_state == WorkflowState.INITIALIZED

        assert sm.transition_to(WorkflowState.PLANNING) == WorkflowState.PLANNING
        assert sm.transition_to(WorkflowState.GENERATING) == WorkflowState.GENERATING
        assert sm.transition_to(WorkflowState.REVIEWING) == WorkflowState.REVIEWING
        assert sm.transition_to(WorkflowState.REPAIRING) == WorkflowState.REPAIRING
        assert sm.transition_to(WorkflowState.COMPLETED) == WorkflowState.COMPLETED

    def test_invalid_state_transition_raises(self):
        sm = WorkflowStateMachine()
        with pytest.raises(WorkflowStateError) as exc_info:
            sm.transition_to(WorkflowState.COMPLETED)
        assert "INITIALIZED" in str(exc_info.value)
        assert "COMPLETED" in str(exc_info.value)

    def test_failure_transitions_from_any_state(self):
        sm = WorkflowStateMachine()
        sm.transition_to(WorkflowState.PLANNING)
        assert sm.transition_to(WorkflowState.FAILED) == WorkflowState.FAILED


class TestBaseAgentLifecycle:
    """BaseAgent execution template method and lifecycle hooks tests."""

    def test_agent_before_execute_validation(self):
        agent = PlannerAgent()
        with pytest.raises(AgentExecutionError) as exc_info:
            agent.run(None)
        assert "context" in str(exc_info.value).lower()

    def test_agent_missing_request_validation(self):
        agent = PlannerAgent()
        ctx = AgentWorkflowContext(request=None)
        with pytest.raises(AgentExecutionError) as exc_info:
            agent.run(ctx)
        assert "request" in str(exc_info.value).lower()

    def test_agent_run_success_flow(self):
        agent = PlannerAgent()
        req = GenerationRequest(source_code="def foo(): pass")
        ctx = AgentWorkflowContext(request=req)
        result_ctx = agent.run(ctx)
        assert result_ctx.test_plan is not None
        assert len(result_ctx.reasoning_traces) == 1


class TestConcreteAgents:
    """PlannerAgent, GeneratorAgent, ReviewerAgent, RepairAgent execution tests."""

    def test_planner_agent_execution(self):
        agent = PlannerAgent()
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx = agent.run(ctx)

        assert isinstance(ctx.test_plan, TestPlan)
        assert "add" in ctx.test_plan.target_functions

    def test_generator_agent_execution(self):
        agent = GeneratorAgent()
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx = agent.run(ctx)

        assert len(ctx.candidate_tests) >= 1
        assert isinstance(ctx.candidate_tests[0], CandidateTest)
        assert "test_" in ctx.candidate_tests[0].test_name

    def test_reviewer_agent_execution(self):
        agent = ReviewerAgent()
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx = agent.run(ctx)

        assert isinstance(ctx.review_report, ReviewReport)
        assert ctx.review_report.is_approved is True

    def test_repair_agent_skip_when_approved(self):
        agent = RepairAgent()
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.review_report = ReviewReport(is_approved=True)
        ctx = agent.run(ctx)

        assert len(ctx.repair_history) == 0
        assert ctx.reasoning_traces[-1].step_action == "skip_repair"

    def test_repair_agent_applies_repair_when_unapproved(self):
        agent = RepairAgent()
        req = GenerationRequest(source_code="def add(a, b): return a + b")
        ctx = AgentWorkflowContext(request=req)
        ctx.review_report = ReviewReport(is_approved=False, flaws=["flaw1"])
        ctx = agent.run(ctx)

        assert len(ctx.repair_history) == 1
        assert isinstance(ctx.repair_history[0], RepairAction)
        assert "Repair" in ctx.repair_history[0].repair_type


class TestFullWorkflowExecution:
    """Full AgentWorkflow sequential execution and error handling tests."""

    def test_successful_workflow_execution(self):
        wf = AgentWorkflow()
        req = GenerationRequest(source_code="def multiply(x, y): return x * y", user_id="u1")
        ctx = wf.execute_workflow(req)

        assert wf.current_state == WorkflowState.COMPLETED
        assert ctx.test_plan is not None
        assert len(ctx.candidate_tests) == 1
        assert ctx.review_report is not None
        assert len(ctx.reasoning_traces) == 4

    def test_unapproved_flow_triggers_repair(self):
        agents = [
            PlannerAgent(),
            GeneratorAgent(),
            UnapprovedReviewerAgent(),
            RepairAgent(),
        ]
        wf = AgentWorkflow(agents=agents)
        req = GenerationRequest(source_code="def divide(a, b): return a / b")
        ctx = wf.execute_workflow(req)

        assert wf.current_state == WorkflowState.COMPLETED
        assert ctx.review_report.is_approved is False
        assert len(ctx.repair_history) == 1

    def test_none_request_raises_validation_error(self):
        wf = AgentWorkflow()
        with pytest.raises(ValidationError):
            wf.execute_workflow(None)
        assert wf.current_state == WorkflowState.FAILED

    def test_agent_failure_causes_workflow_failure(self):
        agents = [PlannerAgent(), FaultyAgent()]
        wf = AgentWorkflow(agents=agents)
        req = GenerationRequest(source_code="def foo(): pass")

        with pytest.raises(WorkflowExecutionError) as exc_info:
            wf.execute_workflow(req)

        assert wf.current_state == WorkflowState.FAILED
        assert "FaultyAgent" in str(exc_info.value)


class TestContainerIntegration:
    """IoC ApplicationContainer wiring verification."""

    def test_container_provides_wired_agent_workflow(self):
        container = get_container()
        wf = container.agent_workflow
        assert isinstance(wf, AgentWorkflow)
        assert len(wf.agents) == 4

        req = GenerationRequest(source_code="def test(): pass")
        ctx = wf.execute_workflow(req)
        assert wf.current_state == WorkflowState.COMPLETED
