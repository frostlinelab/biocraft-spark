from __future__ import annotations

import json
from pathlib import Path
from typing import IO

import yaml
import jsonschema

from biocraft_core.runtime.scheduler.types import RetryPolicy, TaskNode
from .schema import PluginSpec, StepRetry, StepSpec

_SCHEMA_PATH = Path(__file__).parent / "plugin_schema.json"
_schema: dict | None = None


def _get_schema() -> dict:
    global _schema
    if _schema is None:
        _schema = json.loads(_SCHEMA_PATH.read_text())
    return _schema


def load_plugin(source: str | Path | IO) -> tuple[PluginSpec, list[TaskNode]]:
    """Parse and validate a plugin YAML, returning (PluginSpec, list[TaskNode])."""
    if isinstance(source, (str, Path)):
        raw = yaml.safe_load(Path(source).read_text())
    else:
        raw = yaml.safe_load(source)

    jsonschema.validate(instance=raw, schema=_get_schema())

    steps: list[StepSpec] = []
    for s in raw["steps"]:
        retry_raw = s.get("retry", {})
        steps.append(
            StepSpec(
                name=s["name"],
                image=s["image"],
                command=s["command"],
                env=s.get("env", {}),
                depends_on=s.get("depends_on", []),
                retry=StepRetry(
                    max_attempts=retry_raw.get("max_attempts", 1),
                    delay_seconds=retry_raw.get("delay_seconds", 1.0),
                ),
            )
        )

    spec = PluginSpec(
        name=raw["name"],
        version=raw["version"],
        description=raw.get("description", ""),
        steps=steps,
    )

    nodes = [
        TaskNode(
            name=step.name,
            image=step.image,
            command=step.command,
            env=step.env,
            depends_on=tuple(step.depends_on),
            retry=RetryPolicy(
                max_attempts=step.retry.max_attempts,
                delay_seconds=step.retry.delay_seconds,
            ),
        )
        for step in steps
    ]

    return spec, nodes
