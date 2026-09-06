# Phase 32 Wave 15：监控成本投影与边界收口

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮问题

Wave 14 已把成本写入 Phase 32 receipt 和 read model，但 `Phase32ProviderOperationStore` 同时承担 receipt 生命周期和 usage/cost 聚合，文件膨胀到 736 行，违反了存储与 usage 责任边界。API 虽然已经序列化 read model，却缺少一条测试证明监控读接口能看到成本旁路，同时不会泄露冻结 Provider binding。

## 变更

- 新增 `src/novel_workflow/usage/phase32_provider_usage.py`，只负责从 receipt-shaped records 重建 token、成本、余额和 provider/model 分组投影。
- `Phase32ProviderOperationStore` 保留 begin/lease/return/succeed/reject/read/list 等持久化生命周期，`usage_summary()` 委托给 usage 域包。
- 新增 API 合同测试，验证 `/api/phase32/runs/{run_id}` 和列表投影能返回成本/余额字段及 `by_provider`，同时不返回 `provider_bindings_by_stage`。

## 退出门

定向测试 `27 passed`；`compileall` 和 `git diff --check` 通过。全量回归需在本轮最终改动稳定后运行。真实 Provider、实时余额查询和账单对账仍未授权。

## 下一道门

完成全量离线回归后，若用户单独授权真实 Provider 成本门，再创建全新 Run 做最小调用数验证。不得恢复历史 Run 或把本地估算当作账单事实。
