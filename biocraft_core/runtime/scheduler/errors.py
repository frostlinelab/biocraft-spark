class SchedulerError(Exception):
    """Base exception for all scheduler errors."""


class DAGCycleError(SchedulerError):
    """A cycle was detected in the DAG."""


class MissingDependencyError(SchedulerError):
    """A task depends on a task name not present in the DAG."""


class DuplicateTaskError(SchedulerError):
    """Two tasks share the same name."""
