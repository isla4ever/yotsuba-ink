# Yotsuba Ink Phase 32 Stage Artifact Contract

状态：Phase 32 已批准，本文是三种创作路线的唯一目标生产合同。旧 Phase 27 八阶段图只用于历史 Run 的只读归档；在 Phase 32 实施 Wave 完成前，当前生产代码仍可能尚未全部迁移，不能据本文声称新路线已经可执行。

日期：2026-08-22

实施 RFC：`docs/architecture/phase-32-three-creation-routes-reconstruction.md`

## 1. 产品路线

配置页不是运行阶段。新 Run 必须冻结以下一条创作路线：

```text
screenplay_sample:
brief -> cast -> beat_board -> scene_deck -> script -> export

short_novel:
brief -> story_map -> cast -> section_plan -> text -> cover -> export

long_novel:
brief -> book_architecture -> cast -> volumes -> rolling_detail -> text -> cover -> export
```

路线表达交付物，不表达速度或模型质量。生产合同删除 `fast / balanced / deep`；审阅密度、自动继续、Provider、模型、上下文预算和有向换稿次数属于 Run 前冻结的 Workflow/ReviewPolicy。

三条路线共享一个 LangGraph runtime、checkpointer、Provider gateway、operation receipt、Evidence/Outbox、Canon/Wiki、SSE、read model 和恢复语义。不得建立 route runtime selector、fallback、shadow、dual graph 或旧 schema converter。

## 2. 新建作品与 Run

新建作品保持两个主步骤：

1. 选择创作路线和官方/自定义流水线；需要调整时创建本书副本或另存模板。
2. 提交自由创作想法、目标时长/篇幅和可选 Source Pack/Adaptation Package；高级配置可调整 ReviewPolicy 与 Provider。

项目创建后以“待定标题”显示。正式标题只来自已提交 Brief，不从向导输入、候选稿或 UI mock 提前投影。

Run 创建时冻结：

```text
architecture_version: phase32-routes-v1
creation_route_id / route_revision
creation_language: zh-CN
compiled_stage_manifest[]
review_policy
scale_profile
provider_bindings_by_stage
inputs / export_profile
workflow_id / workflow_revision / workflow_digest
```

路线在 Run 内不可切换。需要切换时创建新 Run；历史内容只能通过用户显式选择的 Import Package 成为新 Run 的 Source，不得转换旧执行状态。

## 3. 每阶段一个核心 Artifact

每阶段只有一个用户可编辑或确认的核心 Artifact。聚合根可以引用有界子单元，但子单元只能属于一个聚合版本，不能绕过聚合根独立成为第二权威。

候选、draft、锁定、provenance、review、质量报告、预算、Context receipt、Provider receipt、checkpoint、Evidence、Outbox、SSE 和 UI 坐标都是 sidecar 或确定性投影，不得进入核心文学 Artifact。

### 3.1 剧本样片

| 阶段 | 唯一核心 Artifact | 用户决定 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `brief` | `ScreenplayBriefArtifact` | 样片类型、目标时长、命题、观众承诺、可见冲突、结尾效果、语气 | Planning aggregate | Cast、Beat Board |
| `cast` | `CharacterBibleAggregate` | 必要人物、屏幕目标、利害、限制、对白声纹、关系压力 | Planning aggregate | Beat Board、Scene Deck、Script |
| `beat_board` | `BeatBoardArtifact` | 哪些角色决策和结果必须被看见，节奏是否兑现样片承诺 | Planning aggregate | Scene Deck |
| `scene_deck` | `SceneDeckArtifact` | 场景顺序、地点/时间、人物、可见目标、对抗、结果和软页数 | Planning aggregate | Script |
| `script` | `ScreenplayDraftArtifact` | 接受、局部改写、分支或回到 Scene Deck 修订 | Script version store + Evidence proposal | Export、Adaptation Package |
| `export` | `ScriptDeliveryArtifact` | Fountain/PDF/Markdown、标题页与版本注记 | ExportStore | 无 |

`BeatBoardArtifact` 的单元为 `dramatic_job / visible_pressure / character_decision / outcome / setup_or_payoff_refs / timing_hint`。顺序、引用和覆盖是硬合同；决定是否可信、冲击是否足够是文学 warning。

`SceneDeckArtifact` 只规划屏幕上可见的行动、冲突和结果，不写小说式内心梗概。Script 使用规范块类型；Provider 不拥有 scene ref、版本、页码、状态或导出元数据。

### 3.2 短中篇小说

| 阶段 | 唯一核心 Artifact | 用户决定 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `brief` | `NovelBriefArtifact` | 前提、读者承诺、主题、世界硬规则、结局方向、声音和软篇幅 | Planning aggregate | Story Map |
| `story_map` | `StoryMapArtifact` | 开场压力、故事问题、选择/揭示、后果、Promise 推进和收束条件 | Planning aggregate | Cast、Section Plan |
| `cast` | `CharacterBibleAggregate` | 必要人物、欲望、利害、限制、关系和变化范围 | Planning aggregate | Section Plan、Text |
| `section_plan` | `SectionPlanArtifact` | 章节/段落单元、戏剧任务、POV、场景负载、handoff 和软预算 | Planning aggregate | Text |
| `text` | `ShortProseUnitArtifact` | 接受、人工编辑、定向改写、分支或上游修订 | Prose unit version store + Evidence/Outbox | Cover、Export |
| `cover` | `CoverArtifact` | 视觉 Brief、候选资产与正式封面 | ArtifactStore + AssetStore | Export |
| `export` | `BookDeliveryArtifact` | 正文版本、封面、格式和元数据 | ExportStore | 无 |

`StoryMapArtifact` 使用有限 anchors，不使用精确 turn 配额。Provider/作者在 ScaleProfile 的容量范围内提出数量，接受后才冻结。代码校验稳定 ref、顺序、Promise 覆盖和 ending state，不宣称能确定性证明文学因果。

`ShortProseUnitArtifact` 是唯一正文单元合同；code-owned `unit_kind=section|chapter` 从 Section Plan 投影，不存在 Chapter/Section 两套生产 Artifact。

### 3.3 长篇小说

| 阶段 | 唯一核心 Artifact | 用户决定 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `brief` | `NovelBriefArtifact` | 长期承诺、世界规则、主题、终局、声音和规模 | Planning aggregate | Book Architecture |
| `book_architecture` | `BookArchitectureAggregate` | Book/Part 边界、进入/退出状态、Promise 推进和终局条件 | Planning aggregate | Cast、Volumes |
| `cast` | `CharacterBibleAggregate` | Book/Part/Volume scope、人物职责、关系、限制、弧线和归档 | Planning aggregate | Volumes、Rolling Detail、Text |
| `volumes` | `VolumeArchitectureAggregate` | 卷承诺、冲突、高潮、闭合、Part 归属和人物/结构引用 | Planning aggregate | Rolling Detail |
| `rolling_detail` | `DetailPlanIndexArtifact` | 当前有界 Window 的章节施工图、场景、handoff 和下一窗口入口状态 | Planning aggregate | Text、下一 Window |
| `text` | `ChapterArtifact` | 接受、人工编辑、定向改写、分支或未来规划 amendment | ChapterStore + Evidence/Outbox | 下一章/Window、Cover、Export |
| `cover` | `CoverArtifact` | 视觉 Brief、候选资产与正式封面 | ArtifactStore + AssetStore | Export |
| `export` | `BookDeliveryArtifact` | Part/Volume/Chapter 版本清单、封面、格式和元数据 | ExportStore | 无 |

`BookArchitectureAggregate` 只保存 Book root、稳定 Part refs、全书 Promise/milestone refs 和 ending conditions；每个 `PartContractArtifact` 保存 entry state、dramatic question、Promise 生命周期、turning points、exit state 和 unresolved obligations。不得恢复 flat 全书 `StorySpineArtifact cause/change`。

`VolumeArchitectureAggregate` 和 `DetailPlanIndexArtifact` 都是聚合根。有界 `VolumeContractArtifact` 与 `DetailWindowArtifact` 通过一个聚合 commit 提交。Rolling Detail 默认覆盖 1-3 卷或 12-40 章，最终窗口大小由上下文预算和自然边界决定。

## 4. Cast 与事实权威

Cast 是正文前唯一具名主体注册表：

- Cast 前的 Story Map/Book Architecture 只用功能描述；用户在 Brief 中给出的名字在 Cast commit 前没有稳定 subject ref。
- Cast 后的 Beat/Scene、Section、Volume、Window、Text 和 Script 只能引用冻结 subject ref。
- 新增主体、职责升级、关系端点变化、首次/最后出场 scope 变化必须走 Character amendment + ImpactAnalysis。
- 已被 accepted prose/script 引用的主体只能停止未来出场或归档，不得硬删除历史身份。
- 3D/2D 人物图、出场覆盖和关系邻域是可重建投影，不能写回 Character Artifact。

未来新建 Run 使用三条官方路线 `r3` 与 `cast.v2` Context policy。每次 Cast Provider
请求必须携带内容寻址的 `epistemic_custody`：以 source path、source ref、value digest、
认识论状态、允许用途和禁止升级方式逐项标记作者输入及上游规划字段。作者约束、已接受规划、
未来风险、计划结局、主题/故事问题和风格约束不得混为同一种“事实”。规划 Artifact 仍不是
Canon；开放问题、怀疑、未来结果和风险不得被 Cast 固化为隐秘动机、罪责、必然后果或既成
关系。该边界属于 Prompt/Context 合同与文学审读要求，不使用关键词过滤冒充确定性 blocker。

World rules、Character Graph、用户知识库、Wiki、Canon 和 Evidence 是不同系统。模型对话、检索结果、review、自评分和 UI 可视化没有 Canon/Wiki 写权限。

## 5. 篇幅与容量

| 路线 | P0 支持范围 | 默认建议 |
| --- | ---: | ---: |
| 剧本样片 | 3-30 分钟目标时长 | 8-15 分钟 |
| 短中篇小说 | 2,000-130,000 中文字符 | 网络短故事 10,000-30,000 |
| 长篇小说 | 100,000-1,000,000 中文字符 | 首次生产门 100,000-200,000 |

`100,000-130,000` 允许两条小说路线重叠：单一主线、少量人物和单体收束推荐短中篇；多 Part、多卷、长期 Promise 和连载推荐长篇。

Scale planner 返回 `min / recommended / max` 和推导原因。Provider/作者在范围内提出结构数量，接受后冻结。字数、页数、节拍、章数、卷数和场景密度首先是软目标；只有空文本、明显截断或低于冻结最低可用比例才阻断。禁止为凑数量隐藏扩写、截断、重排或换稿。

## 6. ReviewPolicy 与重试

ReviewPolicy 在 Run 前冻结：

```text
checkpoint_policy: milestone | every_stage | every_unit
warning_policy: continue_and_surface | pause_at_milestone
contract_correction_limit: 1
directed_redraft_limit_by_stage: 0..2
auto_continue_stages[]
mandatory_decision_stages[]
```

确定性 blocker 永远暂停。文学 warning 可以继续并在里程碑汇总，但不能被丢弃。系统不提供“忽略所有错误并一路冻结”。

三类重试必须独立记账：

1. 传输重试：同一输入、operation identity 和 Provider 的有界重连。
2. 合同纠正：解析/Schema 错误最多一次，不改变文学方向。
3. 定向换稿：必须有明确 direction、scope、次数和用户/ReviewPolicy 授权。

达到上限进入 `needs_action`。不得自动切换 Provider/model、继续 attempt N+1 或用完整失败稿污染局部恢复。

## 7. 确定性质量与文学判断

允许阻断：

- Artifact 缺失、空文本、Schema/code-owned metadata 违规；
- 未知/重复 ref、悬空引用、顺序缺口、Window 重叠；
- 使用未冻结主体/结构/source fact；
- accepted 版本被覆盖或 stale 下游继续执行；
- 已知互斥状态变化没有台面 transition/evidence；
- manifest/hash/version/receipt/checkpoint/writeback 幂等失效；
- 明显截断或低于最低可用篇幅。

只能 warning：

- 动机、因果说服力、高潮力度、节奏和创造性；
- 人物声音趋同、解释过多、AI 味、主题表达和市场吸引力；
- 可拍性、余韵、长线潜力及任何低置信 LLM reviewer 判断。

warning 必须绑定 stage/unit/source refs、精确 evidence 和建议动作。Reviewer 没有自动改稿、写 Canon/Wiki 或无限重试权限。

## 8. LangGraph、Provider 与 Context

LangGraph Graph API 是唯一生产控制面：一个 Run thread、一个持久 checkpointer、一个 interrupt/resume 路径、一个事件体系和一个 Outbox。相邻正文/剧本单元按 handoff 和 accepted state 顺序执行；只读 reviewers 可以读取同一冻结快照并行运行。

每个 Provider operation 调用前保存不可变、脱敏、内容寻址的输入快照，receipt 记录真实 usage、transport attempts、Provider result 和合同结果。Schema/文学失败不得伪装成传输重试；Export 不调用 Provider。

Context 必须按 route/stage/unit 窄编译：

- Screenplay：当前 Beat/Scene、相关 Cast、上一 scene handoff；
- Short novel：当前 Section、相关 Cast、Story Map anchors、上一 handoff；
- Long novel：Book/Part/Volume 当前合同、Detail chapter、Resolved State、相关 Cast、上一 handoff。

Context/Prompt 大小不得随全书长度线性增长。Source Pack 只能由用户选择并按 route policy 注入；正文不盲检索。Provider 不写 ID、顺序、hash、status、版本、Evidence lifecycle 或导出元数据。

`inputs.creation_language` 是 Run 创建前冻结的唯一输出语言权威。当前产品只支持 `zh-CN`；所有 Provider Artifact 的面向作者自然语言字段必须使用简体中文。Schema key、枚举值、稳定 ref 和 code-owned metadata 继续使用合同规定的 ASCII，不得因为语言要求把引用改成中文标签。语言偏离属于可见 warning 与人工验收问题，不用脆弱的关键词扫描伪装为确定性 blocker。

## 9. Amendment、版本与跨路线输入

committed Artifact 不原地覆盖。正式修改创建 source-bound `ArtifactAmendment`，先生成 `ImpactAnalysis`：

```text
preserved[]
stale[]
blocked_references[]
accepted_history[]
recompute_scope[]
```

用户选择 `affected_only` 或 `restart_from_stage`。新版本成为 active 后，原 Run 进入 `needs_action`，stale 下游不能在原 Run 继续；accepted prefix 保持不可变。正式继续路径必须创建 successor Run：使用新的 Run/thread/checkpoint 身份，继承最早 stale stage 之前的 committed 规划 Artifact，从 stale frontier 重新执行。原 Run、旧 checkpoint 和 accepted Script/Text prefix 只作历史对照，不能被清空、复制为新执行前缀或恢复调用 Provider。

一个 amendment 只允许一个内容寻址 branch plan 和 successor。Project lineage 保存相邻 source/target 边，source 与 target 事件流各写一个 `run.branched` provenance；客户端不能指定 target Run id、切换 route、覆盖 Provider binding 或复用 source checkpoint。

剧本样片可以显式导出 `AdaptationPackage`。小说路线导入时只把用户选择的 Brief/Cast/Beat/Scene/Script refs 作为带签名 Source Pack 和规划提案材料，仍须生成并确认本路线自己的 Artifact。源/目标 Run 不共享可变状态。

## 10. State、事件与 UI 投影

`NarrativeRunState` 只保存 route、stage/unit cursor 和引用。Provider receipt、review、Evidence、Outbox、usage、Context manifest 和 SSE sequence 由各自 Store/read model 拥有。

Run read model 必须返回 `creation_route_id / route_revision / stage_manifest / active_stage_id / active_unit_ref / stage_status / artifact_refs / pending_decisions / provider_usage / failure / checkpoint`。Header、Project Shell、工作台、监控和历史页只从这份 manifest/read model 投影，不维护固定八阶段数组或本地 fake progress。

SSE 复用稳定领域事件：`stage.started`、`candidate.created`、`decision.required/resolved`、`artifact.committed`、`unit.failed`、`review.completed/unavailable`、`evidence.completed/recovery_required`、`writeback.committed/failed`、`checkpoint.saved`、`run.branched`、`export.ready`。事件增加 route revision 和可选 unit/artifact kind，不复制三套事件名；`run.branched` 只记录 successor Run 的双向 provenance，不能伪装成未实际保存的 checkpoint。

UI 保持 Version 20 暗黑专业创作台：

- Header 从动态 manifest 渲染短心电图进度；阶段事件只律动一次。
- 阶段二级侧栏使用统一的紧凑宽度 token（当前为 184px），内容按真实高度排列，不拉伸铺满；监控专注页的 route rail 按其独立信息密度设计。
- 主区占满剩余视口；右 Inspector 只显示当前阶段的来源、影响、质量和回执。
- 作者协作台与产品主侧栏互斥，但保留阶段二级导航。
- 监控隐藏 Project 主侧栏，使用 route-aware rail + 内容 + 健康/日志 Inspector。
- Loading/route/tab/内容切换有限淡入淡出；SSE 不触发整页闪烁；Reduced Motion 有静态降级。

## 11. 历史 Run 与迁移

所有 `phase27-vnext` Run 保持不可变、只读、零 Provider：可查看、比较和导出，不可 resume、decision、amend 或写回。旧 Artifact、Prompt、模板和 mode 只能存在于历史文档、归档数据和 archive viewer，不得成为新 Run 构建输入。

Phase 32 每个 Wave 必须：

1. 建立一个新正向生产路径；
2. 同时删除对应旧字段、模板、Prompt、路由、selector 和 runtime branch；
3. 用正向合同测试和旧路径拒绝测试证明边界；
4. 运行静态搜索证明 legacy 缺席；
5. 通过 fake Provider、全量离线和浏览器低层门后，才申请新鲜真实 Provider 成本门。

## 12. 验收边界

本合同批准不等于实现完成。证据必须分开记录：

- 文档批准；
- 本地 Artifact/Graph/API 合同；
- Fake Provider 与恢复；
- 前端 build 和浏览器矩阵；
- 新鲜真实 Provider；
- 通篇文学冷读与成本报告。

历史 Run、旧测试数字和设计截图不能替代新路线的生产验收。README、CHANGELOG、Git commit 和 GitHub push 只能在三路线证据包完整后进行。
