"""TestGen AI v2.3 — AgentWorkflow Core Execution Engine

Stateful multi-agent execution orchestrator. Sequences PlannerAgent, GeneratorAgent,
ReviewerAgent, and RepairAgent while managing state transitions, structured logging,
context propagation, and exception handling.
"""

import time
import uuid
from typing import Dict, List, Optional
import structlog

from app.agents.base import BaseAgent
from app.domain.v23_models import AgentWorkflowContext, GenerationRequest
from app.exceptions.v23_exceptions import AgentExecutionError, ValidationError, WorkflowExecutionError
from app.workflows.states import WorkflowState, WorkflowStateMachine

logger = structlog.get_logger()


class AgentWorkflow:
    """Core execution engine for TestGen AI v2.3 multi-agent workflow."""

    def __init__(self, agents: Optional[List[BaseAgent]] = None) -> None:
        if agents is None:
            from app.agents.generator import GeneratorAgent
            from app.agents.planner import PlannerAgent
            from app.agents.repair import RepairAgent
            from app.agents.reviewer import ReviewerAgent

            agents = [
                PlannerAgent(),
                GeneratorAgent(),
                ReviewerAgent(),
                RepairAgent(),
            ]

        self.workflow_id = str(uuid.uuid4())
        self.state_machine = WorkflowStateMachine(WorkflowState.INITIALIZED)
        self.agents: List[BaseAgent] = agents
        self.logger = logger.bind(component="AgentWorkflow", workflow_id=self.workflow_id)

    @property
    def current_state(self) -> WorkflowState:
        """Get current workflow execution state."""
        return self.state_machine.current_state

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a cognitive agent into the workflow sequence."""
        self.agents.append(agent)
        self.logger.info("agent_registered", agent_name=agent.agent_name)

    def execute_workflow(self, request: GenerationRequest) -> AgentWorkflowContext:
        """Execute the multi-agent pipeline sequentially while updating state and context.

        Args:
            request: Incoming GenerationRequest payload.

        Returns:
            Updated AgentWorkflowContext.

        Raises:
            WorkflowExecutionError: On agent or workflow execution failures.
        """
        if request is None:
            self.state_machine.transition_to(WorkflowState.FAILED)
            raise ValidationError("request", "GenerationRequest cannot be None")

        context = AgentWorkflowContext(request=request)
        self.logger.info("agent_workflow_started", user_id=request.user_id)
        start_time = time.perf_counter()

        try:
            for agent in self.agents:
                if agent.target_state and agent.target_state != self.state_machine.current_state:
                    self.state_machine.transition_to(agent.target_state)

                agent_start = time.perf_counter()
                self.logger.info("agent_step_started", agent_name=agent.agent_name, state=self.current_state.value)
                
                # Execute agent with timing and error handling
                context = agent.run(context)

                agent_elapsed_ms = round((time.perf_counter() - agent_start) * 1000, 2)
                self.logger.info(
                    "agent_step_completed",
                    agent_name=agent.agent_name,
                    elapsed_ms=agent_elapsed_ms,
                    state=self.current_state.value,
                )

            # Mark workflow completed
            self.state_machine.transition_to(WorkflowState.COMPLETED)
            total_elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self.logger.info(
                "agent_workflow_completed",
                total_elapsed_ms=total_elapsed_ms,
                state=self.current_state.value,
                trace_count=len(context.reasoning_traces),
            )
            return context

        except AgentExecutionError as aee:
            self.state_machine.transition_to(WorkflowState.FAILED)
            self.logger.error(
                "agent_workflow_failed",
                agent_name=aee.agent_name,
                error=aee.message,
                state=self.current_state.value,
            )
            raise WorkflowExecutionError(self.workflow_id, aee.message) from aee
        except Exception as exc:
            self.state_machine.transition_to(WorkflowState.FAILED)
            self.logger.error("agent_workflow_unexpected_error", error=str(exc), state=self.current_state.value)
            raise WorkflowExecutionError(self.workflow_id, str(exc)) from exc
