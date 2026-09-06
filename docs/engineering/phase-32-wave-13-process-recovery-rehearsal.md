# Phase 32 Wave 32.13：独立进程恢复演练

状态：**dormant 能力完成；未注册生产 bootstrap、未接真实 Provider、未切换旧 Run 主链**

日期：2026-08-23

## 本轮目标

把“重新打开 context 可以恢复”提升为真实子进程边界验证：子进程在 SQLite checkpoint context 尚未关闭时直接退出，父进程使用新 Repository、SQLite connection 和 Graph 实例恢复同一个 Run，并从上次 SSE cursor 继续消费事件。

## 演练路径

`tests/test_phase32_process_recovery.py` 的子进程会：

1. 创建 screenplay Phase 32 Run；
2. 使用真实 `Phase32GraphExecutionService` 和 SQLite checkpointer 运行 brief；
3. 写入 decision checkpoint/read model/event；
4. 在 `async with open_phase32_checkpointer(...)` 尚未退出时执行 `os._exit(0)`。

父进程随后：

1. 新建 `Phase32RunRepository` 读取 Run；
2. 校验状态仍为 `awaiting_decision`、pending decision 和 checkpoint id 完整；
3. 新建 SQLite checkpointer 与 Graph，提交原 decision，继续推进到后续阶段；
4. 使用原 event sequence 作为 cursor，验证只收到 cursor 之后的连续事件。

这证明 SQLite 连接异常关闭不会污染 checkpoint；Run projection、event log 和 graph thread 可以在新进程中重新汇合到同一个 durable frontier。

## 现有 journal / SSE 门

Wave 32.12 的 projection journal 已覆盖 state/read model/failure event 的中断切点；本轮再覆盖 SQLite process exit 和 SSE cursor replay。两者均使用同一 Phase 32 repository、单一 LangGraph runtime，不创建 shadow checkpoint 或第二条事件流。

## 测试证据

新增 `tests/test_phase32_process_recovery.py`：独立子进程退出后 checkpoint 重开、decision resume 和 event cursor replay 全部通过。

本轮定向验证：`1 passed`。全量回归需在本轮改动稳定后执行。

## 下一道门

进入 Provider 成本/余额 sidecar：把真实 usage、transport attempts、模型/provider binding 摘要投影到监控 read model，同时保持 secret 不落盘；完成 fake Provider 成本边界后再申请真实 Provider 小门。
