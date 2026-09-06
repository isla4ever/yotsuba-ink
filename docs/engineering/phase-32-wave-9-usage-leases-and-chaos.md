# Phase 32 Wave 32.9：Usage Projection、Operation Lease 与混沌恢复

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

补齐 Provider receipt 在跨进程和运行监控上的两个底层缺口：同一 pending operation 不能被两个进程同时拿去调用 Provider；Provider usage 不能停留在 receipt 文件里而不进入 Phase 32 Run read model。

本轮仍不复用旧 runtime、不注册 HTTP、不切换 bootstrap、不调用真实 Provider。

## Operation lease

`Phase32ProviderOperationStore` 现在为每个 operation 使用独立 POSIX file lock（`<operation-root>/.locks/`）包住 receipt 状态转换。线程锁只负责进程内互斥，file lock 负责多个进程之间的 `begin/claim/return/succeed/reject` 竞争。

新增 receipt sidecar 字段：

- `lease_owner`：当前调用进程的短期身份；
- `lease_expires_at`：UTC 过期时间；
- `transport_attempts`：传输调用次数。

Provider 调用前必须先 `claim_pending`。有效租约会拒绝其他 owner；进程崩溃后租约过期即可被新进程回收。正常 transport exception 通过 `release_pending` 清除租约并保留 `pending`，默认最多 3 次传输尝试；达到上限后抛出 `Phase32ProviderOperationRetryExhausted`，不再隐式烧 token。返回 payload 后租约立即清除，解析/合同失败仍进入 `contract_rejected`，不会转成 transport retry。

## Usage read model

`Phase32ProviderOperationStore.usage_summary()` 从 durable receipts 重建 Provider 操作数、返回/成功/合同拒绝/pending 数量，以及 prompt/completion/total/reasoning tokens。`Phase32GraphExecutionService` 在每次图步骤提交 read model 时，从注入 driver 的 operation store 投影 `RouteRunReadModel.provider_usage`；没有 Phase 32 receipt store 的 fake driver 保留原有 usage，不伪造数字。

Provider usage 统一经过 `normalize_provider_usage`，当 Provider 只返回 prompt/completion 时确定性补齐 `total_tokens`。

## 混沌测试证据

新增 `tests/test_phase32_provider_operation_leases.py`，覆盖：

- 两个独立 store 实例争抢同一 operation 时只有一个 lease owner；
- 租约过期后的跨进程恢复；
- 最大 transport attempt 限制；
- receipt usage 汇总；
- gateway 中断后释放租约、同 operation 重试并递增 attempt；
- usage 投影到真实 Phase 32 Run read model。

定向验证：`4 passed`（本轮混沌/usage/lease）。此前 Phase 32 receipt/driver 定向验证保持通过；全量回归需在本轮改动稳定后重新执行。

## 下一道门

继续处理真实运行失败到 Run read model 的 failure/pending projection、Provider lease 的进程中断 replay，以及跨进程 checkpoint/Run execution lock；通过 fake gateway 与新鲜离线全量回归后，才申请真实 Provider 小门。
