# Phase 32 Wave 16：成本投影一致性合同

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

Wave 15 已把成本投影暴露给监控 API，但仅有字段存在性还不足以证明监控可信。本轮为 receipt、provider/model breakdown 和 Run usage summary 增加确定性一致性门。

## 合同

- `cost_status=known` 必须同时存在 `estimated_cost_usd`；存在成本值时不能标成 `unknown`。
- `Phase32ProviderUsageSummary.provider_operations` 必须等于 `by_provider.operations` 之和。
- 总成本为 `known` 时，所有 provider 分组都必须为 `known`，且分组成本之和必须等于总成本。
- 任一 provider 分组出现 `insufficient`，Run 级余额状态必须显式呈现 `insufficient`。
- 不改变旧 `ProviderUsageSummary` 和旧 runtime 的历史精确合同。

## 验证

新增 3 条拒绝测试，覆盖 breakdown 数量漂移、成本总额漂移和 receipt 状态漂移。定向成本/API/receipt 测试 `30 passed`；全量后端回归 `1001 passed`，另有 1 个既有 Starlette/httpx 弃用告警；`compileall` 与 `git diff --check` 通过。

## 下一道门

离线合同已经具备进入真实 Provider 小门的条件，但真实调用、余额查询、账单对账和生产 bootstrap 仍需单独授权；不得把本地估算当成 Provider 账单事实。
