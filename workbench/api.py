"""REST API views for pipelines and task runs."""

import hashlib
import json
import os
import threading
import uuid
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Pipeline, TaskRun

from biocraft_core.plugin import builtin_blocks, discover_plugins, BlockParam, BlockPort, BlockSpec, PluginBlocksSpec

# ── File upload storage directory ───────────────────────────────────────────────

UPLOAD_DIR = Path(getattr(settings, "BIOCRAFT_UPLOAD_DIR", settings.BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
    resources = None
    if b.runtime is not None and b.runtime.resources is not None:
        resources = {
            "minThreads": b.runtime.resources.min_threads,
            "minMemoryGb": b.runtime.resources.min_memory_gb,
        }
    return {
        "name": b.name,
        "label": b.label,
        "description": b.description,
        "icon": b.icon,
        "pluginName": b.plugin_name,
        "pluginVersion": b.plugin_version,
        "hasRuntime": b.runtime is not None,
        "resources": resources,
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
        "label": "Built-in",
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


# ── File upload API ──────────────────────────────────────────────────────────────

@csrf_exempt
def file_upload(request):
    """POST /api/files/upload/ — upload one or more files for workflow input

    Accepts multipart/form-data with one or more ``file`` fields.
    Returns a flat list of file metadata objects safe to store in node data.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    uploaded = request.FILES.getlist("files")
    if not uploaded:
        return JsonResponse({"error": "No files provided"}, status=400)

    results: list[dict] = []
    for f in uploaded:
        # Generate a collision-resistant name: <uuid8>_<original_name>
        name_uuid = uuid.uuid4().hex[:8]
        safe_name = f"{name_uuid}_{f.name}"
        dest = UPLOAD_DIR / safe_name

        # Stream to disk in chunks
        with open(dest, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)

        # SHA-256 checksum for integrity
        file_hash = hashlib.sha256()
        with open(dest, "rb") as fh:
            while True:
                block = fh.read(8192)
                if not block:
                    break
                file_hash.update(block)

        results.append({
            "id": safe_name,
            "name": f.name,
            "size": dest.stat().st_size,
            "type": f.content_type or "application/octet-stream",
            "path": str(dest),
            "sha256": file_hash.hexdigest(),
        })

    return JsonResponse({"files": results}, status=201)


@csrf_exempt
def file_delete(request, file_id: str):
    """DELETE /api/files/<file_id>/ — remove an uploaded file from disk"""
    if request.method != "DELETE":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    dest = UPLOAD_DIR / file_id
    # Prevent path traversal
    if dest.resolve().parent != UPLOAD_DIR.resolve():
        return JsonResponse({"error": "Invalid file id"}, status=400)

    try:
        dest.unlink()
    except FileNotFoundError:
        pass
    return JsonResponse({"deleted": True}, status=200)


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


def _run_pipeline_bg(run_id: int, pipeline_yaml: str, plugins_dir) -> None:
    """Execute a pipeline in a background thread and update the TaskRun in-place.

    Each background thread gets its own Django DB connection via close_old_connections().
    SQLite serialises writes so concurrent runs are safe at the DB level.
    """
    from django.db import close_old_connections
    from django.utils import timezone

    close_old_connections()  # ensure a fresh connection for this thread

    try:
        tr = TaskRun.objects.get(pk=run_id)
    except TaskRun.DoesNotExist:
        return

    try:
        graph: dict = json.loads(pipeline_yaml) if pipeline_yaml else {}
    except (json.JSONDecodeError, ValueError):
        graph = {}

    nodes_raw = graph.get("nodes", [])
    node_count = max(len(nodes_raw), 1)
    has_runtime = any(
        n.get("data", {}).get("hasRuntime", False)
        for n in nodes_raw
        if isinstance(n, dict)
    )

    try:
        if has_runtime:
            from django.conf import settings as djsettings
            from biocraft_core.plugin.resolver import get_all_block_specs, resolve_graph_to_task_nodes
            from biocraft_core.runtime.executor import DockerContainerExecutor
            from biocraft_core.runtime.resources import ResourcePool, RuntimeConfig
            from biocraft_core.runtime.scheduler.engine import DAGEngine

            cfg_raw = getattr(djsettings, "BIOCRAFT_RUNTIME", {})
            cfg = RuntimeConfig(**cfg_raw) if cfg_raw else RuntimeConfig()
            pool = ResourcePool(cfg)

            block_specs = get_all_block_specs(plugins_dir)
            task_nodes = resolve_graph_to_task_nodes(graph, block_specs, pool)

            if task_nodes:
                executor = DockerContainerExecutor()
                engine = DAGEngine(executor, max_workers=cfg.max_parallel_containers)
                dag_result = engine.run(task_nodes)

                results = [
                    {
                        "node_id": tn.name,
                        "label": tn.name,
                        "status": dag_result.results[tn.name].status.value,
                        "step": i + 1,
                        "total": len(task_nodes),
                    }
                    for i, tn in enumerate(task_nodes)
                    if tn.name in dag_result.results
                ]
                tr.status = (
                    TaskRun.Status.SUCCEEDED if dag_result.succeeded
                    else TaskRun.Status.FAILED
                )
                tr.result_json = {
                    "nodes": results,
                    "total_steps": len(task_nodes),
                    "engine": "dag",
                    "dag_result": dag_result.to_dict(),
                }
            else:
                # Graph only has built-in blocks — instant success
                tr.status = TaskRun.Status.SUCCEEDED
                tr.result_json = {
                    "nodes": [
                        {
                            "node_id": n.get("id"),
                            "label": n.get("data", {}).get("label", "unknown"),
                            "status": "completed",
                            "step": i + 1,
                            "total": node_count,
                        }
                        for i, n in enumerate(nodes_raw)
                        if isinstance(n, dict)
                    ],
                    "total_steps": node_count,
                }
        else:
            # Simulation mode
            tr.status = TaskRun.Status.SUCCEEDED
            tr.result_json = {
                "nodes": [
                    {
                        "node_id": n.get("id"),
                        "label": n.get("data", {}).get("label", "unknown"),
                        "status": "completed",
                        "step": i + 1,
                        "total": node_count,
                    }
                    for i, n in enumerate(nodes_raw, 0)
                    if isinstance(n, dict)
                ],
                "total_steps": node_count,
            }
    except Exception as exc:
        tr.status = TaskRun.Status.FAILED
        tr.error_message = f"{type(exc).__name__}: {exc}"
        tr.result_json = {"error": str(exc)}

    tr.finished_at = timezone.now()
    tr.save()


@csrf_exempt
def pipeline_run(request, pk: str):
    """POST /api/pipelines/<id>/run/ — create a TaskRun and start execution asynchronously.

    Returns HTTP 202 immediately with the new TaskRun (status=running).
    The caller should poll GET /api/task-runs/<id>/ until status is no longer
    'running' or 'pending'.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        p = Pipeline.objects.get(pk=pk)
    except Pipeline.DoesNotExist:
        return JsonResponse({"error": "Pipeline not found"}, status=404)

    from django.conf import settings
    from django.utils import timezone

    tr = TaskRun.objects.create(pipeline=p, status=TaskRun.Status.RUNNING)
    tr.started_at = timezone.now()
    tr.save()

    plugins_dir = getattr(settings, "BIOCRAFT_PLUGINS_DIR", None)
    t = threading.Thread(
        target=_run_pipeline_bg,
        args=(tr.id, p.yaml_content, plugins_dir),
        daemon=True,
    )
    t.start()

    return JsonResponse({
        "id": tr.id,
        "pipeline_id": tr.pipeline_id,
        "pipeline_name": tr.pipeline.name,
        "status": tr.status,
        "started_at": tr.started_at.isoformat() if tr.started_at else None,
        "finished_at": None,
        "result_json": None,
        "error_message": None,
        "created_at": tr.created_at.isoformat(),
    }, status=202)


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
