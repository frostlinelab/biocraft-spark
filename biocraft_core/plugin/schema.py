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


# ── Block-based plugin (v2) ───────────────────────────────────────────


@dataclass
class BlockPort:
    """A typed input or output port on a block node."""
    name: str
    label: str = ""
    port_type: str = "file"  # "file" | "directory" | "string" | "number" | "signal"
    pattern: str = ""         # file glob, e.g. "*.fastq"
    multiple: bool = False    # whether multiple values are accepted


@dataclass
class BlockParam:
    """A configurable parameter exposed in the Node Inspector."""
    name: str
    label: str = ""
    param_type: str = "string"  # "string" | "integer" | "float" | "boolean" | "select"
    default: str | int | float | bool | None = None
    min: int | float | None = None
    max: int | float | None = None
    options: list[str] = field(default_factory=list)  # for "select" type


@dataclass
class BlockRuntime:
    """Container execution spec for a block."""
    image: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class BlockSpec:
    """A single draggable block contributed by a plugin (or built-in)."""
    name: str                      # unique ID within the defining scope
    label: str = ""                # palette display name
    description: str = ""          # tooltip / help text
    icon: str = "process"          # icon key: "start" | "end" | "input" | "output" | "process" | "beaker" | "microscope" | "dna" | "filter" | "wrench"
    plugin_name: str = ""          # owning plugin (empty = built-in)
    plugin_version: str = ""       # plugin version
    runtime: BlockRuntime | None = None  # None for built-in blocks that don't execute containers
    inputs: list[BlockPort] = field(default_factory=list)
    outputs: list[BlockPort] = field(default_factory=list)
    params: list[BlockParam] = field(default_factory=list)


@dataclass
class PluginBlocksSpec:
    """Top-level plugin spec for the blocks-based format."""
    name: str
    version: str
    description: str = ""
    icon: str = "process"
    blocks: list[BlockSpec] = field(default_factory=list)
