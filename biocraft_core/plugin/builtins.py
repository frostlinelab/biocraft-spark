"""Built-in block definitions (Start, End, Input).

These are defined using the same BlockSpec data structure as plugin-contributed
blocks, so the frontend receives them through the same /api/blocks/ endpoint.
"""

from biocraft_core.plugin.schema import BlockParam, BlockPort, BlockSpec


def builtin_blocks() -> list[BlockSpec]:
    """Return the three built-in workflow blocks."""
    return [
        BlockSpec(
            name="start",
            label="Start",
            description="Workflow entry point — every workflow must have exactly one Start block.",
            icon="start",
            plugin_name="builtin",
            runtime=None,
            inputs=[],
            outputs=[
                BlockPort(
                    name="trigger",
                    label="Trigger",
                    port_type="signal",
                ),
            ],
            params=[],
        ),
        BlockSpec(
            name="end",
            label="End",
            description="Workflow exit point — collects all output files. Files from the last plugin are highlighted.",
            icon="end",
            plugin_name="builtin",
            runtime=None,
            inputs=[
                BlockPort(
                    name="data",
                    label="Data",
                    port_type="signal",
                ),
            ],
            outputs=[],
            params=[],
        ),
        BlockSpec(
            name="input",
            label="Input",
            description="File upload source — drag files here or select from the file picker. Supports fan-out to downstream plugins.",
            icon="input",
            plugin_name="builtin",
            runtime=None,
            inputs=[],
            outputs=[
                BlockPort(
                    name="files",
                    label="Files",
                    port_type="file",
                    multiple=True,
                ),
            ],
            params=[
                BlockParam(
                    name="path",
                    label="Default Directory",
                    param_type="string",
                    default="",
                ),
                BlockParam(
                    name="pattern",
                    label="File Filter",
                    param_type="string",
                    default="*",
                ),
            ],
        ),
    ]
