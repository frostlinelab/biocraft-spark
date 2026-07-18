"""CPU resource pool and fan-out calculator.

Handles global runtime resource limits and computes parallelism
for plugin blocks that process multiple input files.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeConfig:
    """Global runtime resource limits. Set in Django settings as BIOCRAFT_RUNTIME."""
    cpu_cores: int = 4
    cpu_threads: int = 8
    memory_gb: int = 8
    max_parallel_containers: int = 8


@dataclass
class LanePlan:
    """Describes how many parallel instances to spawn for a fan-out block."""
    file_count: int          # total input files
    min_threads_per_instance: int  # plugin requirement
    max_parallel: int         # how many can run at once
    active_waves: int         # number of sequential waves
    lanes: list[list[str]]    # filenames grouped by wave

    @property
    def total_threads(self) -> int:
        return self.min_threads_per_instance * self.max_parallel

    @property
    def badge(self) -> str:
        return (
            f"{self.file_count} files · "
            f"{self.total_threads} threads / "
            f"{self.min_threads_per_instance} per instance"
        )


class ResourcePool:
    """Manages global CPU/memory constraints for container fan-out."""

    def __init__(self, config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig()

    def max_parallel(self, min_threads_per_instance: int) -> int:
        """Compute maximum parallel instances based on CPU thread count."""
        per_instance = max(1, min_threads_per_instance)
        max_by_cpu = self.config.cpu_threads // per_instance
        return min(self.config.max_parallel_containers, max_by_cpu)

    def calculate_lanes(
        self,
        filenames: list[str],
        min_threads_per_instance: int = 1,
    ) -> LanePlan:
        """Compute the lane plan for a given set of input files.

        Args:
            filenames: List of input file names to process.
            min_threads_per_instance: Minimum threads per container instance.

        Returns:
            LanePlan with wave grouping.
        """
        file_count = len(filenames)
        max_par = self.max_parallel(min_threads_per_instance)

        if max_par <= 0:
            max_par = 1

        # Group files into waves
        lanes: list[list[str]] = []
        for i in range(0, file_count, max_par):
            lanes.append(filenames[i : i + max_par])

        return LanePlan(
            file_count=file_count,
            min_threads_per_instance=min_threads_per_instance,
            max_parallel=max_par,
            active_waves=len(lanes),
            lanes=lanes,
        )

    def to_dict(self) -> dict:
        """Serialize config for the frontend."""
        return {
            "cpuCores": self.config.cpu_cores,
            "cpuThreads": self.config.cpu_threads,
            "memoryGb": self.config.memory_gb,
            "maxParallelContainers": self.config.max_parallel_containers,
        }
