# Biocraft-Spark

<aside>
ℹ️

**Biocraft‑Spark** — 本地运行、跨平台、面向初学者的生物信息学工作台。用 GUI + 容器化技术隐藏环境复杂度，让不会 Linux 的用户也能完成专业级分析。当前主线选择 Django 框架，优先打通核心工作流与插件生态；未来 Cloud 版本会重新回到 Rust 构建，并在 Dioxus 发布 1.0 后评估采用。

**Team:** Divinity Studio

</aside>

## 🎯 Goals

- [x]  完成 Core Runtime（容器执行 ✅ · DAG Scheduler ✅ · v0.1 重试 + 插件格式 ✅）
- [ ]  搭建 Django 主线框架与基础界面（已创建 Django 项目骨架，进入实现阶段）
- [ ]  实现 Prokka + Roary Pipeline
- [ ]  发布插件 SDK & 官方插件
- [ ]  建立插件市场
- [ ]  商业化准备（Biocraft‑Business）

---

## 🧠 架构速览

**核心理念：** 降低生信门槛，统一工具生态，本地运行保障数据安全

**四层架构：** Core Runtime → Django App Layer → Plugin Layer → Data Layer

**技术选型：** Django 主框架 • Python 后端 • Docker/Podman 容器 • DAG 调度 • 未来 Cloud：Rust + Dioxus（待 1.0）

**插件三类型：** Tool Adapter → Pipeline → Analysis & Visualization

---

## 📌 重要文档

[Biocraft‑Advanced：完整方案（2025 版）](https://app.notion.com/p/Biocraft-Advanced-2025-1cbb4ab8c7db4cf9bff58d9fab43ad8d?pvs=21)

---

## 🛣️ Roadmap

- **Phase 1 — Core Runtime：** 1 个月（容器执行器 + DAG 调度器 + 插件格式）
- **Phase 2 — Django UI & Pipeline：** 1–2 个月（Django 主线框架 + Pipeline Builder）
- **Phase 3 — 插件生态：** 2 个月（插件 SDK + 官方插件 + 插件市场）
- **Phase 4 — Cloud / 商业化：** 远程执行 + 任务队列 + 企业权限；Cloud 版本回到 Rust 构建，视 Dioxus 1.0 生态成熟度决定前端方案

## 📝 Progress Log

- **2026-05-02：** Django 项目骨架已创建，项目正式进入实现阶段；下一步从 `workbench` 首页入口开始接入 Django 主线。
- **2026-05-02：** 新增 Docker 化任务：先把 Django 项目放入容器运行，建立后续 Core Runtime 容器执行能力的基础。
- **2026-05-02：** 新增 JetBrains IDE 一键运行任务：在 PyCharm / IntelliJ 中配置 Run/Debug Configuration，一键启动 Docker 化后的 Django 服务。
- **2026-05-02：** 修正容器方案为 Docker out of Docker：Django 容器通过挂载 OrbStack / Docker socket 调度宿主机容器，而不是单纯配置网络代理。
- **2026-05-02：** Docker out of Docker 连通性验证完成：`/docker-ping` 可返回 `{"docker": true}` 与容器列表；同时完成懒加载 Docker SDK、`setuptools>=80.0.0` 兼容修复与 `workbench` 测试覆盖。
- **2026-05-04：** 开始封装 Core Runtime 的 Container Executor：确定放置在独立 `biocraft_core/runtime/executor/` 包，拆分 `types.py`、`errors.py`、`docker_executor.py` 与统一导出层；下一步接入 `/executor-ping/` 验证接口，并作为 DAG 调度器的底层执行抽象。
- **2026-05-04：** Container Executor v0 验证通过：`/executor-ping/` 成功返回 HTTP 200，执行 `python:3.12-slim` 容器并输出 `Biocraft executor online`；Core Runtime 已从 Docker socket 连通升级为可运行容器任务的执行抽象。
- **2026-05-04：** 启动 DAG Scheduler v0 设计：在 `biocraft_core/runtime/scheduler/` 下拆分 `types.py` / `errors.py` / `dag.py` / `engine.py`，以 Container Executor 为节点执行单元。v0 范围聚焦最小闭环（拓扑排序 + 并行波次执行，暂不做重试与持久化）；验证接口 `/scheduler-ping/` 跑 3 节点 DAG（A → B、A → C）以确认顺序与并行度。Phase 1 状态推进至 In progress（Container Executor → Halfway done，DAG Scheduler → In progress）。后续 v0.1 接入失败传播与重试，v0.2 接入状态持久化。
- **2026-05-04：** DAG Scheduler v0 验证通过：`/debug/ping-scheduler` 返回 `succeeded: true`，3 节点 DAG（A → B、A → C）依赖顺序与同层并行度均符合预期，A/B/C 均 `exit_code: 0`。同步完成调试接口规整：所有 ping 接口收敛到 `/debug/` 命名空间（`ping-docker` / `ping-executor` / `ping-scheduler`），保留旧 reverse 名称以兼容现有代码与测试。Phase 1 三大件中两件（容器执行器、DAG 调度器）已打通最小闭环，下一步进入 v0.1（失败传播 + 重试策略）与插件格式（YAML + JSON Schema）定义。
- **2026-06-20：** Core Runtime v0.1 完成。实现重试策略（新增 `RetryPolicy`、支持 `delay_seconds` 等待以及耗尽后的失败传播逻辑）；定义基于 YAML + JSON Schema 的插件格式，提供 Schema 校验及加载器（`biocraft_core/plugin/`）；新增 `/debug/ping-plugin/` 验证接口实现对插件 YAML 的解析及拓扑顺序的格式验证。Core Runtime 目标三阶段（容器执行 ✅ / DAG 调度 ✅ / v0.1 重试与插件格式 ✅）均已顺利完成。

## 🛠 Project Phases

[Project Phases✨](Biocraft-Spark/Project%20Phases%E2%9C%A8%205291ce4b607282649b0b81c1482bd3a3.csv)

---

## ⚙ Task Details

[Phase Task Details✨](Biocraft-Spark/Phase%20Task%20Details%E2%9C%A8%20b3e1ce4b607283df96fe81bdc560b650.csv)