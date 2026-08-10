# Phase 19：Narrative Program 与 Prompt Compiler

> 状态：Wave 19A-19E 已落地；Wave 19F 已完成真实三章正文检查点与 Canon 结算，整书长篇验收仍待后续预算与人工冷读
> 适用范围：Info、Summary、Outline、Detail、正文 Prompt、人物/关系/伏笔状态、Wiki/RAG/Canon、模型思考策略
> 核心原则：前置阶段负责做决定，正文负责把决定写成自然发生的故事；计划永远不能覆盖已冻结正文现实。

## 1. 问题不是单纯 Prompt 太长

真实 32 章验收 Run 暴露出三类问题：

1. 同一信息以多个权威版本出现。正文同时收到章细纲、SceneContract、前章摘要、结果桥、尾文、Voice Spec、Voice Genome、人物图和世界规则。
2. 上游阶段没有编译成稳定的可执行状态。Detail 把全部历史章节 ledger 反复带入，首批 Prompt 已约 2.6 万字符，后期增至约 4.5 万字符。
3. `priority` 只是代码字段，最终 Prompt 仍是多块平级 Markdown。模型需要自己判断“已发生事实、计划意图、人物认知、表达偏好”谁覆盖谁。

正文开启更强 thinking 不能解决这些冲突。它只会让模型在重复上下文上消耗更多 Token。

## 2. 产品决策

Yotsuba Ink vNext 使用一条 Narrative Program，而不是七次互不相干的生成：

```text
Story DNA
  -> Causal Spine
  -> Volume Program
  -> Chapter Execution Graph
  -> PromptBrief
  -> Prose Reality
  -> Reality Reconciliation
  -> Canon / Wiki / Next PromptBrief
```

每一层只做本层决策，并把下游需要的最小合同交出去。

## 3. 各阶段的新职责

### 3.1 Info：Story DNA

Info 只建立可持续创作基线，不提前写完整剧情：

- 核心概念与阅读承诺；
- 世界规则、可变区域与禁区；
- 主要人物的身份、欲望、恐惧、底线、秘密和能力边界；
- 初始关系边及双方对关系的不同理解；
- 叙事视角、语言边界和人物声音；
- 下游不能违反的约束。

Info 不负责逐章事件、伏笔回收章节或关系最终结果。

### 3.2 Summary：Causal Spine

Summary 固化全书因果脊柱：

- 初始失衡；
- 主角及关键人物的选择链；
- 每个关键转折改变了什么后续可能性；
- 主要人物弧的起点、不可逆节点和终点；
- 结局必须兑现的承诺；
- 哪些内容仍保持开放。

结构术语只用于检查，不能代替人物选择和因果。

### 3.3 Outline：Volume Program

每卷必须拥有明确的 `state_in -> pressure -> irreversible_change -> state_out`：

- 卷目标、卷代价、卷结算；
- 每名主要人物在本卷的 trajectory segment；
- 关键关系边的 `state_in / pressure / state_out`；
- 世界规则的揭示顺序；
- 伏笔投放、推进、回收或延后的时间窗；
- 与前卷、后卷的因果交接。

Outline 不规定所有场景动作，不把平均章节数当作卷界。

### 3.4 Detail：Chapter Execution Graph

Detail 是正文的施工图，不是剧情摘要。每章 v2 产物应包含：

```text
chapter_state_in
chapter_state_out
scene_contracts[]
character_beats[]
relationship_beats[]
fact_reveals[]
foreshadow_actions[]
wiki_candidates[]
continuity_handoff
```

`character_beats[]` 只覆盖本章实际参与或受本章结果影响的人物：

- `character`
- `want_now`
- `belief_in`
- `knowledge_in`
- `action_choice`
- `cost`
- `knowledge_out`
- `state_out`
- `next_pressure`

`relationship_beats[]` 记录有实际状态变化的有向关系：

- `source` / `target`
- `state_in`
- `surface_goal`
- `hidden_pressure`
- `change_trigger`
- `state_out`
- `evidence_target`

不是每章都强制所有人物露面。系统在卷级做 trajectory coverage：主要人物长时间没有行动、选择或后果时阻断 Detail 定稿，而不是在每章硬塞群像。

### 3.5 Chapter Text：Prose Realization

正文不再接收完整 Story Brief、全量人物图或全量历史细纲，只消费当前场景的 `PromptBrief`：

1. 当前场 SceneContract；
2. 冻结正文结果桥与实际尾文；
3. 当前有效事实、物件和关系状态；
4. 当前 POV 知识边界；
5. 本场表达差量；
6. 可自由创造的范围。

模型可自由决定动作细节、感官、对白、潜台词、句法与局部策略，不能改变进入状态、转折、代价、离场和 handoff。

### 3.6 Postprocess：Prose Reality

章后抽取只读取最终正文：

- 实际发生的动作、选择和结果；
- 人物知识、关系、物件、伤势和空间变化；
- 伏笔证据；
- 可提交事实及逐字证据；
- 下一章仍有效的未完成动作。

计划没有在正文出现，就不能写入 Canon、Wiki 或 Narrative World State。

## 4. 计划与现实对账

每章完成后生成确定性的 `RealityReconciliation`：

| 状态 | 含义 | 后续行为 |
| --- | --- | --- |
| realized | 正文有证据完成计划 | 写入活动叙事状态 |
| deferred | 正文明确保留但未完成 | 带入下一章未完成动作 |
| omitted | 计划没有出现在正文 | 不写回，进入质量诊断 |
| contradicted | 正文与计划或 Canon 冲突 | 阻断提交或建立修订分支 |
| superseded | 冻结正文形成了不同但有效结果 | 以现实为准，补丁更新未来 Detail |

未来细纲不能自动覆盖冻结正文。若实际结果与未来计划有结构性偏差，只允许生成 `FuturePlanPatch`，由质量门或用户确认后更新尚未执行的 Detail。

## 5. Wiki、RAG、Canon 与状态机边界

| 系统 | 唯一职责 | 权威性 |
| --- | --- | --- |
| Canon | 已提交、带正文证据的硬事实 | 最高，修改需修订分支 |
| Narrative World State | 当前有效的人物、关系、物件、空间、知识状态 | 高，带有效期与来源 |
| Foreshadow Ledger | 稳定线索 ID、状态、承诺、证据和回收窗口 | 高，不等于事实正文 |
| Character Trajectory Ledger | 人物计划与实际变化的双轨账本 | 计划和现实分栏 |
| Wiki | 面向用户的可读派生页 | 不能覆盖 Canon |
| RAG | 从知识库/Wiki/Canon 中按需检索 | 只负责召回，不负责裁决 |

RAG 不再召回正文 Prompt 已拥有的完整 Summary、Outline 或 Detail。命中必须带来源、签名、权威等级和相关性；没有命中时保持空，不用远期背景填满上下文。

## 6. Prompt Compiler 合同

Wave 19A 已新增纯函数 `compile_prompt_brief()`，不调用 Provider。每条重要 claim 记录：

- `source_stage`
- `source_chapter`
- `source_signature`
- `authority`
- `confidence`

优先级固定为：

1. 冻结正文和带签名的已验证叙事状态；
2. 已提交 Canon；
3. 当前场 SceneContract；
4. 当前章 Detail 计划；
5. 远期 Outline、伏笔和检索参考。

第一场读取上一章结果桥与尾文；第二场起只读取前一场实际尾文和当前 handoff。`chapter_outline` 被 SceneContract 替代，Voice Genome 被 LiteraryIntent 替代，source signatures 只进入 trace，不作为模型正文内容。

真实第 4 章离线复算：

| 场景 | system | user | 调用边界 | 总字符 |
| --- | ---: | ---: | ---: | ---: |
| 4_1 | 1,649 | 3,686 | 191 | 5,545 |
| 4_2 | 1,649 | 2,399 | 814 | 4,881 |

旧 Run 的正文 Prompt 为 6,789-14,819 字符。新结果只是离线编译证据，不等于 Provider 质量验收。

## 7. Agent 与 thinking 分工

不为每章增加一个模型 Agent。职责按模式分配：

| 职责 | Fast | Balanced | Deep |
| --- | --- | --- | --- |
| 确定性 Prompt Compiler | 必选 | 必选 | 必选 |
| 章节 Planner | 无 | 仅高风险可选 | 高风险/卷首卷末可选 |
| 正文生成 | thinking 关闭 | 关闭或最低 | 关闭或最低 |
| 语义/衔接主审 | 无 | thinking 开启 | thinking 开启 |
| 因果/终章专项 | 无 | 风险触发 | 固定职责、风险触发 |
| 抽取与 Wiki | 结构化、thinking 关闭 | 同左 | 同左 |

可选 Planner 只输出 3-5 个当前叙事任务、冲突裁决和桥接策略；不能写正文、不能改硬事实、不能写回 Canon/Wiki。正文生成与审稿可并行准备，但不能并行生成相邻章节。

## 8. Prompt 预算

| 阶段 | 目标 | 硬上限 |
| --- | ---: | ---: |
| Info | 6K-8K | 10K |
| Summary | 8K-10K | 12K |
| Outline（按卷） | 8K-10K | 12K |
| Detail（按批） | 8K-10K | 12K |
| Chapter 单场 | 5K-9K | 16K |
| 语义 Review | 正文 + 4-6 条目标合同 | 16K |

超限时只能按 P3 -> P2 -> P1 压缩；P0 超限必须显式阻断，不能尾部字符串截断。

## 9. 实施波次

### Wave 19A：正文 Prompt Compiler（已完成）

- 单场 `PromptBrief`；
- 权威来源 trace；
- 第一场/后续场不同上下文；
- world/voice/outline 去重；
- Detail ledger 固定为最近两章。

### Wave 19B：结构阶段 Context Compiler（已完成）

- `compile_structure_context()` 已按 Summary / Outline / Detail 分别编译唯一上游语义，去掉 Story Brief、人物图、Voice 等重复注入；
- Detail 基础 Prompt 与当前卷任务分离，批次只携带当前卷和最近两章连续性 ledger，不再随章节线性重放全部历史；
- P0 结构段超预算会显式阻断，可选段按预算移除并记录 `omitted_keys`；
- 当前结论来自确定性编译与测试，不代表真实 Provider 已完成结构质量验收。

### Wave 19C：Detail v2 与人物轨迹（已完成）

- `schema_version=2` 已新增稳定 `scene_id / beat_id / fact_id / action_id / candidate_id`；
- 每章包含 1-6 个 `character_beats[]`、0-6 个有向 `relationship_beats[]`，并逐项绑定本章已有场景；
- 场景数按叙事需要限定为 1-3，不再强制两场；事实、Wiki 候选和伏笔动作只发送给其绑定场景；
- `character_shift` 和旧 `foreshadow` 仅作为历史 Run 兼容投影，不再是新产物权威；
- Detail 前端已提供人物/关系轨迹编辑、引用校验和稳定 ID 保存入口；卷级 trajectory coverage 负责阻止主要人物长期失联，而不是把所有人物硬塞进每章。

### Wave 19D：Reality Reconciliation（已完成）

- 场景 `turn / cost / exit / handoff` 与 Detail 的事实、人物、关系、伏笔计划都编译为稳定 `plan_item_id`，并在最终正文抽取后逐项进入五态对账；
- 对账记录绑定正文、Detail、SceneContract、计划和事务签名；`contradicted` 进入阻断，`deferred/omitted` 不得伪装成已实现事实；
- 人物、关系、伏笔和 Wiki 写回必须携带当前 `reconciliation_ids`、正文 assertion IDs 与证据签名，卷级 Canon 审计再次核对缺失、冲突和陈旧记录；
- 新版 `narrative_verification schema v2` 在正文验证后立即重新投影章后抽取，只保留正文证据支持的条目；章节正式写回和卷级 Canon 审计再次执行同一证据门。旧历史 Run 保留兼容读取，但新版记录不得降级为 `legacy_unverified`；
- `FuturePlanPatch` 只在 `superseded` 时生成 `proposed` 提案，绑定正文签名与 `base_detail_signature`。当前没有自动应用路径，也绝不改写已冻结正文；未来接受时必须以这两个签名做 CAS，任一基线变化即标记 `stale`；
- 正文、Detail 或章节恢复失效时，同步清理事务、对账和其派生补丁，避免旧证据继续写回。

### Wave 19E：Reviewer 与 Provider 策略（已完成，三章真实质量检查已执行）

- Reviewer 继续遵守窄职责和冻结稿输入；它们只诊断或提出证据定位的小补丁，不能写 Canon，也不能替代确定性 Reality Reconciliation；
- DeepSeek 的 Summary / Outline / Detail / model review / cold edit 已按节点开启 thinking，正文生成和章后抽取保持关闭以控制成本和结构稳定性；
- 请求策略按具体模型能力合并 `thinking.type` 与 `reasoning_effort`，思考开启时移除不兼容采样参数；
- JSON Output 会设置 `response_format={"type":"json_object"}`，Prompt 同时保留 JSON 关键词和示例；已有 `输出结构 / 输出合同 / JSON 输出示例` 时不再重复注入协议；空 content 显式失败，不伪造成功；
- Prefix Completion 保留为显式 Beta 实验能力，不进入默认正文主线。

### Wave 19F：三章 A/B 验收

- 同一 Story DNA；
- 旧 Prompt 与新编译 Prompt 对比；
- 检查 handoff、POV 越权、人物轨迹、关系变化、伏笔证据、重复表达、人工冷读和 Token；
- 三章检查点通过后，才允许创建预算可闭合的新长篇 Run；本轮不以技术通过替代投稿人工审读。

#### 2026-08-06 Detail v2 真实检查点

- Run `phase19f-prompt-compiler-three-chapter-20260806-a1` 复用了 3 个签名一致的 v2 逐章批次；修复前合并器曾把总稿错误标为 v1，恢复事件撤销待确认总稿并保留历史 Token、attempts、operations，`provider_calls=0`。
- 合并后本地投影了 7 处人物/关系状态边界；场内 handoff、跨章进入/离场、引用、稳定 ID、四条 Outline 伏笔终章回收均通过。唯一缺项是主要人物在 1-3 章没有 `character_beat`。
- 第一次窄轨迹补丁错误继承 `detail_outline` 的 `reasoning_effort=max`，在 `1800 tokens` 上限内被截断，消耗 `3932 tokens` 后 fail-closed；没有正文、待确认稿或正式写回产生。
- 轨迹补丁改用独立 `detail_trajectory_repair` 任务并关闭 thinking 后，一次 retry 成功，消耗 `2337 tokens`。总用量为 `330490 tokens`、15 条 operation；三个 Detail 批次仍为零调用复用，正文仍为 0 章。
- 结构硬门通过后，人工冷读仍发现补丁把 Info 的“失踪”强化为“已故”，并发现一处人物代词漂移。当前稿已用零 Provider 的确定性修正保留“失踪”状态、消除代词歧义，并把结局代价逐字对齐为“吊销修复执照”；总稿、批次和审批副本重新验签一致。
- Wave 19F 定向合同矩阵 `126 passed`；测试 Provider 的单章分卷范围已改为规范闭区间，原六项下游回归 `6 passed`，后端全量为 `1115 passed / 1 skipped`。`git diff --check` 与 Python `compileall` 通过；这些检查没有新增 Provider 调用。

#### 2026-08-06 正文三章真实验收与恢复

- Run `phase19f-prompt-compiler-text-three-chapter-20260806-a1` 形成 3 章冻结正文，长度为 `3563 / 3376 / 3511` 字符，总计 `10450`；第 1-3 章语义审稿均完成，正文候选没有重新生成。
- 运行曾在确认后的定稿复审中报“新的跨卷 Canon 冲突”。审计证据显示不是正文冲突，而是自动确认器重建写回提案时漏传 `state`，把第 1、2 章已绑定的叙事对账降级成 `legacy_unverified`。
- `prepare_acceptance_text_writebacks()` 现已把当前 `NovelRunState` 传入 `build_writeback_proposal()`；新增 `acceptance_canon_writeback_evidence_recovery` 只在卷审计唯一失败码为 `writeback_evidence_invalid`、没有正式 commit 且章节签名未变时生效。
- 同一 Run 的恢复事件 `acceptance_canon_writeback_evidence_rebound` 证明：`provider_calls=0`、`prose_changed=false`、`budget_changed=false`；第 1、2 章提案恢复为 `evidence_bound`，卷审计重新进入 `prepared`，随后正式 Canon 原子提交并完成运行。
- 最终运行状态为 `completed`，无当前错误；首次收束后的报告仍有 Wiki/RAG 记录、可疑实体名和伏笔证据历史三项红灯，后续按下述确定性对账修复。无论技术检查是否通过，投稿状态始终保持 `needs_author_review`。

#### 2026-08-06 章级 RAG、实体身份与伏笔投影收束

- `wiki_rag_recorded` 现在区分“执行过检索”和“检索有命中”。Context Packet v3 已直接携带 Info / Summary / Outline / Detail，且同卷章后 Wiki 要等卷级 Canon 原子提交后才正式可见；因此本 Run 的真实证据是 `retrieval_attempts=3 / chapter_retrievals=0 / zero_hit_retrievals=3 / invalid_retrievals=0`。零命中不会再被误报为没有执行，但也绝不能表述为 RAG 召回有效。
- Wiki 有命中时仍必须满足 Packet 的 `wiki-retrieval:` 签名与持久化 Context 签名一致；零命中只在查询、检索版本、空 hits、空签名和空 `retrieved_context` 全部一致时才算可追溯尝试，不能靠补空键通过。
- Canon 身份检查不再对普通中文长句做任意两字滑窗。`持有一台老式播放器` 中的 `台老` 不再被误判为 `钟老` 的近似姓名；显式两字 target / holder / character 槽位仍继续执行近似身份校验，三至四字姓名在事实句中的误写也继续阻断。
- 细纲 `foreshadow_actions[]` 现在按精确名称继承 Outline `foreshadow_windows[]` 的全局稳定 ID，同时保留本章 `action_id`。章后抽取第一次兑现伏笔时，只能从已确认计划目录创建现实账本；未规划 ID、同义改名和无逐字证据仍被拒绝。
- Reality Reconciliation 对伏笔允许最多四条同场逐字断言共同证明一个计划动作，解决“乳名、声痕、离线、复制”被拆成多个事实后每条单独相似度不足的问题；非伏笔计划仍沿用原来的显式绑定、claim key 或单条语义证据规则。
- 已提交卷的伏笔投影恢复进一步绑定：Outline 稳定 ID、章节 Context Packet 的计划状态、冻结正文 SHA、章节 commit、写回 proposal、卷 commit、Reality Reconciliation 与唯一原始断言。`pending/rejected` 提案不可恢复；空的 `not_required` 仅可在上述证据全部成立时作为历史漏投影修正。
- 同一 Run 新增事件 `committed_foreshadow_projection_recovered`（event `1075`），只恢复“被删记忆的残留声痕”：第 1 章逐字证据完成投放，第 3 章逐字证据完成回收。事件记录 `provider_calls=0 / prose_changed=false / budget_changed=false / canon_changed=false`，没有生成或修改正文。
- 重写后的自动化报告 `technical_passed=true`，三项红灯均已收束；伏笔证据明确记录为 `ledger_records=2 / evidenced_records=1 / evidence_transitions=2 / recovered_records=1`，`submission_readiness` 仍为 `needs_author_review`。另外三条终章伏笔没有足够的已验证断言进入现实账本，仍必须在人工冷读中逐项核对，不能用“存在一条伏笔历史”替代完整终章兑现审查。
- 本波次扩圈定向回归为 `89 passed`，最终伏笔/报告定向回归为 `67 passed`；后端全量为 `1164 passed / 1 skipped`，Python `compileall` 与 `git diff --check` 通过。唯一 warning 来自 Starlette TestClient 对当前 httpx 兼容入口的弃用提示，不影响本波次行为结论。

#### 2026-08-06 Prompt Compiler 可观测性与三章离线 A/B

- `PromptPlan.prompt_trace` 现在记录稳定 `prompt_signature / brief_signature`、旧式场景上下文与 LiteraryExecution 字符数、新 PromptBrief 字符数、节省比例、claim 权威分布、来源签名数量和裁剪原因；正文 Provider 的 `provider_attempt_started` 事件只携带这份内容无关 trace，不保存 Prompt 原文。
- 质量合同恢复除正文签名外继续绑定 `context_signature`；新增场景 `handoff_out` 漂移回归，证明正文未变但 SceneContract 已变化时必须 fail-closed，不能复用旧语义审稿、专项审稿或协调结果。
- 对 Run `phase19f-prompt-compiler-text-three-chapter-20260806-a1` 的 3 章 8 场执行零 Provider 离线复算：旧上下文核心合计 `50636` 字符，新 PromptBrief 合计 `27553`，减少 `23083`，压缩率 `45.59%`；最大最终调用 Prompt 为 `6732 / 16000` 字符。
- 8 场 P0 任务、有效事实、POV 和适用的前章/场内交接全部保留；原始来源签名渲染数为 `0`，重复编译行数为 `0`。审计前后 Run revision 均为 `1474`、事件数均为 `1075`，没有预算、正文、Canon 或运行状态写入。
- 该报告证明编译器的上下文主次、字符预算与可追溯性，不证明新 Prompt 已在另一组真实 Provider 调用中获得更好的文学质量；正式 A/B 仍须使用同一 Story DNA、相同模型参数和有界三章预算，并由人工盲读比较衔接、人物声音与解释密度。

## 10. 当前边界

- 2026-08-06 离线与真实检查：Prompt 快照、后端回归、前端构建和 CSS 审计已通过；真实三章 Run 已完成正文、叙事对账、卷级 Canon 提交和运行收束。历史 Provider 失败仍保留在审计链中，不能抹除。
- 当前 32 章 Run 仍被预算闭合门阻断，第 5 章不得启动。
- Wave 19A-19E 的结构结论主要来自离线编译、合同测试和构建；Wave 19F 已有真实三章正文验收证据，但尚未证明整书长篇的章节规模、投稿规则和人工文学质量。
- Info 的人物 DNA、Summary 的不可逆因果结构、Outline 的卷级人物/有向关系轨迹仍需继续升级；必须先扩展后端产物合同，再增加前端字段，禁止制造只存在于 UI 的假能力。
- `FuturePlanPatch` 当前只生成可审计提案；接受、CAS 应用和用户决策 UI 尚未实现，不得把 `proposed` 表述为未来细纲已经更新。
- Detail 轨迹弹窗仍需补齐渲染/交互和多视口浏览器验收；三章真实报告的 Wiki/RAG、实体规范化和伏笔证据红灯已收束，Prompt Compiler 的离线 A/B 也已通过。下一轮应使用新稳定 ID 链路执行有界的真实三章 Provider A/B，再决定是否开启整书长篇 Run。
- 不使用 AI detector 分数证明可投稿；质量验收依赖人工冷读、连续性证据、具体编辑记录和投稿平台政策。
