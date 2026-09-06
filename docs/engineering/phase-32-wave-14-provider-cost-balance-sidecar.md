# Phase 32 Wave 14：Provider 成本与余额旁路

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 目标

在不引入旧 runtime、实时价格查询或真实 Provider 调用的前提下，把一次 Phase 32 Run 的 Provider 成本和余额状态纳入可恢复的监控 read model。成本必须来自 Run 创建时冻结的 pricing snapshot；缺少价格时保持 `unknown`，不能用 `0` 代替未知。

## 合同

- `ProviderProfile` 可提供可选的输入/输出 token 单价，以及兼容旧配置的固定单次输出估算。
- `phase32_provider_binding.py` 在冻结阶段写入 `pricing_snapshot`，快照包含 provider profile/template、model、USD 单价和内容寻址引用。
- `Phase32ProviderOperationReceipt` 保存 provider/model 标识、pricing snapshot ref、usage、estimated cost、cost status 和 balance status。
- `Phase32ProviderOperationStore.usage_summary()` 从 receipts 重建总量和 `by_provider` 分组，不依赖内存或前端状态。
- 余额状态只接受公开错误码：成功调用不推断实时余额，Provider 明确返回 `insufficient_balance` 时记录 `insufficient`；不会保存 API Key、headers 或原始错误 body。
- 同一 operation 的 provider/model/pricing ref 发生漂移时拒绝恢复，避免重启后把一次请求按新价格重算。

## 变更边界

保留旧 `ProviderUsageSummary` 和 `OperationStore`，避免改变历史 runtime 的精确投影合同。Phase 32 使用独立 `Phase32ProviderUsageSummary`，由 `RouteRunReadModel` 消费；这仍是 sidecar，不进入核心文学 Artifact、Canon、Evidence 或 checkpoint State。

## 验证

新增 `tests/test_phase32_provider_cost_sidecar.py`，覆盖：

1. 内容寻址的定价快照和 token 计算；
2. 无价格时 `unknown` 且不伪造零成本；
3. receipt 持久化成本并在重建 summary 时按 provider/model 分组；
4. 同 operation 的定价快照漂移拒绝；
5. 余额不足只投影公开状态且不落盘凭证。

本轮定向验证：成本 sidecar 与 Phase 32 receipt/graph/repository 测试共 `36 passed`。真实 Provider 余额查询、账单对账和生产 bootstrap 注册仍属于后续成本门，不能由本轮离线 fake Provider 证据替代。

## 下一道门

在用户明确授权真实 Provider 成本门后，使用新 Run 做一次小额度端到端验证：核对 Provider 返回 usage、receipt、SSE/read model 和账单侧数据；任何价格或余额不确定性都必须显示为未知并停止自动推断。
