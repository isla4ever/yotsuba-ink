# Phase 32 Wave 32.5：Start/Resume 编排与决策收据

状态：**本地 orchestration/fake Provider 合同完成；生产 API、真实 Provider 和前端主链切换未开始**

日期：2026-08-23

## 本轮边界

本轮没有注册 HTTP 入口，也没有把 Provider gateway 接进 bootstrap。新增服务只在注入 fake driver 与 durable checkpointer 时执行，用于先锁定 start/resume、重放和决策幂等语义。

## 已实现

- `Phase32DecisionReceiptStore`：独立于旧 `OperationStore` 的 Phase 32 决策收据命名空间。
- 收据绑定 `run_id + operation_key + decision_id + command signature`；同一命令幂等，复用 operation key 但修改命令会拒绝。
- `Phase32RunExecutionService.start()`：
  - created/running Run 执行一个 graph step；
  - awaiting/completed/cancelled Run 返回现有 durable frontier，不重复启动；
  - failed Run 必须走显式恢复路径。
- `Phase32RunExecutionService.resume()`：
  - 只接受当前 read model 中的 pending decision；
  - 通过同一 SQLite checkpoint 恢复图；
  - graph 成功后写 succeeded receipt；
  - 进程在 graph 写入后、receipt 完成前中断时，下一次请求可根据已消失的 decision 做 deterministic reconciliation。
- 每个 Run 在单进程内使用 async lock 串行化 start/resume，避免同一决策的并发重复推进。

## 验证证据

- 决策收据存储和命令冲突测试：1 passed。
- start/resume、重复决策、awaiting 幂等测试：2 passed。
- 现有 Phase 32 durable/fake lifecycle 与旧 runtime 回归继续通过。

## 仍未关闭的门

- 尚未把该服务注册到 `bootstrap.py` 或 `/api/phase32/runs/{run_id}/start|resume`。
- Provider receipt、usage、Outbox/writeback、任务取消/超时、跨进程 leader/锁语义仍未完成。
- 没有真实 Provider、成本/余额、长篇连续性、文学质量、浏览器或 GitHub 发布验收。
