"""Docker-backed verification for the FastQC plugin using a real FASTQ fixture."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from biocraft_core.plugin import get_all_block_specs, resolve_graph_to_task_nodes
from biocraft_core.runtime.executor import DockerContainerExecutor
from biocraft_core.runtime.scheduler import DAGEngine


@skipUnless(
    os.environ.get("BIOCRAFT_RUN_DOCKER_TESTS") == "1",
    "set BIOCRAFT_RUN_DOCKER_TESTS=1 to run Docker-backed integration tests",
)
class FastQCIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.fixture_dir = Path(settings.BASE_DIR) / "tests" / "fastqc"
        self.input_dir = self.fixture_dir / "inputs"
        self.output_dir = self.fixture_dir / "outputs"
        host_project_dir = os.environ.get("BIOCRAFT_DOCKER_HOST_PROJECT_DIR")
        self.mount_fixture_dir = (
            Path(host_project_dir) / "tests" / "fastqc"
            if host_project_dir
            else self.fixture_dir
        )
        shutil.rmtree(self.output_dir, ignore_errors=True)
        self.output_dir.mkdir(parents=True)

        # Isolate the plugins dir so the test does not depend on the real plugins/.
        self.plugins_tmp = tempfile.TemporaryDirectory()
        self._override = override_settings(BIOCRAFT_PLUGINS_DIR=Path(self.plugins_tmp.name))
        self._override.enable()
        shutil.copy(
            Path(settings.BASE_DIR) / "tests" / "fixtures" / "fastqc.plugin.yaml",
            Path(self.plugins_tmp.name) / "fastqc.plugin.yaml",
        )

    def tearDown(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)
        self.output_dir.mkdir(parents=True)
        (self.output_dir / ".gitkeep").touch()
        self._override.disable()
        self.plugins_tmp.cleanup()

    def test_fastqc_processes_real_fixture_with_isolated_mounts(self):
        graph = {
            "nodes": [
                {
                    "id": "input",
                    "data": {
                        "blockPlugin": "builtin",
                        "blockName": "input",
                        "files": [{"id": "fastqc_sample.fastq", "name": "sample.fastq"}],
                    },
                },
                {
                    "id": "fastqc",
                    "data": {
                        "blockPlugin": "fastqc",
                        "blockName": "run-fastqc",
                        "hasRuntime": True,
                        "paramValues": {"threads": 1},
                    },
                },
            ],
            "edges": [{"source": "input", "target": "fastqc"}],
        }
        specs = get_all_block_specs(settings.BIOCRAFT_PLUGINS_DIR)
        tasks = resolve_graph_to_task_nodes(
            graph,
            specs,
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            mount_input_dir=self.mount_fixture_dir / "inputs",
            mount_output_dir=self.mount_fixture_dir / "outputs",
        )

        result = DAGEngine(DockerContainerExecutor()).run(tasks)

        self.assertTrue(result.succeeded, result.to_dict())
        task_output = self.output_dir / tasks[0].name
        self.assertTrue((task_output / "sample_fastqc.html").is_file())
        self.assertTrue((task_output / "sample_fastqc.zip").is_file())
