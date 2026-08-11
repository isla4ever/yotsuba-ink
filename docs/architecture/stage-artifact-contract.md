# Yotsuba Ink vNext Stage Artifact Contract

状态：Phase 26 已批准并完成 Wave 26.1-26.6 离线闭环的唯一生产合同（2026-08-11）。旧七阶段、`info_recommend`、`detail_outline`、`chapter_text`、`cover_image`、`export_artifact` 和 Detail v1/v2/v3 已断代；历史版本只允许在离线归档查看器中作为失败证据读取。本地桌面/390px 浏览器矩阵已通过；两次智谱 `info` 探针的额度失败保留为历史证据，随后用户明确批准的 `provider-deepseek-text / deepseek-v4-pro` 已通过 `info` 和 `characters` 严格探针，其中 `characters` 使用生产预算 `max_tokens=4200`，当前停在 `characters` 人工决策 checkpoint。一次早期验收脚本的 `max_tokens=1800` 截断失败只作为运行配置边界证据，没有改动生产模板；成功 Run 的 `info` 使用此前已验证的验收预算 `3480`，不是生产默认值 `4600`；`summary` 至 `cover`、三章 Run 与人工文学验收仍未开始。

## 生产阶段

配置页不是运行阶段。LangGraph 只编译并执行下面这一条图：

```text
info -> characters -> summary -> outline -> detail -> text -> cover -> export
```

| 阶段 | 唯一核心 Artifact | 用户决策 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `info` 创作立项 | `StoryBriefArtifact` | 题材承诺、世界前提、主题问题、结局承诺、叙事声音 | `ArtifactStore.info` | `characters`、`summary` |
| `characters` 人物编排 | `CharacterBibleArtifact` | 主角、重要配角、功能角色、NPC 槽位的职责、关系、弧线、首次出现窗口 | `ArtifactStore.characters` | `summary`、`outline`、`detail`、`text` |
| `summary` 全书梗概 | `SummaryArtifact` | 因果链、高潮、结局和人物结局是否成立 | `ArtifactStore.summary` | `outline` |
| `outline` 分卷大纲 | `OutlineArtifact` | 各卷目标、转折、人物窗口、线程窗口和章节范围 | `ArtifactStore.outline` | `detail` |
| `detail` 章节施工图 | `DetailArtifact` | 每章目的、场景转折、义务和跨章交接 | `ArtifactStore.detail` | `text`、`cover` |
| `text` 正文 | `ChapterArtifact`（按章版本） | 接受、人工编辑、定向修订或保留分支 | `ChapterStore`，证据后进入 Outbox | 下一章、`cover`、`export` |
| `cover` 封面 | `CoverArtifact` | 视觉 brief 和最终资产 | `ArtifactStore.cover`、AssetStore | `export` |
| `export` 导出 | `ExportArtifact` | 格式、章节版本、封面和元数据 | `ExportStore` | 无 |

每个阶段只有一个用户可编辑或批准的 Artifact。候选、审稿、预算、调用收据、checkpoint、Evidence、SSE 和写回状态不是 Artifact 字段。

## Artifact 分层

### 核心 Artifact

- `StoryBriefArtifact`：`title`、`premise`、`story_promise`、`world_rules`、`thematic_question`、`ending_promise`、`voice`、`cast_requirements`。
- `CharacterBibleArtifact`：稳定 `character.id`、`tier`、`narrative_function`、目标、内在需求、三点弧线、首次出现窗口、硬边界；关系只引用已注册 id；NPC 只能是冻结槽位。
- `SummaryArtifact`：稳定 `beats[]`（事件和后果）、`climax`、`resolution`、`character_outcomes[]`。
- `OutlineArtifact`：连续卷窗口、`objective`、因果 `turns[]`、`ending_state`、人物窗口和线程窗口。
- `DetailArtifact`：连续章节 `id/number`、`purpose`、POV id、场景（地点、目标、障碍、转折、结果）、义务和 handoff。
- `ChapterArtifact`：章节 id、版本 id、标题、正文和 `author_status`。生成节点只可返回 `candidate`。
- `CoverArtifact`：可执行 `brief` 和已选择资产 id；资产 URL、尺寸和生成收据属于 sidecar。
- `ExportArtifact`：格式、已接受章节版本 id、封面资产 id 和导出元数据。

### 确定性投影

关系图、章节 cast、卷卡、节奏条、章节号、卷归属、交接链、引用集合、签名、字数软目标、Artifact 表单摘要和前端导航均由核心 Artifact、`BookScalePlan` 或领域账本派生，可删除后重建。投影不得反写核心 Artifact。

### 运行时 sidecar

`NarrativeRunState` 只保存 routing：`run_id`、阶段状态、Artifact ref、章节版本 ref、当前节点、decision ref、operation ref、失败证据 ref 和状态 revision。Provider receipt、token/cost、review lane、checkpoint id、interrupt、Evidence、Outbox 事务和 SSE 序列存放在各自的领域存储。

### 窄调用 / 工具结果

标题候选、因果缺口、人物弧检查、连续性检查、章节 Evidence、封面资产生成等只服务一个节点，必须带输入签名和证据 ref，不能扩充主 Artifact，不能直接写 Canon/Wiki。

### 删除字段

删除 `schema_version`、版本转换器、`new_characters`、自由文本人物/关系快照、`wiki_candidates`、`fact_reveals`、`foreshadow_actions`、自评分、UI 坐标、重复 synopsis/act/key-turn 字段、模型自动修复字段和所有 fallback 字段。正文后事实、Wiki、Canon 与伏笔变化都从正文 Evidence 生成提案。

## 人物编排边界

`characters` 是正文前唯一角色注册表。`outline`、`detail`、`text` 只能引用稳定 `character_id`。新增角色、职责升级、关系重定向或首次出现窗口变化必须生成带触发证据和影响 Artifact 的 `CharacterChangeProposal`，由 LangGraph `interrupt()` 等待明确批准后创建新版本；拼写和展示名变化属于确定性投影，不是语义变更。

主角和重要配角必须冻结完整档案；功能角色必须冻结剧情职责；必要 NPC 只能冻结用途、窗口和限制，允许在施工图中命名但不能升级职责。Fast 模式也必须在正文前产生版本和决策回执。

## Memory、Wiki、Canon、RAG

- 用户上传知识库是前置 `info` 的 Source Pack。RAG 只在立项/规划阶段读取，结果带来源、签名和采用状态；正文节点禁止盲检索。
- Worldbuilding 是创作设定；Character Graph 是角色与关系投影；Wiki 是正文 Evidence 驱动的事实账本；Canon 是用户批准后的事实权威；它们不能互相代替。
- Evidence 先生成 proposal，用户或明确的写回节点批准后才进入 Canon/Wiki；Retrieval、proposal agent 和模型自评分没有写权限。
- 字数只有软目标和合理容错。超出目标只生成诊断，不自动删改正文；硬门只检查合同、引用、状态和安全容量。

## LangGraph、LangChain 和 Provider

LangGraph Graph API 是唯一生产运行时：一个 thread、一个持久 checkpointer、一个 `interrupt()`/`Command(resume=...)` 决策路径、一个事件投影和一个写回 Outbox。相邻章节顺序生成；同一冻结版本的审稿角色可用 `Send` 并行读取。

生产源码默认禁止直接使用 LangChain API：`pyproject.toml` 不直接依赖 `langchain*`，`src/` 不导入 `langchain`。LangGraph 传递安装的 `langchain-core` 只视为框架内部依赖，不成为 Yotsuba Ink 的模型、工具、Prompt、memory、structured output 或 Agent authority。若未来出现直接 LangGraph 子图与现有领域端口都无法覆盖的真实需求，必须先通过独立 RFC、源码 spike 和删除矩阵评审，不能在窄节点中顺手引入。

每个生产节点使用 Run 创建时冻结的 `ProviderBinding`（provider、model、temperature、max tokens、top-p、timeout、prompt、idempotency key）。没有隐式默认、Provider fallback、Reviewer fallback、schema alias、converter 或 legacy execution switch。Provider 失败进入 Graph failure/interrupt，由用户决定重试或取消。

Provider 结构化响应去除首尾空白后必须是一个完整 JSON object，只允许一次标准 JSON 解析；Markdown fence、解释文本、对象截取、语法 repair、字段 alias/converter、默认值注入和未知字段丢弃全部禁止。所有核心键必须显式出现，允许为空时返回空字符串或空数组。Outline 多卷按卷调用，Detail 每批最多 8 章，单元结果经 operation receipt、冻结目标和引用校验后才确定性聚合；部分结果不得写成候选 Artifact。Export 不调用 Provider，Fast 自动接受，Balanced/Deep 只允许确认或取消。

## 事件和 UI 投影

SSE 只投影稳定领域事件：`run.started/completed/failed`、`node.started/completed/failed`、`artifact.candidate_ready/committed`、`decision.required/resolved`、`review.started/completed/unavailable`、`evidence.proposed`、`writeback.queued/committed/failed`、`checkpoint.saved` 和 `branch.created`。事件 envelope 只有 event/run/thread/sequence/type/stage/node/chapter/status/payload ref/checkpoint ref；前端不得消费原始 Graph State。

前端路由使用上述八个 stage id；阶段表单只编辑当前核心 Artifact；人物工作台读取 `CharacterBibleArtifact` 与其 change proposal；运行观察显示当前 node、并行 review、预算、checkpoint 和失败 evidence；写回状态只读取 `review.*`、`evidence.*`、`writeback.*` 事件。保存草稿不等于正式写回。

## 合同门

每个迁移 Wave 必须同时证明新路径并删除旧路径：

1. fake Provider 全图可重放；结构化输出、Artifact ref、decision、interrupt、checkpoint、SSE 和 Outbox 幂等测试通过。
2. 静态扫描无 legacy/shadow/dual runtime、Detail v1/v2/v3、fallback、alias、converter 或旧 stage id 生产引用。
3. projection 可删除重建；断线重连不影响执行；同一 operation/decision/writeback 恰好一次。
4. 全量离线测试和前端构建通过后，才可在用户批准、限额和脱敏收据下进行新的真实 Provider Run。真实输出、文学连续性、成本和作者冷读另行验收。
