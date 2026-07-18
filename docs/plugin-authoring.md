# Plugin Authoring Guide

> 如何为 Biocraft-Spark 编写插件 — 从零到发布。

---

## 目录

- [概述](#概述)
- [快速开始](#快速开始)
- [插件 YAML 格式](#插件-yaml-格式)
- [积木定义参考](#积木定义参考)
- [端口类型系统](#端口类型系统)
- [连接规则](#连接规则)
- [配置参数](#配置参数)
- [容器路径约定](#容器路径约定)
- [容器镜像规范](#容器镜像规范)
- [完整示例](#完整示例)
- [本地验证](#本地验证)
- [向后兼容](#向后兼容)

---

## 概述

在 Biocraft-Spark 中，**插件 = 积木的集合**。一个插件 YAML 文件可以定义一个或多个积木（block），每个积木对应一个可在工作流编辑器中拖拽使用的节点。

**核心理念：插件作者只需声明"我的工具需要什么输入、产出什么输出、怎么运行"，Biocraft 负责文件路由、容器调度和错误重试。**

```
插件 YAML  ──加载──▶  积木注册表  ──展示──▶  编辑器面板
                           │
                           ▼
                      用户拖拽组装
                           │
                           ▼
                      DAG 调度执行
```

---

## 快速开始

最小的插件只包含一个积木：

```yaml
name: hello-world
version: "0.1"
description: 最小示例插件

blocks:
  - name: greet
    label: Hello
    description: 打印一条问候语
    icon: process

    runtime:
      image: python:3.12-slim
      command: ["python", "-c", "print('Hello, Biocraft!')"]
```

保存为 `hello-world.plugin.yaml`，放入 `plugins/` 目录。启动 Biocraft 后，该积木会自动出现在编辑器右侧面板中。

---

## 插件 YAML 格式

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 插件包名，用作面板中的分类标题。建议使用小写字母和连字符，如 `my-bio-tools` |
| `version` | string | ✅ | 语义化版本号，如 `"1.0.0"` |
| `description` | string | ❌ | 一句话描述插件的用途 |
| `icon` | string | ❌ | 面板分类图标，默认 `process`。可选值见 [图标列表](#可用图标) |
| `blocks` | array | ✅ | 积木列表，至少 1 个 |

### 积木字段 (`blocks[]`)

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 积木唯一标识，插件内不可重复 |
| `label` | string | ❌ | 面板显示名称，默认使用 `name` |
| `description` | string | ❌ | 鼠标悬停提示文字 |
| `icon` | string | ❌ | 积木图标，默认 `process` |
| `runtime` | object | ❌ | 容器执行配置（无 `runtime` 的积木为纯控制节点） |
| `inputs` | array | ❌ | 输入端口列表 |
| `outputs` | array | ❌ | 输出端口列表 |
| `params` | array | ❌ | 用户可配置的参数列表 |

### Runtime 字段 (`runtime`)

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `image` | string | ✅ | Docker 镜像，如 `biocontainers/fastqc:v0.11.9` |
| `command` | string[] | ✅ | 容器启动命令，数组格式。支持 `${params.xxx}` 引用参数 |
| `env` | object | ❌ | 环境变量键值对 |

---

## 积木定义参考

### Inputs 端口 (`inputs[]`)

每个输入端口定义一个节点**左侧**的连接点：

```yaml
inputs:
  - name: reads           # 端口 ID（必填）
    label: 测序文件         # 端口显示名（选填，默认用 name）
    type: file            # 端口类型：file | directory | string | number | signal
    pattern: "*.fastq"    # 文件 glob 过滤（仅 file/directory 类型有效）
    multiple: true        # 是否接受多个值（多文件输入）
```

### Outputs 端口 (`outputs[]`)

每个输出端口定义一个节点**右侧**的连接点：

```yaml
outputs:
  - name: report
    label: 质量报告
    type: file
    pattern: "*.html"     # 本积木产出的文件模式
```

### 可用图标

| 图标键 | 形状 | 适用场景 |
|---|---|---|
| `start` | 圆形 | 工作流入口 |
| `end` | 带横线的圆形 | 工作流出口 |
| `input` | 六边形 | 数据输入源 |
| `output` | 六边形 | 数据输出汇 |
| `process` | 圆角矩形 | 通用计算步骤 |
| `condition` | 菱形 | 分支/判断 |
| `beaker` | 烧杯 | 实验/分析工具 |
| `microscope` | 显微镜 | 质量控制/检查 |
| `dna` | DNA 双螺旋 | 序列分析 |
| `filter` | 漏斗 | 筛选/过滤 |
| `wrench` | 扳手 | 工具/转换 |
| `builtin` | 分层菱形 | 内置/系统 |

---

## 端口类型系统

| 类型 | 说明 | 连接规则 |
|---|---|---|
| `file` | 单个文件 | 可连 `file`、`directory` 端口；同类型优先 |
| `directory` | 目录 | 可连 `directory` 端口；也可接收 `file`（文件放入目录） |
| `string` | 文本值 | 可连 `string`、`number`（自动转换） |
| `number` | 数值 | 可连 `number`；也可连 `string`（需可解析） |
| `signal` | 控制信号 | 只连 `signal`；用于 Start → End 等流程控制 |

---

## 连接规则

编辑器会校验端口连接：

1. **类型兼容** — 只有兼容的端口类型才能相连（见上表）
2. **方向匹配** — 输出端口 → 输入端口
3. **容量检查** — `multiple: false` 的输入端口只能接受一个连接
4. **循环检测** — 不允许形成环路

---

## 配置参数

参数会在编辑器的 Node Inspector 面板中渲染为表单控件：

```yaml
params:
  - name: threads          # 参数 ID（必填）
    label: 线程数           # 表单标签（选填，默认用 name）
    type: integer          # 类型：string | integer | float | boolean | select
    default: 4             # 默认值
    min: 1                 # 最小值（integer/float）
    max: 32                # 最大值（integer/float）
    options: []            # 选项列表（select 类型必填）

  - name: mode
    label: 运行模式
    type: select
    default: "auto"
    options: ["auto", "fast", "sensitive"]
```

在 `runtime.command` 中使用 `${params.参数名}` 引用参数值：

```yaml
runtime:
  command: ["fastqc", "-t", "${params.threads}", "-o", "/data/output", "/data/input/*.fastq"]
```

---

## 资源配置

插件积木可以声明每个实例所需的 CPU 和内存资源。Biocraft 使用这些信息来计算并行度（fan-out）。

```yaml
runtime:
  image: biocontainers/prokka:1.14.6
  command: ["prokka", "--cpus", "${params.threads}", ...]
  resources:
    min_threads: 2        # 每个实例最少需要的线程数
    min_memory_gb: 4      # 每个实例最少需要的内存 (GB)
```

### Fan-out 自动并行

当 Input 积木提供了 N 个文件，且下游插件声明了 `resources.min_threads`，Biocraft 自动计算并行度：

```
并行实例数 = min(文件数, 全局线程数 / 插件最低线程数)
```

**示例：** 8 核 16 线程的机器，Prokka 声明 `min_threads: 2`：
- 5 个 fasta 文件 → 5 × 2 = 10 线程 < 16 → **5 个全部并行**
- 50 个 fasta 文件 → min(50, 16/2) = **8 个并行**，分 7 波执行

在编辑器中，插件节点会自动展开显示 fan-out lanes（鱼骨结构），每条 lane 对应一个输入文件。Lanes 由 Biocraft 锁定对齐，用户无需手动排列。

### 全局资源池

在 Django `settings.py` 中配置：

```python
BIOCRAFT_RUNTIME = {
    "cpu_cores": 8,
    "cpu_threads": 16,
    "memory_gb": 32,
    "max_parallel_containers": 8,
}
```

前端可通过 `GET /api/runtime-config/` 获取资源信息，用于编辑器中的资源徽标显示。

---

## 容器路径约定

**所有积木的容器命令必须遵守以下路径约定：**

| 常量 | 容器内路径 | 用途 |
|---|---|---|
| `INPUT_DIR` | `/data/input` | 上游步骤筛选后的文件挂载到此 |
| `OUTPUT_DIR` | `/data/output` | 本步骤的产出写入此目录 |
| `SHARED_DIR` | `/data/shared` | 工作流级共享数据（参考基因组等） |

**规则：从 `/data/input` 读，往 `/data/output` 写。** Biocraft 自动处理文件挂载和路由。

---

## 容器镜像规范

1. **入口兼容** — 镜像的默认 `ENTRYPOINT` 不能阻塞 `command` 参数
2. **路径约定** — 命令中读写路径使用 `/data/input` / `/data/output`
3. **幂等性** — 相同输入多次执行应产生相同输出
4. **退出码** — 成功返回 `0`，失败返回非 `0`
5. **无交互** — 不要有 `prompt`、`tty` 等需要人工输入的逻辑

推荐使用 [BioContainers](https://biocontainers.pro/) 的官方镜像。

---

## 完整示例

### 示例 1：FastQC（单积木插件）

```yaml
name: fastqc
version: "1.0.0"
description: Quality control for sequencing reads
icon: microscope

blocks:
  - name: run-fastqc
    label: FastQC
    description: Run FastQC quality control on sequencing reads
    icon: beaker

    runtime:
      image: biocontainers/fastqc:v0.11.9
      command:
        - "fastqc"
        - "-o", "/data/output"
        - "-t", "${params.threads}"
        - "/data/input/*.fastq"

    inputs:
      - name: reads
        label: Sequencing Reads
        type: file
        pattern: "*.fastq"
        multiple: true

    outputs:
      - name: report
        label: QC Report
        type: file
        pattern: "*.html"
      - name: data
        label: QC Data
        type: file
        pattern: "*.zip"

    params:
      - name: threads
        label: Threads
        type: integer
        default: 4
        min: 1
        max: 32
```

### 示例 2：Trimmomatic（带多参数）

```yaml
name: trimmomatic
version: "1.0.0"
description: Read trimming tool
icon: filter

blocks:
  - name: trim
    label: Trimmomatic
    description: Trim adapter sequences and low-quality bases
    icon: filter

    runtime:
      image: biocontainers/trimmomatic:v0.39
      command:
        - "trimmomatic"
        - "PE"
        - "-threads", "${params.threads}"
        - "/data/input/*_1.fastq"
        - "/data/input/*_2.fastq"
        - "/data/output/trimmed_1.fastq"
        - "/data/output/unpaired_1.fastq"
        - "/data/output/trimmed_2.fastq"
        - "/data/output/unpaired_2.fastq"
        - "${params.mode}:${params.window}:${params.quality}"
        - "MINLEN:${params.minlen}"

    inputs:
      - name: reads
        label: Paired Reads
        type: file
        pattern: "*.fastq"
        multiple: true

    outputs:
      - name: trimmed
        label: Trimmed Reads
        type: file
        pattern: "trimmed_*.fastq"

    params:
      - name: threads
        label: Threads
        type: integer
        default: 4
        min: 1
        max: 32
      - name: mode
        label: Trimming Mode
        type: select
        default: "SLIDINGWINDOW"
        options: ["SLIDINGWINDOW", "MAXINFO"]
      - name: window
        label: Window Size
        type: integer
        default: 4
        min: 1
        max: 20
      - name: quality
        label: Quality Threshold
        type: integer
        default: 20
        min: 0
        max: 40
      - name: minlen
        label: Min Read Length
        type: integer
        default: 36
        min: 1
        max: 1000
```

### 示例 3：多积木插件（工具集）

```yaml
name: quality-toolkit
version: "1.0.0"
description: 测序质量控制工具集
icon: microscope

blocks:
  - name: fastqc
    label: FastQC
    description: 生成质量报告
    icon: beaker
    runtime:
      image: biocontainers/fastqc:v0.11.9
      command: ["fastqc", "-o", "/data/output", "/data/input/*.fastq"]
    inputs:
      - name: reads
        label: Reads
        type: file
        pattern: "*.fastq"
        multiple: true
    outputs:
      - name: report
        label: Report
        type: file
        pattern: "*.html"

  - name: multiqc
    label: MultiQC
    description: 汇总多个 FastQC 报告
    icon: beaker
    runtime:
      image: ewels/multiqc:v1.14
      command: ["multiqc", "-o", "/data/output", "/data/input/"]
    inputs:
      - name: reports
        label: QC Reports
        type: directory
        multiple: false
    outputs:
      - name: summary
        label: Summary Report
        type: file
        pattern: "multiqc_report.html"
```

---

## 本地验证

```python
from biocraft_core.plugin import discover_plugins

plugins = discover_plugins("plugins/")
for p in plugins:
    print(f"✅ {p.name} v{p.version} — {len(p.blocks)} block(s)")
    for b in p.blocks:
        ports_in = ", ".join(f"{t.name}:{t.port_type}" for t in b.inputs) or "none"
        ports_out = ", ".join(f"{t.name}:{t.port_type}" for t in b.outputs) or "none"
        print(f"   [{b.icon}] {b.label}")
        print(f"       image: {b.runtime.image if b.runtime else 'none'}")
        print(f"       in:  {ports_in}")
        print(f"       out: {ports_out}")
```

也可以启动 Django 后访问 `GET /api/blocks/` 查看所有已加载的积木。

---

## 向后兼容

旧版格式（使用 `steps:` 定义完整流水线）仍可正常加载：

```yaml
# 旧格式 — 仍然有效，每个 step 自动转换为一个 BlockSpec
name: prokka-roary-pipeline
version: "0.1"
steps:
  - name: prokka
    image: biocontainers/prokka:1.14.6
    command: ["prokka", "--outdir", "/data/output", "/data/input/genome.fasta"]
    outputs:
      - pattern: "*.gff"
        type: file
```

检测逻辑：有 `blocks:` 键 → 新格式；有 `steps:` 键 → 旧格式自动转换；两者皆无 → 跳过并警告。

**建议新插件使用 `blocks:` 格式**，以获得完整的端口、参数和图标支持。
