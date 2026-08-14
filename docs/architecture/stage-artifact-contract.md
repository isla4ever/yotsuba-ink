# Yotsuba Ink vNext Stage Artifact Contract

状态：Phase 27 实施中的唯一生产合同（2026-08-12）。生产阶段、Artifact、Run 输入与 LangGraph 路径必须遵循本文；Phase 26 和更早文档只保留为失败证据。当前仅证明离线合同与 fake Provider 基线，尚未完成 Phase 27 浏览器矩阵、全新真实 Provider Run、8-12 章单卷冷读或投稿质量验收。

## 生产阶段

配置页不是运行阶段。LangGraph 只编译并执行下面这一条图：

```text
brief -> spine -> cast -> volumes -> detail -> text -> cover -> export
```

| 阶段 | 唯一核心 Artifact | 用户决策 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `brief` 创作立项 | `StoryBriefArtifact` | 故事承诺、世界规则、主题问题、结局承诺、叙事声音和软长度意图 | `ArtifactStore.brief` | `spine` |
| `spine` 故事脊柱 | `StorySpineArtifact` | 因果推进、最终变化和结局是否兑现立项承诺 | `ArtifactStore.spine` | Role Demand、`cast`、`volumes` |
| `cast` 人物编排 | `CharacterBibleArtifact` | 主角、重要配角、功能/历史主体的职责、关系、变化和首次出现窗口 | `ArtifactStore.cast` | `volumes`、`detail`、`text` |
| `volumes` 分卷架构 | `VolumeArchitectureArtifact` | 每卷卷名、promise/conflict/climax/closure 与自然边界是否构成完整故事 | `ArtifactStore.volumes` | `detail` |
| `detail` 章节施工图 | `DetailArtifact` | 每章章名、字符预算、目的、场景转折和跨章交接是否均衡 | `ArtifactStore.detail` | `text`、`cover` |
| `text` 正文 | `ChapterArtifact`（按章版本） | 接受、人工编辑、定向修订或保留分支 | `ChapterStore`，证据后进入 Outbox | 下一章、`cover`、`export` |
| `cover` 封面 | `CoverArtifact` | 视觉 brief 和最终资产 | `ArtifactStore.cover`、AssetStore | `export` |
| `export` 导出 | `ExportArtifact` | 格式、章节版本、封面和元数据 | `ExportStore` | 无 |

每个阶段只有一个用户可编辑或批准的 Artifact。候选、审稿、预算、调用收据、checkpoint、Evidence、SSE 和写回状态不是 Artifact 字段。

## Artifact 分层

### 核心 Artifact

- `StoryBriefArtifact`：`title`、`premise`、`promise`、`world_rules`、`theme`、`ending_promise`、`voice`、`length_envelope`。
- `StorySpineArtifact`：确定性 `turn-N`、每个 turn 的 `cause/change`、`ending`、有限 `open_questions` 和 `progress_types`。
- `CharacterBibleArtifact`：预分配稳定 subject id；每个主体只保存 `name/kind/function/drive/change/debut/limits/demand_refs`，关系只引用冻结 id。`historical_record` 不得承担 POV 或产生当下行动。
- `VolumeArchitectureArtifact`：确定性 `volume-N`、2-12 字唯一卷名、`promise/conflict/climax/closure`、连续 `turn_refs`、`cast_ids/thread_ids` 和粗粒度 `length_hint`；精确章数由确定性 Scale 投影按卷负载冻结。
- `DetailArtifact`：连续 `chapter-N`、卷引用、2-12 字唯一章名、代码冻结的逐章目标字符数、`purpose`、POV id、2-4 个 `scenes { place/objective/conflict/turn/result }` 和 handoff；相邻章场景数最多相差 1。
- `ChapterArtifact`：章节 id、运行时分配的版本 id、从 Detail 原样继承的只读章名、正文和 `author_status`。正文 Provider 只返回纯文本流；版本身份、标题和状态由 LangGraph 确定性绑定。
- `CoverArtifact`：可执行 `brief` 和已选择资产 id；资产 URL、尺寸和生成收据属于 sidecar。
- `ExportArtifact`：格式、已接受章节版本 id、封面资产 id 和导出元数据。

### 确定性投影

关系图、人物压力、章节 cast、卷卡、节奏条、章节号、卷归属、交接链、引用集合、签名、ScaleProfile、Artifact 表单摘要和前端导航均由核心 Artifact 或领域账本派生，可删除后重建。投影不得反写核心 Artifact。

### 运行时 sidecar

`NarrativeRunState` 只保存 routing：`run_id`、阶段状态、Artifact ref、章节版本 ref、当前节点、decision ref、operation ref、失败证据 ref 和状态 revision。Provider receipt、token/cost、review lane、checkpoint id、interrupt、Evidence、Outbox 事务和 SSE 序列存放在各自的领域存储。

### 窄调用 / 工具结果

标题候选、因果缺口、人物弧检查、连续性检查、章节 Evidence、封面资产生成等只服务一个节点，必须带输入签名和证据 ref，不能扩充主 Artifact，不能直接写 Canon/Wiki。

### 删除字段

删除 `schema_version`、版本转换器、`new_characters`、自由文本人物/关系快照、`wiki_candidates`、`fact_reveals`、`foreshadow_actions`、自评分、UI 坐标、重复 synopsis/act/key-turn 字段、模型自动修复字段和所有 fallback 字段。正文后事实、Wiki、Canon 与伏笔变化都从正文 Evidence 生成提案。

## 人物编排边界

`cast` 是正文前唯一具名主体注册表。`volumes`、`detail`、`text` 只能引用冻结主体 id。新增主体、职责升级、关系重定向或首次出现窗口变化必须生成带触发证据和影响 Artifact 的 `CharacterChangeProposal`，由 LangGraph `interrupt()` 等待明确批准后创建新版本；不得在下游阶段临时补登记、转换旧槽位或用 alias 修复引用。

主角和重要配角必须冻结完整档案；功能角色必须冻结剧情职责；必要功能主体与历史主体必须在正文前冻结稳定名称、类型、用途、窗口和至少一条限制，不能升级职责。Fast 模式也必须在正文前产生版本和决策回执。

## Memory、Wiki、Canon、RAG

- 用户上传知识库是前置 `brief` 的 Source Pack。RAG 只在 `brief/spine/volumes` 前置规划读取，结果带来源、签名和采用状态；正文节点禁止盲检索。
- Worldbuilding 是创作设定；Character Graph 是角色与关系投影；Wiki 是正文 Evidence 驱动的事实账本；Canon 是用户批准后的事实权威；它们不能互相代替。
- Evidence 先生成 proposal，用户或明确的写回节点批准后才进入 Canon/Wiki；Retrieval、proposal agent 和模型自评分没有写权限。
- 全书字符目标按去除空白后的字符数确定性均分到冻结章数，各章目标最多相差 1 字。正文容差为极速 ±15%、平衡 ±12%、精细 ±8%；超界时完整定向重写，最多 3 次，不截断正文，也不允许改动冻结章名、场景转折或交接。

## LangGraph、LangChain 和 Provider

LangGraph Graph API 是唯一生产运行时：一个 thread、一个持久 checkpointer、一个 `interrupt()`/`Command(resume=...)` 决策路径、一个事件投影和一个写回 Outbox。相邻章节顺序生成；同一冻结版本的审稿角色可用 `Send` 并行读取。

生产源码默认禁止直接使用 LangChain API：`pyproject.toml` 不直接依赖 `langchain*`，`src/` 不导入 `langchain`。LangGraph 传递安装的 `langchain-core` 只视为框架内部依赖，不成为 Yotsuba Ink 的模型、工具、Prompt、memory、structured output 或 Agent authority。若未来出现直接 LangGraph 子图与现有领域端口都无法覆盖的真实需求，必须先通过独立 RFC、源码 spike 和删除矩阵评审，不能在窄节点中顺手引入。

每个生产节点使用 Run 创建时冻结的 `ProviderBinding`（provider、model、temperature、max tokens、top-p、timeout、prompt、idempotency key）。没有隐式默认、Provider fallback、Reviewer fallback、schema alias、converter 或 legacy execution switch。Provider 失败进入 Graph failure/interrupt，由用户决定重试或取消。

Provider 结构化响应去除首尾空白后必须是一个完整 JSON object，只允许一次标准 JSON 解析；Markdown fence、解释文本、对象截取、语法 repair、字段 alias/converter、默认值注入和未知字段丢弃全部禁止。所有核心键必须显式出现，允许为空时返回空字符串或空数组。Cast dossier、关系、卷边界、卷合同和 Detail 只按调用前冻结的容量/叙事边界拆分，单元结果经 operation receipt、冻结目标和引用校验后才确定性聚合；部分结果不得写成候选 Artifact。正文是单章纯文本流，不包 JSON；Export 不调用 Provider。

审稿结果同样是严格 sidecar 合同。每个 finding 必须含当前章节正文中的非空精确 `evidence` 和显式 `subject_ids`；人物审稿只可引用冻结主体 id。运行时向人物审稿确定性投影当前章必需、当前可用和未来尚不可用的主体集合。未来窗口主体缺席不构成 finding；只有精确正文证据证明提前出现时才允许阻断。无效证据或未知主体使该 review receipt 失败并投影 `review.unavailable`，不得过滤、降级或自动改文。

## 事件和 UI 投影

SSE 只投影稳定领域事件：`run.started/completed/failed`、`node.started/completed/failed`、`artifact.candidate_ready/committed`、`decision.required/resolved`、`review.started/completed/unavailable`、`evidence.proposed`、`writeback.queued/committed/failed`、`checkpoint.saved` 和 `branch.created`。事件 envelope 只有 event/run/thread/sequence/type/stage/node/chapter/status/payload ref/checkpoint ref；前端不得消费原始 Graph State。

前端路由使用上述八个 stage id；阶段表单只编辑当前核心 Artifact；人物工作台读取 `CharacterBibleArtifact` 与其 change proposal，3D 星图、关系邻域、出场时间线和档案面板共同覆盖正式角色与功能/历史主体；运行观察显示当前 node、并行 review、预算、checkpoint 和失败 evidence；写回状态只读取 `review.*`、`evidence.*`、`writeback.*` 事件。保存草稿不等于正式写回。

## 合同门

每个迁移 Wave 必须同时证明新路径并删除旧路径：

1. fake Provider 全图可重放；结构化输出、Artifact ref、decision、interrupt、checkpoint、SSE 和 Outbox 幂等测试通过。
2. 静态扫描无 legacy/shadow/dual runtime、Detail v1/v2/v3、fallback、alias、converter 或旧 stage id 生产引用。
3. projection 可删除重建；断线重连不影响执行；同一 operation/decision/writeback 恰好一次。
4. 全量离线测试和前端构建通过后，才可在用户批准、限额和脱敏收据下进行新的真实 Provider Run。真实输出、文学连续性、成本和作者冷读另行验收。
5. Character reviewer 的未来窗口误报必须因缺少章节内精确证据而成为不可用 receipt；真实提前出现、有效 prose 硬边界和硬容量 finding 仍可阻断；正文必须通过当前质量档位的字符数合同，三次完整重写仍超界时 Run 明确失败。

## 2026-08-11 真实三章合同证据

- Run `phase26-deepseek-submission-7c66d1a6-8` 接受 `chapter-1-v3-accepted`（1811）、`chapter-2-edit-bc817e88a1aef999-accepted`（1666）和 `chapter-3-edit-a6d3d5e69adc147d-accepted`（1809）；后两章为人工编辑候选，均通过同一 author decision 提交。
- 46 条 Provider operation 为 42 成功、4 失败、0 pending，合计 271,120 tokens；10 条人工 decision 单独记账，不伪装成 Provider 调用。
- 第 3 章只由 Provider 选择 `span_ids`，代码将 8 条 claim 绑定到已接受正文；Outbox、Canon、Wiki 使用同一 transaction 且各提交一次。第 1、2 章旧 quote mismatch 不重试、不转换、不写回。
- 文本阶段完成后 CoverBrief 文本成功；真实图片 Provider 未配置也未调用，fake binding 失败使 Run 停在 `cover.generate_candidate`，Export 未运行。
- 冷读判定仅为“连贯的三章短篇接受样本”：第 1 章略有公式化表达，第 2 章信息压缩，第 3 章的证据驱动主题收束最强但经过人工编辑。不能据此声称模型独立投稿质量、8-12 章单卷或全书验收完成。

## 2026-08-12 新合同验收边界

- `phase26-deepseek-three-gate-dcf5623f-2` 已取消，只保留为人物注册与审稿误报的失败证据；不得恢复、改写或把其中 Artifact/checkpoint/Evidence 复制到下一次验收。
- 新代码把具名历史主体纳入正文前冻结注册表，并要求审稿 finding 绑定当前章节精确证据与冻结主体 id。相关结果目前只属于离线合同证据，不能回填旧 Run 的成功结论。
- 下一次真实三章门禁必须创建完全全新的 Run，从 `brief` 开始，并让三章全部走新 Evidence、review 和 exactly-once Canon/Wiki 写回。通过人工冷读后才允许创建新的 8-12 章单卷 Run。
- GitHub 只在重构、离线门、浏览器矩阵、全新三章和单卷验收全部结束并完成提交范围审查后推送一次；Gitee 不参与该发布路径。
