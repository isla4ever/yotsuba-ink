# Phase 20：LangGraph 叙事运行时与 Context Engineering 重构规划

> 状态：Wave 20A/20B 合同与 Context 基线已收口，Wave 20C Chapter Shadow 已完成；legacy 主路径尚未迁移。
>
> 调研与代码快照：2026-08-06。
>
> 本文定义产品决策、领域边界、数据合同、迁移顺序和验收方法。真实 DeepSeek Run 与 LangGraph 主路径迁移继续暂停，直至 Dual Run 的幂等、恢复和成本退出条件通过。

## 1. 结论先行

Yotsuba Ink 应采用 LangGraph，但不应把产品改造成由一个 LLM Supervisor 自由指挥的“全自治多 Agent”。正确架构是：

```text
LangGraph 负责执行控制面
    +
Yotsuba Ink 负责叙事领域内核与事实权威
```

LangGraph 逐步接管节点调度、条件路由、章节子图、并行 Reviewer、人工中断、可恢复检查点和重试状态；现有 Stage Artifact、Prompt Compiler、Provider 适配、Reality Reconciliation、Canon/Wiki/Memory 写回门、Token Budget 和前端事件合同继续保留并收紧。

这不是一次“换框架即提升文笔”的重构。当前质量瓶颈来自四个层面：

1. Prompt 和 Context 中存在重复权威、主次不清和随章节增长的问题。
2. 章节计划、正文现实、审稿诊断和正式写回之间仍有权威边界漏洞。
3. 审稿角色、预算、复检和恢复状态分散在多个 orchestration 模块，策略容易漂移。
4. 技术门通过不能证明文学质量、连续性或投稿准备度。

因此迁移顺序必须是：

```text
领域权威与 Context 合同
  -> Prompt / Context 编译
  -> 章节子图 Shadow Run
  -> 新 Run 的章节主路径
  -> Stage / Global Graph
  -> 长篇真实验收
```

不做 Big Bang，不迁移正在运行或已经失败的旧 Run，不在当前 500 余项脏工作树上整包替换自研运行时。

## 2. 产品评审

### 2.1 用户真正需要解决的问题

用户并不是单纯需要“更多 Agent”或“更长思考”，而是需要一个能以合理 Token 成本稳定生产长篇小说的系统：

- 前置阶段能形成足够明确、精简、可执行的叙事计划；
- 每章能继承上一章的现实状态、人物知识和未完成动作；
- 正文保留创作空间，但不随意改写全书因果、人物走向和 Canon；
- 审稿能发现具体问题，并只修真正需要修的局部；
- 恢复不会重复生成、重复扣费或把旧证据当成新证据；
- Wiki、RAG、Story Bible、Canon 和运行记忆各司其职；
- Fast / Balanced / Deep 是不同的生产策略，而不是同一 Prompt 的 Token 档位。

### 2.2 对用户提议的判断

“初始 Prompt 只告诉 Agent 去哪里找前置内容”只对了一半。

正确部分是：Writer 不应一次性接收所有历史正文、全量 Wiki、所有规则和全部审稿标准。

需要修正的部分是：不能把检索不确定性直接推给 Writer，让它在写作时临时决定查什么、相信什么。Writer 应收到已经冻结、去重、带来源和优先级的 `ContextSnapshot`；检索 Agent 只负责找候选，提炼 Agent 只负责生成事实卡，确定性 Context Broker 决定哪些内容进入本次写作上下文。

### 2.3 本期正确决策

- 采用 LangGraph 作为新的执行控制面，优先使用 Graph API 表达 Global / Stage / Chapter Subgraph。
- 不引入 LangChain AgentExecutor，不要求业务逻辑依赖 LangChain 抽象。
- 不建立一个能自由改计划、正文和 Canon 的总管 Agent。
- 不让相邻章节并行生成；后一章必须等待前一章现实对账和临时状态落盘。
- 多 Agent 只用于上下文检索、窄职责审稿和证据提炼，且只读取冻结快照。
- 所有 Agent 只输出 Proposal 或 Evidence，不能直接写共享事实。
- Context Broker 与 Prompt Compiler 默认是确定性代码，不额外消耗模型 Token。
- Thinking 按任务类型和模型能力开启，不全程开启。
- 先迁移章节控制面，证明恢复与质量门可靠后，再迁移全局阶段图。

### 2.4 本期明确不做

- 不恢复或重跑 `phase19f-prompt-compiler-live-ab-20260806-b1`。
- 不把 LangGraph 加入必装依赖；Shadow 只使用可选 extra。
- 不把现有 JSON `RunStore` 立即替换成 LangGraph Checkpointer。
- 不复制 PlotPilot、NovelClaw、CrewAI 或 AutoGen 的完整代码。
- 不用 Agent 数量、模型自评分或 AI Detector 分数证明“可投稿”。
- 不让 Cover / Export 阻塞前期正文生产；它们按本文阶段依赖并行准备，但最终导出必须等待正文和质量门完成。

## 3. 当前架构真实盘点

### 3.1 Legacy 主路径仍没有使用 LangGraph

当前 legacy 执行主路径仍不依赖 `langgraph` 或 `langchain`；`langgraph` 只作为可选 Chapter Shadow extra。执行主路径是：

```text
NovelWorkflowRunner
  -> stream_workflow()
  -> NovelWorkflowCompiler.compile_order()
  -> orchestration/*
  -> RunStore / WikiStore / ProviderRegistry
```

`NovelWorkflowCompiler` 只对 `WorkflowDefinition.nodes/edges` 做拓扑排序，并明确拒绝环。注释中的“shaped like LangGraph”只是设计意图，不是实际集成。

### 3.2 当前也不是一个简单 DAG

虽然顶层 Workflow Definition 是有向无环图，运行时已经在 DAG 外实现：

- 暂停与人工确认；
- 章节级顺序生成；
- 质量修订循环；
- 多 Reviewer 并行；
- 预算与熔断；
- Run revision CAS；
- 快照、恢复、分支和历史事件；
- 临时 Canon、卷级审计和正式写回；
- Reality Reconciliation 与 FuturePlanPatch；
- SSE 运行观测。

真正的问题不是“有没有循环”，而是循环、恢复和权威状态分散在大量模块中，缺少统一的图状态与节点合同。

### 3.3 复杂度证据

2026-08-06 本地快照：

- `src/novel_workflow`：约 415 个 Python 文件；
- `src/novel_workflow/orchestration`：约 115 个 Python 文件、20,882 行；
- 当前工作树：约 536 条修改或新增记录；
- `RunStore` 同时承载 Run JSON、事件、快照、revision、恢复请求、导出和分支等多种职责；
- 前置阶段、正文、审稿、写回和恢复已经形成多套局部状态机。

这些数字不是“必须拆文件”的理由，但说明策略已经跨模块扩散。Phase 20 的目标是重新确立责任边界，不是为了行数机械拆分。

### 3.4 Prompt / Context 现状

当前 Prompt Compiler 已有实质进展：历史三章离线复算中，8 个场景的旧上下文核心从 `50,636` 字符下降到 `27,553`，压缩 `45.59%`，最大最终 Prompt 为 `6,732 / 16,000` 字符。

但全链路仍有结构性问题：

- Detail 第 1 章 Prompt 约 25,865 字符，第 32 章增长到约 45,016 字符；
- Detail 每批重复携带完整基线、当前卷和全部前序章节 ledger；
- 正文中 `chapter_outline`、`LiteraryIntent`、`SceneContract`、前章桥、摘要、尾文、Voice Genome 和 Voice Spec 存在语义重叠；
- Provider 结构化输出增强可能对已有 JSON 合同再次附加协议；
- 被整体标记为 protected 的大段上下文无法进行字段级去重和裁剪。

因此 Phase 19 证明了“可以压缩”，尚未证明“所有阶段都已形成稳定的最小充分上下文”。

### 3.5 真实失败证据

失败 Run `phase19f-prompt-compiler-live-ab-20260806-b1` 只完成第 1 章正文：

- 正文约 3,459 字；
- 首次语义审稿完成；
- 自动局部修订触发后进入复检；
- 原本参与硬门的 `causal_fact_auditor` 在复检规划中变为 unavailable；
- 协调状态降级，正文停在 `prose_ready`；
- 没有完成三章，也没有完成正式 Canon/Wiki 收束。

这说明失败来自“审稿角色规划、预算和复检状态合同不一致”，不是再跑一次模型就能解决的问题。它应作为 Shadow Run 和恢复测试的固定失败夹具保存。

## 4. 根因分层

### 4.1 控制面碎片化

当前节点执行、审稿路由、预算、失败恢复、人工确认和写回状态分别由不同模块推导。同一策略修改需要同步多个模块，容易出现：

- 初审路由了某角色，复检却无法恢复同一角色；
- 角色结果被保存，但没有参与硬门；
- 软文学诊断不可用，却错误阻断生产；
- 事件写 completed，状态却是 degraded；
- 恢复只绑定正文签名，没有绑定完整 Context / Contract 签名。

### 4.2 领域权威混杂

计划中的事实、正文已经发生的事实、模型抽取结果、审稿推断、Wiki 投影和 Canon 正式事实不能互相替代。任何 Agent 直接写共享状态都会造成“模型自己提出、自己检索、再把自己证明为真”的自证循环。

### 4.3 Context Flooding 与 Context Rot

上下文窗口大不代表注意力无限。问题不是能否塞下 40K 字符，而是模型能否识别：

- 哪条事实是当前唯一权威；
- 哪条只是未来计划；
- 哪条已经被正文推翻；
- 哪条只对当前 POV 可见；
- 哪条风格规则只需要在本场生效。

重复内容会放大冲突，thinking 只会让模型在更多冲突上花费更多 Token。

### 4.4 多 Agent 的错误用法

多 Agent 不是质量的同义词。错误做法包括：

- 多个 Agent 同时写同一章或相邻章节；
- Reviewer 在正文冻结前开始审稿；
- Reviewer 各自读取不同版本的 Context；
- 让 Reviewer 直接修改正文或 Canon；
- 每次局部补丁后重跑全部 Reviewer；
- 为了“更稳”固定增加角色，而不看章节风险。

这些做法会增加 Token、延迟和状态竞争，却无法保证文学质量。

## 5. 外部框架与项目调研

### 5.1 LangGraph

截至 2026-08-06，`langchain-ai/langgraph` 约 39K stars、MIT License，仍在活跃更新。官方能力与本项目的匹配点：

| LangGraph 能力 | Yotsuba Ink 用途 | 边界 |
| --- | --- | --- |
| StateGraph / conditional edge / Command | 阶段路由、章节质量分支、有限循环 | 不让 LLM 自由决定事实权威 |
| Checkpointer | 线程级运行状态、恢复、人工中断、time travel | 不替代 Canon / Wiki / Artifact Store |
| Store | 跨线程偏好或共享长期信息 | 不直接作为小说 Canon 的无审核写入口 |
| Subgraph | Stage / Chapter / Review Mesh | 默认 per-invocation，避免 Reviewer 跨章污染 |
| interrupt | Info/Deep 人工确认、修订裁决 | 节点重放要求副作用幂等 |
| streaming | 映射现有 SSE 事件与 Provider delta | 前端继续消费稳定领域事件 |
| pending writes / durable execution | 节点失败后避免重复成功任务 | Provider 调用和正式写回仍需业务幂等键 |

关键判断：LangGraph 可以替代自研执行控制面，但不能替代叙事领域合同。Checkpointer 是执行记忆，Canon 是小说现实，两者必须分开。

### 5.2 PlotPilot

`shenminglinyi/PlotPilot` 约 1.4K stars，近期仍更新。源码值得借鉴：

- DDD 分层与独立 engine runtime；
- Story Bible、章节摘要、叙事事件、故事线、伏笔和知识三元组；
- T0-T3 上下文分层、近期章节与向量召回分离；
- Prompt Package、变量投影和续写上下文装配；
- 章后摘要、状态、事件、因果、伏笔、索引的独立管线；
- SQLite 单写者调度和 checkpoint；
- 文风、张力、陈词和一致性诊断。

其连续性优势主要来自“长期叙事状态结构化 + 每章动态装配 + 章后更新”，不是 Prompt 更长。

不能复制或整体二次开发：仓库许可证是 Apache 2.0 加 Commons Clause，明确限制以其核心功能向第三方收费。Yotsuba Ink 只能吸收通用架构思想，并自行实现。

### 5.3 STORM

Stanford STORM 约 30K stars、MIT。可借鉴的是“先研究、再组织、后写作”：

- 多视角提出问题；
- 检索与写作分离；
- 先形成结构，再生成全文；
- 资料附来源而不是直接混入文风 Prompt。

它适合题材资料、时代背景、职业细节和世界观研究，不适合作为小说正文运行时直接替换。

### 5.4 NovelClaw

`iLearn-Lab/NovelClaw` 约 358 stars、MIT。可借鉴：

- 章节工作区与可观察 Agentic Loop；
- 章节级计划、评分、有限重试；
- 章后摘要和事实卡进入记忆；
- 用户可在章节间介入。

风险是执行器和多种状态仍集中在大模块中，且按评分重写整章容易造成 Token 放大。适合借鉴交互和章节工作区，不适合作为主运行时。

### 5.5 其他框架决策

| 项目 | 当前判断 | 决策 |
| --- | --- | --- |
| CrewAI | 角色协作成熟、MIT、约 56K stars | 不作为核心；容易演变为角色堆叠，可参考任务/角色描述 |
| AutoGen | 多 Agent 会话能力强、约 60K stars | 不作为核心；当前仓库许可证元数据需进一步法务确认 |
| PydanticAI | 类型化 Agent/结构化输出清晰、MIT、约 19K stars | 暂不新增依赖；先复用现有 Pydantic 合同，可参考其 schema 思路 |
| Temporal Python SDK | 跨进程长任务和强可靠性优秀、MIT | Phase 20 不引入；只有出现多机、数小时任务和严格 SLA 再评估 |
| Langfuse | 追踪和评估成熟、约 32K stars | 只考虑可选观测适配器；许可证和部署边界另行评审 |

### 5.6 FictionForge 源码审计与融合决策

本轮审计固定到 `wanqili857-byte/fictionforge` 的提交
`c381297e2c6c670f374933d850b9b85756dead27`（2026-08-06）。仓库采用 MIT License，
创建时间为 2026-07-24，审计时 32 stars。四个离线测试脚本共 92 项断言通过；
Python 3.14 运行 `theory_of_mind.py` 时仍有无效转义告警。项目很新、样本规模小，
README 的“长篇稳定”描述不能替代真实长篇、恢复、成本和人工盲读证据。

它值得学习的不是“给每个角色都开一个 Agent”，而是以下叙事建模顺序：

1. 作者维护真相表，角色只持有自己的记忆、信念、知识和对他人知识的判断；Writer
   不直接读取作者真相全文。
2. 世界事件先按 `public / traces / hidden` 分层，再按地点、感知阶段和关系信任投影给角色。
3. 角色先独立提出行动；同天同地的角色冲突再进入 Scene Director 合成，Narrator 最后把事件线变成章节 spec。
4. 事件先按故事弧模拟，再按天与地点聚成场景、分配到章节；正文不是第一步自由补全全书因果。
5. 同章后一场直接读取前一场冻结正文的有界尾部，而不是仅依赖生成前细纲承接句。
6. 角色的旧信念不删除，只标记为已修正，使认知反转本身成为可追溯叙事状态。

Yotsuba Ink 已经拥有 FictionForge 缺少的强边界：Stage Artifact、Context/Contract/Scene
签名、Provider receipt、LangGraph 恢复控制面、Reality Reconciliation、Canon/Wiki 正式写回门、
Token Budget 与运行事件合同。因此不替换现有架构，也不复制其 `scripts/gen.py`（约 1587 行）、
正则 YAML 解析、Markdown Vault 直接改写或整章 anti-AI 自动重写。其关键词式真相匹配、手动合并角色
更新和失败时进程退出，也不能进入生产主路径。

本次对照还暴露了一个 Yotsuba 的真实空洞：`ChapterContextPacket.knowledge_matrix`、
Prompt Compiler 的 POV P0 区和确定性 POV 检查都已存在，但生产代码只从
`story_bible.character_profiles[*].knowledge` 或 `stage_display_artifacts.character_knowledge` 读取；
当前没有对应的正式写入端。C3 第 4 章 Context 中 `knowledge_matrix={}`，所以现有 Writer 实际只收到
一条通用的“不得越权”提示，没有收到当前 POV 的已知、怀疑、误信、隐瞒与误读快照。这个能力不能标记为完成。

本轮已补齐第一版确定性生产端：`literary/epistemic_snapshot.py` 从 Info/作者确认的人物知识和上一章
以前有效的 `NarrativeAssertion` 投影 `CharacterEpistemicSnapshot`，保留断言 ID、证据签名、authority
revision 与快照签名；只有 `epistemic` 类型的明确认知谓词进入快照。完整矩阵仍留在运行状态用于审校，
Context Budget、Prompt Compiler 与 ContextSnapshot 只向 Writer 暴露当前 POV 投影。旧 Packet 没有快照时
继续走 POV-only 的 `knowledge_matrix` 兼容路径。

#### 5.6.1 融合后的领域合同

新增的目标产物应是 `CharacterEpistemicSnapshot`，而不是可自由写状态的角色 Agent：

```text
CharacterEpistemicSnapshot
  character_id
  chapter / scene_id
  knows[] / suspects[] / believes[] / conceals[] / misreads[]
  thinks_others_know[]
  source_assertion_ids[] / source_signatures[]
  authority_revision / snapshot_signature
```

- `knows` 只能来自已冻结正文证据和已正式确认 Canon；计划中的 `knowledge_out` 只是本场目标，不能提前写入。
- `believes / misreads` 可以与作者真相冲突，但必须保留来源、置信度和修正 lineage。
- `thinks_others_know` 是角色判断，不等于对方真的知道，不能提升为 Canon。
- 当前 POV 的投影进入 Writer P0；其他角色只暴露“可观察行为”和当前 POV 已有的 ToM 判断，隐藏真相不进入 Prompt。
- Snapshot 在场景生成前冻结并参与 Context Signature；任何来源变化都使正文、审稿和写回缓存失效。
- 章后叙事抽取只产生 `EpistemicProposal`，Reality Reconciliation 绑定逐字证据后才能更新下一场或下一章 Snapshot。

#### 5.6.2 事件预演按模式分配

| 模式 | 角色认知 | 事件预演 | 额外模型成本 |
| --- | --- | --- | --- |
| Fast | 确定性投影当前 POV 快照 | 直接使用已确认 Detail SceneContract | 0 个角色 Agent |
| Balanced | 确定性投影 + 冲突/缺口检查 | 由确定性 Rehearsal Compiler 生成短 `Chapter Intent Brief` | 默认 0；高风险时最多 1 次合成 |
| Deep | 同一冻结 Snapshot 上并行读取在场角色提案 | 仅冲突场景启用角色 Proposal + Scene Resolver | 最多 2 个在场角色 Proposal + 1 次 Resolver；不覆盖 Writer |

角色 Proposal 只能回答“此人基于自己所知会尝试什么、会隐藏什么、会误判什么”；不能写正文、
不能修改 Detail、不能直接写 Canon/Wiki。Scene Resolver 输出短事件拍，不输出文学段落。Writer 仍是唯一
正文作者，相邻章节继续严格顺序，避免多 Agent 把声音写碎或制造状态竞争。

#### 5.6.3 实施与验收顺序

1. 先补 `CharacterEpistemicSnapshot` 的生产写入、来源证据、签名和章后 Proposal，不在正在运行的 C3 中途改变 Context。
2. 用当前 C3 和固定失败 Run 离线重建 Snapshot，证明同一输入确定、错误真相不泄露、POV 越权能被命中。
3. 先上线 Fast/Balanced 的零 Agent 投影；只有高风险 Deep 场景再打开 Proposal/Resolver feature flag。
4. 比较“无预演 / 确定性预演 / Deep 角色预演”三组的 Prompt 长度、调用数、衔接缺陷和人工盲读结果。
5. 只有角色行动兑现率和 POV 边界优于基线、且 Token 增量受预算约束，才允许进入新 Run 主路径。

FictionForge 临时克隆只保留在 `/tmp` 研究目录，不进入产品树、发布包或 Git 历史。

## 6. 目标架构

### 6.1 总览

```text
User / API / UI
      |
      v
Yotsuba Domain Command Layer
      |
      v
LangGraph Global Graph
  ├─ Planning / Info Subgraph
  ├─ Summary Subgraph
  ├─ Outline Subgraph
  ├─ Detail Subgraph
  ├─ Chapter Subgraph x N (strictly sequential)
  ├─ Cover Subgraph (dependency-gated parallel track)
  └─ Export Subgraph (prepare early, finalize after hard gates)
      |
      +---- Context Broker ---- Retrieval / Story Bible / Canon / Wiki
      |
      +---- Provider Adapters -- Model capability profiles
      |
      +---- Domain Stores ------ Artifact / Evidence / Canon / Outbox
      |
      +---- Event Adapter ------ existing SSE contract
```

### 6.2 三类图必须分开

1. `Execution Graph`：LangGraph 运行路径，允许有限循环、interrupt、条件分支和并行 Reviewer。
2. `Artifact Dependency Graph`：Info -> Summary -> Outline -> Detail -> Text 等产物依赖，保留版本与签名。
3. `Narrative Causality Graph`：人物、事件、伏笔、关系和事实的故事内因果，不等同于执行顺序。

当前瓶颈的一部分来自把这三类“图”混在同一 Run State 和 orchestration 推导中。Phase 20 必须分别建模，只通过稳定 ID 与签名关联。

### 6.3 Global Graph

```text
START
  -> load_or_create_run
  -> validate_workflow_contract
  -> resolve_quality_mode
  -> stage_router

stage_router
  -> info_subgraph
  -> summary_subgraph
  -> outline_subgraph
  -> detail_subgraph
  -> text_volume_loop
  -> cover_subgraph
  -> export_subgraph

text_volume_loop
  -> chapter_subgraph (sequential)
  -> volume_audit
  -> volume_commit_or_interrupt
  -> next_volume | cover/export finalize
```

顶层只保存引用、状态和签名，不在 Checkpoint 中重复保存整本正文。

### 6.4 Stage Subgraph 通用骨架

```text
load_upstream_artifacts
  -> compile_stage_context
  -> generate_structured_artifact
  -> schema_validate
  -> deterministic_contract_check
  -> optional_quality_review
  -> artifact_draft
  -> interrupt_if_required
  -> confirmed_writeback
  -> publish_stage_event
```

Stage Artifact Contract 继续决定每个阶段的产物、用户决策、写回和下一阶段依赖。LangGraph 不能改变该产品语义。

### 6.5 Chapter Subgraph

```text
load_chapter_snapshot
  -> compile_context_snapshot
  -> risk_classification
  -> optional_chapter_planner
  -> sequential_scene_generation
  -> deterministic_contract_check
  -> prose_freeze
  -> review_mesh
  -> adjudicate_review
  -> [accept | bounded_local_patch | human_interrupt]
  -> targeted_recheck
  -> reality_reconciliation
  -> writeback_proposal
  -> chapter_provisional_commit
  -> next_chapter_brief
```

约束：

- 相邻章节不并行；同章场景默认顺序生成；
- `prose_freeze` 后 Reviewer 才能启动；
- Reviewer 共享同一个 `ReviewInputSnapshot`；
- 局部补丁每章最多一次，超过范围转人工；
- 补丁后只复检阻断角色和受影响的确定性门；
- Reality Reconciliation 通过前不能形成正式写回；
- 章节只进入卷内 provisional overlay，卷审计后才正式 Canon commit。

### 6.6 Cover 与 Export 的并行位置

Cover 不必等待所有正文完成：

- `Info + Summary` 确认后可生成 Cover Brief 与视觉方向；
- `Outline` 稳定后可生成候选封面；
- 若书名、人物视觉或结局定位变更，候选签名失效并提示重生成；
- 正式选中和导出封面在最终包签名前确认。

Export 也不必最后才开始：

- Detail 确认后即可准备 Manifest、章节目录、元数据和格式选项；
- 正文生成期间持续更新文件清单与校验状态；
- 最终 package 仍必须等待所有章节、卷级 Canon、封面选择和作者审读状态满足规则。

两者是依赖受控的并行支线，不是绕过正文质量门的捷径。

## 7. 核心数据合同

### 7.1 NarrativeGraphState

LangGraph State 只保存控制面所需的小对象和引用：

```text
run_id / project_id / thread_id
runtime_engine / graph_version / workflow_version
quality_mode
current_stage / current_volume / current_chapter / current_scene
artifact_refs + artifact_signatures
context_snapshot_ref + context_signature
review_plan_ref + review_snapshot_id
proposal_refs + gate_status
budget_state + retry_state
pending_interrupt
state_revision
last_node_receipt
```

禁止直接存入：全本正文、全量 Wiki、完整向量结果、API Key、模型思维链和未裁剪 Provider 响应。

### 7.2 ContextSnapshot

`ContextSnapshot` 是一次模型调用的唯一上下文来源：

```text
snapshot_id
run_id / stage / chapter / scene
source_artifact_signatures
authority_revision
mission
must_write_now[]
must_preserve[]
handoff
pov_knowledge
active_facts[]
character_states[]
relationship_states[]
foreshadow_windows[]
style_delta[]
forbidden[]
retrieval_evidence[]
included_slots[] / dropped_slots[]
conflicts[]
char_budget / token_budget
context_signature
```

一旦 Provider 调用开始，Snapshot 不可原地修改。任何 Context 变化都产生新 snapshot 和新签名，旧审稿、旧补丁和旧写回提案自动 stale。

### 7.3 AgentProposal

所有子 Agent 统一返回提案，不能直接写领域状态：

```text
proposal_id
agent_role
task_kind
input_snapshot_id
input_content_signature
status
claims[]
evidence_anchors[]
recommended_patch_targets[]
confidence
blocking_recommendation
model_operation_id
created_at
```

`blocking_recommendation` 只是建议，最终阻断由确定性 Coordinator 根据 `ReviewLaneSpec` 决定。

### 7.4 EvidenceLedger

每条正式判断必须能回到冻结来源：

```text
evidence_id
source_kind
source_artifact_id
source_signature
chapter / scene
start_offset / end_offset
verbatim_excerpt
claim_key
assertion_id
reconciliation_id
validity_status
```

证据偏移必须定义统一字符单位，并同时保存可复核 excerpt 与来源签名，避免前后端 UTF-16 / Unicode offset 不一致。

### 7.5 ReviewLaneSpec

```text
role
required
blocking
trigger_reasons[]
max_tokens
deadline_seconds
fallback_limit
recheck_policy
degrade_policy
```

不再依赖 `secondary_role + additional_roles`、共享 `cold_edit` 次数或隐式角色推导。

### 7.6 NodeReceipt 与 SideEffect Outbox

每个外部副作用都必须具备：

```text
node_receipt_id
node_name
input_signature
idempotency_key
provider_operation_id
domain_commit_revision
outbox_status
result_ref
```

Provider 调用、Wiki 写入、Canon commit、文件导出和 SSE 关键事件都通过 receipt/outbox 去重。LangGraph 从节点开头重放时，先读取 receipt，已完成操作只复用结果，不重复扣费或写回。

### 7.7 WritebackTransaction

正式写回至少绑定：

- 当前正文签名；
- ContextSnapshot 签名；
- Detail / SceneContract 签名；
- Reality Reconciliation ID；
- Evidence IDs；
- 当前 Run revision；
- 目标 Canon / Wiki revision；
- 决策者与决策时间。

任一签名变化都必须 fail-closed，不能用文本相同或旧报告“看起来还能用”来放行。

## 8. Context Broker 设计

### 8.1 不是另一个大模型

Context Broker 默认是确定性服务，职责是读取、检索、裁剪、去重、仲裁和冻结。它不生成正文，也不自行发明事实。

```text
TaskSpec
  -> source resolver
  -> authority resolver
  -> retrieval candidates
  -> evidence normalization
  -> semantic deduplication
  -> budget allocator
  -> ContextSnapshot
```

只有 Deep 高风险场景允许一个小型 Planner Agent 在冻结候选事实之上生成 `PlanningBrief`。Planner 不能新增事实，只能排序任务、指出冲突和建议桥接策略。

### 8.2 权威顺序

同一 claim 冲突时按以下顺序裁决：

1. 用户确认且当前版本有效的 Artifact 决策；
2. 已提交 Canon；
3. 当前卷 provisional overlay；
4. 当前章 Detail / SceneContract 中尚未实现的计划；
5. 前章 commit、离场状态和 Next Chapter Brief；
6. Story Bible / 人物关系 / 世界观当前版本；
7. Wiki 投影；
8. 知识库与外部检索；
9. Reviewer 诊断和模型推断。

低层来源不能静默覆盖高层来源。冲突必须进入 `ContextSnapshot.conflicts[]`，由路由策略决定阻断、降级或人工确认。

### 8.3 P0-P3 上下文分层

| 层级 | 内容 | 裁剪规则 |
| --- | --- | --- |
| P0 | 当前任务、SceneContract、前章结果桥、POV 边界、硬 Canon | 永不裁剪 |
| P1 | 当前人物/关系状态、有效伏笔、场景必须兑现的事实 | 只去重，不丢关键条目 |
| P2 | 当前卷局部结构、风格差量、相关世界规则 | 按风险和相关度裁剪 |
| P3 | 远程 Wiki/RAG、背景资料、软文学建议 | 预算不足时先丢弃 |

禁止把完整历史章节当作默认 P0。正常章只需要最近 1-2 章的精确 handoff、当前卷关键状态和风险命中的远程证据。

### 8.4 检索 Agent 的正确职责

可并行的窄职责：

- `KnowledgeRetriever`：从用户知识库和外部研究找候选片段；
- `CanonRetriever`：按 claim / entity / chapter 取当前有效事实；
- `CharacterStateRetriever`：取本章人物知识、欲望、关系和最近状态；
- `ForeshadowRetriever`：取当前窗口内必须投放、推进或回收的条目；
- `ContinuityRetriever`：取前章离场、未完成动作、情绪和物理位置。

它们可以并行，但必须在写作前汇合成一个冻结 Snapshot。Writer 不直接访问多个可变 Store，也不在写作中临时改变事实来源。

## 9. Prompt Compiler v2

### 9.1 单一调用结构

正文 Prompt 固定为：

```text
短身份（你是谁、服务什么叙事目标）
  +
本次任务 Mission
  +
Must Write Now
  +
Must Preserve / Handoff / POV Knowledge
  +
Active Facts
  +
Style Delta（1-3 条）
  +
Forbidden
  +
输出合同
```

身份应清晰但简短，说明角色认知和创作责任；不能把全部写作理论、质量量表和阶段历史塞进 system prompt。

### 9.2 去重规则

- `SceneContract` 是当前场景动作、转折和离场的唯一权威，不再并列渲染同义 `chapter_outline` 长文；
- 前章承接只保留一个 `handoff`，摘要、尾文和 bridge 不重复讲同一结果；
- Voice Genome 提供稳定基线，Voice Spec 只提供本场差量；
- 世界规则只在 `active_facts` 出现一次；
- JSON 协议只在结构化任务出现一次，并由 Provider 能力适配器保证幂等；
- 来源签名进入 trace，不进入 Writer 可见 Prompt 原文。

### 9.3 目标预算

- Detail 单章/单批 Prompt 不随章节数线性增长；
- Detail 正常目标 `<= 12K` 字符；
- 单场正文 Prompt 正常目标 `8K-10K` 字符，硬上限继续 `16K`；
- 当前 SceneContract、前章 handoff 和 POV 知识不得因裁剪丢失；
- 同一事实、风格规则和前章结果在最终 Prompt 中各出现一次；
- Prompt trace 只记录长度、槽位、签名、裁剪原因和权威分布，不保存敏感正文。

## 10. Thinking 模式矩阵

Thinking 是任务级能力，不是质量模式的总开关。不得保存或展示模型私有思维链，只保存最终结构化结果、证据和可审计摘要。

| 任务 | Fast | Balanced | Deep | 原因 |
| --- | --- | --- | --- | --- |
| Info 创意定位 | off / summary | summary | enhanced | 需要发散与收敛，但结果必须结构化 |
| Summary 因果结构 | off / summary | summary | enhanced | 适合处理不可逆选择和因果链 |
| Outline 卷级规划 | off / summary | summary | enhanced | 需要全局节奏与人物走向 |
| Detail 章节计划 | off | summary | enhanced | 细化人物/关系/伏笔状态，防止正文自由漂移 |
| Context Broker | off | off | off | 确定性编译更省 Token、更可复现 |
| 高风险 Chapter Planner | 不启用 | 条件启用 summary | 条件启用 enhanced | 只输出短 PlanningBrief，不写正文 |
| 正文 Writer | off | off / low | low | 注意力用于叙事、动作、对白和节奏，避免重复规划 |
| 语义/衔接审稿 | 不启用 | summary | enhanced | 需要跨段和跨章判断 |
| 因果/Canon 审稿 | 不启用 | 条件 summary | enhanced | 高风险事实核对需要受控推理 |
| 文学冷读 | 不启用 | 条件 off | summary | 只做诊断，不应默认硬阻断 |
| JSON 抽取 / Wiki 索引 | off | off | off | 结构化输出与本地校验更重要 |

Provider Capability Adapter 必须按厂商和模型映射 `thinking`、`reasoning_effort`、采样参数、JSON Output、Prefix Completion 和 Token 上限。模型不支持时显式降级并记录，不能悄悄忽略参数。

## 11. 多 Agent 拓扑与预算

### 11.1 总原则

- Agent 数量由风险触发器决定，不由模式固定凑数；
- 所有 Reviewer 读取同一冻结正文和 ContextSnapshot；
- 独立 Reviewer 可并行，Writer 和相邻章节不可并行；
- Writer 是唯一正文作者；Patch Agent 只在确定性准入后修改定位片段；
- Reviewer 只提交证据和建议，Coordinator 是确定性代码；
- 每个角色有 deadline、Token、fallback 和 recheck policy；
- legacy runtime 与 LangGraph shadow 必须读取同一份 `ReviewLaneSpec` 策略；语义主审 120 秒，Deep 硬专项 180 秒，诊断冷读 Balanced/Deep 为 60/90 秒，禁止用统一 wave deadline 覆盖角色合同；
- 模型不可用时按 blocking 属性决定 fail-closed 或降级诊断。

### 11.2 Fast

```text
Deterministic Context Broker
  -> Single Writer
  -> Deterministic schema / continuity / Canon gates
  -> provisional commit
```

- 不启用模型 Reviewer；
- 不自动改稿；
- 结构错误和 Canon 冲突仍硬阻断；
- 适合快速初稿，不宣称投稿准备完成。

### 11.3 Balanced

```text
Context Broker
  -> Single Writer
  -> Semantic / Continuity Reviewer (required)
  -> Causal Reviewer (risk-triggered)
  -> deterministic adjudication
  -> at most one local patch
```

- 通常 1 个模型 Reviewer，高风险时最多 2 个；
- 文学冷读只在明确风险时串行或后台诊断，不作为默认硬门；
- Reviewer 总墙钟目标 `<= 60s`，超时按角色策略处理；
- Patch 后只复检语义主审和实际触发阻断的专项角色；
- 不重跑正文生成，不无脑整章重写。

### 11.4 Deep

```text
Context Broker
  -> optional high-risk Planner
  -> Single Writer
  -> frozen prose
  -> parallel Review Mesh
       ├─ semantic_continuity_editor (required, blocking)
       ├─ causal_fact_auditor (triggered, blocking)
       ├─ character_pov_auditor (triggered, blocking)
       └─ literary_cold_reader (triggered, diagnostic)
  -> deterministic adjudication
  -> at most one local patch
  -> targeted recheck
```

- 初审最多 4 个角色，不意味着每章都运行 4 个；
- Review Mesh 总墙钟目标 `<= 90s`；
- 强制角色最多一次同角色故障转移；
- 文学冷读不可用只记录诊断降级，不阻断硬一致性通过；
- 额外硬专项必须真正参与协调和质量门，不能“调用了但不生效”；
- 每章自动局部补丁最多一次。

### 11.5 局部补丁准入

只有同时满足以下条件才允许 Patch Agent：

- 问题有明确冻结证据和定位锚点；
- 修改不改变章节主因果、人物目标或 SceneContract；
- 最多 1-4 个相邻片段；
- `search` 覆盖合计不超过 `min(600 字, 正文 15%)`；
- replacement 总量和全文净变化也受限；
- 不跨多个场景，不重写整章；
- 补丁后签名更新，旧审稿和写回提案失效。

无法定位、需要大改结构或会影响后续章节时，生成 `FuturePlanPatch` 或进入人工裁决，不消耗更多自动重写 Token。

## 12. 各阶段在新体系中的职责

### 12.1 Info

定义作品创意 DNA、题材定位、世界规则、主要人物、人物欲望/缺陷/秘密和初始关系。它是 v1 的强人工门，不追求把全书情节写完。

### 12.2 Summary

定义完整因果骨架、关键选择、不可逆代价、主角变化、对手系统、关键转折和结局方向。它回答“为什么会发生”，不是宣传简介。

### 12.3 Outline

定义每卷功能、冲突升级、人物阶段目标、关系走向、世界揭示和伏笔窗口。它控制全书节奏和方向，不承担每场动作细节。

### 12.4 Detail

Detail 是正文稳定性的主要计划层，必须明确：

- 每章 1-3 个稳定 ID 场景；
- POV、地点、进入状态、目标、策略、冲突、转折、代价和离场状态；
- 人物 `state_in -> action_choice -> cost -> state_out -> next_pressure`；
- 真实发生变化的有向关系；
- 当前章事实揭示与知识边界；
- 伏笔投放/推进/回收动作；
- 前后章 continuity handoff；
- 允许的局部创作空间与禁止越界项。

正文可以创新表达、场面、对白和微观动作，但不能自由重写人物走向、关系结果或后续章节计划。发生合理偏离时，不把偏离静默写回 Detail，而是生成可审核的 `FuturePlanPatch`。

### 12.5 Text

正文只负责实现当前 SceneContract，并在允许空间内创造具体文学表达。Writer 不负责重新规划全书，也不直接维护 Wiki/Canon。

### 12.6 Cover / Export

按 6.6 的并行依赖执行。封面和导出是正式阶段产物，但不能携带正文 Reviewer、人物关系网等无关运行面板，也不能在最终硬门前谎报完成。

## 13. Memory、Wiki、Canon、RAG 与 LangGraph Store 分工

| 系统 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| 知识库 | 用户提供的外部依据、题材研究、参考资料 | 小说已经发生的事实 |
| Story Bible / 世界观 / 人物关系 | 用户确认的创作设计与当前设定 | 自动证明正文已经实现 |
| Detail Plan | 未来章节计划和预期变化 | 已发生现实 |
| Canon | 经正文证据和 Reality Reconciliation 验证的现实 | 未实现的计划和 Reviewer 推断 |
| Wiki | Canon、Artifact 和来源的可读投影与索引 | 独立于来源的事实权威 |
| Memory / Summary | 为后续检索压缩历史、记录章节桥接 | 替代原始证据 |
| RAG | 从上述来源召回候选证据 | 决定候选是否可信 |
| LangGraph Checkpointer | 当前 thread 的执行状态、恢复和 interrupt | 小说事实数据库 |
| LangGraph Store | 跨 thread 用户偏好、可共享运行信息 | 绕过领域写回门 |

检索结果必须携带来源、版本和签名。零命中应记录为“执行过但无结果”，不能伪装成 RAG 有效。

## 14. LangGraph 集成边界

### 14.1 选择 Graph API，不选全量 Agent 抽象

Global / Stage / Chapter 使用 StateGraph：

- 分支和循环显式；
- 子图可独立测试；
- 每个节点边界有 checkpoint；
- 前端可以看到稳定节点和状态；
- 不需要把现有 Provider 和 Pydantic 合同改写成 LangChain Agent。

Functional API 可用于迁移早期把现有幂等函数包装成 task，但不作为最终全局拓扑的唯一表达方式。

### 14.2 Checkpointer 与 Domain Store

迁移初期不自研 LangGraph Checkpointer，也不让 Checkpointer 成为领域主库：

- 本地/测试使用官方 SQLite 或内存实现；
- 生产候选使用官方 Postgres Checkpointer；
- 现有 RunStore 在 Dual Run 期间仍是领域事件和兼容读模型；
- Artifact、Canon、Evidence、Outbox 保持独立 Domain Store；
- 若未来确需自定义 Checkpointer，必须通过官方 conformance tests。

### 14.3 SSE 兼容层

LangGraph 原生事件不直接暴露给前端。新增 `GraphEventAdapter` 将：

- graph node start/update/complete；
- Provider stream delta；
- interrupt；
- retry / degraded / failed；
- domain commit

映射为现有稳定 SSE 领域事件。UI 不感知底层 runtime 是 legacy 还是 langgraph。

### 14.4 Run 兼容策略

- `runtime_engine=legacy|langgraph` 在 Run 创建时冻结；
- 旧 Run 永远按 legacy 恢复，不原地迁移；
- 新 Run 可由 feature flag 选择 LangGraph；
- 新 Run 只有在 Shadow/Main flags、可选依赖和 live chapter adapter 四项同时满足时才允许选择 LangGraph；否则冻结为 legacy 并记录 fail-closed 原因，避免“配置显示 LangGraph、实际仍跑旧路径”的错配；
- 同一 Run 不允许运行时中途切换引擎；
- 失败回滚是“新建同输入 Run 并选择 legacy”，不是篡改原 Run 历史。

## 15. 迁移波次

### Wave 20A：合同与基线

- 评审并冻结本文；
- 建立 ADR：LangGraph 边界、Store 边界、Agent 写权限、Run 兼容策略；
- 固定 B1 失败 Run 为零 Provider 回放夹具；
- 记录当前节点、事件、预算、Context 和写回基线；
- 冻结 Stage Artifact Contract 已定义的同章最多四角色、软硬角色和墙钟预算，并让实现、预算、复检与恢复路径逐项对齐。

退出条件：没有依赖变更，没有运行时变更，架构合同可被测试引用。

#### 2026-08-06 进度

已完成：

- 冻结“质量修订后必须复检原首审硬专项”的合同；`causal_fact_auditor` 与 `finale_payoff_auditor` 从持久化的 `secondary_review / secondary_reviews` 恢复，不再依赖先前是否产生 `blocking_specialty_contracts`；
- 文学冷读 `independent_cold_editor` 继续是诊断角色，不会被上述恢复路径提升为阻断硬门；
- 对已经持久化了旧 `review_revalidation` 的失败 Run 增加同策略原位升级，不重生成正文、不重做局部修订，也不改变 generation / candidate / regeneration / revision 预算和操作历史；
- 语义审稿输出截断的恢复计划同时继承历史硬专项，避免新策略再次覆盖并丢失角色；
- B1 原始 Run 临时副本的零 Provider 回放确认：恢复后角色为 `semantic_continuity_editor + causal_fact_auditor`，正文候选仍为 `pending_review`，第二次恢复无新事件；实际 `opened={}` 表示旧作用域已有可用 `cold_edit` 容量，角色 allowance 已正确加入；
- 新增 B1 精简失败形态测试，覆盖历史硬角色恢复、正文预算保护、幂等和诊断角色边界；审稿、恢复、预算与合同扩圈测试为 `110 passed / 1 third-party warning`。

已完成：

- [ADR-001](./adr-001-langgraph-control-plane-boundary.md) 已冻结 LangGraph 控制面、Domain Store、Agent 写权限和旧 Run 兼容策略；
- B1 节点、事件、Context、预算和已有写回状态已提炼为脱敏固定回放夹具 `tests/fixtures/phase20_b1_quality_revision_replay.json`，测试走正式恢复入口并保持零 Provider、Context 只读和 Canon/事务状态不变；
- Reviewer 结果保存、`chapter_review_state` 协调、SSE 逐角色事件、预算 lane、失败恢复以及软硬角色边界已完成代码审计，并由 Reviewer 合同测试锁定；语义与专项结果事件都显式绑定同一个 `review_snapshot_id` 和角色；
- Context 与写回基线已冻结，Wave 20A 退出评审完成，下一阶段只进入 legacy runtime 的 Context Broker v2。

### Wave 20B：Context Broker v2（仍跑 legacy）

- 引入 `TaskSpec / ContextSnapshot / AgentProposal / ReviewLaneSpec` 领域合同；
- Detail 改为最近 handoff + 当前卷状态 + 风险召回，不再线性增长；
- Prompt Compiler 按字段去重，Provider JSON 增强幂等；
- 写回提案绑定 Context / Contract / Evidence 签名；
- 修复恢复上下文签名与 marker 失效规则。

#### 2026-08-06 进度

已完成 Wave 20B 的第一片 legacy baseline：

- 新增 `novel_workflow.literary.context_broker`，冻结 `TaskSpec`、`ContextSnapshot`、`AgentProposal`、`ReviewLaneSpec`、`ContextEvidence` 和 `ContextSource`；合同为严格、可序列化、不可原地修改的 Pydantic 模型，不包含 Provider、API key、完整正文或 Store 写权限。
- `ContextBrokerV2` 只做确定性去重、P0/required 优先级分配、预算裁剪和 Snapshot 签名；任何 Agent 的 `blocking_recommendation` 都保持 advisory，不能直接成为阻断或写回。
- 合同级防护拒绝敏感字段和超大载荷；阻断 Reviewer 必须显式 `required + fail_closed`，required lane 不得静默 skip。
- Detail Context 新增 3 -> 32 章非增长回归：基础上下文保持相同，分批 Prompt 只保留最近两章 ledger，未增加正文 Provider 调用。
- 现有 `prompt_compiler_audit` 已纳入 Context Snapshot 门：逐场必须有 64 位签名和稳定 ID，三章 Snapshot 签名必须唯一；审计报告只输出字符、签名和状态，不输出正文内容。
- `Context Snapshot` 身份已从正文 Provider 的 prompt trace 进入 `ProseDraft`、场景草稿和章节 Artifact 的 `context_snapshot_refs`；场景恢复、修复、章节复检、写回提案、正文定稿、阶段级正式写回和失败快照恢复都会重建当前 Snapshot 并 fail-closed 校验。提案签名包含 Snapshot 身份；没有 Snapshot 的旧 Run 仍走兼容路径。
- Snapshot 绑定兼容边界已收口：空 Chapter Artifact 不预先伪装成新版；第一份带 Snapshot 的 `prose_ready` 章节写入时才升级 `context_snapshot_binding_version=1`。新版服务端 Artifact 要求每章、每场完整绑定，删除章节版本、草稿签名或场景覆盖都会 fail-closed；旧 Artifact 版本和旧场景记录仍可零 Provider 恢复。
- 写回提案不再只保存章节级摘要签名：单场直接保留真实 Snapshot ID/签名，多场保存按场景顺序排列的 `scene_id + snapshot_id + snapshot_signature` 列表以及聚合签名。提案签名和决策 CAS 同时覆盖版本、逐场证据、聚合签名与数量，重复或空 `scene_id` 会被拒绝。
- 摘要复检 API、写回提案决策、章节定稿、Artifact 审批、阶段正式写回和失败快照恢复均使用服务端权威 Chapter Artifact；审批同时比较提交稿和服务端当前稿的 Snapshot identity。失败快照恢复会分别重建失败快照与当前章节身份，任一上下文漂移都不允许原位恢复。
- 新增真实 `generate_scene_sequence()` 的 fail-on-call 历史恢复测试、API 上下文漂移、审批删除字段、多场景提案决策和当前快照过期测试。相关定向套件 `67 passed`，全仓后端回归为 `1192 passed / 1 skipped`，仅保留既有 Starlette/httpx 弃用警告。本轮没有引入 LangGraph 依赖，也没有真实 Provider 调用。

尚未完成：三章有界真实 A/B、人工盲读和 Snapshot 绑定在真实 Provider/重启路径中的验证。当前完成的是 legacy runtime 的 Context 身份与写回边界，不代表真实 Run 已达到投稿质量。

退出条件：不增加正文模型调用，三章离线与有界真实 A/B 都证明 Context 更短且关键约束未丢。

### Wave 20C：Chapter Graph Shadow Run（已完成）

- 添加 LangGraph 为可选依赖；
- 用 StateGraph 表达 Chapter Subgraph，但不发 Provider 请求、不写 Domain Store；
- 读取 legacy Run 的冻结节点输入，回放路由、门、角色计划和状态转换；
- 对比 legacy 与 shadow 的节点决策、预算、审稿角色和失败状态；
- 将 B1 复检缺陷变成必须通过的 Shadow fixture。

已完成的实现与证据：

- `runtime/graph/chapter_shadow_graph.py` 使用 Graph API 编译最小 Chapter Shadow，显式表达候选校验、失败分类、角色恢复、预算规划和状态投影；编译时不配置 checkpointer 或 Store。
- `acceptance/chapter_shadow_replay.py` 在隔离副本上运行 legacy 纯恢复逻辑，与 Shadow 投影逐字段比较，不接收 Provider、RunStore、SSE 或写回句柄。
- B1 fixture 验证 `semantic_continuity_editor + causal_fact_auditor` 不再漂移，`independent_cold_editor` 仍为诊断角色，正文生成/修订预算与写回状态保持不变。
- `langgraph` 以 `>=1.2.7,<2.0.0` 可选 extra 锁定，当前解析版本为 `1.2.10`；未安装 extra 时 legacy 主路径仍可运行。
- Chapter Shadow 专项与相邻合同套件 `24 passed`；全量后端回归在 `uv run --extra langgraph pytest -q` 中完成，无失败项，仅保留既有 Starlette/httpx 弃用警告。

退出条件：Shadow 零副作用、零 Provider、路由差异全部可解释，B1 不再产生角色漂移。20C 已满足；这不代表 Dual Run、真实 Provider 或投稿质量验收完成。

### Wave 20D：Chapter Graph Dual Run（测试控制面已完成）

- 新建测试 Run 使用 LangGraph Chapter Subgraph；
- Provider 结果通过幂等 operation cache 单次调用，legacy 对照只消费录制结果；
- GraphEventAdapter 输出现有 SSE；
- interrupt / resume、进程崩溃、超时、角色部分失败和局部补丁均做故障注入；
- Domain Store 仍只有一个写者。

已完成的实现与证据：

- `runtime/graph/chapter_dual_ports.py` 提供显式 Provider、operation cache、Token 记账和唯一 Domain Commit 端口；同一 operation key 的完成结果只计费一次。
- `runtime/graph/chapter_dual_graph.py` 使用带 InMemorySaver 的 Chapter Subgraph，正文生成后才进入并行 Reviewer；硬角色不可用进入 interrupt，软文学角色只降级诊断，局部补丁后只复检语义与触发角色。
- `runtime/graph/event_adapter.py` 将图结果投影为现有 `chapter_pipeline_step_completed`、Reviewer、协调和 `chapter_completed` 事件，不把 LangGraph 原生事件暴露给前端。
- `acceptance/chapter_dual_replay.py` 只消费已录制 receipt 生成 legacy 对照，不重新调用 Provider。
- 6 个故障注入用例覆盖正常并行、Writer receipt 后崩溃、硬审稿超时 interrupt/resume、软审稿降级、局部补丁崩溃和 Domain commit 后崩溃；20D 相关套件 `86 passed`，全量后端回归 `1202 passed, 1 skipped`。

退出条件：无重复 Provider 调用、无重复扣费、无重复写回；章节结果和事件合同可被现有前端消费。测试控制面已满足；这仍不是新 Run 主路径，也未替代真实 Provider A/B。

### Wave 20E：新 Run 的 Chapter Graph 主路径

- 仅对 feature flag 新 Run 开启；
- Fast / Balanced / Deep 全部通过模式合同；
- 旧 Runner 继续作为回滚路径；
- 完成三章真实 A/B 与人工盲读；
- 通过后再执行单卷 8-12 章试运行。

当前已完成的前置边界：

- `runtime/graph/runtime_engine.py` 为 Run 创建冻结 `runtime_engine` 与选择原因；旧 Run 恢复时不会被新的请求输入覆盖。
- API 创建与 SSE 创建入口都记录 selection；默认和 flag 未满足时明确选择 legacy，避免“配置显示 LangGraph、实际仍跑旧路径”的隐式错配。
- 20E 主路径尚未打开：仍缺少真实 Provider 三章 A/B、Fast/Balanced/Deep 对照和人工盲读，因此不能把 Dual Run 测试结果当作新 Run 质量验收。

#### 2026-08-06 增量实现

- 新增 `runtime/graph/chapter_graph_runtime.py` 作为唯一领域适配边界：真实运行时只需提供有界的 Provider operation handler 和 provisional commit handler，LangGraph 节点不直接依赖 `ProviderRegistry`、`RunStore` 或领域写回。
- `review_lanes_for_mode()` 固定 Fast/Balanced/Deep 的角色预算，Deep 最多四个 lane；语义、因果和结局专项才可能成为硬门，独立冷读始终是诊断角色。
- 新增 `FileProviderOperationCache`、`FileDomainCommitPort` 和 `RunStoreCheckpointSaver`。它们分别保存 Provider receipt、临时提交 receipt 和 LangGraph execution checkpoint，均不把正文、Prompt、API Key 或 Canon 写入 checkpoint。
- 新增 20E/20G 适配器专项测试：三档模式、角色上限、进程重启、Writer receipt 复用、Domain commit 后崩溃和重复写回保护均已通过；这些是控制面和持久化端口测试，不等同于真实 Provider 文学质量验收。

仍未完成：适配器尚未替换 `stream_workflow()` 的章节领域主循环；当前 feature flag 选择仍以 legacy 回退为安全默认。必须先完成真实 Provider 三章 A/B、人工盲读、成本/延迟对照以及旧 Runner 回滚演练，才能打开新 Run 的 Chapter Graph 主路径。

退出条件：质量、成本、恢复和延迟均不劣于 legacy，且不需要手工修复状态。

### Wave 20F：Stage / Global Graph

- 逐步迁移 Info、Summary、Outline、Detail；
- 接入人工确认 interrupt；
- Cover / Export 依赖支线并行；
- RunStore 缩为兼容读模型和领域事件适配；
- 移除已被图节点完全替代且无消费者的旧 orchestration 路径。

退出条件：所有阶段产物、确认、恢复、SSE 和路由与 Stage Artifact Contract 一致。

### Wave 20G：生产持久化与长篇验收

- 选择正式 Checkpointer 与备份策略；
- 做节点级恢复、进程重启、数据库故障和网络故障测试；
- 完成至少一卷真实质量验收后，再创建完整长篇 Run；
- 长篇必须分卷设检查点，禁止“整本写完再看”；
- 最终仍需要人工作者审读和投稿规则核对。

#### 当前边界

已完成的是可替换的执行持久化端口和故障夹具；尚未完成 RunStore 领域状态、Provider receipt、Domain outbox 的跨进程原子提交，也没有完成单卷 8-12 章或完整长篇的真实质量验收。因此本 Phase 仍不能标记为完成或宣称“可投稿”。

## 16. Shadow / Dual / A-B 验收

### 16.1 零 Provider 离线回放

- 使用固定 Run Snapshot 和录制 Provider Result；
- 比较节点序列、角色路由、预算、gate 和 writeback proposal；
- 确认同一 snapshot 重放结果一致；
- Context 或 Contract 改变时旧缓存必须失效；
- 不允许修改原 Run revision、事件、预算和正文。

### 16.2 三章真实 A/B

使用同一 Story DNA、相同模型、相同参数、相同 Detail 和相同章节目标：

- A：当前稳定 legacy + Prompt Compiler；
- B：Context Broker v2 + LangGraph Chapter Graph；
- 先做 3 章，不直接写完整本；
- Provider 调用不可双倍执行，必要时使用录制响应做路由对照；
- 人工盲读不显示运行时和版本。

比较维度：

- 前章到本章承接；
- 人物声音和 POV 知识边界；
- 人物/关系状态兑现；
- 因果、物证、代价和场景结果；
- 伏笔投放/推进/回收证据；
- 解释密度、模板句和重复意象；
- 局部补丁是否真的局部；
- 输入/输出 Token、模型调用数和墙钟时间；
- 中断恢复是否重复请求或丢状态。

### 16.3 单卷验收

三章通过后只扩到 8-12 章单卷，验证：

- Prompt 长度不随章节数线性增长；
- 章节间状态连续；
- 卷级 Canon 审计和原子提交；
- 后章可以消费 provisional overlay，但不能消费 rejected proposal；
- 修改早期章节后，依赖和导出正确 stale；
- Reviewer 调用数量随风险变化，而不是每章固定最大值。

### 16.4 完整长篇验收

只有单卷通过后才允许完整长篇。每卷必须停下来做：

- 自动合同检查；
- 人工冷读抽样；
- 人物/关系轨迹；
- 伏笔与 Canon 审计；
- 成本和延迟复盘；
- 是否继续下一卷的显式决策。

不能用“运行完成”替代“内容可投稿”。

## 17. 可量化验收门

### 17.1 控制面

- 同一幂等键的 Provider 调用次数：`1`；
- interrupt / crash 恢复后的重复正式写回：`0`；
- 节点状态与 SSE completed/degraded/failed 不一致：`0`；
- 软诊断角色 unavailable 导致硬阻断：`0`；
- 必需硬角色未参与协调却放行：`0`；
- 旧 Context / Contract 签名命中审稿或写回缓存：`0`。

### 17.2 Context / Prompt

- Detail Prompt 不随总章节数线性增长；
- 正常 Detail `<= 12K` 字符；
- 正常单场正文 `8K-10K` 字符，硬上限 `16K`；
- P0 丢失：`0`；
- 同一权威事实重复渲染：`0`；
- Context 冲突未显式记录：`0`；
- Prompt trace 泄露正文或密钥：`0`。

### 17.3 多 Agent

- Reviewer 输入正文签名和 ContextSnapshot 不一致：`0`；
- Reviewer 直接写 Canon/Wiki/正文：`0`；
- 相邻章节并行生成：`0`；
- Patch 后无关 Reviewer 重跑：`0`；
- 每章自动 Patch 次数：`<= 1`；
- 超范围 Patch 被接受：`0`。

### 17.4 叙事与写回

- 无正文证据的正式 Canon/Wiki 写回：`0`；
- rejected / pending proposal 被后章检索：`0`；
- 人物同一状态的 `state_out -> next state_in` 无解释断裂：`0`；
- POV 越权硬错误：`0`；
- 已规划关键因果未实现却被标记 completed：`0`；
- FuturePlanPatch 未经 CAS/确认直接改后续 Detail：`0`。

文学质量不设虚假的自动百分制通过线。保留结构化技术指标，同时用人工盲读记录具体问题、修改量和是否愿意继续阅读。

## 18. 测试矩阵

### 18.1 StateGraph 单元测试

- 每个条件边和循环上限；
- Fast / Balanced / Deep 拓扑；
- 必需/可选角色超时；
- 节点 receipt 命中与失效；
- interrupt 前后幂等；
- subgraph 输入/输出 schema；
- state reducer 不覆盖无关字段。

### 18.2 Context 测试

- 32 章 Detail 不增长；
- P0 永不裁剪；
- 多来源同 claim 按权威顺序裁决；
- 旧 Canon、旧 Wiki、旧 Detail 不进入 Snapshot；
- POV 只看到可知事实；
- 零命中与失败检索区分；
- Context signature 对任一有效来源变化敏感。

### 18.3 Reviewer 测试

- 四角色真正并行并共享同一 Snapshot；
- 额外硬专项发现冲突时阻断；
- 任一硬专项 unavailable 时 degraded；
- 文学冷读 unavailable 只诊断降级；
- 每个角色独立报告、focus、operation ID 和预算；
- Patch 后只复检触发角色；
- 恢复能保留所有角色，不按旧双角色合同丢报告。

### 18.4 写回与恢复测试

- Context 漂移但正文未变时 fail-closed；
- marker 对 Contract、Context、Scene handoff 变化失效；
- 旧合同一对多迁移保留 lineage；
- Wiki/Canon 写回必须绑定 reconciliation 和 assertion evidence；
- FuturePlanPatch 使用 Detail baseline signature 与目标 revision CAS；
- 失败快照清理临时事务；
- 卷审计验证每条正式写回的正文证据。

### 18.5 故障注入

- Provider 在生成前、流式中、完成后断线；
- Checkpointer 写失败；
- Domain commit 成功但 SSE 失败；
- SSE 成功但客户端断线；
- Reviewer 部分超时；
- 进程在 interrupt、Patch、Canon commit 前后崩溃；
- 重启后 Provider 调用、Token 记录和正式写回不重复。

## 19. 回滚策略

- LangGraph 只对新 Run 通过 feature flag 开启；
- legacy Runner 在至少两个稳定版本周期内保留；
- 旧 Run 不迁移、不重签、不重写历史；
- Shadow / Dual Run 失败只丢弃影子状态，不影响领域主库；
- 新引擎失败可用相同输入创建 legacy Run，但必须保留失败 Run 审计；
- Domain Store schema 迁移必须向前兼容，回滚不删除新字段；
- Checkpointer 故障不能自动回退并重复执行 Provider，必须先检查 NodeReceipt；
- Canon / Wiki 已正式提交后不得通过运行时回滚静默撤销，只能建立修订分支。

## 20. 许可证与供应链边界

- LangGraph：MIT，可作为依赖使用；版本必须锁定并由 CI 验证；
- STORM：MIT，只参考研究/写作分层；
- NovelClaw：MIT，只参考工作区和有限循环；
- PlotPilot：Apache 2.0 + Commons Clause，不复制源码、不形成派生实现；
- CrewAI / PydanticAI：当前不引入；
- AutoGen / Langfuse：许可证元数据和商业边界需独立复核；
- 所有外部 Prompt、样例和测试语料必须记录来源与许可，不能把训练资产或 vendor snapshot 放入主产品树。

## 21. 代码边界草案

本节只定义未来归属，不代表本轮创建这些文件。

```text
src/novel_workflow/
  runtime/
    graph/
      global_graph.py
      stage_graph.py
      chapter_graph.py
      review_graph.py
      state.py
      commands.py
      event_adapter.py
      receipts.py
  context/
    broker.py
    authority.py
    retrieval_plan.py
    snapshot.py
    budget.py
  literary/
    agent_proposal_schemas.py
    evidence_ledger_schemas.py
    review_lane_schemas.py
  storage/
    graph_checkpoint.py
    domain_outbox.py
```

边界原则：

- `runtime/graph` 只做执行控制，不放 Prompt 文案、Canon 规则或 API 路由；
- `context` 负责最小充分上下文，不执行正文生成；
- `literary` 保持纯领域合同和可测试规则；
- `storage` 只做持久化和 outbox；
- `api` 继续是薄适配层；
- 大模块按独立变化责任拆分，不为行数机械拆分。

## 22. Definition of Done

Phase 20 只有同时满足以下条件才完成：

- [ ] 本文、ADR、实现和 Stage Artifact Contract 对 Reviewer 数量、写权限、墙钟预算和三档模式一致；
- [ ] ContextSnapshot、AgentProposal、EvidenceLedger、ReviewLaneSpec、NodeReceipt 合同稳定；
- [ ] Context Broker v2 不调用模型且不丢 P0；
- [x] `CharacterEpistemicSnapshot` 有生产写入端、逐字证据与签名，当前 POV 的最小可知世界进入 Writer P0，隐藏真相不泄露；
- [ ] Detail Prompt 不再随章节线性增长；
- [x] LangGraph Chapter Shadow 在固定失败 Run 上路由正确且零副作用；
- [ ] interrupt / crash 恢复不重复 Provider、Token 或写回；
- [ ] 所有 Reviewer 使用同一冻结 Snapshot；
- [ ] 可选文学角色不可用不会错误阻断；
- [ ] 所有硬角色结果真正参与协调；
- [ ] Patch 后只做定向复检，每章最多一次局部补丁；
- [ ] 叙事抽取的单条无证据叶 assertion 不触发整次重抽取：仅当其无逐字证据、无下游依赖、数量不超过 2 且占比不超过 15% 时确定性删除，并交由 Reality Reconciliation 认定对应计划未实现；被引用 assertion 或场景指纹失败继续 fail closed；
- [ ] Reality Reconciliation 是 Canon/Wiki 正式写回的强制前置；
- [ ] 新旧 SSE 合同对前端兼容；
- [ ] 三章真实 A/B 完成并有人类盲读记录；
- [ ] 单卷 8-12 章通过连续性、成本、恢复和卷级 Canon 审计；
- [ ] 完整长篇只在单卷通过后启动，并按卷设置人工检查点；
- [ ] 未用 AI Detector 或模型自评分冒充投稿质量证明；
- [ ] legacy 回滚路径经过演练且不篡改旧 Run。

## 23. 下一步执行顺序

1. 评审本文的 LangGraph 边界与三档 Agent 拓扑。
2. 把 `stage-artifact-contract.md` 已定义的多角色合同冻结为测试基线，补齐实现与恢复路径的偏差。
3. 把 B1 失败 Run 冻结为回放夹具，补齐角色漂移、复检预算和事件状态测试。
4. 在 legacy runtime 内完成 Context Broker v2 和数据合同，先证明质量瓶颈不是靠换框架掩盖。
5. Shadow 通过后建立 Chapter Dual Run 的录制 Provider、故障注入和事件适配基线。
6. Dual Run 通过后，才为新 Run 打开 Chapter Graph feature flag，禁止直接迁移 Global Graph。

## 24. 参考资料

- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Workflows and Agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangChain Multi-agent and Context Engineering](https://docs.langchain.com/oss/python/langchain/multi-agent)
- [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- [stanford-oval/storm](https://github.com/stanford-oval/storm)
- [shenminglinyi/PlotPilot](https://github.com/shenminglinyi/PlotPilot)
- [iLearn-Lab/NovelClaw](https://github.com/iLearn-Lab/NovelClaw)
- [wanqili857-byte/fictionforge](https://github.com/wanqili857-byte/fictionforge)
