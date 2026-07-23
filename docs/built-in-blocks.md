# Built-in Blocks Reference

> Built-in blocks for Biocraft-Spark — the control foundation of every workflow.

---

## Overview

Built-in blocks are the foundational components of every workflow, provided directly by the Biocraft runtime (not loaded from plugins). They appear under the **"Built-in"** category in the editor panel.

---

## Block List

### Start

| Property | Value |
|---|---|
| **Name** | `start` |
| **Icon** | ▶ Circle |
| **Purpose** | Workflow entry point |

**Rules:**
- Every workflow **must have exactly one** Start block
- The Start block has no input ports
- The Start block has one output port `trigger` (type: `signal`)

**Output ports:**

| Port | Type | Description |
|---|---|---|
| `trigger` | `signal` | Trigger signal, usually connected to one or more processing blocks |

---

### End

| Property | Value |
|---|---|
| **Name** | `end` |
| **Icon** | ⏹ Circle with bar |
| **Purpose** | Workflow exit point |

**Rules:**
- A workflow can have **multiple** End blocks (e.g. different endpoints of conditional branches)
- The End block has one input port `data` (type: `signal`)
- The End block has no output ports

**Input ports:**

| Port | Type | Description |
|---|---|---|
| `data` | `signal` | Receives the upstream completion signal |

---

### Input

| Property | Value |
|---|---|
| **Name** | `input` |
| **Icon** | 📥 Hexagon |
| **Purpose** | File upload source, supports drag-and-drop and a file picker |

**Rules:**
- The Input block has no input ports
- The Input block has one output port `files` (type: `file`, multiple files allowed)
- Supports dragging files onto the node, or clicking to use the file picker
- Uploaded files automatically appear in the file list inside the node
- When connected to a downstream plugin block, Biocraft automatically computes the fan-out parallelism

**Output ports:**

| Port | Type | Multiple | Description |
|---|---|---|---|
| `files` | `file` | ✅ | List of uploaded files |

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path` | `string` | `""` | Default directory path |
| `pattern` | `string` | `"*"` | File type filter, e.g. `*.fasta` |

**Fan-out behavior:**
When an Input has 5 fasta files connected to Prokka, the Prokka node automatically expands into 5 aligned lanes (fishbone structure). Each lane processes one file in parallel.

---

### End

| Property | Value |
|---|---|
| **Name** | `end` |
| **Icon** | ⏹ Circle with bar |
| **Purpose** | Workflow exit, automatically collects all output files |

**Rules:**
- A workflow can have **multiple** End blocks
- The End block has one input port `data` (type: `signal`)
- The End block has no output ports
- **End automatically collects the output files of all upstream plugins**
- In the Node Inspector, **the last plugin's files are highlighted** ⭐
- Intermediate plugin files are also listed (collapsible)

**Input ports:**

| Port | Type | Description |
|---|---|---|
| `data` | `signal` | Receives the upstream completion signal |

**Node Inspector display:**
```
Outputs:
  ⭐ Prokka (last plugin):
     ├── genome_1.gff     12 KB
     ├── genome_1.fna      1.2 MB
     └── genome_1.faa     430 KB

  Input (source):
     ├── genome_1.fasta    3.4 MB
     └── genome_2.fasta    4.1 MB
```

---

## Typical Usage

### Minimal workflow

```
Start ──▶ End
```

The most basic flow — processes no data, only verifies the workflow engine runs.

### Data processing workflow

```
Start ──▶ Input ──▶ [Plugin Block] ──▶ Output ──▶ End
```

1. **Start** triggers the workflow
2. **Input** reads `.fastq` files from the local filesystem
3. **Plugin Block** (e.g. FastQC) processes the data
4. **Output** writes results to a specified directory
5. **End** marks the workflow complete

### Branching workflow

```
              ┌──▶ [FastQC] ──▶ End
Start ──▶ Input ──┤
              └──▶ [Trimmomatic] ──▶ Output ──▶ End
```

The same input can be fanned out to multiple processing paths, each with its own End.

---

## Differences from Plugin Blocks

| Dimension | Built-in blocks | Plugin blocks |
|---|---|---|
| **Source** | Built into the Biocraft runtime | YAML plugin files |
| **Runtime** | No container execution | Docker container execution |
| **Configurability** | Limited parameters | Full parameter system |
| **Ports** | Fixed control/data ports | Defined by the plugin author |
| **Category** | "Built-in" | Plugin name as the category title |
