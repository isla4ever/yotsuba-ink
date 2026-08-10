# Phase 21：阶段语义重整与细纲优先的叙事生产

> 状态：历史规划冻结稿；实施结果以 `phase-21-detail-first-narrative-production.md` 与 `phase-22-chapter-rhythm-and-detail-first.md` 为准。
>
> 日期：2026-08-07
>
> 适用范围：Planning、Info、Summary、Outline、Detail、Chapter Text、Cover、Export、Prompt Compiler、Context Broker、RAG、质量模式、LangGraph Chapter Runtime
>
> 前置文档：`stage-artifact-contract.md`、`phase-19-narrative-program-and-prompt-compiler.md`、`phase-20-langgraph-narrative-runtime.md`

## 1. 结论先行

Yotsuba Ink 的下一轮重点不是继续给正文增加规则、Reviewer 或自动修订，而是让每个前置阶段只完成自己应完成的叙事决策，并把结果编译成下一阶段所需的最小上下文。

核心产品决定如下：

1. Info 定义故事可以成立的创作基线，不规划逐章剧情。
2. Summary 定义全书因果脊柱和结局承诺，不承担分卷排期。
3. Outline 定义每卷如何推进和结算，不承担逐场写作。
4. Detail 是逐章剧本，也是正文剧情安排的唯一权威来源。
5. Chapter Text 负责把当前场景剧本写成自然发生的小说，不再重新规划剧情，也不接收全部上游 Artifact 原文。
6. Postprocess、Reviewer、Reality Reconciliation 负责理解已经写出的正文，不把审稿标准提前压给 Writer。
7. RAG 只在用户实际上传资料库并显式选择使用时启动，主要服务 Planning / Info 的资料理解；正文阶段禁止临时检索用户资料库。
8. Fast、Balanced、Deep 必须拥有不同的阻断与人工合同，不能共享同一套 Deep 级正文门禁。
9. LangGraph 继续作为执行控制面，但在本阶段合同通过三章 A/B 前，不继续扩大到 Stage / Global 主路径。

本阶段不是减少创作质量，而是把质量前移到正确的决策层，并把正文从重复规划、规则记忆和自我审稿中释放出来。

## 2. 当前问题的本质

当前系统已经有 Prompt Compiler、Detail v2、Context Snapshot、Reality Reconciliation、Reviewer 和 Canon/Wiki 写回，但仍存在四类结构性问题。

### 2.1 上游阶段有产物，却没有形成单向编译链

同一决定可能同时存在于 Summary、Outline、Detail、Context Packet、SceneContract、Story Bible 和质量目录中。即使最终 Prompt 已经比旧版本短，Writer 仍需要判断多个相似表达谁更权威。

正确行为应是：

```text
上游完整 Artifact
    -> 当前阶段编译投影
    -> 下一阶段最小输入
```

下游不再读取所有祖先 Artifact，也不重新解释祖先字段。

### 2.2 Detail 的结构很丰富，但还不像一份可执行剧本

Detail v2 已经覆盖场景、人物、关系、事实、伏笔和交接，但存在以下问题：

- 章级状态、场景进出状态和 continuity handoff 存在重复权威；
- handoff 依赖模型逐字复制，结构正确性被字符串表述方式绑架；
- Wiki 候选与事实揭示重复描述相近内容；
- 机器字段很多，但缺少一份作者能直接审阅的章节因果与选择链；
- Writer 需要从多组字段中自行重新组织本场任务。

Phase 21 不继续堆字段，而是确立一个权威数据层和两个编译投影。

### 2.3 正文承担了不属于写作的职责

Writer 当前仍可能看到质量 Rubric、阶段阻断措辞、禁用项、事实目录和写回相关概念。它同时被要求：

- 写出自然正文；
- 记住所有约束；
- 自检是否通过质量阀门；
- 逐项兑现计划目录；
- 避免触发启发式检测。

这会使正文趋向保守、解释性强、动作机械、缺少意外但合理的细节。

### 2.4 生产门与编辑诊断没有分层

Fast 与 Balanced 虽然减少了模型审稿调用，但确定性 blocking finding 仍可能让它们停在正文阶段。模式差异因此只体现在 Token 和界面，而没有真正体现在自动生产能力上。

## 3. Phase 21 的非协商原则

### 3.1 每个阶段只做一次属于自己的决定

上游负责决定，下游负责消费。后续阶段可以细化，但不能用另一套平级表达重新决定同一件事。

### 3.2 细纲是剧本，不是正文草稿

细纲必须讲清楚：

- 本章从什么现实状态进入；
- 哪些人物在什么认知下做出什么选择；
- 选择遇到什么阻力并付出什么代价；
- 什么信息被谁得知、误解或继续隐瞒；
- 伏笔在本章被投放、推进、回收还是延后；
- 场景发生怎样的不可逆转折；
- 本章以什么状态离场并给下一章留下什么压力。

细纲不得规定：

- 每句对白；
- 每个动作的具体表现；
- 每段感官描写；
- 比喻、句法和段落节奏；
- 不改变剧情结果的局部策略；
- 人物如何用符合自身性格的方式完成既定选择。

这些内容属于正文的创作自由区。

### 3.3 正文只执行当前剧本

正文 Provider 每次只接收当前场景的执行简报、必要承接和最小事实边界。Writer 不读取全量 Summary、Outline、Detail、Wiki、人物图和资料库。

### 3.4 计划不能伪装成已经发生的事实

Detail 只写 Narrative Plan。正文完成并经过 Reality Reconciliation 后，真实发生的内容才能进入临时叙事状态；卷级提交后才能成为正式 Canon。

### 3.5 自动生产和投稿精修是两个产品承诺

- Fast 交付完整快速草稿；
- Balanced 交付可读、可继续编辑的初稿；
- Deep 交付经过审校和人工确认的编辑候选稿。

三个模式都必须能生产，但不能对三者承诺完全相同的投稿准备度。

## 4. 各阶段唯一职责与下游投影

| 阶段 | 唯一职责 | 权威 Artifact | 用户决策 | 写回目标 | 只交给下一阶段 | 明确不负责 |
| --- | --- | --- | --- | --- | --- | --- |
| Planning | 定义创作请求和运行策略 | `ProjectCreationSpec` | 题材、规模、模式、资料、Provider | Run Input Snapshot | 创作目标、硬偏好、资料选择 | 写世界观、剧情和正文 |
| Info | 建立故事可持续创作的基线 | `StoryDNA` | 书名、核心概念、世界规则、人物基线、叙事角色 | Story Bible 基线、人物图基线 | `StoryDNABrief` | 逐章剧情、伏笔回收章节 |
| Summary | 建立全书因果脊柱 | `CausalSpine` | 主线冲突、人物选择链、关键转折、结局承诺 | 全书因果与人物弧计划 | `CausalSpineBrief` | 分卷排期、逐场动作 |
| Outline | 把因果脊柱分配到各卷 | `VolumeProgram` | 每卷目标、代价、节奏、结算、人物/关系推进 | 分卷计划与伏笔窗口 | 当前卷 `VolumeBrief` | 逐章正文、具体对白 |
| Detail | 把当前卷编译成逐章剧本 | `DetailNarrativeBlueprint` | 章节因果、选择、信息、伏笔、交接是否成立 | Narrative Plan Ledger | 当前章与当前场 `ExecutionBrief` | 文学表达和句法设计 |
| Chapter Text | 实现当前场景剧本 | `ChapterArtifact` | Fast/Balanced 可不干预；Deep 选择或编辑正文 | Prose Reality、临时叙事状态 | 下一章 `ContinuityLedger` | 重做全书规划、查询资料库 |
| Cover | 包装已稳定的作品定位 | `CoverArtifact` | 视觉方向和选中方案 | 封面资产、导出引用 | 选中封面及元数据 | 等待全书正文完成后才启动 |
| Export | 验证并交付当前版本 | `ExportManifest` | 格式、范围、版本 | 导出包和审计记录 | 最终交付物 | 修改正文或 Canon |

### 4.1 Planning：创作请求，不是故事阶段

Planning 只冻结：

- 用户希望写什么；
- 大致篇幅与章节长度偏好；
- 目标读者与内容边界；
- 叙事角色/风格配置；
- Fast / Balanced / Deep；
- 是否上传资料库以及选中哪些文档；
- 各阶段 Provider 和预算。

Planning 不生成世界事实，也不把用户资料搜索结果直接变成 Canon。

### 4.2 Info：Story DNA

Info 的产物只回答“这是什么故事，谁生活在怎样的世界里”：

- 核心概念与阅读承诺；
- 世界硬规则、可变区域和未知区域；
- 主要人物的欲望、恐惧、底线、秘密和能力边界；
- 初始关系以及双方对关系的不同理解；
- 叙事 POV、时间和语言边界；
- 下游绝不能推翻的少量约束。

Info 给 Summary 的 `StoryDNABrief` 必须是压缩投影，不包含推荐过程、资料原文或 UI 展示字段。

### 4.3 Summary：Causal Spine

Summary 只回答“全书为什么会从起点走到结局”：

- 初始失衡；
- 主要人物的选择链；
- 每次不可逆转折改变了哪些可能性；
- 反派或阻力系统如何升级；
- 人物弧的起点、临界点和终点；
- 结局必须兑现的承诺；
- 仍可由后续阶段决定的开放空间。

Summary 不规定卷数和每章任务。它给 Outline 的是因果节点和人物弧关键点，不是全文梗概原文。

### 4.4 Outline：Volume Program

Outline 只回答“每一卷承担哪段变化”：

- `state_in -> pressure -> irreversible_change -> state_out`；
- 卷目标、卷代价、卷结算；
- 人物和关系的卷级 trajectory；
- 世界规则的揭示顺序；
- 伏笔的投放、推进、回收窗口；
- 前卷结果和后卷压力。

Outline 给 Detail 的 `VolumeBrief` 只包含当前卷及与相邻卷有关的交接，不带全书所有卷的完整文本。

### 4.5 Detail：Detail Narrative Blueprint

Detail 是本阶段重构重点。它必须先在卷级验证章节链，再成为正文输入。

每章权威蓝图至少表达：

- `chapter_id` 与所属卷；
- `chapter_promise`：本章给读者的核心变化；
- `state_in`：从上一章现实继承的进入状态；
- `causal_chain[]`：原因、选择、阻力、结果；
- `scenes[]`：有序场景剧本；
- `decision_beats[]`：人物选择、代价、状态与认知变化；
- `relationship_changes[]`：本章真正发生变化的关系；
- `planned_assertions[]`：计划在正文中成立的事实或信息揭示；
- `foreshadow_actions[]`：伏笔动作与下一处理窗口；
- `chapter_handoff`：离场状态、未完成动作、情绪/知识延续和下一章压力；
- `freedom_envelope`：允许 Writer 自主创造的范围。

Detail 的权威关系固定为：

1. 场景 `entry_state` / `exit_state` 是场景边界权威。
2. 章级 `state_in` 由首场 `entry_state` 投影。
3. 章级 `state_out` 由末场 `exit_state` 投影。
4. `chapter_handoff` 引用末场 `handoff_id`，不复制另一份状态描述。
5. 后一场 `handoff_in_id` 引用前一场 `handoff_out_id`，不要求逐字复制自然语言。
6. Wiki 候选由 `planned_assertions[]` 派生，模型不重复填写相同事实。

场景数量默认 1-3，但不是全局硬上限。高潮、群像汇合或复杂调查章可以在明确预算下扩展；系统检查的是场景是否各自造成有效变化，而不是是否命中固定数量。

### 4.6 Chapter Text：Prose Realization

正文只回答“这份剧本怎样在人物身上自然发生”。

Writer 必须遵守：

- 当前场景的进入状态；
- 当前人物的欲望、认知和错误信念；
- 必须发生的选择、转折和代价；
- 世界硬事实与 POV 权限；
- 必须抵达的离场状态；
- 与上一章、上一场和上一卷的承接。

Writer 可以自由决定：

- 动作的具体实施方式；
- 对白、停顿、潜台词和身体反应；
- 感官焦点与环境细节；
- 句法、段落长度和叙述节奏；
- 不改变核心结果的局部策略和意外；
- 如何以人物性格而非计划术语表现既定选择。

Writer Prompt 中不得出现：

- 最低质量分；
- Reviewer 检查目录；
- AI 检测或模板味评分；
- Canon/Wiki 写回协议；
- 全量人物图、全量历史章节或全量资料库；
- “触发某门会被阻断”一类后台措辞；
- 要求逐字复刻细纲表述的指令。

### 4.7 Cover 与 Export

Cover 依赖稳定的 Story DNA、题材定位、主要人物和作品标题，不强依赖正文全部完成。允许在 Info 确认后生成概念方向，在 Summary/Outline 稳定后生成正式候选；最终 Export 只引用用户选中的有效版本。

Export 可以随时生成预览清单，但正式包必须绑定当前章节版本、封面版本、Canon revision 和校验结果。

## 5. Detail 的三个编译产物

### 5.1 Author Chapter Plan

面向用户的章节剧本视图，强调可阅读性：

```text
本章承接
本章核心变化
人物选择与代价
信息揭示与误解
伏笔动作
场景推进
章末结果
下一章压力
```

它由结构化 Blueprint 投影，不是另一份可独立漂移的模型长文。

### 5.2 Scene Execution Brief

面向 Writer 的唯一剧情输入：

```text
身份：当前 POV 与时间地点
必须承接：上一场/上一章已经发生的结果
本场任务：目标、阻力、策略与不可逆转折
人物选择：欲望、可知信息、错误信念、选择与代价
必须抵达：离场状态和 handoff
最小硬事实：当前场相关的 Canon / 状态
表达差量：1-3 条本场风格信号
创作自由区：允许自主决定的具体表现
```

Execution Brief 是确定性编译结果，默认不增加 Planner 模型调用。

### 5.3 Plan Ledger

面向章后 Reality Reconciliation：

- 每个计划项有稳定 ID；
- 每项绑定来源 Detail 签名和 scene ID；
- 只描述预期变化和证据目标；
- 不包含文学评分；
- 不提前写 Canon。

## 6. 正文 Context 合同

### 6.1 权威顺序

正文 Context 的冲突优先级固定为：

1. 已冻结正文现实与上一章最终交接；
2. 已提交 Canon 和当前有效 Narrative World State；
3. 当前场 Scene Execution Brief；
4. 当前章尚未执行的 Detail 计划；
5. 当前场命中的远期伏笔或事实；
6. 表达偏好。

计划不得覆盖已经发生的正文现实；表达偏好不得覆盖剧情和事实。

### 6.2 每次 Writer 调用只包含

- 一个身份和写作任务；
- 一个 Scene Execution Brief；
- 上一场实际尾文，或第一场所需的上一章冻结尾文；
- 当前 POV 的最小认知快照；
- 当前场相关的少量硬事实；
- 当前场表达差量；
- 纯正文输出合同。

### 6.3 明确排除

- 完整 Story Brief；
- 完整 Summary；
- 完整 Outline；
- 完整 Detail；
- 全量 Wiki / Canon；
- 全量人物关系图；
- 用户上传资料原文；
- 质量评分和 Reviewer Prompt；
- 来源签名、事务 ID 和内部状态名称。

这些内容保留在 Context Snapshot trace 和审计层，不作为正文文字输入。

## 7. RAG 与用户资料库边界

### 7.1 启动条件

用户资料库 RAG 只有同时满足以下条件才启用：

1. 当前项目确实存在用户上传的文档；
2. 用户在 Planning 中选择“使用资料库”或选中具体文档；
3. 当前任务属于资料理解、事实引用或设定建立；
4. 检索结果能够保留文档、段落和来源标识。

没有上传资料时：

- 不执行空检索；
- 不产生“知识库暂无命中”占位 Context；
- 不阻断运行；
- 不把内置 Wiki 或联网搜索伪装成用户资料库。

### 7.2 允许使用的阶段

| 阶段 | 用户资料库 RAG | 用途 |
| --- | --- | --- |
| Planning | 只检查资料可用性 | 选择文档与策略 |
| Info | 允许，是主要消费阶段 | 提炼题材事实、世界规则、专业资料和禁区 |
| Summary | 默认读取已确认 `WorldSourcePack` | 必要时验证全书因果是否违反来源 |
| Outline | 不直接检索原库 | 消费已确认的来源投影 |
| Detail | 不直接检索原库 | 消费世界规则与专业事实卡 |
| Chapter Text | 禁止 | Writer 不临时查资料库，不自行裁决来源 |
| Cover | 不使用 | 只消费作品定位和视觉 brief |
| Export | 不使用 | 只做交付校验 |

### 7.3 World Source Pack

Info 阶段将用户资料检索结果提炼为 `WorldSourcePack`：

- 来源文档与段落；
- 可使用的事实卡；
- 仅供参考的风格/结构信号；
- 禁止直接复制的表达；
- 资料之间的冲突；
- 用户确认后的世界规则投影。

后续阶段只读取已确认投影，不反复查询原始资料库。

### 7.4 章间检索不是用户资料库 RAG

正文连续性使用另一套来源：

- 最近 2-3 章：直接读取冻结 `ContinuityLedger`；
- 当前卷状态：直接读取 Narrative World State；
- 远期人物、物件、伏笔和历史事实：按风险从 Canon/Wiki 索引召回；
- 当前 Detail 已拥有的内容：禁止再次检索。

这属于内部叙事状态检索，不得与“用户上传资料库 RAG”混为同一开关、指标或 UI 状态。

## 8. 质量运行时重新分层

### 8.1 L0：生成信封，所有模式硬门

- Provider 调用失败；
- 空正文；
- 明显截断；
- 不是纯正文；
- 当前场完全没有形成可执行离场状态；
- Artifact 无法持久化或恢复。

### 8.2 L1：叙事完整性，按模式处理

- Canon 硬冲突；
- 当前 POV 获得不可能知道的信息；
- 人物死亡、地点、物件持有、时间等状态冲突；
- 上一章结果和本章进入状态无法连接；
- 当前场改变了剧本规定的核心转折或代价。

这些问题需要确定性证据，不允许仅凭总体印象阻断。

### 8.3 L2：编辑诊断，不阻断 Fast/Balanced

- 文风漂移；
- 模板味；
- 普通段落或动作相似；
- 章长偏离软目标；
- 节奏、张力或信息增量不足；
- 伏笔证据不够醒目；
- AI 化表达风险；
- 文学总分或盲读偏好。

L2 只生成定位明确的建议。Deep 可由用户选择局部精修，但任何模式都不因 L2 触发整章自动重写。

### 8.4 长度与重复策略

- 章节和场景长度使用目标区间，不要求精确命中字数；
- 超出软区间但内容完整时只提示；
- 只有明显截断、输出失控或超过 Provider/平台安全上限时阻断；
- `scene_repetition` 只有在确认是 Provider 重复输出同一段或重复执行已完成动作时才可升级为硬问题；
- 普通语义相似、主题回声和有意复沓属于编辑诊断。

## 9. 三档模式新执行合同

| 项目 | Fast | Balanced | Deep |
| --- | --- | --- | --- |
| 目标 | 完整快速草稿 | 可读初稿 | 编辑候选稿 |
| Writer | 每场单一 Writer | 每场单一 Writer | 每场单一 Writer |
| 模型审稿 | 0 | 风险触发语义/衔接主审 | 语义主审 + 结构触发专项 |
| 自动修补 | 仅 L0 技术恢复 | 最多一次可定位局部修补 | 最多一次局部修补，用户确认 |
| 文学诊断 | 记录，不阻断 | 展示建议，不阻断 | 展示并可进入精修 |
| 人工干预 | 不要求 | 可选暂停、编辑或忽略 | 阶段/卷确认 |
| Canon/POV 硬冲突 | 不写冲突事实，进入警告队列 | 一次修补；仍失败时只在无法推导下一章状态时暂停 | 阻断并等待裁决 |
| 下一章 | 自动继续 | 默认自动继续 | 当前章确认后继续 |

Fast/Balanced 的正文可以带警告完成，但警告事实不得绕过 Reality Reconciliation 写入正式 Canon。

## 10. Agent 与 Thinking 分工

### 10.1 Planning Agent 的正确位置

默认采用确定性编译，不为每章增加一个“整理 Prompt Agent”。只有以下情况才启用窄职责 Planner：

- Detail 内存在两个互相冲突的剧情承诺；
- 卷首/卷末需要复杂交接；
- 多 POV、倒叙或时间跳跃需要先给出桥接策略；
- 角色知识和世界事实存在待裁决冲突。

Planner 只返回 3-5 项桥接或冲突裁决建议，不写正文、不新增剧情、不写 Canon。

### 10.2 Thinking 分配

- Info：资料理解或复杂设定时开启；
- Summary：复杂因果规划时开启；
- Outline：开启，用于卷级分配与兑现；
- Detail：优先开启，是最需要推理的创作阶段；
- Chapter Text：关闭或最低，让模型专注叙事表达；
- Semantic Reviewer：开启；
- 结构化抽取：关闭；
- Cold Edit：Deep 开启，结果只作诊断或局部建议。

Thinking 不是全局质量开关。它应服务决策密集任务，而不是让 Writer 在过量约束中继续推理。

## 11. 保留、收敛、替换和废弃

### 11.1 保留

- Stage Artifact 合同与确认语义；
- Prompt Compiler / Context Snapshot 的签名和审计能力；
- SceneContract 稳定 ID；
- Reality Reconciliation 五态；
- Canon / Narrative World State / Wiki 分层；
- LangGraph Chapter Shadow / Dual 的恢复与幂等机制；
- Writer、Reviewer 和写回提案的权限隔离。

### 11.2 收敛

- Detail v2 的重复状态字段收成单一权威和派生投影；
- Writer Prompt 收成 Scene Execution Brief；
- 最近章节上下文收成 2-3 章冻结账本；
- Reviewer 目录只保留给 Reviewer；
- 模式策略集中为一个可审计的决策表。

### 11.3 替换

- 自然语言 handoff 逐字相等，替换为稳定 handoff ID + 结构化状态；
- 单一 `passed` 布尔值，替换为 `production_status + diagnostics_status + writeback_status`；
- 全量上游 Artifact 注入，替换为阶段编译投影；
- 以固定场景数量判断 Detail，替换为变化有效性和预算检查；
- 用户资料库与内部 Wiki 召回共用 RAG 语义，替换为两套明确来源。

### 11.4 废弃

- 为通过文学评分自动整章重写；
- 质量未达标就连续重试；
- 精确字符删减要求；
- Writer Prompt 中的质量最低分和 Reviewer Rubric；
- 正文阶段检索用户上传资料库；
- 把检索零命中作为正文阻断条件；
- Agent 直接修改 Canon、Wiki 或后续 Detail；
- 用单一总分决定章节是否可以继续。

## 12. 目标运行流

```text
Planning: ProjectCreationSpec
  -> Info: StoryDNA (+ optional WorldSourcePack)
  -> Summary: CausalSpine
  -> Outline: VolumeProgram
  -> Detail: DetailNarrativeBlueprint
  -> Volume Rehearsal
  -> Chapter Dramatic Plan
  -> Scene Execution Brief
  -> Writer
  -> L0 Production Gate
  -> Mode-aware L1 Narrative Gate
  -> Prose Reality Extraction
  -> Reality Reconciliation
  -> Provisional Narrative State
  -> Next Scene / Next Chapter
  -> Async L2 Diagnostics
  -> Volume Audit
  -> Canon / Wiki Commit
```

相邻章节继续串行。Reviewer 可以在同一冻结正文上并行，但不能阻塞 Fast，也不能直接写事实层。

## 13. 实施波次

### Wave 21A：阶段语义与模式合同冻结

- 将本文件评审为 Phase 21 产品合同；
- 为现有所有正文 finding 建立 `L0/L1/L2` 清单；
- 列出 Fast/Balanced/Deep 当前实现与目标合同差异；
- 暂停 Phase 20F Stage / Global Graph 扩张；
- 固定现有三章失败 Run 和一组正常 Run 作为回放基线。

退出条件：每个阶段的 Artifact、用户决策、写回、下游投影和非职责均明确；没有代码行为变化。

### Wave 21B：Detail Blueprint 编译投影

- 在不破坏旧 Run 的前提下，为 Detail v2 增加 Author Chapter Plan 投影；
- 引入 handoff ID，章级状态改为派生值；
- 将事实揭示与 Wiki 候选收成 planned assertion 投影；
- 编译 Scene Execution Brief；
- 增加卷级章节链预演，先验证因果、人物轨迹、知识变化和伏笔窗口。

退出条件：同一 Blueprint 可稳定生成作者视图、Writer Brief 和 Plan Ledger，三者无平级重复权威。

### Wave 21C：Writer Prompt 与正文自由区

- Writer Prompt 移除质量分、Reviewer Rubric、写回协议和阻断措辞；
- 只保留当前 Execution Brief、承接、POV、最小事实和表达差量；
- 明确 freedom envelope；
- 长度改为软目标和宽容差；
- 校验旧 Prompt 与新 Prompt 的字符量、重复 claim 和来源优先级。

退出条件：同一事实在最终 Writer Prompt 只出现一次；Writer 不接触任何资料库原文、质量分或后台协议。

### Wave 21D：Mode-aware Quality Runtime

- 将 `passed` 拆成生产、诊断和写回三个状态；
- Fast 只执行 L0 硬门与必要现实抽取；
- Balanced 启用风险触发主审和最多一次局部修补；
- Deep 保留硬专项和人工确认；
- `scene_repetition`、长度、模板味、Voice、AI 风险重新分类；
- 无法定位的问题禁止自动修补。

退出条件：Fast/Balanced 不再被 L2 文学诊断阻断；Deep 的硬门仍有证据和恢复能力。

### Wave 21E：RAG 生命周期收敛

- Planning 明确资料选择和 RAG 开关；
- 没有上传资料时完全跳过用户资料库路径；
- Info 生成来源绑定的 WorldSourcePack；
- Summary/Outline/Detail 消费确认投影；
- Chapter Text 明确拒绝用户资料库检索句柄；
- 内部 Canon/Wiki 长程召回使用独立命名、事件和指标。

退出条件：用户资料库与内部叙事检索在配置、运行、事件和指标中均不可混淆。

### Wave 21F：三章 A/B 与单卷验收

- 同一 Story DNA、Causal Spine、Volume Program 和 Detail Blueprint 对照旧/新 Writer；
- Fast、Balanced、Deep 各生成前 3 章；
- 人工盲读相邻章承接、人物鲜明度、创造性和解释腔；
- 通过后生成 8-12 章单卷；
- 检查卷首承接、卷末结算、伏笔窗口、人物轨迹和 Canon 写回；
- 不在整本完成后才首次检查。

退出条件：新链路在质量、连续性、Token、延迟和自动完成率上均不劣于旧链路。

### Wave 21G：接入 LangGraph Chapter 主路径

- 将通过验收的新模式决策和 Brief 合同接入 Chapter Graph；
- 继续使用现有 Provider receipt、checkpoint、event adapter 和 Domain Commit 端口；
- 新 Run 通过 feature flag 灰度；
- 旧 Run 永远按旧合同恢复；
- 通过单卷验收后再恢复 Phase 20F。

退出条件：无重复 Provider、无重复计费、无重复写回，前端不感知底层运行时差异。

## 14. 验收指标

### 14.1 阶段职责

- 每个阶段只有一个权威 Artifact；
- 每个下游只消费直接上游编译投影和必要事实状态；
- Writer Prompt 不含完整祖先 Artifact；
- 计划字段不能在正文前进入 Canon。

### 14.2 Prompt 与 Context

- 单场 Writer Prompt 中同一 claim 出现次数为 1；
- 当前 Scene Execution Brief、上一实际结果和 POV 边界永不丢失；
- 典型单场正文总 Prompt 目标不超过 6K 字符，硬上限 8K；
- Context 超限时只裁剪 P2/P3，P0 冲突必须在 Provider 调用前显式失败；
- Prompt trace 记录包含/排除来源，但不保存密钥或把内部签名发给模型。

### 14.3 自动生产

- Fast 固定三章样例无需人工完成率至少 95%；
- Balanced 非 Provider 故障导致的人工停顿率低于 5%；
- Fast 每章模型审稿调用为 0；
- 任何模式不因 L2 文学评分触发整章自动重写；
- 每章质量局部修补最多一次，且不能改变 generation 次数。

### 14.4 叙事质量

- 三章相邻衔接人工盲读平均至少 4/5；
- 8-12 章单卷无未解决 Canon、POV、死亡、时间、地点和物件硬冲突；
- Detail 计划项以 `realized/superseded/deferred` 为主，`omitted` 进入诊断而非机械补写；
- 人物选择能追溯到 Detail，但正文表达不与细纲逐句同构；
- 卷首能感知上一卷后果，卷末完成本卷结算并建立下一卷压力。

### 14.5 RAG

- 无上传文档时用户资料库检索调用为 0；
- Chapter Text 用户资料库检索调用永远为 0；
- WorldSourcePack 每条事实有来源文档和段落；
- 零命中不阻断正文；
- 内部长程召回不会重复注入 Detail 已提供的当前场信息。

## 15. 兼容与迁移

- 旧 Run 的 Detail v1/v2、字符串 handoff 和现有 Context Packet 保持可读；
- 新 Run 可以先用 v2 + 编译投影，不立即要求数据迁移；
- handoff ID 和派生状态通过新版 Artifact 版本启用；
- 旧 Artifact 不伪造新 Snapshot 或新 reconciliation；
- 任何字段删除都先完成读兼容、写新格式和回放测试；
- Phase 21 不原地改变已提交 Canon，不重签旧正文；
- 当前脏工作树中的在途成果必须增量接入，禁止整包回退或替换。

## 16. 建议代码边界

以下是实施阶段的目标责任，不代表本轮已经创建模块：

```text
src/novel_workflow/stages/
  stage_projection.py              # 阶段 Artifact -> 下游最小投影
  detail_narrative_blueprint.py    # Detail 权威与派生关系
  detail_volume_rehearsal.py       # 卷级章节链确定性预演

src/novel_workflow/literary/
  scene_execution_brief.py         # Writer 唯一剧情简报
  narrative_gate_policy.py         # L0/L1/L2 与模式决策纯函数
  continuity_ledger.py             # 最近章节冻结交接

src/novel_workflow/references/
  world_source_pack.py             # 用户资料在 Info 的来源投影
  narrative_retrieval.py           # Canon/Wiki 长程召回，不是用户资料 RAG
```

API 继续只做适配；编译、检索、质量决策和写回规则不得放入 route。

## 17. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 放宽正文后出现事实漂移 | L1 保留证据型 Canon/POV/状态检查，写回继续经过 Reality Reconciliation |
| 细纲过细压制创造力 | 强制 freedom envelope，禁止规划对白、微动作和句法 |
| 细纲过松导致断层 | 卷级预演、稳定 handoff ID、人物选择链和下一章压力 |
| Fast 质量警告积累 | 不写不确定 Canon，卷末生成质量债务摘要，但不阻断生产 |
| RAG 资料被误当指令 | WorldSourcePack 只保存来源事实和参考信号，用户确认后才成为世界规则 |
| 为短 Prompt 丢失关键事实 | P0/P1 保护、签名审计和冲突前置失败，不静默截断 |
| LangGraph 迁移固化错误策略 | Phase 21F 通过前不打开新 Run Chapter Graph 主路径 |
| 为新 schema 做 Big Bang | 先投影、后新写、旧读兼容、按 Run 冻结版本 |

## 18. Definition of Done

Phase 21 只有同时满足以下条件才算完成：

1. Planning、Info、Summary、Outline、Detail、Text、Cover、Export 各有唯一职责和权威 Artifact。
2. 每个阶段明确用户决策、写回目标、下一阶段投影和非职责。
3. Detail 成为正文唯一剧情剧本，并能生成作者视图、Scene Execution Brief 和 Plan Ledger。
4. Writer 只接收当前剧本、承接、POV、最小事实和表达差量。
5. Writer 保留动作细节、对白、感官、潜台词、句法和局部策略的创作自由。
6. Fast/Balanced 不再被文学诊断和单一总分阻断。
7. Deep 保留证据型硬门、局部精修和人工定稿。
8. 用户未上传资料时不启动用户资料库 RAG。
9. Chapter Text 永不直接检索用户资料库。
10. 最近章节连续性使用冻结账本，远期事实召回与用户资料 RAG 完全分离。
11. 没有任何质量失败触发无界重试或整章自动重写。
12. 三章 A/B 和 8-12 章单卷人工盲读通过。
13. Reality Reconciliation、Canon、Wiki、恢复、预算和幂等边界保持有效。
14. 新合同通过验收后才接入 LangGraph Chapter 主路径。
15. 真实 Provider 和人工盲读完成前，不宣称已经具备自动投稿质量。

## 19. 本轮边界

本文件只冻结下一轮产品与架构计划。本轮不修改：

- Prompt 实现；
- Detail schema；
- QualityEngine；
- RAG 运行逻辑；
- LangGraph 路由；
- 前端页面；
- 真实 Provider Run。

下一步应先执行 Wave 21A 的差异审计和测试基线，不直接进入正文 Prompt 改写。
