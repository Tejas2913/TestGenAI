"""TestGen AI v2.3 — Workflow State Machine

Defines valid execution states and enforces valid state transition logic.
"""

from enum import Enum
from typing import Dict, Set
import structlog

from app.exceptions.v23_exceptions import WorkflowStateError

logger = structlog.get_logger()


class WorkflowState(str, Enum):
    """Workflow execution state enum."""

    INITIALIZED = "INITIALIZED"
    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    REVIEWING = "REVIEWING"
    REPAIRING = "REPAIRING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Valid state transitions mapping
VALID_TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
    WorkflowState.INITIALIZED: {WorkflowState.PLANNING, WorkflowState.FAILED},
    WorkflowState.PLANNING: {WorkflowState.GENERATING, WorkflowState.COMPLETED, WorkflowState.FAILED},
    WorkflowState.GENERATING: {WorkflowState.REVIEWING, WorkflowState.COMPLETED, WorkflowState.FAILED},
    WorkflowState.REVIEWING: {WorkflowState.REPAIRING, WorkflowState.COMPLETED, WorkflowState.FAILED},
    WorkflowState.REPAIRING: {WorkflowState.REVIEWING, WorkflowState.COMPLETED, WorkflowState.FAILED},
    WorkflowState.COMPLETED: set(),
    WorkflowState.FAILED: set(),
}


class WorkflowStateMachine:
    """Manages and validates state transitions for AgentWorkflow."""

    def __init__(self, initial_state: WorkflowState = WorkflowState.INITIALIZED) -> None:
        self._current_state = initial_state
        self.logger = logger.bind(component="WorkflowStateMachine")

    @property
    def current_state(self) -> WorkflowState:
        """Get the current state."""
        return self._current_state

    def transition_to(self, target_state: WorkflowState) -> WorkflowState:
        """Transition current state to target state if valid.

        Args:
            target_state: WorkflowState to transition to.

        Returns:
            Updated WorkflowState.

        Raises:
            WorkflowStateError: If transition is invalid.
        """
        allowed = VALID_TRANSITIONS.get(self._current_state, set())
        if target_state not in allowed:
            self.logger.error(
                "invalid_state_transition",
                current_state=self._current_state.value,
                target_state=target_state.value,
            )
            raise WorkflowStateError(
                current_state=self._current_state.value,
                target_state=target_state.value,
            )

        self.logger.info(
            "state_transition",
            from_state=self._current_state.value,
            to_state=target_state.value,
        )
        self._current_state = target_state
        return self._current_state
