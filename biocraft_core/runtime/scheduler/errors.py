class SchedulerError(Exception):
    """Scheduler 错误基类。"""


class DAGCycleError(SchedulerError):
    """DAG 中存在环。"""


class MissingDependencyError(SchedulerError):
    """依赖了一个不在 DAG 中的任务名。"""


class DuplicateTaskError(SchedulerError):
    """DAG 中存在重名任务。"""
