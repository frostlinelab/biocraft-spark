"""Resolve a React Flow node graph into executable TaskNode objects.

This bridges the gap between the visual editor (nodes + edges saved as JSON)
and the DAG execution engine (topologically-sorted TaskNode list).

Supports fan-out: when an Input node with N files is connected to a plugin
block, N parallel TaskNode instances are created — one per input file.
"""

from __future__ import annotations

from typing import Any

from biocraft_core.plugin.builtins import builtin_blocks
from biocraft_core.plugin.discovery import discover_plugins
from biocraft_core.plugin.schema import BlockSpec
from biocraft_core.runtime.resources import ResourcePool
from biocraft_core.runtime.scheduler.types import RetryPolicy, TaskIO, TaskNode


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

    Raises:
        ValueError: If a node references a block that can't be found.
    """
    nodes: list[dict] = graph.get("nodes", [])
    edges: list[dict] = graph.get("edges", [])

    # Build lookups
    block_by_key: dict[tuple[str, str], BlockSpec] = {}
    for b in block_specs:
        block_by_key[(b.plugin_name, b.name)] = b

    node_by_id: dict[str, dict] = {n["id"]: n for n in nodes if isinstance(n, dict)}

    # Build reverse adjacency for depends_on resolution
    reverse_adjacency: dict[str, list[str]] = {}
    for e in edges:
        if not isinstance(e, dict):
            continue
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src and tgt:
            reverse_adjacency.setdefault(tgt, []).append(src)

    # Find Input nodes and their file counts
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

    # Collect runtime blocks
    runtime_nodes: list[dict] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        data = n.get("data", {})
        plugin = data.get("blockPlugin", "")
        block_name = data.get("blockName", "")
        has_runtime = data.get("hasRuntime", False)

        if not has_runtime:
            continue

        block_spec = block_by_key.get((plugin, block_name))
        if block_spec is None:
            raise ValueError(
                f"Node {n.get('id')} references unknown block: "
                f"plugin='{plugin}', block='{block_name}'."
            )
        runtime_nodes.append(n)

    task_nodes: list[TaskNode] = []
    node_to_task_names: dict[str, list[str]] = {}

    for n in runtime_nodes:
        data = n.get("data", {})
        plugin = data.get("blockPlugin", "")
        block_name = data.get("blockName", "")
        block_spec = block_by_key[(plugin, block_name)]

        if block_spec.runtime is None:
            continue

        # Check for fan-out: does an Input node feed into this one?
        upstream_ids = reverse_adjacency.get(n.get("id", ""), [])
        all_input_files: list[str] = []
        for uid in upstream_ids:
            if uid in input_files_by_id:
                all_input_files.extend(input_files_by_id[uid])

        if all_input_files:
            # ── Fan-out: create one TaskNode per input file ────────
            min_threads = block_spec.runtime.resources.min_threads if block_spec.runtime.resources else 1
            pool = resource_pool or ResourcePool()
            lane_plan = pool.calculate_lanes(all_input_files, min_threads)

            task_names: list[str] = []
            for file_name in all_input_files:
                task_name = f"{block_spec.plugin_name}__{block_spec.name}__{n['id']}__{file_name}"
                task_names.append(task_name)

                depends_on: list[str] = []
                for uid in upstream_ids:
                    if uid in node_to_task_names:
                        depends_on.extend(node_to_task_names[uid])

                # Each fan-out instance gets one file as its input
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
                        command=list(block_spec.runtime.command),
                        env=dict(block_spec.runtime.env),
                        depends_on=tuple(depends_on),
                        inputs=inputs,
                        outputs=outputs,
                        retry=RetryPolicy(max_attempts=1, delay_seconds=1.0),
                    )
                )

            node_to_task_names[n["id"]] = task_names
        else:
            # ── Single instance ─────────────────────────────────────
            task_name = f"{block_spec.plugin_name}__{block_spec.name}__{n['id']}"
            task_names = [task_name]
            node_to_task_names[n["id"]] = task_names

            depends_on: list[str] = []
            for uid in upstream_ids:
                if uid in node_to_task_names:
                    depends_on.extend(node_to_task_names[uid])

            inputs = tuple(
                TaskIO(
                    pattern=p.pattern,
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
                    command=list(block_spec.runtime.command),
                    env=dict(block_spec.runtime.env),
                    depends_on=tuple(depends_on),
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
        plugin_specs = discover_plugins(plugins_dir)
        for ps in plugin_specs:
            specs.extend(ps.blocks)

    return specs
