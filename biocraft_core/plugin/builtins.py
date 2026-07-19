"""Built-in block definitions (Input block).

These are defined using the same BlockSpec data structure as plugin-contributed
blocks, so the frontend receives them through the same /api/blocks/ endpoint.
"""

from biocraft_core.plugin.schema import BlockParam, BlockPort, BlockSpec


def builtin_blocks() -> list[BlockSpec]:
    """Return the built-in Input block."""
    return [
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
