from __future__ import annotations

from collections import defaultdict, deque

from .errors import DAGCycleError, DuplicateTaskError, MissingDependencyError
from .types import TaskNode


def build_layers(nodes: list[TaskNode]) -> list[list[TaskNode]]:
    """
    Kahn's algorithm for topological layering. Nodes within a layer have no
    dependencies on each other and may execute in parallel.

    Raises:
        DuplicateTaskError: Duplicate task name
        MissingDependencyError: Dependency references a non-existent task
        DAGCycleError: Cycle detected
    """
    by_name: dict[str, TaskNode] = {}
    for node in nodes:
        if node.name in by_name:
            raise DuplicateTaskError(f"Duplicate task name: {node.name!r}")
        by_name[node.name] = node

    in_degree: dict[str, int] = {name: 0 for name in by_name}
    children: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        for dependency in node.depends_on:
            if dependency not in by_name:
                raise MissingDependencyError(
                    f"Task {node.name!r} depends on unknown task {dependency!r}"
                )
            children[dependency].append(node.name)
            in_degree[node.name] += 1

    layers: list[list[TaskNode]] = []
    frontier = deque(name for name, degree in in_degree.items() if degree == 0)
    visited = 0
    while frontier:
        layer_size = len(frontier)
        current_layer: list[TaskNode] = []
        for _ in range(layer_size):
            name = frontier.popleft()
            current_layer.append(by_name[name])
            visited += 1
            for child in children[name]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    frontier.append(child)
        layers.append(current_layer)

    if visited != len(by_name):
        unresolved = [name for name, degree in in_degree.items() if degree > 0]
        raise DAGCycleError(f"Cycle detected involving: {unresolved}")

    return layers
