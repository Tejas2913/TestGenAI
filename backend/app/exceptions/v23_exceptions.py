"""TestGen AI v2.3 — Workflow & Agent Exception Hierarchy

Standardized exception classes for workflow execution, state transitions, validation, and agent execution failures.
"""


class WorkflowError(Exception):
    """Base exception for all TestGen AI v2.3 workflow errors."""

    def __init__(self, message: str, details: float = None) -> None:
        super().__init__(message)
        self.message = message


class AgentExecutionError(WorkflowError):
    """Raised when an individual cognitive agent fails during execution."""

    def __init__(self, agent_name: str, message: str, original_exception: Exception = None) -> None:
        super().__init__(f"Agent [{agent_name}] execution failed: {message}")
        self.agent_name = agent_name
        self.original_exception = original_exception


class WorkflowExecutionError(WorkflowError):
    """Raised when the AgentWorkflow execution fails unexpectedly."""

    def __init__(self, workflow_id: str, message: str) -> None:
        super().__init__(f"Workflow [{workflow_id}] error: {message}")
        self.workflow_id = workflow_id


class WorkflowStateError(WorkflowError):
    """Raised when an invalid workflow state transition is attempted."""

    def __init__(self, current_state: str, target_state: str) -> None:
        super().__init__(f"Invalid workflow state transition: '{current_state}' -> '{target_state}'")
        self.current_state = current_state
        self.target_state = target_state


class ValidationError(WorkflowError):
    """Raised when input parameters or AgentWorkflowContext state validation fails."""

    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(f"Validation failed for '{field_name}': {message}")
        self.field_name = field_name


class ProviderError(WorkflowError):
    """Base exception for LLM provider errors."""

    def __init__(self, provider_name: str, message: str) -> None:
        super().__init__(f"Provider [{provider_name}] error: {message}")
        self.provider_name = provider_name


class ProviderTimeoutError(ProviderError):
    """Raised when provider call times out."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when provider is down or unreachable."""
    pass


class ProviderAuthenticationError(ProviderError):
    """Raised when provider API key authentication fails."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded."""
    pass
