# Phase 32 Wave 32.1 Run Authority Cutover Matrix

状态：Definition contracts、archive-only reader、dormant persistence/preflight/branch 与共享 Graph fixture 切片已完成；Persistence/Projection/Graph 生产切换尚未开始。

> 2026-08-25 Wave 46 后续处置：本文件记录的 dormant `phase32_branch_contract.py` 从未接入生产，且其客户端 target id、旧 checkpoint frontier 与 binding override 语义已被正式 amendment successor Run 否定，现已删除。Preflight 与共享 route Graph 保留；当前生产分支合同见 `docs/engineering/phase-32-wave-46-amendment-branch-recovery.md`。

日期：2026-08-23

## 1. 切换原则

`FrozenRouteContract` 是新 Run 的路线与 ReviewPolicy 权威，`GraphRunDefinition` 是未来唯一可执行 Run 定义。当前两者保持 dormant，直到 repository、state、event、preflight、branch、graph 和 API 可以在同一切换波次改读，并同步删除旧 `quality_mode`、固定 `STAGE_ORDER/PHASE27_EDGES` 与 Fast 自动接受。

不得把 Phase 32 route identity 附加到旧 `RunDefinition` 后继续运行固定八阶段图。Scale、Provider、Artifact 和输入合同尚未完成的部分只允许保存显式、内容寻址的冻结快照，不从旧模式推导默认值。

## 2. 权威链

```text
Create Run request
  -> RouteGraphCompiler
  -> FrozenRouteContract
  -> GraphRunDefinition
  -> NarrativeRunRepository definition.json
  -> dynamic NarrativeRunState / RunReadModel
  -> one compiled LangGraph + checkpointer
  -> route-aware events / SSE / UI projection
```

历史 `phase27-vnext` definition 只由 `Phase27ArchiveRunReader` 读取；不能进入新 graph、resume、decision、branch 或 Provider 调用。

本切片已完成的 archive boundary：

- `src/novel_workflow/archive/phase27_archive_reader.py` 严格读取分离的 `definition.json`、`read_model.json` 与 `events.jsonl`，只返回类型化 summary/detail/event page，不暴露原始 JSON、Provider binding、输入全文、checkpoint payload 或文学 Artifact 内容；
- archive 根明确拆为 `archive/runs` 与 `archive/events`，bootstrap 不再挂载旧 viewer，也不读取生产 `native_runtime/runs`；
- 所有历史 Run 的能力投影恒为 `execute/resume/decision/branch/amend/writeback/provider = false`，读取前后文件 hash/mtime 不变；
- reader 不导入 runtime、Provider、Run repository 或 writer。151 个现存 Phase 27 Run 与 25,501 条事件已通过离线全量读扫描；这不是生产切换，也没有移动或改写真实历史数据。

本切片新增的 dormant persistence contract：

- `storage/phase32_run_repository.py` 只接受 `phase32-routes-v1`，以 `runs/<run_id>/{definition,state,read_model}.json` 与 `events/<run_id>/events.jsonl` 保存一条 route-aware Run；创建时先校验 definition/state/read model 的 identity、manifest、digest 和 status；
- Projection 提交只允许成对传入 state/read model，事件写入校验 route identity、连续 sequence、幂等 event id 和事件形状；`phase27-vnext` 明确抛出 `phase27_run_requires_archive_reader`；
- Projection commit 先写同 Run 的 `projection.journal.json`，再依次替换两个 projection；任一替换中断时下一次 `read/state/read_model` 会校验 journal 并重放成对 payload，journal definition digest 漂移会阻断恢复；
- 该 repository 尚未接入 `filesystem_stores`、Graph、Preflight、Branch、API 或恢复入口，因此没有形成第二生产 runtime；它只为下一批单向切换提供可重启 persistence 证据。

本切片新增的 dormant Preflight/Branch contract：

- `orchestration/phase32_run_preflight.py` 只验证 Phase 32 definition、state、read model 的 route identity、manifest、Provider stage 顺序和 projection status/active stage 一致性，不读取 Provider store、不调用模型、不推导旧 `quality_mode`；
- `orchestration/phase32_branch_contract.py` 只生成 source-bound branch plan，拒绝 route 切换、source digest 漂移、没有 active decision 的 active-decision branch、未知/已接受/Export binding override；不复制 checkpoint、Artifact、Canon 或 Outbox；
- 两个 contract 当前没有被旧 runs API、旧 BranchService、NarrativeRuntime 或恢复入口导入，旧固定八阶段执行路径仍保持原样，等待 Graph/Preflight/Branch/API 同波切换。

本切片新增的 dormant Graph fixture：

- `runtime/graph/route_graph.py` 是唯一共享 builder。它接收 `GraphRunDefinition`，按冻结 manifest 动态挂载每个 stage lifecycle 子图，并按 manifest downstream edges 连接父图；没有固定阶段数组、`quality_mode` 或旧 `PHASE27_EDGES` 依赖。
- Provider generation 只在 `provider_task_kind` 非空的阶段执行；`export` 只经过 deterministic `commit_stage`，并发出 `export.ready`，因此 graph builder 本身不会为交付阶段调用 Provider。
- 必审阶段、自动继续阶段和有界定向换稿由冻结 `ReviewPolicy` 决定；决策 payload 带 route identity 与 domain revision，过期或错路由的恢复值被拒绝。driver/event sink 是窄端口，尚未连接旧 Store、Provider gateway 或 API。
- `tests/test_phase32_route_graph.py` 覆盖三路线拓扑、同一 builder/checkpointer 运行三路线、Export 无 generation、ReviewPolicy interrupt/auto-continue、跨 definition state 拒绝、定向换稿上限和旧固定字段静态拒绝；当前定向切片为 `10 passed`。

该 Graph 仍是 fixture-only：没有挂到 `filesystem_stores`、`NarrativeRuntime`、恢复服务或 HTTP 入口。Wave 32.1 退出前必须和 repository、projection、preflight、branch、API 一起单向切换，并同步删除旧 graph reader。

本切片新增的 dormant History projection：

- `storage/phase32_history_projection.py` 只读取 `Phase32RunRepository` 的 definition/read model，动态投影路线、阶段 manifest、进度、active unit、pending decision、checkpoint 和 Export 状态；不读取旧 `quality_mode`、固定 `STAGE_ORDER` 或文学 Artifact 内容。
- `tests/test_phase32_history_projection.py` 覆盖路线标签、动态阶段总数、待决策/可分支状态和旧字段静态拒绝；该 reader 仍未替换旧 `RunHistoryProjection`，避免在旧 API 仍使用旧 repository 时形成双读路径。

本切片新增的 dormant Event projection：

- `storage/phase32_event_projection.py` 从 `Phase32RunRepository` 分页读取已校验的 `RouteRunEventEnvelope`，返回 route/revision/manifest/definition identity、连续 cursor、`has_more` 和决策/失败/Export 终止状态；不读取旧 `EventProjection`。
- `tests/test_phase32_event_projection.py` 定向 `3 passed`，覆盖分页重连、决策 required/resolved 终止判定、Export terminal、非法 cursor/page size 和旧事件 reader 静态拒绝。HTTP/SSE adapter 已以 dormant 形式完成，但仍延后到同波 API cutover，避免提前形成第二入口。

本切片新增的 dormant HTTP/SSE adapter：

- `api/phase32_sse.py` 只消费 `Phase32EventProjection` 的 route-aware page，使用 sequence cursor 重连，输出稳定 `id/data` SSE 帧，并在 `decision.required`、失败或 `export.ready` 终止；它不导入旧 `api.sse` 或 `storage.event_projection`。
- `tests/test_phase32_sse.py` 覆盖首屏事件、游标重连、Export 终止、负游标拒绝、响应 headers 与旧适配器静态隔离。
- 该 adapter 仍未挂载到旧 `/api/runs/{run_id}/events`，也没有新增并行 HTTP 入口；只有在 Repository、Graph、Preflight、Branch、History、Event、API 同一波切换时才允许替换旧 SSE reader。

2026-08-23 Wave 32.2 首个 Artifact contract slice：

- 新增 dormant `output_contracts/phase32_route_artifacts.py`、`phase32_artifact_base.py` 与 `phase32_delivery_artifacts.py`，按职责拆分通用基类、规划合同、正文/封面/交付合同；覆盖三路线 Brief/Cast、剧本 `BeatBoard`/`SceneDeck`/`ScreenplayDraft`、短中篇 `StoryMap`/`SectionPlan`/`ShortProseUnit`、长篇 `BookArchitecture`/`VolumeArchitecture`/`DetailPlanIndex`/`Chapter` 以及 Cover/Delivery。核心模型只保存创作内容和稳定引用，不包含 Provider、状态、版本、进度、审阅或 UI 字段。
- 合同统一使用 `extra=forbid`、不可变模型、稳定 ref、连续 ordinal 和有界集合；Character relationship、Part -> Volume -> Window 跨聚合引用、跨 Window chapter ref、路线篇幅包络和阶段 Artifact 类型均由确定性代码校验。
- `tests/test_phase32_route_artifacts.py` 定向 `11 passed`，覆盖 strict schema、主体注册表、屏幕可见场景、Story Map/Section 顺序、正文/封面/交付类型、长篇层级覆盖、短长篇篇幅范围、跨路线 Artifact 拒绝和旧合同静态隔离。
- 该模块尚未被旧 `artifacts_vnext.py`、Provider、Graph、API 或持久化导入；Wave 32.2 仍未关闭，后续还需完成 Scale/Artifact 与 Run 创建的 fixture commit 退出门。

2026-08-23 Wave 32.2 Scale contract slice：

- 新增 dormant `workflows/phase32_scale.py`，将剧本样片固定为分钟单位、短中篇与长篇固定为中文字符单位；每条路线明确 `minimum / recommended band / maximum` 与推导说明。
- 长篇额外冻结滚动 Window 容量为 12-40 章、1-3 卷；总字数与 Window 容量分离，允许作者在 P0 包络内选择软目标，不自动截断或凑字数。
- `tests/test_phase32_scale.py` 定向 `11 passed`，覆盖默认/自定义目标、边界拒绝、滚动窗口、单位/顺序/extra 字段拒绝和旧规模逻辑静态隔离。
- `freeze_phase32_scale_profile()` 已把 typed `ScaleProfile` 写入 `GraphRunDefinition.scale_profile` 的内容寻址快照，并校验路线/策略版本/包络一致；旧 generic snapshot 仍可被 dormant 夹具读取，但没有接入旧 `narrative_scale.py` 或 Create API。

2026-08-23 Phase 32 no-Provider Run creation fixture：

- 新增 dormant `orchestration/phase32_run_fixture.py`，按官方三路线冻结 RouteContract、ReviewPolicy、typed ScaleProfile、Inputs 和显式 Provider binding snapshot；随后原子提交 `brief=running` 的 State/ReadModel 并写入首个 `stage.started` 事件。
- `tests/test_phase32_run_fixture.py` 覆盖三路线创建、Definition/Scale identity、事件连续性、新 Repository 实例重启读取、未注册路线拒绝和 Provider/legacy runtime 静态隔离；该 fixture 不调用 Provider，也未挂到旧 API。

2026-08-23 fixture 联合门：

- 新增 `tests/test_phase32_fixture_integration.py`，让三条 fixture Run 依次通过 `Phase32RunPreflight`、`Phase32BranchContract` 和同一个 `route_graph` builder，运行到 Brief 的首个 mandatory decision 中断。
- 联合测试确认动态 stage manifest、route/definition digest、Scale/ReviewPolicy、stage-boundary branch frontier 与 Graph interrupt identity 一致；Fake driver 只生成 Brief，Export 从未触发。

2026-08-23 decision/event replay slice：

- 新增 dormant `storage/phase32_graph_event_sink.py`，只把共享 Graph 的稳定领域事件封装为 `RouteRunEventEnvelope` 顺序写入 Phase 32 Repository；不拥有编排、Provider 或 ReadModel 业务。
- 联合 fixture 现在会接受所有 mandatory decisions，验证事件 sequence 连续、`decision.required/resolved` 成对出现、`export.ready` 成为最后事件，并通过 `Phase32EventProjection` 验证游标越过 terminal 后仍保持 terminal。

2026-08-23 creation wizard contract slice：

- 新增 dormant `workflows/phase32_creation_wizard.py`，将向导第一步建模为 `CreationIntent`：先选剧本/小说，小说再选择短中篇/长篇，并由同一 ScalePolicy 校验目标单位和包络。
- 第二步通过 `recommend_workflows()` 只返回与推断路线匹配且可用的官方/自定义流水线；`new_workflow_seed()` 为“新建”生成路线绑定的默认 workflow seed，不能跨路线选择。
- `tests/test_phase32_creation_wizard.py` 定向 `10 passed`，覆盖意图歧义拒绝、路线推断、官方匹配排序、自定义流水线选择、新建默认 seed、不可用/错路线拒绝和旧模式静态隔离；该合同尚未接入 Create API 或前端路由。

## 3. 逐文件切换矩阵

| Owner | 当前 writer | 当前 readers | Phase 32 replacement | 同波删除 | 正向测试 | 拒绝/静态测试 |
| --- | --- | --- | --- | --- | --- | --- |
| `workflows/graph_run_definition.py` | Route/Workflow freeze service | repository、preflight、graph compiler | `GraphRunDefinition` 内嵌 `FrozenRouteContract`，其余合同为显式内容寻址快照 | 无旧 RunDefinition importer | 三路线 round-trip、digest、动态初始阶段 | 拒绝旧字段、篡改、缺失/多余/乱序 Provider stage |
| `storage/narrative_run_repository.py` | Create Run API、Branch service | runtime、history、story bible、collaboration | 仅写/读 Phase 32 definition；历史读取移至 archive repository | `quality_mode`、`hierarchical_scale_plan` 新 Run authority、固定 `StageId/STAGE_ORDER` 初始化 | 三路线重复创建与动态 read model | production repository 拒绝 phase27；静态无旧字段/固定顺序 |
| `runtime/graph/state.py` | graph node updates | graph router、executor、projector、checkpoint | route revision、manifest digest、stage/unit cursor、动态 string-key mappings | 固定 `StageId`、`quality_mode`、chapter-only cursor authority | 三路线 checkpoint round-trip | route 外 stage/unit mapping 拒绝 |
| `storage/event_projection.py` | runtime/event sink | SSE、read model rebuild、monitor | route revision、stage id、unit ref、artifact kind；stage 由 Run manifest 校验 | 固定 `StageId`、chapter-only identity | 三路线事件重放得到同一投影 | route mismatch、未知 stage、错误 revision 拒绝 |
| `runtime/graph/narrative_graph.py` | graph builder | Runtime invoke/resume | `runtime/graph/route_graph.py` 按 compiled manifest 装配共享 lifecycle、unit cursor 和 interrupt | 固定八节点/边、`quality_mode` state | 三条 Fake Run 共用同一 builder/checkpointer | static 无 `STAGE_ORDER/PHASE27_EDGES`、无 route runtime selector |
| `runtime/graph/stage_graph.py` | stage lifecycle | narrative graph | ReviewPolicy 驱动 accept/interrupt/needs_action | Fast 自动接受 branch | policy 自动继续与 mandatory decision | 搜索无 `quality_mode == fast` |
| `runtime/graph/chapter_decision.py` | prose unit decision | text unit graph | route/unit-agnostic decision policy | Fast 正文自动接受 | short/long text 单元各一例 | 无 mode 分支；deterministic blocker 不可自动继续 |
| `runtime/graph/manuscript_review.py` | manuscript milestone decision | text/export transition | warning policy + milestone decision | Fast 稿件自动接受 | warning 汇总与明确 continue/pause | blocker 不得由 warning policy 绕过 |
| `api/routes/runs.py` | HTTP create/start/decision/branch adapter | browser/web client | 请求解析后调用 Route freeze/Run service；stage validation 读 manifest | Workflow `quality_mode`、`STAGE_ORDER` 校验、旧 executable workflow | 三路线 create/start/read API | 旧 mode payload、route 外 stage、历史写请求拒绝 |
| `orchestration/run_preflight.py` | start preflight result | API/Runtime | 校验 definition digest、route manifest、Provider stages、Artifact parser registry | 固定 Provider stage list、旧 executable contract | 三路线 preflight | binding 缺失/多余、digest 漂移、archive Run 拒绝 |
| `runtime/graph/branch_service.py` | branch definition/checkpoint seed | repository、runtime | manifest ordinal、source-bound amendment/branch policy | `STAGE_ORDER.index`、旧 mode 复制 | 三路线合法 frontier branch | 跨 route、route 外 stage、archive source 执行拒绝 |
| `storage/run_history_projection.py` | rebuildable history projection | workbench/history API | route label、deliverable、manifest progress、active unit | `quality_mode` 展示、固定 stage pointer | 三路线历史摘要 | 不从 archive definition 构建可执行动作 |
| `workflows/executable_contract.py` | 旧 Workflow 编译校验 | API、preflight、templates | `RouteGraphCompiler` + registries | 整个生产模块及 `PHASE27_EDGES` | official/custom route compile | production import scan 无该模块 |
| `output_contracts/artifacts_vnext.py` | 旧 Artifact/Stage 类型 | runtime、API、tests | Wave 32.2 route Artifact modules + manifest stage ids | `STAGE_ORDER` 与 flat Spine 新 Run authority | route Artifact fixtures | production import scan 无固定 stage order |

## 4. 单向切换批次

1. **Definition contracts（已完成）**：完成 `GraphRunDefinition`、动态 read model/state/event schema 与纯校验测试，保持无 production importer。
2. **Persistence and projection**：repository、event、history 一次切换；将 Phase 27 reader 移到 archive-only 边界，拒绝新写入和执行。（archive reader 切片已完成，生产根目录切换仍待本批次整体落地。）
3. **Preflight and branch**：改读 manifest；所有 stage/binding/frontier 校验由 Run authority 驱动。（纯合同切片已完成，生产入口尚未切换。）
4. **Graph execution**：一个 builder 按 manifest 装配三条 Fake Run；同时删除固定 executable contract 和三处 Fast 自动接受。
5. **API cutover**：Create/Start/Decision/Branch 只接受 Phase 32；删除旧模板和 mode 输入。

任何批次若不能同时删除其对应旧 reader，不接入 production importer。批次 2-5 在同一 Wave 32.1 内完成，不能形成可长期运行的双路径。

## 5. 退出门

- 三条 Fake Run 分别持久化正确 route identity、manifest、policy、bindings 和 definition digest；
- 同一个 LangGraph builder/checkpointer 执行三种实际拓扑；
- checkpoint、event、read model、SSE 使用 manifest 动态阶段；
- production 源码不存在 `quality_mode` 执行分支、固定 `STAGE_ORDER/PHASE27_EDGES` 或旧 executable contract import；
- 历史 Run 只读、零 Provider，所有写操作明确拒绝；
- 定向、全量后端、`compileall`、`git diff --check` 与 production closure audit 全部通过。

本切片通过只代表 archive boundary 与 dormant persistence contract 已有正向/拒绝/不可变性证据；在上述退出门关闭前，Wave 32.1 仍为进行中。

## 6. Definition contracts 证据

- `runtime/graph/route_run_state.py` 只保存 route identity、stage/unit cursor、Artifact/operation refs、attempts、failure 和 domain revision；不保存文学正文、Provider payload、Review 结果或固定 chapter cursor。
- `storage/route_run_read_model.py` 嵌入可展示的 compiled stage manifest 与 ReviewPolicy summary，动态校验 stage status、Artifact kind、pending decision、active unit 和 failure scope；恢复时必须与原 `GraphRunDefinition` 一致。
- `storage/route_run_event.py` 只接受 Phase 32 稳定事件名，并校验 route revision、manifest/definition digest、stage、unit 和 Artifact kind；`export.ready` 只能属于 Export stage。
- 三条路线均通过 definition/state/read model/event 的原子 JSON/JSONL 落盘恢复夹具；route identity、manifest、stage mapping 和事件归属可从同一冻结定义重建。
- Phase 32 定向合同集 `66 passed`；兼容回归 `129 passed, 1 warning`；全量后端 `843 passed, 1 warning`；`compileall`、`git diff --check`、frontend structure audit 和 production closure audit 通过。
- 新合同仍无 production importer；旧 repository/state/event/runtime 未改读，未形成第二执行路径。
