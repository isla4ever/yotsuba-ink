# Yotsuba Ink Phase 27：后端合同与前端重构交接

> 状态：Phase 27 vNext 合同、前端工作台、浏览器矩阵与一次真实长篇 Run 已在 2026-08-17 完成 v1.0 Demo 收口。本文件保留为语义交接合同；真实 Run 的工程与质量边界见 `docs/engineering/yotsuba-ink-v1-balanced-110k-acceptance.md`，低置信文学 finding 见 `docs/engineering/yotsuba-ink-v1-open-findings.md`。
>
> 日期：2026-08-13。工作树为脏工作树，本文不授权 reset/revert/clean、启动本地服务、调用真实 Provider、恢复旧 Run 或提前推送。

## 1. 交接原则

下一位 Agent 可以重新决定视觉语言、组件组合、动效、2D/3D 比例、响应式断点和页面信息密度。不要把现有页面的 CSS、卡片结构或布局当作设计规范。必须保留的是后端语义和数据所有权：页面只能编辑当前阶段的一个核心 Artifact；运行状态、审稿、checkpoint、Evidence、写回和 Provider usage 都是 sidecar/read-model 投影，不能伪装成 Artifact 字段。

这次交接要解决的是“后端已经换成什么，UI 怎样准确地让作者做决定”。不是给每个阶段增加更多面板，也不是把原始 JSON 搬到前端。每一块界面都应回答四个问题：当前阶段唯一产物是什么、作者现在要做什么决定、决定写回哪里、下游真正需要什么。

权威阅读顺序：

1. [stage-artifact-contract.md](./stage-artifact-contract.md)
2. [phase-27-adaptive-story-planning-reconstruction.md](./phase-27-adaptive-story-planning-reconstruction.md)
3. 本交接文档
4. 相关 Pydantic/TypeScript contract 与 read-model/API 测试

Phase 26、25 及更早文档只用于理解失败证据。它们不是 UI 字段、stage id 或运行时行为的兼容来源。

## 2. 当前后端结论与验证边界

生产图只有一条顺序：

```text
brief -> spine -> cast -> volumes -> detail -> text -> cover -> export
```

生产运行时是直接 LangGraph Graph API：`StateGraph`、持久 checkpoint、`interrupt()`/`Command(resume=...)`、章节审稿的 `Send` 并发分支和领域事件投影。生产业务源码不应导入高层 LangChain API。不能恢复 Shadow/Dual/legacy Runner、旧 stage alias、Detail v1/v2/v3、converter、normalizer、repair、fallback 或 default injection。

当前离线证据（2026-08-17 提交前复核）：

- `.venv/bin/pytest -q`：`527 passed, 1 warning`；警告为既有 Starlette/httpx 弃用提示。
- `.venv/bin/python -m compileall -q src tests` 与 `git diff --check`：通过。
- 前端 Vitest `421 passed`；TypeScript/Vite production build、CSS audit 和首屏/lazy CSS split 通过。
- Volumes 真实阶段组件在 `1440x1000` 与 `390x844` 通过 event fixture -> reducer -> stage view 浏览器门；两卷切换、冻结 turn/人物引用、长度软建议和底部决策栏正常，无线程字段、横向溢出或控制台错误/警告。该门没有调用真实 Provider。

上述离线结果与真实 Run/浏览器记录共同构成本次 v1.0 Demo 证据。它们不等同于完整人工逐章冷读、投稿质量或真实图片生图验收；后续迭代仍按验收报告中的软告警推进，不能恢复历史 Run `phase26-deepseek-*`。

## 3. 后端分层：什么是事实，什么是投影

### 3.1 核心 Artifact（唯一可编辑事实）

核心 Artifact 使用 Pydantic `extra="forbid"`。模型输出缺键、未知键、Markdown fence、解释文字、截断 JSON 或解析失败都会让 operation 失败，不会自动修复。稳定 id、序号、哈希、状态、时间戳、版本号由代码绑定或派生，不由模型发明。

| stage | 核心 Artifact | 模型/代码字段边界 | 作者决定 | 正式写回 | 写回内容 | 下游只需要 |
| --- | --- | --- | --- | --- | --- | --- |
| `brief` | `StoryBriefArtifact` | 模型语义字段：`title`、`premise`、`promise`、`world_rules[]`、`theme`、`ending_promise`、`voice`；`length_envelope` 是用户软目标 | 故事承诺、不可违背的世界规则、主题问题、结局方向、声音、篇幅意图 | `ArtifactStore.brief` | 承诺、规则、主题、软长度 | 承诺、规则、主题、软长度；不带 Source Pack 全文 |
| `spine` | `StorySpineArtifact` | `turns[] {id,cause,change}`、`ending`、`open_questions[]`、`progress_types[]`；`id` 由代码绑定为连续 `turn-1...` | 因果链是否成立，最终变化是否兑现 Brief，哪些问题留给后续 | `ArtifactStore.spine` | turns、ending、开放问题、progress 类型 | turns、ending、open questions、Role Demand 输入；不带完整 Brief |
| `cast` | `CharacterBibleArtifact` | `subjects[] {id,name,kind,function,drive,change,debut,limits,demand_refs}`；`relations[] {a,b,type,pressure}`；`subject-*` 预分配，关系引用冻结 id | 叙事中心、主要/功能/NPC 责任、关系压力、人物变化、首次出现窗口 | `ArtifactStore.cast` | 唯一具名主体注册表与关系图事实 | 冻结 subject id、当前卷相关角色片段和关系引用 |
| `volumes` | `VolumeArchitectureArtifact` | `volumes[] {id,title,promise,conflict,climax,closure,turn_refs,cast_ids,length_hint}`；`volume-*` 和 turn 覆盖由代码校验 | 每卷是否是一个可独立成立的故事，边界、高潮、闭合和卷间承接 | `ArtifactStore.volumes` | 卷名、卷承诺/冲突/高潮/闭合、连续 turn refs、相关主体、短中长提示 | 当前卷合同和相关 cast；不带固定 chapter window 或无权威线程字段 |
| `detail` | `DetailArtifact` | `chapters[] {ref,volume_ref,purpose,pov,cast_ids,scenes[],handoff}`；scene 为 `{place,objective,conflict,turn,result}`；chapter ref 由代码连续绑定 | 每章的戏剧目的、场景冲突/转折/结果、结尾如何交给下一章 | `ArtifactStore.detail` | 章节施工图、POV、场景和 handoff | 当前章 manifest、当前卷、冻结人物片段、上一章 handoff |
| `text` | `ChapterArtifact`（按章版本） | `chapter_id`、`version_id`、`title`、`content`、`author_status`；正文 Provider 只返回纯文本，version/status/字数/receipt 由代码生成 | 接受、人工编辑、定向修订、保留分支 | `ChapterStore`，随后 Evidence proposal/Outbox | 当前章正文版本和接受状态 | 当前章正文、下一章 handoff、接受版本清单 |
| `cover` | `CoverArtifact` | `brief {concept,image_prompt,palette[],negative_constraints[]}` 与 `selected_asset_id`；图片 URL/尺寸/调用收据为 sidecar | 视觉方向、候选资产、最终封面 | `ArtifactStore.cover`、`AssetStore` | 可执行的视觉 Brief 和已选资产引用 | Export 的封面资产 ref |
| `export` | `ExportArtifact` | `format`（`md/json/zip`）、`chapter_version_ids[]`、`cover_asset_id`、`metadata {title,author,version_note}`；不调用 Provider | 格式、章节版本、封面和交付元数据 | `ExportStore` | 导出清单与交付回执 | 无 |

### 3.2 可派生投影（可以删除后重建）

以下内容不能作为表单事实写回：ScaleProfile、角色压力、角色图节点位置/颜色、卷卡节奏条、章节计数/卷归属、交接链摘要、引用集合、schema/prompt/manifest digest、Artifact 表单摘要、阶段导航 readiness。它们都必须从 Artifact、领域账本或 read model 派生。UI 可以展示它们，但不应提供“保存投影”的操作。

### 3.3 运行时 sidecar（只观察和追踪）

`NarrativeRunState` 只保存路由和引用：`run_id`、`graph_revision`、`stage_cursor`、`artifact_refs`、`current_unit_ref`、`chapter_cursor`、`scale_profile_ref`、`context_manifest_ref`、`pending_decision_ref`、`pending_review_refs`、`last_failure_ref`、`last_checkpoint_ref`、`state_revision`。Provider receipt、token/成本、review lane、checkpoint、interrupt、Evidence、Outbox 事务和 SSE 序列分别归属对应 Store/read model。

UI 必须让 sidecar 可见，但不能把 sidecar 当作内容编辑器：例如“审稿不可用”是状态，不是一个可以编辑的字段；“写回排队”是事务状态，不是正文内容；manifest hash 是诊断标识，不是作者要复制的正文资料。

## 4. 每阶段 UI 交接合同

下面的“主任务”和“必要辅助”是语义建议，不是组件或 CSS 限制。下一位 Agent 可完全重做布局，但不能改变信息归属、用户决策和写回目标。

### `brief`：创作立项

- 主任务：编辑并确认 `title/premise/promise/world_rules/theme/ending_promise/voice/length_envelope`。
- 必须可见：故事承诺、世界规则、主题、结局承诺、软篇幅；把字数/章数呈现为“建议/包络”，不能显示成机械配额。
- Source Pack：只有用户上传并主动选定时显示来源摘要、出处和采用状态；RAG 只能在前置规划阶段使用。
- 不应出现：人物完整关系图、Wiki、正文质量审稿、全量知识库原文、旧 `info` 字段。
- 决策提交：保存草稿与 `commit` 分开；commit 后才允许进入 `spine`。

### `spine`：因果脊柱

- 主任务：扫描 `turns[]` 的“因为 cause，局面 change”，检查结局兑现 Brief。
- 必须可见：因果顺序、最终 ending、有限 open questions、information/relationship/external/internal progress 标签。
- 辅助：只显示因果缺口、进度诊断、Brief 关键承诺的只读引用。
- 不应出现：章节施工表、具体人物行为脚本、每卷章数、人物自由添加入口。
- `RoleDemandProposal` 是窄调用结果，不属于 Spine Artifact；如展示，只作为“需要哪些戏剧职责”的待确认分析，并不能直接把人物写进 Cast。

### `cast`：人物编排/角色圣经

- 主任务：冻结正文前的主角、重要配角、功能角色、必要 NPC/历史记录的职责、驱动力、变化、限制、关系和首次出现窗口。
- 必须可见：角色档案、关系压力、demand 来源、debut 窗口、kind/tier、孤立/过载等诊断。debut 窗口使用本 Run 按篇幅与合理章长带推导的动态建议章数作为上下限；Spine turn 编号不是章号，UI 不得把二者等同。
- 人物拓扑：权威输入是 `CharacterBibleArtifact -> projectCharacterBibleGraph()`。节点只能引用 `subject.id/name/kind/tier/function/debut/status`；边只能引用注册主体的 `source/target/relation/pressure/polarity/valid_from_stage/valid_from_chapter` 等投影字段。画布只能发出选择事件，不能创建角色、编辑关系事实或改变 Artifact。
- 推荐交互：桌面可以使用 3D 星图/拓扑作为探索入口，选中后在同一工作区查看档案与关系；移动端默认名册/列表，再按需查看关系，不能强制加载 3D。
- 下游约束：`volumes/detail/text` 只能引用冻结 subject id。新增主体、职责升级、关系重定向或首次窗口变化必须走 `CharacterChangeProposal` + `interrupt()`，不可在下游偷偷补人。

### `volumes`：分卷故事架构

- 主任务：审阅每个自然闭合的卷合同：`title/promise/conflict/climax/closure`，以及 `turn_refs/cast_ids/length_hint`。
- Provider 按卷顺序窄调用；每次只看到本卷 `volume_spine_turns` 和上一卷 closure 交接，不读取完整 Spine 或相邻卷 turns。
- 必须可见：卷的完整故事承诺、核心冲突、高潮、闭合、卷间承接和容量建议；章节数只能显示为动态建议区间。
- 边界解释：`VolumeBoundaryProposal` 是窄调用的“候选边界 + 理由”，不是代码生成的剧情判断。代码只验证顺序、覆盖、重叠、引用和容量。
- 不应出现：固定“每卷 8 章”、每章剧情填空、角色行为细节、把总字数算术结果当作卷结构。

### `detail`：章节施工图

- 主任务：按卷/叙事段审阅章节施工表；每章看 `purpose/pov/cast_ids/scenes/handoff`，每个 scene 看 `place/objective/conflict/turn/result`。
- 必须可见：章节目的、独立场景冲突/欲望/变化、章末结果和 handoff。不要要求一章塞完整人物弧、世界观百科和所有伏笔。
- 章节边界：由叙事边界、POV 交接、地点/时间断裂、独立因果序列和 token ceiling 决定；不是固定 8 章切片。
- 辅助：可以显示当前卷合同、冻结人物引用、连续性诊断和 handoff，但保持只读来源标识。
- 下游：正文只取当前 chapter 的 manifest，不把整个 Detail 或上游全文注入 Prompt。

### `text`：单章正文与写回

- 主任务：阅读/编辑单章纯文本，处理 review finding，然后接受、定向修订、人工编辑或保留分支。
- 必须可见：正文、当前章标题、章节导航、审稿 lane（`continuity`、`character`、`prose`）、精确证据、决策状态、Context Manifest 摘要、checkpoint 和写回状态。
- 正文协议：Provider 返回纯文本流，不包 JSON；UI 不显示“JSON 解析”或原始 token 流作为正文。标题优先使用已批准 Detail，确需改标题是独立短调用。
- Context Manifest：展示“本章为什么拿到这些片段”的可读摘要（task、required/optional、forbidden 的人类语言、来源和预算），不要直接展示原始 JSON/hash；详情可在单独诊断抽屉中查看。
- 审稿：reviewer 只读当前不可变正文版本，不能直接改正文或写 Canon/Wiki。finding 必须带正文精确 evidence 和冻结 subject ids；无效 finding 应显示 `review.unavailable`，不能静默过滤。
- 写回：Evidence 先提案，Canon/Wiki/Outbox 再按批准状态写回；“保存草稿”不等于正式写回。

### `cover`：视觉 Brief 与资产

- 主任务：编辑 Cover Brief、查看候选图、选择正式资产。
- 必须可见：concept、image_prompt、palette、negative_constraints、资产状态、尺寸/来源/收据摘要。
- 文本 Brief 和图片 Provider 是两个调用；图片失败要明确失败，不展示 fake 资产冒充成功。
- 不应出现：运行时人物图谱、章节审稿面板、全量上下文。

### `export`：交付

- 主任务：选择 `format`、已接受章节版本、封面资产和 metadata，执行校验与导出。
- 必须可见：版本清单、缺失/未接受章节、封面选择、标题/作者/版本说明、验证结果、下载/打包回执。
- Export 不调用 Provider，不反推或修改任何上游 Artifact。

## 5. UI 一致性：约束语义，不锁定风格

接手 Agent 可以选择深色驾驶舱、浅色编辑器、黑晶、纸张或其它专业方向，但八个阶段必须像同一个写作工具：

- 统一导航、阶段状态、错误/等待/提交反馈和决策操作位置；阶段颜色可以变化，但语义颜色（成功、阻断、警告、不可用）不能随页面改变含义。
- 主 Artifact 永远有明确的主阅读/编辑区域；辅助信息通过侧栏、抽屉、时间线、表格或局部弹层承载，避免卡片堆叠和“为填空而填空”。
- 输入必须拥有清晰边界、label、focus/invalid 状态、合理 min/max width 和中文长文本换行；禁止固定窄列导致挤压、遮挡或横向溢出。
- 长内容由内部滚动容器负责，页面 body 不被强制滚动到陌生位置；决策/确认操作必须在可靠的 sticky/fixed action dock 中保持可达，并避开移动端安全区。
- 桌面和移动是两个布局，而不是把桌面三栏压缩。3D 画布必须懒加载、可暂停、可卸载，并有列表降级和键盘可达的替代入口。
- 不展示原始 JSON、Graph State、Prompt 全文、内部 stage alias、Provider secret 或不可读 digest。可读的来源/状态摘要优先，诊断详情再进入抽屉。
- 动效只表达生成、切换、聚焦、审稿和写回状态；背景星空、粒子和图片素材不能夺取正文阅读焦点，也不能成为事实来源。

建议建立一个小而稳定的 design token 层（surface、text、muted、accent、danger、success、focus、stage accent、spacing、radius、shadow），由八阶段复用。具体字体、材质、线框、动效和是否使用生成图片由 UI Agent 评审决定；不要把“科技感”实现成持续高成本动画或大量装饰面板。

## 6. 人物拓扑参考与复用边界

### 6.1 与叙事产品相关的两个源码项目

1. **PlotPilot**：`https://github.com/shenminglinyi/PlotPilot`，HEAD `7dc03a37a06b57e823df222da0e3bde5d1c84715`，记录日期 2026-07-19。仓库实际许可证为 Apache-2.0 + Commons Clause（含禁止销售条款；GitHub API 返回 `NOASSERTION`），因此不能直接复制代码、Prompt 或 UI，也不应把它作为商业派生实现。可借鉴的抽象是临章执行计划、连续性账本、角色上下文锁、Prompt/context 装配、checkpoint/recovery 和可观测事件。
2. **FictionForge**：`https://github.com/wanqili857-byte/fictionforge`，HEAD `c381297e2c6c670f374933d850b9b85756dead27`，记录日期 2026-08-06，MIT。可借鉴 TickRunner/ChapterCoordinator 的“长线计划 -> 临章 spec”、相邻章节顺序生成、世界真相与人物认知分层。不能复制其双管线、机械 spec、fallback 或静默降级；Yotsuba 的唯一事实仍是本文件的 Artifact/Graph/Store 合同。

这两个项目是叙事编排思想的来源，不是前端拓扑组件来源。完整许可证与源码取舍台账在 Phase 27 主文档中维护。

### 6.2 与人物图谱直接相关的两个开源技术参考

- `react-force-graph-3d`（Vasturiano 生态）：当前仓库已使用并懒加载，适合把 `CharacterGraph` 投影为可旋转/聚焦的三维关系图。只读取节点/边投影；需要锁定实际版本并重新核对许可证、bundle 和 WebGL 性能。
- `three`：底层 WebGL/相机/材质运行时，当前仓库已有依赖。可用于自定义星点、标签和相机过渡，但不应另造第二套人物事实模型或把地球/星空装饰绑定到剧情数据。

这两个库是实现参考，不是产品合同。人物拓扑只在 `cast` 作为编辑/冻结工作台的主视图；`volumes/detail/text` 仅显示当前引用主体的只读邻域或名册投影。任何“点击星点新增人物”“拖边改变关系”都必须被拒绝或改成显式 `CharacterChangeProposal` 流程。

## 7. API、SSE 和前端状态对接

前端通过现有 API/read model 读取事实和运行投影，不读取 Graph State：

| 用途 | 读取方式 | UI 责任 |
| --- | --- | --- |
| Run/阶段状态 | `GET /api/runs/{run_id}` 的 `definition` 与 `read_model` | 阶段导航、运行状态、artifact ref、pending decision、checkpoint、failure、usage 摘要 |
| Context Manifest | `read_model.context_manifest_ref`，再读 `GET /api/runs/{run_id}/context-manifests/{manifest_id}` | 生成可读的上下文来源/预算摘要；不展示原始 hash/JSON 作为正文 |
| 运行事件 | SSE 稳定领域事件 | reducer 只处理 `run/node/artifact/decision/review/evidence/writeback/checkpoint` 事件；不得猜测事件文案生成字段 |
| Artifact | artifact ref 对应的 API/服务投影 | 只编辑当前阶段 Artifact；草稿和 commit 分开；提交后显示回执 |
| 人物图 | `CharacterBibleArtifact` 的确定性 `CharacterGraph` 投影 | 选择/聚焦/过滤，不直接写回节点/边 |

必须覆盖这些状态：生成中、待人工决策、已提交、失败、审稿不可用、写回排队、写回成功、写回失败、断线重连和 checkpoint 恢复。状态展示应可读，但不可通过“看起来成功”的绿色标签掩盖失败 receipt。

## 8. 交接后的建议执行顺序

1. UI Agent 先读本文件和两个权威架构文档，做一次只读 API/contract audit，列出当前页面与后端字段的差异。
2. 先建立八阶段信息架构和共享状态/表单边界，再决定是否生成原型图。原型图只服务布局讨论；不替代真实 Artifact 数据。
3. 先完成 `brief/spine/cast/volumes/detail/text` 的核心编辑与状态投影，再做 `cover/export`；每一步都保留旧路径静态缺席门。
4. 用真实 API fixture/fake Graph 做浏览器离线验收：1280x920、1440x1000、1728x1100 和 390px；检查横向溢出、内部滚动、sticky 决策栏、焦点、模态层、长中文换行和 3D 加载/卸载。
5. UI 测试/build/CSS 审计通过后，才由另一项明确批准开启真实 Provider：全新 Run、先三章门禁、脱敏 operation receipt、断线/恢复和人工文学冷读；真实图片 Provider 单独验收。
6. 所有离线、浏览器和真实验收完成后，才统一审查范围、提交并只推送 GitHub `main`。Gitee 不参与；不盲删未证明已合并的分支。

## 9. 不可误读的限制

- 当前 `278 passed` 是后端离线合同证据，不是在线 Provider 证据。
- 软字数、角色数量、卷数和章节数是建议/诊断，不是固定模板；完整卷闭合优先于平均章数。
- 正文之前冻结人物；下游不能“顺手添人”。
- RAG 只对用户上传并选定的 Source Pack 在前置规划启用；正文不盲检索。
- Canon/Wiki/Memory/Evidence 是证据驱动的辅助系统，不是创作警察；低置信冲突和软目标偏差先诊断/人工确认，不自动删改正文。
- UI 可以完全推翻当前实现，但不能改变 stage 顺序、Artifact 字段含义、写回所有权、事件语义或真实验收门槛。
