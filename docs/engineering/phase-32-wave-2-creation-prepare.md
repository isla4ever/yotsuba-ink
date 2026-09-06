# Phase 32 Wave 32.2：创建准备合同

状态：**本地合同完成；生产项目/Run 切换、Graph 执行和真实 Provider 验收未开始**

日期：2026-08-23

## 产品决定

创建向导先生成一个独立的 Phase 32 preparation，再由后续 Wave 将项目读模型、运行监控和 stage workbench 一起切换到该 Run。当前不把新 Run 直接挂到旧 `ProjectRecord`，也不让旧 `/api/projects` 或 `/api/runs` 读取这批数据。这样可以避免 UI 看不到的孤儿 Run 和两套运行时同时写入同一作品。

## 已实现

- `POST /api/creation-wizard/prepare`：根据 `CreationIntent + WorkflowSelection` 编译官方路线。
- 冻结 `FrozenRouteContract`、`ScaleProfile`、`ReviewPolicy`、输入快照和每个 Provider stage 的 binding。
- 旧工作流模板只作为配置快照来源；新建路线草稿不写旧工作流 Store。
- `Phase32CreationPreparationStore` 先落盘 reservation，再落盘 `GraphRunDefinition`，最后标记 prepared。
- 同一 `idempotency_key` 和相同请求返回原定义；同 key 参数变化返回 409；Run id 冲突且定义不同也返回 409。
- `GET /api/creation-wizard/preparations/{idempotency_key}` 返回可恢复的冻结 Run；中断发生在 reservation 与 Run 写入之间时，下一次相同请求会用原始时间戳和输入重建同一 digest。
- `GET /api/phase32/runs` 与 `GET /api/phase32/runs/{run_id}` 只读动态 Run manifest/read model，向监控台提供真实阶段进度，不暴露 Provider binding，也不改读旧 `/api/runs`。
- `GET /api/phase32/runs/{run_id}/events?after=N` 复用同一 Repository 的游标 SSE 投影；当前 Run 尚未启动时不会伪造进度或事件。
- `Phase32GraphExecutionService` 已建立 step/resume 适配：复用同一 LangGraph checkpointer，遇到 decision interrupt 会把 `awaiting_decision`、pending decision 和 checkpoint 原子投影回 native Run；Provider driver 仍由后续 Wave 注入。

## 验证证据

- Phase 32 创建准备定向测试：7 passed。
- 后端全量离线测试：943 passed，1 warning（Starlette/httpx 依赖弃用提示）。
- 前端 Vitest：32 passed；production build、结构审计、CSS 审计和 CSS 构建检查通过。

## 未关闭门

- 仍未把创建按钮切到本接口；旧 Project/Run 主链保持不变。
- 仍未通过生产 API 从 Phase 32 Run 启动 LangGraph、Provider gateway、SSE 监控或真实项目主读模型。
- 当前只完成可注入 driver 的图执行适配和测试，尚未把它挂到生产启动 API，也未调用真实 Provider。
- 未进行真实 Provider、成本、长篇连续性、浏览器全链路或 GitHub 发布验收。
