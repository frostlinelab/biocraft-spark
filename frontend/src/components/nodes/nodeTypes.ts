import type { NodeTypes } from "@xyflow/react"
import InputNode from "./InputNode"
import PluginNode from "./PluginNode"

export const nodeTypes: NodeTypes = {
  biocraftInput: InputNode,
  biocraftPlugin: PluginNode,
}
