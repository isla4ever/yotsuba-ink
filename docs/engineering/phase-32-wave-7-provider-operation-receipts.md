# Phase 32 Wave 32.7：Provider Operation Receipt

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

把一次冻结 Provider 请求的恢复边界从“内存中的驱动调用”提升为独立、可重放的 Phase 32 receipt。网络传输失败、Provider 已返回但进程退出、Artifact 合同拒绝和成功候选必须拥有不同的状态，不能把它们混成同一种重试。

本轮不复用旧 `OperationStore`，不修改旧 runtime，不注册 HTTP，不调用真实 Provider。

## Receipt 合同

`Phase32ProviderOperationStore` 位于 `storage/phase32_provider_operation_store.py`，只服务 Phase 32 route runtime。每条 receipt 至少绑定：

- `run_id`、`operation_key`、`stage_id`；
- 冻结 `Phase32ProviderRequest` 的 SHA-256 `request_signature`；
- Provider 原始 payload、usage、diagnostic；
- 成功时的候选 `artifact_ref` 与 `unit_ref` 结果。

状态机为：

```text
pending -> returned -> succeeded
                    \-> contract_rejected
```

- `pending`：调用前创建；网络/传输异常保留该状态，同一 operation 可以有界重试。
- `returned`：Provider 返回后先落盘 raw payload，再做 Artifact 解析；进程重启可从该状态继续。
- `succeeded`：Artifact 合同解析、候选持久化和 unit ref 校验均成功；同一 operation 直接恢复候选，不再调用 gateway。
- `contract_rejected`：返回内容无法满足路线 Artifact 合同或 Provider envelope 合同；状态不可伪装成传输重试，同一 operation 后续只返回拒绝，新的文学方向必须生成新的 operation identity。

同一 `operation_key` 复用不同 `request_signature` 会被拒绝。成功、返回和合同拒绝的 receipt 内容寻址且不可篡改；原始 Provider payload 不拥有 Artifact ID、顺序、hash、状态或写回元数据的权威性。

## 驱动恢复语义

`Phase32RouteDriver.generate_stage` 现在按以下顺序工作：

1. 从冻结 request 计算签名并创建/读取 receipt；
2. 已成功时校验 receipt 指向的 candidate Artifact 并直接恢复；
3. `pending` 才调用 gateway；返回 envelope 先持久化为 `returned`；
4. 从 `returned` 解析并绑定路线 Artifact，成功后保存 candidate 并标记 `succeeded`；
5. 解析失败标记 `contract_rejected`，不自动换 Provider、不隐式扩大重试次数。

Artifact Store 仍然是 candidate/committed 核心 Artifact 的唯一持久化边界，Provider receipt 只是 sidecar；Export 仍为确定性聚合，不调用 Provider。

## 测试证据

新增 `tests/test_phase32_provider_operation_receipt.py`，覆盖：

- 相同 operation 成功重试不重复调用 gateway；
- 新驱动实例从 durable receipt 恢复候选；
- operation key 复用不同 request signature 被拒绝；
- malformed Artifact payload 与 malformed Provider envelope 均记录为 `contract_rejected`；
- transport timeout 保留 `pending` 并允许同一 operation 重试。

定向验证：`17 passed`（含原 Phase 32 driver 测试）。全量回归：`969 passed`，另有 1 个既有 Starlette/httpx 弃用 warning。真实 Provider、成本/余额、长篇文学质量和生产 bootstrap 仍未验收。

## 下一道门

接入前仍需完成 Provider input/context receipt、usage read model、跨进程锁/超时策略与 fake gateway 的混沌恢复测试；只有 receipt、成本边界、恢复语义和 fake gate 一起通过，才可申请真实 Provider 小门。
