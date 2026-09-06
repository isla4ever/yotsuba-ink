# Phase 32 Wave 32.11：Failure Event 与 SSE/Read Model 一致性

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

把执行失败从“只在 HTTP 异常里存在”提升为可重放的 Run 事件，并让监控 read model、事件分页和 SSE terminal 语义保持一致。失败仍然是 sidecar，不进入核心 Artifact。

## Failure event

`RouteRunEventType` 新增 `stage.failed`，用于没有 active unit 的阶段失败；已有 `unit.failed` 继续用于有界 unit 失败。`Phase32RunExecutionService` 在 failure projection 成功后追加带 route identity、stage、node、code、retryable 和截断 message 的失败事件：

- transport timeout/连接错误：`retryable=true`，Run state 保持 `running`；
- Provider lease busy：可重试；
- 合同拒绝或 retry limit：`retryable=false`；
- 事件 sequence、Run definition digest 和 stage identity 由 Repository 统一校验。

失败事件不会携带 Provider 原始 payload、secret 或完整异常堆栈。

## SSE terminal 语义

`Phase32EventProjection` 将 `stage.failed` 与 `unit.failed` 视为当前事件页的 terminal；下一次 `stage.started` 会清除 terminal，允许客户端继续订阅恢复后的事件。这样监控台可以在失败时停止刷新，用户显式重试后又从新的 stage.started 继续收到事件，而不需要本地猜测状态。

## Journal / checkpoint 边界

本轮复用既有 `Phase32RunRepository` projection journal 和 `open_phase32_checkpointer` 的 SQLite busy-timeout/setup retry。Wave 10 的 Run execution file lock 保证 start/resume 不会同时写同一个 projection/checkpoint；既有 journal replay 与 SQLite reopen 测试继续作为恢复门，不新增第二套 checkpoint 存储。

## 测试证据

扩展 `tests/test_phase32_execution_failure_lock.py`，覆盖：

- failure read model 与 `stage.failed` 事件同时出现；
- 事件 payload 不泄露 raw Provider 内容；
- failure event page 为 terminal；
- 重试后的 `stage.started`/`decision.required` 可继续被 SSE event projection 消费。

本轮定向验证：`2 passed`。此前 Wave 32.10 定向回归保持通过；全量回归需在本轮稳定后执行。

## 下一道门

下一步补真实的进程中断恢复演练：在 projection journal 写入、SQLite checkpoint 写入和 failure event append 的不同切点终止进程，再用新进程验证 state/read model/event sequence 能恢复到同一个 durable frontier。之后再进入 Provider 成本/余额门。
