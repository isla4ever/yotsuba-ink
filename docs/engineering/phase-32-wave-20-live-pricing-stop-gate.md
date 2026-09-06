# Phase 32 Wave 20：真实计价投影 Stop Gate

状态：**真实 Brief 返回成功，但计价投影确定性失败；Run 已取消且未接受候选；最低责任层已离线修复**

日期：2026-08-23

## 范围与停止条件

本轮原计划使用一个全新 `screenplay_sample` Run，依次执行 Brief、Cast 和 Beat Board，并在第三个候选的人工决策点停止。每个真实 operation 的 transport attempt 上限固定为 `1`；任一确定性合同失败立即停止，不用剩余调用次数换取表面进度。

实际只发生一次真实 Provider 调用。Brief 返回后，冻结价格为 known，但 operation receipt 和 read model 的成本状态错误地成为 unknown。该问题属于确定性计价合同失败，因此未接受 Brief、未进入 Cast，也没有创建替代 Run。

## 官方价格复核与修正

真实调用前重新核验 DeepSeek 官方价格页：

- `deepseek-v4-flash` cache-miss 输入：`$0.14 / 1M tokens`；
- `deepseek-v4-flash` 输出：`$0.28 / 1M tokens`；
- 来源：https://api-docs.deepseek.com/quick_start/pricing/
- 本地核验时间：`2026-08-23T10:45:17+08:00`。

Wave 32.19 保存的 `$0.44 / $1.32` 已与当前官方页面不一致。本轮先把代码权威、三份官方 Workflow 镜像和实际 Provider store 同步到新费率；cache-miss 输入价仍作为本地保守上界，不冒充 Provider 账单。`deepseek-v4-pro` 继续没有猜测性价格条目。

调用前 readiness 输出仅包含以下非敏感结论：Provider 已启用、密钥存在、Flash 精确价格存在、来源匹配、冻结模型为 `deepseek-v4-flash`。没有输出 API Key 或请求 header。

## 新鲜 Run

```text
project_id: p32-screenplay-project-20260823-105004
run_id: p32-screenplay-three-stage-live-20260823-105004
creation_route_id: screenplay_sample
workflow_id: official-deepseek-fast
model_id: deepseek-v4-flash
definition_digest: 13b1241e2b23106578725aa55c49e87634ce7f1bc2ef452d7810b4a69420610f
definition file sha256: 398aefd2e0a8216dcf8bd4ecc6cc621013921dfe69bcfa9f3dcce6eee23a2744
```

Brief operation：

```text
provider operations: 1
transport attempts: 1
status: succeeded
prompt tokens: 867
completion tokens: 460
total tokens: 1327
reasoning tokens: 0
candidate artifact sha256: 6b53e3f8b5d4d940e88d135367a5c27fd20a95d765f84d159f52e01f73d1dee3
```

Provider 返回单一完整 JSON object，Schema 一次匹配，没有解析修复。按冻结费率离线重算的诊断值为 `$0.00025018`，但原成功 receipt 的 `estimated_cost_usd` 为 null、`cost_status` 为 unknown；该诊断值不得作为已落盘账单或已闭合 read model 成本。

## 最低责任层与修复

调用链为：

```text
GraphRunDefinition pricing snapshot
-> Phase32RouteDriver
-> Phase32ProviderOperationStore.record_return()
-> phase32_pricing_snapshot()
-> receipt/read model usage projection
```

`Phase32RouteDriver` 传入已验证的 `Phase32ProviderPricingSnapshot` 模型对象；`phase32_pricing_snapshot()` 却只接受 `dict`，把其他输入统一降级为 `model_id=unknown`。因此 readiness 在网络前正确通过，usage 也正确返回，但 receipt 计价计算拿到 unknown snapshot。

修复保持单一边界：`phase32_pricing_snapshot()` 直接接受并返回已验证模型，同时新增 `test_receipt_costs_a_validated_pricing_snapshot_model`，证明 typed snapshot 能生成 known cost。没有新增 fallback、历史 converter 或 receipt 猜测修复。

成功 receipt 按合同不可变，本轮没有事后补写成本。Run 在原 Brief 决策点提交 `cancel`：

```text
status: cancelled
active_stage_id: brief
pending decisions: 0
candidate artifacts: 1
committed artifacts: 0
provider operations: 1
transport attempts: 1
```

取消后的事件为：`stage.started -> candidate.created -> decision.required -> decision.required -> decision.resolved(cancel)`。LangGraph SQLite 为本 Run 保存 `9` 条 checkpoint 和 `84` 条 writes。第二个 `decision.required` 来自恢复 interrupt 后重放同一决策节点，没有产生新的 Provider operation。

## Brief 人工审读

确定性字段和目标时长通过；`sample_type` 已改为作者语义，没有重复内部 route ID。控制室、维护通道、倒计时、封锁操作和调度通话构成可拍摄的台面冲突，主角的违规选择也有明确职业风险。

保留的文学 warning：

- “按规程就会导致证人死亡”目前是 Brief 声明，后续 Beat/Scene 必须用可见信息证明，不能直接当作无争议事实；
- 手动解除封锁与检修车安全驶出的铁路操作关系仍偏概念化，Scene Deck 必须给出可信的具体机制；
- 结尾的“失去岗位与信任”需要落成可见动作或状态变化，不能只靠总结句宣告。

这些 warning 没有触发隐藏换稿；本轮停止原因是计价投影确定性失败，不是文学偏好。

## 安全与回归

- Phase 32 runtime 全目录对实际密钥原值扫描：`0` 个匹配文件；
- Wave 18 definition/candidate SHA-256 仍分别为 `2c3e009c...6dd1` 与 `280038cd...4dc`，未接受、恢复或改写；
- 计价、Driver、receipt、gateway、execution 定向回归：`39 passed`；
- 全量后端：`1015 passed`，另有 1 个既有 Starlette/httpx 弃用告警；
- `compileall`、`git diff --check` 和 production closure audit 通过；
- 本轮真实 Provider 调用总数：`1`。

## 下一道门

必须创建又一个全新 Run，重新从 Brief 开始验证修复后的 known receipt cost。只有新 Brief 的 Artifact、usage、receipt、read model 与人工审读同时通过，才接受并进入 Cast；Cast 合格后才进入 Beat Board。不得恢复本轮 cancelled Run，也不得根据离线重算值改写其成功 receipt。
