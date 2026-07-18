"""REST API views for pipelines and task runs."""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Pipeline, TaskRun

from biocraft_core.plugin import builtin_blocks, discover_plugins, BlockParam, BlockPort, BlockSpec, PluginBlocksSpec


# ── Runtime config API ──────────────────────────────────────────────────────

def runtime_config(request):
    """GET /api/runtime-config/ — return global runtime resource settings"""
    from django.conf import settings
    from biocraft_core.runtime.resources import RuntimeConfig

    cfg_raw = getattr(settings, "BIOCRAFT_RUNTIME", {})
    cfg = RuntimeConfig(**cfg_raw) if cfg_raw else RuntimeConfig()
    return JsonResponse({
        "cpuCores": cfg.cpu_cores,
        "cpuThreads": cfg.cpu_threads,
        "memoryGb": cfg.memory_gb,
        "maxParallelContainers": cfg.max_parallel_containers,
    })


# ── Block / Plugin API ────────────────────────────────────────────────────────

def _serialize_param(p: BlockParam) -> dict:
    return {
        "name": p.name,
        "label": p.label,
        "paramType": p.param_type,
        "default": p.default,
        "min": p.min,
        "max": p.max,
        "options": p.options,
    }


def _serialize_port(p: BlockPort) -> dict:
    return {
        "name": p.name,
        "label": p.label,
        "portType": p.port_type,
        "pattern": p.pattern,
        "multiple": p.multiple,
    }


def _serialize_block(b: BlockSpec) -> dict:
    return {
        "name": b.name,
        "label": b.label,
        "description": b.description,
        "icon": b.icon,
        "pluginName": b.plugin_name,
        "pluginVersion": b.plugin_version,
        "hasRuntime": b.runtime is not None,
        "inputs": [_serialize_port(p) for p in b.inputs],
        "outputs": [_serialize_port(p) for p in b.outputs],
        "params": [_serialize_param(p) for p in b.params],
    }


def block_list(request):
    """GET /api/blocks/ — list all available blocks (built-in + discovered plugins)"""
    from django.conf import settings

    plugins_dir = getattr(settings, "BIOCRAFT_PLUGINS_DIR", None)
    plugin_specs: list[PluginBlocksSpec] = []
    if plugins_dir:
        plugin_specs = discover_plugins(plugins_dir)

    categories: list[dict] = []

    # Built-in category always comes first
    builtins = builtin_blocks()
    categories.append({
        "name": "builtin",
        "label": "内置",
        "description": "Built-in workflow control blocks",
        "icon": "builtin",
        "blocks": [_serialize_block(b) for b in builtins],
    })

    # Plugin categories (sorted by name)
    for spec in sorted(plugin_specs, key=lambda s: s.name):
        categories.append({
            "name": spec.name,
            "label": spec.name.replace("-", " ").title(),
            "description": spec.description,
            "icon": spec.icon,
            "blocks": [_serialize_block(b) for b in spec.blocks],
        })

    return JsonResponse({"categories": categories})


# ── Pipeline API ──────────────────────────────────────────────────────────────

def pipeline_list(request):
    """GET /api/pipelines/ — list all pipelines"""
    pipelines = Pipeline.objects.all()
    return JsonResponse({
        "pipelines": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in pipelines
        ]
    })


@csrf_exempt
def pipeline_create(request):
    """POST /api/pipelines/ — create a new pipeline"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = body.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)
    pipeline = Pipeline.objects.create(
        name=name,
        description=body.get("description", ""),
        yaml_content=body.get("yaml_content", ""),
    )
    return JsonResponse({
        "id": pipeline.id,
        "name": pipeline.name,
        "description": pipeline.description,
        "yaml_content": pipeline.yaml_content,
        "created_at": pipeline.created_at.isoformat(),
        "updated_at": pipeline.updated_at.isoformat(),
    }, status=201)


@csrf_exempt
def pipeline_detail(request, pk: str):
    """GET/PUT/DELETE /api/pipelines/<id>/ — get, update, or delete a single pipeline"""
    try:
        p = Pipeline.objects.get(pk=pk)
    except Pipeline.DoesNotExist:
        return JsonResponse({"error": "Pipeline not found"}, status=404)

    if request.method == "DELETE":
        p.delete()
        return JsonResponse({"deleted": True}, status=200)

    if request.method == "PUT":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        p.name = body.get("name", p.name)
        p.description = body.get("description", p.description)
        p.yaml_content = body.get("yaml_content", p.yaml_content)
        p.save()
        return JsonResponse({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "yaml_content": p.yaml_content,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        })

    return JsonResponse({
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "yaml_content": p.yaml_content,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    })


@csrf_exempt
def pipeline_run(request, pk: str):
    """POST /api/pipelines/<id>/run/ — create a new TaskRun and execute it"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        p = Pipeline.objects.get(pk=pk)
    except Pipeline.DoesNotExist:
        return JsonResponse({"error": "Pipeline not found"}, status=404)

    from django.conf import settings
    from django.utils import timezone

    tr = TaskRun.objects.create(
        pipeline=p,
        status=TaskRun.Status.PENDING,
    )

    tr.status = TaskRun.Status.RUNNING
    tr.started_at = timezone.now()
    tr.save()

    # Parse the saved React Flow graph
    try:
        graph = json.loads(p.yaml_content) if p.yaml_content else {}
    except (json.JSONDecodeError, ValueError):
        graph = {}

    nodes_raw = graph.get("nodes", [])
    node_count = len(nodes_raw) if nodes_raw else 1

    # Check if any node has container runtime
    has_runtime_blocks = any(
        n.get("data", {}).get("hasRuntime", False)
        for n in nodes_raw
        if isinstance(n, dict)
    )

    if has_runtime_blocks:
        # ── Real execution via DAGEngine ──────────────────────────
        from biocraft_core.plugin.resolver import get_all_block_specs, resolve_graph_to_task_nodes
        from biocraft_core.runtime.executor import DockerContainerExecutor
        from biocraft_core.runtime.scheduler.engine import DAGEngine

        try:
            plugins_dir = getattr(settings, "BIOCRAFT_PLUGINS_DIR", None)
            block_specs = get_all_block_specs(plugins_dir)
            task_nodes = resolve_graph_to_task_nodes(graph, block_specs)

            if task_nodes:
                executor = DockerContainerExecutor()
                engine = DAGEngine(executor)
                dag_result = engine.run(task_nodes)

                results = [
                    {
                        "node_id": task_node.name,
                        "label": task_node.name,
                        "status": dag_result.results[task_node.name].status.value,
                        "step": i + 1,
                        "total": len(task_nodes),
                    }
                    for i, task_node in enumerate(task_nodes)
                    if task_node.name in dag_result.results
                ]

                tr.status = (
                    TaskRun.Status.SUCCEEDED
                    if dag_result.succeeded
                    else TaskRun.Status.FAILED
                )
                tr.result_json = {
                    "nodes": results,
                    "total_steps": len(task_nodes),
                    "engine": "dag",
                    "dag_result": dag_result.to_dict(),
                }
            else:
                # No runtime blocks resolved (e.g. only built-ins)
                results = [
                    {
                        "node_id": n.get("id"),
                        "label": n.get("data", {}).get("label", "unknown"),
                        "status": "completed",
                        "step": i + 1,
                        "total": node_count,
                    }
                    for i, n in enumerate(nodes_raw)
                    if isinstance(n, dict)
                ]
                tr.status = TaskRun.Status.SUCCEEDED
                tr.result_json = {"nodes": results, "total_steps": node_count}
        except Exception as exc:
            tr.status = TaskRun.Status.FAILED
            tr.error_message = f"{type(exc).__name__}: {exc}"
            tr.result_json = {"error": str(exc)}
    else:
        # ── Simulation mode (built-in blocks only) ─────────────────
        results = []
        for i, node in enumerate(nodes_raw, 1):
            if isinstance(node, dict):
                results.append({
                    "node_id": node.get("id"),
                    "label": node.get("data", {}).get("label", "unknown"),
                    "status": "completed",
                    "step": i,
                    "total": node_count,
                })
        if not results:
            results.append({"status": "completed", "step": 1, "total": 1})
        tr.status = TaskRun.Status.SUCCEEDED
        tr.result_json = {"nodes": results, "total_steps": node_count}

    tr.finished_at = timezone.now()
    tr.save()

    return JsonResponse({
        "id": tr.id,
        "pipeline_id": tr.pipeline_id,
        "pipeline_name": tr.pipeline.name,
        "status": tr.status,
        "started_at": tr.started_at.isoformat() if tr.started_at else None,
        "finished_at": tr.finished_at.isoformat() if tr.finished_at else None,
        "result_json": tr.result_json,
        "error_message": tr.error_message,
        "created_at": tr.created_at.isoformat(),
    }, status=201)


# ── TaskRun API ───────────────────────────────────────────────────────────────

def taskrun_list(request):
    """GET /api/task-runs/ — list task runs, optionally filtered by pipeline_id"""
    pipeline_id = request.GET.get("pipeline_id")
    qs = TaskRun.objects.select_related("pipeline").all()
    if pipeline_id:
        qs = qs.filter(pipeline_id=pipeline_id)
    return JsonResponse({
        "task_runs": [
            {
                "id": tr.id,
                "pipeline_id": tr.pipeline_id,
                "pipeline_name": tr.pipeline.name,
                "status": tr.status,
                "started_at": tr.started_at.isoformat() if tr.started_at else None,
                "finished_at": tr.finished_at.isoformat() if tr.finished_at else None,
                "error_message": tr.error_message,
                "created_at": tr.created_at.isoformat(),
            }
            for tr in qs
        ]
    })


def taskrun_detail(request, pk: int):
    """GET /api/task-runs/<id>/ — get a single task run with full result"""
    try:
        tr = TaskRun.objects.select_related("pipeline").get(pk=pk)
    except TaskRun.DoesNotExist:
        return JsonResponse({"error": "TaskRun not found"}, status=404)
    return JsonResponse({
        "id": tr.id,
        "pipeline_id": tr.pipeline_id,
        "pipeline_name": tr.pipeline.name,
        "status": tr.status,
        "started_at": tr.started_at.isoformat() if tr.started_at else None,
        "finished_at": tr.finished_at.isoformat() if tr.finished_at else None,
        "result_json": tr.result_json,
        "error_message": tr.error_message,
        "created_at": tr.created_at.isoformat(),
    })


# ── Dashboard stats ───────────────────────────────────────────────────────────

def dashboard_stats(request):
    """GET /api/dashboard-stats/ — aggregate numbers for the dashboard"""
    return JsonResponse({
        "pipelines_count": Pipeline.objects.count(),
        "task_runs_count": TaskRun.objects.count(),
        "recent_runs": [
            {
                "id": tr.id,
                "pipeline_id": tr.pipeline_id,
                "pipeline_name": tr.pipeline.name,
                "status": tr.status,
                "created_at": tr.created_at.isoformat(),
            }
            for tr in TaskRun.objects.select_related("pipeline").order_by("-created_at")[:10]
        ],
        "status_breakdown": {
            "pending": TaskRun.objects.filter(status=TaskRun.Status.PENDING).count(),
            "running": TaskRun.objects.filter(status=TaskRun.Status.RUNNING).count(),
            "succeeded": TaskRun.objects.filter(status=TaskRun.Status.SUCCEEDED).count(),
            "failed": TaskRun.objects.filter(status=TaskRun.Status.FAILED).count(),
        },
    })
