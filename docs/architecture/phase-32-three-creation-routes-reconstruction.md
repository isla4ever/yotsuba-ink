# Phase 32：三种创作路线前后端重构计划

> **2026-09-06 发布边界修订**：经用户确认，`v0.1.0` 以三路线文本链、恢复、写回、质量证据和浏览器闭环为阻断门。封面图片生成不进入本次验收；短中篇与长篇以真实 `CoverBrief` 和唯一 `image_deferred` 终态证明边界，不得生成占位 CoverAsset 或宣称完整图片交付。本文中把图片、文学成品或规模性能列为体验版阻断项的早期表述，均以此修订及 Wave 67 发布候选报告为准。

> **2026-09-06 公开创建合同修订**：`v0.1.0` 的新建入口只允许选择 `official.screenplay_sample`、`official.short_novel`、`official.long_novel` 三条现有官方路线。本文早期关于“新建流水线”、自定义模板或从旧 workflow catalog 匹配新 Project 的表述不属于本次发布合同；这些能力若未来重启，必须以新的 Artifact、写回与迁移设计单独验收。旧 workflow 记录只保留只读历史线索，不得产生新的 canonical Run。

状态：**Wave 0-67 的三路线生产权威、文本运行、人工决定、恢复、写回、监控、交付证据和真实 DeepSeek exact-12 已闭合，进入 `v0.1.0` 发布候选。工程连续性通过；文学成品质量仍有明确 warning；图片验收按上述修订独立延后。**

日期：2026-08-22

> 2026-08-25 进度补记：Wave 33 已统一阅读/编辑双态与 184px 二级导航并完成 Rolling Detail；Wave 34-37 已依次完成 Section Plan、Beat Board、Scene Deck 与逐 Scene Script；Wave 38 已完成剧本确定性交付；Wave 39 已完成短中篇逐单元 Text、窄上下文、跨进程恢复与五视口浏览器闭环；Wave 40 已完成短中篇真实封面资产、正式选择草稿、确定性 Book Delivery、DOCX 下载与文件/封面双哈希验证；Wave 41 已完成长篇逐章 Text、accepted prefix、作者草稿、Cover 与 ordered Chapter Manifest/Book Delivery 闭环，并修复混合已知/未知 Provider 成本导致 read model 回退的上游汇总错误；Wave 42 已把作者协作迁为三路线 stage capability，闭合线程、首次 Context Receipt、选区改稿候选、拒绝保护、历史切换和三视口浏览器门；Wave 43 已把监控台改为同一 Run read model、Artifact Store 与正式事件流的只读内容投影，闭合完成、失败、逐单元待审和三视口抽屉/焦点门；Wave 44 已把 Story Bible 改为 committed Artifact 与 accepted sequential prefix 的三路线只读投影，闭合候选隔离、真实分页、来源跳转和三视口浏览器门；Wave 45 已完成 committed 规划 Artifact 的 source-bound amendment、确定性 ImpactAnalysis、新 committed version、stale Run 投影、Provider preflight blocker 和 receipt 中断恢复；Wave 46 已完成 amendment successor Run、旧 accepted prefix 保护、Project lineage、唯一 plan、事件与 receipt 中断恢复，并删除未接生产且语义冲突的通用 branch contract；Wave 47 已在九个规划工作台接入正式修订副本、影响预览、scope 选择、stale 恢复和 successor 跳转，完成 `1440x920 / 1024x700 / 390x844` Portal、焦点循环、Reduced Motion 与单 Loader 浏览器门。Wave 48 随后完成正式 Canon/Wiki writeback、恢复决策、三路线 Fake Provider 浏览器矩阵与全量离线门；自动无障碍、规模/性能、分级真实 Provider 与文学冷读门仍未闭合。

> 2026-08-24 发布门补记：全部功能迭代与离线门完成后，以三条新官方路线分别执行一次小规模真实全链路 Run。`0.1.0` 体验版只以链路稳定性和确定性交付为发布阻断门，文学质量作为非阻断观察；三条同时通过后才重写 README/CHANGELOG、推送并发布 `v0.1.0`，随后删除旧 Release/Tag。

> 2026-08-26 进度补记：Wave 48 的 Phase 32 写回恢复已完成定向回归、隔离浏览器矩阵和全量离线门。剧本样片进入 `export`，短中篇进入 `cover` 待决策，长篇进入下一章待决策；每条已重试路线只产生 1 次写回 Provider 请求。另一条长篇 Run 保持 `writeback_recovery`，Story Bible 明确提示恢复而不自行补写；已提交态 Story Bible 显示 Canon/Wiki 正式事实只读投影。后端 `1123 passed, 1 warning`，前端 `68 files / 170 tests`，TypeScript/Vite、CSS/结构、CSS build、oxfmt、compileall、closure audit 和 `git diff --check` 均通过；隔离服务已停止，未调用真实 Provider。证据与截图见 `docs/engineering/phase-32-wave-48-canon-wiki-writeback.md`。Wave 48 已关闭，真实 Provider、自动无障碍、规模/性能、文学冷读和 `0.1.0` 发布门继续保持未闭合。

> 2026-08-26 真实 Provider 补记：在 Wave 48 离线门通过后，按用户授权创建全新小规模 Run。`release-smoke-screenplay-20260826-r7` 冻结 `provider-deepseek-text / deepseek-v4-flash`，3 个 Script scene、3 个 writeback 均完成，10/10 Provider operation 成功、严格 JSON 解析 10/10 `exact_object`、无 pending operation，并持久化 Fountain 交付。`release-smoke-short-20260826-r3` 的 Brief 首次真实网络错误在同一 operation 上以 `transport_attempts=2` 恢复，3 个 Text unit 与 3 个 writeback 完成；Cover 因图片定价快照缺失按 fail-closed 停止。另做 3 次低成本重复探针，响应完全一致。详见 `docs/engineering/phase-32-wave-49-real-provider-stability.md`。这关闭了“小规模文本链路稳定性”证据，不关闭三路线真实 Provider、图片成本、自动无障碍、规模/性能、文学冷读或 `0.1.0` 发布门。

> 2026-08-26 长篇补记：真实 Run `release-smoke-long-20260826-r4` 在修正 release-smoke 长篇目标与两组长篇 Prompt 合同后完成 Brief、Book Architecture、Cast、Volumes、Rolling Detail、2 个 Chapter 和 2 个 writeback，10 个文本 operation 均为 `exact_object`；随后在 Cover 图片定价门按 fail-closed 停止。此前 `r1-r3` 的长篇失败分别暴露篇幅下限、Part promise ref 和 Detail nested field 漂移，均已添加离线重现与合同测试。由于这些修复发生在早期真实 Run 之后，最终发布证据仍必须在代码冻结后从三条路线重新创建。

> 2026-09-06 进度补记：Wave 52-60 已把三路线 smoke、正文连续性、确定性交付、Provider admission、冻结预算和 release evidence 接回同一 Phase 32 权威；Wave 61-64 以全新 exact-12 长篇 Run 推进到 Rolling Detail，DeepSeek 返回完整 12 章结构，但 `chapter_01` 在 Chapter Cast 外引用 `mentor`，以 `provider_contract_failed` 安全停止。Wave 65 建立 Schema 合法拒绝稿的隔离、完整 source binding、稳定身份/引用重校验、不可变 Candidate、LangGraph checkpoint 恢复与幂等 repair receipt；Wave 66 接入作者工作台并在 `1440x920 / 1024x700 / 390x844` 证明失败摘要、受限人物范围编辑和显式 Candidate decision 闭环，Provider operations 保持 9。正式证据 Run 仍为只读失败态，图片调用保持 0。详见 `docs/engineering/phase-32-wave-65-contract-quarantine-repair.md` 与 `docs/engineering/phase-32-wave-66-contract-repair-workbench-closure.md`。

当前权威：

- `docs/architecture/stage-artifact-contract.md`
- `docs/architecture/phase-28-v1.1-literary-reliability-and-author-control.md`
- `docs/architecture/phase-29-v1.1-million-character-author-led-deep-mode.md`
- `docs/architecture/phase-30-figma-ui-production-migration.md`
- `docs/architecture/phase-31-deep-mode-author-collaboration.md`

本文件描述三路线的总目标合同。用户已批准该方向，`stage-artifact-contract.md` 与 Phase 32 已成为当前生产权威；每项能力是否闭合仍以对应 Wave 的正向、删除、测试、浏览器和真实 Provider 退出门为准。不得把局部技术闭环表述为文学验收、图片验收或体验版发布完成。

## 1. 执行结论

Yotsuba Ink 不再把 `fast / balanced / deep` 当成三种创作模式。它们把作品类型、自动化程度、模型配置和质量策略混在一起，导致三套模板实际上运行同一条八阶段链路，差异只剩模型、颜色和是否自动接受，无法形成清晰的产品价值。

下一代产品只保留三种由交付物决定的创作路线：

1. **剧本样片**：快速验证一个故事能否在可见动作、场景与对白中成立，输出可阅读、可演示、可继续改编的规范剧本样片。
2. **短中篇小说**：完成一个有明确读者承诺、完整收束和可控篇幅的单体小说，避免长篇层级给短作品增加无意义负担。
3. **长篇小说**：面向多 Part、多卷、长期连载和专业作者协作，使用层级架构、滚动细纲、状态账本与提交后修订维持长期连续性。

三条路线拥有不同阶段、Artifact、工作台、默认审阅策略和质量检查，但共享一套：

- LangGraph 权威运行时与 checkpointer；
- Run、Provider operation、receipt、usage、checkpoint 与恢复语义；
- Evidence、Outbox、Canon/Wiki 和 Resolved Story State；
- SSE 事件、read model 和监控控制台；
- Provider 绑定、知识库、Source Pack 和作者协作 sidecar；
- Version 20 暗黑专业创作台设计系统。

不建立三套 runtime、三套 Store、三份复制页面或 `legacy / v2 / fallback` 兼容路径。差异通过一个 `CreationRouteSpec` 编译为不同 LangGraph 图，通过 Artifact 和 `workbench_kind` 投影为不同 UI。

## 2. 当前系统的最低责任问题

### 2.1 固定八阶段已经写入多层合同

当前不是“改三个模板名”就能升级：

- `workflows/definition_schemas.py` 把 `NodeType` 和 `QualityMode` 固定为八阶段与三档模式；
- `workflows/executable_contract.py` 要求节点与边精确等于 `STAGE_ORDER / PHASE27_EDGES`；
- `runtime/graph/stage_graph.py` 通过 `quality_mode == fast` 自动接受全部阶段；
- `NarrativeRunState`、Run read model、前端 `StageType / QualityMode` 和路由都假设八阶段固定存在；
- Header、工作流模板、Project Shell 和监控页按八个固定节点投影；
- Provider Prompt、Artifact parser、Context compiler 和恢复逻辑仍以 `spine / volumes / detail` 为共同前提。

因此必须从 Workflow/Run 合同开始纵向迁移，不能只改 Figma 页面或 JSON 模板。

### 2.2 旧三档缺少独立价值

| 旧模式 | 当前真实差异 | 产品问题 |
| --- | --- | --- |
| Fast | 自动接受阶段、少量修复差异 | 把“没人审”误当成“更快”，文学告警仍会被带到下游 |
| Balanced | 人工阶段决策 | 与 Deep 的作品结构相同，没有独立创作方法 |
| Deep | 人工决策、作者协作和长篇层级候选 | 专业能力被绑在一个质量档，而不是作品结构和作者需要上 |

作品类型、审阅密度、Provider 质量和自动化程度必须拆开。用户选择的是要交付什么；流水线再决定在哪里暂停、用什么模型和允许何种有界修复。

### 2.3 固定线性因果脊柱不应继续作为共同阶段

规划本身有正收益，但“每个重大节点都必须由模型准确写成 `cause -> change`，再把全书塞进一条线性链”并不可靠：

- 它容易把同一调查、取证或关系变化拆成重复 turns 以满足数量；
- 线性链难以表达并行人物线、主题回声、悬念延迟兑现和长篇局部改道；
- LLM 对叙事因果的判断可以作为诊断证据，但不能成为无限自动换稿的硬权威；
- 当前精确 turn 数、固定里程碑位置和语义预审叠加，已经让结构配额压过了作品需要。

Phase 32 保留规划，但按交付物改造为：

- 剧本样片：**决策节拍 + 场景结果**；
- 短中篇：**Story Map + 章节/段落计划**；
- 长篇：**Book/Part Architecture + Volume Contract + Rolling Detail Window**。

确定性代码只校验身份、引用、顺序、覆盖、状态和写回边界。动机是否充分、因果是否有说服力、高潮是否有效等文学判断进入 warning、作者协作或人工抽检，不能引发隐藏重试。

## 3. 外部依据与产品口径

本节只用于校准产品，不把奖项或研究口径冒充行业唯一标准。检索日期均为 2026-08-22。

| 来源 | 可采用结论 | 不直接照搬 |
| --- | --- | --- |
| [第九届鲁迅文学奖参评作品征集公告](https://www.chinawriter.com.cn/n1/2026/0302/c403937-40672666.html) | 中文文学口径：小小说 2,000 字以下、短篇 25,000 字以下、中篇 25,000-130,000 字 | 奖项分类不是产品技术上限，也不覆盖网络长篇运营 |
| [SFWA Nebula Rules](https://sfwa.org/complete-nebula-awards-rules/) | 英文奖项以 7,500 / 17,500 / 40,000 words 区分 short story、novelette、novella、novel | 英文 word count 不能直接换算成中文字符数 |
| [Plan-and-Write](https://ojs.aaai.org/index.php/AAAI/article/view/4726) | 显式故事线规划优于完全无规划生成 | 不证明固定五点或一条全书线性链适合所有作品 |
| [Re3](https://aclanthology.org/2022.emnlp-main.296/) | 结构计划、滚动相关上下文、重写与局部编辑能改善长程连贯 | 研究中的多候选 rerank 不能变成产品里的隐藏烧 token |
| [DOME](https://aclanthology.org/2025.naacl-long.63/) | 动态层级大纲和状态记忆比完全固定大纲更适合长篇不确定性 | 不引入第二套知识图谱权威或论文专用训练管线 |
| [CONCOCT](https://aclanthology.org/2023.findings-emnlp.723/) | 层级大纲需要控制抽象层次和节奏密度 | 不把自动 concreteness 分数作为文学硬门 |
| [ReCITE / ACL 2026](https://aclanthology.org/2026.acl-long.1003/) | LLM 从真实文本推断因果关系仍存在显著困难，因果判断需要证据与人工校准 | 不把该基准分数直接换算成创作质量分数 |
| [Oscars Screenwriting Resources](https://www.oscars.org/nicholl/screenwriting-resources) | 剧本样片应以 master scene format 的场景标题、动作和对白为中心，清晰优先 | 不把细微排版差异作为阻断创作的绝对标准 |

### 3.1 产品篇幅政策

| 路线 | P0 支持范围 | 推荐默认 | 决策逻辑 |
| --- | ---: | ---: | --- |
| 剧本样片 | 3-30 分钟目标时长 | 8-15 分钟 | 以分钟/规范页和场景承载为中心，不用小说字数控制 |
| 短中篇小说 | 2,000-130,000 中文字符 | 网络短故事推荐 10,000-30,000 | 25,000 是短/中篇编辑提示，不改变运行时权威 |
| 长篇小说 | 100,000-1,000,000 中文字符 | 首次正式验收 100,000-200,000 | 采用 Part/Volume/Window 分层；超过 1,000,000 在完成规模门前不承诺生产支持 |

`100,000-130,000` 是有意保留的重叠区：

- 单一主线、少量人物、无需多 Part/多卷长期演进时推荐短中篇；
- 多 Part、多卷、多条长期 Promise、人物 scope 和持续连载时推荐长篇；
- 向导给出解释和推荐，但用户可改选；Run 创建后路线冻结，切换路线必须创建新 Run。

篇幅始终是软目标。只有正文/剧本为空、明显截断，或低于冻结最低可用比例时阻断。达到最低可用后，以内容完整、连续、可读和兑现承诺为主，不为凑字数自动扩写、截断或换稿。

## 4. 路线与审阅策略解耦

### 4.1 `CreationRouteId`

```text
screenplay_sample
short_novel
long_novel
```

路线决定：阶段图、Artifact、篇幅单位、工作台、默认 Context 和导出格式。

### 4.2 `ReviewPolicy`

审阅策略是 Workflow 配置，不是第四种模式：

```text
review_policy:
  checkpoint_policy: milestone | every_stage | every_unit
  warning_policy: continue_and_surface | pause_at_milestone
  contract_correction_limit: 1
  directed_redraft_limit_by_stage: 0..2
  auto_continue_stages: [stage_id]
  mandatory_decision_stages: [stage_id]
```

默认值：

| 路线 | 默认暂停点 | 默认自动继续 |
| --- | --- | --- |
| 剧本样片 | Brief、Beat Board、最终 Script | Cast 初稿、Scene Deck 单元通过确定性门后 |
| 短中篇小说 | Brief、Story Map、最终 Manuscript | Cast/Section Plan 可在用户启用后自动继续 |
| 长篇小说 | Brief、Book Architecture、每个 Part/Volume 边界、每个 Detail Window、正文接受 | 只自动执行同一已批准 Window 内的窄节点 |

用户可在建 Run 前调整，但系统不得提供“忽略所有错误并一路冻结”的开关。确定性 blocker 永远暂停；文学 warning 可以按策略在里程碑汇总，而不是每条告警打断创作。

## 5. `CreationRouteSpec` 目标合同

```text
CreationRouteSpec
  route_id
  revision
  label
  deliverable_kind
  length_policy_ref
  default_review_policy_ref
  stages[]
  capabilities[]
  export_profiles[]

RouteStageSpec
  stage_id
  label
  artifact_kind
  workbench_kind
  provider_task_kind?
  upstream_stage_ids[]
  unitization: aggregate | bounded_units | sequential_units | deterministic
  decision_policy_ref
  context_policy_ref
  collaboration_enabled
```

编译规则：

1. 恰好一个起点和一个交付终点；图必须无环。
2. 每个阶段恰好一个用户可编辑/确认的核心 Artifact；review、receipt、usage、checkpoint 和日志是 sidecar。
3. 下游声明的 Artifact 依赖必须在上游可达，不能靠 route 文件顺序猜测。
4. `export` 为确定性节点，不绑定文本 Provider。
5. 每个 Provider stage 必须绑定同类型 Prompt、Schema 和 Context policy。
6. Run 创建时冻结 route revision、实际阶段图、ReviewPolicy、ScaleProfile 和 Provider bindings。
7. 前端只消费服务端返回的 route manifest，不再维护独立固定阶段数组。

## 6. 三种路线的完整阶段合同

### 6.1 剧本样片

生产图：

```text
brief -> cast -> beat_board -> scene_deck -> script -> export
```

| 阶段 | 核心 Artifact | 用户决定 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `brief` | `ScreenplayBriefArtifact` | 正式片名、样片类型、目标时长、核心命题、观众承诺、可见冲突、结尾效果和语气 | Planning aggregate | Cast、Beat Board、Export |
| `cast` | `CharacterBibleAggregate` | 屏幕上真正需要的人物、目标、利害、行为限制、说话差异和关系压力 | Planning aggregate | Beat Board、Scene Deck、Script |
| `beat_board` | `BeatBoardArtifact` | 哪些决策和结果值得被看见，节奏是否完成样片承诺 | Planning aggregate | Scene Deck |
| `scene_deck` | `SceneDeckArtifact` | 场景顺序、地点/时间、参与者、可见目标、对抗、结果和目标页数 | Planning aggregate | Script |
| `script` | `ScreenplayDraftArtifact`（按 scene/version） | 接受、局部改写、分支或回到 Scene Deck 修订 | Script version store，Evidence proposal 后写回 | Export、Adaptation Package |
| `export` | `ScriptDeliveryArtifact` | 导出 Fountain/PDF/Markdown、标题页与版本注记 | ExportStore | 无 |

`BeatBoardArtifact` 不要求每个 beat 都证明完整因果链。单个 beat 只保存：

```text
beat_ref
dramatic_job
visible_pressure
character_decision
outcome
setup_or_payoff_refs[]
timing_hint
```

Beat 的顺序、引用和覆盖是硬合同；“这个决定是否足够可信”“这个结果是否有冲击”是 warning/人工判断。

`SceneDeckArtifact` 面向可拍摄内容，不写小说式内心梗概。场景至少包含 master scene heading、可见行动、冲突与结果；Scene Deck 可以合并或拆分未来场景，但已接受 Script scene 不得被原地改写。

### 6.2 短中篇小说

生产图：

```text
brief -> story_map -> cast -> section_plan -> text -> cover -> export
```

| 阶段 | 核心 Artifact | 用户决定 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `brief` | `NovelBriefArtifact` | 正式书名、前提、读者承诺、主题问题、世界硬规则、结局方向、叙事声音和软篇幅 | Planning aggregate | Story Map、Export |
| `story_map` | `StoryMapArtifact` | 开场压力、核心问题、不可逆选择、承诺推进、收束条件是否足够支撑单体故事 | Planning aggregate | Cast、Section Plan |
| `cast` | `CharacterBibleAggregate` | 必要人物、欲望、利害、限制、关系与变化范围 | Planning aggregate | Section Plan、Text |
| `section_plan` | `SectionPlanArtifact` | 章节/段落单元、戏剧任务、POV、场景负载、handoff 和软预算 | Planning aggregate | Text |
| `text` | `ShortProseUnitArtifact`（按 unit/version） | 接受、人工编辑、定向改写、分支或上游修订 | Prose unit version store + Evidence/Outbox | Cover、Export |
| `cover` | `CoverArtifact` | 视觉 Brief、候选资产与正式封面 | ArtifactStore + AssetStore | Export |
| `export` | `BookDeliveryArtifact` | 格式、正文版本、封面与交付元数据 | ExportStore | 无 |

`StoryMapArtifact` 使用有限结构锚点，不使用精确 turn 配额：

```text
opening_state
story_question
anchors[]:
  anchor_ref
  dramatic_job
  pressure
  choice_or_revelation
  consequence_or_open_effect
  promise_refs[]
ending_state
open_questions[]
```

Provider 在 ScaleProfile 给出的容量范围内提出锚点数量，代码只校验范围、稳定 ref、Promise 覆盖和顺序。用户接受后才冻结；后续调整通过 amendment，不用隐藏重新规划凑数量。

`SectionPlanArtifact` 可按篇幅投影为单篇段落、章节或小型窗口，但 UI 统一称为“章节/段落计划”。短作品不强制分卷，不生成空泛卷名，也不要求每章固定场景数。

`ShortProseUnitArtifact` 是唯一正文单元合同；它的 code-owned `unit_kind=section|chapter` 从冻结的 Section Plan 投影，Provider 只返回标题对应的纯正文。不存在 Chapter/Section 两套可执行正文 Artifact。

### 6.3 长篇小说

生产图：

```text
brief -> book_architecture -> cast -> volumes -> rolling_detail -> text -> cover -> export
```

| 阶段 | 核心 Artifact | 用户决定 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `brief` | `NovelBriefArtifact` | 正式书名、长期读者承诺、世界规则、主题、终局方向、声音和规模 | Planning aggregate | Book Architecture、Export |
| `book_architecture` | `BookArchitectureAggregate` + `PartContractArtifact` | 全书问题、Part 边界、各 Part 进入/退出状态、Promise 推进和终局条件 | Planning aggregate | Cast、Volumes |
| `cast` | `CharacterBibleAggregate` | Book/Part/Volume scope、人物职责、关系、限制、弧线和归档 | Planning aggregate | Volumes、Rolling Detail、Text |
| `volumes` | `VolumeArchitectureAggregate` + `VolumeContractArtifact` | 每卷承诺、冲突、高潮、闭合、Part 归属和人物/结构引用 | Planning aggregate | Rolling Detail |
| `rolling_detail` | `DetailPlanIndexArtifact` + `DetailWindowArtifact` | 当前 1-3 卷或 12-40 章的施工图、场景、handoff 和下一窗口入口状态 | Planning aggregate | Text、下一 Window |
| `text` | `ChapterArtifact`（按章版本） | 接受、人工编辑、定向改写、分支或未来规划 amendment | ChapterStore + Evidence/Outbox | 下一章、下一 Window、Cover、Export |
| `cover` | `CoverArtifact` | 视觉 Brief、候选资产与正式封面 | ArtifactStore + AssetStore | Export |
| `export` | `BookDeliveryArtifact` | 版本清单、封面、格式和元数据 | ExportStore | 无 |

`BookArchitectureAggregate` 取代全书 flat Spine：

```text
book_root
  book_promise
  central_question
  part_refs[]
  global_milestone_refs[]
  ending_conditions[]

PartContractArtifact
  part_ref
  title
  entry_state
  dramatic_question
  promises_opened[]
  promises_advanced[]
  turning_points[]
  exit_state
  unresolved_obligations[]
```

Part 内允许多个并行推进，不要求全部压成一个 `cause/change` 数组。代码确定性检查 Promise 生命周期、Part 顺序、引用和 entry/exit state 的来源；文学上的动机桥和说服力由 advisory review 与作者确认处理。

Rolling Detail 延续 Phase 29 的层级候选、聚合提交、稳定 ref、window handoff 和 amendment 方向。当前 Phase 29.1 的候选持久化能力作为实现基础，不等于已经完成生产迁移。

### 6.4 Cast 前的具名主体边界

短中篇的 Story Map 和长篇的 Book Architecture 都位于 Cast 之前，因此：

- Provider 只能使用“主角、对手、关系承载者、证人”等功能描述，不得擅自登记具名主体；
- 用户在 Brief 中已经明确提供的名字可以作为原始创作材料出现，但在 Cast commit 前不获得稳定 subject ref；
- Cast 是正文前唯一具名主体注册表；只有 Cast commit 后的 Volumes、Section Plan、Rolling Detail、Text 和 Script 才能引用稳定 subject ref；
- 下游发现新具名主体必须生成 Character amendment/impact，不得临时补人或把自由文本名称转换成隐藏 alias。

### 6.5 跨路线改编包

三条路线都能独立创建和运行。剧本样片不是短中篇或长篇的强制前置，但可以显式导出 `AdaptationPackage`：

```text
package_id
source_run_id / source_route_revision
brief_ref
cast_ref
selected_beat_refs[]
selected_scene_refs[]
accepted_script_version_refs[]
source_signatures[]
author_note
```

短中篇或长篇向导导入它时，只把经过用户选择的内容作为带来源签名的 Source Pack 和规划提案材料；系统仍生成并确认本路线自己的 Brief、Story Map/Book Architecture、Cast 和后续 Artifact。改编包不能直接成为新路线的 committed Artifact、Canon 或正文事实，也不能让源 Run 与目标 Run 共用可变状态。

## 7. 动态变通机制

“不死板”不是放弃合同，而是把可变创作判断放在正确层级。

### 7.1 容量范围而不是机械配额

- Scale planner 返回 `min / recommended / max` 与推导原因；
- Provider 或作者在范围内提出结构数量；
- 只有用户/ReviewPolicy 接受候选后才冻结实际数量；
- 后续只允许未来单元 amendment，不静默改已接受结构；
- 字数、页数和节拍密度首先是 warning，只有明显残缺才 blocker。

### 7.2 未来窗口 amendment

当正文暴露更好的方向时，系统允许：

1. 选中受影响的未来 Story Map anchor、Part、Volume、Window 或 scene；
2. 生成 `ImpactAnalysis`，列出 preserved、stale、blocked references；
3. 用户选择 `affected_only` 或 `restart_from_stage`；
4. 创建新 Artifact version，accepted prefix 保持不可变；
5. 只重新编译受影响 Provider inputs，不清空成功单元。

### 7.3 局部回退而不是全书重跑

| 问题 | 恢复粒度 |
| --- | --- |
| Beat/anchor 文学力度不足 | warning；作者协作或显式定向换稿当前单元 |
| Scene/section Schema 错误 | 同一冻结输入一次合同纠正 |
| 某个 Detail Window 失败 | 只恢复该 Window 未完成单元 |
| 章节连续性硬冲突 | 暂停当前章；保留 accepted prefix；修订当前章或未来规划 |
| Projection/SSE 损坏 | 从权威记录重建，不调用 Provider |
| Provider 余额/鉴权 | 保留 operation 与 checkpoint，用户修复同一 binding 后显式恢复 |

### 7.4 三类“重试”必须分开

1. **传输重试**：同一输入、同一 operation identity、有界重连，不算换稿。
2. **合同纠正**：解析/Schema 错误最多一次，只返回缺失或违规字段，不带文学旧稿污染。
3. **定向换稿**：必须有明确问题、作用域和用户/ReviewPolicy 授权；次数由阶段配置，不能因模糊 LLM 评分自动触发。

达到上限后进入 `needs_action`，不自动换模型、不继续 attempt N+1、不空烧 token。

## 8. 质量门

### 8.1 确定性 blocker

允许阻断的事实包括：

- Artifact 缺失、空文本、Schema 或 code-owned metadata 违规；
- 未知/重复稳定 ref、悬空引用、顺序缺口或 Window 重叠；
- 使用未冻结人物、场景、章节、Part、Volume 或 source fact；
- accepted 版本被覆盖、stale 下游仍试图执行；
- 已知状态从 A 跳到互斥 B 且没有台面 transition/evidence；
- 导出版本、hash、封面或章节 manifest 不一致；
- Provider receipt、operation identity、checkpoint 或 writeback 幂等性失效；
- 明显截断或低于最低可用篇幅。

### 8.2 文学 warning

以下只能形成可定位 warning、作者协作上下文或盲读证据：

- 动机不够充分、因果说服力不足；
- 冲突偏弱、节拍冲击不足、高潮提前或拖延；
- 人物声音趋同、主题表达直白、AI 味或解释过多；
- 节奏、情绪、创造性、可拍性和市场吸引力；
- LLM reviewer 给出的任何低置信语义判断。

warning 必须带 `stage/unit/source refs + evidence excerpt + suggested action`，不能只返回分数，也不能改变 Canon/Wiki。

### 8.3 路线专项质量面

| 路线 | 硬门重点 | 软质量重点 |
| --- | --- | --- |
| 剧本样片 | Scene heading、人物引用、场景顺序、对白归属、可见结果、导出结构 | 可拍性、视觉行动、对白差异、节奏、样片结尾冲击 |
| 短中篇 | Story Map/Section refs、状态连续、结局存在、版本写回 | 单体完整、承诺兑现、信息密度、重复、声音和余韵 |
| 长篇 | Part/Volume/Window 连续、Promise 生命周期、状态 transition、accepted prefix | 长线推进、人物弧、支线停滞、卷闭合、局部改道后的整体方向 |

## 9. 后端目标架构

### 9.1 目录与责任

建议在现有领域边界内形成：

```text
src/novel_workflow/
  creation_routes/
    specs.py
    compiler.py
    review_policy.py
    scale_policy.py
  output_contracts/
    brief.py
    characters.py
    screenplay.py
    short_novel.py
    long_novel.py
    delivery.py
  runtime/graph/
    route_graph.py
    stage_graph.py
    unit_graph.py
    ... existing evidence/chapter/collaboration boundaries
  planning/
    aggregates.py
    amendments.py
    dependency_index.py
    impact_analysis.py
```

`src/novel_workflow/api` 继续只做 payload 校验、依赖获取、HTTP/SSE 适配和错误映射。Route 编译、质量、Context、amendment、Provider operation 与持久化规则不能进入 API route 文件。

### 9.2 `GraphRunDefinition`

```text
architecture_version: phase32-routes-v1
run_id / project_id / workflow_id / workflow_revision
creation_route_id / route_revision
compiled_stage_manifest[]
review_policy
scale_profile
inputs（含冻结 `creation_language`；当前只支持 `zh-CN`）
provider_bindings_by_stage
export_profile
created_at
```

删除 `quality_mode`。Run 中只保存冻结后的实际合同，不在运行中读取“当前模板最新版”。

### 9.3 动态 Run State 和 Read Model

`NarrativeRunState` 继续只保存路由与引用，但 `stage_status`、`artifact_refs`、`candidate_refs` 和 attempts 改为由 compiled manifest 校验的动态映射，不再是固定八阶段 TypedDict。

Read model 至少新增：

```text
creation_route_id
route_revision
stage_manifest[]
active_stage_id
active_unit_ref
review_policy_summary
stage_status{}
artifact_refs{}
pending_decisions[]
provider_usage
failure / checkpoint / updated_at
```

任何 UI 进度、导航和监控阶段都从同一个 `stage_manifest` 投影。

### 9.4 LangGraph 编译

`RouteGraphCompiler` 负责：

1. 校验 `CreationRouteSpec`；
2. 为每个 StageSpec 装配共享 stage lifecycle 子图；
3. 为 `bounded_units / sequential_units` 装配 unit 子图；
4. 按 ReviewPolicy 插入 interrupt，而不是在 node 内判断旧 `fast`；
5. 装配 Text/Script、Evidence、Cover 和 Export 专用节点；
6. 将 checkpoint、operation、failure 和 event 绑定同一 run/thread namespace。

不允许 `if route_id == ...` 大分支散落在 route、Store 和 UI。差异必须集中在 Spec、Artifact parser、Context policy 和 workbench registry。

### 9.5 Provider 与 Context

- 每个 stage/unit 使用不可变 `ProviderInputReceipt`；
- Prompt schema 只暴露模型拥有的文学字段，ID/顺序/hash/status 由代码绑定；
- Screenplay 只读取相关 Beat、Scene、人物邻域和上一 scene handoff；
- 短中篇 Text 只读取当前 Section、相关人物、Story Map anchors 和上一 handoff；
- 长篇 Text 只读取 Book/Part/Volume 当前合同、Detail chapter、Resolved State、相关人物和上一 handoff；
- Source Pack 只在用户选择且 route policy 允许时注入，正文不盲检索；
- Context 大小必须与当前 unit 相关，不随全书长度线性增长。
- 每次 Provider 调用前创建独立 Phase 32 operation receipt；receipt 绑定冻结 request signature、stage、raw return、usage、diagnostic 和恢复结果。
- receipt 状态严格区分 `pending`、`returned`、`succeeded`、`contract_rejected`：传输失败只保留 pending；合同失败不得伪装成传输重试；成功 operation 重启后从 receipt 恢复 candidate，不重复调用 Provider。
- Provider receipt 是 sidecar，不拥有 Artifact 的 ID、顺序、hash、状态或写回权威；同一 operation key 复用不同 request signature 必须拒绝。

## 10. 前端统一信息架构

### 10.1 Version 20 视觉边界

- 保持中性暗黑石墨基底，提升正文与小字对比度；
- 三条路线只使用局部 aura、图标、光标和重点状态差异，不整页换色；
- Screenplay 使用冷青 + 少量琥珀时间标记，短中篇使用薄荷 + 暖白纸面提示，长篇使用克制紫 + 冷蓝层级提示；
- Success/Warning/Danger 保持固定语义色，不被路线色覆盖；
- 不堆卡片、不做卡片套卡片；结构工作台优先使用轨道、列表、分栏和连续表面；
- 所有 route/tab/内容显隐使用 160-240ms opacity + 2-6px 位移；
- 新事件只局部淡入，不整页频闪；Reduced Motion 下取消位移、脉冲和 3D 自动运动。

### 10.2 统一 Shell

| 区域 | 合同 |
| --- | --- |
| Project 主侧栏 | 当前作品、冻结路线、动态阶段、Story Bible、监控、知识库、设置 |
| Header | 从 route manifest 渲染短心电图进度；最大宽度 640-720px；阶段事件到达时只律动一次 |
| 阶段二级侧栏 | 全阶段统一 `184px` 桌面宽度；内容项按真实内容高度排列，不拉伸铺满 |
| 主工作区 | `minmax(0, 1fr)`，占满剩余视口，不用固定 max-width 制造大留白 |
| 右侧 Inspector | 320-360px，可收起；只显示来源、影响、质量、回执或阶段专属检查 |
| 作者协作台 | 右侧互斥抽屉；打开时收起产品主侧栏，但保留阶段二级侧栏 |
| 监控模式 | 隐藏 Project 主侧栏，使用 route-aware rail + 主内容 + 健康/日志 Inspector |

二级侧栏宽度以一个 design token 管理，Spine/Story Map、Cast、Volumes、Detail、Text、Script 不得各自定义宽度。

### 10.3 工作流模板与新建向导

工作流列表以连续流水线展示三个真实 RouteSpec，不使用八宫格。

详情页保留用户已认可的倾斜阶段牌组：点击哪张牌就选中哪一阶段并切换右侧配置；牌组数量和连接关系来自 route manifest，不再假定八张。Stage 配置包括：Provider、模型、Prompt 版本、ReviewPolicy、换稿上限、Context policy 与预算。

新建作品统一进入两步主流程，顺序固定为“先理解需求，再匹配流水线”：

1. **创作意图**：先选择“剧本”或“小说”，填写自由创作想法；选择小说后再出现“短中篇 / 长篇”，并按路线显示分钟或字符软目标。剧本不显示小说长度选项，小说不显示剧本时长选项。
2. **流水线匹配**：系统根据第一步推断的路线过滤已有官方/自定义流水线，默认推荐匹配的官方模板；用户可选择现有流水线，或点击“新建流水线”，由系统预填该路线的配置入口和默认合同。第二步不能把路线改成另一类作品。

所有“新建小说 / 新建项目 / 新建作品”入口统一进入这一个向导。路线在第二步确认并创建 Run 后冻结，不在侧栏、Header 或运行中切换；需要换路线时回到第一步或创建新的 Run。

向导 UI 约束：第一步使用清晰的交付物分段控件和条件式小说长度选择，不把三条路线和八个阶段同时铺成网格；第二步使用连续流水线预览和可选模板列表，选中哪条流水线就显式高亮其阶段牌组与摘要；“新建”沿用当前路线，不再弹出一个脱离上下文的空白配置弹窗。下一步、返回、取消、加载、无匹配和错误状态都必须有真实 action 与过渡动画，不能靠 mock/timer 派生状态。

## 11. 三条路线的阶段工作台

### 11.1 剧本样片 UI

| 阶段 | 二级侧栏 | 主区 | Inspector/关键交互 |
| --- | --- | --- | --- |
| Brief | 目标/格式导航 | 样片定位与承诺表单 | 时长包络、来源和准备度 |
| Cast | 人物名册 | 当前人物档案与关系邻域 | 屏幕职责、对白声纹、出场覆盖 |
| Beat Board | 纵向节拍索引 | 可拖动决策节拍轨道，不做通用卡片墙 | 时间密度、setup/payoff、警告 |
| Scene Deck | 场景列表 | Master scene cards 连续编排，支持拆分/合并未来 scene | 页数预算、人物、地点、结果 |
| Script | Scene 导航 | 规范剧本编辑器：scene heading/action/dialogue/parenthetical | 版本、格式检查、作者协作、局部 diff |
| Export | 版本清单 | Fountain/PDF/Markdown 交付表面 | hash、页数、版本注记 |

剧本编辑器需要成熟的块类型与键盘行为。实现阶段先评估基于 ProseMirror/Tiptap 的 route-local editor；只有 spike 证明 selection anchor、版本 diff、导出和无障碍都满足现有合同后才引入，不用 textarea 假装专业剧本编辑器。

### 11.2 短中篇小说 UI

| 阶段 | 二级侧栏 | 主区 | Inspector/关键交互 |
| --- | --- | --- | --- |
| Brief | 立项段落导航 | 紧凑结构化编辑 | 篇幅包络、Source Pack、承诺覆盖 |
| Story Map | anchor 列表与 Promise 过滤 | 连续故事地图：开场压力、选择、后果、收束 | 未兑现承诺、重复推进、文学 warning |
| Cast | 人物名册 | 档案 + 关系 3D/2D 只读投影 | 当前故事职责和出场覆盖 |
| Section Plan | 章节/段落列表 | 戏剧任务、场景与 handoff 编辑 | 预算、POV、人物/anchor refs |
| Text | 章节导航 | 稿纸式正文与版本编辑 | Review、Evidence、Context、协作 diff |
| Cover | 资产轨道 | Visual Brief 与候选 | 真实图片状态和导出绑定 |
| Export | Manifest | 版本、封面、格式和元数据 | 完整性与 hash 回执 |

Story Map 的可视化只用于选择和理解，不把节点坐标写回 Artifact。关系图保持 3D 增强与 2D/列表降级，不能因图谱不可用阻断人物编辑。

### 11.3 长篇小说 UI

| 阶段 | 二级侧栏 | 主区 | Inspector/关键交互 |
| --- | --- | --- | --- |
| Brief | 立项区块 | 长期承诺、规则、终局与规模 | Research/Source、锁定和影响 |
| Book Architecture | Book/Part 树 | 当前 Part 合同、Promise 生命周期和转折编辑 | entry/exit state、影响和覆盖 |
| Cast | 核心/本 Part/本卷/归档筛选 | 当前人物档案、关系和 scope | dependency、首次/最后出场、归档影响 |
| Volumes | Part -> Volume 导航 | 均衡分卷轨道和当前卷合同 | Promise、人物、结构引用和容量 |
| Rolling Detail | Volume -> Window -> Chapter | 当前 Window 章节施工表 | handoff、状态、场景、stale 单元 |
| Text | Part/Volume/Chapter 树 | 正文与版本 | Context、Evidence、Review、协作、未来 amendment |
| Cover | 资产轨道 | Visual Brief 与候选 | 全书主题与正式资产 |
| Export | Part/Volume/Chapter manifest | 流式交付与版本选择 | hash、缺失版本、封面和元数据 |

长篇工作台只挂载当前聚合根、当前单元和邻接单元。400-500 章、120+ 人物时必须使用分页/虚拟列表，不能一次挂载整本表单或正文。

## 12. 作者协作台迁移

Phase 31 的线程、Context receipt、SelectionAnchor、Patch Candidate、同一 LangGraph/checkpointer 和“不可直接写 Canon/Wiki”边界全部保留。作者协作不再绑定旧的 `deep-only` 模式，而是由 RouteStageSpec 声明能力；三条路线都开放多轮讨论、方案和定向改稿，封面/导出等非文本交付阶段保持关闭：

| 路线 | P0 接入阶段 |
| --- | --- |
| 剧本样片 | Beat Board、Scene Deck、Script |
| 短中篇 | Story Map、Cast、Section Plan、Text |
| 长篇 | Book Architecture、Cast、Volumes、Rolling Detail、Text |

旧 `fast / balanced / deep` Run 也共享同一多轮协作合同；模式只影响原有运行审阅与自动继续策略，不再决定作者协作是否可用。协作模型、Context receipt、选区锚点和 patch writeback 仍按 Run/Stage 冻结，不能因为放开入口而绕过 Artifact amendment、分支、Canon/Wiki 或 source binding 权限。

讨论、方案、改稿三种模式不变。改稿仍只生成 source-bound patch candidate；结构新增、删除、重排和 accepted 历史修改必须走对应 amendment/branch，不允许聊天框直接覆盖 Artifact。

首次发送显示完整 Context 回执，第二次轻提示；Artifact/source/context policy 变化后重新确认。线程绑定 `route + stage + artifact version + unit`，旧线程可读但必须 fork/rebase 后才能继续。

## 13. 运行监控

监控使用同一三栏框架，但内容按 route/stage 适配：

| 路线/阶段 | 左 rail | 中央内容 | 右 Inspector |
| --- | --- | --- | --- |
| 剧本 Brief/Beat | 阶段/beat | 当前 Artifact、正在生成的 beat | 健康、决策、Provider、日志 |
| 剧本 Scene/Script | scene 树 | 当前 scene 卡或剧本文本 | 格式检查、usage、checkpoint、日志 |
| 短中篇规划 | anchor/section | Story Map 或计划投影 | warning、决策、回执、日志 |
| 短中篇正文 | chapter/section | 当前正文与实时版本状态 | Review、Evidence、writeback、日志 |
| 长篇规划 | Part/Volume/Window | 当前聚合单元与覆盖 | stale/impact、checkpoint、日志 |
| 长篇正文 | Part/Volume/Chapter | 当前章与连续性状态 | Review、Evidence、Canon/Outbox、日志 |

历史事件 replay 完成后一次呈现，不逐条闪烁。SSE 新事件按短窗口批量投影，只让新增日志/状态局部淡入。日志始终存在且可收起；中央区域填满可用视口，不因正文舒适行长而让整个 panel 变窄。

Phase 32 的 SSE 适配器只包装上述 route-aware event projection，使用 sequence cursor 重连并在终止事件后关闭流；它保持 dormant，直到与新 API 同波替换旧事件 reader。

## 14. API、事件和前端合同

### 14.1 API 方向

```text
GET  /api/creation-routes
GET  /api/creation-routes/{route_id}
GET  /api/workflows
GET  /api/workflows/{workflow_id}
POST /api/projects
POST /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/route-manifest
GET  /api/runs/{run_id}/stages/{stage_id}/artifacts/current
GET  /api/runs/{run_id}/stages/{stage_id}/units
POST /api/runs/{run_id}/decisions
POST /api/runs/{run_id}/planning/{stage_id}/amendments
GET  /api/runs/{run_id}/planning/amendments/{amendment_id}/impact
POST /api/runs/{run_id}/planning/amendments/{amendment_id}/apply
GET  /api/runs/{run_id}/planning/amendments/{amendment_id}/branch
POST /api/runs/{run_id}/planning/amendments/{amendment_id}/branch
GET  /api/runs/{run_id}/events?after={sequence}
```

实际 route 文件只调用 domain service。Stage API 不接受客户端自报 Artifact type、code-owned ID、Canon 文本或 route graph。

### 14.2 事件最小字段

现有事件字段继续保留，并增加：

```text
creation_route_id
stage_id
unit_ref?
artifact_kind?
route_revision
```

事件 type 仍使用领域动作，例如 `stage.started / candidate.created / decision.required / artifact.committed / unit.failed / evidence.completed / run.branched / export.ready`，不为三条路线复制三套事件名。`run.branched` 同时写入 source 与 successor Run，记录不可变 lineage provenance；没有真实 checkpoint 写入时不得借用 `checkpoint.saved`。

### 14.3 前端合同

删除固定 `StageType` 与 `QualityMode`。前端使用服务端返回的：

```text
CreationRouteManifest
RouteStageManifest
ArtifactEnvelope
WorkbenchKind
StageCapability[]
```

`workbench_kind` 只决定选择哪个已注册生产工作台，不能让服务端传组件名、CSS 或任意 schema renderer。每种 Artifact 仍有显式 TypeScript parser 和专用 UI。

## 15. 历史数据、迁移与删除矩阵

### 15.1 历史 Run

- 所有 `phase27-vnext` Run 保持不可变，只能在 archive viewer 中查看、导出和比较；
- 不允许恢复、重新决策、amendment 或继续调用 Provider；
- 用户可以显式“从历史作品创建新路线”，系统将选定 Brief/正文/知识材料导出为带来源的 Import Package，再创建全新 Phase 32 Run；
- Import Package 是新 Run 的 Source，不是旧 Artifact 转换器或兼容 runtime。

### 15.2 同 Wave 必须删除的旧生产路径

| 新路径建立时 | 同时删除/退休 | 静态退出门 |
| --- | --- | --- |
| `CreationRouteSpec` 编译 | `QualityMode fast/balanced/deep`、固定 `STAGE_ORDER/PHASE27_EDGES` 执行合同 | 生产源码无旧三档分支和固定八阶段校验 |
| Route-aware RunDefinition | `quality_mode` Run 字段和 Fast 自动接受 | API/TS/Python 新 Run 合同拒绝旧字段 |
| Story Map/Book Architecture | `StorySpineArtifact`、`spine_preflight`、旧 prompt-spine 生产绑定 | 新 Run 无 `spine cause/change` 权威 |
| Screenplay/Section/Rolling Detail | monolithic Detail 作为所有作品唯一计划 | Context/Provider/UI 不再读取 flat Detail 生产路径 |
| 三路线官方模板 | `official-deepseek-fast/balanced/deep` | Workflow list 只暴露三条新官方路线及用户模板 |
| 动态前端 manifest | 固定八阶段 route/header/nav 常量 | 静态搜索与组件测试证明无独立阶段数组 |
| Route review policy | 模糊 LLM 评分触发的自动换稿 | 所有 creative retry 都有 direction、scope、limit 和 receipt |

历史文档和 archive viewer 可以出现旧术语，但不能作为构建输入、运行 selector 或新建入口。

### 15.3 当前未完成能力的吸收矩阵

当前工作树包含 Phase 28/29 的大量未提交可靠性修复，实施时必须逐项吸收，不能用 Phase 32 名义覆盖或回退：

| 现有能力 | Phase 32 处理 | 不能误判为 |
| --- | --- | --- |
| Phase 28 Evidence、Resolved State、Context 污染隔离、定向局部恢复 | 保留并适配新的 unit/artifact refs | 已通过三路线真实 Provider 验收 |
| Phase 29.1 Planning aggregate candidate/acceptance 与稳定 ref 候选 | 作为 Book/Part/Volume/Window 及其它 bounded planning unit 的持久化基础 | flat 生产图已经完成迁移 |
| Phase 29 amendment/dependency/impact 设计 | 并入 Wave 32.3，扩展到 Story Map、Beat/Scene、Part/Volume/Window | 允许直接覆盖 committed Artifact |
| Phase 30 Version 20 唯一前端与生产 API/SSE 适配 | 保留视觉、Shell、IO 和状态管理基线，动态化 route/stage | 继续在旧前端或另建第三套前端 |
| Phase 31 作者协作线程、Context receipt、SelectionAnchor、Patch Candidate | 保留同一 runtime 与权限边界，改由 stage capability 启用 | 聊天内容拥有 Artifact/Canon 写权限 |

Wave 32.0 必须输出逐文件表：`keep as-is / adapt / supersede after replacement / archive-only`。在对应新路径通过退出门前，不删除仍承载唯一正确行为的现有实现；新路径切换时又必须同时删除旧生产入口，不能留下长期双路由。

## 16. 实施 Waves

每个 Wave 必须同时证明新路径、删除对应旧路径、通过正反合同测试后再继续。不能先保留双生产路径“以后再清理”。

### Wave 32.0：评审与工作区保护

工作：

- 用户批准三路线、篇幅政策、因果规划替代、默认 ReviewPolicy 和历史归档边界；
- 更新 `stage-artifact-contract.md` 为 Phase 32 唯一合同；
- 逐文件盘点当前 Phase 28/29 未提交改动，标记保留、吸收、重写和过期；
- 冻结现有历史 Run 为只读证据，不启动服务或 Provider。

退出门：合同无未决高影响问题；工作树无用户改动被覆盖；明确每个当前 dirty 文件的归属。

2026-08-22 执行证据：

- `stage-artifact-contract.md` 已切换为 Phase 32 三路线 canonical，旧固定八阶段只作为待删除现状和历史边界出现；
- `docs/engineering/phase-32-wave-0-dirty-worktree-inventory.md` 已逐项覆盖 Phase 32 开始前的 `45` 个 tracked dirty 文件及 `5` 个 untracked backend 文件；
- Phase 32 开始前全量后端基线为 `777 passed, 1 warning`，唯一 warning 为既有 Starlette/httpx 弃用提示；
- production closure audit 未发现第二 runtime、legacy/shadow/dual runtime marker 或异常 frontend pipeline 顶层目录；
- 三份 Wave 32.0 文档代码围栏成对，目标文档 `git diff --check` 通过；没有启动服务、恢复历史 Run 或调用真实 Provider。

Wave 32.0 退出门已关闭。Wave 32.1 首个切片只建立可独立测试的 Route Kernel；在能够于同一 Wave 删除旧 `QualityMode`、固定 executable contract 和 Fast 自动接受前，不把新 Kernel 接入生产 Run，也不把 dormant contract 称为生产迁移完成。

### Wave 32.1：Route Kernel 与新 Run 合同

工作：

- 新增 `CreationRouteSpec / RouteStageSpec / ReviewPolicy / RouteGraphCompiler`；
- 建立三条官方路线定义与 route manifest；
- RunDefinition、state、read model、event 增加 route identity 和动态 stage mapping；
- 同时删除旧 QualityMode、固定 executable contract 和 Fast 自动接受。

测试：三图拓扑、非法依赖、重复 stage、错误 Artifact/Prompt、冻结 digest、重复创建、旧字段拒绝、动态投影。

退出门：fake runtime 能分别创建三种全新 Run，checkpoint/read model 中只存在一条实际 compiled graph。

2026-08-22 首个 Route Kernel 切片：

- 新增 `workflows/route_specs.py`、`review_policy.py` 与 `route_compiler.py`，建立三条官方路线、三份默认 ReviewPolicy、统一 compiled manifest 和稳定 route digest；
- 编译器已拒绝重复 stage/dependency、未知上游、多起点、非唯一 Export 终点、环、错误 Artifact/workbench/Provider task/unitization 组合、未知或跨路线 ReviewPolicy、无 Provider 节点的定向换稿；
- 三条 manifest digest 分别为：剧本样片 `9f3514b0daeffefbed02aca301a9c12cd1b478b898bc9f3cfca3a0ca0982ec8c`、短中篇 `368b6a43bf8952f644d9b2891a82f89ea59b7f7a1babb87d286bbbdfef535998`、长篇 `553e4f8e5fc813654ebf06f6612d37736d8dee66ea62adde6a7bcfa50ed8a29d`；
- 新增 `tests/test_creation_routes.py`：`25 passed`；与既有 Workflow template、Project API、Phase 26 边界的兼容回归为 `68 passed, 1 warning`；当前全量后端为 `802 passed, 1 warning`；`compileall`、全工作树 `git diff --check` 和 production closure audit 通过；
- 本切片没有接入生产 Run，没有改动 API、Store、SSE、LangGraph 或前端，也没有启动服务、恢复历史 Run 或调用真实 Provider。

Wave 32.1 尚未关闭。下一切片必须把 route identity 和 compiled manifest 迁入 RunDefinition/state/read model/event，并在同一 Wave 删除旧 `QualityMode`、固定 `STAGE_ORDER/PHASE27_EDGES` executable contract 与 Fast 自动接受；只有三条 Fake Run 共用同一实际 graph/checkpointer 后才满足退出门。

2026-08-22 冻结路线权威切片：

- 生产追踪确认旧 `quality_mode` 在 API/orchestration/storage/runtime 仍有 `28` 个读取或分支点，固定 `STAGE_ORDER/PHASE27_EDGES` 及其 executable contract 在生产源码仍有 `47` 个引用；因此拒绝仅在 API/RunDefinition 外层追加 `route_id` 的假迁移；
- 新增 `workflows/frozen_route_contract.py`，把 compiled route manifest、用户最终 ReviewPolicy、route identity 与 manifest/policy/整体三层 digest 冻结为未来 Run 唯一可嵌入的 route authority；
- 合同允许同一路线的作者自定义 ReviewPolicy，但拒绝跨路线 policy、route 外阶段引用、确定性 Export 自动生成或定向换稿、旧 `quality_mode` 字段，以及 route identity、manifest、policy 或整体合同的落盘篡改；
- Route Kernel + 冻结合同定向测试为 `43 passed`；与既有 Run repository/API/event/workflow 边界兼容回归为 `112 passed, 1 warning`；当前全量后端为 `820 passed, 1 warning`；`compileall`、全工作树 `git diff --check` 和 production closure audit 通过；
- `FrozenRouteContract` 当前没有 production importer，不构成第二 runtime。旧 RunDefinition/state/event 尚未修改，Wave 32.1 仍未关闭，也不据此宣称三路线可创建或执行。

下一切片以 `FrozenRouteContract` 为切换锚点，先形成 RunDefinition、动态 read model/state/event、Preflight 与 Branch 的 keep/delete 调用矩阵，再在可同步删除旧模式和固定阶段读者的边界上进行生产切换；Provider 及尚未完成的 Artifact 合同不得用旧字段推导或默认补齐。

2026-08-22 Run authority cutover 设计切片：

- 新增 `docs/engineering/phase-32-wave-1-run-authority-cutover.md`，逐文件记录 repository、state、event、graph、decision、API、preflight、branch、history、旧 executable contract 与 Artifact stage order 的当前 writer/readers、Phase 32 replacement、同波删除项和正反测试；矩阵冻结为五个单向批次，不允许 production importer 先于旧 reader 删除；
- 新增 `workflows/graph_run_definition.py`，以 `FrozenRouteContract` 作为路线与 ReviewPolicy 唯一权威，冻结 Run/project/workflow identity、内容寻址的 inputs/scale/provider snapshots、route 支持的 export profile 和整体 definition digest；typed `ScaleProfile` 已能校验路线/策略版本/包络，Provider 语义仍留给 Wave 32.3，不读取或推导旧 mode 默认值；
- Provider binding 必须按 compiled manifest 顺序精确覆盖全部 Provider stages，不能缺失、多余、乱序或给 deterministic Export 绑定 Provider；三路线都可从自身 manifest 动态生成首阶段 `available`、其余阶段 `locked` 的初始投影；
- 新增 `tests/test_graph_run_definition.py`，与 Route Kernel/冻结合同合计 `53 passed`；Run repository、Workflow/API、projection 与 Phase 26 边界兼容回归为 `116 passed, 1 warning`；当前全量后端为 `830 passed, 1 warning`；`compileall`、全工作树 `git diff --check`、frontend structure audit 与 production closure audit 通过；
- 本切片仍没有 production importer，没有改写旧 Run 数据，没有启动服务、恢复历史 Run 或调用真实 Provider。审计仍能定位旧 mode/固定 stage readers，因此 Wave 32.1 未关闭。

下一切片建立动态 Run read model/state/event 的纯合同与 manifest 校验器，并用 repository persistence fixture 证明 route identity 和 stage mapping 可重建；只有能够与 archive-only reader、Preflight/Branch/Graph/API 的同波删除计划一起落地时，才把 `GraphRunDefinition` 接入生产 repository。

2026-08-22 动态 state/read model/event 合同切片：

- 新增 `runtime/graph/route_run_state.py`，建立只包含 route identity、stage/unit cursor、Artifact/operation refs、attempts、failure 和 domain revision 的 checkpoint snapshot；所有 stage mapping 必须由冻结 manifest 校验，删除目标中的 `quality_mode`、固定 `StageId` 和 chapter-only cursor 均未进入新合同；
- 新增 `storage/route_run_read_model.py`，把 compiled stage manifest、ReviewPolicy summary、动态 stage status、typed Artifact refs、pending decisions、Provider usage、failure 和 checkpoint 投影为同一 UI/API read model；Artifact kind、unit scope、decision/failure stage 和 manifest 都必须与原 `GraphRunDefinition` 一致；
- 新增 `storage/route_run_event.py`，固定 Phase 32 领域事件集合，事件携带 route revision、manifest/definition digest 及可选 unit/Artifact identity；未知 stage、错误 Artifact kind、aggregate stage 上的 unit ref、错误 Export stage 和旧字段全部拒绝；
- 新增 `tests/test_route_run_projection_contracts.py`，三条路线均完成 definition/state/read model/event 的原子 JSON/JSONL 落盘与恢复，并覆盖 route/manifest/policy 漂移、动态 stage 缺失或越界、错误 Artifact/decision/failure/unit 归属、空/重复引用和旧 `quality_mode/chapter` 字段；
- Phase 32 定向合同集为 `66 passed`；Run repository、Workflow/API、projection 与 Phase 26 边界兼容回归为 `129 passed, 1 warning`；全量后端为 `843 passed, 1 warning`；`compileall`、全工作树 `git diff --check`、frontend structure audit 与 production closure audit 通过；
- Definition contracts 批次已完成，但这些模型仍无 production importer；旧 repository/state/event/runtime 没有改读，没有启动服务、恢复历史 Run 或调用真实 Provider，因此 Wave 32.1 仍未关闭。

2026-08-23 archive-only reader 切片：

- 新增 `archive/phase27_archive_reader.py`，严格读取分离的 Phase 27 `definition.json/read_model.json/events.jsonl`，投影为类型化 summary/detail/event page；不返回 `raw` JSON，不导入旧 RunDefinition、runtime、Provider 或 writer；
- archive API 仍是 `/api/archive/runs`，新增 `cursor/after` 分页与事件只读投影；所有执行、恢复、决策、分支、amend、写回和 Provider 能力恒为 `false`，旧 `run.json` 合同返回 404；
- 测试覆盖 completed/failed/awaiting_decision、损坏/未知 architecture 拒绝、事件连续性、API 只读、文件 hash/mtime 不变；真实目录离线扫描 `151` 个 Run、`25,501` 条事件通过；
- 本切片没有移动、恢复或改写 `runtime/novel_workflow/native_runtime`，没有启用 Phase 32 production importer，因此 Wave 32.1 仍未关闭。

2026-08-23 dormant persistence contract 切片：

- 新增 `storage/phase32_run_repository.py`，只接受 `phase32-routes-v1`，持久化 definition/state/read_model 与分离的 route-aware events；创建、projection commit、事件 append 都在写入前校验 route identity、manifest、digest、status、sequence 和幂等性；
- `phase27-vnext` 输入明确拒绝为 `phase27_run_requires_archive_reader`，不允许通过新 repository 进入执行；损坏 projection、事件缺口、重复事件 ID 和跨 Run 事件均拒绝；
- `tests/test_phase32_run_repository.py` 与已有 projection 合同合计 `20 passed`；projection commit 先写 `projection.journal.json`，读/恢复时可重放成对 state/read model，覆盖首个文件替换后进程退出和 definition digest 漂移拒绝；该 repository 仍未接入旧 `filesystem_stores`、Graph、Preflight、Branch、API 或恢复入口，因此没有形成 dual runtime，Wave 32.1 仍未关闭。

2026-08-23 dormant Preflight/Branch contract 切片：

- 新增 `orchestration/phase32_run_preflight.py`，验证冻结 definition/state/read model 的 route identity、manifest、Provider stage 顺序、active stage 和 status 一致性；不读取 Provider、不调用模型、不从旧 `quality_mode` 推导任何值；
- 新增 `orchestration/phase32_branch_contract.py`，只构建 source-bound branch plan，要求 source digest、route revision 和 frontier 合同一致；分支不能切换路线，binding override 只能指向 frontier 之后的 Provider stage，不能触碰 deterministic Export；
- `tests/test_phase32_preflight_branch_contract.py` 定向 `8 passed`；两个模块仍未接入旧 runs API、BranchService、NarrativeRuntime 或恢复入口，因此没有形成 dual runtime，Wave 32.1 仍未关闭。

> Wave 46 后续处置：上述未接生产的通用 branch contract 允许客户端 target id、旧 checkpoint frontier 和 binding override，与 amendment successor Run 的唯一生产合同冲突，现已连同专属 fixture 删除；Preflight 与共享 route Graph 保留。正式分支见 `docs/engineering/phase-32-wave-46-amendment-branch-recovery.md`。

2026-08-23 dormant Graph fixture 切片：

- 新增 `runtime/graph/route_graph.py`，同一个 builder 接收 `GraphRunDefinition`，从冻结 manifest 动态生成 stage lifecycle 子图和父图边；三条官方路线共用该 builder，不读取固定 stage 数组、`quality_mode` 或旧 `PHASE27_EDGES`。
- Provider generation 只绑定 manifest 中声明了 `provider_task_kind` 的阶段；`export` 只走 deterministic `commit_stage` 并发出 `export.ready`。ReviewPolicy 的 mandatory/auto-continue、domain revision 和有界 directed redraft 都在 graph fixture 中有正向/拒绝测试。
- 新增 `tests/test_phase32_route_graph.py`，定向 `10 passed`，覆盖三路线拓扑、同一 builder/checkpointer 完整 fake lifecycle、Export 零 generation、跨 definition state 拒绝、定向换稿上限与旧字段静态审计。
- 新增 dormant `storage/phase32_history_projection.py`，只从 Phase 32 definition/read model 投影动态路线、manifest 进度、active unit、pending decision、checkpoint 和 Export 状态；它尚未替换旧 `RunHistoryProjection`，避免形成双读路径。
- 新增 dormant `storage/phase32_event_projection.py`，按 route identity 和连续 sequence 分页读取 `RouteRunEventEnvelope`，统一计算 decision/failed/Export terminal 状态；旧 HTTP/SSE 入口未改读。
- 新增 dormant `api/phase32_sse.py`，只将上述 projection 输出为游标化 SSE 帧；它不导入旧 `api.sse`/`EventProjection`，并在终止事件后关闭流。该适配器只有在同波 API cutover 时才可挂载。
- `tests/test_phase32_event_projection.py` 定向 `3 passed`，覆盖分页重连、终止事件游标越过后的 terminal 恢复和旧事件 reader 静态拒绝。
- 该 builder 仍未接入 `filesystem_stores`、旧 `NarrativeRuntime`、API 或恢复服务；Graph 生产切换必须和 repository、projection、Preflight、Branch、API 在同一批次删除旧 reader 后进行，Wave 32.1 仍未关闭。

下一切片先同步切换 repository、event/history projection 的生产根与拒绝合同；如果仍有 production runtime reader 需要旧 RunDefinition，则不把 creation-prepare 结果接入 Phase 32 Create/Start 入口。

### Wave 32.2：Artifact 与 Scale 合同

工作：

- 把 `artifacts_vnext.py` 按职责拆分；
- 首个 dormant slice 已建立 `output_contracts/phase32_artifact_base.py`、`phase32_route_artifacts.py` 与 `phase32_delivery_artifacts.py`，按职责覆盖三路线规划、正文、封面和交付 Artifact 的最小核心字段、稳定引用、顺序/覆盖校验与路线绑定；旧 `artifacts_vnext.py` 尚未切换。
- 同一 slice 新增 `workflows/phase32_scale.py`，冻结三路线的单位、P0 包络、推荐带、推导原因和长篇 12-40 章/1-3 卷滚动 Window 容量；`freeze_phase32_scale_profile()` 已将它写入 Run 定义的内容寻址 scale snapshot，但 Create API 仍未切换。
- 新增 dormant `orchestration/phase32_run_fixture.py`，无 Provider 创建三路线 Definition，原子提交 `brief=running` State/ReadModel 并追加首个 `stage.started`；新 Repository 实例可恢复同一 identity、projection 和事件。
- 三路线 fixture 已通过 Preflight、stage-boundary Branch 和共享 route Graph 的联合门，首个 Brief mandatory decision 可中断且没有触发 Export/Provider；该门仍为离线 fixture，不代表 API/生产切换。
- 新增 dormant `storage/phase32_graph_event_sink.py` 后，fixture 可把 Graph 事件顺序写入 Repository，并用 EventProjection 验证 decision required/resolved、Export terminal 和 cursor 越过终止事件后的稳定终态；旧 SSE/API 仍未改读。
- 新增独立 `POST /api/creation-wizard/prepare` 预备边界：它只将 `CreationIntent + WorkflowSelection` 冻结为原生 `GraphRunDefinition`，并用 reservation/prepared sidecar 处理幂等、冲突和进程中断恢复；旧 `/api/projects`、`/api/runs` 不读取或写入该根。
- 建立 BeatBoard/SceneDeck/Screenplay、StoryMap/SectionPlan、BookArchitecture/Volume/RollingDetail 合同；
- 保留并适配 Character、Chapter、Cover、Delivery、Evidence 边界；
- Scale planner 改为容量包络 + 接受后冻结；
- 同时删除 flat Spine 与所有作品共用 monolithic Detail 的新 Run 权威。

测试：Pydantic `extra=forbid`、稳定 ref、范围边界、Promise lifecycle、Part/Volume/Window 连续、场景/章节引用、篇幅软门和明显截断硬门。

退出门：三路线可在无 Provider 情况下由 fixture/作者输入完成所有规划 Artifact commit。

### Wave 32.3：Provider、Context 与 Graph 子图

工作：

- 为各 stage/unit 建立窄 Provider task 和 Prompt；
- Context compiler 按 route/stage/unit 读取最小相关材料；
- 装配 stage/unit/text/script/evidence/export 子图；
- 实现传输重试、一次合同纠正、显式定向换稿三类独立账本；
- 接入 amendment/dependency/impact 与 stale gate。

测试：Prompt 镜像一致性、禁止字段、Context 上限、同 operation 重连、合同纠正上限、needs_action、重复 resume、accepted prefix 不变、局部重算准确。

退出门：Fake Provider 完成三路线端到端，任一失败只影响当前 unit，operation/Artifact/Evidence 均幂等。

### Wave 32.4：Store、API、SSE 与恢复

工作：

- Planning aggregate/unit、amendment、dependency、route projection 的持久化；
- 动态 stage/unit API 与 read model；
- SSE cursor、batch projection、projection rebuild；
- 历史 Run archive viewer 与 Import Package；
- API route 保持薄适配。

测试：进程重启、SQLite checkpoint、并发 decision、重复 idempotency key、SSE 断线/续传、projection 删除重建、历史 Run 写请求拒绝。

退出门：三种 Run 在重启、断线、重复提交后不重复 Provider 调用、commit、Outbox 或 Export。

2026-08-23 Run/SSE 正式权威切片：

- `GET /api/runs`、`GET /api/runs/{id}`、`GET /api/runs/{id}/events`、
  `POST /api/runs/{id}/start` 与 `POST /api/runs/{id}/decisions` 已统一读取或驱动 Phase 32
  Repository、History/Event Projection 与 Execution Service；
- Phase 32 SSE 已合并进唯一 `api/sse.py`，按 sequence cursor 恢复并在 terminal projection
  后关闭；旧 `/api/phase32/runs/**`、`POST /api/runs` 和 `/resume` 均以 `410` 明确拒绝；
- 删除旧 Run history adapter、旧 legacy archive viewer 和独立 Phase 32 route/SSE adapter，历史
  Phase 27 Run 只保留隔离只读 archive；
- 后端全量 `1018 passed, 1 warning`，Run/SSE 目标集 `34 passed, 1 warning`，`compileall`
  通过；本轮未调用 Provider；
- 本切片关闭正式 Run/SSE/执行适配边界，但 Wave 32.4 总退出门尚未完全关闭：Artifact payload、
  Planning/unit write API、author collaboration、Story Bible、Cover assets 与 Import Package 仍待迁移。

### Wave 32.5：统一 Shell、模板与向导

工作：

- Workflow 列表改为三条真实流水线；
- 倾斜阶段牌组读取动态 manifest，修复点击选中和键盘操作；
- 两步新建向导接入 route/length/review/provider 真实合同；
- Project Shell、Header 心电图、Command Palette 和导航动态化；
- 删除固定八阶段前端常量与旧模式主题。

测试：点击/键盘选择任意阶段，所有按钮有真实 action；加载只有一个全局层；路线锁定；移动端菜单只在移动端显示；Reduced Motion。

退出门：从 Studio 选择任一路线可创建真实项目/Run，并进入正确首阶段；无 mock/timer 派生状态。

2026-08-23 Project 创建权威与前端进入链路切片：

- `POST /api/projects` 已成为 Phase 32 Project/Run 唯一创建入口；旧
  `/api/creation-wizard/prepare` 与 `POST /api/runs` 分别以 `410` 明确拒绝；
- Version 20 新建向导、作品库、Project Shell、Header 和侧栏均消费 Project 返回的动态
  route manifest；创建后进入 `/run/brief`，刷新恢复同一 Project，锁定阶段不可进入；
- 首次浏览器验收发现前端把短中篇 Story Map/Cast 顺序画反，并用旧八阶段 Workflow nodes
  冒充 Phase 32 路线；现已在路线投影边界修复，三条路线使用与后端 manifest 一致的
  6/7/8 阶段名称和顺序，旧极速/均衡/精细不再作为创建页产品模式；
- `1440x920`、`1024x700`、`390x844` 浏览器门通过；书架拖拽真实写入
  `PUT /api/projects/order`，旧 `/monitor` 对 Phase 32 只显示隔离提示，控制台
  `0 error / 0 warning`；
- 后端全量 `1016 passed, 1 warning`，前端全量 `10 files / 36 tests passed`，production
  build、CSS/structure audit 通过；本轮未调用 Provider；
- 详细证据见 `docs/engineering/phase-32-wave-26-project-authority-cutover.md`。Wave 32.5
  在该切片后仍未整体关闭：Workflow 正式配置、`/api/runs`、active-run state、执行/SSE/
  Artifact/Monitor 尚未迁移，不能据此宣称 Phase 32 完整生产切换。

2026-08-23 Version 20 active-run 与监控切片：

- Version 20 `useActiveRun`、Shell、Header 心电图、动态阶段状态和移动端监控入口已统一消费
  Phase 32 Run envelope 与 SSE，不再用旧固定八阶段或 timer 派生进度；
- 新增 Phase 32 专用监控台，提供 `272px` 动态阶段栏、阶段/事件内容区和 Inspector，投影
  Artifact 引用、pending decision、Provider usage/cost、checkpoint、连接与恢复状态；
- 创作历史已切到正式 `GET /api/runs`；Phase 32 未迁移阶段显示明确状态页，不再回落旧
  Cast/Volumes/Text/Cover/Export 工作台；
- 空 manifest 首帧不再产生 SVG `width="NaN%"`；前端全量 `15 files / 44 tests passed`，
  production build、CSS/structure/CSS build checks 与三视口浏览器门通过；
- 详细证据见
  `docs/engineering/phase-32-wave-27-run-sse-active-authority-cutover.md`。Wave 32.5 的 active-run、
  Shell 与 Monitor 投影已关闭；Workflow 正式配置和 Artifact 内容工作台仍阻止该 Wave/Phase
  整体关闭。

### Wave 32.6：三路线工作台

工作：

- 先完成共用 Brief/Cast/Text/Cover/Export 外壳；
- 再依次完成 Screenplay、Short/Medium、Long 专属规划工作台；
- 统一二级侧栏、主区和 Inspector 尺寸；
- 接入 draft、decision、amendment、selection、diff 和 source receipt；
- 必要时经 spike 引入专业剧本编辑依赖和列表虚拟化依赖。

测试：每页 Default/Loading/Empty/Error/Busy/Streaming/ReadOnly/Stale/Reduced Motion；草稿防丢；选区 stale；拖拽/键盘等价；400 章/120 人性能 fixture。

退出门：用户可不调用模型，从空白完成每条路线；也可用 Fake Provider 完成相同 Artifact 和决策闭环。

2026-08-23 Brief Artifact 编辑闭环切片：

- 正式 Run API 已开放当前阶段 Artifact 读取和 source-bound 草稿读写；作者草稿绑定
  `run_id + decision_id + domain_revision + source_artifact_ref`，Schema、路线和冻结规模漂移
  在保存前拒绝；
- `accept` 携带 `draft_ref` 时，执行服务先将草稿物化为新的 candidate，再由同一 LangGraph
  decision 路径提交 committed Artifact；不可变 decision receipt 同时冻结原 candidate、草稿
  和物化 candidate 引用，重复命令保持幂等；
- Version 20 Brief 工作台按剧本/小说 Artifact 显示专用字段，支持 650ms 自动保存、刷新恢复、
  定稿、取消、ReviewPolicy 允许时的定向换稿、committed 只读、冻结规模/创作意图/版本来源
  Inspector；Run 尚未暴露 Artifact 时不会发送预期失败的读取请求；
- 决策成功后同时刷新 Run envelope 并从当前 SSE cursor 续接；监控台在重连窗口内优先读取
  pending decision candidate，因此不再把已生成 Story Map 错报为“尚无阶段产出”；
- Fake Provider 浏览器门覆盖空白、candidate、草稿恢复、取消对话框、`Esc` 关闭、定稿、
  Story Map 事件续接和 committed 只读；`1440x920`、`1024x700`、`390x844` 均无横向溢出，
  控制台 `0 error / 0 warning`；
- 后端 Artifact/API 目标集 `11 passed, 1 warning`，前端 Run API/草稿目标集 `2 files / 6 tests
  passed`；最终后端全量 `1021 passed, 1 warning`，前端全量 `17 files / 51 tests passed`，
  TypeScript、production build、CSS/structure/CSS build、`compileall`、`git diff --check` 和
  production closure audit 均通过；本切片未调用真实 Provider；
- 详细证据见
  `docs/engineering/phase-32-wave-28-brief-artifact-editing-closure.md`。Wave 32.6 仍未整体关闭：
  当前只迁移共用 Brief；Story Map、Book Architecture、Cast、Volumes、Rolling Detail、Text、
  Script、Cover 和 Export 等工作台仍须逐个建立相同的正式 Artifact 闭环。

2026-08-23 Story Map Artifact 专业工作台切片：

- 短中篇 `StoryMapArtifact` 已接入与 Brief 相同的 current/source-bound draft/decision receipt/
  committed/SSE 唯一链路，不回读旧 Spine 或建立第二套 Store；
- Version 20 工作台提供统一 272px anchor rail、开场/问题/锚点/结尾/开放问题编辑、稳定 ref
  上下重排、650ms 自动保存、刷新恢复、定向换稿、committed 只读和三视口适配；
- 浏览器验收暴露并修复 Phase 32 Monitor 右侧运行日志缺口；右栏只投影同一 SSE 事件流的最新
  6 条，完整历史继续保留在中央阶段事件区；
- 新鲜隔离 Fake Run 在 Story Map 定稿后自动提交 Cast 与 Section Plan 并停在 Text 决策点；
  后端全量 `1022 passed, 1 warning`，前端全量 `21 files / 60 tests passed`，production build、
  CSS/structure/CSS build、`compileall`、`git diff --check` 与 closure audit 均通过；
- 详细证据见
  `docs/engineering/phase-32-wave-29-story-map-artifact-workbench-closure.md`。Wave 32.6 仍未整体
  关闭：Book Architecture、Cast、Volumes、Rolling Detail、Section Plan、Beat Board、Scene
  Deck、Text、Script、Cover 和 Export 等专业工作台仍待迁移；本切片未调用真实 Provider。

2026-08-23 Book Architecture 专业工作台切片：

- 长篇 `BookArchitectureArtifact` 已接入正式 current/source-bound draft/decision receipt/
  committed/SSE 链路，使用统一 272px Part rail、Book root、Part contracts、Promise 引用观察、
  稳定 ref 重排、650ms 自动保存、刷新恢复、定向换稿、committed 只读和三视口适配；
- 首次浏览器定稿暴露 `bounded_units` 错把聚合首项 ref 当成 Graph `active_unit_ref`：作者合法
  重排后被误判为候选身份漂移。失败 Run 保持不可变；运行时修正为只有
  `sequential_units` 持有 active unit cursor，并用两个 Part 反转提交回归；
- 新鲜隔离 Fake Run 成功保留 `part-hearing / part-archive` 顺序与作者修改，自动提交 Cast 后
  停在 Volumes 决策点；Monitor 显示 Book Architecture 的 5 条事件、最近日志、`4/4`
  Provider operations、checkpoint 与当前决策；
- 后端全量 `1023 passed, 1 warning`，前端全量 `24 files / 68 tests passed`，production build、
  CSS/structure/CSS build、`compileall`、`git diff --check` 与 closure audit 均通过；
- 详细证据见
  `docs/engineering/phase-32-wave-30-book-architecture-workbench-closure.md`。Wave 32.6 仍未整体
  关闭：Cast、Volumes、Rolling Detail、Section Plan、Beat Board、Scene Deck、Text、Script、
  Cover 和 Export 等专业工作台仍待迁移；本切片未调用真实 Provider。

2026-08-23 Cast 人物圣经专业工作台切片：

- 三条路线共用的 `CharacterBibleAggregate` 已接入正式 current/source-bound draft/decision
  receipt/committed/SSE 链路；服务端允许人物文学字段、限制和已登记人物关系修改，同时拒绝
  人物增删、冻结 `subject_ref` 替换和悬空关系端点；
- Version 20 提供统一 272px 人物 rail、紧凑人物档案、关系 composer、路线化文案、Inspector、
  650ms 自动保存、刷新恢复、定向换稿、committed 只读与 3D 确定性图谱；
- 浏览器发现 3D 首帧 `720px` 画布反向撑宽移动工作区并形成 ResizeObserver 测量循环；修复后
  `390x844` canvas 为 `385x458`，五个人物完整入镜，缩放后内部 `scrollLeft=0`；
- 短中篇 Fake Run 完成人物字段修改、`maya -> chen-ke` 关系新增、刷新恢复和定稿；长篇 Monitor
  显示 Cast 当前内容、3 条阶段事件、最近日志、`3/3` Provider operations、checkpoint 与当前决策；
- 后端全量 `1027 passed, 1 warning`，前端全量 `28 files / 76 tests passed`，production build、
  CSS/structure/CSS build、`compileall`、`oxfmt --check`、`git diff --check` 与 closure audit 均通过；
- 详细证据见 `docs/engineering/phase-32-wave-31-cast-workbench-closure.md`。Wave 32.6 仍未整体
  关闭：Volumes、Rolling Detail、Section Plan、Beat Board、Scene Deck、Text、Script、Cover
  和 Export 等专业工作台仍待迁移；本切片未调用真实 Provider。

2026-08-24 Volumes 卷册架构专业工作台切片：

- 长篇 `VolumeArchitectureAggregate` 已接入正式 current/source-bound draft/decision receipt/
  committed/SSE 链路；Provider candidate 与作者草稿共用 Book Architecture Part 和 Cast subject
  上游引用验证；
- 作者可以编辑卷承诺、冲突、高潮、闭合与软篇幅，并重排冻结的 Volume 集合；服务端拒绝
  Volume ref、Part 归属、人物范围增删替换以及重复人物引用；
- Version 20 提供统一 272px Volume rail、四段卷合同编辑器、Part/人物可读标签、Inspector、
  650ms 自动保存、刷新恢复、定向换稿、committed 只读和三视口适配；
- 新鲜隔离 Fake Run 保留作者对 `volume-2` 的四段修改和 `volume-2 / volume-1` 重排，定稿后
  进入 Rolling Detail 决策点；Monitor 显示 Volumes 5 条阶段事件、最近日志、`5/5` Provider
  operations、checkpoint 与 committed ref；
- 后端全量 `1033 passed, 1 warning`，前端全量 `31 files / 84 tests passed`，production build、
  CSS/structure/CSS build、目标 `oxfmt --check`、`compileall`、`git diff --check` 与 closure audit
  均通过；
- 详细证据见 `docs/engineering/phase-32-wave-32-volumes-workbench-closure.md`。Wave 32.6 仍未整体
  关闭：Rolling Detail、Section Plan、Beat Board、Scene Deck、Text、Script、Cover 和 Export
  等专业工作台仍待迁移；本切片未调用真实 Provider。

2026-08-24 Wave 33-36 专业工作台续迁：

- Wave 33 把已迁移 Artifact 工作台统一为默认阅读态、按需编辑态与 `184px` 二级导航，消除候选页面默认表单墙，并完成长篇 Rolling Detail 的 source-bound 浏览器闭环；
- Wave 34 完成短中篇 Section Plan 的 source-bound 双态工作台、冻结上游引用与浏览器矩阵；
- Wave 35 完成剧本 Beat Board 的可见压力、角色决定、结果与 setup/payoff 引用工作台，不恢复旧脊柱因果链；
- Wave 36 完成 Scene Deck 的场景顺序、可见调度、制作信息、Cast 引用与软页数工作台；Beat Board 仅作为上游依据，不伪造 Artifact 未定义的逐场 `beat_ref`；
- Wave 36 全量门为后端 `1054 passed, 1 warning`、前端 `45 files / 116 tests passed`，production build、CSS/structure/CSS build、`compileall`、目标 `oxfmt --check`、`git diff --check` 与 closure audit 均通过；
- 详细证据见 `docs/engineering/phase-32-wave-33-read-edit-stage-workbench-closure.md`、`docs/engineering/phase-32-wave-34-section-plan-workbench-closure.md`、`docs/engineering/phase-32-wave-35-beat-board-workbench-closure.md` 与 `docs/engineering/phase-32-wave-36-scene-deck-workbench-closure.md`；这些切片均未调用真实 Provider。
- 当前仍未整体关闭：Script/Text、Cover、Export、Phase 32 作者协作、Story Bible、自动无障碍、规模/性能、分级真实 Provider 与文学冷读门。

2026-08-24 Wave 37-38 剧本正文与交付续迁：

- Wave 37 完成按冻结 Scene 顺序逐场生成、source-bound 草稿、历史 Scene 回看、阅读/编辑双态、顺序提交与 committed 只读；
- Wave 38 在 Export commit 时从 ordered committed Scene 版本确定性物化 Fountain、PDF 与 Markdown，下载不调用 Provider、不重新生成正文；
- `ScriptDeliveryArtifact`、文件回执、Artifact digest、SHA-256、Scene/version refs 与真实文件共同形成不可变交付边界，列表/下载 API 只投影该权威；
- Brief 的正式 `title` 成为交付文件名与作品库标题的唯一来源，三条官方路线升级为 `r3`，占位标题被合同拒绝；
- Version 20 剧本交付页使用统一 184px 文件轨道、Scene Manifest、完整性摘要和右侧交付回执；1024px 摘要采用 2x2，390px 文件轨道转为横向导航；
- 浏览器真实下载 `失序档案.fountain` 为 `116 B`，SHA-256 为 `99451a10fe68fe2b56fa60525913627ae82c056b1f0c34c1b644173aa98b0ebb`，接口返回 `200`，页面状态切换为“已下载”；
- 最终全量门为后端 `1065 passed, 1 warning`、前端 `50 files / 125 tests passed`；production build、CSS/structure/CSS build、`compileall`、目标 `oxfmt --check`、`git diff --check` 与 closure audit 均通过；
- 详细证据见 `docs/engineering/phase-32-wave-37-screenplay-workbench-closure.md` 与 `docs/engineering/phase-32-wave-38-script-delivery-workbench-closure.md`；两轮均未调用真实 Provider。

2026-08-24 Wave 39 短中篇正文续迁：

- Text 严格按 committed Section Plan 的冻结单元顺序逐一生成和提交，`unit_ref / unit_kind / title / pov_subject_ref` 不允许 Provider 或作者草稿漂移；
- 当前 Provider 上下文只读取当前 Section、相关 Story Map anchors、POV 与一跳关系人物、上一 handoff 和最多 1,200 字正文尾部，不注入完整历史正文；
- Version 20 使用统一 184px 单元导航、主稿纸和计划/交接 Inspector，支持默认阅读态、当前候选编辑、自动保存、刷新恢复、定向换稿和 accepted 历史回看；
- SQLite checkpointer 恢复测试在 U01 提交后重开仓储与 checkpointer，准确恢复到 U02；U02 提交后进入 `cover/awaiting_decision`；
- 最终全量门为后端 `1069 passed, 1 warning`、前端 `52 files / 127 tests passed`；production build、CSS/structure/CSS build、`compileall`、目标 `oxfmt --check` 与 `git diff --check` 均通过；
- 详细证据见 `docs/engineering/phase-32-wave-39-short-prose-workbench-closure.md`；本轮未调用真实 Provider。

2026-08-24 Wave 40 封面与小说成书交付续迁：

- 短中篇 `CoverArtifact` 已使用真实持久化 PNG 候选、source-bound 选择草稿、刷新恢复和正式封面定稿；没有把 CSS 色块或远程占位图当成资产；
- 无图片 binding 的新鲜 Run 在 Cover 正确记录 `provider_contract_failed` 并保持不可变；另一个在创建前冻结本地 Fake image binding 的 Run 完成三候选与正式选择，全程不发外部请求；
- `BookDeliveryArtifact` 只绑定 ordered committed 正文版本与正式封面，Export commit 确定性物化 DOCX，列表和下载只读取不可变回执；
- 浏览器下载的 `失序档案.docx` 为 `7,245 B`，文件 SHA-256 与页面/API 回执一致，内嵌 `cover.png` SHA-256 与 committed Cover 一致；
- Cover/Book Delivery CSS 已按 shell、主内容和 Inspector/receipt 职责拆分；四视口无横向溢出、未命名按钮为 `0`、控制台 `0 error / 0 warning`；
- 最终全量门为后端 `1073 passed, 1 warning`、前端 `56 files / 133 tests passed`；production build、CSS/structure/CSS build、`compileall`、目标 `oxfmt --check`、`git diff --check` 与 closure audit 均通过；
- 详细证据见 `docs/engineering/phase-32-wave-40-cover-book-delivery-closure.md`；本轮未调用真实 Provider。

2026-08-25 Wave 41 长篇逐章正文与交付续迁：

- 长篇 Text 严格按 committed Rolling Detail 冻结的章节顺序串行生成；当前章只读取所属
  Book/Part/Volume、Detail chapter、相关 Cast、上一章 handoff 和最多 `1,200` 字正文尾部；
- 当前候选章开放 source-bound 正文草稿，服务端允许文学正文修改，同时拒绝
  `chapter_ref / volume_ref / title / pov_subject_ref` 漂移；历史 accepted 章节保持只读；
- Version 20 使用统一 `184px` Part/Volume/Chapter 树、阅读/编辑双态正文、移动端横向章节导航
  与计划/交接/来源 Inspector；两章提交后复用正式 Cover 与 Book Delivery 工作台完成交付；
- 浏览器编辑后的第二章进入 ordered Export Manifest；DOCX 为 `7,777 B`，文件 SHA-256
  `e2234234c6b58c8c85aa2f2ce0e2fe7c73b397e9ac37de8e73bd3b3343454c7d`，正式封面 SHA-256
  `438c39240643ca425158458501d4f40ceeb65831c8fbf9af35cec91084d8654a`，页面/API/落盘回执一致；
- 修复 Provider usage 混合成本聚合：文本成本未知、Fake 图片成本 `0.0 / known` 时，全局保持
  `null / unknown`，子项保留各自精度；Run read model 从 receipt store 正确重建为 `11/11` 成功；
- 最终全量门为后端 `1080 passed, 1 warning`、前端 `58 files / 135 tests passed`；production build、
  CSS/structure/CSS build、`compileall`、`git diff --check` 与 closure audit 均通过；
- 详细证据见 `docs/engineering/phase-32-wave-41-long-chapter-workbench-closure.md`；本轮未调用真实 Provider。

### Wave 32.7：Provider operation receipt（已完成）

工作：

- 建立独立 `Phase32ProviderOperationStore`，不复用 legacy `OperationStore`；
- 以 `pending / returned / succeeded / contract_rejected` 区分传输、返回、合同与成功状态；
- 绑定冻结 Provider request signature、raw payload、usage、diagnostic 和候选恢复结果；
- 在 driver 中实现同 operation 成功恢复、returned 重启解析、合同拒绝持久化和 pending 传输重试。

测试：fake gateway 重复 operation、驱动/context 重启、签名冲突、malformed payload/envelope、transport timeout。

退出门：receipt、Artifact candidate 和 request identity 均具备可验证的幂等恢复语义；真实 Provider、bootstrap 注册和 production cutover 仍未开始。

### Wave 32.8：作者协作与监控

作者协作与 route-aware 监控状态：**作者协作已于 Wave 42 完成；运行监控已于 Wave 43 完成本地确定性与响应式浏览器闭环。**

Wave 42 已验证三路线 stage capability、Run/Stage/Unit 线程隔离、首次完整 Context Receipt、后续轻提示、
source-bound SelectionAnchor、Patch Candidate 拒绝保护、历史切换、路由复位，以及
`1440x920 / 1024x700 / 390x844` 响应式投影。Patch 仍不提供直接应用或写回入口；正式
amendment/branch 已在 Wave 45-46 闭合，作者协作 patch 转 amendment 与 Evidence/Outbox 写回仍是独立未闭合门。详细证据见
`docs/engineering/phase-32-wave-42-author-collaboration-migration.md`。

Wave 43 已验证剧本完成、短篇合同失败、长篇 `chapter-1` committed / `chapter-2` candidate 三类
Run 状态；阶段/单元导航、中间真实 Artifact 内容、failure、pending decision、usage、checkpoint 与
最近 200 条正式事件都来自同一权威链路。SSE 刷新保留选择与旧内容，`1024px / 390px` 检查器使用
可关闭抽屉并正确归还焦点。详细证据见
`docs/engineering/phase-32-wave-43-route-aware-run-monitor-closure.md`。

Wave 44 已把 Story Bible 收敛为 Run read model、committed Artifact 与 accepted sequential prefix 的
只读投影。剧本、短中篇和长篇使用各自结构语义；candidate 不进入页面，正文不被自动推断为事实，
连续性只显示可追溯的规划 Promise、开放问题、闭合条件与 handoff。分页 cursor 绑定 projection
revision，来源可返回正式阶段；`1440x920 / 1024x700 / 390x844` 已验证空状态、五分类、56 人加
4 条关系分页、来源跳转、移动端激活分类可见和无横向溢出。详细证据见
`docs/engineering/phase-32-wave-44-story-bible-closure.md`。

Wave 45-47 已完成 committed 规划 Artifact 的 source-bound amendment、确定性 ImpactAnalysis、stale
阻断、successor Run 处置和 Version 20 正式交互。successor 使用新的 Run/thread/checkpoint 身份，只继承
stale frontier 之前的 committed 规划 Artifact；source Run 与 accepted Script/Text prefix 保持不可变。
Project lineage、唯一 branch plan、双向 `run.branched` provenance、receipt 中断恢复、九个规划工作台入口、
刷新恢复和显式跳转均已闭合，旧通用 checkpoint branch 合同已删除。详细证据见
`docs/engineering/phase-32-wave-45-artifact-amendment-authority.md`、
`docs/engineering/phase-32-wave-46-amendment-branch-recovery.md` 与
`docs/engineering/phase-32-wave-47-version20-artifact-amendment-workbench.md`。

工作：

- Phase 31 的 `deep-only` 入口门槛已迁为 stage capability，并覆盖旧三种 quality mode；
- Context receipt 和 patch schema 适配新 Artifact；
- Monitor rail/content/inspector 按 route/stage 动态投影；
- 修复历史 replay、日志、Evidence、checkpoint、usage 和 writeback 全状态。

测试：三路线线程隔离、source-bound patch、rebase/fork、取消/恢复、SSE 静默 replay、日志不消失、无整页闪烁。

退出门：协作台不能绕过 amendment/branch/Canon 权限；监控能完整观察三条 Fake Run 的真实内容和健康。

### Wave 32.9：清理、分级真实验收与发布

工作：

- 静态删除旧生产模板、Prompt、类型、路由、CSS selector 和死代码；
- 全量后端/前端/浏览器/性能/恢复门；
- 删除 `official-deepseek-fast/balanced/deep` 旧身份、映射和模板，只保留
  `official.screenplay_sample`、`official.short_novel`、`official.long_novel` 三条官方路线；
- 三条官方路线分别执行一次小规模、全阶段、真实 Provider 新鲜 Run，先验证链路稳定性，不以
  文学审美阻断 `0.1.0`；
- 三条 Run 同时通过后，从零重写 README、`0.1.0` CHANGELOG、截图和发布说明；
- 最终确定性门通过后提交、推送并发布 `v0.1.0`，新 Release 可见后再删除旧 Release/Tag。

退出门：见第 17 节；旧生产路径和旧三档身份静态缺席；三条同版本新鲜 Run、Export、截图、
稳定性报告和 `0.1.0` 发布物齐全。

## 17. 测试与验收矩阵

### 17.1 静态与合同门

- `rg` 证明生产代码无旧 `fast/balanced/deep`、固定 `STAGE_ORDER/PHASE27_EDGES` 和 `official-deepseek-*`；
- 三 RouteSpec graph snapshot 与 digest 稳定；
- 非法 stage、Artifact、Prompt、Context、ReviewPolicy 和 route revision 全部拒绝；
- API adapter 不出现编排、Context 聚合、质量和持久化业务；
- 前端目录只使用 `layout/planning/brief/running/settings/state/services/contracts/lib`；
- production build 无 archive/legacy runtime import。

### 17.2 后端测试层

1. Unit：Artifact、Scale、route compiler、dependency、impact、quality、Context、Prompt、receipt。
2. Property-based：稳定 ref、插入/移动、Window 连续、Promise lifecycle、预算守恒和幂等；实施时引入 `Hypothesis`，不手写少量样例冒充边界覆盖。
3. Graph：每路线 happy path、warning、blocker、cancel、regenerate、amend、resume、restart。
4. Store/API：并发、重复 key、损坏 projection、历史只读、Export hash。
5. Chaos：Provider timeout/429/鉴权、进程退出、SSE 断线、重复 resume、Evidence 失败。
6. Full regression：Phase 28 确定性连续性、Evidence、Outbox、Canon/Wiki 与 Phase 31 协作边界全部迁移后通过。

### 17.3 前端与浏览器门

视口：`1440x920`、`1024x700`、`390x844`。

- 三条路线所有阶段逐页截图，并与 Version 20 视觉基线和本 RFC 信息层级核对；
- 所有 click、hover、active、focus、drag、keyboard、route、modal、drawer、toast 都有可观察结果；
- Header 动态阶段数、二级侧栏 `184px`、主区满高、Inspector 收起和监控专注模式正确；
- 无双层 Loader、无加载结束突变、无内容重叠、无大面积无意义留白；
- SSE 更新不让整页闪烁，日志和当前内容不因阶段切换丢失；
- `prefers-reduced-motion`、键盘、焦点、对比度和屏幕阅读器标签通过；
- 引入 `@axe-core/playwright` 做自动无障碍门，不能只靠截图；
- 控制台零 error，网络请求无 mock，失败状态可恢复且文案指出最低责任层。

### 17.4 性能与规模门

- 500 章、50 卷、9 Part、120+ 人物；
- 10,000 Provider operations、20,000 events；
- 列表只挂载可见区，切换当前单元不加载整本正文；
- Context/Prompt 大小不随全书字符数线性增长；
- event append、usage summary 和 SSE cursor 不全文件扫描；
- 监控批量消费事件，页面不持续 animation loop；
- Export 流式读取章节，不在内存中保留多份全书字符串。

### 17.5 `0.1.0` 三路线真实全链路稳定性门

这是一组体验版发布阻断门，只在全部功能 Wave、静态门、Fake Provider、恢复、前后端全量测试和
浏览器矩阵完成后执行。历史、失败和旧三档 Run 一律不复用；三条路线各创建新的 Project 与 Run。

#### 17.5.1 发布前置

1. 生产源码、运行配置、前端和测试中不存在 `official-deepseek-fast/balanced/deep`、旧
   `fast/balanced/deep` 模式或兼容映射；
2. 验收只允许选择 `official.screenplay_sample`、`official.short_novel`、
   `official.long_novel`，并在 Run 创建时冻结 Route revision/digest、ReviewPolicy、ScaleProfile、
   文本 Provider 和图片 Provider binding；
3. 短中篇和长篇必须在创建 Run 前通过真实图片 Provider preflight；缺少图片 binding 时不得先跑
   文本阶段再在 Cover 失败；
4. 每条 Run 预先冻结最大 Provider operation 数、调用预算和成本上限；密钥、完整请求正文和原始
   敏感响应不得进入日志或发布证据；
5. 为小规模长篇建立显式 `release_smoke` ScaleProfile。它只缩小容量，不改变官方 RouteSpec、
   Stage、Artifact、Prompt、Context、ReviewPolicy 或 Provider 路径；不得出现在普通创建向导、
   不得转为生产作品、不得让正常长篇下限退化；
6. 三条 Run 必须基于同一份 runtime source digest。任一 Run 后发生运行时代码、Prompt、Schema、
   Route、Provider 或持久化修改，三条 Run 全部作废并重新开始。

#### 17.5.2 小规模完整样本

| 官方路线 | `release_smoke` 容量 | 必须走完的真实链路 | 最终交付 |
| --- | --- | --- | --- |
| `official.screenplay_sample` | 3 分钟目标、2-3 个 Scene | Brief -> Cast -> Beat Board -> Scene Deck -> Script -> Export | Fountain、PDF、Markdown 均可下载并通过哈希 |
| `official.short_novel` | 2,000-5,000 字软目标、2-3 个正文单元 | Brief -> Story Map -> Cast -> Section Plan -> Text -> Cover -> Export | 真实封面；EPUB、DOCX、Markdown 均可下载并通过哈希 |
| `official.long_novel` | 1 Part、1 Volume、1 Detail Window、2 章；仅验收容量 | Brief -> Book Architecture -> Cast -> Volumes -> Rolling Detail -> Text -> Cover -> Export | 真实封面；EPUB、DOCX、Markdown 均可下载并通过哈希 |

字数和时长只用于限制成本，不用于凑量。只要正文非空、非明显截断并能完成 Artifact/Export 合同，
文学表现不阻断本门。

#### 17.5.3 稳定性通过条件

- 每个 Stage 都产生合法 candidate、decision/auto-continue 记录、committed Artifact 和单调 SSE
  事件；顺序正文单元全部拥有不可变版本；
- UI 路由、Header、二级导航、监控当前内容、日志、Provider usage 和终态作品库均投影同一 Run
  权威，没有 mock、计时器假进度、双 Loader 或阶段错位；
- Provider operation identity、input snapshot、receipt、usage、checkpoint、Artifact writeback 与
  Export hash 完整，调用次数不存在无界增长；
- 断开并恢复一次 SSE 后不重复 Provider 调用、不丢日志；完成 Run 刷新后读取静态终态，不重放
  历史执行；
- 所有配置的导出文件都能真实下载，文件、正文版本和封面 SHA-256 与冻结回执一致；
- 三条 Run 均到达 `completed/export`，没有 `needs_action`、悬挂 decision、未结算 operation、
  孤立 candidate 或未写回状态。

#### 17.5.4 失败处理纪律

1. 首次失败立即停止当前 Run，冻结 definition、state、checkpoint、Provider input/receipt、usage、
   SSE 和浏览器证据；不得在同一 Run 上连续 regenerate 或 attempt N+1；
2. 先把故障归到最低责任层：Provider 传输/能力、结构解析、Prompt/Context 编译、Artifact 合同、
   Graph 状态转换、持久化/幂等、SSE/read model 或前端投影；
3. 先用冻结输入和脱敏响应建立离线 fixture 重现，再修改生产代码；本地 Stage guard 只有在根因确实
   属于该 Stage Artifact 时才允许，否则必须修正共同上游或底层权威；
4. 禁止用 fallback、隐式默认值、旧字段 alias、自动换模型、吞错 normalizer、额外隐藏重试或第二套
   runtime 掩盖失败；同类问题跨阶段或再次出现时，强制进行责任边界审查并重构，不继续打补丁；
5. 修复必须同时增加正向合同、拒绝合同和旧路径静态缺席证据。失败 Run 保持只读；修复后创建全新
   Project/Run，从该路线起点重新验收；
6. 三条 Run 没有在同一 runtime source digest 下全部通过前，不得开始版本修改、README 重写、
   commit、push、Tag 或 Release 操作。

### 17.6 `0.1.0` 文学观察边界

体验版首发先证明系统能稳定完成三种不同作品链路，文学质量不作为 `0.1.0` 发布阻断条件。不得因
模型 reviewer 的低分、节奏、文风、人物魅力或“AI 味”自动换稿，也不得为改善样本反复调用真实
Provider。

每份样本仍应生成简短非阻断观察记录：

```text
作品承诺兑现
结构完整与收束
人物动机与变化
事件/状态连续性
节奏与信息密度
对白/叙事声音区分
重复、解释过度和 AI 味
路线专项：可拍性 / 单体余韵 / 长线可持续性
问题定位到 stage + artifact/unit + prompt/context/quality 责任层
```

自动指标只做筛查。空 Artifact、明显截断、引用损坏、状态矛盾、缺章、封面/Export 不一致仍是
确定性稳定性失败；其余文学问题只进入后续版本清单。不能让同一模型既创作又以自评分证明自己
质量达标。更大篇幅、通篇冷读和文学质量提升在 `0.1.0` 之后单独验收，不反向改写本次稳定性结论。

## 18. 发布证据包

`0.1.0` 发布前必须交付：

- 三个官方 Workflow ID、RouteSpec、Workflow revision/digest 和冻结 ReviewPolicy；
- 三条新鲜 Run 的 Project/Run ID、Provider receipts、usage、失败/恢复记录；
- 各 Stage/Artifact/Unit 数、篇幅、版本和完整率；
- Context 预算、Prompt digest、Evidence、Outbox、Canon/Wiki 和 Export hash；
- Desktop/短桌面/Mobile 截图与交互录像；
- 无障碍、性能、恢复和静态删除报告；
- 三份稳定性报告和简短非阻断文学观察；
- 未阻断但进入下一版本的问题清单。

发布顺序固定为：

1. 三条稳定性 Run 全部通过并冻结证据；
2. 把 `pyproject.toml`、`apps/web/package.json`、lock metadata 和所有对外版本统一为 `0.1.0`；
3. 从零重写 `README.md`，只描述当前新产品：产品定位、三条创作路线、功能边界、安装、Provider/
   图片 Provider 配置、首次使用流程、数据存储与隐私、体验版限制、开发验证和 License；
4. README 不保留 v1/v1.1、旧八阶段、旧三档、Phase/Wave 过程、历史 Run 战报、内部调试解释或
   与普通用户无关的实现流水账；任何链接的多语言 README 必须同步重写，否则删除入口；
5. `CHANGELOG.md` 以 `[0.1.0]` 作为新产品首个公开版本，只写用户可感知能力与已验证边界；
6. 对 README/版本元数据之外没有运行时代码变化做静态证明，再重跑全量确定性门、构建、浏览器
   发布页检查、敏感信息扫描和 `git diff --check`；
7. 创建单一发布 commit，推送到 GitHub，创建并验证 `v0.1.0` Tag/Release 和安装说明可用；
8. 新 Release 可见且仓库默认页正确后，删除旧 GitHub Release 与对应旧 Tag。当前本地观察到的
   旧 Tag 为 `v1.1.0`，执行时必须先只读确认远端精确目标；不删除 Git 历史提交、不重写 main 历史；
9. 最后从全新 checkout 按 README 执行一次安装、启动和三路线入口 smoke，确认公开仓库不是只在
   当前脏工作树可运行。

README、截图、CHANGELOG、Git commit、push 和 Release 是验收结果，不是验收手段。证据包不完整、
任一真实 Run 未完成或发布后全新 checkout 不可用时，`0.1.0` 不得发布。

## 19. 风险与控制

| 风险 | 触发信号 | 控制 |
| --- | --- | --- |
| 三路线变成三套系统 | Store/API/UI 出现大量 route 复制 | RouteSpec + shared lifecycle + Artifact/workbench registry；静态重复审计 |
| “灵活”变成无合同 | Provider 可自由改 ID、顺序和事实 | 文学字段灵活，身份/引用/状态/写回严格确定性 |
| 旧因果链换名后继续存在 | Story Map/Part 仍强制精确 cause/change 配额 | 删除生产 StorySpine，范围内提案，因果只作 warning |
| 自动继续掩盖质量问题 | warning 被静默丢弃或一路冻结 | 里程碑汇总、可定位证据、mandatory decision 不可关闭 |
| ReviewPolicy 变成旧三档换皮 | 路线卡上出现速度/质量三色切换 | 路线只描述交付物；审阅策略在 Workflow 高级配置 |
| 长篇计划重新巨型化 | 一次加载全书 Part/Volume/Detail | 聚合根 + bounded units + pagination/virtualization |
| 作者协作形成第二权威 | Chat patch 直接改 Artifact/Canon | source-bound candidate + amendment/branch + Evidence/Outbox |
| 真实验收继续空烧 token | 合同拒绝后自动 attempt N+1 | Stop gate、成本门、离线重放、显式恢复 |
| Figma 风格被功能堆叠破坏 | 卡片套卡片、持续闪烁、灰字不可读 | Version 20 token、统一尺寸、逐页截图与浏览器矩阵 |
| 历史兼容污染新运行时 | 旧 Run 可以 resume 或调用新 graph | archive-only + explicit Import Package + 写请求拒绝 |

## 20. 明确拒绝的方案

1. 只把 Fast/Balanced/Deep 改中文名称，继续同一八阶段图。
2. 为三条路线复制三套 LangGraph、Store、SSE 或前端 Shell。
3. 把旧 Spine 藏进 `story_map` 名称下，继续精确 turn 配额和无限语义修复。
4. 让用户在运行中切换路线或审阅策略，导致冻结合同漂移。
5. 用一个通用 JSON 表单渲染所有 Artifact，牺牲专业工作台和类型安全。
6. 因为怕加依赖而用 textarea 模拟专业剧本编辑器、用全量列表模拟长篇导航。
7. 因为依赖成熟就引入第二套 Provider/Agent/runtime 协议。
8. 把 LLM reviewer 分数当 blocker 或自动换稿授权。
9. 为旧 Run 增加 converter/fallback，使新旧 Artifact 同时可执行。
10. 未通过小门就直接运行 50,000、100,000 或 1,000,000 字真实 Provider 测试。
11. 用 `official-deepseek-fast/balanced/deep` 兼容映射或旧 JSON 模板冒充三条新官方路线验收。
12. 在新 `v0.1.0` Release 可见前先删除唯一可用旧 Release，或通过重写 Git 历史伪装为全新仓库。

## 21. 批准后的第一执行顺序

本 RFC 获批后，严格按以下顺序开始：

1. 改写 `stage-artifact-contract.md`，使 Phase 32 成为唯一生产目标合同。
2. 完成 dirty worktree 逐文件归属表，先吸收 Phase 28/29 已完成能力，不覆盖用户改动。
3. 实施 Wave 32.1 Route Kernel，先让三条 Fake Run 使用同一 runtime 成立。
4. 通过 Route/Artifact/State/Recovery 后端门后再开始 UI，不用 mock UI 倒逼假接口。
5. UI 按 Shell/向导 -> 共用工作台 -> 三路线专属工作台 -> 监控/协作顺序接入。
6. 全部离线、浏览器、恢复和静态删除门通过后，再申请第一次真实 Provider 成本门。

Phase 32 的成功标准不是“页面上出现三个入口”，而是三个入口分别产生不同且合理的创作过程，同时仍能在一个可恢复、可追溯、可测试、可长期维护的 Yotsuba Ink 产品中完成真实交付。
