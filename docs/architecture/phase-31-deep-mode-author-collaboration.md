# Phase 31：精细模式作者协作台

状态：Wave 31.1-31.7 已在 Version 20 唯一生产前端完成离线合同、fake Provider、前端与浏览器验收；Wave 31.8 真实 Provider 调用仍需按本 Phase 的独立成本门执行，历史 Run 不恢复

日期：2026-08-21

上游权威：

- `docs/architecture/stage-artifact-contract.md`
- `docs/architecture/phase-29-v1.1-million-character-author-led-deep-mode.md`
- `docs/architecture/phase-30-figma-ui-production-migration.md`

## 1. 执行摘要

### 1.1 用户真正需要解决的问题

精细模式目前能生成候选、换一稿和接受人工编辑，但专业作者缺少一个能围绕当前作品事实持续讨论、逐步澄清意图、提出局部方案并安全写回的 AI 协作面。用户不应为了润色一个段落或重构一个人物动机，反复把正文、人物、世界规则和伏笔复制到外部网页模型；系统也不应把每次修改都退化成整稿重生成。

本 Phase 将新增“作者协作台”，但不增加第九个创作阶段，也不建立第二套 Agent runtime。它是 `spine/cast/volumes/detail/text` 五个阶段内的协作 sidecar：只读权威上下文，持久化对话和调用回执，必要时产出绑定源版本的变更候选，并通过现有 Artifact draft、Phase 29 amendment 或 Chapter branch 边界正式写回。

### 1.2 产品评审结论

用户提出的方向正确，但以下四点不能按字面直接实现：

1. 不能“每阶段永久只有一条无限对话”。长篇项目会让线程上下文无限增长并混入旧版本事实。正确做法是每阶段可建多线程，线程绑定 `stage + artifact version + unit/window`，历史可检索，默认恢复当前作用域的最近线程。
2. 不能让“直接改动”绕过审阅。产品界面可以叫“改稿”，但后端只能生成可审阅 patch candidate；用户确认后才进入 draft、amendment 或 chapter branch。
3. 不能用模糊的“记忆全开”开关。每项上下文必须显示来源、作用域、版本/签名、采用原因和预计字符/token，且不得把完整 Canon、Wiki、人物库或全书对话塞给模型。
4. 不能因为附件用了 `styled-components` 就引入新的样式体系。附件只作为输入框的玻璃层级、底部工具区和发送按钮参考；生产实现继续使用当前 React、CSS token、Lucide 与 `motion` 边界。

### 1.3 最终产品决定

- 功能暂时只对 `quality_mode=deep` 的全新可执行 Run 开放。
- 首批接入 `spine`、`cast`、`volumes`、`detail`、`text`。
- 不接入 `brief`：Brief 是短而强约束的立项合同与硬确认门，首版保留结构化编辑，避免在立项阶段混淆承诺与讨论草稿。
- 不接入 `cover/export`：封面资产和交付清单不是多轮文学协作的高价值场景。
- 对话提供 `讨论`、`方案`、`改稿` 三种模式，而不是只有“聊天/自动改”二选一。
- 作者协作面板位于右侧；打开时收起全局产品主导航，但保留 Spine turn、Cast 名册、Volumes 卷册、Detail 章节、Text 章节等阶段二级导航。
- 首次发送前显示完整上下文回执；第二次发送前显示一次轻提示；之后保持可展开的常驻摘要。上下文来源或 Artifact 版本发生实质变化时必须重新确认。
- 对话永远没有 Canon、Wiki、Memory、Evidence 或 committed Artifact 的直接写权限。

## 2. 当前权威与根因

### 2.1 当前单一生产路径

```text
brief -> spine -> cast -> volumes -> detail -> text -> cover -> export
```

作者协作台不是这条链路中的新阶段。它只能附着在当前 Run 和当前阶段 Artifact 上，不拥有阶段推进、Run 状态或下游事实。

### 2.2 当前事实图

| 概念 | 当前写入者 | 当前读取者 | 持久化/恢复 | 当前缺口 |
| --- | --- | --- | --- | --- |
| 阶段候选 | `StageExecutor` / Provider | 阶段决策与 UI | `ArtifactStore` | 只支持单轮候选，不支持对话提案 |
| 待决策编辑 | `save_stage_artifact_draft()` | 当前 interrupt 与 UI | `StageArtifactDraftStore` | 严格绑定 pending decision，不能修改 committed Artifact |
| 已提交规划 | Artifact commit | 下游 Context 与 UI | `ArtifactStore`；Phase 29 迁移到聚合 Store | Phase 29.2 amendment 尚未落地，不能原地覆盖 |
| 正文版本 | Text 子图、人工编辑 | 审稿、Evidence、Export | `ChapterStore` | 修改必须成为新候选/分支，不能覆盖 accepted version |
| 章节上下文 | `ContextCompiler` | 正文 Provider、诊断 UI | `ContextManifestStore` | 当前 `ContextManifest.task` 只允许 `chapter-N`，不能冒充通用聊天上下文 |
| Provider 请求 | Provider input compiler / gateway | Operation 诊断、usage | `ProviderInputStore` + `OperationStore` | 只有阶段/提案/正文/审稿/Evidence/封面请求，没有多轮对话请求 |
| 执行与恢复 | LangGraph | Run read model / SSE | SQLite checkpointer | 没有作者协作子图，但不能另建第二套 runtime |
| Evidence | Evidence 提取节点 | Outbox、Story Bible | `EvidenceStore` | 模型对话不能伪造 Evidence |
| Canon/Wiki | Outbox 事务 | Context、Story Bible | `CanonStore` / Wiki projection | 只能由已接受正文 Evidence 写回 |
| 本书知识库 | 上传/索引接口 | Brief/规划 Context | Knowledge store | 只能选取有界 Source Pack，不能默认全量注入 |
| 设置 | `SettingsPage` + Provider API | Planning/Run 创建 | Workflow/Provider stores | 没有作者协作 Provider、默认上下文和保留策略 |

### 2.3 根因判断

缺的不是一个聊天气泡组件，而是五个底层合同：

1. 缺少与 Artifact 版本和局部 unit 精确绑定的对话线程身份。
2. 缺少可追溯、可预算、可重新确认的交互式上下文回执。
3. 缺少 selection-bound、source-bound、可预览的 patch candidate。
4. 缺少同一 LangGraph/checkpointer 内的多轮协作子图与幂等 Provider operation。
5. 缺少对话历史、流式状态、取消、失败和恢复的真实读模型。

如果只加前端聊天框，最终会产生“UI 有历史、后端无权威；模型看似改了、Artifact 实际没改；上下文开关很多、来源无法追溯”的第二套假系统。

### 2.4 Phase 29 依赖

- `讨论` 和 `方案` 可以在 committed Artifact 上只读运行。
- `改稿`若目标是当前 pending candidate，可复用 `StageArtifactDraftStore`。
- `改稿`若目标是 committed Spine/Cast/Volumes/Detail，必须等待 Phase 29.2 `ArtifactAmendment` 与 Dependency Index 退出门。
- Cast 的新增/删除主体、关系重定向和作用域改变必须等待 Phase 29.3 的作者权威合同；Phase 31 不用聊天 patch 绕过该门。
- accepted Text 只能创建新 chapter candidate/branch，不能修改旧版本。

## 3. 外部方案调研与取舍

调研方式：2026-08-21 使用 GitHub 官方仓库、GitHub API 和 npm registry 核对；stars 仅为当日快照，不作为架构正确性的证明。

| 项目 | 当日证据 | 许可证 | 可复用能力 | Phase 31 决定 |
| --- | --- | --- | --- | --- |
| [assistant-ui](https://github.com/assistant-ui/assistant-ui) | 11,751 stars；HEAD [`08611a0`](https://github.com/assistant-ui/assistant-ui/commit/08611a01b9026d44251b401ef8ea461cc4da4d6d)；`@assistant-ui/react 0.15.16`；React 18/19 | MIT | Thread、Message、Composer、ThreadList、ActionBar、流式/附件/可访问性原语；支持 custom runtime | **采用 `@assistant-ui/react` 前端原语**；只写 Yotsuba custom runtime，不接 Assistant Cloud、Vercel adapter 或 LangGraph JS SDK |
| [Vercel AI SDK](https://github.com/vercel/ai) | 26,323 stars；HEAD [`016b944`](https://github.com/vercel/ai/commit/016b944a7b935272d6e322c988cfb88acb24ff5f)；`@ai-sdk/react 4.0.74` | Apache-2.0 | Provider 抽象、chat hooks、tool UI、stream | 不采用；会在浏览器/TypeScript 侧形成第二套 Provider 和 agent loop，绕过 Python LangGraph 与 Operation receipt |
| [CopilotKit](https://github.com/CopilotKit/CopilotKit) | 36,906 stars；HEAD [`09cd6a8`](https://github.com/CopilotKit/CopilotKit/commit/09cd6a85e5355bd5076f04d68db9a60939b2e1ca)；v1.68.3 | MIT | AG-UI、shared state、HITL、Generative UI | 不采用 runtime/protocol；现有 SSE、interrupt、read model 已拥有同一职责，接入会产生双权威 |
| [LobeHub](https://github.com/lobehub/lobehub) | 81,857 stars；HEAD [`66227ba`](https://github.com/lobehub/lobehub/commit/66227ba5022c399d254cbb43692d7bb87927fdeb)；v2.2.14 | LobeHub Community License，商业派生需单独许可 | 多 Provider、线程组织、白盒记忆、Agent 页面 | 只参考线程历史与白盒记忆交互；不复制代码或 UI |
| [Open WebUI](https://github.com/open-webui/open-webui) | 149,384 stars；默认分支 HEAD [`01f4282`](https://github.com/open-webui/open-webui/commit/01f4282f1ffe0d6212f58d3afbeae21fffd0c4be)；v0.11.0 | 自定义 Open WebUI License，含品牌限制 | Notes 选区改写、知识库、模型连接、持久记忆 | 只参考 Notes 的“选区 -> 改写 -> 预览”产品模式；不复制代码 |
| [Chatbot UI](https://github.com/mckaywrigley/chatbot-ui) | 33,342 stars；HEAD [`81328b6`](https://github.com/mckaywrigley/chatbot-ui/commit/81328b61d2a4ab597a7a057be70e785cf756d9f8)，最后代码提交为 2024-06 | MIT | 完整聊天应用和历史 | 不采用；活跃度与整站 Supabase/Next 架构不符合当前边界 |
| [Tiptap](https://github.com/ueberdosis/tiptap) | 38,101 stars；HEAD [`f434577`](https://github.com/ueberdosis/tiptap/commit/f434577e6bb2010b321653cb132a57bda18764fa)；v3.30.2 | MIT | Headless editor、ProseMirror selection、扩展 | 本 Phase 不引入；先为现有 textarea/表单建立统一 SelectionAnchor，富文本迁移另立 Phase |
| [BlockNote](https://github.com/TypeCellOS/BlockNote) | 10,098 stars；HEAD [`b2175c6`](https://github.com/TypeCellOS/BlockNote/commit/b2175c6d0108c1be736deab84f23bdfd3c7acc3c)；v0.54.0 | 核心 MPL-2.0，XL 为 GPL-3.0/商业许可 | Block editor、协作、拖拽 | 不采用；块模型、23MB 级未压缩包和混合许可证会扩大正文编辑器范围 |

结论：首版只引入一个新前端依赖 `@assistant-ui/react`。它负责成熟的对话交互原语，不拥有线程数据、Provider 调用、LangGraph 状态、上下文选择或 Artifact 写回。若实现 spike 证明 custom runtime 无法满足现有 SSE/receipt 语义，则退回本地无头组件实现，而不是引入另一套后端协议。

## 4. 目标权威图

```mermaid
flowchart LR
    selection[阶段编辑器选区] --> anchor[SelectionAnchor]
    artifact[当前 Artifact/Chapter 版本] --> compiler[Collaboration Context Compiler]
    sources[Cast / Volume / Detail / Resolved State / Wiki / Source Pack] --> compiler
    policy[用户确认的 Context Policy] --> compiler
    compiler --> receipt[不可变 Turn Context Receipt]
    receipt --> graph[同一 LangGraph 作者协作子图]
    history[Conversation Store] --> graph
    graph --> provider[冻结 Provider Binding]
    provider --> response[Assistant Message / Plan / Patch Candidate]
    response --> review{作者确认变更?}
    review -->|否| history
    review -->|pending candidate| draft[StageArtifactDraftStore]
    review -->|committed planning| amendment[ArtifactAmendment]
    review -->|chapter| branch[Chapter Candidate / Branch]
    draft --> artifact
    amendment --> artifact
    branch --> artifact
```

### 4.1 权威边界

| 概念 | 唯一作者 | 说明 |
| --- | --- | --- |
| 对话线程/消息 | `CollaborationStore` | 对话历史不是 Artifact、Memory 或 Canon |
| 每轮上下文 | `CollaborationContextCompiler` + immutable receipt | 客户端只提交选择意图，不能提交伪造的 Canon/Wiki 文本 |
| Provider 调用 | 同一 `FrozenNarrativeProviderGateway` | 新增协作请求类型，但不增加 provider fallback 或浏览器直连 |
| 协作控制流 | 同一 LangGraph runtime/checkpointer | 使用独立 thread namespace，不增加 runtime selector |
| 变更候选 | `ArtifactPatchCandidateStore` | 只保存 proposal；没有事实权威 |
| 正式规划写回 | 当前 draft 或 Phase 29 amendment | 必须保留 source version 与影响分析 |
| 正文写回 | `ChapterStore` 新候选/分支 | accepted version 不可变 |
| Canon/Wiki/Memory | 现有 Evidence/Outbox 边界 | 协作对话无写权限 |

## 5. 核心合同

### 5.1 `CollaborationThread`

```text
thread_id
run_id
project_id
stage_id: spine | cast | volumes | detail | text
scope:
  artifact_ref / chapter_version_id
  unit_ref: part / turn / subject / relation / volume / detail-window / chapter
title
provider_binding_ref
context_policy_ref
status: active | archived | deleted
created_at / updated_at
```

规则：

- 一个阶段可以有多条线程；“新对话”不是清空旧历史。
- 线程首次创建时冻结 Provider binding。修改全局默认只影响新线程；已有线程可显式“以新模型分叉”，不能静默换模型。
- Artifact 或 Chapter 版本变化后，旧线程仍可只读查看；继续发送前必须显式 rebase/fork 到新版本。
- 删除线程只删除协作历史与 sidecar，不删除 Artifact、Provider receipt 或已应用 amendment 的审计记录。

### 5.2 阶段作用域

| 阶段 | 默认线程作用域 | 允许讨论 | 改稿可写字段 | 禁止直接写 |
| --- | --- | --- | --- | --- |
| Spine | 当前 Part / turn；短篇可为全 Spine | 因果、转折、结局、开放问题 | `cause/change/ending/open_questions` 文本 | id、milestone、顺序、progress 数量、Part/turn 结构 |
| Cast | 当前 subject / relation | 动机、背景、声纹、关系压力、人物弧 | 既有主体文学字段、既有关系 `type/pressure` | subject id、kind、debut scope、增删主体、关系端点 |
| Volumes | 当前 Part / volume | 卷界、承诺、冲突、高潮、收束 | `title/promise/conflict/climax/closure/length_hint` | volume id、turn refs、cast ids、卷数与顺序 |
| Detail | 当前 Detail Window / chapter / scene | 场景目的、冲突、转折、handoff、连续性 | `purpose`、scene 文本字段、`handoff` | chapter/volume ref、turn refs、预算、场景身份与章节结构 |
| Text | 当前 chapter version / selection | 语气、节奏、信息密度、局部重写 | `content` 中精确选区替换 | title、chapter id、version id、author status、跨章结构 |

结构新增、删除、重排和引用改变可以在 `方案` 模式提出，但必须跳转到对应结构编辑器或 Phase 29 amendment 表单执行，不能伪装成文本 patch。

### 5.3 `SelectionAnchor`

```text
anchor_id
stage_id
source_ref
unit_ref
field_path
field_hash
selection_start
selection_end
selected_text_hash
selected_char_count
preview
created_at
```

- `preview` 只保留前后有限字符，Composer 显示为 `“主角拒绝签字……” · 正文选区 · 428 字`。
- 完整选区保存在本地 draft 和服务端受控 turn input 中，不复制进消息正文。
- 应用 patch 时必须同时匹配 `source_ref + field_path + field_hash + selected_text_hash + offsets`。
- 任一值漂移就返回 `selection_stale`，不做模糊匹配、正则猜测或自动 rebase。
- 结构输入、textarea 和正文 textarea 使用同一合同；本 Phase 不要求更换编辑器。

### 5.4 对话模式

| 模式 | Provider 输出 | 是否可写回 | UI 结果 |
| --- | --- | --- | --- |
| `讨论` | 自然语言分析、追问、建议 | 否 | 普通 assistant message，可引用来源 |
| `方案` | 目标、问题、步骤、影响范围、风险、待确认项 | 否 | 结构化 plan，可继续讨论或转为改稿 |
| `改稿` | 解释 + `ArtifactPatchCandidate` | 仅确认后 | before/after diff、影响提示、接受/放弃/继续讨论 |

默认模式为 `讨论`。用户在一条线程中切换模式不会改变历史，但每个 turn 都记录实际 mode。系统永远不提供“自动接受所有改动”。

### 5.5 `ArtifactPatchCandidate`

```text
patch_id
thread_id / turn_id
stage_id
source_ref
source_signature
unit_ref
operations[]:
  field_path
  before_hash
  selection_anchor_id?
  replacement
  rationale
context_receipt_ref
provider_operation_ref
status: proposed | accepted | rejected | stale
```

- P0 只允许 `replace_text`，不实现任意 JSON Patch。
- 数组索引不作为长期身份；操作必须先绑定稳定 `unit_ref`，再由代码投影当前 field path。
- Provider 不返回内部 id、hash、status 或版本；代码从冻结 source 确定性绑定。
- 接受前再次执行 Artifact schema、引用、范围、source revision 和阶段业务校验。
- 一个 patch 失败不得退回“整稿覆盖”。

### 5.6 对话历史与摘要

- UI 可浏览完整历史，但 Provider 每轮只读取最近有界 turn、用户显式 pin 的决定和带 message refs 的 rolling summary。
- rolling summary 是模型生成 sidecar，不是作品事实；必须显示来源 turn 范围和摘要签名。
- 用户可删除未应用的线程；已产生并接受 patch 的 turn 保留最小审计引用。
- 对话内容不自动写入作者偏好、项目 Memory、Canon、Wiki 或知识库。

## 6. 上下文选择与回执

### 6.1 来源分类

| 分类 | 实际权威 | 默认策略 |
| --- | --- | --- |
| 当前选区/字段 | 当前 source-bound editor draft | `改稿`必选；讨论可选 |
| 当前 Artifact 局部单元 | Stage Artifact / Chapter version | 必选，只取当前 unit |
| 上游冻结合同 | committed Brief/Spine/Cast/Volumes/Detail | 按阶段确定性选取，不让用户勾选无关全量 |
| 人物与关系 | `CharacterBibleArtifact` 的相关邻域 | 只取 scope 命中的主体和关系 |
| 当前 Part/卷/窗口/章 | Phase 29 aggregate 或现有 Artifact 投影 | 必选当前局部，不取整本 |
| 连续性状态 | `ResolvedStoryState` | Text 默认开启；其它阶段只读摘要 |
| Canon/Wiki | Evidence 驱动投影 | 只读、相关事实、带 evidence refs |
| 伏笔/Promise | Story Bible 的 open-loop/promise 投影 | Detail/Text 默认开启，按当前窗口过滤 |
| 本书知识库 | 用户已选择的 Source Pack | 默认关闭；用户显式选文档/片段 |
| 写作机制 | 版本化 `CraftMechanismPack` | 只包含写作方法/风格约束，不拥有剧情事实 |
| 作者偏好 | 全局/本书 `CollaborationProfile` | 默认开启，内容有界且用户可编辑 |

“Memory、Wiki、Canon、知识库、写作机制”必须在 UI 中分开命名，不能合并成一个“增强记忆”总开关。

### 6.2 `CollaborationContextPolicy`

设置页保存的是默认选择策略，不保存一次具体 Provider 输入：

```text
policy_id / version
stage_defaults
source_pack_defaults
max_input_chars
max_history_turns
include_author_preferences
include_craft_mechanisms
created_at / updated_at
```

每轮实际输入由服务端重新编译。客户端不能把任意文本伪装成 Canon/Wiki/Memory。

### 6.3 `CollaborationTurnContextReceipt`

```text
receipt_id
thread_id / turn_id
source_artifact_ref
sources[]:
  category
  source_ref
  scope_ref
  source_version / hash
  reason
  char_count / token_estimate
required / optional / omitted
history_message_refs
rolling_summary_ref?
budget
receipt_hash
created_at
```

该 receipt 与现有章节 `ContextManifest` 并列但不混用：章节生成继续使用 `ContextManifestStore`；作者协作使用独立 `CollaborationContextReceiptStore`。两者都由同一 Context domain 负责，但合同、任务和生命周期不同。

### 6.4 首次与后续确认

1. 第一次点击发送：服务端先返回 context preview，UI 打开全局居中回执弹窗。
2. 弹窗展示本轮必要来源、可选来源、排除项、预计字符/token 和 Provider/模型；用户确认后才创建 turn。
3. 第二次发送：Composer 上方出现一次轻提示，例如“沿用 7 项上下文 · 约 6.2k tokens”，用户可展开修改。
4. 第三次及以后：保留紧凑 receipt chip，不主动打断。
5. Artifact 版本、scope、Source Pack、Craft Mechanism 或 Provider binding 变化时，旧 preview signature 失效，必须重新弹出完整确认。
6. 预算超限时不静默截断。编译器返回 `context_budget_exceeded` 与建议移除项，由用户或确定性优先级策略重新确认。

## 7. LangGraph 控制面

### 7.1 单一 runtime 决定

新增 `author_collaboration_graph.py`，由现有 `NarrativeRuntime` 创建并复用同一：

- Python LangGraph Graph API；
- SQLite checkpointer；
- `FrozenNarrativeProviderGateway`；
- Provider binding/secret resolver；
- OperationStore、EventProjection 与 API bootstrap。

协作线程使用 `thread_id = <run_id>:collab:<collaboration_thread_id>` 的独立 checkpoint namespace，避免阻塞主叙事图，但不增加 Shadow/Dual runtime、LangChain agent loop、CopilotKit AG-UI 后端或 TypeScript Provider。

### 7.2 最小 State

```text
run_id
collaboration_thread_id
stage_id
scope_ref
source_ref
active_turn_id
mode
user_message_ref
context_receipt_ref
provider_operation_ref
assistant_message_ref
patch_candidate_ref
pending_patch_decision_ref
status_revision
failure_ref
```

State 只保存 routing 和 refs。完整消息、上下文片段、Provider 输入、流式正文和 patch 内容分别进入对应 Store，不进入 checkpoint 大对象。

### 7.3 Node 与 Edge

```mermaid
flowchart TD
    ingest[ingest_user_turn] --> validate[validate_source_binding]
    validate --> context[compile_context_receipt]
    context --> call[call_collaboration_provider]
    call --> persist[persist_assistant_message]
    persist --> route{mode}
    route -->|讨论| done[turn_completed]
    route -->|方案| plan[validate_plan_result]
    plan --> done
    route -->|改稿| patch[validate_patch_candidate]
    patch --> decide[interrupt: patch_decision]
    decide -->|reject| done
    decide -->|accept pending draft| draft[save_stage_draft]
    decide -->|accept committed planning| amend[create_amendment]
    decide -->|accept chapter| branch[create_chapter_candidate]
    draft --> done
    amend --> done
    branch --> done
```

### 7.4 幂等、取消与恢复

- 客户端为每次发送生成 `client_turn_id`；operation key 为 `collab:<thread_id>:<turn_id>:<attempt>`。
- 相同 key + 相同 request signature 重放返回同一 turn；内容不同则 `409 turn_replay_conflict`。
- Provider 调用前持久化 input snapshot 和 `pending` receipt；返回后先记 `provider_returned`，领域校验通过才 `succeeded`，patch 合同失败记 `contract_rejected`。
- “停止生成”必须中断当前 HTTP stream，turn 记 `cancelled`，保留已显示的 partial message 为不可应用草稿；不能把用户取消记成 Provider 成功或合同失败。
- 断线重连通过 thread/turn cursor 读取已持久化 chunk 或最终消息；不能再次调用 Provider。
- retry 创建新 attempt，并显示上一 attempt 的失败/取消记录；不隐藏重试。
- 同一 patch decision 只能接受一次。重复 accept 幂等；source 变化后返回 `patch_stale`。

### 7.5 事件与流

现有 Run SSE 只增加稳定生命周期事件：

```text
collaboration.thread_created
collaboration.turn_started
collaboration.context_frozen
collaboration.turn_completed
collaboration.turn_cancelled
collaboration.turn_failed
collaboration.patch_ready
collaboration.patch_accepted
collaboration.patch_rejected
collaboration.patch_stale
```

Token/chunk delta 不写入全局 Run event JSONL，避免长对话造成事件膨胀。对话使用独立 cursor stream；服务端持久化有界 partial buffer 和最终 message，稳定事件只携带 refs。

## 8. Provider 与设置

### 8.1 Provider 能力

在现有 Provider profile 上增加确定性 capability projection：

```text
supports_multi_turn
supports_streaming
supports_structured_patch
max_context_tokens?
capability_checked_at
capability_source: discovered | tested | manual
```

- 不按厂商名称硬编码能力。
- OpenAI-compatible 服务通过模型发现与一次显式 capability test 得出可用性。
- “各大厂默认开启”解释为：所有通过 multi-turn readiness 的文本 Provider 默认进入可选池；未通过的服务明确不可用，不伪装启用。
- 不允许协作请求静默切换 Provider/model。

### 8.2 全局设置新 Tab

`/studio/settings` 改为两个一级 Tab：

1. `模型与服务`：保留当前 Provider 管理、密钥、默认文本/图片模型与 readiness。
2. `作者协作`：新增以下设置。

作者协作设置：

- 默认 Provider / model，只列通过 multi-turn readiness 的文本服务；
- 默认模式：`讨论`；
- 五阶段默认 Context Policy；
- 默认 Source Pack 采用方式：关闭/每次选择；不提供“全库自动注入”；
- 最大单轮上下文预算、最大历史 turn 数；
- Craft Mechanism Pack 选择与版本；
- 作者偏好编辑；
- 对话历史保留和删除入口；
- capability matrix 与最近检查结果。

不可配置的安全项：

- 改稿必须预览确认；
- patch source binding；
- Canon/Wiki/Memory 无直接写权；
- Provider 无 silent fallback；
- secrets 不进入消息或前端持久化。

本书 `/settings` 只展示当前 Run 冻结的协作 Provider/profile 和“为新线程使用新配置”的入口，不能回写已经开始的线程。

## 9. UI 与交互规格

### 9.1 壳层与互斥关系

桌面宽屏：

```text
阶段二级栏 | 当前 Artifact 编辑区 | 作者协作台 420-480px
```

- 打开作者协作台时，自动关闭 `ProductNavigationRail` 并收起全局 `WorkbenchSidebar` 的产品主导航层。
- Spine 因果 turn、Cast 名册、Volumes 卷、Detail/Text 章节等阶段二级栏继续保留，宽度不变。
- 关闭协作台后恢复用户此前的全局侧栏展开状态。
- `>=1440px` 使用 docked panel；`1024-1439px` 使用右侧 overlay sheet，不压缩主编辑区到不可用宽度；`<768px` 使用全屏 sheet。
- Monitor、Studio、Planning、Brief、Cover、Export 不展示入口。

### 9.2 入口

- 阶段 Header 右侧新增 `Sparkles` 图标按钮，tooltip 为“作者协作”。仅 deep mode 且当前阶段 eligible 时可见。
- 选中文本后，在字段边界显示一次短暂的 `WandSparkles` 上下文按钮；点击后将选区加入 Composer，而不是立即发送。
- 键盘选区同样更新按钮可用状态；移动端通过字段工具栏的“引用选区”入口完成，不依赖 hover。
- committed read-only 内容仍可进入 `讨论/方案`；只有存在合法 draft/amendment/branch 目标时才启用 `改稿`。

### 9.3 Panel 信息架构

Header：

- 当前阶段与 scope，例如“正文 · 第 12 章”；
- 线程标题；
- Provider/model 小标签；
- 历史、上下文回执、更多、关闭图标；
- 不显示大面积功能说明。

Message area：

- 用户消息、assistant 消息、结构化方案、patch diff 使用不同语义层；
- source citation chip 可展开查看来源类别和版本，不泄露内部 hash 全文；
- patch 使用行内 before/after 或分段 diff，不把整份 Artifact 复制成两列；
- assistant 消息操作包括复制、继续追问、转为方案、基于本回复改稿；
- 失败、取消、contract rejected、stale 都有独立状态，不用一个红色“生成失败”概括。

Thread history：

- 在作者协作台内部打开抽屉，不占用全局左侧导航；
- 按阶段和 scope 分组，显示标题、最后更新时间、model、未应用 patch 状态；
- 支持新建、重命名、归档、删除未应用线程、以新版本/新模型分叉；
- 不把历史 Run 的线程挂到当前 Run。

### 9.4 Composer

视觉复用用户附件的以下特征：

- 黑晶玻璃底、1px 中性高光边界、顶部输入区、底部工具区、独立发送按钮；
- 使用当前 design tokens，圆角收敛到 8px，避免 16px 大胶囊；
- 使用 Lucide `Paperclip/Database/WandSparkles/Send/StopCircle`，不复制附件内联 SVG；
- 不引入 `styled-components`；
- Hover 不上移 5px，不改变布局；使用边界、亮度和 1-2px 光晕；
- 深色背景正文和小字达到可读对比，placeholder 不在 focus 时消失成低对比灰。

Composer 从上到下：

1. Selection/reference chips；
2. 自适应 textarea，最小 72px、最大 180px 内部滚动；
3. `讨论 / 方案 / 改稿` segmented control；
4. 添加选区、上下文、附件/Source Pack、Craft Mechanism；
5. context receipt 摘要、token estimate、发送/停止按钮。

### 9.5 上下文回执弹窗

- 使用全局 Portal、居中、单一内部滚动、稳定 footer。
- 左侧为来源分类；主区为已采用项；底部显示总字符/token、Provider/model 和排除项。
- 每项显示来源名称、作用域、版本、采用原因与预算，不展示 raw JSON。
- 主操作为“确认并发送”；次操作为“返回调整”。
- 关闭弹窗不创建 turn、不调用 Provider。

### 9.6 `Generating` 加载器

复刻用户给出的“旋转光环 + 字母依次增强”概念，但按工作台密度重做：

- assistant message 占位使用 `64x64px`，中心为 `Generating` 字母波动，外环 2 秒线性旋转；
- Panel 首次恢复使用 `72x72px`；按钮内只使用 16px `LoaderCircle`，不塞完整字母动画；
- 色彩使用中性白 + deep 模式克制紫/品红局部光，不铺满面板、不频闪；
- 动画只在真实 `turn.status=streaming` 时存在，完成后 `160ms` 淡出，内容 `180ms` 淡入；
- `prefers-reduced-motion` 下停止旋转与字母缩放，只显示静态环和“生成中”；
- `aria-live=polite` 只播报一次状态变化，不逐字播报 streaming delta。

### 9.7 Motion 与状态

- Panel：180-240ms opacity + 8px x 位移；
- Message：120-180ms opacity + 2px y 位移；
- Context chips 和 patch 状态只在新增时轻显，不持续 shimmer；
- Streaming 更新不能让整页重排或频闪；
- 必须覆盖 Empty、Loading、Streaming、Cancelled、Offline、Provider Failed、Contract Rejected、Context Stale、Patch Stale、ReadOnly、Reduced Motion。

## 10. API 与模块边界

### 10.1 HTTP/SSE 适配

建议路由：

```text
GET    /api/runs/{run_id}/collaboration/threads
POST   /api/runs/{run_id}/collaboration/threads
GET    /api/runs/{run_id}/collaboration/threads/{thread_id}
PATCH  /api/runs/{run_id}/collaboration/threads/{thread_id}
DELETE /api/runs/{run_id}/collaboration/threads/{thread_id}

POST   /api/runs/{run_id}/collaboration/threads/{thread_id}/context-preview
POST   /api/runs/{run_id}/collaboration/threads/{thread_id}/turns
POST   /api/runs/{run_id}/collaboration/threads/{thread_id}/turns/{turn_id}/cancel
GET    /api/runs/{run_id}/collaboration/threads/{thread_id}/stream?cursor=...

POST   /api/runs/{run_id}/collaboration/patches/{patch_id}/accept
POST   /api/runs/{run_id}/collaboration/patches/{patch_id}/reject
```

`context-preview` 返回 preview signature；`turns` 只接受该 signature 与 source refs。服务端在 Provider 调用前重新验证，发现 scope/source 变化返回 `409 context_reconfirmation_required`。

API route 只解析输入、调用 domain service、映射错误。Context 编译、thread orchestration、patch validation 和写回不能进入 route 文件。

### 10.2 前端目标边界

```text
apps/web/src/features/pipeline/
  running/collaboration/
    AuthorCollaborationPanel.tsx
    CollaborationThread.tsx
    CollaborationComposer.tsx
    ContextReceiptDialog.tsx
    PatchCandidateView.tsx
    GeneratingIndicator.tsx
  state/
    useAuthorCollaboration.ts
    useStageSelectionCapture.ts
  services/
    authorCollaborationApi.ts
    authorCollaborationStream.ts
  contracts/
    authorCollaboration.ts
  lib/
    authorCollaborationProjection.ts
```

不新增顶层 `components/`、`dialogs/`、`screens/`、`chat/` 或 `ai/`。`assistant-ui` adapter 只负责把后端 thread/message 状态投影为前端 primitives。

### 10.3 后端目标边界

```text
src/novel_workflow/
  api/routes/author_collaboration.py       # 薄 HTTP adapter
  orchestration/author_collaboration.py    # thread/turn/patch application service
  references/collaboration_context.py      # 有界上下文编译
  output_contracts/author_collaboration.py # Pydantic IO/domain contracts
  storage/collaboration_store.py           # thread/message/turn/patch refs
  storage/collaboration_context_store.py   # immutable context receipts
  runtime/graph/author_collaboration_graph.py
  runtime/graph/author_collaboration_requests.py
```

Provider gateway 增加一个窄 `generate_collaboration_turn()` 能力；不新建第二个 provider package、retry policy 或浏览器直连路径。

## 11. Keep / Migrate / Delete / Archive

| 路径/概念 | 决定 | 说明 |
| --- | --- | --- |
| `StageArtifactDraftStore` | Keep | pending candidate 的正式草稿写回权威 |
| Phase 29 `ArtifactAmendment` | Migrate/Dependency | committed planning patch 的唯一落点 |
| `ChapterStore` / branch service | Keep | Text patch 产生新候选/分支 |
| `ContextManifestStore` | Keep | 继续只服务章节生成，不扩大 task schema |
| `OperationStore` / Provider input snapshot | Migrate | 增加 collaboration/cancelled 语义和 usage 投影 |
| `FrozenNarrativeProviderGateway` | Migrate | 增加窄多轮流式请求，不增加 fallback |
| `EventProjection` | Keep | 只记录稳定协作生命周期，不记录 token delta |
| `SettingsPage` | Migrate | 一级 Tabs + CollaborationProfile |
| 用户附件 `styled-components` Card/Loader | Delete as production path | 只保留视觉语义，不复制组件和样式体系 |
| Vercel AI SDK / CopilotKit runtime / AG-UI | Delete from proposal | 不进入依赖或生产架构 |
| 全量 Canon/Wiki/Memory 注入 | Delete from proposal | 改为相关投影与 receipt |
| 模型直接写 Artifact/Canon/Wiki | Delete from proposal | 必须走 candidate + author decision |
| 历史 Run 对话恢复 | Archive only | 历史 Run 只读，不变成新执行输入 |

## 12. 实施 Waves

### Wave 31.0：方案评审门

- 正向：本文件冻结产品边界、来源台账、合同、UI 和迁移顺序。
- 删除：评审前不实现聊天组件、不调用 Provider、不修改运行图。
- 证据：权威图、阶段矩阵、Context/patch/writeback 边界完整。
- 退出门：用户确认“讨论/方案/改稿”、右侧面板与可审阅 patch 决定。

### Wave 31.1：合同、Store 与 fake Provider

- 正向：Thread/Message/Turn/Selection/Context Receipt/Patch contracts；immutable stores；fake collaboration provider。
- 删除：任意 dict 消息、客户端自报上下文正文、无 source binding patch。
- 测试：identity、replay、stale source、预算、删除/归档、provider receipt 生命周期。
- 退出门：fake Provider 可完成三种模式，未接受 patch 不改变任何 Artifact。

### Wave 31.2：Context Compiler 与五阶段 scope

- 正向：五阶段相关来源投影、preview/confirm、receipt、第二次轻提示状态。
- 删除：全量 Canon/Wiki/Cast/Detail/对话历史注入。
- 测试：来源签名、scope 过滤、token 上限、Source Pack opt-in、Artifact 变更重确认。
- 退出门：同一输入稳定生成同一 receipt；无越权来源。

### Wave 31.3：单一 LangGraph 协作子图

- 正向：thread namespace、nodes/edges、stream/cancel/reconnect、operation receipt。
- 删除：浏览器 Provider、TypeScript agent loop、第二 checkpointer/runtime selector。
- 测试：断线、取消、重复发送、重复 resume、provider_returned 后校验失败、进程恢复。
- 退出门：每个逻辑 turn 最多一次 Provider 调用，重连不重复计费。

### Wave 31.4：右侧工作台与对话历史

- 正向：`assistant-ui` custom runtime、Panel、Composer、History、Context receipt、Generating 动画。
- 删除：复制附件 `styled-components`、内联 SVG、hover 位移、全局持续动画。
- 测试：键盘、screen reader、Reduced Motion、empty/loading/error/cancelled、长中文和历史切换。
- 退出门：五阶段都能讨论/方案；其他阶段无入口；全局主导航互斥但阶段二级栏保留。

### Wave 31.5：选区与 patch candidate

- 正向：textarea/结构字段 SelectionAnchor、diff preview、stale detection、pending draft apply。
- 删除：模糊文本替换、整 Artifact 覆盖、未经确认写回。
- 测试：重复文本、Unicode、跨段选区、source edit 后 stale、schema/引用拒绝、重复 accept。
- 退出门：pending candidate 的五阶段合法文本字段可安全改稿并撤回。

### Wave 31.6：Amendment 与 Chapter branch

- 前置：Phase 29.2/29.3 对应退出门通过。
- 正向：committed planning patch -> amendment impact；Text patch -> new chapter candidate/branch。
- 删除：committed Artifact 原地覆盖、accepted prose 改写、Cast 权威绕过。
- 测试：依赖影响、未来窗口失效、旧线程只读、branch lineage、Export 仍引用 accepted versions。
- 退出门：正式写回只有一个权威路径，旧版本完整可审计。

### Wave 31.7：设置、Provider capability 与全链路浏览器门

- 正向：全局作者协作 Tab、provider/model capability、五阶段默认政策、项目冻结快照。
- 删除：按厂商品牌猜能力、silent fallback、Run 中静默换 model。
- 测试：Provider profile 切换只影响新线程、密钥不入前端、设置保存/恢复、API 失败。
- 退出门：fake Provider 五阶段 E2E 与浏览器矩阵通过。

### Wave 31.8：真实 Provider 验收

- 前置：用户再次批准 Provider、模型、预算和最多调用次数。
- 正向：全新 deep Run，对五阶段各执行至少一条讨论、一条方案和一条有界改稿。
- 删除：历史 Run 复用、隐藏重试、无限上下文、模糊文学结论阻断。
- 证据：脱敏 receipts、call count、token、取消/恢复、patch diff、人工确认和最终 Artifact lineage。
- 退出门：技术、浏览器、真实 Provider 与人工创作质量分别报告，不互相冒充。

## 13. 验收门

### 13.1 确定性合同

- Deep 以外模式无入口且 API 拒绝。
- 只有五个阶段允许创建线程。
- Context receipt 可重建、签名稳定、预算有界。
- Provider input 与 receipt 一一对应。
- patch 绑定 source version、unit、field 和 selection hash。
- 未确认 patch 不改变 draft/amendment/chapter。
- 对话不能写 Evidence/Canon/Wiki/Memory。
- committed planning 和 accepted prose 不可原地覆盖。

### 13.2 前端与浏览器

- `1728x1100`、`1440x1000`、`1280x920`、`1024x700`、`390x844`。
- Panel 与阶段二级栏不互斥；全局主导航不与 Panel 重叠。
- 选区 chip、Composer、回执弹窗、历史、diff 无横向溢出。
- Streaming 不造成编辑区闪动或滚动跳跃。
- Escape/close/backdrop 不丢未发送文本或未决 patch。
- 键盘、焦点、ARIA live、Reduced Motion、触屏入口完整。
- Console 零新增 error/warning。

### 13.3 性能

- 不把完整消息历史放入 React 顶层 context 或 LangGraph State。
- Thread/message 使用 cursor pagination；默认只挂载可见窗口。
- Token delta 不进入全局 Run event log。
- 大型 Artifact 只编译当前 unit/window；Context 预算不随书长线性增长。
- Panel 关闭后停止 stream subscription 和动画，不保留隐形 scroll owner。

### 13.4 真实 Provider

- 每个 turn 的 provider/model、input receipt、usage 和结果状态可追溯。
- 取消、超时、断线、contract rejected 不隐藏成成功。
- 讨论质量、方案可执行性、patch 准确度与文学质量由作者单独评审。
- 真实验收必须使用全新 Run，不恢复历史失败 Run。

## 14. 风险与控制

| 风险 | 触发信号 | 控制 |
| --- | --- | --- |
| 对话变成第二套创作权威 | 消息内容被下游直接读取 | 下游只读 committed Artifact/Chapter；对话仅 sidecar |
| 上下文越多越好 | 一次选择整本 Wiki/Cast/Detail | scope compiler + budget + receipt + 超限显式阻断 |
| 旧线程污染新版本 | Artifact 改版后继续发送 | source binding + rebase/fork + 重新确认 |
| “直接改动”造成内容丢失 | 模型响应立即覆盖 textarea | patch candidate + diff + author accept + source hash |
| Provider 重复计费 | 断线后重新调用 | idempotency key + checkpointer + persisted partial/final turn |
| 聊天 UI 入侵主工作台 | 主编辑区变窄、阶段导航消失 | dock/overlay breakpoint；只收起全局主导航 |
| 依赖拖入第二 runtime | 使用 AI SDK/CopilotKit backend adapter | assistant-ui 仅 primitives + Yotsuba custom runtime |
| 动画喧宾夺主 | 持续光环、全页 shimmer | 只在真实 streaming 状态播放；Reduced Motion |
| Phase 29 未完成却先写 committed patch | 无 amendment 仍提供接受按钮 | 31.6 明确依赖 29.2/29.3；此前只讨论/方案或 pending draft |

## 15. 明确拒绝的替代方案

1. 为每阶段增加一个永久聊天字符串字段。
2. 把完整聊天历史、Canon、Wiki、人物库和知识库每轮全部发给模型。
3. 让前端直接调用 OpenAI-compatible Provider。
4. 引入 CopilotKit/AG-UI 或 Vercel AI SDK 作为第二套 Agent/Provider 控制面。
5. 把用户附件的 `styled-components`、内联 SVG 和 180px Loader 原样复制到生产。
6. 为了捕获选区立刻把全部编辑器迁移到 Tiptap/BlockNote。
7. 使用模糊匹配或字符串 replace 把模型结果写回 Artifact。
8. 允许模型在聊天中新增主体、改稳定 ID、重排卷章或直接写 Canon/Wiki。
9. 让“改稿”自动接受，或提供关闭审阅的全局开关。
10. 用历史 Run 验证新协作功能。

## 16. 评审后的第一步

用户批准本文件后，只进入 Wave 31.1：先落合同、Store、fake Provider 和拒绝测试，不启动服务、不调用真实 Provider，也不先做视觉组件。Wave 31.1 证明“对话不拥有 Artifact、patch 不经确认不写回、Context 有界可追溯”后，才进入 Context Compiler 与 UI。

## 17. Wave 31.1-31.7 实现与 Version 20 验收证据（2026-08-21）

作者协作功能已落在 Phase 30 切换后的唯一 Version 20 `apps/web`，没有在仓库外旧前端
备份中继续开发，也没有 legacy UI、双入口或 Feature Flag。前端引入
`@assistant-ui/react` 对话 primitives；线程、消息、Context Receipt、Provider 调用、
SSE 和 patch 写回仍由 Yotsuba Ink 自有合同拥有。

确定性与浏览器证据：

- Deep 模式仅 `spine/cast/volumes/detail/text` 显示作者协作入口；`brief/cover/export`、
  Studio、Planning 和 Monitor 无入口。后端合同同时拒绝非 Deep 和越权阶段。
- Spine 选区被绑定为 `17 字 · turns.0.change`，不会把整份 Artifact 或模糊文本替换
  当作 patch 来源；讨论、方案和改稿保持独立模式。
- 首次发送前显示完整 Context Receipt：本轮要求、当前局部 Artifact、明确选区、冻结
  上游约束和显式排除的知识库均带范围与预算。点击“放弃本次”后输入草稿保留，本轮
  没有确认发送，因此没有 Provider 调用或 Artifact 写回。
- 桌面 `1440x900` 下，Spine 因果链二级栏保留，打开约 `446px` 作者协作台时仅隐藏
  全局主侧栏；Monitor 使用 `210px + 950px + 280px` 的阶段、内容、健康日志三栏。
- 移动端 `390x844` 下协作台成为完整 `390px` 工作面板，作品库、Spine 和协作台均
  无页面级横向溢出；Header 左上导航触发器只在移动端可见。
- 全局设置新增“作者协作”Tab，只把 ready 且声明 multi-turn/streaming/structured
  patch 能力的 Provider/Model 暴露给新线程；Run 已冻结的线程不会被设置静默改写。
- 浏览器控制台 `0 error / 0 warning`。前端 `5 files / 23 tests passed`，build、CSS
  audit、structure audit 和 CSS build gate 均通过；后端全量为
  `702 passed, 1 warning`；真实 Provider Wave 31.8 未执行。

本节只关闭 Wave 31.1-31.7 的本地合同、fake Provider 和浏览器门。真实模型的讨论质量、
方案可执行性、patch 准确度、成本、取消/恢复和文学质量仍必须在全新 Deep Run 中单独验收。
