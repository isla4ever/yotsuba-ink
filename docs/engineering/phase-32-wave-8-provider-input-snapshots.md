# Phase 32 Wave 32.8：Provider Input Snapshot

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

把 Phase 32 Provider 调用前的冻结输入提升为独立、可重启验证的 sidecar。Operation receipt 只保存“这次调用处于什么状态”，输入快照保存“当时究竟把什么内容发给 Provider”。两者必须绑定，才能避免进程重启后使用漂移的上下文、错误的流水线配置或被篡改的请求继续恢复。

本轮不复用旧 `ProviderInputStore`，不修改旧 runtime，不注册 HTTP，不调用真实 Provider。

## 输入快照合同

`Phase32ProviderInputStore` 位于 `storage/phase32_provider_input_store.py`。每个快照绑定：

- `run_id`、`operation_key`、`stage_id`；
- 完整的 secret-free `Phase32ProviderRequest` JSON；
- 由冻结 request canonical JSON 推导的 SHA-256 `request_signature`；
- 内容寻址的 `provider_input_ref`：`p32-provider-input-{request_signature}`。

写入前递归拒绝 `api_key`、authorization、headers、secret、token、credential 等敏感字段，不尝试把凭据“清洗后”落盘。写入采用深拷贝，快照文件不可变；读取会重新计算 request digest、校验 ref、校验请求身份，并拒绝篡改或悬空引用。

## Receipt 绑定与恢复

`Phase32ProviderOperationReceipt` 新增 `provider_input_ref`（并提供 `input_snapshot_ref` 只读别名）。`Phase32RouteDriver` 在 gateway 调用前按以下顺序执行：

1. 构造冻结 `Phase32ProviderRequest` 并计算 request signature；
2. 写入或恢复输入快照；
3. 创建/读取带 snapshot ref 的 operation receipt；
4. 只有 `pending` 才调用 gateway；`returned`/`succeeded` 直接走持久化恢复路径。

带快照的 receipt 在读取时会验证 snapshot 存在、request signature、operation key 和 stage identity。快照缺失、篡改或与 receipt 不匹配都会转换成 receipt conflict，阻断继续执行，而不是静默触发新的 Provider 调用。低层 receipt fixture 仍可不绑定快照以保持归档/测试工具的读取兼容；生产 `Phase32RouteDriver` 始终绑定快照。

## 测试证据

新增 `tests/test_phase32_provider_input_snapshot.py`，覆盖：

- 快照内容寻址、重复写入幂等与篡改拒绝；
- secret/header/access token 等字段拒绝落盘；
- receipt 读取时缺失快照阻断；
- 同 operation 使用不同 request/context signature 被拒绝。

定向验证：`25 passed`（快照、receipt、driver）。全量回归：`984 passed`，另有 1 个既有 Starlette/httpx 弃用 warning。真实 Provider、成本/余额、跨进程锁与生产 bootstrap 仍未验收。

## 下一道门

继续补齐 usage/read model、跨进程锁与 pending 超时/租约策略，再用 fake gateway 做进程中断、重复回调、乱序返回和坏包混沌测试。通过这些离线门后，才申请新鲜真实 Provider 小门。
