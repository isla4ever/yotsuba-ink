# Phase 27：自适应故事规划与叙事逻辑重构

> 状态：**Phase 27 生产闭环已于 2026-08-17 完成 v1.0 Demo 收口。历史 29.33/29.34 失败记录仍保留为设计证据；当前权威证据是全新的 `official-deepseek-balanced` 长篇 Run `balanced-110k-v1-demo-20260817-040033`：8/8 阶段完成、44 章、107,613 个非空白字符、Export ZIP 可用，终态作品库打开走静态快照且不重放历史 SSE。低置信 reviewer finding、AI 味和文学偏好已降级为后续记录，不阻断本次 Demo 发布。**
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
- **一卷先由故事闭合定义，再由确定性代码分配章数。** 章节数、卷数和 Spine turn 数由冻结编辑政策确定性计算；角色数量由动态最小培养容量与不可合并 Role Demand 双重约束；正文长度仍是按章节负载分配的软目标带，不是硬剧情模板。
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
| [阅文作家专区：章节篇幅建议](https://write.qq.com/portal/content/5334622703010001) / [章节字数答疑](https://write.qq.com/portal/content/5335955104795501) / [作家问答](https://write.qq.com/ask/qtuyclw) | 阅文官方创作资料，复核 2026-08-16 | 仅提炼编辑建议，不复制原文 | 常见网文章长约 2000-4000 字、约 2500-3000 字可作为稳定中心，章节长度应大致统一 | 产品默认冻结 2000-3000 字、首选 2500；没有找到统一卷章数标准，因此 8-20 章/卷、首选 14 明确标为 Yotsuba Ink 产品政策 |

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

`length_envelope` 是用户意图，不是 `BookScalePlan`：只包含可选的全书字符目标与章数偏好。合理章长、单场承载、Spine 每 turn 章节承载密度和相邻章节奏带属于系统冻结的 `NarrativeCapacityPolicy`，不能由 Provider 或 Detail 反向改写。

### 4.2 `spine` 全书故事脊柱

| 项目 | 设计 |
|---|---|
| 唯一 Artifact | `StorySpine` |
| 核心字段 | `turns[] { cause, change }`、`ending`、`open_questions[]`、`progress_types[]` |
| 用户决定 | 因果链是否成立、结局是否兑现承诺、哪些问题故意留到系列后续 |
| 写回 | `ArtifactStore.spine` |
| 下游依赖 | `turns`、ending、open questions 和后续窄调用产生的 role demand refs；不依赖人物完整档案 |
| 生成方式 | 一次调用；调用前按冻结 turn 上界计算输出预算，Provider ceiling 不足时明确失败并要求新 Run 使用更高预算，不截断、不隐藏分段 |
| 删除内容 | 不写场景、人物行为、章节区间、卷号、完整世界百科 |

`turns` 是“因为 A，局面改变为 B”的因果骨架，而不是小说梗概散文。人物职责不是字符串规则可以可靠推导的确定性投影；Cast 通过一个窄 `RoleDemandProposal` 调用回答“需要哪些当下行动者，以及哪些贯穿证据、记忆或关系的历史主体”，每项只返回 `demand_key/subject_mode/function/required_change/active_turn_refs`。`subject_mode` 只允许 `actor|historical_record`；后者必须由多个 Spine turn 持续引用其身份、声音、证词、遗物或缺席，且下游必须稳定引用，`required_change` 只描述其记录或遗产的叙事意义变化。代码校验 turn refs、去重、容量和 dossier kind，并为通过的 demand 预分配携带同一模式的稳定 ref。只有这些抽象职责进入 Cast，不再先创建人物再强行安放；`RoleDemandProposal` 是 Cast binding 下的生成工具结果，不并入 `StorySpine` 核心 Artifact。

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

人物数量不由篇幅、章节数、线程数或 POV 数直接指定。生成分两步：模型先从已定稿 Spine 提取不可合并的行动职责；每项 demand 必须引用能证明独立主体必要性的 `active_turn_refs`，程序、鉴定、受理等服务默认由机构承担，除非 turns 明确要求一个会选择、阻挠、隐瞒或承担后果的持续人物。模型再按 demand ref 分组返回最小人物档案，不能自造 subject id；代码绑定 subject id 后，用一个窄关系调用只返回 `a/b/type/pressure`，因此跨组关系不需要在人物档案中复制。`active_turn_refs` 只证明职责在 Spine 的位置，不是章号；`debut` 必须根据代码冻结的精确 `scale_plan.chapter_target`，把角色第一次真正登台的 turn 映射为窄章节窗口，不能把 `turn-8` 写成 `chapter:8`。后端在 Cast 候选与人工草稿边界立即拒绝超过本 Run 精确章节槽位的值，前端窗口控件读取同一冻结篇幅政策。篇幅只投影人物建议容量与硬上限，不直接变成人数配额；实际人数仍由已接受的不可合并 role demands 决定。输出预算只约束响应承载上限，不另造第二套人数权威。

必要 NPC 可以先冻结为功能槽位：有稳定 id、用途、首次窗口和 limits，但不要求长档案。Detail 可以给槽位填充现场姓名作为局部呈现，不能把槽位升级成独立弧线或跨卷关系。

### 4.4 `volumes` 自适应分卷架构

| 项目 | 设计 |
|---|---|
| 唯一 Artifact | `VolumeArchitecture` |
| 核心字段 | `volumes[] { id, title, promise, conflict, climax, closure, turn_refs, cast_ids, length_hint }` |
| 用户决定 | 每卷是否像一个完整故事、卷间承接是否值得继续、角色引用与叙事负载是否合理 |
| 写回 | `ArtifactStore.volumes` |
| 下游依赖 | 当前卷的 promise/conflict/climax/closure、turn_refs、cast_ids、length_hint；不读其它卷全文 |
| 删除内容 | `character_windows.entry_state/exit_state/turn_id`、线程 action、机械 chapter window |

代码先由全书字数与冻结章长政策计算精确章数，再由单卷章节容量政策计算 `volume_min/target/max`；`VolumeBoundaryProposal` 必须精确返回 `volume_target` 个连续 turn ranges 和边界理由。“哪里自然闭合”仍属于模型的创作判断，但“闭合成几卷”属于代码数值权威。随后模型逐卷写合同，代码校验顺序、覆盖、重叠、引用、序列化上限、逐卷 turn 承载和全书章节容量。人物数量与 `length_hint` 都不参与章数或卷数推导。`id` 由代码绑定。每个卷必须通过结构硬校验和人工 closure review：promise、conflict、climax、closure 非空，turn refs 连续且可达；失衡边界必须退回 Volumes，不得把完整高潮拆到下一卷或让 Detail 注水。

章节布局分两层：代码按精确全书章数、精确卷数、逐卷 turn 负载、单卷容量和 turn 承载密度一次性冻结所有卷的精确章节槽位；DetailLayout 再依据必要 POV 交接、地点/时间断点、关系并发与具体台面变化，为每个槽位分配连续 turn refs 和独立戏剧任务。DetailLayout 仍按卷顺序窄调用并持有每卷独立 receipt，但后卷数量不再根据前卷模型输出动态重算；前卷少一章或多一章立即失败。只有第二层拥有事件拆演的创作权；若槽位无法在不注水、不越权新增剧情的前提下成立，就返回 `insufficient` 并退回 Spine/Volumes。

### 4.5 `detail` 章节施工图

| 项目 | 设计 |
|---|---|
| 唯一 Artifact | `DetailPlan`，按卷/段保存章节施工图 |
| 核心字段 | `chapters[] { ref, purpose, pov, scenes[], handoff }`；scene 为 `{ place, objective, conflict, turn, result }` |
| 用户决定 | 每章是否推进、场景顺序是否有戏、章节结尾是否把下一章接上 |
| 写回 | `ArtifactStore.detail`；段落候选必须一次性通过引用和连续性校验后提交 |
| 下游依赖 | 当前 chapter manifest、选中的 subject dossiers、当前卷 turns、上一章 handoff |
| 删除内容 | 重复 synopsis/act/key-turn、自由 foreshadow action、重复 obligation prose、模型生成的章节 id |

Detail 是真正的剧本阶段：它负责具体人物会做什么、在什么场景里受什么阻力、发生什么转折、结果如何影响下一章。Volumes 只声明本卷相关人物和连续 turn 引用，不提前替 Detail 写行为。

Detail 默认按卷生成；大卷按叙事边界分段，而不是固定 8 章。可切分边界包括 act/sequence 结束、主要转折后、POV handoff、地点/时间断裂和独立因果序列边界。每个段都有不可变 `DetailSegmentHandoff { previous_ref, promises, unresolved, next_ref }`。只有 token/JSON 容量是硬上限；若一段过大，先由确定性 planner 重新切段，再调用模型。

### 4.6 `text` 正文

Provider 的正文输出是单章纯文本流，不包 JSON；标题优先来自已批准 Detail，确需调整时使用独立的短元数据调用。代码将冻结的 chapter ref、标题与完整文本组装为 `ChapterDraftResult`；`version_id`、word count、author status、attempt 和 receipt 均由代码确定。正文 Prompt 不注入所有上游 Artifact，只接收 `ChapterContextManifest`（见第 8 节）。

相邻章节串行生成。固定审稿角色可用 LangGraph `Send` 对同一不可变章节版本并行只读；审稿不自动改文。用户选择接受、人工编辑、定向修订或保留分支后，才进入 ChapterStore 和 Evidence proposal。

### 4.7 `cover` 与 `export`

Cover 只消费已接受正文的标题、简介、主题和用户视觉决策；图片 Provider 失败显式停图，不回退 fake 资产。Export 只消费接受版本和资产 ref，不调用文本 Provider，不反推 Artifact。

## 5. 自适应规模模型

### 5.1 `LengthEnvelope` 与 `NarrativeScaleProfile`

`LengthEnvelope` 是 brief 的用户输入；`NarrativeScaleProfile` 是确定性投影，包含：

- `word_target_soft`；官方流程不提供章数输入，代码同时投影章节可行区间、精确章数、卷数可行区间和精确卷数；
- `json_item_caps`（按模型上下文和字段上限计算）；
- `volume_candidate_cap`、`detail_segment_char_cap` 与冻结的 `capacity_policy`；`volume_candidate_cap` 只限制单次边界提案可序列化的候选数，`capacity_policy` 定义合理章长、单卷章节容量、Spine 每 turn 章节承载密度、单场承载和相邻章节奏带；
- 题材/声音预设产生的节奏建议，仅作为 UI diagnostics。

任何一个值改变，都必须重新计算 profile 并记录输入签名；不会改变已接受 Artifact。字数偏差超过软目标只产生 `length.diagnostic`。只有截断、空正文、极端超过硬容量或合同不完整才阻断。

### 5.2 动态角色规模

角色规模只问“当前 Story Spine 需要哪些不可替代的戏剧行动者，以及哪些必须跨阶段保持身份稳定的历史主体”，再检查候选人物是否过载。创作性的 role demand 来自 Cast binding 下的 `RoleDemandProposal`，人物数量不进入 `NarrativeScaleProfile`、`NarrativeScalePlan`、深度模式覆盖项或 UI 篇幅建议。actor demand 必须以 turns 中已经冻结的行动、选择、阻力或责任为证据；historical_record demand 必须以贯穿多个 turns 的记录、证词、遗物或缺席为证据，不得为了补人物数登记只被提及一次的逝者。若同一主体能在不冲突其动机、职责和变化的前提下承担两项功能，就必须合并。人物候选存在后，关系边、首次出现密度、每卷局部冲突和一个主体承担的 demand 数才进入可重建诊断。长篇单线故事可以保持小 cast；短篇多线故事也可以拥有较大 cast。所有主体必须有可追溯 demand，否则是 orphan warning。`output_budget.item_cap` 只是 Provider 容量上限，不能被 UI、Prompt 或代码解释成人数目标。

### 5.3 动态分卷与章节

流程：

1. Scale 先由合理章长带求全书章节区间并冻结精确章数，再由单卷容量政策冻结精确卷数；
2. Spine 生成因果 turns 和结局；
3. 窄 `VolumeBoundaryProposal` 调用严格按精确卷数提出连续自然边界，代码校验数量、引用、覆盖、平衡与容量；
4. 模型为每个已校验候选单元写卷契约；
5. Scale 检查真实 turn 数能否承载冻结章数，再按各卷 turn 负载和单卷容量确定性分配精确槽位；
6. 用户批准卷契约和自然边界；
7. `DetailLayoutProposal` 逐槽决定 turn 分布与戏剧任务，不能决定章数；容量不足时明确退回前置规划。

数值层必须先冻结卷数，创作层再选择最自然的边界位置。若精确卷数内不存在可承载且闭合的边界组合，退回 Spine 或提示调整全书目标，不能让模型私自改变卷数。

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
| spine | 全书因果链 | turns 由完整章节容量与每 turn 承载密度动态推导；10 万字建议 30 个、可行域约 23-43 个 | 冻结 Provider ceiling 无法容纳上界时在调用前失败 |
| role demand | 因果段 | 每项 4 个短字段，通常 3-12 项 | turn refs 超过单元容量 |
| cast dossier | demand group | 每组最多 5 个 subject，不返回关系和 subject id | role demand 超过组上限 |
| cast relation | 已绑定 subject 集 | 每条只含 4 个短字段 | 关系候选超过 profile cap |
| volume boundary | 全书 turn refs | 每项只含 turn range 与边界理由 | turn refs 超过单元容量 |
| volumes | 已校验卷候选集 | 每卷 7 个模型字段，通常 1-6 卷，id 由代码绑定 | 预测超过 cap 时按候选卷调用 |
| detail | 叙事段 | 每章 1 purpose + 动态 scenes + handoff | 只按剧情边界或 token ceiling 拆；场景上下限由本 Run 的章长带和单场承载区间推导 |
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
optional: [world_rule_refs, previous_handoff_ref]
forbidden: [full_canon, full_wiki, unrelated_characters, full_previous_chapter]
snippets: [{ref, purpose, text, source_hash}]
budget: {input_chars, output_tokens}
manifest_hash: ...
```

`required` 是当前章节不可缺的最小资料；`optional` 由确定性引用解析器按当前 chapter refs 选择；`forbidden` 用于静态/运行时断言，避免意外全量注入。上一章默认只给 handoff 和短尾部/确定性 recap，不给全文；只有当前场景明确需要时才读取可定位片段。

### 8.2 Resolver 顺序

1. 读取当前 Detail 章节脚本和 Volume contract；
2. 根据 `pov`、场景 subject refs、地点和当前卷 turn refs 选择最小人物/世界片段；
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
| Volumes Board | 一卷一张完整故事卡：promise/conflict/climax/closure、turn/cast refs、建议长度 | 拖动只改变未冻结分配；闭合诊断来自代码 |
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
- 截至 2026-08-15，章节预算、Spine 容量合同、Cast 换稿重新派生 Role Demand、Volumes 单卷窄调用、阶段草稿持久化与 SSE sequence 续接后的最新完整离线基线为后端 `356 passed`、前端 `402 passed`；`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、`git diff --check` 和 production closure audit 均通过。闭环审计未发现 legacy runtime 标记或意外的 frontend pipeline 目录；构建中的 3D 图 vendor 大 chunk 已独立懒加载，不进入首屏执行路径。该基线不代表三章、单卷或 10 万字验收。
- 工作流配置页已在 `1440x1000`、`1280x920`、`1024x900` 和 `390x844` 验证：八阶段稿件栈、官方模板信息层级、右侧配置区、键盘切换和阶段切换后的滚动复位均正常，控制台为 0 error / 0 warning。三套官方 DeepSeek 流水线的文本和图片 Provider 均通过 `configuration_only` 准备度检查；该检查不发送真实生成请求。
- 截至 2026-08-15，本证据只关闭 contract/fake Provider/Graph/frontend source 离线门、工作流配置页浏览器门与一次真实 Run 的 SSE 中途截断续接门；当时尚未完成 10 万字长篇和 GitHub 发布。该历史状态已由本文第 16 节的 2026-08-17 v1.0 Demo 证据取代。

### 15.1 Harness H1 真实 Brief 换稿门（2026-08-15）

- 两个旧失败 Run 保持只读：`backend-run-1786727675176` 的换稿曾产生旧式 repair operation；`backend-run-1786728901000` 已删除隐藏 repair 后，Flash Brief 换稿仍因 high thinking 消耗完整 `4600` 输出上限而截断。根因位于官方 Flash 请求策略，不在 JSON repair、解析器或预算上限。
- 官方策略现把 Flash 的 `brief/cast` 固定为 `thinking.type=disabled` 且不发送 `reasoning_effort`；Pro Brief 保留 `thinking.type=enabled + reasoning_effort=high`。结构化预算测试证明 Pro 保留冻结上限，Flash 使用按 Artifact 规模计算的紧凑预算；没有增加 token 上限或兼容旧快照。
- 全新平衡模式 Run `backend-run-brief-flash-h2-20260815` 从同一项目、工作流和 10 万字输入创建。Brief 三次 Provider 草稿分别使用 `1457`、`1815`、`1985` tokens，均为 `reasoning_tokens=0`、状态成功且没有 repair operation；三份不可变输入分别为 `provider-input-4455d14293ad9525783d82df67b627565af8da8064893add4c68f251b5091b8d`、`provider-input-4f583d0950afea22158cda9cefc4bf471032cd6f088eab5656763068a38afd54` 与 `provider-input-b4e436644b53c1a8c3658198eba2b19862c2b0524c8273e864ad34862c842ff9`。递归扫描没有 Header、Authorization、API key 或 secret 键。
- 第三稿之后只做一次人工外科式编辑，没有伪装成 Provider call。最终提交 `brief-committed-c2e1f874ca2c48fc4893-31d74773`，书名与项目投影均为《盐库原件》；结局明确为林汐违法调取并修复原件、提交可验证日志、失去执业资格并触发分级重审和制度整改，关闭了“接受制裁却没有违法前因”的缺口。
- 浏览器截图为 `output/playwright/h2-flash-brief-initial.png`、`output/playwright/h2-flash-brief-regenerated.png`、`output/playwright/h2-brief-third-provider-draft.png` 与 `output/playwright/h2-brief-final-edited.png`，控制台保持 0 error / 0 warning。Brief 已正式写回并进入 Spine；该门仍只证明一个真实 Provider 单阶段及人工决策闭环，不替代三章、单卷、三档 10 万字、连续性或投稿质量验收。

### 15.2 Harness H1 Spine 换稿与容量合同门（2026-08-15）

- Spine 初稿 operation `backend-run-brief-flash-h2-20260815:spine:generate:1` 使用 `1404 + 1226 = 2630` tokens，得到 13 个转折。它能抵达 Brief 结局，但提前给弟弟和同事取名，使用“不明势力”、可拆卸记者支线和抽象改革表述，并把弟弟生死留成核心开放问题；截图为 `output/playwright/h2-spine-initial.png`。
- UI 只提交一次 Spine 换稿。operation `backend-run-brief-flash-h2-20260815:spine:generate:2` 使用 `1865 + 1118 = 2983` tokens，输入为 `provider-input-adfba6cbe04c83bb4b1e639f0e9c9eda0add162ca02396a49899fed7c501b9a1`；签名与内容寻址引用一致，递归扫描无 Header/secret，结构化解析为单一 exact object，`repairs_applied=[]`。候选 `spine-candidate-9369ab36c872b3f4be7d-6206c8f7` 回显 20 个转折并删除了新增姓名、记者支线与“不明势力”，开放问题收敛为两个后续实施问题；截图为 `output/playwright/h2-spine-regenerated.png`，控制台 0 error / 0 warning。
- 换稿仍未达到文学门：它在第 7-11 个转折已经提交证据、吊销执照、完成听证和制度改革，随后才补大潮、完整日志、弟弟结局和重复重审，形成终局提前、事件倒挂与重复收束。Run 保持 `spine / awaiting_decision`，没有确认候选，也没有进入 Cast。
- 真实证据同时发现容量合同错误：当前 10 万字平衡 Run 的冻结 `scale_plan` 是 `turn_target=20`、合法区间 `18-23`，因此初稿 13 本应失败；旧 `output_budget` 却写入 `expected_items=item_cap=8`，且非分段 Spine 绕过了候选前数量校验。现在 Spine 预算从冻结 Scale 的上界派生，默认容量上限为 24，当前 18-23 区间的预算为最多 `4726` tokens（低于官方冻结 `5000`）；候选落库前按平衡区间或精细模式用户锁定值硬校验，越界直接失败且不触发隐藏修稿。
- Spine Prompt 现要求每个 cause 直接承接上一 change、Cast 前不得给 Brief 未命名主体取名、终局只在最后一到两个转折完成，并禁止把核心案件或主要人物去向留进 open questions。生成中 UI 也不再把空候选误报为“阶段产物不是有效 JSON”；对应回归测试、全量后端 `344 passed`、前端 `381 passed`、构建与审计均通过。当前候选来自修复前冻结 Prompt，只保留为失败证据，不据此继续真实 Provider 链路。

### 15.3 Harness H1 新 Prompt Spine 闭环门（2026-08-15）

- 通过正式新建作品 UI 从最新 `official-deepseek-balanced` 创建项目 `proj-39ebbb8a60` 与项目专属工作流 `wf-proj-39ebbb8a60`，再创建 10 万字符平衡模式 Run `backend-run-1786732069818`。冻结工作流 digest 为 `fe6e6d1522493a4ce79f289ebf865ccdc2b9325ce8212151097a0b29d060a938`，Scale 建议仍为约 40 章、3 卷、Spine 20 个转折且合法区间 `18-23`；没有改写旧项目或旧 Run。
- Brief 首稿与定向换稿分别为 `brief:generate:1/2`，使用 `1516` 与 `1970` tokens；不可变输入为 `provider-input-1819766e505742b027bc0d36da3563264d52c315c3a578e12c22b4fbf5669073` 与 `provider-input-478e366048af93ac80d3d03ea1bfd3701be596eee5d22aac7f41b46fc3cd8715`。两稿均为 Flash、`reasoning_tokens=0`、无失败和无 repair。第二稿仍把失踪十年的林澈写成在事故现场被找到后自首，并弱化调档/修复规则，因此通过 UI 做一次人工外科式编辑；正式写回 `brief-committed-7a520f8c5feb42e7b588-a545725f`，书名为《潮汐证词》。截图为 `output/playwright/h3-brief-initial.png`、`h3-brief-regenerated.png` 与 `h3-brief-final-edited.png`。
- 新 Prompt 的 Spine 首稿 `spine:generate:1` 使用 `1695 + 1560 = 3255` tokens，生成 19 个转折并通过数量硬合同；它仍包含“永久失忆后又想起”、突然出现的旧友、系统后门、原件已修复又已销毁以及三次终局收束。定向换稿 `spine:generate:2` 使用 `2144 + 1222 = 3366` tokens，输入为 `provider-input-9446f03e10c62749a060a823bce13c117628da4854c8b0578f8674a54d3555eb`，生成 20 个转折且开放问题为空，但仍在第 10 条确认人物终局、第 15-17 条完成听证/处罚/整改、第 18 条又把处罚写回未决，文学门仍不通过。
- 两个 Spine Provider 结果都只沿用 Brief 已有姓名，输入 ref 与 request signature 一致，递归扫描无 Header、Authorization、API key 或 secret，结构化结果 `repairs_applied=[]`。随后通过 UI 将 20 条人工收紧为一条顺序证据链：每个 cause 使用上一 change，遗忘不可逆，物证只来自晶片/索引/授权/日志/交接单/听证，外部压力由审计、断电与大潮承担，第 18 条只完成证据纳入与比对，第 19-20 条才完成裁决、重审、处罚和制度整改。正式写回 `spine-committed-2a661e770a2550b1c1de-7ff895c5`；截图为 `output/playwright/h3-spine-initial.png`、`h3-spine-regenerated.png` 与 `h3-spine-final-edited-title-fixed.png`。
- 真实浏览器同时复现“Brief 已正式写回且 API 项目名为《潮汐证词》，运行侧栏仍显示待定书名”。前端现在只在 `artifact.committed(brief)` 后投影正式标题，并在会话启动时用 Project API 校准已错过的提交事件；候选稿和其它阶段提交不会改书名。新增纯投影合同测试，目标测试为 `11 passed`，同一真实页面已从“待定书名”更新为《潮汐证词》。
- Spine 确认后 Graph 只进入 Cast，没有跳过人物阶段。当前 Run 停在 `cast / awaiting_decision`，Brief 与 Spine 已提交，Volumes 及其后阶段仍锁定；Cast 初稿为 12 名主体、19 组关系，来自 1 次 role-demand proposal、3 个 dossier 单元和 1 次关系 proposal。全 Run 当前 9 个 Provider operation 全成功、`32534` tokens、`reasoning_tokens=0`、无 failure；但 Cast 尚未换稿或确认，林澈的历史主体归类和角色膨胀仍需下一门审查，不能据此宣称 Cast、分卷、细纲或长篇链路通过。

### 15.4 Volumes 单卷窄调用离线合同门（2026-08-15）

- 旧 Run `backend-run-1786732069818-cast-recovery-v2` 的 Volumes 冻结输入曾把三卷、完整 `story_spine` 和伪 `thread_ids` 一次性交给 Provider，模型因此提前消费相邻卷事件；候选 `volumes-candidate-a2f00cbcd7311cd45d14-6238c098` 保留为语义越界失败证据，不确认、不回填。
- 新合同按 `volume-1 -> volume-2 -> volume-3` 顺序执行三个 operation。每次只含当前卷的 `volume_spine_turns`、单个 `volume_boundary`、最小人物引用与卷序策略；第二卷起只继承上一卷已经生成的 `title + closure`。请求不再暴露完整 `story_spine`、复数 `volume_boundaries`、相邻卷 turns 或 `thread_ids`。
- Provider 单元 Schema 固定 `volumes.minItems = volumes.maxItems = 1`；代码在聚合后顺序绑定 `volume-N` 与冻结 `turn_refs`，并验证三卷对边界的完整连续覆盖。首稿 operation key 使用 `volumes:generate:1:volume-N`，换一稿使用 `volumes:generate:2:volume-N`，旧 attempt 的不可变输入和 receipt 不覆盖。
- 后端定向扩圈 `126 passed`、前端 Volumes 投影/视图定向测试 `17 passed`；随后完整门为后端 `349 passed`、前端 `394 passed`，`compileall`、TypeScript/Vite production build、CSS audit/split、`git diff --check` 和 production closure audit 全部通过。该证据只证明 fake Provider、输入隔离、Schema、聚合和 UI 投影合同，不证明真实 DeepSeek 分卷质量。
- 真实阶段组件通过 dev-only event fixture 走完整 event -> reducer -> `VolumeStageView` 投影，在 `1440x1000` 与 `390x844` 验证两卷切换、卷名、冻结 turn refs、人物引用、长度软建议和底部决策栏。页面无“叙事线程引用”，移动端 `document.scrollWidth == clientWidth == 390`，控制台 0 error / 0 warning，213 个静态请求全部 200。截图为 `output/playwright/volumes-contract-desktop-1440.png`、`volumes-contract-mobile-390.png` 与 `volumes-contract-mobile-390-bottom.png`。
- 当前旧 Run 的 Provider binding、Prompt 和 Schema 已在创建时冻结，最新代码不会也不应回填。下一门必须先完成全量离线门和 Volumes 桌面/390px 浏览器门，再新建 Run 做真实 Volumes 首稿/换稿和人工闭合审查；通过前不得进入 Detail、三档 10 万字或发布。

### 15.5 Harness H5 真实 Spine、Cast 与 Volumes 决策门（2026-08-15）

- 全新 Run `backend-run-cast-demand-h5-20260815` 绑定项目 `proj-fdc697770d`、项目工作流 `wf-proj-fdc697770d`、平衡模式和 100,000 字软目标。当前 read model 为 `volumes / awaiting_decision`：Brief、Spine、Cast 已完成，Volumes 候选待决，Detail、Text、Cover、Export 全部锁定。18 次 Provider operation 全部成功，累计 `54,517 prompt + 9,318 completion = 63,835 tokens`，`reasoning_tokens=0`，无 failure 或 pending Provider operation。
- Spine 首稿完成真实 UI 审查后只做一次换稿，再做一次人工外科式编辑并正式提交 `spine-committed-31ace257c4cd2dfcb185-e6d494d5`。最终 20 个 turns 把大潮、独立物证、听证、死亡/责任认定、林澈处罚与制度整改依次收在 turn 17-20；删除了私人渠道、非法录音、主动同事、事后信件、死亡时间矛盾、终局提前和重复收尾。最终结论不依赖越权取得的记忆单独定案，弟弟的事后补救也不洗白既有造假责任。首稿与最终人工稿截图为 `output/playwright/h5-spine-initial.png`、`output/playwright/h5-spine-regenerated-edited.png`。
- Cast 首稿由 6 名主体和 9 条关系组成，已经比旧链路收敛，但仍把审计部门、法院和独立技术组分别人格化为负责人、法官和工程师。真实换稿暴露的根因不是单份 dossier 文风，而是旧的 Cast regeneration 只重写人物档案，继续消费首稿 Role Demand，因而无法删除被错误人格化的需求。现在只有用户明确要求 Cast 换稿时，Graph 才以 `role_demand:proposal:cast-N` 重新派生需求，并让 dossier 与关系窄调用继承同一 revision direction；普通 Provider 失败重试继续沿用原需求，不进行隐藏重规划。
- Cast 换稿后正式提交 `cast-committed-fbb7494a3fcb969072ca-737396ca`，只保留林澈、历史主体林泽和事故幸存者沈墨 3 名具名主体，关系为 0。林泽冻结为 `historical_record`，不得拥有 POV、当下行动或直接互动；沈墨只承担实名授权和关键晶片来源，修复后永久遗忘且不得恢复记忆或继续参加调查；审计、法院、技术组继续作为机构程序而不是人物槽位。对应截图为 `output/playwright/h5-cast-initial.png`、`output/playwright/h5-cast-regenerated.png`。
- Role Demand Prompt 进一步明确：部门、法院、委员会、技术组等机构职责不得自动转换为负责人、法官、委员或工程师等具名人物。回归合同覆盖“换稿重新派生需求并可缩减 cast”“普通失败不隐藏重规划”“关系窄调用继承换稿方向”和“机构保持非人格化”；定向后端测试为 `26 passed`，`compileall` 与涉及文件 `git diff --check` 通过。
- Volumes 首稿与一次真实换稿均按 `volume-1 -> volume-2 -> volume-3` 执行三个独立 operation。三卷边界始终冻结为《空白求救》 turn 1-7、《越权修复》 turn 8-14、《终审盐痕》 turn 15-20；每次调用只收到当前卷 turns、当前 boundary、最小人物引用、卷序策略，以及第二卷起的上一卷 `title + closure`，不含完整 Spine、相邻卷 turns、复数 boundaries 或 `thread_ids`。三卷 `length_hint` 均为 `medium`，在约 40 章投影下允许 Detail 按负载形成接近 14/14/12 的章数分配，而不是机械要求逐卷完全相等。
- 后端当前持久化候选仍是 `volumes-candidate-9f85d66cbb91f755f9e4-be30988b`。H5 人工草稿在此基础上继续收紧：第二卷重新纳入历史主体林泽，避免 Detail 丢失弟弟责任约束；第三卷删除林澈再次主动越权的选择，把她固定为证人和被调查人；越权取得的记忆只作辅证，结论由独立物证支撑。截图为 `output/playwright/h5-volumes-initial.png`、`output/playwright/h5-volumes-regenerated-edited.png`。
- Harness H5 后的最新完整门为后端 `354 passed`、前端 `394 passed`，`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、全工作树 `git diff --check` 和 production closure audit 全部通过。检查前后 Run 均保持 `volumes / awaiting_decision`，18 次 Provider operation、token 统计、正式 Artifact refs 和 pending decision 均未变化。
- H5 当时的未决风险是人工编辑只存在浏览器会话；该风险由下节的阶段草稿 sidecar 关闭，但 Volumes 尚未定稿，不能据此进入 Detail。

### 15.6 Volumes 阶段草稿持久化与刷新恢复门（2026-08-15）

- 新增独立 `StageArtifactDraftRecord` 与内容寻址 Store，草稿严格绑定 `run_id + stage_id + decision_id + domain_revision + source_artifact_id`。GET/PUT `/api/runs/{run_id}/stage-drafts/{decision_id}` 只读取或保存当前待决策 Artifact 的人工编辑稿；API route 只做输入/错误适配，决策解析、vNext Artifact 校验和编辑候选保存归属 `orchestration/stage_artifact_editing.py`。
- 保存草稿不会调用 `Command(resume=...)`，不会写 candidate/committed Artifact、改变 pending decision、发送 Provider 请求、追加领域事件或创建 operation receipt；“确认定稿”仍是唯一推进 Graph 的动作。前端 `useStageArtifactDraft` 以 650ms 防抖自动保存，并明确投影读取、已同步、未保存、保存中、已保存和失败状态；运行工作台不再以组件内 map 充当草稿权威。
- H5 正式草稿为 `volumes-draft-daec4452df337eaade436b92`，latest pointer 已从一次临时验证编辑恢复到该不可变记录。第二卷 `cast_ids` 为 `subject-1/subject-2/subject-3`，第三卷人工冲突与高潮保持“林澈只作为证人和被调查人、越权记忆只作辅证、独立物证完成认定”的版本。
- 隔离浏览器会话 `h5-stage-draft` 已从作品库恢复该稿，并在刷新后再次恢复同一三卷内容和“已保存”状态；控制台为 0 error / 0 warning。证据为 `output/playwright/h5-volumes-draft-restored-before-refresh.png`、`output/playwright/h5-volumes-draft-restored-after-refresh.png`、`output/playwright/h5-volumes-draft-final-closure.png` 与 `output/playwright/h5-volumes-draft-final-after-refresh.png`。
- 最终完整门为后端 `356 passed`、前端 `397 passed`，`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、全工作树 `git diff --check` 和 production closure audit 全部通过；草稿状态样式复用既有 `artifact-draft-status` 体系，没有抬高 CSS 基线或建立第二套状态样式。
- 最终只读账本仍为 `volumes / awaiting_decision`、`domain_revision=3`、18/18 Provider operation 成功、`63,835 tokens`、114 条事件、checkpoint `1f198269-6cf1-6096-8006-6de7853a2de1`；pending decision 与源候选均未变化，Detail/Text/Cover/Export 仍锁定。
- **当时未决硬门：阶段草稿是可恢复的 sidecar，不是正式 `VolumeArchitectureArtifact`。在下一节关闭真实 SSE 断线交互前不得点击“确认定稿”；三档 10 万字、Detail、发布和 Git 操作继续禁止。**

### 15.7 Harness H6 真实 SSE 中途截断与 sequence 续接门（2026-08-15）

- 根因位于前端 transport/controller 边界：`consumeRunEventStream` 在没有收到稳定终态事件时把普通 EOF 返回为 `completed`，`useRunStreamController` 又没有从最后已投递 sequence 自动续接。对 H5 的 114 条真实事件在 `sequence=60`（Spine 的 `checkpoint.saved`）截断后，修复前页面错误退回 `/run/spine`，把 Volumes 显示成“未开始”并暴露“继续下一阶段”；网络只有 `events?after=0`，没有 `after=60`。截图为 `output/playwright/h6-sse-truncated-baseline.png`。
- transport 现在只有 `decision.required`、`run.failed` 和 `run.completed` 能产生终态；非终态 EOF 返回 `null`，没有 SSE 空行分隔符的中断尾帧不解析、不投递，由续接响应完整重放。controller 最多进行 3 次有界续接，首个续接立即执行，后续使用短退避，并始终读取当前 Run 最后已成功投递的 sequence。瞬时 fetch/reader 网络错误沿同一路径恢复；完整帧内的 HTTP/Schema/Artifact 合同错误仍显式失败，不被重试掩盖。
- sequence cursor 只在 payload ref 全部解析并真正投递事件后前移；补取 payload 失败时会重新读取尚未投递的事件，不再先移动 cursor 造成事件丢失。重复 sequence 在投递前过滤；Abort、组件卸载或 session 失效继续沿原有 `AbortError` 立即停止，不会产生后台续接。
- 合同测试证明：第一响应在 `sequence=44` 非终态结束后，第二请求严格为 `events?after=44`；即使第二响应重复携带 44，事件 44 和终态 45 也各只投递一次。另有瞬时网络失败保持 cursor、主动 invalidate 不发第二请求和非终态 EOF 不等于完成的覆盖。
- 隔离会话 `h6-sse-reconnect` 从作品库打开同一个 H5 Run。浏览器只 mock `after=0` 返回真实事件 1-60，随后观察到真实请求 `after=60` 返回 61-114，页面正确恢复 `/run/volumes`、`待决策`、三卷人工稿与“已保存”状态；控制台 0 error / 0 warning。截图为 `output/playwright/h6-sse-reconnected-after-fix.png`，mock 随后已撤销。
- 最新完整门为后端 `356 passed`、前端 `402 passed`，`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、全工作树 `git diff --check` 和 production closure audit 全部通过。只读账本仍为 `volumes / awaiting_decision`、`domain_revision=3`、18/18 Provider operation 成功、`63,835 tokens`、114 条事件、checkpoint `1f198269-6cf1-6096-8006-6de7853a2de1`；pending decision、源候选和草稿 `volumes-draft-daec4452df337eaade436b92` 均未变化。
- **下一硬门：先对当前三卷人工草稿完成最终产品/叙事审查，再由用户动作确认 Volumes 并进入 Detail。Detail 仍必须先完成真实生成、一次换稿、逐章标题/场景负载/字符预算均衡与浏览器回显验收；在此之前不得启动三档 10 万字并行测试、发布或 Git 操作。**

### 15.8 自然分卷与动态章节布局断代（2026-08-16）

- 产品复评确认“先由总字数除出章数，再按每卷 8/12/16 章反推卷数”颠倒了创作权威。生产 `NarrativeCapacityPolicy` 冻结合理章长带、单场承载带、Spine 每 turn 章节承载密度与相邻章节奏带；`NarrativeScalePlan` 只提供动态全书章节可行区间、章节建议值、Spine 转折区间和场景容量，不再包含 `volume_target/min/max`。
- 精细模式已删除 `volume_target_override`，旧字段由 strict schema 直接拒绝，不做 alias、converter 或默认忽略。配置页不再显示数值化卷数建议，改为“按故事脊柱的自然闭合动态决定”。
- `VolumeBoundaryProposal` 只依据连续 Spine turns 的局部承诺、升级、高潮与闭合提出自然卷界。代码只校验顺序、唯一覆盖、引用、全书章节容量和 `volume_candidate_cap`；后者只是单次结构化响应的技术序列化上限，不是目标卷数。
- Volumes 通过后，Scale 以已成立卷合同的 turn 负载建立宽容量区间；人物数量不再参与章数，`length_hint` 只温和调整软目标，不能改变结构下限。`DetailLayoutProposal` 再根据可拆分事件决定实际章节数与每章独立戏剧任务。实际总章数必须落在合理章长带推导的全书可行区间，容量不足返回 `insufficient` 并退回前置规划，禁止 Detail 或正文注水。
- 细纲场景数不设固定产品值：运行时以冻结的合理章长带和单场最小/最大承载推导本 Run 的场景容量边界；最终章节数只能接受容量校验，不能反过来改写编辑章长政策。Provider 根据具体事件单元、人物对抗、时空转换和不可逆转折在边界内选择。正文预算在 Detail 冻结后以首选章长为基准，综合场景、出场人物、转折、地点与 `length_hint` 分配，再用全书软目标做有界整体校准，不由场景数或总字数除章节数单独决定。
- 新增/更新合同覆盖自然两卷不再被旧单卷目标拒绝、技术上限仍阻断、旧卷数覆盖字段被拒绝、前后端不再投影卷数范围、DetailLayout receipt 恢复不重复 Provider 调用。定向门为后端 `152 passed`、前端 `9 passed`；随后全量门为后端 `408 passed`、前端 `112 files / 412 tests passed`，`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、`git diff --check` 与 production closure audit 全部通过。CSS 首屏为 `27.7 KiB gzip`，既有 `graph-3d-vendor` 大 chunk 仍独立懒加载。
- 最新后端从当前工作树重启后，官方平衡模板在 `1440x1000` 与 `390x844` 实测显示 `100,000` 字对应 `34-50` 章可行区间、建议约 `45` 章、合理章长与 `1-4` 场动态容量；分卷只显示“按故事脊柱的自然闭合动态决定”。八阶段稿件栈切换会同步更新配置区，Detail 的正文预算与细纲字数边界在双端无重叠，控制台为 0 error / 0 warning。截图为 `output/playwright/dynamic-scale-config-desktop-final.png`、`output/playwright/dynamic-scale-config-mobile-final.png`、`output/playwright/dynamic-scale-detail-desktop-after-css-gate.png` 与 `output/playwright/dynamic-scale-detail-mobile-after-css-gate.png`。这些证据没有调用真实 Provider，也不证明 10 万字正文质量。
- H5 的 workflow digest、Scale、Provider 输入、候选和人工草稿都冻结在本次断代前，不能把新 schema 或新 Prompt 回填后继续执行。下一次真实验收必须从最新官方平衡模板新建 Run，并从 Brief 开始完成每阶段换稿与 UI 验收；Cover 继续按用户要求暂时跳过。

### 15.9 编辑章长政策优先于算术均分（2026-08-16）

- 复核发现 Detail 在选定实际章数后仍以 `word_target_soft / chapter_count` 重算 `chapter_target_band`，并从均分值开始分配各章正文预算。这会让 34 章布局把“合理章节”改写成接近 3000 字、50 章布局又改写成接近 2000 字，实际章数反向篡改了编辑政策。
- 唯一合同改为：`NarrativeCapacityPolicy` 冻结 `chapter_characters_min/preferred/max` 与相邻章节奏容差；`chapter_target_band` 只投影这套政策并删除误导性的 `average_characters`、`variation_percent` 和 `adjacent_delta_percent`。实际章数仍须落在全书目标与章长带推导的可行区间，但不能产生一套新的章长标准。
- Detail 冻结所有章节后，代码先用 `preferred_characters` 作为基准，再根据场景数、出场主体数、转折数、地点变化和 `length_hint` 形成各章负载差异；最后只在每章最小/最大承载内对全书软目标做整体校准。全书目标仍可收敛，各章不再从均分值起步。
- DetailLayout Prompt 删除“优先最小章节方案”的偏置，改为以 `chapter_target` 作为编辑重心，并只在真实戏剧单元更轻或更密时下调或上调；分卷数量仍由 Spine 的自然闭合决定，章长区间只负责容量校验，不能参与卷数算术。

### 15.10 Spine 与 Detail 双向容量约束（2026-08-16）

- 容量缩放包含一个明确的小规模边界：若合理章长带得到的全书最大章节数仍低于“最小三段式 Spine + 长篇每 turn 章节密度”所需的最小章数，三个 turns 只表达结构语法，可由一章承载多个 turns；只要两者存在交集，真实 Spine 数仍必须按长篇密度反向收窄 Detail，10 万字主链路不享受该边界。

- 真实 10 万字 DetailLayout 证明旧 `20` 个 Spine turns 会被机械拆成约 `40` 章，并产生等待、争执、隐瞒等填充章。根因不是 Detail Prompt 的措辞，而是 `turn_target=min(20, ...)` 与 `turn_max=min(24, ...)` 在 Spine 上游截断了因果容量。
- `NarrativeCapacityPolicy` 新增 `spine_chapters_per_turn_min/preferred/max`，默认 `1.15/1.33/1.50`。10 万字按 `2000-3000` 字合理章长先得到 `34-50` 章、中心 `40`，再动态得到 Spine `27-34` turns、中心 `30`；场景数仍由章长与单场承载区间推导，卷数仍只由自然闭合决定。
- Spine 确认后必须用真实 turn 数二次求交：27 turns 允许 `34-40` 章，30 turns 允许 `35-45` 章，34 turns 允许 `40-50` 章；20 turns 与 10 万字容量无交集时直接退回 Spine。Volumes 的每卷范围和 DetailLayout 的全书范围读取同一收窄结果，不能形成“低密度 Spine + 高章节数 Detail”的无效组合。
- 精细模式 turn 覆盖的技术上限与 `StorySpineArtifact` 对齐为 `120`，但用户值仍必须落在本书动态区间。`120` 是序列化上限，不是可绕过编辑密度的自由配额。默认 Spine item cap 同步为 `120`，三套官方 DeepSeek 模板提升到 `7500` output tokens，以容纳 10 万字平衡区间上界；预算仍在 Provider 调用前按真实上界计算，不截断、不 repair。
- 本节改动只使新 Run 的生产合同成立；现有 `backend-run-balanced-dynamic-scale-2500-20260816` 已冻结旧 20-turn Spine 和旧工作流，不得继续确认其 Detail 候选。完成离线门后必须从 Brief 后检查点创建新分支 Run，或在没有合法分支入口时创建全新平衡 Run。
- 小规模最小脊柱语法与动态夹具修正后的定向扩圈为 `86 passed`；当前工作树完整门为后端 `423 passed`、前端 `112 files / 412 tests passed`，`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、全工作树 `git diff --check` 与 production closure audit 均通过。CSS 首屏仍为 `27.7 KiB gzip`，本轮证据只证明离线合同，不代表真实 DeepSeek 或文学质量。

### 15.11 Brief 战术污染与 Spine 固定分段断代（2026-08-16）

- 全新平衡 Run `backend-run-1786839061486` 在 `100,000` 字动态合同下完成 Brief 与三次 Spine 候选。第三稿满足 `30 turns`，但仍大量依赖权限核验、找协助者、收集样本、通缉躲藏，并在最后两项重复形成终局；继续换稿会把数量合格误当成结构合格，因此该 Run 停在 `spine / awaiting_decision`，不得进入 Cast。
- Provider 输入快照证明三次换稿方向、`turn_target=30` 与 `turn_range=[27,34]` 均完整进入最终 Prompt。最低责任边界不是 SSE、上下文丢失或 Detail，而是已确认 Brief 把“潜入系统底层”、特殊权限和物理/生物防护提前冻结为剧情事实，Spine 又只收到总数量纪律；第三次人工要求“五段各 6 turns”进一步把动态结构退化为机械填槽。
- 新唯一合同不再给 Spine 固定五段或固定段长。Brief 只冻结战略承诺，不预写潜入、取物、工具、权限、追捕和门禁路线；`world_rules` 只保留跨阶段持续改变人物选择的最少必要规则。Spine 先在动态 `turn_range` 内选择真实不可逆变化总数，再按实际总数伸缩启动、中心反转、危机、唯一高潮和直接余波，既有证据优先彼此改义，不靠持续获取新工具、新样本或新文件凑进展。
- 官方模板升级为 `29.14.0-structural-brief-boundary`。平衡模式的 Brief 从 Flash 改为 Pro，DeepSeek Pro 的 Brief/Spine 均启用冻结的高推理策略；输出预算检测到思考策略时保留完整阶段上限，仍只接受一次严格 JSON 解析。前端默认模板、代码种子与运行时官方三模板使用同一版本；旧 Run 的 Prompt digest 和 ProviderBinding 不回填。
- 当前定向合同门为后端 `29 passed`、前端 `6 passed`；运行时官方模板镜像与代码权威一致测试 `4 passed`。随后完整门为后端 `425 passed`、前端 `112 files / 413 tests passed`，`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、`git diff --check` 与 production closure audit 均通过，首屏 CSS 仍为 `27.7 KiB gzip`；配置就绪报告 `ok: true`。浏览器与新真实 Run 证据仍待本节后续补齐，不能据此宣称 Spine 文学质量已修复。

### 15.12 动态场景容量与全书软目标校准（2026-08-16）

- 复核确认 `1-6` 场虽然来自章长/单场承载区间，却没有在 DetailLayout 选定实际章数后重新收窄：10 万字选 34 章时，一场最多 2400 字，无法承载均衡正文；选 50 章时，六场最低 3000 字，又会迫使单章过重。生产链现在先用章长带推章节区间，再按实际章数、编辑首选章长、全书软目标容差带和单场承载力二次推导本 Run 的场景边界。默认 10 万字下，34/40/50 章分别得到 `2-5`、`2-5`、`1-4` 场；这仍是可行边界，不是每章场数配额。
- `word_target_soft` 不再要求所有逐章目标之和精确等于输入值。代码优先保留 `实际章数 × 2500` 的编辑首选总量；只在越出默认 `±10%` 全书软目标带时校准到最近边界。因而 34/40/50 章的规划总量分别为 9 万、10 万和 11 万字，随后再按场景、人物、转折、地点与 `length_hint` 分配差异；没有任何章节直接复制 `总目标/章数`。
- 逐章分配的上下界同时受场景承载、编辑章长、全书软目标和相邻节奏约束。相邻节奏带的一半被用作预算中心两侧的全局安全余量，因此即使轻重章节交替，仍能保留差异且不会因贪心再平衡产生本可行却被误判失败的布局。
- 定向合同门为后端 `89 passed`、前端 `12 passed`，并额外回放 34-50 章每种 1000 组随机合法负载，预算总和、动态场景边界和相邻节奏均无失败。随后完整门为后端 `430 passed`、前端 `112 files / 413 tests passed`，`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、`git diff --check` 与 production closure audit 均通过；该证据尚不等于浏览器或真实 DeepSeek 长篇验收。
- 隔离浏览器会话 `dynamic-soft-scale` 已在官方平衡模板完成 `1440x1000` 与 `390x844` 双端复核：100,000 字正确回显“建议 40 章（34-50 章）”“合理章长 2,000-3,000 字”“按故事脊柱的自然闭合动态决定分卷”与“每章按剧情负载在 2-5 场内选择”。桌面端切换到 Detail 后右侧配置、执行模型和下一阶段同步更新；移动端内部滚动可抵达完整配置区，`document.scrollWidth == clientWidth`，无重叠或横向溢出。控制台为 0 error / 0 warning，工作流、历史与 Provider readiness 请求均为 200；初始化时一条被后续同路径请求替换的 history 请求显示 `ERR_ABORTED`，不属于服务失败。截图为 `output/playwright/dynamic-soft-scale/desktop-brief-scale-1440x1000.png`、`desktop-detail-stage-1440x1000.png`、`mobile-brief-scale-390x844.png`、`mobile-detail-top-390x844.png` 与 `mobile-detail-settings-390x844.png`。该证据关闭动态尺度配置页浏览器门，真实 DeepSeek 的 Brief 至 Text 质量与 10 万字总量仍必须由全新 Run 证明。

### 15.13 DeepSeek 结构化响应包络（2026-08-16）

- 全新平衡 Run `backend-run-1786843496089` 的 Brief 首稿成功，但同阶段定向换稿在冻结 `max_tokens=4600` 下失败：该次调用使用 `1725 prompt + 4600 completion` tokens，其中 `4076` 为 reasoning，最终 `finish_reason=length`，没有可提交的完整 JSON。首次成功调用也已使用 `4569/4600` completion tokens，其中 `4110` 为 reasoning。故障最低责任边界是 DeepSeek Pro 的结构化响应包络，不是 Brief 内容、Schema、JSON repair 或 SSE。
- 该证据否定 15.11 中“Brief/Spine 使用高推理即可保留完整阶段上限”的旧假设。DeepSeek 的 completion ceiling 同时承载 reasoning 与可见 Artifact；提高上限不能保证高推理停止吞噬输出，且 Spine 已独立出现相同失败类型。
- 新唯一策略为：Pro 的 `brief` 与 `spine` 保留 `thinking.type=enabled`，但统一使用 `reasoning_effort=low`；`cast/volumes/detail/text/text.evidence/text.review` 均禁用 thinking 且不再发送相互矛盾的高 `reasoning_effort`。后续结构化质量由阶段拆分、冻结上下文、严格 Schema、换稿和人工决策保证，不用不可控的隐藏推理占用 Artifact 预算。
- 三套官方 DeepSeek 流水线、前端默认模板和代码种子同步升级为 `29.16.0-structured-reasoning-envelope`。旧 Run 保留其失败输入、receipt 和冻结 ProviderBinding，不回填新策略；完成离线门并重启后端后必须新建平衡 Run 继续真实验收。

### 15.14 DeepSeek V4 思考强度兼容映射断代（2026-08-16）

- 全新平衡 Run `backend-run-1786844357478` 已完成 Brief 两稿比较与人工定稿，随后 Spine 首次调用在 `7500/7500` completion tokens 处失败；回执为 `7500 reasoning tokens`、`0 response chars` 和 `finish_reason=length`。冻结 Provider 输入证明请求确实携带 `thinking.type=enabled` 与 `reasoning_effort=low`，参数没有在适配器中丢失。
- DeepSeek V4 官方文档明确只提供 `high/max` 两档思考强度；为了兼容，`low/medium` 会映射为 `high`。因此 15.13 的“low 是可控低推理”假设不成立。继续提高 `max_tokens` 或重试只会扩大不可控的隐藏推理包络，不能保证留下完整 JSON。
- 新唯一策略是所有 DeepSeek Brief、Spine、Cast、Volumes、Detail、Text Evidence 与 Review 结构化节点显式关闭 thinking，并且不发送 `reasoning_effort`。Pro/Flash 的质量分工继续保留；创作质量由阶段职责拆分、冻结上下文、动态容量、严格 Schema、真实换稿和人工决策承担。
- 三套官方工作流、前端默认模板和代码种子升级为 `29.17.0-nonthinking-structured-artifacts`。失败 Run 保留不可变证据；离线门和后端重启通过后，从已确认 Brief 后的 checkpoint 建立新分支 Run，只冻结新的 Spine Provider binding，避免重算 Brief 且不篡改失败账本。

### 15.15 Spine 可行域不再服从中性章数（2026-08-16）

- 分支 Run `backend-run-1786844357478-brief-branch-2917` 证明非思考策略已生效：Spine 调用返回完整合法 JSON，新增 usage 为 `1904 prompt + 1473 completion`、`0 reasoning`，但 25 turns 被旧 `27-34` 合同拒绝。25 turns 仍能在默认密度下承载约 34-37 章，与 10 万字的 34-50 章编辑容量有真实交集；要求补到 27 会把 40 章中性建议错误升级为硬剧情配额。
- 新公式以完整章节容量求 Spine 可行域：最少 turns 由 `chapter_min / chapters_per_turn_max` 推导，最多 turns 由 `chapter_max / chapters_per_turn_min` 推导，中性 `turn_target` 才继续读取中性章节建议。默认 10 万字因此从 `27/30/34` 改为 `23/30/43`；实际 Spine 定稿后仍用真实 turn 数把 Detail 章数收窄到可承载交集，25 turns 对应约 34-37 章，不允许补水到 40 章。
- Spine 的非思考可见 JSON ceiling 从 7500 调整为 8000，以容纳 43-turn 合法上界的 7601-token 预测包络；这不是隐藏推理预算。三套官方工作流与前端镜像升级为 `29.18.0-feasible-spine-capacity`，旧失败 Run 与 29.17 分支均保留不可变诊断，新验收从同一 Brief checkpoint 再建分支。

### 15.16 三档模式共享叙事可行域（2026-08-16）

- 复评确认质量档位只能改变模型、审稿强度和人工决策策略，不能改变同一故事的结构容量。旧逻辑在极速模式把动态 Spine 区间收缩为中性 `turn_target` 单点，既与配置页展示的完整区间不一致，也会让平衡模式可接受的自然 25-turn Spine 在极速模式被迫补到 30 turns。
- 新唯一合同是极速和平衡模式都保留由合理章长带推导的完整 `turn_min/target/max`；极速通过自动接受阶段决策提速，而不是通过固定转折数提速。精细模式只有用户显式填写 `turn_target_override` 且数值位于本书动态可行域时，才将区间收缩为该单点。
- 正文章数继续先由冻结的合理章长带推导，卷数继续只由 Spine 的自然闭合决定，Detail 场景数继续由选定章节布局、单场承载力与实际戏剧任务共同决定。任何档位都不得用 `总目标/预设章数` 产生正文篇幅标准，也不得用平均每卷章数反推卷数。
- 三套官方工作流、代码种子和前端镜像升级为 `29.19.0-nonquota-narrative-scale`；旧 Run 与旧项目工作流保持不可变，不做版本转换或兼容回填。

### 15.17 历史主体注册表与 Cast 绑定归位（2026-08-16）

- 平衡 Run `backend-run-1786844357478-brief-branch-2919` 的 25-turn Spine 已完成换稿、人工收紧与正式提交，但 Cast 首稿只登记四名当下行动者，遗漏贯穿全书核心证词的母亲。若继续进入 Detail/Text，母亲声音只能退化成自由文本人物，无法由冻结 `subject_id` 约束。最低责任边界不是 Cast 文风，而是 Role Demand 只允许“做独立不可逆选择的人”，系统性排除了贯穿证据、记忆与关系的历史主体。
- `RoleDemandProposal` 新增严格 `subject_mode=actor|historical_record`。历史主体只有在其身份、声音、证词、遗物或缺席贯穿多个 Spine turns 且下游必须稳定引用时登记；其 `required_change` 描述记录或遗产的意义、可信度、所有权或后果变化，不得虚构当下行动。机构、委员会和部门仍保持机构形态，不能借历史主体规则人格化。
- `role_demand.proposal` 从 Spine structured tasks 完整迁移到 Cast binding，预分配 `subject_refs` 携带 `subject_mode`；人物档案分组校验与最终组装均强制 historical demand 只能生成 `kind=historical_record`，actor demand 不得伪装成历史主体。旧 Spine task、跨 stage attempt 兼容参数和旧 operation key 形态直接删除，不做 schema 回填。
- 三套官方 DeepSeek 流水线、后端代码种子、前端镜像与 Cast Prompt 升级为 `29.20.0-historical-subject-registry`。定向合同门为 `114 passed`，当前完整门为后端 `434 passed`、前端 `112 files / 413 tests passed`；`compileall`、TypeScript/Vite production build、CSS audit、首屏/lazy CSS split、静态 legacy 搜索与 `git diff --check` 全部通过。旧 29.19 Run 的冻结 ProviderBinding 保持不可变；真实验收必须从已确认 Spine 检查点创建只覆盖 Cast binding 的新分支。

### 15.18 章节与分卷数量权威归位（2026-08-16）

- 复评否定 29.24 的“先接受 Spine/自然卷界，再让模型或交集选择实际章数”设计。动态智能的正确含义是确定性容量计算加受限创作，不是把数量权威交给模型。
- `NarrativeCapacityPolicy` 冻结单章 `2000/2500/3000` 字、单卷 `8/14/20` 章和 Spine 每 turn `1.15/1.50/1.80` 章。`NarrativeScalePlan` 由用户全书目标计算并冻结 `chapter_min/target/max` 与 `volume_min/target/max`；10 万字为 `34/40/50` 章、`2/3/5` 卷。官方配置删除章数输入，UI 只展示系统结果。
- Spine 的真实 turn 数只做承载校验，不能夹紧或移动 40 章目标。25 turns 的交集为 34-45，40 合法；20 turns 无法承载 40，必须退回 Spine。`VolumeBoundaryProposal` 必须精确返回 3 个连续边界，模型只决定边界位置；失衡的 turn 覆盖退回 Volumes。
- 卷内槽位总和必须精确等于 40，每卷在产品容量与 turn 密度交集内，只按 turn 数确定性分配；`length_hint` 不再参与数量算法。DetailLayout 仍逐卷窄调用和独立 receipt，但每卷只填精确槽位，少一章、多一章或前卷改变后卷预算都立即失败。
- 三套官方工作流、代码种子与前端镜像升级为 `29.25.0-deterministic-book-scale`。旧平衡 Run 冻结 29.24 政策，不迁移、不回填；必须在离线门和浏览器门通过后创建全新 10 万字平衡 Run。

### 15.19 首稿结构与人物合同前移（2026-08-16）

- 产品复评否定“先生成、等读者发现大问题后再换稿”的默认路径。换稿只用于审美取舍或明确方向的创作变体；缺里程碑、因果位置错误、连续信息转折、缺少外部/关系推进、角色职责重复、人物背景空泛、多主角、终卷高潮错绑等问题必须在 Provider receipt 成功和候选写入前失败。
- `StorySpineArtifact.turns[]` 正式包含 `progress_type` 与 `milestones`。长篇六个里程碑各出现一次：启动固定首 turn，主动承诺位于 20%-30%，中心反转位于 40%-60%，危机位于 65%-80%，高潮固定倒数第二 turn，余波固定末 turn；短篇可在保持顺序时合并相邻功能。长篇至少包含 relationship 与 external 推进，禁止连续三个 information turns。
- `RoleDemandProposal` 冻结 `subject_mode/narrative_role/irreducibility/active_turn_refs`。`irreducibility` 必须说明无法并入已有主体或机构的具体选择、压力或后果；整批需求必须恰好一个主角、职责互不重复、key 唯一，唯一主角必须引用首尾 Spine turns。实际人物数量由这些不可合并职责决定，但受篇幅容量动态硬上限约束；10 万字为建议 `3-7`、硬上限 `11`，建议范围不是人数配额。
- `CharacterBibleArtifact` 把人物背景拆为 `background/conflict_history/present_stakes`，并保留可演绎的 `temperament/speech_style/drive/change/limits`。空泛占位、运行时术语、重名主体、角色标签冒充姓名和多个主角都直接拒绝；历史主体继续禁止当下行动、说话和 POV。
- 终卷 `climax_turn_ref` 必须精确绑定 Spine 中唯一的全书 `climax` turn，普通卷高潮必须落在本卷后 40%。三套官方工作流、Python 种子、运行时 JSON 与前端镜像统一升级为 `29.26.0-first-draft-contract`。旧 Run 保持冻结，不迁移、不回填；最新全门通过后只能创建全新平衡模式 10 万字 Run，从 Brief 首稿重新验收。

### 15.20 人物出场尺度与关系推进闭环（2026-08-16）

- 复核发现 Cast 的 `debut` 仍按 `chapter_range` 下限投影：10 万字虽然冻结 40 章，人物窗口却按 34 章提前。根因是 Cast 组装与候选校验读取了 `chapter_min`，同时前端 Prompt 仍把 `chapter_target` 写成建议。新唯一规则改为全链路只读取代码冻结的精确 `chapter_target`；可行区间只解释容量，不再参与人物出场编号。
- Spine 首稿门新增两类可确定性拒绝：不同 turns 不能复用相同 `cause/change`，单一 turn 的前因和变化不能是同一状态；12 turns 以上至少包含两次 external 推进。Role Demand 必须让非主角 demand 覆盖每一个 relationship turn，防止关系线存在于 Spine 却没有进入冻结人物注册表。
- 人物档案对“暂无、待补充、不详、未知、未明确、尚未确定”等加长占位前缀和只靠标点拉长的空泛标签直接失败。该门只拦截明确未决内容，不使用关键词打分替代文学判断。
- 本节定向后端门为 `119 passed`。完整后端、前端、构建、CSS、浏览器与全新平衡模式真实 Provider Run 仍待执行，完成前不能进入 10 万字正文验收或提交推送。

### 15.21 首次可见候选稳定性（2026-08-16）

- 真实平衡 Run `backend-run-1786872631140` 的 Brief 在修复 DNS 分类与单对象输出预算后以冻结输入首稿通过；Spine 第一次完整 Provider 响应则因连续三个 `information` turns 在候选写入前被硬合同拒绝。门禁阻止了坏稿暴露给读者，但 0.7 的结构采样温度和仅描述结果的 Prompt 没有让“首稿可执行”成为默认行为。换稿不能承担这类结构修复。
- 三档官方工作流统一升级为 `29.29.0-first-visible-draft-stability`。Spine 温度冻结为 `0.45`，Cast 温度冻结为 `0.55`；Brief、Volumes 保留原创意温度，Detail `0.30`、Text `0.82` 不变。质量档位只改变模型路径、审稿与人工决策策略，不得让同一结构阶段使用互相冲突的稳定性标准。
- Spine 的最终渲染 Prompt 在所有官方和自定义模板之后追加不可绕过的首稿自检：输出前静默核对精确 turn 数、六个代码锚点、上一 change 到下一 cause 的因果链和推进类型；任意三个连续 turns 必须至少包含一个 `relationship/external/internal`，且关系或外部转折必须留下可供 Role Demand 识别的选择承担者、后果承担者或压力来源。检查过程不输出，失败内容在同一次响应内重排或重写，不能留给读者换稿。
- 人物数量继续由两层权威共同约束：字数量级只计算最小可培养容量、编辑中心和硬上限，真实人数由不可合并 Role Demand 决定。10 万字的 `3-7/11` 不是填槽配额。人物档案继续强制拆分 `background/conflict_history/present_stakes/temperament/speech_style`，新增要求 `limits` 必须给出具体能力、伦理、知识、资源或行为边界；关系 `type/pressure` 也必须描述已经成立的选择、信任、责任或风险，拒绝“可能、或许、潜在、关系复杂”等未决表述。
- 定向门已通过：后端模板、Artifact 与 Provider Prompt 合同 `82 passed`，前端模板镜像 `6 passed`，`compileall` 通过。完整后端、完整前端、生产构建、CSS、闭环审计和真实 Provider 首稿仍待验证，不能据此宣称 10 万字全链路完成。

## 16. 2026-08-17 v1.0 Demo 收口附录

- 真实 Run：`balanced-110k-v1-demo-20260817-040033`，Project `proj-e1007717ad`，书名 `明日来电`。
- 阶段：`brief -> spine -> cast -> volumes -> detail -> text -> cover -> export` 全部完成；封面生图按配置跳过，但 Cover 元数据与 Export 闭环。
- 正文：44 章、107,613 个非空白字符，章节标题与分卷标题完整，单章 1,710-3,692 字，平均 2,445.75，P90 2,962。
- Provider：314 次调用，311 成功、3 次失败后恢复，总 tokens 1,760,252；失败收据保留在验收报告中。
- 质量边界：只有流程崩溃/死锁、合同解析失败、关键 Artifact/正文缺失、明确上游硬约束冲突、主体越权或章内物理状态直接矛盾、未达 10 万字和不可导出才是本次硬门；模型低置信 finding、转折伏笔、AI 味和文学偏好记录为软告警。
- 发布：前后端完整测试、TypeScript、生产构建、CSS 门禁、compileall、diff 检查与浏览器桌面/390px 证据均已完成；本次可按用户要求提交并推送 GitHub `main`。
