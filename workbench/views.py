from importlib import import_module
import io

from django.http import JsonResponse
from django.shortcuts import render

from biocraft_core.runtime.executor import ContainerSpec, DockerContainerExecutor
from biocraft_core.runtime.scheduler import DAGEngine, TaskNode
from biocraft_core.plugin import load_plugin

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

def scheduler_ping(request):
	nodes = [
		TaskNode(
			name="A",
			image="python:3.12-slim",
			command=["python", "-c", "print('A: start')"],
		),
		TaskNode(
			name="B",
			image="python:3.12-slim",
			command=["python", "-c", "print('B: left after A')"],
			depends_on=("A",),
		),
		TaskNode(
			name="C",
			image="python:3.12-slim",
			command=["python", "-c", "print('C: right after A')"],
			depends_on=("A",),
		),
	]

	engine = DAGEngine(executor=DockerContainerExecutor(), max_workers=4)
	run_result = engine.run(nodes)
	return JsonResponse(run_result.to_dict())

def plugin_ping(request):
	"""Validate plugin YAML loading without running containers."""
	sample_yaml = """\
name: ping-plugin
version: "0.1"
description: Plugin format sanity check
steps:
  - name: step-a
    image: python:3.12-slim
    command: ["python", "-c", "print('step-a')"]
  - name: step-b
    image: python:3.12-slim
    command: ["python", "-c", "print('step-b')"]
    depends_on: ["step-a"]
    retry:
      max_attempts: 2
      delay_seconds: 1.0
"""
	try:
		spec, nodes = load_plugin(io.StringIO(sample_yaml))
		return JsonResponse({
			"ok": True,
			"plugin": spec.name,
			"version": spec.version,
			"nodes": [
				{
					"name": n.name,
					"image": n.image,
					"depends_on": list(n.depends_on),
					"retry": {
						"max_attempts": n.retry.max_attempts,
						"delay_seconds": n.retry.delay_seconds,
					},
				}
				for n in nodes
			],
		})
	except Exception as exc:
		return JsonResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status=400)
