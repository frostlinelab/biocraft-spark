from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse

from biocraft_core.runtime.scheduler import TaskStatus


class DockerPingTests(TestCase):
    def test_docker_ping_reports_import_failures(self):
        with patch("workbench.views.import_module", side_effect=ModuleNotFoundError("distutils")):
            response = self.client.get(reverse("docker_ping"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["docker"], False)
        self.assertIn("import failed", response.json()["error"])

    def test_docker_ping_returns_container_names(self):
        client = Mock()
        client.ping.return_value = True
        client.containers.list.return_value = [
            SimpleNamespace(name="alpha"),
            SimpleNamespace(name="beta"),
        ]
        docker_module = Mock()
        docker_module.from_env.return_value = client

        with patch("workbench.views.import_module", return_value=docker_module):
            response = self.client.get(reverse("docker_ping"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"docker": True, "containers": ["alpha", "beta"]},
        )


class SchedulerPingTests(TestCase):
    @patch("workbench.views.DockerContainerExecutor")
    def test_scheduler_ping_returns_dag_result(self, executor_cls):
        executor = executor_cls.return_value
        executor.run.side_effect = [
            SimpleNamespace(
                exit_code=0,
                stdout="A: start\n",
                stderr="",
                error_message=None,
            ),
            SimpleNamespace(
                exit_code=0,
                stdout="B: left after A\n",
                stderr="",
                error_message=None,
            ),
            SimpleNamespace(
                exit_code=0,
                stdout="C: right after A\n",
                stderr="",
                error_message=None,
            ),
        ]

        response = self.client.get(reverse("scheduler_ping"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "succeeded": True,
                "tasks": {
                    "A": {
                        "status": TaskStatus.SUCCESS.value,
                        "exit_code": 0,
                        "stdout": "A: start\n",
                        "stderr": "",
                        "error": None,
                    },
                    "B": {
                        "status": TaskStatus.SUCCESS.value,
                        "exit_code": 0,
                        "stdout": "B: left after A\n",
                        "stderr": "",
                        "error": None,
                    },
                    "C": {
                        "status": TaskStatus.SUCCESS.value,
                        "exit_code": 0,
                        "stdout": "C: right after A\n",
                        "stderr": "",
                        "error": None,
                    },
                },
            },
        )
