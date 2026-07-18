from django.contrib import admin

from .models import Pipeline, TaskRun


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name", "description")


@admin.register(TaskRun)
class TaskRunAdmin(admin.ModelAdmin):
    list_display = ("id", "pipeline", "status", "started_at", "finished_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("pipeline__name", "error_message")
