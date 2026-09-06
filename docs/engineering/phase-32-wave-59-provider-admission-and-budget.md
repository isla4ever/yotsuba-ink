# Phase 32 Wave 59：私有 Provider Admission 与逐次传输预算

- **状态**：领域合同、持久防线、唯一生产装配、聚焦硬化与后端全量回归已完成；后续 Wave 60 release harness 与证据链也已落地
- **日期**：2026-09-05
- **适用范围**：`official.long_novel` 的私有 `continuity_acceptance` exact-12 文本验收
- **公共产品影响**：公共 `POST /api/projects` 仍不能选择该 profile；production 与 release-smoke 行为不变
- **图片边界**：不进入图片生成、图片 Provider、CoverAsset 或图片质量验收；本波图片调用数为 0

## 1. 本轮结论

Wave 59 关闭了真实 exact-12 文本样本前的三条高风险入口：私有 Run 的跨进程可恢复创建、可持久复核且不能伪造自相矛盾结论的 Provider readiness，以及每次真实文本传输前与下一次 claim 精确绑定的预算授权。它没有把验收 profile 暴露给公共创建 API；同一个私有 admission authority 已由 production bootstrap 装配到 execution、generation 与 writeback 的唯一正式链路。

当前可以声明：

1. exact-12 Run 只能从私有领域入口冻结为 `official.long_novel + long_novel + continuity_acceptance`；
2. readiness 是绑定 Run definition 与代码策略的持久、脱敏、会过期裁决，不是一次进程内布尔值；
3. 每个文本 transport attempt 在 claim 和 Provider gateway 之前都必须取得不可变预算 admission；admission fence 精确绑定 authorization、Run、definition、operation、request、admission ref 与 attempt；
4. continuity acceptance 的单 operation 传输上限由代码和 budget authority 共同冻结为 3；durable terminal receipt 的本地 replay 不产生新 admission 或 Provider 调用，真实 transport retry 则必须再次预留 token 与成本；
5. 作者协作不能创建验收线程，也不能借历史线程执行 Provider turn；
6. 图片执行不属于该私有服务可接收的请求类型，任何冻结图片绑定都会使 readiness 失败；
7. start/decision API 会把 admission/readiness/budget/preflight 阻断映射为脱敏、结构化的 409/422，而不是泄露内部异常或在阻断后创建 Driver/Provider operation。
8. Run 初次创建与 projection 提交已具备按 Run 的跨进程锁和 staging 恢复；在 journal 前硬退出不会再把同一 Run 永久卡在 stale staging。

当前不能声明：

- 已完成真实 DeepSeek exact-12 稳定性或文学质量验收；
- Provider 请求跨远端/本地持久化窗口物理 exactly-once；
- 已有可独立运行的 release harness 或完整 evidence bundle；
- `continuity_acceptance` 可以代表 production acceptance；
- 短篇/长篇已经完成图片与完整成书交付。

## 2. 私有 exact-12 启动边界

`Phase32CreationService.prepare_continuity_acceptance()` 是仅供 domain/internal 调用的创建入口。它要求：

- 显式 idempotency key；
- route 为 `long_novel`；
- workflow selection 为 `existing` 且 workflow id 精确等于 `official.long_novel`；
- 调用方提供的 project/run id 使用 `continuity-acceptance-` 命名空间；
- scale profile 冻结为单 Window、单卷、恰好 12 章。

preparation 的 request digest 同时包含 `profile_kind`，因此同一 idempotency key 不能跨 production、release-smoke 与 continuity acceptance 重放。preparation store 以 idempotency key 为粒度，把读取、reservation、恢复、Run definition 创建与 `mark_prepared` 放在同一个可重入事务临界区；POSIX 环境同时持有进程内锁与文件 `flock`。相同请求的并发进程只能复用持久 winner 的 request、ids 与 `created_at`，冲突请求不能覆盖 winner；若进程在 reservation 后或 Run definition 写入后中断，后续进程会沿现有 preparation/repository 权威恢复，不创建第二份 Run，也不调用 Provider。

preparation record 在读取和写入时重新计算 `profile_kind + request_payload` digest，并核对 payload/envelope 的 idempotency key、显式或确定性派生的 Project/Run id，以及 `reserved/prepared` 与 definition digest 的状态配对。修改 payload 却沿用旧 digest、替换 envelope id 或伪造状态的记录都会作为损坏记录 fail-closed，不能参与恢复。

Run repository 另以 safe Run id 持有可重入跨进程锁。初次创建若在 `definition/state/read_model` 任一 staging 写入后硬退出，冷进程只会复用完整且与目标 definition 精确一致的内部 staging，或清理已确认未提交、只含白名单内部文件的 partial staging 后重建；已提交 target、symlink、目录或未知文件绝不被清理或覆盖。

`Phase32ContinuityAcceptanceService.prepare()` 在上述 immutable Run 之外再冻结两项 operator authority：

- 绑定 `definition_digest` 的显式 Run budget；
- 绑定同一 definition 与代码策略的 readiness admission。

它没有默认花费额度。调用方必须显式提供美元、逻辑 operation 数和总 token 三项正数上限。

公共项目创建请求没有 `profile_kind` 字段，Pydantic 输入合同继续拒绝额外选择器；Wave 59 没有新增私有 profile 准备或预算授权 API。bootstrap 只注册 domain/internal-only authority，并把同一实例注入 execution、generation 与 writeback；既有通用 start/decision route 只能寻址已经持久化的 Run，仍必须通过这项 authority。

## 3. 持久 Provider readiness

### 3.1 代码所有的策略

私有策略固定要求：

| 字段 | 固定值 |
|---|---|
| canonical workflow | `true` |
| text-only | `true` |
| model | `deepseek-v4-pro` |
| profile kind | `continuity_acceptance` |
| pricing 最大年龄 | 24 小时 |
| admission 最大 TTL | 900 秒 |

调用方不能降低这些要求，也不能通过传入更宽松策略延长 admission。

### 3.2 持久与脱敏语义

readiness admission 保存 Run id、definition digest、policy/report digest、观测时间、过期时间、阶段级脱敏结论和 `ready/blocked` verdict。它不保存 API key、secret ref/value、base URL、请求、Prompt 或 Provider payload。

readiness 合同本身也执行语义防伪：stage 的 `ready` 必须与 `issue_codes` 等价，ready stage 必须同时具备 base URL、secret、可计价且新鲜的 pricing；report 必须聚合全部 stage issue，并重新核对价格年龄、required model、text-only/image absence 与总 verdict。report 还冻结期望 Provider stage manifest；读取 current verdict 时会与 Run definition 精确比对 stage 数量、顺序以及每阶段 provider profile/template/model identity。删除、增加、换序或替换阶段后即使重新计算全部 digest/ref，也只能得到 blocked verdict。构造“字段显示失败但 verdict=ready”或“图片/模型不匹配却漏报 issue”的记录会在持久化前被拒绝，不能仅靠伪造布尔值获得 admission。

有效期取以下两者的较早值：

```text
min(observed_at + admission TTL,
    observed_at + frozen pricing freshness remaining)
```

读取时只要发生 definition drift、policy drift、未来时间、`checked_at >= expires_at`、价格过期、blocked verdict、记录缺失或记录损坏，就 fail-closed。新的 blocked 观测不会被旧 ready 观测掩盖。

readiness store 使用 content-addressed immutable record，并以 Run 级 POSIX 文件锁串行化“同刻检查 + 写入”。同一 Run、同一 `observed_at` 的冲突裁决只能有一个成功，避免多进程依赖文件名排序选出随机 head。

readiness 只检查冻结配置和本地 secret 是否可解析，不建立网络连接，不创建 Provider input/operation，也不产生费用。

### 3.3 当前价格阻断

代码内 DeepSeek 默认 pricing 的 `verified_at` 是 `2026-08-26T11:43:02+08:00`；按本文复核日期已经超过私有策略允许的 24 小时，因此默认配置当前只能得到 stale readiness，真实 DeepSeek 调用仍被阻断。bootstrap seed 现在只补齐缺失的默认 model pricing，不覆盖持久 store 中已经存在的 operator pricing；操作者写入的新鲜、可追踪价格可以跨进程重启保留。新鲜价格仍必须先冻结进新的 Run definition 并形成新的 readiness admission，不能原地改写既有 Run 的冻结 pricing snapshot。

## 4. 逐 transport attempt 预算

### 4.1 授权与预留

Run budget authorization 是 content-addressed immutable authority，绑定：

- `run_id` 与 `definition_digest`；
- `max_cost_usd`；
- `max_operations`；
- `max_total_tokens`；
- code-owned `max_transport_attempts=3`；
- 授权时间与 USD 币种。

每次文本 generation 或 writeback transport attempt 都用冻结 request、binding 与新鲜价格计算保守上界：输入侧以 Prompt/schema 的 UTF-8 bytes 加固定 framing allowance 估算，输出侧使用冻结 `max_tokens`。未知或非正价格不能形成 admission。

预算 store 在一个 Run 级文件锁事务中同时读取授权、历史 admissions 与 Provider receipts，然后决定是否写入下一条 immutable admission。授权缺失、definition 不匹配、request signature 漂移、attempt 序列断裂、receipt 没有对应 admission、真实 usage/cost 不可知、调用方 retry cap 与冻结 authority 不一致、下一 attempt 超过 3 或任一总上限将被突破时，都拒绝下一次传输。

预算 admission 返回的 fence 不是“已经预算过”的泛化布尔值，而是完整身份：`authorization_ref + run_id + definition_digest + operation_key + request_signature + admission_ref + transport_attempt`。Provider operation store 在自己的 claim lock 内核对这组身份，并在第一次预算 claim 时冻结 receipt 的 definition/budget identity；跨 Run、跨 operation、跨 request、跨 authority 或过期 attempt 的 fence 都不能增加 `transport_attempts`，更不能进入 gateway。

### 4.2 计数语义

- 第一次传输为 `transport_attempt=1`，同时占用一个 logical operation slot；
- 同一 operation 的 transport retry 保持 operation key/request signature 不变，不重复占 logical operation slot；
- 每次 retry 都新增独立 attempt admission，并再次预留 token 与成本；
- 每次成功 claim 都把 admission ref 顺序追加到 receipt 的 `transport_admission_refs`，其数量必须与已 claim 的 `transport_attempts` 完全一致；
- failed attempts 保留其保守预留；
- 最终 returned/succeeded/contract-rejected receipt 只有同时具备一致的 `prompt_tokens`、`completion_tokens`、`total_tokens` 和已知成本时，最终 attempt 才以真实消费替换对应预留；partial 或矛盾 usage 一律 fail-closed，不释放保守预留，也不允许下一次 admission；
- operation 在未来 attempt grant 写入后收到上一 claim 的 late durable return 时，只允许存在一个未 claim 的尾随 grant；该 immutable grant 作为 implicit void 排除出累计占用，两个以上 future grants 视为冲突；
- `record_return` 必须使用 operation 开始时冻结的 pricing snapshot ref 及 provider profile/template/model identity，不能用更便宜或不同来源的价格重算历史成本；
- 不允许通过 retry、重启或并发进程复用旧 admission 绕过累计上限。

这一区分避免了“重试不增加 operation 数”被错误解释成“重试免费”。

### 4.3 调用顺序

对 continuity acceptance 的文本 generation/writeback，权威顺序是：

```text
读取持久 definition
  -> 校验当前 readiness + budget authority
  -> 冻结 Provider input / logical operation receipt
  -> 为目标 transport attempt 取得 budget admission
  -> 在 operation lock 内用完整 admission fence claim pending receipt
     （此时才冻结 budget identity、追加 admission ref 并增加 transport_attempts）
  -> 调用文本 Provider gateway
  -> durable return / contract / usage / cost
```

预算拒绝可以留下 `pending + transport_attempts=0` 的审计 receipt，但不得进入 claim 或 gateway。这是“已有本地 operation 证据”，不是“Provider 已被调用”。

## 5. Start、Resume 与 replay 语义

`Phase32RunExecutionService` 只对 `continuity_acceptance` 启用私有 Run admission：

- start/resume 真正进入新 graph step 前，先读取并预检持久 Run，再要求当前 readiness 与匹配的 budget authority；
- 未注入 admission callback、admission 缺失/损坏/过期或 definition drift 时，在 driver 创建前 fail-closed；
- production 与 release-smoke Run 不进入该私有分支；
- 已在持久 frontier 的 start replay、已成功 decision replay 和只需本地对账的 pending decision，不会为了“检查状态”产生新 Provider admission 或调用；pending/succeeded decision 在进入本地 reconcile 前仍必须精确核对原始 command，同一 decision identity 下的不同 action/payload 会稳定冲突，不能被误当作 replay；
- 直接调用 Driver 也不能绕开边界：没有 text-operation admission 时，在 Provider input/operation 创建前拒绝；
- generation 与 writeback 每次即将重新 claim 传输时都会重新 admission。
- Run projection 的完整读取、提交与 journal 恢复共用同一 Run 级跨进程锁；若进程在 state/read-model staging 写入后、journal 写入前退出，冷读取保留上一份完整 projection，回收已确认的内部 staging，并允许下一次提交继续。并发 event commit 只能形成一个一致 projection/event 序列，不会产生 mixed pair 或双 sequence=1。

Provider receipt 的恢复承诺保持 Wave 58 的精确定义：durable `returned/succeeded/contract_rejected` 后只做本地 replay；若远端已经处理但本地尚未 durable 记录 return，恢复可能再次传输，并必须以新的 transport attempt admission 计入预算。不得把这一语义写成跨网络物理 exactly-once。

现有 `POST /api/runs/{run_id}/start` 与 `POST /api/runs/{run_id}/decisions` 共用这条 admission 路径。readiness 过期、continuity authority 缺失、execution admission 未配置和 budget store 损坏映射为带稳定 `code/retryable/retry_condition` 的脱敏 409；Run definition/projection preflight 拒绝映射为脱敏 422。响应不回显 secret、base URL 或内部损坏 payload，并且这些阻断都发生在 Driver、Provider input、Provider operation 与 gateway 之前。

## 6. Collaboration 与图片隔离

### 6.1 作者协作

continuity acceptance 是受控基线，不允许用自由协作修改样本：

- `create_thread` 每次从 repository 读取 definition，并在解析 source/context 或写 thread 前返回稳定错误 `author_collaboration_unavailable`；
- `execute_turn` 同样重新读取 definition，并在 collaboration executor、Provider input 与 Provider operation 之前拒绝；
- 即使磁盘上存在旧线程或人工构造的 queued turn，也不能由该 service 触发 Provider；
- 普通 production Run 的既有 collaboration 行为不变。

### 6.2 图片链路

本波图片不仅“不计入验收”，也不属于私有 launcher 的可达能力：

- readiness 强制 `text-only`，冻结定义出现任何 image execution binding 即 blocked；
- budget admission 只接受 `Phase32ProviderRequest` 与 `Phase32WritebackProviderRequest`，没有 image request 入口；
- 私有 profile 仍沿既有 CoverBrief → `image_deferred` 语义结束，不能形成 CoverAsset 或 `export.ready`；
- Wave 59 没有新增公共 launcher API；只有受控 domain/operator 入口能准备该 profile，公共创建请求不能选择它；已经持久化的私有 Run 即使通过通用 start/decision API 被寻址，也必须通过同一 readiness/budget admission，不能绕过私有门禁；
- 任何 image operation 数量大于 0 都是停止条件，而不是可忽略 warning。

## 7. 本轮实现矩阵

| 能力 | 权威文件 | 关闭的风险 |
|---|---|---|
| 私有 exact-12 prepare | `orchestration/phase32_creation_service.py`、`storage/phase32_creation_preparation_store.py` | 公共档位误选、非官方 workflow、重复/半写 Run |
| Run create/projection 恢复 | `storage/phase32_run_repository.py` | 进程硬退出遗留 staging、冷启动永久阻断、跨进程 mixed projection/event |
| admission 聚合服务 | `orchestration/phase32_continuity_acceptance.py` | readiness、定义与预算由不同调用方松散拼接 |
| 持久 readiness | `providers/phase32_readiness_contract.py`、`orchestration/phase32_provider_readiness_admission.py`、`storage/phase32_provider_readiness_store.py` | 进程内布尔值、伪造矛盾 verdict、过期价格、策略漂移、同刻竞态 |
| operator pricing seed | `api/bootstrap.py` | 应用重启用过期代码默认值覆盖操作者新鲜价格 |
| 预算合同与事务 | `usage/phase32_run_budget_contract.py`、`usage/phase32_run_budget.py`、`storage/phase32_run_budget_store.py` | 重试免费、超额后补账、并发超售、definition/request 漂移 |
| attempt claim fence 与 pricing identity | `providers/phase32_admission.py`、`storage/phase32_provider_operation_store.py` | admission/claim TOCTOU、跨身份复用、partial usage 释放额度、late return 污染预算、返回时替换定价 |
| start/resume gate | `orchestration/phase32_execution_service.py` | admission 前创建 driver 或推进 graph |
| generation/writeback gate | `runtime/graph/phase32_driver.py`、`orchestration/phase32_writeback.py` | 直接 driver/writeback 绕过、retry 不重新预留 |
| HTTP 错误投影 | `api/routes/runs.py` | 私有 gate 退化为 500、错误详情泄露 secret/URL、阻断后仍创建执行副作用 |
| collaboration 隔离 | `orchestration/phase32_author_collaboration.py` | 自由对话改写受控样本、历史线程旁路 |

## 8. 验证记录

Wave 59 的实现和文档阶段只运行本地 Fake/spy/持久化测试，没有调用真实或计费 Provider。以下数字是已经完成的聚焦切片；测试集合有重叠，不能相加。后端全量结果由主任务在最终整合后回填。

| Gate | 建议命令 | 结果 |
|---|---|---|
| launcher / public isolation / POSIX multiprocessing | `uv run pytest -q tests/test_phase32_creation_prepare.py` | `41 passed` |
| Run create/projection crash recovery | `uv run pytest -q tests/test_phase32_run_repository.py` | `19 passed` |
| readiness report + admission + continuity | `uv run pytest -q tests/test_phase32_provider_readiness.py tests/test_phase32_provider_readiness_admission.py tests/test_phase32_continuity_acceptance.py` | `29 passed` |
| budget/claim fence/pricing + generation/writeback | `uv run pytest -q tests/test_phase32_run_budget.py tests/test_phase32_provider_operation_leases.py tests/test_phase32_provider_cost_sidecar.py tests/test_phase32_continuity_acceptance.py tests/test_phase32_driver.py tests/test_phase32_writeback.py` | `110 passed` |
| start/resume + API 409/422 | `uv run pytest -q tests/test_phase32_execution_api.py tests/test_phase32_execution_service.py` | `52 passed` |
| collaboration isolation | `uv run pytest -q tests/test_phase32_author_collaboration.py tests/test_author_collaboration_api.py` | `17 passed` |
| architecture allowlist | `uv run pytest -q tests/test_phase26_boundaries.py` | `15 passed` |
| Wave 59 consolidated focus | 本表全部相关文件的单次联合命令 | `276 passed` |
| backend full suite | `uv run pytest -q` | `1316 passed, 1 warning` |
| compile / whitespace | `uv run python -m compileall -q src tests`、`git diff --check` | `通过` |
| real DeepSeek calls | 不执行 | `0` |
| real image Provider calls | 不执行 | `0` |

## 9. 后续状态：Wave 60 已完成离线证据与演练

Wave 60 已按本节原定边界完成 append-only transport attempt ledger、版本化脱敏 evidence bundle、冷态 verifier 和复用 production authority 的私有 release harness。Fake exact-12 已在第 4、8 章后重建应用并继续到 12/12 正文与 12/12 writeback，最终唯一终态为 `image_deferred`，image/collaboration operation 均为 0；再次冷启动后 bundle 仍可通过 `require_valid`。

Wave 60 后端全量为 `1322 passed, 1 warning`，真实 DeepSeek 与图片调用均为 0。代码默认 `2026-08-26` pricing 仍已过期，且没有本次真实计费授权，因此真实 exact-12 稳定性与文学质量仍未验收。完整实现、阻断矩阵和下一步受控实测顺序见 [Wave 60 发布证据与离线演练](phase-32-wave-60-release-evidence-and-rehearsal.md)。
