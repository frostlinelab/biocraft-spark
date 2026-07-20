"""Resolve a React Flow node graph into executable TaskNode objects.

This bridges the gap between the visual editor (nodes + edges saved as JSON)
and the DAG execution engine (topologically-sorted TaskNode list).

Supports fan-out: when an Input node with N files is connected to a plugin
block, N parallel TaskNode instances are created — one per input file.
Fan-out is batched into sequential *waves* so the thread pool is never
overloaded: wave N+1 only starts after all of wave N completes.

Param template substitution: ${params.name} tokens in plugin YAML commands
are replaced with the node's current paramValues before execution.
"""

from __future__ import annotations

import re
from typing import Any

from biocraft_core.plugin.builtins import builtin_blocks
from biocraft_core.plugin.discovery import discover_plugins
from biocraft_core.plugin.schema import BlockSpec
from biocraft_core.runtime.resources import ResourcePool
from biocraft_core.runtime.scheduler.types import RetryPolicy, TaskIO, TaskNode


# ── Param template substitution ──────────────────────────────────────────────

_PARAM_RE = re.compile(r"\$\{params\.([^}]+)\}")


def _substitute_params(command: list[str], param_values: dict[str, Any]) -> list[str]:
    """Replace ``${params.name}`` tokens in every command token.

    Unknown keys are left as-is so the container sees the literal string and
    the operator knows something is misconfigured.
    """
    def _replace(token: str) -> str:
        return _PARAM_RE.sub(
            lambda m: str(param_values.get(m.group(1), m.group(0))),
            token,
        )
    return [_replace(t) for t in command]


def _build_param_values(
    node_data: dict[str, Any],
    block_spec: BlockSpec,
) -> dict[str, Any]:
    """Merge node's saved paramValues with block defaults for any missing keys."""
    saved: dict[str, Any] = node_data.get("paramValues") or {}
    merged: dict[str, Any] = {}
    for p in block_spec.params:
        merged[p.name] = saved.get(p.name, p.default)
    return merged


# ── Graph resolution ─────────────────────────────────────────────────────────

def resolve_graph_to_task_nodes(
    graph: dict[str, Any],
    block_specs: list[BlockSpec],
    resource_pool: ResourcePool | None = None,
) -> list[TaskNode]:
    """Convert a React Flow graph dict to a list of TaskNode ready for execution.

    Args:
        graph: Parsed JSON with "nodes" (list of dict) and "edges" (list of dict).
        block_specs: All available BlockSpec objects (builtins + plugins).
        resource_pool: Optional ResourcePool for fan-out lane calculation.

    Returns:
        list[TaskNode] for DAGEngine consumption.

    Built-in blocks (Start, End, Input) are skipped — they contribute
    no container execution. Only blocks with hasRuntime=True produce TaskNodes.

    Fan-out is split into sequential waves: tasks within a wave run in parallel,
    but wave N+1's tasks declare depends_on for all of wave N.

    Raises:
        ValueError: If a node references a block that can't be found.
    """
    nodes: list[dict] = graph.get("nodes", [])
    edges: list[dict] = graph.get("edges", [])

    # ── Build lookups ─────────────────────────────────────────────────────────
    block_by_key: dict[tuple[str, str], BlockSpec] = {
        (b.plugin_name, b.name): b for b in block_specs
    }
    node_by_id: dict[str, dict] = {
        n["id"]: n for n in nodes if isinstance(n, dict)
    }

    # target_id → [source_id, ...]
    reverse_adjacency: dict[str, list[str]] = {}
    for e in edges:
        if not isinstance(e, dict):
            continue
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src and tgt:
            reverse_adjacency.setdefault(tgt, []).append(src)

    # Input nodes → list of file names
    input_files_by_id: dict[str, list[str]] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        data = n.get("data", {})
        if data.get("blockName") == "input":
            files = data.get("files", [])
            if isinstance(files, list):
                input_files_by_id[n["id"]] = [
                    f.get("name", f"file_{i}") if isinstance(f, dict) else str(f)
                    for i, f in enumerate(files)
                ]

    # Collect runtime nodes (skip built-ins)
    runtime_nodes: list[dict] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        data = n.get("data", {})
        plugin = data.get("blockPlugin", "")
        block_name = data.get("blockName", "")
        if not data.get("hasRuntime", False):
            continue
        if (plugin, block_name) not in block_by_key:
            raise ValueError(
                f"Node {n.get('id')} references unknown block: "
                f"plugin='{plugin}', block='{block_name}'."
            )
        runtime_nodes.append(n)

    # ── Build TaskNodes ───────────────────────────────────────────────────────
    task_nodes: list[TaskNode] = []
    # node_id → flat list of all task names produced (across all waves)
    node_to_task_names: dict[str, list[str]] = {}
    # Count how many times each (plugin, block) pair appears so task names
    # carry a stable ordinal rather than the transient canvas node id.
    block_ordinal: dict[tuple[str, str], int] = {}

    for n in runtime_nodes:
        node_id: str = n.get("id", "")
        data = n.get("data", {})
        plugin = data.get("blockPlugin", "")
        block_name = data.get("blockName", "")
        block_key = (plugin, block_name)
        block_spec = block_by_key[block_key]

        block_ordinal[block_key] = block_ordinal.get(block_key, 0) + 1
        ordinal = block_ordinal[block_key]

        if block_spec.runtime is None:
            continue

        param_values = _build_param_values(data, block_spec)
        command = _substitute_params(list(block_spec.runtime.command), param_values)

        upstream_ids = reverse_adjacency.get(node_id, [])

        # Upstream plugin nodes that this node depends on (non-input)
        chain_dep_names: list[str] = []
        for uid in upstream_ids:
            if uid not in input_files_by_id and uid in node_to_task_names:
                chain_dep_names.extend(node_to_task_names[uid])

        # Collect input files from upstream Input nodes
        all_input_files: list[str] = []
        for uid in upstream_ids:
            if uid in input_files_by_id:
                all_input_files.extend(input_files_by_id[uid])

        if all_input_files:
            # ── Fan-out with wave batching ────────────────────────────────────
            min_threads = (
                block_spec.runtime.resources.min_threads
                if block_spec.runtime.resources
                else 1
            )
            pool = resource_pool or ResourcePool()
            lane_plan = pool.calculate_lanes(all_input_files, min_threads)

            all_names: list[str] = []
            prev_wave_names: list[str] = []

            for wave_files in lane_plan.lanes:
                this_wave_names: list[str] = []

                for file_name in wave_files:
                    task_name = (
                        f"{block_spec.plugin_name}__{block_spec.name}"
                        f"__{ordinal}__{file_name}"
                    )
                    this_wave_names.append(task_name)

                    # First wave depends on chain deps; subsequent waves on prev wave
                    depends_on = list(dict.fromkeys(chain_dep_names + prev_wave_names))

                    inputs = tuple(
                        TaskIO(
                            pattern=p.pattern if p.pattern else file_name,
                            io_type=p.port_type,
                            from_step=None,
                        )
                        for p in block_spec.inputs
                    )
                    outputs = tuple(
                        TaskIO(pattern=p.pattern, io_type=p.port_type)
                        for p in block_spec.outputs
                    )

                    task_nodes.append(
                        TaskNode(
                            name=task_name,
                            image=block_spec.runtime.image,
                            command=command,
                            env=dict(block_spec.runtime.env),
                            depends_on=tuple(depends_on),
                            inputs=inputs,
                            outputs=outputs,
                            retry=RetryPolicy(max_attempts=1, delay_seconds=1.0),
                        )
                    )

                all_names.extend(this_wave_names)
                prev_wave_names = this_wave_names

            node_to_task_names[node_id] = all_names

        else:
            # ── Single instance ───────────────────────────────────────────────
            task_name = f"{block_spec.plugin_name}__{block_spec.name}__{ordinal}"
            node_to_task_names[node_id] = [task_name]

            inputs = tuple(
                TaskIO(pattern=p.pattern, io_type=p.port_type, from_step=None)
                for p in block_spec.inputs
            )
            outputs = tuple(
                TaskIO(pattern=p.pattern, io_type=p.port_type)
                for p in block_spec.outputs
            )

            task_nodes.append(
                TaskNode(
                    name=task_name,
                    image=block_spec.runtime.image,
                    command=command,
                    env=dict(block_spec.runtime.env),
                    depends_on=tuple(chain_dep_names),
                    inputs=inputs,
                    outputs=outputs,
                    retry=RetryPolicy(max_attempts=1, delay_seconds=1.0),
                )
            )

    return task_nodes


def get_all_block_specs(plugins_dir: str | None = None) -> list[BlockSpec]:
    """Get all available BlockSpec objects: builtins + discovered plugins."""
    specs: list[BlockSpec] = list(builtin_blocks())
    if plugins_dir:
        for ps in discover_plugins(plugins_dir):
            specs.extend(ps.blocks)
    return specs
