# Phase 32 Wave 32.12：Projection Journal 与 Event Replay

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

消除 failure read model 与 failure event 分两次提交造成的进程中断窗口。Projection journal 现在可以同时保存 state、read model 和一个待追加的 route event；新进程读取 Run 时会按同一 journal 恢复三者。

## 原子恢复边界

`Phase32RunRepository.commit_projection_with_event()` 复用既有 projection journal：

1. 校验 state/read model/event 都属于同一冻结 definition，并校验 event sequence；
2. 将 state、read model 和可选 event 一起写入 journal；
3. 替换 state/read model 文件；
4. 追加 event 并 `flush/fsync`；
5. 最后删除 journal 和 staging 目录。

进程可以在步骤 3、4、5 任意位置退出：

- event 尚未写入：下次 `repository.read()` 从 journal 补写；
- event 已写入但 journal 未清理：下次恢复通过 event idempotency 识别已有事件，不重复追加，再清理 journal；
- state/read model 已替换：恢复仍以 journal 中的成对 payload 为准。

Failure projection 已改为通过该方法提交，因此监控 read model 与 SSE failure event 共享同一个 durable recovery frontier。

## 测试证据

扩展 `tests/test_phase32_run_repository.py`，模拟 failure event append 后进程中断，验证新实例读取后：

- state 与 read model 恢复到同一版本；
- failure event 恰好存在一次；
- event sequence 连续；
- projection journal 被清理。

本轮定向验证：`13 passed`（repository journal、failure projection、event projection）。全量回归需在本轮稳定后执行。

## 下一道门

继续用独立进程演练 SQLite checkpoint 写入、projection journal 恢复和 SSE cursor replay；随后核对 Provider 成本/余额 sidecar 与 Run read model 的一致性，再申请真实 Provider 小门。
