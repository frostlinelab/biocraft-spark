import secrets
from django.db import models


def generate_workflow_id() -> str:
    """Return an 8-character uppercase hex workflow ID like '3A073580'."""
    return secrets.token_hex(4).upper()


class Pipeline(models.Model):
    id = models.CharField(
        max_length=8,
        primary_key=True,
        default=generate_workflow_id,
        editable=False,
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    yaml_content = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.id} — {self.name}"


class TaskRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.CASCADE,
        related_name="task_runs",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    result_json = models.JSONField(null=True, blank=True, default=None)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Run {self.id} — {self.pipeline.name} ({self.status})"


class InstalledPlugin(models.Model):
    """A plugin installed from the remote marketplace registry.

    Tracks marketplace-installed plugins so the UI can show install state and
    support updates/uninstall. Only plugins with a row here are ``managed=True``
    (uninstallable); plugins not yet installed have no row.
    """

    name = models.CharField(max_length=255, unique=True)
    version = models.CharField(max_length=64)
    description = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=64, blank=True, default="process")
    author = models.CharField(max_length=255, blank=True, default="")
    curated = models.BooleanField(default=False)
    source_url = models.URLField(max_length=512)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    installed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.version}"
