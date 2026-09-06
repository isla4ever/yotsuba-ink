# Phase 32 Wave 23：r2 三阶段真实门、嵌套 Interrupt 投影与 Beat 语言合同

状态：**三次真实 Provider 技术调用成功；Cast v2 认识论门通过；Beat v2 引用合同通过，但中文质量与 Run 状态投影失败；最低责任层已离线修复，三阶段整体门仍未通过**

日期：2026-08-23

## 范围与停止条件

本轮获准创建一个全新 `screenplay_sample r2` Run，执行：

```text
Brief -> 人工审读 -> accept -> Cast auto-continue -> Beat Board -> stop
```

冻结 Provider 为 `provider-deepseek-text / deepseek-v4-flash`，每个 operation 的 transport
attempt 上限为 `1`，真实调用总数上限为 `3`。任一合同、状态或语义异常立即停止；不自动
重试、不换模型、不接受 Beat、不执行 Scene Deck，也不恢复或修改 Wave 32.21 的失败 Run。

## 新鲜 Run 与冻结合同

```text
project_id:        p32-screenplay-r2-project-20260823-120128
run_id:            p32-screenplay-r2-three-stage-live-20260823-120128
workflow_id:       official-deepseek-fast
route revision:    r2
definition digest: 2f1064ae3c9a24488481d9b2eff7b8318e237ba379dcf58a4efa4e68fcbaeb82
definition sha256: 5eb64391fdf471fadc9f6b978027f9bbf7d263ef8af962148edca446c6b21e0f
```

调用前已确定性验证：Brief v2、Cast v2、Beat Board v2 均已冻结；Cast Context 为
`context.screenplay.cast.v2`；三阶段均绑定同一个可追溯价格快照；密钥只检查存在性，没有输出
原值。Cast 请求实际携带 `epistemic_custody`，合同 digest 为
`06c8e8fe76f4942f0b3d83a969c2dae22541cae0f0c62cd4980c19aabbbe2fbb`。

## 真实调用与成本

| Stage | receipt | attempts | prompt | completion | total | estimated cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Brief | `succeeded` | 1 | 867 | 359 | 1,226 | $0.00022190 |
| Cast | `succeeded` | 1 | 2,777 | 804 | 3,581 | $0.00061390 |
| Beat Board | `succeeded` | 1 | 2,007 | 1,297 | 3,304 | $0.00064414 |
| 合计 | 3 operations | 3 | 5,651 | 2,460 | 8,111 | $0.00147994 |

三次返回均为一个完整 JSON object，`schema_match_count=1`，无 repair、隐藏合同纠正或传输
重试。Provider response SHA-256：

```text
Brief:     73c4e164014f9c8ca6755eb2c6e3d9fe402b25303eff86d6d33e3cc280134461
Cast:      3603f3d159fd3072aab7c1e13ad4c54262d9e702afa208b74f5822c1d3a34bcf
Beat Board:8a09b525ce6d88a92ef915abcdb91f6900abb13e721452ee0b5fbc6beea7c6ee
```

## 内容审读

### Brief

Brief 的 12 分钟倒计时、控制室/维护通道、主管监控、违规开门和不可逆选择均清楚，可拍摄性
与样片范围合格。保留 warning：断电死亡、丢失职位与法律追责是规划风险，不是已经发生的
Canon；Brief 提前使用的人名在 Cast commit 前也没有稳定 subject ref。

### Cast v2

Cast 提交 `lin_lan / chen_mo / supervisor_li` 三个稳定主体。Wave 32.22 的目标真实通过：

- 陈默的死亡保持为“可能死于断电”；
- 李主管涉事保持为“可能”“尚未证实”“可疑但未成事实”；
- 未来失职、法律追责和关系破裂保持为条件或 arc 范围；
- 未把主管掩盖旧事故升级成隐藏罪责或既成动机。

这证明真实模型确实遵守了 Cast v2 custody 的关键未决性边界。它不等于 Cast 已成为 Canon；
人物目标、关系与未来后果仍是 accepted planning。

### Beat Board v2

Beat 返回 8 个连续时间段，覆盖 `0:00-12:00`；18 个 beat/setup/payoff refs 全部匹配稳定
ASCII 合同，Wave 32.21 的冒号/中文引用错误未复发。

文学与产品质量未通过：全部自然语言字段返回英文，第 8 拍把 `character_decision` 填成
`No decision`。前者不符合中文创作台，后者违反“每拍必须有台面人物决定”的阶段意图。
二者保持文学/Prompt warning，不用关键词过滤冒充确定性 Schema blocker，也没有触发换稿。

未来新 Run 使用 `prompt.phase32.screenplay_sample.beat_board.v3`：Prompt 与字段 Schema 明确
除稳定 refs 外全部自然语言使用简体中文，并禁止用“无决定 / No decision”占位。旧 v2
definition、candidate、receipt 和 input snapshot 不重写。

## 嵌套 Interrupt 状态错位

真实事件已正确到达：

```text
1-3   Brief started/candidate/decision required
4-5   Brief decision resolved/artifact committed
6-9   Cast started/candidate/auto decision/artifact committed
10-12 Beat Board started/candidate/decision required
```

但 repository projection 错误显示：

```text
status: awaiting_decision
active_stage_id: cast
cast: awaiting_decision
beat_board: locked
pending decision stage: beat_board
domain_revision: 2
```

durable checkpoint 的父图仍停在刚完成的 Cast；唯一最深 Beat 子图 frontier 则正确包含
`active_stage_id=beat_board`、Beat candidate ref 和运行中状态。LangGraph 在子图 interrupt 时，
`ainvoke()` 返回父图值并附带子图 decision；旧 `Phase32GraphExecutionService` 直接投影父值，
再把 active parent 标记为 awaiting，形成 UI/read model 与真实 checkpoint 的矛盾。

修复只落在状态投影责任层：从 durable snapshot 读取唯一最深 interrupt frontier，以其值覆盖
父路由状态，然后强制校验 decision stage、domain revision、candidate ref 与 awaiting 状态一致。
没有修改 Graph 路由、Provider、Artifact 或历史 repository 文件。新增回归覆盖
`Brief accept -> Cast auto-continue -> Beat interrupt`，证明 state/read model 均停在 Beat。

该真实 Run 保持原始错位投影、成功 Brief decision receipt、25 个 checkpoints、201 个 writes、
12 条事件和 3 个不可变 Provider receipts，作为失败证据；不接受 Beat、不取消、不重投影。

## 验证与安全

- 状态投影、执行、失败锁与进程恢复回归：`10 passed`；
- Prompt/Artifact/Provider/Driver/Graph 扩展回归：`37 passed`；
- 全量后端：`1025 passed`，另有 1 个既有 Starlette/httpx 弃用 warning；
- `compileall`、`git diff --check`、production closure audit：通过；
- closure audit 无 legacy runtime marker、无异常 frontend pipeline 顶层目录；
- 本 Run 与 Wave 32.21 Run 的持久化文件对实际密钥原值扫描：0 个匹配；
- 本轮真实 Provider 调用总数：严格为 3；发现异常后新增调用：0；
- Wave 32.21 失败 Run：未恢复、未修改。

## 未关闭的门

本轮不能称为三阶段整体通过：真实 Cast v2 与 Beat ASCII 合同已分别证明，但 Beat 中文质量和
repository interrupt 投影在本 Run 中失败。下一次真实门必须另建全新 `r2` Run，冻结 Beat v3，
验证 read model/monitor 正确停在 Beat、中文节拍与逐拍人物决定同时成立。旧 Run 不得用 resume
或事后投影替代新鲜验收。
