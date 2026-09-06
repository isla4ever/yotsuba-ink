# Phase 32 Wave 32.6：执行 API 适配层

状态：**HTTP adapter 合同完成但保持 dormant；bootstrap 注册、真实 Provider 和前端主链切换未开始**

日期：2026-08-23

## 本轮边界

本轮只定义 start/resume 的 HTTP 请求、响应和错误映射。路由依赖 `Phase32RunExecutionService`，不读取旧 `/api/runs`，不暴露 Provider binding，也未加入 `routes/__init__.py` 或 `app.py`，因此不会形成第二条生产执行入口。

## 已实现

- `api/routes/phase32_execution.py`：
  - `POST /api/phase32/runs/{run_id}/start`；
  - `POST /api/phase32/runs/{run_id}/resume`；
  - 返回动态 route read model、当前 graph decision 和 `reused` 标志；
  - 未注册 execution service 返回明确的 `503 phase32_execution_unavailable`；
  - Run 不存在、决策冲突、执行合同错误分别映射为 404/409/422。
- `tests/test_phase32_execution_api.py`：使用实际 Phase 32 orchestration service、durable checkpointer 和 fake driver 验证 start/resume、重复决策、unknown Run 和未配置进程。

## 验证证据

- HTTP adapter 定向测试：2 passed。
- `compileall`、结构边界和 `git diff --check` 继续通过。

## 仍未关闭的门

- 路由尚未注册到生产 bootstrap；当前生产仍只有旧 `/api/runs` 执行入口和 Phase 32 只读投影入口。
- 尚未绑定真实 Provider gateway、Provider receipt/usage、Outbox/writeback、任务取消/超时或跨进程 leader/锁语义。
- 没有真实 Provider、成本/余额、长篇连续性、文学质量、浏览器或 GitHub 发布验收。
