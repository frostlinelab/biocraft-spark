from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from biocraft_core.runtime.executor import ContainerSpec, DockerContainerExecutor

from .dag import build_layers
from .types import DAGRunResult, TaskNode, TaskResult, TaskStatus


class DAGEngine:
    """
    v0.1 调度器:
      - 拓扑分层
      - 同层并行
      - 节点失败按 RetryPolicy 重试，耗尽后传播中止
      - 任意节点最终失败 -> 后续层全部 SKIPPED
      - 不做持久化
    """

    def __init__(self, executor: DockerContainerExecutor, max_workers: int = 4):
        self.executor = executor
        self.max_workers = max_workers

    def run(self, nodes: list[TaskNode]) -> DAGRunResult:
        layers = build_layers(nodes)
        results: dict[str, TaskResult] = {}
        aborted = False

        for layer in layers:
            if aborted:
                for node in layer:
                    results[node.name] = TaskResult(name=node.name, status=TaskStatus.SKIPPED)
                continue

            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                future_to_name = {
                    pool.submit(self._run_one, node): node.name for node in layer
                }
                for future in as_completed(future_to_name):
                    results[future_to_name[future]] = future.result()

            if any(results[node.name].status == TaskStatus.FAILED for node in layer):
                aborted = True

        return DAGRunResult(results=results)

    def _run_one(self, node: TaskNode) -> TaskResult:
        policy = node.retry
        result: TaskResult | None = None

        for attempt in range(policy.max_attempts):
            result = self._execute_once(node)
            if result.status == TaskStatus.SUCCESS:
                return result
            if attempt < policy.max_attempts - 1:
                time.sleep(policy.delay_seconds)

        return result  # type: ignore[return-value]

    def _execute_once(self, node: TaskNode) -> TaskResult:
        try:
            exec_result = self.executor.run(
                ContainerSpec(
                    image=node.image,
                    command=node.command,
                    environment=node.env,
                )
            )
        except Exception as exc:
            return TaskResult(
                name=node.name,
                status=TaskStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
            )

        status = TaskStatus.SUCCESS if exec_result.exit_code == 0 else TaskStatus.FAILED
        return TaskResult(
            name=node.name,
            status=status,
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
            exit_code=exec_result.exit_code,
            error=exec_result.error_message,
        )
