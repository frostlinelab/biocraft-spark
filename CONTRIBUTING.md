# Contributing to Biocraft-Spark

欢迎贡献插件！本指南覆盖插件开发的全流程：从写 YAML 到容器镜像规范。

---

## 目录

- [快速开始](#快速开始)
- [插件 YAML 格式](#插件-yaml-格式)
- [标准容器路径](#标准容器路径)
- [输入输出声明](#输入输出声明)
- [完整示例：Prokka → Roary](#完整示例prokka--roary)
- [容器镜像规范](#容器镜像规范)
- [重试策略](#重试策略)
- [本地调试](#本地调试)

---

## 快速开始

一个 Biocraft 插件就是一个 **YAML 文件**，描述一组有序的容器执行步骤。最小的插件长这样：

```yaml
name: hello-world
version: "0.1"
description: 最小示例
steps:
  - name: greet
    image: python:3.12-slim
    command: ["python", "-c", "print('Hello, Biocraft!')"]
```

保存为 `hello.yaml`，在 Biocraft 中加载即可执行。

---

## 插件 YAML 格式

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 插件名称，唯一标识 |
| `version` | string | ✅ | 语义化版本号，如 `"1.0.0"` |
| `description` | string | ❌ | 一句话描述插件功能 |
| `steps` | array | ✅ | 步骤列表，至少 1 个 |

### 步骤字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 步骤名称，插件内唯一 |
| `image` | string | ✅ | Docker 镜像，如 `biocontainers/prokka:1.14.6` |
| `command` | array | ✅ | 容器启动命令，数组格式 |
| `depends_on` | array | ❌ | 依赖的前置步骤名称列表 |
| `env` | object | ❌ | 环境变量键值对 |
| `inputs` | array | ❌ | 输入文件声明（见下文） |
| `outputs` | array | ❌ | 输出文件声明（见下文） |
| `retry` | object | ❌ | 重试策略 |

---

## 标准容器路径

**所有插件的容器命令必须遵守以下路径约定：**

| 常量 | 容器内路径 | 用途 |
|---|---|---|
| `INPUT_DIR` | `/data/input` | 上游步骤筛选后的文件挂载到此 |
| `OUTPUT_DIR` | `/data/output` | 本步骤的产出写入此目录 |
| `SHARED_DIR` | `/data/shared` | Pipeline 级共享数据（参考基因组等） |

```python
from biocraft_core import INPUT_DIR, OUTPUT_DIR, SHARED_DIR
```

**规则很简单：从 `/data/input` 读，往 `/data/output` 写。** 文件怎么来的、怎么路由的，Biocraft 帮你搞定。

---

## 输入输出声明

这是 Biocraft 最核心的能力：**插件声明需要什么文件，Biocraft 筛选并喂给你。**

### 输入声明 (`inputs`)

```yaml
inputs:
  - from: prokka           # 从哪个上游 step 拿（不填 = 所有上游）
    pattern: "*.gff"       # 文件 glob 模式
    type: file             # "file" 或 "directory"，默认 "file"
```

### 输出声明 (`outputs`)

```yaml
outputs:
  - pattern: "*.gff"       # 本步骤产出的文件模式
    type: file
  - pattern: "*.fna"
    type: file
```

### 工作原理

```
Prokka outputs:  .gff  .gbk  .fna  .faa  .ffn  .tbl  .tsv  .log ...
                       ↓
            Biocraft 按 Roary 的 inputs.pattern 筛选
                       ↓
Roary reads:     /data/input/*.gff   ← 只有 .gff 被挂载进来
```

插件开发者不需要写任何文件复制、筛选、重命名的胶水代码。

---

## 完整示例：Prokka → Roary

```yaml
name: prokka-roary-pipeline
version: "0.1"
description: 基因组注释 → 泛基因组分析

steps:
  - name: prokka
    image: biocontainers/prokka:1.14.6
    command:
      - "prokka"
      - "--outdir"
      - "/data/output"
      - "--prefix"
      - "sample"
      - "/data/input/genome.fasta"
    outputs:
      - pattern: "*.gff"
        type: file
      - pattern: "*.fna"
        type: file
      - pattern: "*.faa"
        type: file

  - name: roary
    image: sangerpathogens/roary:latest
    command:
      - "roary"
      - "-f"
      - "/data/output"
      - "-e"
      - "--mafft"
      - "/data/input/*.gff"
    depends_on:
      - prokka
    inputs:
      - from: prokka
        pattern: "*.gff"
        type: file
    outputs:
      - pattern: "*"
        type: directory
```

> **注意：** Prokka 产出 10+ 种文件，但 Roary 只需要 `.gff`。通过 `inputs.pattern: "*.gff"` 声明，Biocraft 自动筛选。

---

## 容器镜像规范

为了让 Biocraft 能正确执行你的步骤，容器镜像需满足：

1. **入口兼容** — 镜像的默认 `ENTRYPOINT` 不能阻塞 `command` 参数
2. **路径约定** — 命令中读写路径使用 `/data/input` / `/data/output`
3. **幂等性** — 相同输入多次执行应产生相同输出
4. **退出码** — 成功返回 `0`，失败返回非 `0`
5. **无交互** — 不要有 `prompt`、`tty` 等需要人工输入的逻辑

推荐直接使用 [BioContainers](https://biocontainers.pro/) 的官方镜像，它们已经满足以上规范。

---

## 重试策略

```yaml
retry:
  max_attempts: 3       # 最多执行次数（含首次），默认 1（不重试）
  delay_seconds: 5.0    # 重试间隔秒数
```

重试只发生在容器执行失败（非零退出码）时。某步骤重试耗尽后，依赖它的所有下游步骤自动跳过。

---

## 本地调试

在提交插件之前，可以用 Python 直接验证 YAML 格式：

```python
import io
from biocraft_core.plugin import load_plugin

yaml_text = """
name: my-plugin
version: "0.1"
steps:
  - name: test
    image: python:3.12-slim
    command: ["echo", "hello"]
"""

spec, nodes = load_plugin(io.StringIO(yaml_text))
print(f"✅ 插件 {spec.name} v{spec.version} 校验通过")
print(f"   共 {len(nodes)} 个步骤")

for node in nodes:
    deps = ", ".join(node.depends_on) if node.depends_on else "无"
    print(f"   - {node.name} (依赖: {deps})")
```

也可以在 Django 开发服务器启动后访问 `/debug/ping-plugin/` 验证插件格式。
