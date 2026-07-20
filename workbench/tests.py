from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from biocraft_core.plugin import discover_plugins, get_all_block_specs, resolve_graph_to_task_nodes
from biocraft_core.runtime.resources import ResourcePool, RuntimeConfig
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


class FastQCPluginTests(TestCase):
    """First official plugin: plugins/fastqc.plugin.yaml."""

    def setUp(self):
        self.plugins_dir = Path(settings.BIOCRAFT_PLUGINS_DIR)

    def test_discover_fastqc_plugin(self):
        plugins = discover_plugins(self.plugins_dir)
        names = [p.name for p in plugins]
        self.assertIn("fastqc", names)

        fastqc = next(p for p in plugins if p.name == "fastqc")
        self.assertEqual(fastqc.version, "1.0.0")
        self.assertEqual(len(fastqc.blocks), 1)

        block = fastqc.blocks[0]
        self.assertEqual(block.name, "run-fastqc")
        self.assertEqual(block.plugin_name, "fastqc")
        self.assertIsNotNone(block.runtime)
        self.assertEqual(block.runtime.image, "biocontainers/fastqc:v0.11.9")
        self.assertEqual(block.runtime.resources.min_threads, 1)
        self.assertEqual(block.runtime.resources.min_memory_gb, 1.0)
        self.assertTrue(any(p.name == "threads" for p in block.params))
        self.assertTrue(any(p.name == "reads" for p in block.inputs))
        self.assertTrue(any(p.pattern == "*_fastqc.html" for p in block.outputs))

    def test_blocks_api_exposes_fastqc_resources(self):
        response = self.client.get("/api/blocks/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        categories = {c["name"]: c for c in body["categories"]}
        self.assertIn("fastqc", categories)

        blocks = {b["name"]: b for b in categories["fastqc"]["blocks"]}
        self.assertIn("run-fastqc", blocks)
        block = blocks["run-fastqc"]
        self.assertTrue(block["hasRuntime"])
        self.assertEqual(block["resources"]["minThreads"], 1)
        self.assertEqual(block["resources"]["minMemoryGb"], 1.0)
        self.assertEqual(block["params"][0]["name"], "threads")

    def test_resolve_fastqc_fanout_and_param_substitution(self):
        specs = get_all_block_specs(str(self.plugins_dir))
        pool = ResourcePool(RuntimeConfig(cpu_threads=4, max_parallel_containers=4))

        graph = {
            "nodes": [
                {
                    "id": "in1",
                    "data": {
                        "blockPlugin": "builtin",
                        "blockName": "input",
                        "files": [
                            {"name": "sample_a.fastq"},
                            {"name": "sample_b.fastq"},
                        ],
                    },
                },
                {
                    "id": "qc1",
                    "data": {
                        "blockPlugin": "fastqc",
                        "blockName": "run-fastqc",
                        "hasRuntime": True,
                        "paramValues": {"threads": 3},
                    },
                },
            ],
            "edges": [{"source": "in1", "target": "qc1"}],
        }

        tasks = resolve_graph_to_task_nodes(graph, specs, pool)
        self.assertEqual(len(tasks), 2)

        for task in tasks:
            self.assertEqual(task.image, "biocontainers/fastqc:v0.11.9")
            # ${params.threads} must be expanded to the node value
            joined = " ".join(task.command)
            self.assertIn("-t 3", joined)
            self.assertNotIn("${params.threads}", joined)
            self.assertTrue(task.name.startswith("fastqc__run-fastqc__"))
