# Phase 27：自适应故事规划与叙事逻辑重构

> 状态：**用户已指令进入实施；Wave 27.1-27.3 与 Wave 27.4 的合同/前端源码迁移已通过完整离线门，Wave 27.5 的浏览器矩阵尚未开始。浏览器门通过前仍不调用真实 Provider、不恢复旧 Run、不提交或推送。**
>
> 日期：2026-08-12。
>
> 本阶段是对 Phase 26 的语义复评，不是再加一层运行时。Phase 26 已经解决了单一 LangGraph 运行时、checkpoint、interrupt、Artifact 写回和前端观察的基础问题；本阶段解决的是更底层的产品问题：阶段是否真的在为细纲服务，分卷是否以完整故事为单位，人物是否由戏剧需要产生，正文是否只得到当前任务所需的上下文，以及模型输出是否以最少且稳定的 JSON 完成这些工作。

## 1. 复评结论

### 1.1 Phase 26 的能力增量

- LangGraph 已成为唯一生产控制面，旧 Shadow/Dual/legacy 运行路径被定义为不可回归。
- Artifact、审稿、Evidence、Outbox、SSE 和前端 read model 已被分层，Detail v1/v2 被明确淘汰。
- 人物工作台和 3D 星图已有前端基础，三章单卷离线/DeepSeek 样本已证明技术链路可以从立项走到正文候选。
- PlotPilot、FictionForge 和 LangGraph 的源码/官方文档已有初步对照。

### 1.2 暴露的语义缺陷

1. **因果顺序错误。** 现行 `info -> characters -> summary -> outline` 在故事脊柱成立前冻结人物，人物只能从 `cast_requirements` 猜出来，随后由梗概强行安放。人物数量因此是表单输入，而不是戏剧功能的结果。
2. **分卷被算术替代。** `BookScalePlan` 用 8-16 章和总章节数推算卷数，不能证明每卷有自己的承诺、危机、高潮和闭合。
3. **人物规模被章节档位替代。** `<=5/<=50/>50` 的角色数量区间不能表达多线短篇、单线长篇、POV 切换或关系拓扑压力。
4. **细纲批次没有叙事边界。** 固定每 8 章切 Detail 可能把高潮、POV 交接或时间跳跃切开。
5. **正文上下文仍接近全量注入。** 当前 chapter compiler 会把完整人物圣经、梗概、卷计划和上一章正文组合进 Prompt，模型得到的是资料堆，而不是任务说明。
6. **Artifact 仍混合核心决策和派生信息。** 角色窗口、线程动作、节奏指标、版本/预算/审稿状态重复进入 JSON，增加解析和漂移面。
7. **“质量门”容易变成创作门。** 软字数、伏笔 TTL、固定禁词和模型自评分不能直接阻断或自动修改文学内容。

### 1.3 最终取舍

- **唯一运行时：直接使用 LangGraph Graph API。** 不使用 LangChain `create_agent`、AgentExecutor、LangChain memory 或 structured-output API 作为生产入口；`langchain-core` 若由 LangGraph 传递安装，仍只是框架内部依赖。
- **阶段顺序重构为：**

  ```text
  brief -> spine -> cast -> volumes -> detail -> text -> cover -> export
  ```

  `spine` 是全书故事脊柱，`cast` 是人物编排/角色圣经，`volumes` 是分卷故事架构。现有 `summary`、`characters`、`outline` 生产 stage id 在迁移 Wave 中删除；历史 Run 只由离线归档查看器读取，不做 alias、converter 或兼容读取。
- **不新增一个只为“看起来完整”的阶段。** `spine` 取代旧 summary 的语义，`cast` 取代旧 characters 的语义，新增价值来自顺序和契约，而不是页面数量。
- **一卷先由故事闭合定义，再由确定性代码估算章数。** 章节数、卷数、角色数和正文长度都是软目标/容量诊断，不是硬剧情模板。
- **大模型只在需要创作判断的边界生成。** ID、计数、窗口、派生投影、引用集合、签名、预算和状态由代码生成；跨越上下文上限时按预先确定的叙事单元拆调用，不对坏 JSON 做修复。

## 2. 第一手资料账本

访问日期：2026-08-12。源码研究使用隔离临时克隆，未复制到产品树。

| 来源 | 版本证据 | License | 阅读重点 | Yotsuba Ink 可复用边界 |
|---|---|---|---|---|
| [LangGraph GitHub](https://github.com/langchain-ai/langgraph) | HEAD `d56666f7fbf0d380ad84cdf0cbe5aa48ab0cc086`，2026-08-08；本仓库锁定 `1.2.10` | MIT | Graph API、`Send`、subgraph、persistence、interrupt、streaming | 直接采用 Graph API；State 只放路由与 ref，领域事实仍由 Artifact/Store 持有 |
| [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) | 官方文档，访问 2026-08-12 | 文档许可遵循官方站点 | 节点签名、条件边、map-reduce、checkpoint 驱动的执行 | 用显式边表达阶段、相邻章节串行和审稿并发 |
| [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | 官方文档，访问 2026-08-12 | 文档许可遵循官方站点 | `interrupt()`、`Command(resume=...)`、节点从头重跑、幂等副作用 | 审批前不写不可逆副作用；resume 值只用于决策 |
| [LangGraph Persistence/Streaming](https://docs.langchain.com/oss/python/langgraph/persistence) / [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming) | 官方文档，访问 2026-08-12 | 文档许可遵循官方站点 | checkpointer/store 边界，typed stream v2，checkpoint/tasks/custom 事件 | Graph checkpoint 是运行状态唯一权威，SSE 只投影稳定领域事件 |
| [LangChain GitHub](https://github.com/langchain-ai/langchain) | HEAD `f78df6d9772305e29ac07ae5508b468f56a4bcd3`，2026-08-11 | MIT | `create_agent` 顶层形态、structured output 和 middleware | 不采用高层 Agent 控制面；若未来要用必须另立 RFC 和删除矩阵 |
| [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode) / [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) | 官方 API 文档，访问 2026-08-12 | 文档许可遵循官方站点 | `response_format=json_object`、必须明确要求 JSON、空输出、`finish_reason=length`、`max_tokens` | 只接受一次标准解析；空/截断/未知字段进入显式失败，不 repair、不截取、不默认补字段 |
| [PlotPilot](https://github.com/shenminglinyi/PlotPilot) | HEAD `7dc03a37a06b57e823df222da0e3bde5d1c84715`，2026-07-19；tag `v4.6.0`；仓库 2026-08-11 仍有更新元数据 | Apache-2.0 + Commons Clause v1.0 | `chapter_preplanning_service.py`、`chapter_continuity_ledger.py`、`character_narrative_kernel.py`、`prompt_assembler.py`、memory/checkpoint/structured pipeline | 只吸收“临章执行计划、连续性账本、角色上下文锁、Prompt 签名”的抽象；不复制源码、Prompt、合同或 UI。Commons Clause 禁止以软件功能为实质价值销售，法务确认前不作派生商业实现 |
| [FictionForge](https://github.com/wanqili857-byte/fictionforge) | HEAD `c381297e2c6c670f374933d850b9b85756dead27`，2026-08-06；tag `v0.2.0`；仓库 2026-08-11 仍有更新元数据 | MIT | `TickRunner`、`ChapterCoordinator`、`SpecBuilder`、`theory_of_mind.py`、`vault_sync.py`、`scripts/gen.py` | 可重写世界真相/角色认知分层、弧级模拟到临章 spec、相邻段落顺序生成；不复用其 `gen/engine/hybrid` 双管线、机械 spec、fallback 和静默降级 |
| [Brandon Sanderson 2025 Plot Guide](https://www.brandonsanderson.com/blogs/blog/brandon-sandersons-2025-guide-to-plot-lecture-2) | 作者官方课程笔记，2025-01-24 | 仅提炼原则，不复制文字 | Big P/Little p、Promise/Progress/Payoff、信息/关系/内在进展、signposting、令人意外且满足的 payoff | 将 promise、progress、payoff 变成 Spine/Volume/Detail 的检查投影，不把它们变成固定模板 |
| [Randy Ingermanson Snowflake Method](https://www.advancedfictionwriting.com/articles/snowflake-method/) | 作者官方文章，访问 2026-08-12 | 仅提炼原则，不复制文字 | 从小到大迭代设计、设计先于写作但方法不应强迫所有作者 | 采用“脊柱 -> 卷 -> 章节 -> 场景”的逐层展开，不采用固定十步或固定章数 |

## 3. 产品原则与叙事判断

### 3.1 阶段存在的唯一理由

一个阶段必须能回答四个问题：

1. **它冻结了哪个不可替代的创作决策？**
2. **用户在这一刻需要批准或编辑什么？**
3. **哪个领域 Store 会接收这份决策？**
4. **下游在没有其它上游全文的情况下只需要哪些引用？**

如果一个字段只为 UI 画图、显示计数、通过校验或复制另一阶段的叙述，它就不属于核心 Artifact。阶段不得通过堆字段制造“深度”，也不得为了让模型“记得更多”把所有上游全文塞入 Prompt。

### 3.2 一卷是完整的小故事

一卷必须拥有自己的：

- 读者承诺：本卷要让读者期待什么；
- 局部问题：谁要解决什么，失败的代价是什么；
- 不可逆高潮：人物或世界发生了不能撤回的改变；
- 余波闭合：本卷承诺得到满足、转化或有意延迟；
- 系列接口：若还有下一卷，只保留数量受控且明确命名的延续问题；它们不能代替本卷承诺的闭合，也不能把本卷结局变成半截 cliffhanger。

“8-16 章一卷”不是合同。卷的长度由闭合所需的叙事序列决定；篇幅只是软容量约束。一个短推理故事可以一卷 5 章，一个关系线复杂的卷可以 18 章；系统只在超出用户长度包络或模型容量时提出调整，而不自动删情节或补水章节。

### 3.3 章节不是小型全书

章节的责任是制造一次可感知的改变：信息、关系、选择、处境或内在信念至少有一项发生推进。一个章节可以以未解决问题结束，但不能以“没有变化”结束。Detail 只设计这一章的戏剧动作和下一章的交接，不要求每章同时完成整卷的所有人物弧和世界观解释。

### 3.4 节奏检查只做诊断

参考 Promise/Progress/Payoff 和 signposting：

- Spine 记录全书承诺和可见进展类型；
- Volume 记录本卷承诺、关键进展和闭合；
- Detail 记录每章的变化类型和交接；
- 代码派生“最近 N 章是否有变化、伏笔是否重复占用、关系是否停滞、高潮是否被分段切开”等诊断。

这些诊断不按固定百分比打回正文，不自动重写，不因字数软目标偏差而删改。

## 4. vNext 阶段闭环

### 4.1 `brief` 创作立项

| 项目 | 设计 |
|---|---|
| 唯一 Artifact | `StoryBrief` |
| 核心字段 | `premise`、`promise`、`world_rules`、`theme`、`ending_promise`、`voice`、`length_envelope` |
| 用户决定 | 作品想讲什么、读者期待什么、哪些世界规则不可违背、结局方向、声音和软篇幅包络 |
| 写回 | `ArtifactStore.brief` 新版本 |
| 下游依赖 | 只给 Spine：创作承诺、规则、主题、长度包络；不把用户上传资料全文带入 |
| 窄调用 | 若用户启用 Source Pack，规划前做一次带出处的 `source_observation`，只产生候选事实，不写 Canon |
| 硬门 | premise/promise/ending_promise 非空，长度包络可计算；不要求固定章节数 |

`length_envelope` 是用户意图，不是 `BookScalePlan`：包含可选的总字数/总章节数、软平均章节字数、最小/最大合理范围和计数标准。缺省时由题材预设提供建议，但建议必须显示为建议，不能悄悄变成硬配额。

### 4.2 `spine` 全书故事脊柱

| 项目 | 设计 |
|---|---|
| 唯一 Artifact | `StorySpine` |
| 核心字段 | `turns[] { cause, change }`、`ending`、`open_questions[]`、`progress_types[]` |
| 用户决定 | 因果链是否成立、结局是否兑现承诺、哪些问题故意留到系列后续 |
| 写回 | `ArtifactStore.spine` |
| 下游依赖 | `turns`、ending、open questions 和后续窄调用产生的 role demand refs；不依赖人物完整档案 |
| 生成方式 | 一次调用；若 turns 预计超出输出包络，按因果段落预拆为带 `segment_ref` 的多个调用，聚合前全量校验 |
| 删除内容 | 不写场景、人物行为、章节区间、卷号、完整世界百科 |

`turns` 是“因为 A，局面改变为 B”的因果骨架，而不是小说梗概散文。人物职责不是字符串规则可以可靠推导的确定性投影；Spine 通过一个窄 `RoleDemandProposal` 调用回答“需要谁承担冲突、谁必须知道什么、谁必须改变什么”，每项只返回 `demand_key/function/required_change/active_turn_refs`。代码只校验 turn refs、去重和容量，并为通过的 demand 预分配稳定 ref。只有这些抽象职责进入 Cast，不再先创建人物再强行安放；`RoleDemandProposal` 是生成工具结果，不并入 `StorySpine` 核心 Artifact。

### 4.3 `cast` 人物编排/角色圣经

| 项目 | 设计 |
|---|---|
| 唯一 Artifact | `CharacterBible` |
| 核心字段 | `subjects[] { id, name, kind, function, drive, change, debut, limits }`；`relations[] { a, b, type, pressure }`；其中 `id` 由代码绑定，不由模型创造 |
| `kind` | `protagonist`、`major`、`functional`、`npc`、`historical_record`；只有前四类可在正文中被引用，`historical_record` 不拥有当下行动或 POV |
| 用户决定 | 谁是叙事中心、哪些角色承担何种功能、关系压力是否可信、弧线和首次出现窗口是否成立 |
| 写回 | `ArtifactStore.cast`；角色 graph、星图、出场时间线均为投影 |
| 下游依赖 | 只通过 subject id 和被请求字段读取；Detail/Text 不读完整 CharacterBible |
| 新人物约束 | 下游不能直接新增主体。新增、职责升级、关系重定向或首次出现窗口变化必须产生 `CharacterChangeProposal`，绑定触发 evidence/ref 和受影响章节，经 interrupt 批准后创建新版本 |

人物数量不按总章节数公式决定。生成分两步：模型先按已分配的 demand ref 分组返回最小人物档案，不能自造 subject id；代码绑定 subject id 后，再用一个窄关系调用只返回 `a/b/type/pressure`，因此跨组关系不需要在人物档案中复制。`CastDemand` 是可重建诊断，输入为已接受的 role demands、候选 POV/线程、关系图、每卷局部冲突、首次出现拥挤度和 persistent/local 角色比。它输出建议和问题：角色承担过多独立功能、两个角色功能重复、首次出现过密、孤立角色、没有叙事中心。唯一硬门是角色引用可解析、至少一个叙事中心、所有被点名主体先注册；建议数量可被用户接受或修改。

必要 NPC 可以先冻结为功能槽位：有稳定 id、用途、首次窗口和 limits，但不要求长档案。Detail 可以给槽位填充现场姓名作为局部呈现，不能把槽位升级成独立弧线或跨卷关系。

### 4.4 `volumes` 自适应分卷架构

| 项目 | 设计 |
|---|---|
| 唯一 Artifact | `VolumeArchitecture` |
| 核心字段 | `volumes[] { id, promise, conflict, climax, closure, cast_ids, thread_ids, length_hint }` |
| 用户决定 | 每卷是否像一个完整故事、卷间承接是否值得继续、角色/线程分配是否过载 |
| 写回 | `ArtifactStore.volumes` |
| 下游依赖 | 当前卷的 promise/conflict/climax/closure、cast_ids/thread_ids、length_hint；不读其它卷全文 |
| 删除内容 | `character_windows.entry_state/exit_state/turn_id`、线程 action、机械 chapter window |

卷的候选数由 Spine 的不可逆转折、局部 closure 和系列开放问题共同决定，但“哪里自然闭合”属于创作判断，不伪装成规则算法。一个窄 `VolumeBoundaryProposal` 调用只返回候选 turn ranges 和边界理由；代码校验顺序、覆盖、重叠、引用和容量。随后模型为通过的候选单元写卷合同，确定性 `VolumeAllocator` 再在用户长度包络内估算章节区间。`id` 由代码绑定；`length_hint` 只是“短/中/长”或建议章数，不是锁定窗口。每个卷必须通过结构硬校验和人工 closure review：promise、conflict、climax、closure 非空，turn refs 连续且可达；不能因为总字数不够就把完整高潮拆到下一卷。

章节数量分配依据：卷内转折数量、必要 POV 交接、地点/时间 discontinuity、关系线并发、场景密度和用户软长度。分配结果是 `ScaleProjection`，用户可以在 Detail 前调整；调整只重新计算尚未冻结的窗口，不改写已接受 Artifact。

### 4.5 `detail` 章节施工图

| 项目 | 设计 |
|---|---|
| 唯一 Artifact | `DetailPlan`，按卷/段保存章节施工图 |
| 核心字段 | `chapters[] { ref, purpose, pov, scenes[], handoff }`；scene 为 `{ place, objective, conflict, turn, result }` |
| 用户决定 | 每章是否推进、场景顺序是否有戏、章节结尾是否把下一章接上 |
| 写回 | `ArtifactStore.detail`；段落候选必须一次性通过引用和连续性校验后提交 |
| 下游依赖 | 当前 chapter manifest、选中的 subject dossiers、active thread refs、上一章 handoff |
| 删除内容 | 重复 synopsis/act/key-turn、自由 foreshadow action、重复 obligation prose、模型生成的章节 id |

Detail 是真正的剧本阶段：它负责具体人物会做什么、在什么场景里受什么阻力、发生什么转折、结果如何影响下一章。Outline/Volumes 只声明本卷相关人物和线程引用，不提前替 Detail 写行为。

Detail 默认按卷生成；大卷按叙事边界分段，而不是固定 8 章。可切分边界包括 act/sequence 结束、主要转折后、POV handoff、地点/时间断裂和独立线程窗口。每个段都有不可变 `DetailSegmentHandoff { previous_ref, promises, unresolved, next_ref }`。只有 token/JSON 容量是硬上限；若一段过大，先由确定性 planner 重新切段，再调用模型。

### 4.6 `text` 正文

Provider 的正文输出是单章纯文本流，不包 JSON；标题优先来自已批准 Detail，确需调整时使用独立的短元数据调用。代码将冻结的 chapter ref、标题与完整文本组装为 `ChapterDraftResult`；`version_id`、word count、author status、attempt 和 receipt 均由代码确定。正文 Prompt 不注入所有上游 Artifact，只接收 `ChapterContextManifest`（见第 8 节）。

相邻章节串行生成。固定审稿角色可用 LangGraph `Send` 对同一不可变章节版本并行只读；审稿不自动改文。用户选择接受、人工编辑、定向修订或保留分支后，才进入 ChapterStore 和 Evidence proposal。

### 4.7 `cover` 与 `export`

Cover 只消费已接受正文的标题、简介、主题和用户视觉决策；图片 Provider 失败显式停图，不回退 fake 资产。Export 只消费接受版本和资产 ref，不调用文本 Provider，不反推 Artifact。

## 5. 自适应规模模型

### 5.1 `LengthEnvelope` 与 `NarrativeScaleProfile`

`LengthEnvelope` 是 brief 的用户输入；`NarrativeScaleProfile` 是确定性投影，包含：

- `word_target_soft`、`chapter_target_soft`、`chapter_min_reasonable`、`chapter_max_reasonable`；
- `json_item_caps`（按模型上下文和字段上限计算）；
- `volume_candidate_cap`、`detail_segment_char_cap`、`chapter_scene_cap`；
- `cast_pressure_budget`、`pov_pressure_budget`、`thread_pressure_budget`；
- 题材/声音预设产生的节奏建议，仅作为 UI diagnostics。

任何一个值改变，都必须重新计算 profile 并记录输入签名；不会改变已接受 Artifact。字数偏差超过软目标只产生 `length.diagnostic`。只有截断、空正文、极端超过硬容量或合同不完整才阻断。

### 5.2 动态角色规模

角色规模先问“当前故事需要哪些不可替代的戏剧功能”，再检查候选人物是否过载。创作性的 role demand 来自 `RoleDemandProposal`；代码只在候选人物与关系已经存在后计算压力诊断：

```text
pressure = concurrent_threads
         + pov_load
         + relationship_edges
         + first_appearance_density
         + volume_local_conflicts
```

同一 subject 可以承担多个低压力功能，但当压力超过题材/篇幅 profile 的建议包络时只提出“拆分建议”，不强制增人。长篇单线故事可保持小 cast；短篇多线故事可拥有较大 cast。所有主体必须有可追溯 demand，否则是 orphan warning。这个公式不能在人物生成前决定人数，也不能把关系边数量反向伪装成生成前事实。

### 5.3 动态分卷与章节

流程：

1. Spine 生成因果 turns 和结局；
2. 窄 `VolumeBoundaryProposal` 调用提出自然的局部承诺/高潮/闭合单元，代码只校验引用、覆盖与容量；
3. 模型为每个已校验候选单元写卷契约；
4. `VolumeAllocator` 在 LengthEnvelope 内给出建议章节范围；
5. 用户批准卷契约和范围；
6. Detail 再根据具体戏剧动作分配章节，允许在未冻结处移动边界。

不允许先算出卷数再让模型填内容。卷边界的优先级高于平均章节长度；当两者冲突时，保留闭合，提示用户需要缩短或扩展包络。

## 6. JSON 输出精简与稳定协议

### 6.1 最小字段原则

- 模型只返回不可由代码推导的语义；id、排序、章节号、卷归属、计数、窗口、哈希、状态和时间戳由代码生成或绑定。
- 关系只使用稳定 subject ref；不在每个卷/章重复角色散文。
- `phase`、`purpose`、`goal`、`event` 等同义字段只保留一个语义字段；UI 标签从语义派生。
- 质量 finding、Evidence、token/cost、checkpoint、审稿 lane 和写回 receipt 永远是 sidecar。
- 空值必须符合 schema：允许为空的数组返回 `[]`，允许为空的字符串返回 `""`；不允许缺键来省 token。

### 6.2 调用单元与预算

每个调用在执行前由 `OutputBudgetPlanner` 根据 `expected_items × field_char_caps + envelope` 计算 `max_tokens`，并绑定到 Run。建议上限不是剧情要求：

| 调用 | 默认 unit | 目标返回体 | 拆分条件 |
|---|---|---:|---|
| brief | 作品 | 7 个核心字段，约 600-900 tokens | 用户 Source Pack 只作为独立观察结果 |
| spine | 因果段 | 4-12 个 turns，约 900-1800 tokens | 预测超上下文时按因果段预拆 |
| role demand | 因果段 | 每项 4 个短字段，通常 3-12 项 | turn refs 超过单元容量 |
| cast dossier | demand group | 每组最多 5 个 subject，不返回关系和 subject id | role demand 超过组上限 |
| cast relation | 已绑定 subject 集 | 每条只含 4 个短字段 | 关系候选超过 profile cap |
| volume boundary | 全书 turn refs | 每项只含 turn range 与边界理由 | turn refs 超过单元容量 |
| volumes | 已校验卷候选集 | 每卷 7 个模型字段，通常 1-6 卷，id 由代码绑定 | 预测超过 cap 时按候选卷调用 |
| detail | 叙事段 | 每章 1 purpose + 2-6 scenes + handoff | 只按剧情边界或 token ceiling 拆 |
| text | 单章 | 非 JSON 的正文纯文本流；标题来自已批准 Detail 或独立短元数据 | 正文永远不和其它章节合并 |
| review/evidence | 单一窄任务 | 小 sidecar，不扩充 Artifact | 每个审稿 lane 独立调用 |

表中的数量是默认容量，不是业务硬编码；实际值由 ScaleProfile、冻结模型能力和实测保守字符/token 比计算。`OutputBudgetPlanner` 先计算最坏情况 JSON 字符数、结构开销和输出 token 余量，再决定单元大小；不能先调用再靠截断猜测边界。任何调用的 JSON 不能装下预期结果时，执行在模型调用前失败并要求重新切单元，不能依靠截断或 repair。模型返回中的稳定 ref 均由调用前下发或调用后绑定，不能让模型发明 UUID。

### 6.3 严格解析流程

本流程适用于 planning/review/evidence 的小型 JSON；正文是纯文本流，不经过 JSON parser。正文仍必须验证非空、`finish_reason`、字符硬上限和流完整性，再由代码组装 `ChapterDraftResult`。

1. Run 创建时冻结 provider/model、response mode、schema digest、prompt digest、max tokens、temperature、超时和 operation key。
2. DeepSeek 请求 `response_format: {"type":"json_object"}`，system/user 明确出现“JSON”并提供最小例子；其它 Provider 使用其官方严格 schema 能力，否则使用同样的显式 object 合同。
3. 读取完整响应，若 content 为空、`finish_reason == "length"`、非 object、Markdown fence、前后夹杂文本、标准 `json.loads` 失败、Pydantic strict schema 失败或存在未知字段，立即记录失败 receipt。
4. 不做对象截取、`json_repair`、字段 alias、converter、默认值注入、未知键丢弃、自动重试到另一个合同或 fallback Provider。
5. 可重试只限基础设施层明确的 transport failure，并使用同一 operation key、同一 schema、同一 prompt snapshot；格式失败进入 interrupt/failed，由用户决定是否重新生成同一单元。
6. 校验通过后，代码分配确定性 id、排序和派生字段；只有整组单元通过引用/容量/闭合检查才生成候选 Artifact，禁止部分写回。

## 7. Artifact、投影和 sidecar 删除矩阵

| 当前/历史路径 | Phase 27 处理 | 生产状态 |
|---|---|---|
| `info`、`StoryBriefArtifact` | 删除旧 stage id，迁移为 `brief` 新合同 | 旧 Run 仅归档读取 |
| `summary` | 删除 stage id，改为 `spine` | 不做 summary alias |
| `characters` | 删除 stage id，改为 `cast` | 不做 characters converter |
| `outline`、`BookScalePlan` 固定窗口 | 删除机械章数/卷数权威，迁移为 `volumes` + `LengthEnvelope` + `ScaleProfile` | 旧字段不可读取 |
| Detail v1/v2/v3 和任何 `detail_*` 兼容层 | 物理删除生产 schema、prompt、parser、converter 和 fallback | 历史 Run 只读离线查看 |
| `new_characters`、自由角色快照、卷内 character entry/exit/action | 删除；下游只能引用 `CharacterBible` 或提交 change proposal | 不允许隐式增人 |
| `foreshadow_actions`、`wiki_candidates`、`fact_reveals`、模型自评分 | 删除核心 Artifact 字段 | 由正文 Evidence sidecar 提案 |
| `schema_version`、alias、normalizer、repair、default injection、unknown-key drop | 删除 | 静态扫描阻止回归 |
| 全量 Graph State 中的 Artifact 正文 | 删除 | State 只保存 ref、cursor、decision、failure、context manifest ref |
| 旧 Runner、Shadow、Dual、legacy selector、fallback reviewer | 删除并设置静态退出门 | 生产只有 LangGraph |
| 历史 Run | 复制到物理隔离 archive viewer | 无 start/resume/decision/branch/provider/writeback |

## 8. Context Manifest：让模型知道去哪看

### 8.1 Manifest 结构

正文调用只接收签名的 `ChapterContextManifest` sidecar：

```text
task: chapter_ref
required: [chapter_script_ref, volume_contract_ref, pov_dossier_ref]
optional: [active_thread_refs, world_rule_refs, previous_handoff_ref]
forbidden: [full_canon, full_wiki, unrelated_characters, full_previous_chapter]
snippets: [{ref, purpose, text, source_hash}]
budget: {input_chars, output_tokens}
manifest_hash: ...
```

`required` 是当前章节不可缺的最小资料；`optional` 由确定性引用解析器按当前 chapter refs 选择；`forbidden` 用于静态/运行时断言，避免意外全量注入。上一章默认只给 handoff 和短尾部/确定性 recap，不给全文；只有当前场景明确需要时才读取可定位片段。

### 8.2 Resolver 顺序

1. 读取当前 Detail 章节脚本和 Volume contract；
2. 根据 `pov`、场景 subject refs、地点和 active thread refs 选择最小人物/世界片段；
3. 加入上一章 handoff、尚未完成的动作和本章必须兑现的 promise；
4. 通过 source hash、Artifact version 和 manifest policy 签名；
5. 若超出预算，先按优先级删除 optional，再失败；不向模型开放任意检索工具。

### 8.3 Memory/Wiki/Canon/RAG 边界

- **Canon**：用户批准的创作事实权威；只接受带 Evidence 的 proposal。
- **Wiki**：正文 Evidence 形成的低敏感事实索引；可有 `candidate/confirmed/superseded`，不直接改变剧情。
- **Memory**：运行期间的手段/状态投影，服务连续性，不作为事实权威。
- **RAG**：只在用户上传并选中的 Source Pack，于 brief/spine/volumes 前置规划阶段读取；每条结果带 URL/文件 ref、片段 hash、采用状态。正文节点禁止盲检索。
- **Evidence**：正文中可定位的 span 和 claim proposal；模型不能直接写 Canon/Wiki。

这些系统只提供证据和建议，不能把创作锁死。低置信度冲突是诊断或人工确认，不是自动删改；字数和伏笔也采用软目标与合理容错。

## 9. LangGraph State、Node、Edge、interrupt、checkpoint

### 9.1 根 State

根图 State 只保存可恢复路由，不复制 Artifact：

```text
RunState {
  run_id, graph_revision, stage_cursor,
  artifact_refs, current_unit_ref, chapter_cursor,
  scale_profile_ref, context_manifest_ref,
  pending_decision_ref, pending_review_refs,
  last_failure_ref, last_checkpoint_ref, state_revision
}
```

Artifact、Chapter、Evidence、Canon、Wiki、Outbox 和 Provider receipt 各自拥有 Store；Graph State 仅保存引用和 cursor。用户编辑生成新候选 ref，不在 checkpoint 内原地修改旧 Artifact。

### 9.2 图节点与边

- `load_run -> brief.generate -> brief.review -> brief.commit`
- `brief.commit -> spine.generate -> spine.review -> spine.commit`
- `spine.commit -> derive.cast_demand -> cast.generate[group] -> cast.review -> cast.commit`
- `cast.commit -> volumes.generate -> volumes.review -> volumes.commit`
- `volumes.commit -> detail.plan_segment -> detail.generate -> detail.review -> detail.commit`
- `detail.commit -> chapter.prepare_context -> chapter.generate`
- `chapter.generate -> chapter.review.map` 使用 `Send` 并行只读 lane；全部 receipt 汇聚后进入 `chapter.decision`
- `chapter.decision -> chapter.writeback -> next_chapter`；相邻章节不并行
- 全部章节接受后 `cover -> export -> complete`

条件边只依据持久化 decision/status/ref，不依据前端事件或模型自由跳转。审批节点使用 `interrupt()`；resume 时节点会从头执行，因此 interrupt 前的调用/写回必须幂等，或拆到独立已提交节点。错误进入显式 `failed`/`awaiting_user`，不回落到旧 Runner。

### 9.3 并发、checkpoint 与 SSE

- 审稿 `Send` lane 接收同一不可变 chapter version；每条 review operation 有 receipt，汇聚只写 review sidecar。
- 生产单进程使用持久 `AsyncSqliteSaver`；多进程部署另立迁移后使用 `AsyncPostgresSaver`。`InMemorySaver` 只用于离线测试，不得生产。
- `thread_id = run_id`，checkpoint 只保存 graph state、next tasks、interrupt 和 namespace；长期偏好/低敏感投影使用 Store。
- 采用 LangGraph typed stream v2 的 updates/checkpoints/tasks/custom 作为内部输入，API 层只投影 `run/node/artifact/decision/review/evidence/writeback/checkpoint` 稳定事件。前端永远不消费 raw State、message history 或模型 token 作为权威。

## 10. 前端工作台重构映射

契约冻结后才生成原型图。原型只用于确实改变布局的 `spine`、`volumes`、`detail` 和 `cast` 页面；人物星图沿用已有依赖和风格，不新增地球语义或第二图运行时。生图使用仓库已配置的 `gpt-image-gen` skill，生成的是视觉参考，不成为产品资产或交互合同。

| 页面 | 主要信息 | 交互与后端边界 |
|---|---|---|
| Stage Nav | `brief → spine → cast → volumes → detail → text → cover → export` | 只显示后端 stage/readiness，不从旧 stage id 推断 |
| Brief Workbench | 承诺、规则、主题、长度包络 | 保存草稿与 commit decision 分离；Source Pack 显示出处和采用状态 |
| Spine Workbench | 因果 turns、ending、open questions、progress diagnostics | 编辑 cause/change；不出现角色行为脚本或章节填空 |
| Character Workbench | 3D 星图、关系邻域、档案、出场窗口、change proposal | 节点代表 subject；点击查看最小 dossier；新人物只能走 proposal + interrupt |
| Volumes Board | 一卷一张完整故事卡：promise/conflict/climax/closure、cast/thread refs、建议长度 | 拖动只改变未冻结分配；闭合诊断来自代码 |
| Detail Workbench | 卷/段导航、章节施工账本、场景序列、handoff、Context Manifest 预览 | 重点编辑“谁在何处做什么导致什么变化”，不展示全量上游 JSON |
| Text Workbench | 正文、章节版本、审稿 finding、接受/编辑/修订/分支 | 只显示当前章节和必要引用；审稿不自动覆盖正文 |
| Runtime Cockpit | node、checkpoint、review lanes、预算、失败 evidence、writeback | 读取事件和 read model；断线重连按 sequence，不控制执行生命周期 |

UI 派生的角色计数、卷章数、节奏条、引用列表、完整性 badge 和状态颜色均可删除重建，不能写回核心 Artifact。所有页面必须能在 390px 和桌面宽度下保持语义密度，不用装饰卡片填空。

## 11. 迁移 Waves 与退出门

### Wave 27.0：文档评审门（已通过实施授权）

用户已在 2026-08-12 明确要求按 Phase 27 继续完整重构，确认直接 LangGraph、八阶段顺序、自适应分卷/人物、精简 JSON、Context Manifest、UI 同步和最终一次 GitHub main 发布。该授权允许进入离线实施，不等于允许提前调用真实 Provider 或发布。

### Wave 27.1：契约与删除矩阵

建立新 Pydantic/TypeScript contracts、schema digest、ScaleProfile、CastDemand、VolumeArchitecture、ContextManifest；同时删除旧 stage/schema 的生产引用。退出门：静态扫描无 summary/characters/outline/detail v1/v2/v3/fallback/alias/converter/repair 生产引用，历史 archive 路径不可启动 Graph。

### Wave 27.2：Graph 与领域 Store

重构 root graph、stage/chapter/review subgraph、interrupt/checkpoint、operation receipt 和 SSE projection。退出门：fake Provider 能从 brief 到 export 重放；断线、进程故障、重复 resume、重复 review/writeback 都 exactly-once；无第二 Runner。

### Wave 27.3：阶段生成与 Context Resolver

按新单元调用 Provider，接入严格 JSON、OutputBudgetPlanner、closure/cast/continuity diagnostics 和 Context Manifest。退出门：空/截断/未知键/非法 JSON 均显式失败；没有隐藏重试或自动补字段；可重建 projection。

### Wave 27.4：前端工作台

按新 stage ids 重做导航、Spine、Cast、Volumes、Detail 和 runtime context rail；保留 3D 星图为语义投影。退出门：浏览器矩阵、390px/桌面、SSE 重连、decision/写回状态和 proposal interrupt 与后端合同一致。

### Wave 27.5：离线质量门

覆盖 schema/property、graph fault injection、checkpoint recovery、parallel review、archive isolation、context budget、scale profile、cast demand、volume closure、Evidence/Outbox 和前端 reducer。退出门：全量离线测试/build/browser 通过，真实 Provider 仍未调用。

### Wave 27.6：新 Run 真实验证

仅在用户评审和 Wave 27.5 通过后，使用 secret-store 中的 DeepSeek 绑定创建全新 Run；禁止恢复 `phase26-deepseek-three-gate-dcf5623f-2` 或任何旧 Run。顺序为：

1. 一个短篇单卷，验证 brief/spine/cast/volumes/detail；
2. 三章新 Evidence/review/writeback 门禁，人工冷读；
3. 通过后再做 8-12 章单卷完整故事；
4. 只有单卷闭合、章节连续、正文质量和成本均通过，才进行第一卷全量模拟。

真实 Run 不以“JSON 通过”代替文学验收。人工冷读记录承诺兑现、进展 signpost、角色能动性、场景变化、卷闭合、套话密度和上下文泄漏；失败时回到契约/Context/分段的底层问题，不增加 fallback 或局部补丁。

## 12. 测试与真实 Provider 验收矩阵

| 门 | 证明内容 | 不证明什么 |
|---|---|---|
| Contract | strict schema、最少字段、未知键/空/截断失败 | 不证明文学质量 |
| Graph | node/edge/interrupt/checkpoint/Send/receipt 恢复 | 不证明真实 Provider 的内容好坏 |
| Context | manifest 选择正确、禁用全量 dump、预算稳定 | 不证明模型一定遵守文风 |
| Scale | cast/volume/chapter 自适应投影可重建 | 不证明卷闭合自动成立 |
| Browser | 导航、星图、表单、运行观察、写回状态 | 不证明后端真实执行 |
| Fake Provider | 全图、故障注入、分支、archive isolation | 不证明真实 token/cost |
| DeepSeek three-gate | 新 Run、严格 JSON、三章 Evidence exactly-once | 不证明 8-12 章或投稿质量 |
| Single-volume cold read | 卷闭合、人物弧、节奏、连续性、套话和 Context leakage | 不证明其它题材 |
| Submission simulation | 第一卷全量、人工审读、成本/延迟/恢复记录 | 不等于出版或市场成功 |

## 13. GitHub 发布与分支约束

本轮计划阶段不 push。实施和所有离线/浏览器/新 Run 验收完成后，才做一次范围审查、提交并推送 GitHub `main`。Gitee 不参与发布；不得在未证明合并安全前删除任何分支。安全顺序为：只读检查工作树和远端、确认目标 commit/未合并提交及用户改动归属、在评审通过后合并到 `main`、验证 CI 和远端提交可见、最后才讨论删除已合并分支。禁止 reset、revert、覆盖用户脏改动、强推和把 secret 写入仓库。

## 14. 本阶段明确拒绝的方案

- 用 LangChain Agent 再包一层 LangGraph；
- 保留旧 stage id 作为 alias/converter；
- Detail v1/v2/v3 并行读取或自动迁移；
- 固定 8-16 章卷、固定每 8 章 Detail、固定总章节角色配额；
- 正文节点盲 RAG、全量 Canon/Wiki/真相表注入；
- JSON repair、对象截取、字段补齐、静默降级、fallback Provider/Reviewer；
- 审稿直接改正文、Evidence 直接写 Canon、字数偏差自动删改；
- 为 UI 添加无下游价值的 JSON 字段；
- 在真实 Provider 未通过前启动服务、恢复旧 Run 或推送 Git。

Phase 27 的成功不是“阶段更多”或“返回 JSON 更大”，而是用更少的核心决策让 Detail 形成可执行剧本，让 Text 在有限上下文内完成有约束的创作，并且每个失败都能沿唯一 LangGraph 路径被定位、恢复或明确交给用户。

## 15. 2026-08-12 实施证据（滚动更新）

- 当前生产合同已断代为 `brief -> spine -> cast -> volumes -> detail -> text -> cover -> export`；Run 创建只接受项目绑定的 `workflow_id`，Provider、Prompt、workflow revision/digest 和 quality mode 由后端冻结。
- `ScaleProfile` 已从客户端输入移除。客户端只提交用户的 `LengthEnvelope`，后端确定性派生并冻结容量投影；提交旧 `scale_profile`、Provider bindings 或旧 workflow 合同会明确返回 422/409。
- 本地旧 workflow JSON 保留为用户数据，但列表、读取、复制、项目创建和生产 Run 均不能执行它们；未物理删除或转换。
- 正文 Prompt 物料只允许一个签名 `chapter_context_manifest`；章节修订方向是 Manifest 内的 `revision.request` snippet，不会扩成第二个正文物料键。规划/审稿/Evidence 仍执行一次完整 JSON object 解析，正文执行单章纯文本流。
- Graph 故障注入已覆盖阶段 interrupt/checkpoint、并行 review `Send` super-step 的 lane receipt 重放、Provider receipt 成功后恢复、Outbox 在 Canon/Wiki/receipt 边界的幂等恢复，以及从 checkpoint 重建被污染 read model；SSE API 已证明 `after=N` 只续接更大的 domain sequence。
- 生产静态缺席门现覆盖整个 `src/novel_workflow`、整个 frontend pipeline 生产 TypeScript、默认 workflow 和所有默认 Prompt；无旧 stage assignment、`BookScalePlan`、旧 Artifact/ChapterPlan、Detail v1/v2/v3、第二 Runner、fallback Provider/Reviewer 或直接 LangChain import。离线归档 viewer 与生产 Graph/Store 物理隔离，只暴露 list/read 且所有执行能力为 false。
- 截至本节更新，完整离线基线为后端 `276 passed`、前端 `356 passed`；`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、Skill 校验、`git diff --check` 和 production closure audit 均通过。构建中的 3D 图 vendor 大 chunk 已独立懒加载，不进入首屏执行路径。
- 本证据只关闭 contract/fake Provider/Graph/frontend source 离线门。桌面与 390px 浏览器矩阵、真实 SSE 断线交互、全新 DeepSeek Run、三章人工冷读、8-12 章单卷、投稿模拟和 GitHub 发布仍未验收，不得据此宣称 Phase 27 生产闭环完成。
