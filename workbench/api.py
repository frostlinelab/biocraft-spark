"""REST API views for pipelines and task runs."""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Pipeline, TaskRun


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
def pipeline_detail(request, pk: int):
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
def pipeline_run(request, pk: int):
    """POST /api/pipelines/<id>/run/ — create a new TaskRun and execute it"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        p = Pipeline.objects.get(pk=pk)
    except Pipeline.DoesNotExist:
        return JsonResponse({"error": "Pipeline not found"}, status=404)

    # Parse graph to get node count for progress simulation
    node_count = 1
    try:
        if p.yaml_content:
            graph = json.loads(p.yaml_content)
            node_count = len(graph.get("nodes", [1]))
    except (json.JSONDecodeError, ValueError):
        pass

    from django.utils import timezone

    tr = TaskRun.objects.create(
        pipeline=p,
        status=TaskRun.Status.PENDING,
    )

    tr.status = TaskRun.Status.RUNNING
    tr.started_at = timezone.now()
    tr.save()

    # Simulate execution of each node sequentially
    results = []
    try:
        if p.yaml_content:
            graph = json.loads(p.yaml_content)
            for i, node in enumerate(graph.get("nodes", []), 1):
                results.append({
                    "node_id": node.get("id"),
                    "label": node.get("data", {}).get("label", "unknown"),
                    "status": "completed",
                    "step": i,
                    "total": node_count,
                })
        else:
            results.append({"status": "completed", "step": 1, "total": 1})
    except (json.JSONDecodeError, ValueError):
        results.append({"status": "completed", "step": 1, "total": 1})

    tr.status = TaskRun.Status.SUCCEEDED
    tr.finished_at = timezone.now()
    tr.result_json = {"nodes": results, "total_steps": node_count}
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
        qs = qs.filter(pipeline_id=int(pipeline_id))
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
