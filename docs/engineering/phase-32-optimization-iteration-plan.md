# Phase 32 优化迭代计划（文本闭环优先，图片延后验收）

- **文档状态**：文本验收闭合，进入 `v0.1.0` 发布候选收口；图片验收继续独立延后
- **基线日期**：2026-08-26（最近复测：2026-08-27）
- **当前复核日期**：2026-09-06
- **适用范围**：Yotsuba Ink 三档官方创作路线、文本 Provider、运行态、质量门禁、写回与文本侧交付证据
- **核心决定**：图片生成暂不进入本轮验收；本轮不得以假封面、假图片成本、占位图片或“已请求 Provider”替代真实图片结果
- **验收原则**：先证明一条可追踪、可恢复、可复现的文本链路，再单独重新引入图片能力

### 实施进度（更新至 2026-09-06）

- **已完成第一刀**：公共 creation-wizard catalog 已优先返回三条 `official.<route>` canonical 身份；canonical route 可直接进入 Phase 32 Run 冻结。
- **已完成 Provider 选择修复**：默认文本 Provider 只从 enabled、地址/模型完整且允许执行的 profile 中确定性选择，不再取到空配置记录。
- **当前回归**：发布冻结态后端全量 1339 passed、1 个既有 warning；前端为 74 个测试文件 / 193 tests，TypeScript、Vite 8.2.2 production build、结构、CSS 与浏览器审计均已完成。
- **文本门已完成**：全新真实 DeepSeek exact-12 已完成 12/12 章、12/12 写回、人工逐候选监管、稳定性统计和绑定 12/12 source digest 的冷读；工程连续性通过，文学成品质量未通过且 warning 被如实保留。
- **Wave 52 首批证据**：DeepSeek Flash 固定文本 probe 连续 3 次响应 hash 一致，`finish_reason=stop`，每次 47 tokens，延迟 1.202–1.724 秒；详情见 [Wave 52 probe 记录](phase-32-wave-52-canonical-text-probe.md)。
- **Wave 52 canonical smoke**：screenplay r2 达到 `completed`；short-novel r2 达到 `image_deferred`；long-novel r3 完成 10 个章节后达到 `image_deferred`，三条路线均为 0 图片调用。详见 [canonical smoke 证据](phase-32-wave-52-canonical-route-smoke.md) 与 [长篇复跑补充](phase-32-wave-52-canonical-route-smoke-addendum.md)。
- **Wave 53 连续性修复**：执行器现在按持久 checkpoint 的 interrupt id 定向恢复，修复 sequential text → mandatory cover 的旧 decision 串线；Story Map/Section Plan 承诺引用和 Cast/正文命名边界已收紧；新增写回恢复回归，后端全量 1160 passed。
- **Wave 53 真实复测**：canonical short-novel r7 在全新 Run 中完成文本链并停在 `image_deferred`；12 个 Provider operation 中 11 个最终成功、1 个首轮写回合同拒绝后纠正成功，`pending_operations=0`、成本约 `$0.07936368`、46 个 SSE 事件单调递增，图片 operation 为 0。冷启动 API 读取保持一致，Export 返回 409 `image_deferred`。详见 [Wave 53 短篇质量与恢复补充](phase-32-wave-53-short-quality-addendum.md)。
- **Wave 53/54 新鲜复测**：screenplay r3 完成文本交付；short-novel r8 为 11/11 Provider operation 成功、long-novel r9 为 10/10 成功，两个新样本首轮 writeback `span_ids` contract reject 均为 0、空 claims 纠正为 0、pending 为 0，并均停在 `image_deferred`。长篇 r9 命名通过但 release-smoke 只有 2 章，不能作为正式长篇文学质量通过。详见 [Wave 53 三路线闭环记录](phase-32-wave-53-three-route-closure.md) 与 [Wave 54 写回稳定性](phase-32-wave-54-writeback-contract-stability.md)。
- **Wave 53 质量硬门禁**：长篇/短篇正文与剧本现在对 `姓名：X`、`名字是X`、`叫作X`、`输入“X”` 等高置信命名表达执行已登记 Cast 校验；不做泛化 NER。未登记显式姓名会在候选接受前以 `provider_contract_failed` 阻断，并保留具体名称诊断。
- **Wave 54 写回首轮稳定性**：Long r8 暴露 DeepSeek `json_object` 模式不会执行嵌套 `span_ids.maxLength=3`；首轮一个 claim 复制了 4 个 span，第二次纠正退化为空 claims。当前已把 span 数量规则重复放到长上下文末尾硬检查，纠正提示改为只修复超限字段并保留有效 claims；新鲜 Short r8/Long r9 已验证首轮 reject 0、空 claims 纠正 0。
- **Wave 55 文本 Export**：成功列表现在返回 artifact type、source refs、依赖状态和 deferred reason；已结束但无真实 delivery receipt 不再返回空成功。Screenplay r3 冷启动 Export 200 且有真实 Fountain receipt；Short r8/Long r9 冷启动 Export 409 `image_deferred`，均保留已知 source refs、0 items，图片 operation 仍为 0。详见 [Wave 55 文本交付记录](phase-32-wave-55-export-delivery.md)。
- **Wave 51 图片边界已代码化**：canonical 短/长篇只写回 CoverBrief，CoverArtifact 标记 `image_acceptance_status=image_deferred`，不创建 image operation；图谱停在 cover，Export API 返回 409 `image_deferred`。
- **Wave 58 连续性硬门**：新增私有 `continuity_acceptance` 档，只接受单 Window、单卷、恰好 12 章；公共项目创建不能选择该档。持久层新增 accepted-prefix 单调性、state/read-model 配对和 journal 防回滚校验；durable Provider return、终态 singleton/SSE 重连、真实事件观测时间以及版本绑定的冷读 sidecar 均有离线回归。
- **Wave 58 离线验证**：十个直接相关测试文件 130 passed；后端全量 1199 passed、1 个既有弃用 warning；`compileall` 与 `git diff --check` 通过。exact-12 Fake 演练在第 4、8 章后重建存储与 Driver，最终 12/12 前缀完整、operation identity 唯一、图片调用为 0。
- **Wave 59 私有入口**：新增 domain/internal-only exact-12 launcher，只冻结 `official.long_novel + long_novel + continuity_acceptance`，要求显式幂等 key 与隔离命名空间；按 key 的可重入事务与 POSIX `flock` 覆盖 reservation、恢复、Run definition 创建和完成标记，并发相同请求复用持久 winner，冲突请求不能覆盖。公共 `POST /api/projects` 没有 profile selector，production/release-smoke 行为不变。
- **Wave 59 readiness 与价格**：readiness 已变为绑定 definition/policy、content-addressed、脱敏且会过期的持久 admission；stage/report 合同会拒绝自相矛盾的 ready/issue、价格年龄、required model 与 text-only 结论，并把期望 stage manifest 及每阶段 Provider 身份与 Run definition 复核，删减、增加、换序或替换后重算 digest 也不能放行。bootstrap seed 只补缺失 model pricing，不覆盖 operator 已持久化的新鲜价格。代码默认 pricing 仍是历史 seed，但 Wave 61 已把当前运行时价格重新 attestation；现阶段阻断点已从 stale pricing 转为 `explicit_run_budget`。
- **Wave 59 budget/attempt fence**：预算授权绑定 definition digest，美元/逻辑 operation/token 均无默认额度，单 operation transport cap 由代码冻结为 3。每个 attempt admission 以 authorization/Run/definition/operation/request/ref/attempt 完整身份在 operation claim lock 内核对，并顺序写入 receipt 的 claimed refs；跨身份或 stale fence 在 gateway 前拒绝。retry 不重复占逻辑 operation，但会再次占 token/成本。
- **Wave 59 预算恢复硬化**：partial/矛盾 terminal usage 不释放保守预留；返回时 pricing snapshot 与 provider profile/template/model identity 不可替换；late return 只允许留下一个未 claim 的 future grant，并将其作为 immutable implicit void 排除累计占用，更多 future grants 视为冲突。
- **Wave 59 创建与 projection 中断恢复**：preparation record 会重算 request/profile digest 并绑定 idempotency/Project/Run/status；Run repository 以 Run id 跨进程串行 create、完整 read、projection commit/recovery。create 任一 staging 写入点或 projection journal 前硬退出后，冷进程均能保留最后完整权威并安全继续；未知 staging 内容、symlink 或已提交 target 不会被清理。
- **Wave 59 replay、API 与旁路**：start/resume 在新 graph step 前 fail-closed；durable terminal operation 和纯本地 state/decision replay 不重复 admission 或 Provider 调用，但 pending/succeeded decision 仍要求 exact command replay。start/decision API 将 readiness/authority/budget 阻断脱敏映射为 409、preflight 阻断映射为 422；direct driver/writeback 不能绕过；continuity acceptance 的 author collaboration create/execute 被稳定拒绝，图片请求不属于私有 admission 类型且 text-only readiness 会拒绝图片绑定。
- **Wave 59 放行判断**：单次联合聚焦回归 276 passed，后端全量 1316 passed、1 个既有 Starlette 弃用 warning；细分切片为 budget/generation/writeback 110、API + execution 52、launcher 41、Run repository 19、readiness/admission/continuity 29（集合有重叠，不相加）。DeepSeek 真实调用为 0、图片真实调用为 0。详见 [Wave 59 Provider admission 与预算](phase-32-wave-59-provider-admission-and-budget.md)。
- **Wave 60 attempt/evidence**：Provider receipt 现以同一次原子写入保存 content-addressed `claimed/lease_expired/transport_failed/provider_returned` 事件；版本化 bundle 只导出脱敏元数据与 digests，并从冷态 authority 重建验证。旧式无事件 receipt 可兼容读取，但不能通过 release verifier。
- **Wave 60 私有 harness**：harness 复用 production bootstrap 的同一 repository、execution、admission、budget、gateway、Artifact、writeback、Canon/Wiki 与 quality authorities；没有公共 API。默认不自动接受候选，显式 stop policy 才能用于离线批量演练。
- **Wave 60 exact-12 离线结果**：第 4、8 章后分别重建应用，最终 12/12 accepted chapters、12/12 committed writebacks、pending 0、attempt/admission 一一对应、唯一 `image.deferred` 终态、image/collaboration operation 均为 0；再次冷启动后 bundle `require_valid` 通过。Wave 60 专项 6 passed，联合回归 223 passed，后端全量 1322 passed、1 个既有 warning；真实 DeepSeek 与图片调用均为 0。详见 [Wave 60 发布证据与离线演练](phase-32-wave-60-release-evidence-and-rehearsal.md)。
- **Wave 61 零费用预检**：官方 DeepSeek Pro peak cache-miss/输出费率已按保守上界重新 attestation；Provider profile 更新使用 Provider 级跨进程锁与 SQLite 原子 CAS，可恢复 intent→catalog 中断并阻断第三状态漂移。环境报告为 `ready_for_budget_authorization / explicit_run_budget`，`billable_call_count=0`，secret 仅记录存在性。专项 38 passed、Phase 32 联合回归 214 passed、后端全量 1329 passed（均只有 1 个既有 warning）；真实 DeepSeek 与图片调用仍为 0。详见 [Wave 61 真实文本候选零费用预检](phase-32-wave-61-live-candidate-preflight.md)。
- **Wave 62 真实 Brief 门**：用户已授权 `$5 / 48 operations / 2,000,000 tokens`；新增内容寻址候选授权清单并把校验下沉到 continuity admission，直调 execution 也不能绕过。全新 Run 的 Brief 1 次 transport 成功，1,176 tokens、13.983 秒、估算 `$0.00256608`，无纠正/重试，冷启动状态和部分 bundle 一致，图片/写回/协作调用均为 0。候选存在规则矛盾与终局因果 warning，当前停在人工决定。详见 [Wave 62 真实 Exact-12 Brief 门](phase-32-wave-62-live-exact12-brief-gate.md)。
- **Wave 63–67 最终结果**：在人工全程监管下完成 Brief 修订、主体权威、12 章滚动细纲、正文、写回、质量复核和 release bundle。45 个逻辑 operation 最终均形成可用结果；48 次 transport attempt 中 3 次网络失败均在同一 operation 第 2 次尝试恢复。实际 Provider usage 为 286,193 tokens、约 `$0.54674268`；bundle 按失败预留保守计入 371,318 tokens、约 `$0.70662768`。终态唯一为 `image_deferred`，图片与作者协作 operation 均为 0。详见 [Wave 67 发布候选报告](phase-32-wave-67-release-candidate.md)。
- **图片边界不变**：本轮图片调用数要求为 0；图片 Provider、CoverAsset 和完整短篇/长篇交付继续留在独立图片波次。

## 1. 执行摘要

本计划立项时，项目虽已有三条路线定义、阶段产物校验、Fake Provider 测试和多轮真实 DeepSeek 文本运行证据，但官方路线身份、运行时旧模板和图片阶段完成语义尚未统一。经过 Wave 50–67，三路线的文本运行、恢复、写回、证据和图片延后边界已形成工程闭环；真实 exact-12 证明链路连续性和失败恢复通过，同时明确证明文学成品质量尚未通过。后续优化重点转向篇幅达成、降低流程性重复和提高因果可信度，不能用工程通过替代这些质量改进。

本计划把下一轮工作拆成两个验收面：

1. **当前验收面：文本闭环**
   - 只验收 `screenplay_sample`、`short_novel`、`long_novel` 三条官方路线的文本阶段。
   - 验证路由身份、冻结运行、Prompt/Context、DeepSeek 调用、结构化响应、决策、写回、恢复、连续性和证据投影。
   - `short_novel` 和 `long_novel` 到达 `CoverBrief` 后可以明确停止在 `image_deferred`，这不是失败，也不是完整成品交付。

2. **后续验收面：图片与完整交付**
   - 图片 Provider、封面图片资产、图片成本、图片重试、图片质量、封面写回以及依赖封面资产的最终导出全部单独验收。
   - 未完成这条波次前，禁止把短篇/长篇标记为 `completed`，也禁止生成看似真实的 CoverAsset。

本计划及其 Wave 记录是当前实现、测试和现场验收的工程依据；发布候选结论以 Wave 67 报告和冻结 evidence bundle 为准。

## 2. 当前基线与判断

### 2.1 已有证据

| 面向 | 当前证据 | 判断 |
|---|---|---|
| 后端回归 | `uv run pytest -q`：1160 passed，1 warning | 离线回归稳定，但不能替代真实 Provider 验收 |
| 前端 | 68 个 Vitest 文件 / 170 tests；`tsc`、Vite build、结构检查通过 | 基本可构建，仍存在旧模板身份展示 |
| Screenplay 真实运行 | canonical r3：11/11 Provider op 成功；3 个 scene、3 次写回；Fountain 已持久化；47 条 SSE 单调 | 文本结构、恢复和文本交付通过；重复意象仍是文学 warning |
| Short novel 真实运行 | canonical r7：3 个文本单元、3 次写回；Promise/命名门禁通过；12 个 Provider op，1 次首轮写回纠正；到 CoverBrief | 文本链和恢复 pending 统计通过；图片阶段被 fail-closed，不能继续宣称交付完成 |
| Long novel 真实运行 | canonical r8：命名门禁后 2 章、11 个 Provider op（10 succeeded + 1 首轮 writeback reject 后纠正）、0 pending，最终 `image_deferred` | 传输/恢复/命名边界通过；2 章 bounded smoke 不代表长篇质量，仍需标准多章样本 |
| DeepSeek 低成本探针 | 3 次响应 hash 一致，延迟约 2.494/0.842/0.796 秒 | Provider 连接和输出稳定性有正向信号，样本量仍不足 |
| 图片 Provider | 配置存在但 pricing 为空；执行被 fail-closed 或留 pending | 明确移出当前验收，保留阻断证据 |
| 连续性 | Short r7 Promise/命名通过；Screenplay 结构通过但有重复意象 warning；Long r8 handoff 可读且命名门禁通过 | 未注册显式姓名门已验证；长篇仍需标准多章/人工冷读与 writeback reject 率观察 |

### 2.2 当前结论

- 三条路线的 **RouteSpec 与阶段合同** 是新权威；旧的 `official-deepseek-fast`、`official-deepseek-balanced`、`official-deepseek-deep` 只能作为迁移输入，不应继续作为官方产品身份。
- API catalog 仍暴露旧工作流模板，且 `resolve` 对新 route id 不能稳定解析；这是 P0 入口问题。
- 旧模板仍使用 `phase27-vnext` 和 `brief -> spine -> cast -> volumes -> detail -> text -> cover -> export` 图；Phase 32 的路线图和实际执行图未完全同源。
- `source=None` 时 Provider 绑定可能选中空 `base_url` 的文本 profile；这是可直接导致真实调用前失败的 P0 配置问题。
- `CoverBrief`（文本）和 `CoverAsset`（图片）必须在状态上分离；图片未验收时只能写回前者。
- 当前“文本链完成”不等于“产品成品完成”。短篇和长篇的完整交付需要图片波次另行通过。

## 3. 验收边界（必须写进实现和 UI）

### 3.1 本轮纳入

- 三条官方 route id 的 catalog、resolve、prepare、run 和恢复。
- 每条路线的 RouteSpec、artifact contract、stage decision、writeback 和 read-model projection。
- DeepSeek 文本 profile 的显式选择、请求/响应 receipts、结构化解析、错误分类和可重试策略。
- 断点恢复、同 operation 幂等、accepted prefix、pending operation 和失败原因的可见性。
- 文本产物之间的引用、时间线、角色、章节/场景 handoff 检查。
- Screenplay 的文本侧导出证据；短篇/长篇只允许导出明确命名的文本预览（如果实现该能力），不得冒充完整交付。
- UI 对“文本完成”“图片延后”“完整成品”的状态区分。
- 离线回归、真实 DeepSeek 小样本和浏览器 smoke 的证据归档。

### 3.2 本轮不纳入

- 图片生成 Provider 的连通性、模型质量、价格、token/图片计费、图片重试和图片超时预算。
- CoverAsset 的真实二进制、缩略图、尺寸、版权元数据和图片持久化。
- 使用占位图片、旧缓存图片、固定 hash 或“请求已发送”伪造图片成功。
- 依赖 CoverAsset 的短篇/长篇完整 BookDelivery/Export 完成态。
- 用文学评分模型替代人工冷读；自动评分只能作为警告信号。

### 3.3 状态语义

| 状态 | 含义 | 本轮是否可作为验收通过 |
|---|---|---:|
| `text_completed` | 该路线规定的文本阶段、决策和写回均完成 | 是，但仅代表文本面 |
| `image_deferred` | 已生成并写回 CoverBrief，图片阶段被策略性延后 | 是，作为明确的阶段边界 |
| `image_pending` | 已创建图片 operation 但未完成 | 否；本轮不应主动进入该状态 |
| `image_failed` | 图片 Provider 失败 | 否；保留失败证据，不能降级成成功 |
| `completed` | 路线所有必需产物及交付物完成 | 只有图片波次通过后，短篇/长篇才可使用 |

## 4. 单一权威链路

下一轮实现必须能沿着同一个 `run_id` 追踪以下链路，不允许 UI、旧模板和 API 各自推断阶段：

```text
用户选择 route
  -> API catalog/resolve（canonical route id）
  -> frozen Run manifest（route digest + provider snapshot）
  -> RouteSpec stage graph
  -> artifact contract + context/prompt assembly
  -> DeepSeek text operation
  -> Provider receipt（attempts / exact_object / usage / error）
  -> stage decision（accept / retry / regenerate / defer）
  -> artifact writeback（幂等）
  -> read-model projection / SSE
  -> 文本预览或后续图片波次入口
```

### 4.1 责任边界

| 组件 | 只负责 | 不得负责 |
|---|---|---|
| `route_specs.py` / Phase32 route catalog | 路线身份、阶段顺序、阶段依赖 | Provider 选择、UI 文案拼接 |
| API adapter | 入参校验、调用 domain、输出 HTTP/SSE | 聚合质量规则、拼装旧模板 |
| Provider binding | 从冻结快照绑定文本 profile 和执行配置 | 隐式选择第一个 profile、把图片当作文本成功 |
| Context/prompt builder | 读取已接受 artifact，生成可审计 prompt | 直接写业务状态 |
| Runtime graph | 执行阶段、重试、恢复、决策 | 改写 route 身份 |
| Writeback | 以 operation/run 维度幂等持久化 | 覆盖未接受 artifact |
| Read model/SSE | 投影事实和状态 | 通过事件顺序猜测业务完成 |
| Frontend | 展示 route、阶段、证据和动作 | 依据旧 `quality_mode` 猜测路线行为 |

### 4.2 冻结字段

每个真实运行在开始时必须冻结并可读出：

- `route_id`、`route_version`、`route_digest`
- `stage_order`、`stage_graph_digest`
- `provider_profile_id`、`provider_model`、`provider_base_url`（脱敏展示）
- `prompt_contract_version`、`context_digest`
- `image_acceptance_status=image_deferred`（仅当路线到达 CoverBrief 且未启动图片 operation）
- `run_seed`、`created_at`、`budget_policy`

## 5. 问题清单与优先级

| ID | 优先级 | 问题 | 根因 | 目标退出条件 |
|---|---|---|---|---|
| P0-01 | P0 | API catalog 仍返回旧 workflow id；新 route id resolve 失败 | `creation_wizard.py` 仍调用旧 `catalog_entries`，旧映射把 Phase32 当兼容层 | catalog 只返回三条 canonical route；新 id 可 resolve；旧 id 返回明确迁移错误 |
| P0-02 | P0 | 执行合同仍锁定 `phase27-vnext` 和旧 8 节点图 | `executable_contract.py` 与旧 runtime template 仍是执行权威 | 运行态只消费 Phase32 RouteSpec；旧模板不再可执行 |
| P0-03 | P0 | `source=None` 可能选择空 base_url 的文本 profile | profile 按 id 首条选择，未做可执行性筛选 | 未显式指定 profile 时只选择 enabled 且 base_url/model 完整的文本 profile；否则 fail-closed |
| P0-04 | P0 | `quality_mode` 与新 ReviewPolicy 语义冲突 | Fast/Balanced/Deep 仍以旧模板字段进入 UI/runtime | 官方入口不再暴露三种旧质量档；ReviewPolicy 成为唯一决策来源 |
| P0-05 | P0 | 图片延后状态没有统一业务语义 | Cover 文本和图片被同一阶段/完成态混用 | CoverBrief 可接受、CoverAsset 未启动；短长篇显示 `image_deferred`，不显示 completed |
| P1-01 | P1 | Short 时间线出现“仅剩一小时”等前后矛盾 | 缺少跨 artifact 时间线 ledger | 结构 blocker 为 0；所有 deadline/elapsed 关系可追溯到同一事实 |
| P1-02 | P1 | Screenplay 有重复意象、第三场过度解释 | 只有结构校验，没有文学冷读/重复检测 | 自动警告可见；人工冷读记录结论；不把警告伪装成通过 |
| P1-03 | P1 | Long 仅两章 smoke，不能代表长篇连续性 | 测试规模没有分层，缺少 accepted prefix 证明 | 至少完成短 smoke、标准多章和恢复场景三套证据 |
| P1-04 | P1 | 导出 API 对真实运行缺少完整证据 | Fountain 有持久化，short/long exports 为空，PDF/Markdown 只是 hash | 导出响应声明 artifact type、dependency、deferred 原因；不返回空成功 |
| P1-05 | P1 | Provider receipt 和重试证据分散 | transport、parse、writeback 没有同一 operation 视图 | 一次 operation 可看到 attempts、错误类、最终状态、写回版本 |
| P2-01 | P2 | 前端仍显示 Phase 27 和旧 ID 计数 | `officialWorkflows.ts`、模板页和 contract 未切换 | UI 只展示三条官方路线及文本/图片边界 |
| P2-02 | P2 | 构建产物 chunk 偏大，暂不阻断业务验收 | `CharacterGraph3D` 约 1.4MB，入口 JS 约 934KB | 建立 bundle 基线和懒加载计划；不与文本闭环混在同一波次 |
| P2-03 | P2 | 可观测性缺少质量维度 | 只有成功/失败，缺少 continuity warning、cold read 和成本状态 | run summary 有结构质量、连续性、文学警告、Provider 成本状态 |

## 6. 优化波次

### Wave 50：Canonical Route 收口

**目标**：让三条官方路线成为 API、runtime、UI 的唯一身份。

**主要改动**：

- 以 `phase32_creation_wizard.py` 和 `route_specs.py` 的三条 route 为 catalog 单一来源。
- 重写 `creation_wizard.py` 的 catalog/resolve 适配，不再把旧 workflow template 当官方列表返回。
- 为旧 `official-deepseek-*` 增加只读迁移提示；禁止新建、复制、执行和作为默认模板。
- 将 `workflow_ids.py`、`officialWorkflows.ts`、前端 `WorkflowTemplate` contract 改为 route id/route version 语义。
- 删除或归档旧 `phase27-vnext` 执行图的生产入口；测试 fixture 可以留在明确的 legacy 目录。
- UI 去掉 Fast/Balanced/Deep 作为官方模式标签，改为 route + review policy 的可解释摘要。

**验证**：

- API catalog 恰好三条 canonical route，顺序稳定，digest 稳定。
- `POST /api/creation-wizard/resolve` 对三条 canonical id 全部 200；旧 id 返回可诊断的迁移错误。
- 新建的 Run manifest 不包含旧 workflow id、`phase27-vnext` 或旧节点名。
- 前端 route 选择、summary、run 页面不再显示 Phase 27/旧档位。

**退出门禁**：P0-01、P0-02、P0-04 清零；离线全量测试通过。

### Wave 51：文本 Provider 绑定与图片延后合同

**目标**：真实 DeepSeek 调用必须显式、可审计、不会误选空配置；图片完全 fail-closed。

**主要改动**：

- Provider binding 只接受 enabled、类型匹配、`base_url`、model、凭据引用完整的文本 profile。
- `source=None` 不能简单取第一条记录；若没有唯一可执行文本 profile，直接返回可操作错误。
- 在 Run manifest 冻结 provider snapshot；后续 profile 修改不能改变已运行任务。
- 文本阶段 receipts 统一记录 `attempts`、`transport_status`、`parse_status`、`exact_object`、usage、redacted error。
- Cover 阶段拆出 `CoverBrief` 和 `CoverAsset` 语义：本轮只允许前者；图片绑定为空时状态为 `image_deferred`，不能创建图片 operation。
- 图片 pricing 缺失只作为延后原因和未来验收阻断，不得影响已完成文本阶段的真实性，也不得被显示成零成本。

**验证**：

- 空 base_url profile 不会被选中；故意没有可执行 profile 时测试得到 fail-closed。
- 同一 operation 的传输重试不创建重复 artifact；成功后重复 resume 不重复写回。
- 三条路线到达 CoverBrief 时均有明确 `image_deferred` 证据，Provider operation 列表中没有图片调用。

**退出门禁**：P0-03、P0-05 清零；Provider profile contract、recovery、image-deferred 测试通过。

### Wave 52：DeepSeek 文本稳定性验收

**目标**：在不调用图片 Provider 的前提下，完成三条路线的真实文本闭环小样本。

**运行协议**：

1. 每条路线使用新 `run_id`，记录 route digest、prompt contract、provider snapshot 和预算。
2. 先做 3 次固定低成本 probe，保存响应 hash、延迟、usage；hash 一致不等于质量通过，只作为稳定性信号。
3. 每条路线至少跑一次主链和一次故障恢复：
   - Screenplay：`brief -> cast -> beat_board -> scene_deck -> script`，完成文本侧导出。
   - Short：`brief -> story_map -> cast -> section_plan -> text -> CoverBrief`，停在 `image_deferred`。
   - Long：`brief -> book_architecture -> cast -> volumes -> rolling_detail -> text -> CoverBrief`，停在 `image_deferred`。
4. 人为注入一次 Brief transport error 或等价可控故障，验证同 operation 恢复、attempt 计数和最终写回。
5. 运行后保存完整 evidence bundle：manifest、events、receipts、artifact refs、writebacks、quality report、export response。

**通过条件**：

- 文本 operation 的最终响应均为合法结构化对象；解析失败不能静默降级为普通文本。
- 主链无未解释 pending operation；恢复链没有重复 artifact、丢失 accepted prefix 或跳过依赖。
- `exact_object`、writeback 版本、stage decision 与最终 read model 相互一致。
- Short/Long 的 CoverAsset 不存在，且 UI/API 明确标记 image deferred。
- 任何一次 Provider 失败都能按错误类别定位为 retryable、contract、budget 或 configuration。

**退出门禁**：三路线各一主链 + 一恢复链，全部证据可重放；图片调用数为 0。

### Wave 53：连续性与质量门禁

**目标**：把“能生成”升级为“前后可承接、问题可定位”。

**结构质量规则**：

- 每个 artifact 的 `source_refs` 必须指向已接受版本，不能指向 draft 或未来阶段。
- 角色、地点、时间、线索、目标、冲突等实体在相邻阶段有稳定 ID；名称变化必须有别名记录。
- 每个单元/章节/场景输出 `handoff_in` 和 `handoff_out`；下一单元只能消费上一单元的 accepted handoff。
- 时间线 ledger 记录绝对时间、相对时长、deadline、事件顺序和来源；矛盾为 blocker，不以模型解释覆盖。
- Long 的卷/章节层级必须通过既有 hierarchy validator，并额外校验 rolling detail 与已接受章节的边界。
- accepted prefix 明确展示；失败单元之后的内容不能被误算为已交付。
- Story Map 每个 anchor 必须推进至少一个稳定 ASCII `promise_ref`；Section Plan 每个 unit 必须承接已接受 Promise，且覆盖 Story Map 的全部 Promise。旧 Run 保留可读兼容形状，新候选在生产边界严格拒绝空引用或漏覆盖。
- Cast 中在多个 Story Map anchor 持续出现的行动者、对手或被追索对象必须登记；正文不得给未登记对象临时创造姓名、化名或别名，职能标签必须原样延续。
- Writeback transport recovery 必须复用同一 pending operation 及其 immutable Provider input snapshot；不得因 recovery counter 变化而遗留孤立 `pending` receipt。

**文学质量规则**：

- 自动检查重复短语、重复意象、连续场景的动作/情绪复用，只生成 warning，不伪造分数。
- 每条真实样本进行一次人工冷读，记录“可继续阅读/需要返工/阻断”及具体段落引用。
- Screenplay 特别检查场景目标、冲突升级、视觉可拍性和 reveal 是否过度解释。
- Short 特别检查 deadline、线索回收和章节间时间跳跃。
- Long 特别检查卷目标、章节 handoff、人物状态和远距离伏笔，不以两章 smoke 代表全书稳定。

**现有问题的验收样例**：

- Short 中“三天后晚上十点”与“距离失踪报告时间仅剩一小时”的矛盾必须被结构门禁拦截或修正，并在 report 中保留来源。
- Screenplay 第三场重复 storm/dim/wet 等意象、重复“低声”和过度解释 reveal，至少应作为冷读 warning 出现在报告中。

**退出门禁**：P1-01 的结构 blocker 为 0；每条路线都有冷读记录；Provider receipt 不得有未解释的 `pending`；warning 不会改变 completed/image_deferred 的事实语义。

### Wave 54a：写回首轮合同稳定性

**目标**：降低真实文本运行中 Evidence writeback 的首轮合同拒绝，且不牺牲 source-bound 证据边界。

**根因**：DeepSeek 官方文本模板使用 `json_object`，只能保证外层 JSON 语法；`Phase32EvidenceProposalBundle` 的 `span_ids` 嵌套 `max_length=3` 由本地 Pydantic 做最终拒绝，不能指望 Provider 端 schema 自动截断。Long r8 的首轮 payload 将一条 claim 的四个证据片段全部复制，合同纠正虽成功但返回了空 claims，造成可追踪事实丢失风险。

**已实施**：

- 在 `references/phase32_writeback_context.py` 的上下文开头和长上下文末尾都声明 `span_ids` 必须是 1、2 或 3 项，明确禁止复制全部 `source_spans`。
- 合同纠正提示在发现 `claims.*.span_ids` 超限时要求“只修改超限 claim、保留其他合同正确 claim”，避免把一次局部错误恢复成整包空写回。
- 保留 Pydantic 的硬上限和 `contract_rejected` receipt；不做静默截断、不改写 Provider 原始 payload、不把合同错误降级成 warning。
- 增加 Fake Provider 回归，证明首轮超限会留下可见 reject，第二次使用纠正提示并成功完成写回。

**验证**：

- `uv run pytest -q tests/test_phase32_writeback.py` → 17 passed。
- `uv run pytest -q` → 1160 passed，1 warning；`compileall` 与 `git diff --check` 通过。
- 新鲜 Long r9 与 Short r8 均已执行：首轮 reject 0、空 claims 纠正 0、pending 0、图片 operation 0；SSE 和冷启动读模型保持一致。

**退出门禁**：连续 Long/Short 文本样本的首轮 `span_ids` contract reject 降为 0，或每次出现都有明确可复现根因且纠正保留有效 claims；不得以最终 `image_deferred` 隐藏首轮质量损失。该门禁不替代长篇多章文学冷读。

### Wave 55：文本侧导出与交付状态

**目标**：让导出 API 返回“真实存在的产物和依赖”，不再用空列表表示成功。

**主要改动**：

- 导出响应增加 `artifact_type`、`source_artifact_refs`、`dependency_status`、`deferred_reason`；每个真实 item 继续提供 `sha256`、`size_bytes` 和生成时间。
- Screenplay 的 Fountain/Markdown/PDF 若已生成，必须逐项有文件存在性和 hash 证据；只有 hash 计算不能声明下载完成。
- Short/Long 在图片未验收时只允许返回 `text_preview`（如确有需求）；响应必须明确“不等于完整 BookDelivery”。
- 依赖 CoverAsset 的正式 export 返回 `409 image_deferred` 或等价业务错误，不返回空成功数组。
- read model、SSE 和前端下载按钮使用同一依赖判断，避免一个页面显示完成、另一个页面显示空。

**退出门禁**：P1-04 清零；所有导出结果都能由 run evidence 反查到真实文件或明确 deferred/blocked 原因。

### Wave 56：前端、浏览器和可观测性收口

**目标**：用户在真实操作中能理解三条路线当前做到哪里、为什么停下、下一步是什么。

**主要改动**：

- route 选择页展示阶段链、文本验收边界、图片延后说明和预计证据，不展示失真的旧质量档位。
- run 页面区分 active、accepted、retrying、blocked、image_deferred、completed；每个状态显示依据。
- Provider panel 展示 operation attempts、错误类别、是否 exact object、写回版本和成本状态；密钥永不回显。
- 运行详情支持从 stage 到 artifact、receipt、writeback、SSE event 的反查。
- 浏览器 smoke 覆盖：选择 canonical route、启动、查看连续事件、恢复、到 image_deferred、下载/阻止导出。
- 单独建立 bundle 基线和懒加载任务，不阻塞本轮文本验收；重点关注 `CharacterGraph3D` 和入口 chunk。

**退出门禁**：P2-01、P1-05 清零；浏览器主路径无假完成、无永久 loading、无旧身份文案。

**Wave 56 收口记录（2026-08-27）**：前端 72 files / 184 tests、TypeScript/Vite build、结构与 CSS audit、`git diff --check` 均通过；Screenplay、Short、Long 三条真实 Run 已完成浏览器 smoke。Short/Long 在图片未验收时均稳定呈现 `image_deferred`，不显示空文件或无效重试；Screenplay 可下载已冻结 Fountain。Smoke 发现并修复了交付 Hook 的 `Promise.all` 竞态（export artifact 404 会覆盖结构化 409），改为 delivery envelope 优先并补充回归测试。浏览器控制台保留的 `/exports` 409 是预期业务阻断，不属于未捕获异常。详见 [`phase-32-wave-56-frontend-delivery-contract.md`](phase-32-wave-56-frontend-delivery-contract.md)。图片生成和图片质量验收仍留在 Wave 57，未因本次文本闭环而提前放行。

### Wave 58：长篇 exact-12 连续性与质量证据硬门

**编号说明**：原定 Wave 57 是图片验收；按“图片暂不进入验收”的产品决定保持延期，因此文本线继续以 Wave 58 推进，不把图片波次伪装为已完成。

**目标**：在下一次真实 DeepSeek 长篇样本前，把 accepted prefix、恢复语义、验收规模、终态事件和人工冷读版本绑定变成持久合同，而不是依赖运行手册。

**已实施**：

- 私有 `continuity_acceptance` scale profile 冻结为单 Window、单卷、恰好 12 章；8/10/11/13 章、双 Window 和双卷样本在 Rolling Detail 接受边界失败。
- 公共项目创建不接受该私有 profile；正式 production 和既有 release-smoke profile 语义不变。
- Run Repository 在投影提交、读取和 journal 恢复时校验 state/read-model 的 active unit、Artifact refs 与 sequential progress 完全一致。
- 已接受 sequential prefix 不可缩短、替换、重排或删除；允许一次追加多个连续单元。
- Provider receipt 已 durable returned 后，进程重启复用同一 operation 和 immutable input，不再次调用 Provider；不对远端已处理但本地尚未记账的网络窗口宣称物理 exactly-once。
- `image.deferred` / `export.ready` 成为相斥的最终事件；终态重放与 SSE 重连不会新增业务事实。
- Graph 事件使用实际观测时钟，不再把运行、重试和终态全部记录为 definition 创建时间。
- 新增 append-only quality report sidecar，把结构 blocker 与文学 warning 分轨，并把人工冷读精确绑定到不可变正文/剧本版本。
- Continuity quality source digest 同时绑定当前 committed Rolling Detail 版本；一章/错序样本不能形成私有验收证据，规划换版会把旧报告标为 stale。没有可信 code-owned deterministic gate receipt 时，production accepted 保持 fail-closed。
- 新增无网络、无写入、完全脱敏的 Provider readiness report；可硬校验 canonical workflow、模型、profile kind、价格新鲜度、secret 可用性和零图片执行绑定。

**退出门禁（当前投影）**：Wave 58 要求的私有 launcher、强制持久 readiness、执行层预算、append-only attempt ledger、版本化 evidence bundle/verifier 与私有 release harness 已由 Wave 59–60 关闭；Wave 61 已取得新鲜 operator pricing attestation 和零费用环境报告。当前仍缺明确计费授权、真实 exact-12 和人工冷读证据，因此不能声明真实 Provider 稳定性或内容质量通过。未来真实样本仍须 12/12 正文与写回完成、pending 为 0、唯一终态为 `image_deferred`、图片 operation 为 0，并形成一次绑定完整 source digest 的人工冷读记录。

**证据范围**：Wave 58 只证明文本连续性基础设施和私有验收样本，不声明完整长篇 production acceptance。详细协议见 [`phase-32-wave-58-text-continuity-quality-gates.md`](phase-32-wave-58-text-continuity-quality-gates.md)。

### Wave 59：私有 Provider admission 与逐次传输预算

**目标**：把 Wave 58 的 exact-12 合同变成真实 Provider 调用前无法绕过的持久授权边界，同时不影响公共创建与普通 production/release-smoke Run。

**已实施**：

- domain/internal-only launcher 以显式幂等 key 准备官方长篇 exact-12 Run；按 key 的 POSIX 文件锁把 reservation、恢复、definition 创建和完成标记串行在同一临界区，可恢复进程中断且不会让并发冲突请求覆盖 winner；公共项目 API 不暴露 profile selector；
- readiness admission 固定 canonical、text-only、`deepseek-v4-pro`、`continuity_acceptance` 和 24 小时定价新鲜度，持久记录为脱敏 content-addressed fact；有效期不能超过 900 秒或剩余价格新鲜度；stage/report 语义校验拒绝伪造 ready verdict；
- readiness report 冻结期望 stage manifest，current verdict 与 definition 精确核对 stage 数量、顺序和 Provider identity；删减、增加、换序或替换阶段后重算 digest/ref 仍 fail-closed；
- bootstrap seed 保留 operator 已持久化的 model pricing，只补齐缺失默认项；代码默认 `2026-08-26` pricing 当前已 stale，不能形成真实调用放行；
- Run budget authorization 显式冻结美元、逻辑 operation、总 token 和 `max_transport_attempts=3`，并绑定 definition digest；Run 级文件锁防止并发超售；
- generation/writeback 在每次 transport claim/gateway 前取得 attempt admission；fence 完整绑定 authorization/Run/definition/operation/request/ref/attempt，并在 claim lock 内冻结 budget identity、追加 claimed admission ref；同 operation retry 不重复占 logical operation，但会再次占 token/成本；
- partial/矛盾 usage 不释放预留，Provider return 不能替换冻结 pricing identity；late terminal return 最多将一个未 claim 的 future grant 作为 implicit void 排除累计占用；
- preparation record 重算 request/profile digest 并绑定 idempotency/Project/Run/status；Run repository 用 Run 级跨进程锁恢复 create staging 与 journal 前 projection staging，进程硬退出不会永久阻断重试；
- start/resume、direct driver 和 writeback 均 fail-closed；持久 terminal receipt 或纯本地状态/决策 replay 不产生重复 Provider 调用，pending decision 也必须 exact command replay；start/decision API 用脱敏结构化 409/422 表达 readiness/authority/admission/budget 与 preflight 阻断，并明确给出 `retryable/retry_condition`；
- continuity acceptance 的 collaboration thread 创建与 turn 执行均被 `author_collaboration_unavailable` 拒绝；text-only readiness 与类型边界使图片调用不可达。

**证据范围**：本波只使用 Fake/spy/持久化与多进程中断测试；单次联合聚焦回归 276 passed，后端全量 1316 passed、1 warning。细分切片为 budget/generation/writeback 110、API + execution 52、launcher 41、Run repository 19、readiness/admission/continuity 29（集合有重叠）。真实 DeepSeek 调用为 0，真实图片调用为 0；它证明 admission、预算与本地恢复基础设施，不证明 DeepSeek 稳定性或文学质量。详见 [`phase-32-wave-59-provider-admission-and-budget.md`](phase-32-wave-59-provider-admission-and-budget.md)。

### Wave 60：版本化 evidence 与私有 release harness

**目标**：保存每次 transport attempt 的 append-only 证据，并在 Wave 59 已接通的唯一 production bootstrap/domain 链路上增加可停止、可冷验证的操作者 release candidate 适配器。

**已实施**：

- Provider operation receipt 在 claim/terminal lifecycle 的同一次原子写入中追加 content-addressed attempt event，记录 admission ref、时间、耗时、公开错误码与 lease owner hash；早期失败不被累计状态覆盖；
- evidence bundle 固定为 `phase32-continuity-evidence.v1`，以全内容 digest 寻址，递归拒绝 secret、URL、Prompt、request/result、原始 Provider payload 与 Artifact 正文；
- verifier 从当前冷态 stores 重新读取并投影 definition、readiness、budget/admissions、attempts、receipts、events、Artifacts、Evidence、writebacks、Canon/Wiki 和 quality reports；完整 canonical JSON 漂移或任一 closure issue 都阻断；
- closure rules 要求 exact-12 accepted prefix、12/12 writeback、零 pending/取消、冻结 Provider/pricing/input identity、每次 transport 与 admission/authorization 一一对应、完整 token/cost、零 image/collaboration operation、唯一 `image.deferred` 终态，以及绑定当前 12 个 source refs 且冷读结论为 `continue_reading` 的有效 quality report；
- 私有 harness 只持有 production services，不另组 store/gateway/graph；默认停在第一个 operator decision，只有显式 `auto_accept_stages` 可用于离线演练；
- Fake exact-12 在第 4、8 章后冷重启，最终 12/12 正文与 12/12 writeback，pending 0，image/collaboration operation 0，再次重建应用后 bundle 仍通过 `require_valid`；
- 旧式无 attempt event 的 receipt 保持兼容读取，但 release verifier 明确阻断；attempt elapsed 被篡改后即使重算 event ref 也无法通过 receipt 验证。

**证据范围**：专项 `6 passed`，Wave 60/Phase 32 联合回归 `223 passed`，后端全量 `1322 passed, 1 warning`。真实 DeepSeek 调用 0、图片调用 0。离线 Fake 证明工程连续性，不证明真实 Provider 稳定性或文学质量。详见 [`phase-32-wave-60-release-evidence-and-rehearsal.md`](phase-32-wave-60-release-evidence-and-rehearsal.md)。

### Wave 61（已完成）：真实 DeepSeek exact-12 零费用预检

**零费用证据**：已写入 24 小时内复核、可追踪的官方 peak 保守价格，并生成 immutable attestation 与脱敏 environment report；结果为 `ready_for_budget_authorization`，固定 0 Provider 调用。pricing 新鲜度不等于花费授权。

**完成结果**：操作者后续已显式授权 USD/operation/token 上限；Wave 62 已冻结全新 Run，并把 pricing/report/readiness/budget 绑定到同一候选授权清单。若后续执行时 pricing 超过 24 小时，仍必须重新 attestation。

**执行纪律**：只运行一个真实 Run；默认逐候选等待操作者。任一 readiness 过期、预算不足、未知 usage/cost、attempt 无 admission、合同连续失败、writeback needs_action、accepted prefix 漂移、pending 无法恢复、第二终态或图片/协作 operation 出现时立即停止，不自动换模型或扩大预算。

**退出证据**：12/12 immutable chapters 与 writebacks、完整 attempt/latency/token/cost/纠正记录、唯一 `image_deferred`、冷态 bundle ready，以及绑定同一 12 个 source refs 的真实人工冷读。缺少其中任何一项，只能报告阻断或部分结果，不能声明稳定性/质量通过。

### Wave 62–67（已完成）：真实 Exact-12 内容门与发布证据

**完成证据**：全新 Run 冻结用户确认预算与 live candidate authorization；在人工逐候选监管下完成 12 章、12 次正式写回和唯一 `image_deferred` 终态。完整 receipt、attempt、usage、quality 和 cold-process verifier 均绑定同一冻结 definition。

**质量结论**：结构 blocker 为 0，冷读结论为 `continue_reading`；但篇幅达成率仅 68.7%，12 章中 9 章需要定向换稿，仍有流程性重复与因果可信度 warning。因此“运行与连续性通过”和“文学成品未通过”必须并列展示，下一轮按 Wave 67 的质量优化项继续迭代。

### Wave 57（未来）：图片 Provider 重新进入验收

该波次不属于当前迭代，不得提前标记完成。只有在文本波次稳定后才启动：

- 图片 profile、模型、base URL、pricing、超时和预算通过 preflight。
- CoverAsset contract、二进制校验、尺寸/格式、hash、持久化和恢复通过。
- 图片 operation 的重试、幂等、取消、失败恢复和成本 receipts 通过。
- CoverBrief -> CoverAsset -> 正式 Export 的依赖链通过，并进行真实图片质量人工验收。
- Short/Long 才能从 `image_deferred` 进入 `completed`。

## 7. 测试与现场验收矩阵

| 层级 | 频率 | 必测内容 | 通过证据 |
|---|---|---|---|
| 纯函数/合同 | 每次提交 | route digest、artifact schema、时间线、hierarchy、provider profile | 单元测试和失败样例 |
| Runtime/Fake | 每次提交 | 三路线全图、决策、重试、恢复、幂等、image_deferred | pytest 全量和 route graph 报告 |
| API | 每次提交 | catalog/resolve/prepare、旧 id 拒绝、export dependency | HTTP fixture 或 API 集成测试 |
| 前端 | 每次提交 | canonical route 展示、状态映射、SSE、导出阻断 | Vitest、tsc、build、structure audit |
| 真实文本 Provider | 每轮发布候选 | 三路线主链、三 probe、一次传输恢复 | 脱敏 evidence bundle |
| 浏览器 | 每轮发布候选 | 真实用户路径和断点恢复 | screenshot/console/network 记录 |
| 图片 Provider | 当前不执行 | 仅确认没有被误调用 | operation 列表图片调用数为 0 |

### 7.1 真实 DeepSeek 运行的最小证据格式

每个 run 目录或等价存储必须包含：

- `manifest.json`：route/provider/prompt/budget/digest 快照；
- `events.ndjson`：SSE 或事件流，包含 seq、stage、operation、status；
- `provider-receipts.jsonl`：每次调用的 attempt、响应类型、usage、脱敏错误；
- `artifacts.json`：artifact id、version、status、source refs、hash；
- `writebacks.json`：写回目标、幂等 key、版本和时间；
- `quality-report.json`：结构 blocker、连续性 warning、文学冷读结论；
- `exports.json`：真实文件元数据或 deferred/blocked 原因；
- `run-summary.md`：人可以读的结论和未解决项。

禁止只保留最终文本而删除失败尝试、重试和中间状态；否则无法判断连续性和稳定性。

### 7.2 建议的最小样本量

- Probe：每条路线 3 次固定输入，观察 hash、延迟和 usage。
- 主链：每条路线至少 1 次新 run。
- 恢复：每条路线至少 1 次可控 transport/parse 故障恢复；若 parse 故障会破坏预算，应先在 Fake Provider 完成。
- 连续性：Screenplay 至少 3 场，Short 至少 3 个 section，Long 至少 2 章 smoke + 1 次跨章恢复；这些是最低门槛，不是规模保证。
- 冷读：每条路线至少 1 名评审或 1 次明确的人工审阅记录；自动指标不能替代该记录。

## 8. 质量门禁与指标

### 8.1 硬门禁（任一失败即阻断）

- canonical route id 不一致、旧 workflow id 进入新 Run manifest。
- stage graph/digest 在运行中漂移，或 artifact 消费 draft/未来版本。
- Provider profile 不完整仍发起调用，或调用结果未生成 receipt。
- 结构化响应解析失败却被当作成功；写回非幂等导致重复 artifact。
- accepted prefix 被跳过、失败后的单元被误标记为已交付。
- Short/Long 在没有 CoverAsset 时进入 `completed` 或正式 Export。
- 图片 Provider 在本轮产生任何真实 operation；本轮图片调用数要求为 0。

### 8.2 质量指标（用于趋势，不直接替代人工判断）

- text operation success rate、exact-object rate、parse failure rate；
- 首次成功延迟、重试后成功延迟、每 operation attempts 分布；
- accepted artifact/writeback 一致率、重复写回数、恢复后状态漂移数；
- continuity blocker 数、warning 数、跨 artifact 引用缺失数；
- 人工冷读结论和返工段落数；
- export 实体文件率、deferred/blocked 解释完整率；
- 未知成本状态数量（文本和图片分开统计）。

## 9. 迁移、保留、删除、归档矩阵

| 内容 | 处理 | 说明 |
|---|---|---|
| `official.screenplay_sample` / `official.short_novel` / `official.long_novel` | 保留并提升为唯一权威 | catalog、Run、UI、测试统一使用 |
| `official-deepseek-fast/balanced/deep` | 停止作为官方身份，迁移后归档 | 保留只读历史映射和数据迁移脚本，不可新建/执行 |
| `phase27-vnext` executable contract | 从生产入口移除 | legacy fixture 可留在隔离目录并显式标记 |
| `quality_mode` | 从官方产品语义移除或只读迁移字段 | ReviewPolicy/route contract 取代它 |
| CoverBrief 文本产物 | 保留并纳入当前验收 | 可作为 image_deferred 的终点 |
| CoverAsset 图片产物 | 暂缓实现验收 | 不生成、不伪造、不算完成 |
| 旧 UI 模板计数/Phase 27 文案 | 删除 | 避免用户误解实际路线 |
| 历史 run/artifact | 只读保留 | 迁移报表必须标明旧身份和不可重放原因 |

## 10. 风险与恢复策略

### 10.1 Provider 不稳定

- transport error：同 operation 有界重试，保留 attempts；超过预算则 blocked。
- parse/contract error：不得无限重试；记录原始脱敏响应和 contract diff，进入人工诊断。
- profile/config error：fail-closed，不切换到空配置或未冻结的隐式 profile。
- rate limit/timeout：按 provider error class 统计，不把延迟异常归为文学质量问题。

### 10.2 运行恢复

- 恢复入口必须以 `run_id + operation_id + stage` 定位，不以 UI 当前页猜测。
- 恢复前读取最后一个 accepted artifact 和 writeback version；只从下一个未接受阶段继续。
- 若 manifest digest 不匹配，禁止续跑，要求从新 run 重新开始。
- SSE 断线后通过 seq/cursor 补发，不能重复触发 Provider operation。

### 10.3 质量回退

- 出现结构 blocker 时，保留已接受 prefix，阻断后续 stage，不删除历史证据。
- 出现文学 warning 时可以继续，但必须在 run summary 和 UI 可见，并提供返工入口。
- 图片延后是显式业务状态，不是 error retry；不要因为图片暂缓而回滚已通过的文本 artifact。

## 11. 实施顺序与交付物

### 第一步：先修入口和身份（Wave 50）

交付：canonical catalog、resolve、旧 id 拒绝测试、前端路线 contract、迁移说明。

### 第二步：再修 Provider 和状态边界（Wave 51）

交付：可执行 profile 选择器、冻结 snapshot、统一 receipts、image_deferred contract、无图片调用断言。

### 第三步：跑真实文本证据（Wave 52）

交付：三路线新 run、probe、恢复 run、脱敏 evidence bundle、问题复盘。

### 第四步：修连续性、写回和导出（Wave 53-55）

交付：时间线 ledger、handoff checks、冷读记录、导出依赖语义和非空成功保证。

### 第五步：浏览器与发布候选验收（Wave 56）

交付：用户可理解的状态 UI、浏览器 smoke、console/network 证据、发布候选报告。

### 第六步：冻结 exact-12 连续性证据合同（Wave 58）

交付：单 Window/单卷/12 章 profile、accepted-prefix 持久硬门、durable-return 恢复、terminal singleton 和版本绑定的质量 sidecar。

### 第七步：冻结私有执行授权（Wave 59）

交付：跨进程可恢复的私有 launcher、语义防伪的持久 readiness、可跨重启保留的 operator pricing、definition-bound Run budget、cap=3 的 claim-fenced transport admissions、不可替换 pricing/usage fail-closed，以及 start/resume/driver/writeback/API/collaboration 旁路反例。

### 第八步：组装证据与发布 harness（Wave 60，已完成）

交付：append-only attempt ledger、版本化 evidence bundle/export verifier、私有 release harness、exact-12 Fake 双重启与故障证据演练；后端全量 1322 passed，真实 Provider 与图片调用均为 0。

### 第九步：真实文本候选与主体权威门（Wave 61–67，已完成）

已交付：新鲜可追踪 pricing attestation、Provider profile 原子 CAS/中断恢复、固定零调用的脱敏环境报告、全新冻结 Run、显式预算、候选授权清单、真实 Brief/Book Architecture 监制，以及由真实 Cast 暴露并完成本地修复的三路线主体权威人工门。

已交付：使用冻结 ReviewPolicy、Cast 与 Prompt revision 的全新预算授权 Run、后续 exact-12 阶段、完整稳定性统计、绑定 12/12 source digest 的人工冷读和冷态 ready bundle。历史失败 Run 保留为主体权威、引用合同和隔离修复的不可变回归证据。

## 12. Definition of Done

### 当前文本验收完成

- 三条 canonical route 可从 catalog 到 Run manifest；旧官方 id 不再进入新运行。
- 三条路线均有真实 DeepSeek 主链和可控恢复链，Provider receipts、artifact、writeback、SSE 可反查。
- Screenplay 到文本侧交付；Short/Long 到 CoverBrief 后稳定停在 `image_deferred`，没有图片 operation。
- 连续性结构 blocker 为 0；时间线、角色、章节/场景 handoff 有证据；文学 warning 和冷读结论可见。
- export 对真实文件、deferred 和 blocked 做出准确区分；不存在空成功。
- pytest、前端 tests/typecheck/build、浏览器 smoke 和 `git diff --check` 通过。

### 完整三档产品验收完成（未来）

- 在 Wave 57 通过真实图片 Provider、CoverAsset、成本和质量验收后，Short/Long 才能进入 `completed`。
- 完整导出包含所有必需文本和图片资产，所有文件可下载、可 hash、可恢复。
- 发布报告同时给出文本和图片两套 Provider 证据，不以文本稳定性替代图片质量。

## 13. 待决策项（不阻塞当前文档落地）

1. Short/Long 的 `text_preview` 是否作为独立产品能力发布；若不需要，则保留 API 的 `image_deferred` 阻断即可。
2. 人工冷读由内部编辑、产品或外部评审承担；无论由谁承担，都必须落到同一 `quality-report` 结构。
3. Wave 57 图片验收时是否沿用现有图片 endpoint；在定案前不得把当前 profile 当作可用生产 Provider。
4. bundle 优化是否与 Wave 55 同批，还是另立性能波次；不应为了 chunk 指标延迟文本闭环。

## 14. 参考与证据来源

本计划沿用仓库内现有权威文档和实现，不引入外部供应商快照：

- `docs/architecture/stage-artifact-contract.md`：阶段产物、决策、写回和读取边界。
- `docs/architecture/phase-32-three-creation-routes-reconstruction.md`：三条官方路线、路由阶段图和发布要求。
- `docs/engineering/phase-32-wave-49-real-provider-stability.md`：真实 DeepSeek 文本运行、失败恢复、图片 fail-closed 和当前质量观察。
- `docs/engineering/phase-32-wave-48-canon-wiki-writeback.md`：Fake Provider、canon/wiki/writeback 证据规则。
- `docs/engineering/phase-32-wave-58-text-continuity-quality-gates.md`：exact-12、accepted prefix、durable-return 与版本绑定质量证据。
- `docs/engineering/phase-32-wave-59-provider-admission-and-budget.md`：私有 launcher、持久 readiness 与逐 transport attempt 预算。
- `docs/engineering/phase-32-wave-60-release-evidence-and-rehearsal.md`：append-only attempt ledger、版本化 evidence、私有 harness、exact-12 离线演练与 Wave 61 放行顺序。
- `docs/engineering/phase-32-wave-61-live-candidate-preflight.md`：官方 pricing attestation、Provider CAS/中断恢复、零费用脱敏环境报告与待授权硬预算建议。
- `docs/engineering/phase-32-wave-62-live-exact12-brief-gate.md`：候选授权清单、真实 Brief receipt/成本/延迟、冷启动部分证据与人工内容门。
- `docs/engineering/phase-32-wave-63-cast-authority-gate.md`：Brief/Book Architecture 人工监制、真实 Cast 主体冻结断点、三路线 Cast 人工门与 v5 提示修复。
- `src/novel_workflow/workflows/route_specs.py`：三条 RouteSpec 的实现基线。
- `src/novel_workflow/workflows/review_policy.py`：路线级 mandatory stage 与 checkpoint 基线。
- `src/novel_workflow/workflows/phase32_provider_binding.py`：Provider 绑定和图片延后现状。
- `tests/test_creation_routes.py`、`tests/test_phase32_route_graph.py`、`tests/test_phase32_creation_prepare.py`：现有路线、图和图片延后测试基线。

任何与本计划冲突的旧模板、旧 UI 文案或历史报告，都必须先标明 legacy 身份，再决定是否迁移；不能反向成为新的产品权威。
