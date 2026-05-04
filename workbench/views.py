from importlib import import_module

from django.http import JsonResponse
from django.shortcuts import render

from biocraft_core.runtime.executor import ContainerSpec, DockerContainerExecutor

def home(request):
    return render(request=request, template_name="workbench/home.html")

def docker_ping(request):
    try:
        docker = import_module("docker")
    except ModuleNotFoundError as exc:
        return JsonResponse(
            {"docker": False, "error": f"Docker SDK import failed: {exc}"},
            status=503,
        )

    try:
        client = docker.from_env()
        return JsonResponse(
            {
                "docker": client.ping(),
                "containers": [container.name for container in client.containers.list()],
            }
        )
    except Exception as exc:
        return JsonResponse(
            {"docker": False, "error": f"Docker runtime unavailable: {exc}"},
            status=503,
        )

def executor_ping(request):
    executor = DockerContainerExecutor(default_timeout_seconds=30)

    result = executor.run(
        ContainerSpec(
            image="python:3.12-slim",
            command=[
                "python",
                "-c",
                "print('Biocraft executor online')",
            ],
            timeout_seconds=20,
            remove_after_run=True,
        )
    )

    return JsonResponse(
        {
            "ok": result.ok,
            "status": result.status.value,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": result.duration_seconds,
            "error_message": result.error_message,
        }
    )