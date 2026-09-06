# Phase 32 Wave 32.3：Artifact 存储与路线驱动

状态：**本地合同与 fake Provider 生命周期完成；生产启动 API、真实 Provider 和前端主链切换未开始**

日期：2026-08-23

## 本轮边界

本轮只建立 Phase 32 图执行可以注入的 Provider/Artifact 边界，不改变旧项目/Run 主链，也不从 API 触发真实模型调用。三条路线继续共享 `route_graph.py` 的生命周期子图，差异来自已冻结的 route manifest 与 Artifact binding。

## 已实现

- `Phase32ArtifactStore`：按 Run 隔离的内容寻址 JSON 存储。
- candidate 与 committed 两种不可变记录；候选稿可幂等提交，payload digest、route/stage/kind 绑定会在写入和读取时再次校验。
- `Phase32ProviderRequest` / `Phase32ProviderResponse`：只暴露冻结 binding、阶段合同、输入快照和已提交上游引用。
- `Phase32RouteDriver`：
  - Provider 阶段只调用注入的 `Phase32ProviderGateway`；
  - 返回 payload 必须解析为当前路线/阶段的 Pydantic Artifact；
  - candidate 写入后才能进入图的 validate/decision；
  - 非导出阶段只能提交 candidate；
  - `export` 不绑定 Provider，而是从已提交阶段聚合确定性交付 Artifact。
- 三条路线的 fake Provider 生命周期测试覆盖：
  - 剧本样片：brief、cast、beat board、scene deck、script、export；
  - 短中篇：brief、story map、cast、section plan、text、cover、export；
  - 长篇：brief、book architecture、cast、volumes、rolling detail、text、cover、export。

## 验证证据

- Artifact store 定向测试：4 passed。
- Route driver 定向测试：10 passed（含三条路线图执行、decision resume 与 export）。
- 后端全量测试：957 passed，1 个既有 Starlette/httpx 弃用 warning。
- `compileall`、`git diff --check` 通过。

## 仍未关闭的门

- `Phase32RouteDriver` 尚未注册到生产 bootstrap 或 `POST /api/phase32/runs/{run_id}/start`；当前没有任何真实 Provider 请求路径。
- Provider receipt、usage、Outbox/writeback、durable LangGraph checkpointer 生命周期和前端运行监控切换仍需单独 Wave 验证。
- 没有进行真实 Provider 成本/余额、长篇连续性、文学质量、浏览器交互或 GitHub 发布验收。
