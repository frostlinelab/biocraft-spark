"""Resolve a React Flow node graph into executable TaskNode objects.

This bridges the gap between the visual editor (nodes + edges saved as JSON)
and the DAG execution engine (topologically-sorted TaskNode list).
"""

from __future__ import annotations

from typing import Any

from biocraft_core.plugin.builtins import builtin_blocks
from biocraft_core.plugin.discovery import discover_plugins
from biocraft_core.plugin.schema import BlockSpec
from biocraft_core.runtime.scheduler.types import RetryPolicy, TaskIO, TaskNode


def resolve_graph_to_task_nodes(
    graph: dict[str, Any],
    block_specs: list[BlockSpec],
) -> list[TaskNode]:
    """Convert a React Flow graph dict to a list of TaskNode ready for execution.

    Args:
        graph: Parsed JSON with "nodes" (list of dict) and "edges" (list of dict).
        block_specs: All available BlockSpec objects (builtins + plugins).

    Returns:
        list[TaskNode] sorted by topological order (for DAGEngine consumption).

    Built-in blocks (Start, End, Input, Output) are skipped — they contribute
    no container execution. Only blocks with hasRuntime=True produce TaskNodes.

    Raises:
        ValueError: If a node references a block that can't be found in block_specs,
                    or if the graph has no Start node.
    """
    nodes: list[dict] = graph.get("nodes", [])
    edges: list[dict] = graph.get("edges", [])

    # Build lookups
    block_by_key: dict[tuple[str, str], BlockSpec] = {}
    for b in block_specs:
        block_by_key[(b.plugin_name, b.name)] = b

    node_by_id: dict[str, dict] = {n["id"]: n for n in nodes if isinstance(n, dict)}

    # Build edge adjacency: source -> list of targets
    adjacency: dict[str, list[str]] = {}
    for e in edges:
        if not isinstance(e, dict):
            continue
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src and tgt:
            adjacency.setdefault(src, []).append(tgt)

    # Build reverse adjacency for depends_on resolution
    reverse_adjacency: dict[str, list[str]] = {}
    for e in edges:
        if not isinstance(e, dict):
            continue
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src and tgt:
            reverse_adjacency.setdefault(tgt, []).append(src)

    # Collect runtime blocks (skip builtins without runtime)
    runtime_nodes: list[dict] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        data = n.get("data", {})
        plugin = data.get("blockPlugin", "")
        block_name = data.get("blockName", "")
        has_runtime = data.get("hasRuntime", False)

        if not has_runtime:
            continue  # skip built-in control blocks

        block_spec = block_by_key.get((plugin, block_name))
        if block_spec is None:
            raise ValueError(
                f"Node {n.get('id')} references unknown block: "
                f"plugin='{plugin}', block='{block_name}'. "
                f"Available blocks: {list(block_by_key.keys())}"
            )
        runtime_nodes.append(n)

    # Determine per-node dependencies based on edges:
    # Node A depends on Node B if there is an edge A -> B (upstream feeds into downstream)
    # Wait... in React Flow, edges go output -> input, so the flow is:
    #   source (upstream) --edge--> target (downstream)
    # Meaning the target depends on the source.
    task_nodes: list[TaskNode] = []
    node_to_task_name: dict[str, str] = {}

    for n in runtime_nodes:
        data = n.get("data", {})
        plugin = data.get("blockPlugin", "")
        block_name = data.get("blockName", "")
        block_spec = block_by_key[(plugin, block_name)]

        if block_spec.runtime is None:
            continue

        # Determine task name (unique per node)
        task_name = f"{block_spec.plugin_name}__{block_spec.name}__{n['id']}"
        node_to_task_name[n["id"]] = task_name

        # This node depends on all upstream nodes that feed into it
        upstream_ids = reverse_adjacency.get(n.get("id", ""), [])
        depends_on: list[str] = []
        for uid in upstream_ids:
            if uid in node_to_task_name:
                depends_on.append(node_to_task_name[uid])

        # Build TaskIO for inputs/outputs
        inputs = tuple(
            TaskIO(
                pattern=p.pattern,
                io_type=p.port_type,
                from_step=None,  # resolved at container mount time
            )
            for p in block_spec.inputs
        )
        outputs = tuple(
            TaskIO(
                pattern=p.pattern,
                io_type=p.port_type,
            )
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
    """Get all available BlockSpec objects: builtins + discovered plugins.

    Args:
        plugins_dir: Path to plugins directory, or None to skip discovery.

    Returns:
        Combined list of all BlockSpec objects.
    """
    specs: list[BlockSpec] = list(builtin_blocks())

    if plugins_dir:
        plugin_specs = discover_plugins(plugins_dir)
        for ps in plugin_specs:
            specs.extend(ps.blocks)

    return specs
