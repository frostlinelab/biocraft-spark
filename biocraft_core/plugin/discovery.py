"""Plugin discovery — scan the plugins/ directory and load all plugin YAML files.

Each plugin can be in either the legacy "steps" format (pre-assembled pipeline)
or the new "blocks" format (individual draggable blocks).
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
import jsonschema

from biocraft_core.plugin.schema import (
    BlockPort,
    BlockParam,
    BlockResources,
    BlockRuntime,
    BlockSpec,
    PluginBlocksSpec,
)

logger = logging.getLogger(__name__)


def discover_plugins(plugins_dir: str | Path) -> list[PluginBlocksSpec]:
    """Scan *plugins_dir* for .plugin.yaml files and return loaded plugin specs.

    Invalid YAML files are logged and skipped — the server keeps running.
    """
    plugins_dir = Path(plugins_dir)
    if not plugins_dir.is_dir():
        logger.info("Plugin directory %s does not exist — no plugins loaded.", plugins_dir)
        return []

    plugins: list[PluginBlocksSpec] = []
    for yaml_file in sorted(plugins_dir.glob("*.plugin.yaml")):
        try:
            plugin = _load_plugin_file(yaml_file)
            if plugin is not None:
                plugins.append(plugin)
        except Exception:
            logger.exception("Failed to load plugin %s", yaml_file.name)

    return plugins


def _load_plugin_file(path: Path) -> PluginBlocksSpec | None:
    """Load and validate a single plugin YAML file.

    Supports both legacy (steps-based) and new (blocks-based) formats.
    """
    raw = yaml.safe_load(path.read_text())

    if not isinstance(raw, dict):
        logger.warning("Plugin %s is not a YAML mapping — skipping.", path.name)
        return None

    name = raw.get("name", "")
    if not name:
        logger.warning("Plugin %s has no 'name' field — skipping.", path.name)
        return None

    version = raw.get("version", "0.1")
    description = raw.get("description", "")
    icon = raw.get("icon", "process")

    # New format: "blocks" key
    if "blocks" in raw:
        blocks = _parse_blocks(raw["blocks"], plugin_name=name, plugin_version=version)
        return PluginBlocksSpec(
            name=name,
            version=version,
            description=description,
            icon=icon,
            blocks=blocks,
        )

    # Legacy format: "steps" key — convert each step to a bare BlockSpec
    if "steps" in raw:
        blocks = _convert_steps_to_blocks(
            raw["steps"], plugin_name=name, plugin_version=version
        )
        return PluginBlocksSpec(
            name=name,
            version=version,
            description=description,
            icon=icon,
            blocks=blocks,
        )

    logger.warning(
        "Plugin %s has neither 'blocks' nor 'steps' — skipping.", path.name
    )
    return None


def _parse_blocks(
    raw_blocks: list[dict],
    plugin_name: str,
    plugin_version: str,
) -> list[BlockSpec]:
    """Parse the new 'blocks' list format."""
    blocks: list[BlockSpec] = []
    for b in raw_blocks:
        if not isinstance(b, dict):
            continue

        # Runtime
        runtime_raw = b.get("runtime", {})
        runtime = None
        if runtime_raw:
            res_raw = runtime_raw.get("resources") or {}
            resources = BlockResources(
                min_threads=int(res_raw.get("min_threads", 1)),
                min_memory_gb=float(res_raw.get("min_memory_gb", 1.0)),
            )
            runtime = BlockRuntime(
                image=runtime_raw.get("image", ""),
                command=runtime_raw.get("command", []),
                env=runtime_raw.get("env", {}),
                resources=resources,
            )

        # Ports
        inputs = [
            BlockPort(
                name=p.get("name", ""),
                label=p.get("label", p.get("name", "")),
                port_type=p.get("type", "file"),
                pattern=p.get("pattern", ""),
                multiple=p.get("multiple", False),
            )
            for p in b.get("inputs", [])
            if isinstance(p, dict)
        ]
        outputs = [
            BlockPort(
                name=p.get("name", ""),
                label=p.get("label", p.get("name", "")),
                port_type=p.get("type", "file"),
                pattern=p.get("pattern", ""),
                multiple=p.get("multiple", False),
            )
            for p in b.get("outputs", [])
            if isinstance(p, dict)
        ]

        # Params
        params = [
            BlockParam(
                name=p.get("name", ""),
                label=p.get("label", p.get("name", "")),
                param_type=p.get("type", "string"),
                default=p.get("default"),
                min=p.get("min"),
                max=p.get("max"),
                options=p.get("options", []),
            )
            for p in b.get("params", [])
            if isinstance(p, dict)
        ]

        blocks.append(
            BlockSpec(
                name=b.get("name", ""),
                label=b.get("label", b.get("name", "")),
                description=b.get("description", ""),
                icon=b.get("icon", "process"),
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                runtime=runtime,
                inputs=inputs,
                outputs=outputs,
                params=params,
            )
        )

    return blocks


def _convert_steps_to_blocks(
    raw_steps: list[dict],
    plugin_name: str,
    plugin_version: str,
) -> list[BlockSpec]:
    """Convert legacy 'steps' to individual BlockSpecs for backwards compatibility."""
    blocks: list[BlockSpec] = []
    for step in raw_steps:
        if not isinstance(step, dict):
            continue

        step_name = step.get("name", "")
        runtime = BlockRuntime(
            image=step.get("image", ""),
            command=step.get("command", []),
            env=step.get("env", {}),
        )

        # Legacy format: inputs use "from" instead of "name"/"label"
        inputs = [
            BlockPort(
                name=inp.get("from", f"input_{i}"),
                label=inp.get("from", "Input"),
                port_type=inp.get("type", "file"),
                pattern=inp.get("pattern", ""),
            )
            for i, inp in enumerate(step.get("inputs", []))
            if isinstance(inp, dict)
        ]
        outputs = [
            BlockPort(
                name=f"output_{i}",
                label=out.get("pattern", "Output"),
                port_type=out.get("type", "file"),
                pattern=out.get("pattern", ""),
            )
            for i, out in enumerate(step.get("outputs", []))
            if isinstance(out, dict)
        ]

        blocks.append(
            BlockSpec(
                name=step_name,
                label=step_name.replace("-", " ").title(),
                description="",
                icon="process",
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                runtime=runtime,
                inputs=inputs,
                outputs=outputs,
                params=[],
            )
        )

    return blocks
