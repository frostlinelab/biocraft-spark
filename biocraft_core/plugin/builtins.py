"""Built-in block definitions (Start, End, Input, Output).

These are defined using the same BlockSpec data structure as plugin-contributed
blocks, so the frontend receives them through the same /api/blocks/ endpoint.
"""

from biocraft_core.plugin.schema import BlockParam, BlockPort, BlockSpec


def builtin_blocks() -> list[BlockSpec]:
    """Return the four built-in workflow blocks."""
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
            description="Workflow exit point — a workflow may have multiple End blocks.",
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
            description="Data source — reads files from the local filesystem.",
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
                    label="Source Path",
                    param_type="string",
                    default="",
                ),
            ],
        ),
        BlockSpec(
            name="output",
            label="Output",
            description="Data sink — writes files to the local filesystem.",
            icon="output",
            plugin_name="builtin",
            runtime=None,
            inputs=[
                BlockPort(
                    name="files",
                    label="Files",
                    port_type="file",
                    multiple=True,
                ),
            ],
            outputs=[],
            params=[
                BlockParam(
                    name="path",
                    label="Destination Path",
                    param_type="string",
                    default="",
                ),
            ],
        ),
    ]
