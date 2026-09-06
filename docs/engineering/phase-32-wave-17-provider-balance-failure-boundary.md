# Phase 32 Wave 17：Provider 余额失败边界

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

验证规范化 Provider 余额错误从 gateway 到 receipt 的最低责任链：driver 可以保留可重试的 pending operation，同时只向监控投影公开的 `insufficient_balance` 状态，不保存上游错误正文。

## 验证路径

fake gateway 抛出 `ProviderResponseError(code="insufficient_balance")`，Phase32 driver：

1. 使用同一个 operation identity 写入 pending receipt；
2. 释放 lease 并保存公开 diagnostic code；
3. 将余额状态投影为 `insufficient`；
4. 不写入 raw Provider payload、API Key、headers 或错误正文。

新增测试位于 `tests/test_phase32_provider_cost_sidecar.py`，覆盖真实 driver 边界而非只测 store helper。

## 结果

全量回归 `1002 passed`，1 个既有 Starlette/httpx 弃用告警；`compileall` 与 `git diff --check` 通过。真实 Provider 余额响应、账单对账和生产注册仍未执行。

## 下一道门

只有在用户明确授权后，才创建全新 Run 进入真实 Provider 小额度成本门；本轮不恢复历史 Run、不启动生产主链。
