# 故障处理指南

Biocraft-Spark 常见问题及解决方法。

---

## 目录

- [容器运行时（必需）](#容器运行时必需)
- [数据库与启动](#数据库与启动)
- [Docker 相关](#docker-相关)
- [容器执行相关](#容器执行相关)
- [插件加载相关](#插件加载相关)
- [调度器相关](#调度器相关)
- [诊断端点](#诊断端点)

---

## 容器运行时（必需）

> **Biocraft-Spark 必须依赖容器运行时才能运行。** 没有容器运行时，工作流无法执行，应用不可用。

### macOS：必须使用 OrbStack

macOS 上推荐且由安装脚本自动安装的运行时是 **OrbStack**（Docker Desktop 也可用，但若已存在则脚本不会覆盖）。

`install.sh` 在 macOS 上的行为：

1. 若 `/Applications/OrbStack.app` 已存在 → 直接启动。
2. 否则，若安装了 Homebrew → `brew install --cask orbstack`。
3. 否则（**无 Homebrew、无 Xcode/CLT、无 git 也能装**）→ 从 Homebrew cask API 解析最新版 `.dmg`，下载后挂载拷贝到 `/Applications`。
4. `open -a OrbStack` 启动，首启需在 GUI 批准权限；脚本每 5s 轮询 `docker info` 直到就绪（**无固定超时，慢机也能等到**），每 15s 打印一次进度心跳。若 OrbStack 进程退出或 60s 内未启动则提前报错，不会无限卡死。
5. 尽力通过 `osascript` 把 OrbStack 加入登录项实现**开机自启**。

**开机自启未生效？** 脚本的 `osascript` 可能因自动化权限被系统拒绝。手动开启：打开 OrbStack → Settings → 勾选 "Start OrbStack at login"（或在 系统设置 → 通用 → 登录项 中确认 OrbStack 已列出）。

### Linux：自动安装 Docker Engine

无 Docker 时，`install.sh` 通过 `get.docker.com` 安装 Docker Engine 并 `systemctl enable --now docker`，同时把当前用户加入 `docker` 组。

> 加入 `docker` 组在**当前 shell 不会立即生效**。安装脚本在本会话内用 `sudo` 调用 docker；要让普通用户免 sudo，请**注销后重新登录**（或立即执行 `newgrp docker`）。

---

## 数据库与启动

### Dashboard / Marketplace 报错，但 Health 全绿

症状：Health 页面四项全绿，但 Dashboard 显示 "Failed to load dashboard data"、Marketplace 显示 "Failed to load marketplace catalog"。

**原因：** 这四个 Health 端点（`/debug/ping-*`）不查数据库，而 Dashboard（`/api/dashboard-stats/`）和 Marketplace（`/api/marketplace/catalog/`）都要查 SQLite。若数据库表未建，DB 端点返回 500，Health 仍正常。

**解决：** Beta2 的容器入口点会在每次启动时自动执行 `python manage.py migrate`，正常情况下无需手动操作。若使用旧镜像或入口点被绕过，手动迁移：

```bash
cd ~/.biocraft-spark            # 仓库安装则 cd 到仓库目录
./install.sh restart            # 重启会触发入口点自动 migrate
# 仍不行则显式执行：
docker compose -f docker-compose.standalone.yml exec web python manage.py migrate
```

> Marketplace 还要求容器能出站访问 `https://biocraft-marketplace.pages.dev`（Cloudflare Pages）。若 migrate 后 Marketplace 仍返回 502 "Marketplace registry unreachable"，检查容器外网连通：
> ```bash
> docker compose -f docker-compose.standalone.yml exec web \
>   curl -sI https://biocraft-marketplace.pages.dev/index.json
> ```

---

## Docker 相关

### `Docker SDK is not installed`

```
DockerUnavailableError: Docker SDK is not installed. Run: pip install docker
```

**原因：** Python 环境中没有安装 Docker SDK。

**解决：**

```bash
pip install docker
```

---

### `Docker daemon is unavailable`

```
DockerUnavailableError: Docker daemon is unavailable. Check Docker socket mount.
```

**原因：** Docker 守护进程未运行，或 socket 未正确挂载。

**解决：**

1. 确认 Docker 在运行：
   ```bash
   docker info
   ```

2. 如果使用 Docker Compose 启动 Biocraft，确认 `docker-compose.yml` 中有 socket 挂载：
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock
   ```

3. 访问 `/debug/ping-docker/` 确认连通性。

---

### macOS：Docker socket 路径不同

不同运行时的 socket 路径不一样：

```
/var/run/docker.sock                       # Docker Desktop / Linux
/Users/<user>/.orbstack/run/docker.sock    # OrbStack
```

`install.sh` 会自动检测并导出 `DOCKER_SOCK`，`docker-compose.yml` 与
`docker-compose.standalone.yml` 都通过 `${DOCKER_SOCK:-/var/run/docker.sock}`
引用，因此**正常情况下无需手动改挂载路径**。

若手动 `docker compose up` 且 socket 不在默认位置，显式指定即可：

```bash
export DOCKER_SOCK="$HOME/.orbstack/run/docker.sock"
docker compose -f docker-compose.standalone.yml up -d
```

---

## 容器执行相关

### 容器超时

```
ContainerTimeoutError: Container exceeded timeout: 3600s
```

**原因：** 容器执行时间超过设定的超时时间（默认 1 小时）。

**解决：**

1. 检查输入数据量是否过大
2. 在插件 YAML 中不需要特殊配置——Biocraft 调度器会自动重试
3. 如果是大型分析任务，可以联系开发者调整默认超时

---

### `Failed to pull image`

```
ContainerRunError: Failed to pull image: biocontainers/prokka:1.14.6
```

**原因：** 镜像拉取失败。

**解决：**

1. 检查网络连接
2. 确认镜像名称和 tag 正确：
   ```bash
   docker pull biocontainers/prokka:1.14.6
   ```
3. 如果是私有镜像仓库，确认已登录：
   ```bash
   docker login
   ```

---

### 容器退出码非零

```
Container exited with code 1
```

**原因：** 工具本身执行失败。

**解决：**

1. 查看 `stderr` 输出定位具体错误
2. 常见原因：
   - 输入文件路径错误（检查是否使用了 `/data/input` / `/data/output`）
   - 输入文件格式不对
   - 工具参数不正确
3. 可以手动跑一次容器来调试：
   ```bash
   docker run --rm -v $(pwd)/data:/data/input biocontainers/prokka:1.14.6 \
     prokka --outdir /data/output /data/input/genome.fasta
   ```

---

## 插件加载相关

### Schema 校验失败

```
jsonschema.exceptions.ValidationError: 'steps' is a required property
```

**原因：** 插件 YAML 格式不符合 Schema 定义。

**解决：**

1. 确认顶层有 `name`、`version`、`steps` 三个必填字段
2. 每个 step 必须有 `name`、`image`、`command`
3. `command` 必须是数组格式，不能是字符串：
   ```yaml
   # ✅ 正确
   command: ["prokka", "--outdir", "/data/output", "/data/input/genome.fasta"]

   # ❌ 错误
   command: "prokka --outdir /data/output /data/input/genome.fasta"
   ```
4. 使用 `/debug/ping-plugin/` 或本地 Python 脚本预校验：
   ```python
   from biocraft_core.plugin import load_plugin
   load_plugin("my-plugin.yaml")
   ```

---

### 循环依赖

```
DAGCycleError: Cycle detected involving: ['step-b', 'step-a']
```

**原因：** 步骤间的 `depends_on` 形成了环。

**解决：** 检查所有 `depends_on` 引用，确保是有向无环图（DAG）。例如：

```yaml
# ❌ 循环依赖
steps:
  - name: step-a
    depends_on: ["step-b"]
  - name: step-b
    depends_on: ["step-a"]
```

---

### 依赖了不存在的步骤

```
MissingDependencyError: Task 'roary' depends on unknown task 'prokka'
```

**原因：** `depends_on` 或 `inputs.from` 引用了不存在的步骤名。

**解决：** 检查步骤名称拼写，确认被引用的步骤在同一个插件 YAML 中定义。

---

### 步骤重名

```
DuplicateTaskError: Duplicate task name: 'step-a'
```

**原因：** 同一个插件内有两个步骤使用了相同的 `name`。

**解决：** 确保每个步骤的 `name` 在插件内唯一。

---

## 调度器相关

### 下游步骤全部 SKIPPED

```
TaskStatus.SKIPPED
```

**原因：** 上游某个步骤失败，导致所有依赖它的下游步骤被跳过。

**解决：** 定位并修复第一个失败的步骤。查看该步骤的 `stderr` 和 `exit_code`。

---

## 诊断端点

开发模式下可以访问以下端点快速定位问题：

| 端点 | 检查内容 |
|---|---|
| `GET /debug/ping-docker/` | Docker socket 连通性 + 容器列表 |
| `GET /debug/ping-executor/` | 能否成功创建并运行一个容器 |
| `GET /debug/ping-scheduler/` | DAG 调度器拓扑排序 + 并行执行 |
| `GET /debug/ping-plugin/` | 插件 YAML 格式校验 |

全部返回 `"ok": true` 说明 Core Runtime 四层都正常。
