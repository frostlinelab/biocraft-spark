# biocraft_core/runtime/executor/errors.py

class ContainerExecutorError(Exception):
    """Base error for container executor."""

class DockerUnavailableError(ContainerExecutorError):
    """Raised when Docker daemon is unavailable."""

class ContainerRunError(ContainerExecutorError):
    """Raised when a container fails to run correctly."""

class ContainerTimeoutError(ContainerExecutorError):
    """Raised when a container exceeds timeout."""
