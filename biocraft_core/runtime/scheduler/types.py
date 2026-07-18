from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1  # total attempts including first; 1 = no retry
    delay_seconds: float = 1.0


@dataclass(frozen=True)
class TaskIO:
    """一个输入或输出声明：pattern + 类型 + 可选的来源 step。"""
    pattern: str
    io_type: str = "file"  # "file" | "directory"
    from_step: str | None = None  # 仅 input 使用；None = 匹配所有上游


@dataclass(frozen=True)
class TaskNode:
    """DAG 中的一个任务节点 = 一次容器执行。"""

    name: str
    image: str
    command: list[str]
    depends_on: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    inputs: tuple[TaskIO, ...] = ()
    outputs: tuple[TaskIO, ...] = ()
    retry: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass
class TaskResult:
    name: str
    status: TaskStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    error: Optional[str] = None


@dataclass
class DAGRunResult:
    results: dict[str, TaskResult]

    @property
    def succeeded(self) -> bool:
        return all(result.status == TaskStatus.SUCCESS for result in self.results.values())

    def to_dict(self) -> dict:
        return {
            "succeeded": self.succeeded,
            "tasks": {
                name: {
                    "status": result.status.value,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": result.error,
                }
                for name, result in self.results.items()
            },
        }
