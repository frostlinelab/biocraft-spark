"""REST API views for pipelines and task runs."""

import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import InstalledPlugin, Pipeline, TaskRun

from biocraft_core.plugin import (
    builtin_blocks,
    discover_plugins,
    load_plugin_file,
    BlockParam,
    BlockPort,
    BlockSpec,
    PluginBlocksSpec,
)

logger = logging.getLogger(__name__)

# ── File upload storage directory ───────────────────────────────────────────────

UPLOAD_DIR = Path(getattr(settings, "BIOCRAFT_UPLOAD_DIR", settings.BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _docker_host_path(path: Path) -> Path:
    """Translate a project path to the host path seen by the Docker daemon."""
    host_project_dir = str(getattr(settings, "BIOCRAFT_DOCKER_HOST_PROJECT_DIR", ""))
    if not host_project_dir:
        return path

    try:
        relative_path = path.resolve().relative_to(settings.BASE_DIR.resolve())
    except ValueError:
        return path
    return Path(host_project_dir).resolve() / relative_path


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
            run_output_dir = Path(djsettings.BASE_DIR) / "run_outputs" / f"task-run-{run_id}"
            task_nodes = resolve_graph_to_task_nodes(
                graph,
                block_specs,
                pool,
                input_dir=UPLOAD_DIR,
                output_dir=run_output_dir,
                mount_input_dir=_docker_host_path(UPLOAD_DIR),
                mount_output_dir=_docker_host_path(run_output_dir),
            )

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


def _taskrun_output_dir(run_id: int) -> Path:
    """Directory holding a task run's output files (mirrors _run_pipeline_bg)."""
    return Path(settings.BASE_DIR) / "run_outputs" / f"task-run-{run_id}"


@require_http_methods(["GET"])
def taskrun_outputs(request, pk: int):
    """GET /api/task-runs/<id>/outputs/ — list output files produced by a run.

    Walks the run's output directory recursively and returns each regular file
    with its relative path, byte size, and a ``download_url`` that points at
    the single-file download endpoint.
    """
    try:
        TaskRun.objects.get(pk=pk)
    except TaskRun.DoesNotExist:
        return JsonResponse({"error": "TaskRun not found"}, status=404)

    root = _taskrun_output_dir(pk)
    if not root.exists():
        return JsonResponse({"run_id": pk, "files": []})

    files: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        files.append({
            "name": path.name,
            "path": rel,
            "size": path.stat().st_size,
            "download_url": f"/api/task-runs/{pk}/outputs/download/?file={quote(rel)}",
        })
    return JsonResponse({"run_id": pk, "files": files})


@require_http_methods(["GET"])
def taskrun_output_download(request, pk: int):
    """GET /api/task-runs/<id>/outputs/download/?file=<relpath> — download one file.

    Serves the file as an attachment. The ``file`` query parameter must be a
    path relative to the run's output directory; any attempt to escape that
    directory via ``..`` or absolute paths is rejected with HTTP 400.
    """
    try:
        TaskRun.objects.get(pk=pk)
    except TaskRun.DoesNotExist:
        return JsonResponse({"error": "TaskRun not found"}, status=404)

    rel = request.GET.get("file", "").strip()
    if not rel:
        return JsonResponse({"error": "file parameter is required"}, status=400)

    root = _taskrun_output_dir(pk).resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return JsonResponse({"error": "Invalid file path"}, status=400)

    if not target.is_file():
        return JsonResponse({"error": "File not found"}, status=404)

    return FileResponse(
        open(target, "rb"),
        as_attachment=True,
        filename=target.name,
        content_type="application/octet-stream",
    )


def _parse_task_name(name: str) -> dict:
    """Split a task name into its components for UI display.

    Task names follow one of two conventions (see resolver.py):
      - Fan-out:  ``{plugin}__{block}__{ordinal}__{input_file}``
      - Single:   ``{plugin}__{block}__{ordinal}``

    Any unrecognised shape falls back to returning the raw name as ``plugin``
    so the workspace view never breaks on a malformed directory entry.
    """
    parts = name.split("__")
    if len(parts) == 4:
        plugin, block, ordinal_str, input_file = parts
        try:
            ordinal = int(ordinal_str)
        except ValueError:
            ordinal = 0
        return {
            "plugin": plugin,
            "block": block,
            "ordinal": ordinal,
            "input_file": input_file,
        }
    if len(parts) == 3:
        plugin, block, ordinal_str = parts
        try:
            ordinal = int(ordinal_str)
        except ValueError:
            ordinal = 0
        return {
            "plugin": plugin,
            "block": block,
            "ordinal": ordinal,
            "input_file": None,
        }
    return {"plugin": name, "block": "", "ordinal": 0, "input_file": None}


@require_http_methods(["GET"])
def taskrun_workspace(request, pk: int):
    """GET /api/task-runs/<id>/workspace/ — per-task breakdown of a run.

    For each task that produced output on disk, returns its parsed identity
    (plugin/block/ordinal/input_file), status (looked up from
    ``result_json.dag_result.tasks``), and the list of output files with
    download URLs pointing at the existing single-file download endpoint.
    """
    try:
        tr = TaskRun.objects.get(pk=pk)
    except TaskRun.DoesNotExist:
        return JsonResponse({"error": "TaskRun not found"}, status=404)

    # Status per task name — may be missing in simulation mode or older runs.
    result_json = tr.result_json or {}
    dag_tasks = (
        (result_json.get("dag_result") or {}).get("tasks") or {}
        if isinstance(result_json, dict)
        else {}
    )

    root = _taskrun_output_dir(pk)
    if not root.exists():
        return JsonResponse({"run_id": pk, "tasks": []})

    tasks: list[dict] = []
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        task_name = task_dir.name
        parsed = _parse_task_name(task_name)

        outputs: list[dict] = []
        for path in sorted(task_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            outputs.append({
                "name": path.name,
                "path": rel,
                "size": path.stat().st_size,
                "download_url": f"/api/task-runs/{pk}/outputs/download/?file={quote(rel)}",
            })

        tasks.append({
            "task_name": task_name,
            "plugin": parsed["plugin"],
            "block": parsed["block"],
            "ordinal": parsed["ordinal"],
            "input_file": parsed["input_file"],
            "status": dag_tasks.get(task_name, {}).get("status", "unknown"),
            "outputs": outputs,
        })

    return JsonResponse({"run_id": pk, "tasks": tasks})


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


# ── Marketplace API ───────────────────────────────────────────────────────────

# Module-level cache for the remote registry index (TTL from settings). Avoids
# hitting Cloudflare on every catalog request; tests reset this directly.
_INDEX_CACHE: dict = {"fetched_at": 0.0, "data": None}

# Cloudflare bot protection (Error 1010) blocks the default Python-urllib
# User-Agent, so every registry request sends an identifying UA.
_MARKETPLACE_UA = "biocraft-spark/1.0 (+https://github.com/frostlinelab/biocraft-spark)"


def _fetch_marketplace_index() -> dict | None:
    """Fetch the remote marketplace index.json with a simple TTL cache.

    Returns the parsed index dict, or ``None`` if the registry is unreachable
    or returns invalid JSON.
    """
    ttl = getattr(settings, "BIOCRAFT_MARKETPLACE_CACHE_TTL", 300)
    now = time.time()
    if _INDEX_CACHE["data"] is not None and now - _INDEX_CACHE["fetched_at"] < ttl:
        return _INDEX_CACHE["data"]

    url = getattr(settings, "BIOCRAFT_MARKETPLACE_INDEX_URL", "")
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": _MARKETPLACE_UA})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — trusted configured URL
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.exception("Failed to fetch marketplace index from %s", url)
        return None

    _INDEX_CACHE["fetched_at"] = now
    _INDEX_CACHE["data"] = data
    return data


@require_http_methods(["GET"])
def marketplace_catalog(request):
    """GET /api/marketplace/catalog/ — remote plugin catalog, enriched with local install state.

    Each plugin from the registry is annotated with:
      - ``installed_version``: version on disk (marketplace-installed), else null
      - ``managed``: True only if installed via marketplace (has an InstalledPlugin row);
        plugins not yet installed are not managed.
    """
    index = _fetch_marketplace_index()
    if index is None:
        return JsonResponse({"error": "Marketplace registry unreachable"}, status=502)

    plugins_dir = getattr(settings, "BIOCRAFT_PLUGINS_DIR", None)
    disk: dict[str, str] = {}  # name -> version for plugins present on disk
    if plugins_dir:
        for spec in discover_plugins(plugins_dir):
            disk[spec.name] = spec.version
    managed = {ip.name: ip for ip in InstalledPlugin.objects.all()}

    enriched: list[dict] = []
    for p in index.get("plugins", []):
        name = p.get("name", "")
        if name in disk:
            installed_version: str | None = disk[name]
        elif name in managed:
            installed_version = managed[name].version
        else:
            installed_version = None
        enriched.append({
            **p,
            "installed_version": installed_version,
            "managed": name in managed,
        })

    return JsonResponse({
        "schema_version": index.get("schema_version", 1),
        "generated_at": index.get("generated_at", ""),
        "plugins": enriched,
    })


@csrf_exempt
@require_http_methods(["POST"])
def marketplace_install(request):
    """POST /api/marketplace/install/ — download + validate + persist a plugin YAML.

    Body: ``{"yaml_url": "...", "sha256": "...", "author": "...", "curated": bool}``
    Downloads the YAML, optionally verifies its checksum, validates it via the
    existing plugin loader, writes it to the plugins dir, and records an
    InstalledPlugin row (which makes it managed / uninstallable).
    """
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    yaml_url = body.get("yaml_url", "")
    expected_sha = body.get("sha256", "")
    if not yaml_url or not yaml_url.startswith(("http://", "https://")):
        return JsonResponse({"error": "Invalid yaml_url"}, status=400)

    # Download the plugin manifest
    try:
        req = urllib.request.Request(yaml_url, headers={"Accept": "text/yaml", "User-Agent": _MARKETPLACE_UA})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            content = resp.read()
    except Exception:
        logger.exception("Failed to download plugin YAML from %s", yaml_url)
        return JsonResponse({"error": "Failed to download plugin YAML"}, status=502)

    # Optional checksum verification against the registry-published sha256
    actual_sha = hashlib.sha256(content).hexdigest()
    if expected_sha and actual_sha != expected_sha:
        return JsonResponse({"error": "Checksum mismatch"}, status=400)

    # Validate by loading through the existing plugin loader (write to temp first)
    plugins_dir = Path(getattr(settings, "BIOCRAFT_PLUGINS_DIR", settings.BASE_DIR / "plugins"))
    plugins_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", suffix=".plugin.yaml", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        spec = load_plugin_file(tmp_path)
    except Exception:
        logger.exception("Downloaded plugin YAML failed to load")
        return JsonResponse({"error": "Downloaded YAML is not a valid plugin"}, status=400)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if spec is None or not spec.name:
        return JsonResponse({"error": "Downloaded YAML is not a valid plugin"}, status=400)

    # Filename derived from the validated plugin name (not user input), with a
    # safety check to keep it within the plugins dir.
    name = spec.name
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        return JsonResponse({"error": "Invalid plugin name"}, status=400)
    dest = plugins_dir / f"{name}.plugin.yaml"
    dest.write_bytes(content)  # discover_plugins picks this up on next /api/blocks/

    InstalledPlugin.objects.update_or_create(
        name=name,
        defaults={
            "version": spec.version,
            "description": spec.description,
            "icon": spec.icon or "process",
            "author": body.get("author", "official"),
            "curated": bool(body.get("curated", False)),
            "source_url": yaml_url,
            "sha256": actual_sha,
        },
    )
    return JsonResponse({
        "name": name,
        "version": spec.version,
        "installed_version": spec.version,
        "managed": True,
    }, status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def marketplace_uninstall(request, name: str):
    """DELETE /api/marketplace/plugins/<name>/ — remove a marketplace-installed plugin.

    Only plugins with an InstalledPlugin row (i.e. installed via the marketplace)
    can be uninstalled. Plugins without a row (not installed) return 404.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        return JsonResponse({"error": "Invalid plugin name"}, status=400)
    deleted, _ = InstalledPlugin.objects.filter(name=name).delete()
    if not deleted:
        return JsonResponse({"error": "Not a marketplace-installed plugin"}, status=404)
    plugins_dir = Path(getattr(settings, "BIOCRAFT_PLUGINS_DIR", settings.BASE_DIR / "plugins"))
    (plugins_dir / f"{name}.plugin.yaml").unlink(missing_ok=True)
    return JsonResponse({"name": name, "uninstalled": True})
