# Phase 32 Wave 32.10：Failure Projection 与 Run Execution Lock

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

让 Provider/Graph 失败在运行监控中有稳定、可恢复的投影，同时阻止多个进程并发推进同一个 Phase 32 Run。失败信息属于 read model sidecar，不污染核心 Artifact，也不把可重试 transport 中断伪装成永久 Run failed。

## Failure projection

`Phase32RunExecutionService._step` 捕获图执行异常后，会从根因识别 transport timeout、连接错误、Provider lease busy、合同拒绝和其他执行错误，并将：

- `RunFailureProjection.code`；
- 当前 `stage_id`；
- `retryable`；
- 截断到 2,000 字符的 message；
- durable Provider usage；

原子提交到 `RouteRunReadModel`。可重试 transport 失败保持 Run state 为 `running`，下一次显式 `start` 可以重试同一个 operation；成功后正常图投影会清除旧 failure。确定性合同错误会显示为不可重试 failure，避免 UI 把它误认为网络波动。

## Run execution lock

新增 `storage/phase32_execution_lock.py`。`Phase32RunExecutionService.start/resume` 同时使用进程内 `asyncio.Lock` 和每个 Run 独立的 POSIX advisory file lock。文件锁采用非阻塞轮询，不阻塞事件循环；等待超过配置的 timeout 会返回 `phase32_execution_lock_timeout` 冲突。这样两个服务进程无法同时操作一个 LangGraph thread、checkpoint 和 Run projection。

锁只保护 start/resume 生命周期，不拥有 Provider receipt 状态；Provider operation 仍由自己的跨进程 lease 负责。两层边界分别解决 Run 编排互斥和 Provider 调用互斥。

## 测试证据

新增 `tests/test_phase32_execution_failure_lock.py`，覆盖：

- transport 中断写入可重试 failure 和 pending usage；
- 下一次 start 清除 failure 并恢复到 decision interrupt；
- 两个独立执行服务争抢同一 Run 时，第二个服务收到 lock timeout；
- 第一服务释放锁后正常完成当前步骤。

本轮定向测试：`2 passed`。此前 Wave 32.9 定向测试保持通过；全量回归需在本轮改动稳定后执行。

## 下一道门

继续补进程中断后的 checkpoint/repository journal replay、失败事件与 SSE read model 一致性，以及真实 Provider 调用前的成本/余额 read model。通过 fake gateway、跨进程重启和全量离线门后，才申请真实 Provider 小门。
