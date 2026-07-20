# biocraft_core/runtime/executor/docker_executor.py

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import (
    ContainerRunError,
    ContainerTimeoutError,
    DockerUnavailableError,
)
from .types import ContainerResult, ContainerSpec, ContainerStatus, VolumeMount
from collections.abc import Sequence



class DockerContainerExecutor:
    def __init__(
        self,
        docker_base_url: str | None = None,
        default_timeout_seconds: int = 60 * 60,
    ) -> None:
        self.docker_base_url = docker_base_url
        self.default_timeout_seconds = default_timeout_seconds
        self._client = None

    def _get_docker(self):
        if self._client is not None:
            return self._client

        try:
            import docker
            from docker.errors import DockerException
        except ImportError as exc:
            raise DockerUnavailableError(
                "Docker SDK is not installed. Run: pip install docker"
            ) from exc

        try:
            if self.docker_base_url:
                self._client = docker.DockerClient(base_url=self.docker_base_url)
            else:
                self._client = docker.from_env()

            self._client.ping()
            return self._client

        except DockerException as exc:
            raise DockerUnavailableError(
                "Docker daemon is unavailable. Check Docker socket mount."
            ) from exc

    def ping(self) -> bool:
        client = self._get_docker()
        return bool(client.ping())

    def run(self, spec: ContainerSpec) -> ContainerResult:
        client = self._get_docker()

        timeout_seconds = spec.timeout_seconds or self.default_timeout_seconds
        started_monotonic = time.monotonic()
        started_at = _utc_now_iso()

        container = None
        container_id = None

        try:
            if spec.pull_if_missing:
                self._pull_image_if_missing(spec.image)

            docker_volumes = _build_docker_volumes(spec.volumes)

            host_config_kwargs: dict[str, Any] = {}

            if spec.cpu_limit is not None:
                host_config_kwargs["nano_cpus"] = int(spec.cpu_limit * 1_000_000_000)

            if spec.memory_limit is not None:
                host_config_kwargs["mem_limit"] = spec.memory_limit

            container = client.containers.create(
                image=spec.image,
                command=spec.command,
                name=spec.name,
                working_dir=spec.working_dir,
                environment=dict(spec.environment),
                volumes=docker_volumes,
                network=spec.network,
                user=spec.user,
                detach=True,
                **host_config_kwargs,
            )

            container_id = container.id
            container.start()

            exit_code = self._wait_for_container(
                container=container,
                timeout_seconds=timeout_seconds,
            )

            stdout, stderr = self._read_logs(container)

            finished_at = _utc_now_iso()
            duration_seconds = round(time.monotonic() - started_monotonic, 3)

            if exit_code == 0:
                status = ContainerStatus.SUCCEEDED
                error_message = None
            else:
                status = ContainerStatus.FAILED
                error_message = f"Container exited with code {exit_code}"

            return ContainerResult(
                container_id=container_id,
                image=spec.image,
                command=spec.command,
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                error_message=error_message,
            )

        except ContainerTimeoutError as exc:
            stdout, stderr = self._safe_read_logs(container)

            if container is not None:
                self._safe_kill(container)

            finished_at = _utc_now_iso()
            duration_seconds = round(time.monotonic() - started_monotonic, 3)

            return ContainerResult(
                container_id=container_id,
                image=spec.image,
                command=spec.command,
                status=ContainerStatus.TIMEOUT,
                exit_code=None,
                stdout=stdout,
                stderr=stderr,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                error_message=str(exc),
            )

        except Exception as exc:
            stdout, stderr = self._safe_read_logs(container)

            finished_at = _utc_now_iso()
            duration_seconds = round(time.monotonic() - started_monotonic, 3)

            return ContainerResult(
                container_id=container_id,
                image=spec.image,
                command=spec.command,
                status=ContainerStatus.FAILED,
                exit_code=None,
                stdout=stdout,
                stderr=stderr,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                error_message=str(exc),
            )

        finally:
            if container is not None and spec.remove_after_run:
                self._safe_remove(container)

    def stop(self, container_id: str, timeout: int = 10) -> None:
        client = self._get_docker()
        container = client.containers.get(container_id)
        container.stop(timeout=timeout)

    def logs(self, container_id: str) -> str:
        client = self._get_docker()
        container = client.containers.get(container_id)
        raw = container.logs(stdout=True, stderr=True)
        return _decode(raw)

    def inspect(self, container_id: str) -> dict:
        client = self._get_docker()
        container = client.containers.get(container_id)
        return dict(container.attrs)

    def _pull_image_if_missing(self, image: str) -> None:
        client = self._get_docker()

        try:
            client.images.get(image)
            return
        except Exception:
            pass

        try:
            client.images.pull(image)
        except Exception as exc:
            raise ContainerRunError(f"Failed to pull image: {image}") from exc

    def _wait_for_container(self, container, timeout_seconds: int) -> int:
        deadline = time.monotonic() + timeout_seconds

        while True:
            container.reload()

            if container.status == "exited":
                result = container.wait(timeout=5)
                return int(result.get("StatusCode", 1))

            if container.status == "dead":
                return 1

            if time.monotonic() > deadline:
                raise ContainerTimeoutError(
                    f"Container exceeded timeout: {timeout_seconds}s"
                )

            time.sleep(0.5)

    def _read_logs(self, container) -> tuple[str, str]:
        stdout_raw = container.logs(stdout=True, stderr=False)
        stderr_raw = container.logs(stdout=False, stderr=True)

        return _decode(stdout_raw), _decode(stderr_raw)

    def _safe_read_logs(self, container) -> tuple[str, str]:
        if container is None:
            return "", ""

        try:
            return self._read_logs(container)
        except Exception:
            return "", ""

    def _safe_kill(self, container) -> None:
        try:
            container.kill()
        except Exception:
            pass

    def _safe_remove(self, container) -> None:
        try:
            container.remove(force=True)
        except Exception:
            pass

def _build_docker_volumes(volumes: Sequence[VolumeMount]) -> dict[str, dict[str, str]]:
    docker_volumes: dict[str, dict[str, str]] = {}

    for volume in volumes:
        host_path = Path(volume.host_path).resolve()
        # Docker resolves host paths. Under Compose the daemon has a different
        # filesystem namespace from Django, so validation belongs upstream.
        docker_volumes[str(host_path)] = volume.to_docker_volume()

    return docker_volumes

def _decode(raw: bytes | str | None) -> str:
    if raw is None:
        return ""

    if isinstance(raw, str):
        return raw

    return raw.decode("utf-8", errors="replace")

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
