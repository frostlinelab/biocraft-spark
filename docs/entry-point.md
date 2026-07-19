# Entry Point & Topological Layering

## How Biocraft finds the start of a workflow

There is no "Start" block.

The DAG engine does not require an explicit entry-point node. Instead it uses
demand-driven topological ordering:

### 1. The graph comes from the React Flow editor

Users drag an **Input** block onto the canvas, connect it to plugin blocks
(FastQC, Prokka, …), and wire those to downstream blocks. The resulting
`{ nodes, edges }` JSON is the only source of truth — every edge encodes a
data dependency or a control-flow signal.

### 2. `resolve_graph_to_task_nodes` skips decorative blocks

Every built-in block (`Input`) and the routing-only blocks have
`hasRuntime: false`.  The resolver iterates the React Flow node list and
**drops** any node where `hasRuntime` is falsy.  The surviving nodes are the
containerised blocks that actually need to run.

### 3. Kahn's algorithm finds natural roots

`DAGEngine.run()` calls `build_layers(nodes)`, which runs Kahn's topological
sort:

* Every node declares `depends_on` — a tuple of upstream task names.
* Nodes whose `depends_on` is empty after resolution have in-degree zero.
* Those nodes become **layer 0** and execute first.
* As each layer completes, downstream in-degrees are decremented and newly
  unblocked nodes enter the next layer.

In other words: the **first block in the data-flow chain** (the one whose
`depends_on` is empty) is the effective "entry point."  The **last block**
(the one nothing depends on) is the effective "exit point."  Both are
determined implicitly by the topology of the edges the user drew.

## Fan-out (multi-file parallelism)

When an Input node carries *N* files and is connected to a block with
`hasRuntime: true`, the resolver creates *N* copies of that block — one per
file.  Copies are grouped into **waves** computed from the system resource
pool:

```
If max_parallel = 4, min_threads = 2, and 7 files:

Wave 1           Wave 2
┌───────┐       ┌───────┐
│ file1 │ ────▶ │ file5 │
│ file2 │ ────▶ │ file6 │
│ file3 │ ────▶ │ file7 │
│ file4 │ ────▶ │       │
└───────┘       └───────┘
```

Tasks within a wave run in parallel (same `ThreadPoolExecutor` layer).
Tasks in wave *N+1* declare `depends_on` on every task in wave *N*, so the
executor will not start wave 2 before wave 1 finishes.

## Related files

| File | Role |
|------|------|
| `biocraft_core/plugin/resolver.py` | React Flow graph → `list[TaskNode]` with fan-out + waves |
| `biocraft_core/runtime/scheduler/dag.py` | Kahn topological sort (`build_layers`) |
| `biocraft_core/runtime/scheduler/engine.py` | `DAGEngine.run()` — layer-at-a-time `ThreadPoolExecutor` |
| `biocraft_core/runtime/resources.py` | `ResourcePool.calculate_lanes()` — wave grouping |
| `frontend/src/components/WorkflowCanvas.tsx` | Drag-and-drop graph editor |
| `frontend/src/components/nodes/PluginNode.tsx` | Per-node param editor + resource panel |

## Param substitution

Plugin YAML commands may contain `${params.name}` tokens. The resolver
replaces these with the actual `paramValues` stored on the React Flow node
before passing `command` to the container executor. See
`_substitute_params()` in `resolver.py`.
