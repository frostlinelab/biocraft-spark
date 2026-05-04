# biocraft_core/runtime/executor/types.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

class ContainerStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class VolumeMount:
    host_path: Path
    container_path: str
    mode: str = "rw"

    def to_docker_volume(self) -> dict[str, str]:
        return {
            "bind": self.container_path,
            "mode": self.mode,
        }

@dataclass(frozen=True)
class ContainerSpec:
    image: str
    command: str | Sequence[str] | None = None

    name: str | None = None
    working_dir: str | None = None

    environment: Mapping[str, str] = field(default_factory=dict)
    volumes: Sequence[VolumeMount] = field(default_factory=list)

    network: str | None = None
    user: str | None = None

    cpu_limit: float | None = None
    memory_limit: str | None = None

    timeout_seconds: int | None = None

    remove_after_run: bool = True
    pull_if_missing: bool = True

@dataclass(frozen=True)
class ContainerResult:
    container_id: str | None
    image: str
    command: str | Sequence[str] | None

    status: ContainerStatus
    exit_code: int | None

    stdout: str
    stderr: str

    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None

    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == ContainerStatus.SUCCEEDED and self.exit_code == 0
