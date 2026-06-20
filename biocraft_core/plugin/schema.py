from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StepRetry:
    max_attempts: int = 1
    delay_seconds: float = 1.0


@dataclass
class StepSpec:
    name: str
    image: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    retry: StepRetry = field(default_factory=StepRetry)


@dataclass
class PluginSpec:
    name: str
    version: str
    steps: list[StepSpec]
    description: str = ""
