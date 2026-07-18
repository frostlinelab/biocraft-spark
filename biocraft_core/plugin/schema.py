from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InputSpec:
    """一个输入声明：上游哪个 step 的哪种文件。"""
    pattern: str
    from_step: str | None = None  # None = 匹配所有上游依赖
    io_type: str = "file"  # "file" | "directory"


@dataclass
class OutputSpec:
    """一个输出声明：本 step 产出哪种文件。"""
    pattern: str
    io_type: str = "file"  # "file" | "directory"


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
    inputs: list[InputSpec] = field(default_factory=list)
    outputs: list[OutputSpec] = field(default_factory=list)
    retry: StepRetry = field(default_factory=StepRetry)


@dataclass
class PluginSpec:
    name: str
    version: str
    steps: list[StepSpec]
    description: str = ""
