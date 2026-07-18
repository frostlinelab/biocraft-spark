# Runtime Configuration Guide

> 配置 Biocraft-Spark 的全局 CPU/内存资源池。

---

## 概述

Biocraft-Spark 需要一个全局资源池来决定插件积木的并行度（fan-out）。用户告知系统自己机器的 CPU 核心数、线程数、内存，系统据此计算：

- 每个插件积木最多可以并行多少实例
- 当输入文件数超过并行上限时，分几波执行

---

## 配置位置

在 `biocraft_spark/settings.py` 中：

```python
BIOCRAFT_RUNTIME = {
    "cpu_cores": 8,              # CPU 物理核心数
    "cpu_threads": 16,            # CPU 逻辑线程数（含超线程）
    "memory_gb": 32,              # 可用内存 (GB)
    "max_parallel_containers": 8, # 同时运行的容器数量上限
}
```

---

## 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `cpu_cores` | int | 4 | CPU 物理核心数，用于前端信息展示 |
| `cpu_threads` | int | 8 | 逻辑线程数，**决定并行度计算** |
| `memory_gb` | int | 8 | 总可用内存 (GB) |
| `max_parallel_containers` | int | 8 | 硬性限制：无论 CPU 多空闲，最多同时跑几个容器 |

---

## 并行度计算

```
并行实例数 = min(文件数, cpu_threads / 插件最低线程数, max_parallel_containers)
```

### 示例

**机器：** 8 核 16 线程，32 GB，最多 8 容器

**Prokka 插件** (`min_threads: 2`)：

| 输入文件数 | 计算过程 | 结果 |
|---|---|---|
| 5 | min(5, 16/2, 8) | **5 并行** |
| 10 | min(10, 8, 8) | **8 并行**（受 CPU 限制） |
| 50 | min(50, 8, 8) | **8 并行**，分 7 波 |

**FastQC 插件** (`min_threads: 1`)：

| 输入文件数 | 计算过程 | 结果 |
|---|---|---|
| 10 | min(10, 16/1, 8) | **8 并行**（受容器上限限制） |
| 5 | min(5, 16, 8) | **5 并行** |

---

## 前端获取

前端通过 API 获取运行时配置：

```
GET /api/runtime-config/
```

```json
{
  "cpuCores": 8,
  "cpuThreads": 16,
  "memoryGb": 32,
  "maxParallelContainers": 8
}
```

编辑器中的插件节点会显示资源徽标：

```
Prokka [5 files · 10 threads / 16 available]
```

---

## 查看实际配置

```bash
curl http://127.0.0.1:8000/api/runtime-config/ | python -m json.tool
```
