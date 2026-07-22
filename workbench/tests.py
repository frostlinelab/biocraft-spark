import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from biocraft_core.plugin import discover_plugins, get_all_block_specs, resolve_graph_to_task_nodes
from biocraft_core.runtime.resources import ResourcePool, RuntimeConfig
from biocraft_core.runtime.scheduler import TaskStatus

from workbench.models import InstalledPlugin


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
    """Plugin discovery + DAG resolution, demonstrated via the FastQC fixture."""

    FASTQC_FIXTURE = Path(settings.BASE_DIR) / "tests" / "fixtures" / "fastqc.plugin.yaml"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._override = override_settings(BIOCRAFT_PLUGINS_DIR=Path(self.tmp.name))
        self._override.enable()
        shutil.copy(self.FASTQC_FIXTURE, Path(self.tmp.name) / "fastqc.plugin.yaml")
        self.plugins_dir = Path(self.tmp.name)

    def tearDown(self):
        self._override.disable()
        self.tmp.cleanup()

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
        self.assertEqual(block.runtime.image, "biocontainers/fastqc:v0.11.9_cv8")
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
            self.assertEqual(task.image, "biocontainers/fastqc:v0.11.9_cv8")
            # ${params.threads} must be expanded to the node value
            joined = " ".join(task.command)
            self.assertIn("-t 3", joined)
            self.assertNotIn("${params.threads}", joined)
            self.assertTrue(task.name.startswith("fastqc__run-fastqc__"))

    def test_resolve_fastqc_mounts_each_uploaded_file_and_output(self):
        specs = get_all_block_specs(str(self.plugins_dir))
        input_dir = Path(settings.BASE_DIR) / "tests" / "fastqc" / "inputs"
        output_dir = Path(settings.BASE_DIR) / "tests" / "fastqc" / "outputs"
        graph = {
            "nodes": [
                {
                    "id": "in1",
                    "data": {
                        "blockPlugin": "builtin",
                        "blockName": "input",
                        "files": [{"id": "fastqc_sample.fastq", "name": "sample.fastq"}],
                    },
                },
                {
                    "id": "qc1",
                    "data": {
                        "blockPlugin": "fastqc",
                        "blockName": "run-fastqc",
                        "hasRuntime": True,
                    },
                },
            ],
            "edges": [{"source": "in1", "target": "qc1"}],
        }

        tasks = resolve_graph_to_task_nodes(
            graph,
            specs,
            input_dir=input_dir,
            output_dir=output_dir,
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].volumes[0].host_path, input_dir / "fastqc_sample.fastq")
        self.assertEqual(tasks[0].volumes[0].container_path, "/data/input/sample.fastq")
        self.assertEqual(tasks[0].volumes[0].mode, "ro")
        self.assertEqual(tasks[0].volumes[1].container_path, "/data/output")


# ── Marketplace API tests ─────────────────────────────────────────────────────

# A minimal but valid blocks-format plugin used for install/uninstall tests.
_TEST_PLUGIN_YAML = b"""\
name: testplugin
version: "0.1.0"
description: A test plugin for marketplace tests
icon: process
blocks:
  - name: run-test
    label: Test
    description: test block
    icon: process
    runtime:
      image: hello-world:latest
      command: ["echo", "hi"]
      resources:
        min_threads: 1
        min_memory_gb: 1.0
    inputs:
      - name: in
        label: In
        type: file
        pattern: "*.txt"
    outputs:
      - name: out
        label: Out
        type: file
        pattern: "*.out"
    params:
      - name: mode
        label: Mode
        type: string
        default: fast
"""


def _fake_urlopen(content: bytes):
    """Return a MagicMock that behaves like urlopen()'s context manager."""
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = content
    cm.__exit__.return_value = None
    return cm


def _reset_index_cache() -> None:
    from workbench.api import _INDEX_CACHE
    _INDEX_CACHE["data"] = None
    _INDEX_CACHE["fetched_at"] = 0.0


class MarketplaceCatalogTests(TestCase):
    """GET /api/marketplace/catalog/ — enrichment with local install state."""

    def setUp(self):
        _reset_index_cache()
        # Isolate from local dev state (manually-installed plugins on disk / in DB).
        self.tmp = tempfile.TemporaryDirectory()
        self._override = override_settings(BIOCRAFT_PLUGINS_DIR=Path(self.tmp.name))
        self._override.enable()

    def tearDown(self):
        self._override.disable()
        self.tmp.cleanup()
        InstalledPlugin.objects.all().delete()

    @patch("workbench.api._fetch_marketplace_index")
    def test_catalog_enriches_installed_status(self, mock_index):
        mock_index.return_value = {
            "schema_version": 1,
            "plugins": [
                {
                    "name": "fastqc",
                    "version": "1.0.0",
                    "description": "Quality control",
                    "icon": "microscope",
                    "author": "official",
                    "curated": True,
                    "yaml_url": "https://example/plugins/fastqc.plugin.yaml",
                    "sha256": "abc",
                },
                {
                    "name": "prokka",
                    "version": "2.0.0",
                    "description": "Annotation",
                    "icon": "dna",
                    "author": "official",
                    "curated": False,
                    "yaml_url": "https://example/plugins/prokka.plugin.yaml",
                    "sha256": "def",
                },
            ],
        }

        # Neither plugin is installed yet → both null / not managed.
        response = self.client.get(reverse("marketplace_catalog"))
        self.assertEqual(response.status_code, 200)
        plugins = {p["name"]: p for p in response.json()["plugins"]}

        self.assertIsNone(plugins["fastqc"]["installed_version"])
        self.assertFalse(plugins["fastqc"]["managed"])
        self.assertTrue(plugins["fastqc"]["curated"])

        self.assertIsNone(plugins["prokka"]["installed_version"])
        self.assertFalse(plugins["prokka"]["managed"])

        # After recording a marketplace install (InstalledPlugin row), prokka shows
        # as installed + managed (uninstallable).
        InstalledPlugin.objects.create(
            name="prokka",
            version="2.0.0",
            source_url="https://example/plugins/prokka.plugin.yaml",
        )
        response = self.client.get(reverse("marketplace_catalog"))
        plugins = {p["name"]: p for p in response.json()["plugins"]}
        self.assertEqual(plugins["prokka"]["installed_version"], "2.0.0")
        self.assertTrue(plugins["prokka"]["managed"])

    @patch("workbench.api._fetch_marketplace_index")
    def test_catalog_returns_502_when_registry_unreachable(self, mock_index):
        mock_index.return_value = None
        response = self.client.get(reverse("marketplace_catalog"))
        self.assertEqual(response.status_code, 502)


class MarketplaceInstallTests(TestCase):
    """POST install / DELETE uninstall — isolated to a temp plugins dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._override = override_settings(BIOCRAFT_PLUGINS_DIR=Path(self.tmp.name))
        self._override.enable()
        _reset_index_cache()

    def tearDown(self):
        self._override.disable()
        self.tmp.cleanup()
        InstalledPlugin.objects.all().delete()

    @patch("workbench.api.urllib.request.urlopen")
    def test_install_downloads_and_persists(self, mock_urlopen):
        mock_urlopen.return_value = _fake_urlopen(_TEST_PLUGIN_YAML)

        response = self.client.post(
            reverse("marketplace_install"),
            data={
                "yaml_url": "https://example/plugins/testplugin.plugin.yaml",
                "author": "tester",
                "curated": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        body = response.json()
        self.assertEqual(body["name"], "testplugin")
        self.assertEqual(body["version"], "0.1.0")
        self.assertTrue(body["managed"])

        # DB record created with the metadata sent in the body
        ip = InstalledPlugin.objects.get(name="testplugin")
        self.assertEqual(ip.version, "0.1.0")
        self.assertTrue(ip.curated)
        self.assertEqual(ip.author, "tester")
        self.assertEqual(ip.source_url, "https://example/plugins/testplugin.plugin.yaml")

        # YAML file written to the (temp) plugins dir
        self.assertTrue((Path(self.tmp.name) / "testplugin.plugin.yaml").exists())

    @patch("workbench.api.urllib.request.urlopen")
    def test_install_rejects_checksum_mismatch(self, mock_urlopen):
        mock_urlopen.return_value = _fake_urlopen(_TEST_PLUGIN_YAML)
        response = self.client.post(
            reverse("marketplace_install"),
            data={
                "yaml_url": "https://example/plugins/testplugin.plugin.yaml",
                "sha256": "deadbeef" * 8,  # wrong checksum
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Checksum", response.json()["error"])
        self.assertFalse(InstalledPlugin.objects.filter(name="testplugin").exists())

    @patch("workbench.api.urllib.request.urlopen")
    def test_install_rejects_invalid_yaml(self, mock_urlopen):
        # A YAML scalar (not a mapping) → loader returns None → 400
        mock_urlopen.return_value = _fake_urlopen(b"just a scalar string\n")
        response = self.client.post(
            reverse("marketplace_install"),
            data={"yaml_url": "https://example/plugins/bad.plugin.yaml"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(InstalledPlugin.objects.filter(name="bad").exists())

    def test_uninstall_removes_record_and_file(self):
        # Seed an installed plugin directly (file + DB record).
        (Path(self.tmp.name) / "testplugin.plugin.yaml").write_bytes(_TEST_PLUGIN_YAML)
        InstalledPlugin.objects.create(
            name="testplugin",
            version="0.1.0",
            source_url="https://example/plugins/testplugin.plugin.yaml",
        )
        self.assertTrue(InstalledPlugin.objects.filter(name="testplugin").exists())

        response = self.client.delete(
            reverse("marketplace_uninstall", kwargs={"name": "testplugin"})
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertFalse(InstalledPlugin.objects.filter(name="testplugin").exists())
        self.assertFalse((Path(self.tmp.name) / "testplugin.plugin.yaml").exists())

    def test_uninstall_rejects_unmanaged_plugin(self):
        # fastqc has no InstalledPlugin row → 404 (not installed via marketplace).
        response = self.client.delete(
            reverse("marketplace_uninstall", kwargs={"name": "fastqc"})
        )
        self.assertEqual(response.status_code, 404)
