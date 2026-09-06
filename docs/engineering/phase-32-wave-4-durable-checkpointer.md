# Phase 32 Wave 32.4：Durable Checkpointer 生命周期

状态：**本地 durable/fake Provider 恢复完成；生产启动 API、真实 Provider 和前端主链切换未开始**

日期：2026-08-23

## 本轮边界

本轮只解决 LangGraph checkpoint 的连接、schema 初始化、关闭和重新打开语义，不注册 Phase 32 start/resume API，也不改变 Provider 调用策略。旧 NarrativeRuntime 与 dormant Phase 32 runtime 共享同一套 SQLite 生命周期 helper，但仍使用各自的数据根目录和业务状态合同。

## 已实现

- 新增 `runtime/graph/checkpoint_lifecycle.py`：统一处理 `AsyncSqliteSaver` 的目录创建、schema 检查、busy timeout、锁竞争退避和 context 关闭。
- 旧 `open_sqlite_runtime()` 改为复用该 helper，移除重复的私有 schema 初始化实现。
- 新增 dormant `runtime/graph/phase32_checkpointer.py`：Phase 32 只使用显式 `phase32/checkpoints.sqlite` namespace。
- 用 `Phase32GraphExecutionService + Phase32RouteDriver + fake gateway` 验证：
  - 首次执行在 mandatory decision 中断；
  - context 关闭后重新打开同一 SQLite 文件；
  - 新 Repository 实例从同一 Run/thread 恢复；
  - 继续接受决策并完成短中篇全路线导出。

## 验证证据

- durable 恢复定向测试：1 passed。
- 旧 SQLite runtime/协作恢复定向测试：1 passed。
- Wave 32.3 的三路线 fake lifecycle 与 Artifact store 测试继续通过。

## 仍未关闭的门

- 没有生产 `start/resume` API、运行任务生命周期管理、Provider receipt/usage/outbox 或前端运行监控切换。
- 没有真实 Provider、成本/余额、长篇连续性、文学质量、浏览器或 GitHub 发布验收。
