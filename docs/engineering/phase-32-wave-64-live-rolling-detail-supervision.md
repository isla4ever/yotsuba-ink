# Phase 32 Wave 64：Rolling Detail 真实监制、失败恢复与下一轮闭环方案

- **状态**：真实 Run 已按硬失败规则停止在 Rolling Detail；未进入 Text；未调用图片
- **日期**：2026-09-06（执行证据时间为 2026-09-05 UTC）
- **证据 Run**：`continuity-acceptance-run-a2c4903f135af471afbc`
- **冻结定义**：`bb182ec946a16c1f349e0485a11ea518627ade2c3764683075e83e51664c0f97`
- **模型**：`deepseek-v4-pro`

## 1. 监制边界与停止条件

本轮继续使用用户明确确认的冻结上限：

```text
max_cost_usd: 5.00
max_operations: 48
max_total_tokens: 2,000,000
max_transport_attempts_per_operation: 3
text_only: true
```

监制可以审读候选、提交源绑定人工草稿、接受合格候选以及在冻结策略内定向重生成；不得自动接受、扩大预算、调用图片，或在确定性硬失败后继续追加 Provider 调用。

本轮最终触发的是确定性合同失败，因此 Run 已停止。停止后执行的修复只处理本地状态、回执和测试，没有新增 Provider operation。

## 2. 已接受的上游权威

当前 Run 已原子提交：

```text
brief:
  p32-brief-committed-4f8638915f02b06acc89b56fe09659c28d747ca9c8a13da6c3a1204204a873ca
book_architecture:
  p32-book_architecture-committed-4dc9c2e892d3df5840d1ec3beefeb7a39121a8ca54a856a4bea4940695af23a5
cast:
  p32-cast-committed-f09ba8fa51acec27b390a0fbf783da231e5e47909d690f92fb6fb191ba47107d
volumes:
  p32-volumes-committed-906d354dd7d19922654da6837a9543368d3fb6ecf2839b0c470a039d04960349
```

首卷 `volume_01` 冻结为 37,500 字，只应完成第一封报告，并以第二封刚开始显影收尾。其 Cast 范围为 `protagonist / mentor / missing_01 / missing_02`。

## 3. Rolling Detail 三次真实结果

### 3.1 初次生成：输出截断

首次输出触及冻结的 6,000 token 上限，JSON 未闭合：

```text
receipt:
  p32-provider-operation-50d06e1422dcea57a0f70c9531fd878698db6fb18c32de620b2b722f3877cb90
status: contract_rejected
finish_reason: length
provider_code: output_truncated
usage: 6,980 prompt + 6,003 completion = 12,983
estimated_cost_usd: 0.03298548
```

该结果暴露出真实执行只有通用终态失败、没有显式合同失败恢复入口。Wave 64 已新增一个受冻结 ReviewPolicy、域版本、readiness、授权和预算共同约束的幂等恢复命令。

### 3.2 显式技术恢复：结构通过，编辑质量失败

恢复命令 `rolling-detail-truncation-recovery-wave64-1` 在同一 Run、同一预算下生成了一个完整候选：

```text
candidate:
  p32-rolling_detail-candidate-7520335381aed05c9e21ca540367a750-b43e9077
receipt:
  p32-provider-operation-b43e90776e9fa12881cab3e2ec451598e246077f62f3d9f2158f11c6021358cb
status: succeeded
usage: 7,340 prompt + 4,307 completion = 11,647
estimated_cost_usd: 0.02674452
```

结构层满足一个首卷 Window、12 章、37,500 字和每章一个场景，但人工审读判定不能接受：

1. 第一卷提前完成了第二封，越过“第二封刚开始显影”的卷尾边界；
2. 第七章提前使用冻结墨，并消耗终局保留的“导师交付修复刀”记忆；
3. 第十章写成报告会自动归档，违反“持证修复师主动完成归档”；
4. 第十二章进入第三封并出现首卷范围外的陆明川；
5. 自然语言出现周砚秋、陆明川时，Chapter Cast 引用没有同步登记；
6. Rolling Detail 人工草稿当时冻结 Chapter/Scene Cast scope，无法通过普通内容编辑补救。

因此候选没有被接受，也没有进入正文生成。

### 3.3 唯一编辑重生成：内容显著改善，合同门禁拒绝

在刷新 readiness 和 live authorization 后使用唯一剩余的编辑重生成：

```text
readiness:
  p32-provider-readiness-97b95995f0eb36a64aa650310761c9c3ba3650c764848f778bd27f8cc1bd7fa3
live authorization:
  p32-live-candidate-auth-b37040a303d0736e08e2a99a3af120211ce32aae656627c6498790650a1e28f4
receipt:
  p32-provider-operation-00873f2e2d642a0d3637f09484419a6f1b246812743c674c9d99337be434eee3
status: contract_rejected
finish_reason: stop
usage: 7,606 prompt + 4,102 completion = 11,708
estimated_cost_usd: 0.02628384
```

该输出完整、可解析，且满足：

- 一个 `window_volume_01`；
- `chapter_01` 至 `chapter_12`，总长度恰好 37,500；
- 每章一个单一地点/时间场景；
- 第一封只在第十章归档，第十一章验证失踪与记录保留；
- 第十二章只开始第二封，没有完成第二封或进入第三封；
- 未使用冻结墨，未提前消耗终局记忆，未写自动归档；
- 四个首卷 Cast ref 在 12 章联合范围内均有覆盖。

新确定性门禁仍正确拒绝了它：`chapter_01.handoff` 写出“沈砚”，但 `chapter_01.cast_subject_refs` 没有 `mentor`。这不是解析错误，而是自然语言名称与局部引用不一致。

人工复核还发现三个不应忽略的连续性问题：

1. 第一章 `hook` 已出现“周砚秋”，第三章却再次把姓名显影当成首次确认，信息揭示顺序冲突；
2. 第八章确认期限为三天后，第十章发生在第四日下午，且本卷明确没有使用冻结墨，时间账不闭合；
3. “不可篡改的时间戳”“周砚秋身份确认”等措辞把有限证据提升为过强结论。

即使只修正 `mentor` 引用，该候选仍不应直接进入正文。

## 4. 稳定性与质量结论

Run 最终用量：

| 指标 | 结果 |
|---|---:|
| Provider operations | 9 / 48 |
| returned | 9 |
| succeeded | 7 |
| contract rejected | 2 |
| transport failed / pending | 0 / 0 |
| prompt tokens | 41,964 |
| completion tokens | 22,113 |
| total tokens | 64,077 / 2,000,000 |
| conservative estimated cost | `$0.14295996 / $5.00` |
| image operations | 0 |

判断：

- **传输稳定性**：9/9 返回，当前样本没有网络或 Provider transport failure；
- **结构输出稳定性**：全 Run 合同成功率为 7/9；Rolling Detail 一次截断、一次成功落候选、一次语义合同拒绝；
- **编辑质量**：三次 Rolling Detail 中没有一个可直接进入正文，当前长篇链路尚未形成质量闭环；
- **连续性**：定向重生成能显著纠正宏观情节边界，但仍会在局部 Cast、揭示顺序和时间账上漂移；
- **成本**：远低于冻结预算，失败原因不是额度不足。

## 5. 本轮已实施的工程修复

### 5.1 显式合同失败恢复

- 新增 `POST /api/runs/{run_id}/recoveries`；
- 只允许终态 `provider_contract_failed`；
- 要求精确域版本、非空方向、幂等 recovery id；
- 受冻结 ReviewPolicy redraft limit 约束；
- 恢复前重新经过 readiness、live authorization 和预算 admission；
- 同一个恢复命令重放不产生第二次 Provider 调用。

### 5.2 Rolling Detail 确定性门禁

- continuity acceptance 只能规划首个 Volume prefix；
- 12 章联合 Cast 必须覆盖首卷冻结 Cast scope；
- 任一章节自然语言出现已注册 `display_name` 时，对应 `subject_ref` 必须在该章 Cast；
- 任一场景自然语言出现已注册 `display_name` 时，对应 `subject_ref` 必须在该场景 Cast；
- 章节允许的角色不自动成为场景允许的角色。

### 5.3 Prompt v6

Rolling Detail 提示合同升级到 v6，明确：

- `hook` 与 `handoff` 也属于当前章节 Cast 边界；
- 下一章才进入的人物只能用职能描述承接，不能提前写姓名；
- 场景字段只能写场景 Cast 对应姓名；
- 不得为了容纳越界姓名而虚增不参与当前单元的角色引用。

新提示只影响未来冻结的 Run，不改写当前 Run 的 v4 冻结定义。

### 5.4 终态决策一致性

真实失败后曾出现：State 已为 `failed`，ReadModel 却残留旧 pending decision，重生成决策回执也停在 `pending`。

现已修复：

- 非重试失败清空 pending decision；
- 失败的 regenerate 明确记为已消耗一次 redraft；
- 其决策回执以 `downstream_failure` 成功对账；
- 重放相同命令只修复旧投影，不进行 Provider 调用；
- recovery 同时考虑技术恢复次数和已消耗编辑重生成次数；
- 持久化合同禁止 `failed / cancelled / completed / image_deferred` 暴露 pending decision。

当前真实 Run 已完成无调用对账：Provider operations 在对账前后均为 9，pending decision 已清空，决策回执为 `succeeded`。

## 6. 下一轮优化方案

### P0：保持当前 Run 为失败证据，不再调用

验收条件：

- Run 保持 `failed / rolling_detail`；
- 失败码为 `provider_contract_failed`；
- pending decision 为 0；
- 图片与 Text operation 均为 0；
- operation 数保持 9。

### P1：建立“合同隔离候选 → 人工修复 → 再校验”通路

当前 Provider receipt 已保留完整 `raw_provider_payload`，但语义校验失败后没有可编辑 Candidate，导致一个局部错误必须重新付费生成整份 12 章规划。

下一步应新增显式、不可静默的隔离修复流程：

1. contract-rejected receipt 暴露稳定 `receipt_ref` 与红acted validation findings；
2. 仅当 raw payload 已通过 JSON Schema、失败属于可人工修正的跨字段语义合同时，允许创建 `quarantined_candidate`；
3. 人工修复必须绑定 Run、definition digest、receipt、stage、domain revision 和原始 payload digest；
4. 修复稿允许调整文学字段及同一冻结 Volume/Cast 注册表内的 Chapter/Scene Cast scope，但不能新增 subject、Volume、Chapter 或 Scene identity；
5. 修复后重新运行全部 schema、引用、规模与语言门禁；
6. 通过后只恢复到 `awaiting_decision`，仍需显式接受；
7. 全过程 Provider operation 增量必须为 0，并保留原拒绝回执和修复谱系。

这条通路不能自动把姓名塞进 Cast，也不能自动删改文本；系统只提供可审计的人工修复能力。

### P1：为 Rolling Detail 增加可验证的进度账

仅靠自由文本 `dramatic_job / exit_state / handoff` 无法稳定证明 Volume promise、climax、closure 和时间约束是否按章兑现。下一轮应先设计最小结构合同，再改 UI：

- 每章显式记录当前 `volume_ref` 下的进度动作类型，例如 `setup / test / irreversible_action / verify / handoff`；
- 对不可逆动作记录稳定目标引用和发生章，防止归档、失踪、冻结墨等事件提前或重复；
- 增加相对时间账或期限余额，不允许在没有延长期动作时越过冻结期限；
- Volume closure 必须由最后章的 exit/handoff 显式承接，不能在中段提前完成；
- 上游 Volume 自身也要检查 promise 与 climax 是否逻辑矛盾。本 Run 的“在不归档前提下证明归档因果”与“高潮实际归档”应在 Volumes 人工门被标记为措辞冲突。

在字段合同冻结前，不应通过页面填空或通用关键词扫描假装解决这些语义关系。

### P2：规划阶段质量侧车

现有质量报告只绑定已提交正文前缀，无法记录“Rolling Detail 为什么被人工拒绝”。应增加 planning review sidecar：

- 来源绑定精确 Candidate/receipt payload digest；
- 系统 blocker 与人工 editorial warning 分轨；
- 记录 Cast 越界、揭示顺序、时间账、认识论过度断言、Volume closure 漂移；
- 后续重生成或人工修复后旧报告自动标记 stale，但不可删除；
- 只有 planning blockers 清零且人工结果为 continue，才开放接受动作。

### P2：再开一个全新 exact-12 Run

只有 P1 完成并通过离线回放后，才申请新的明确预算授权。新 Run 的验收顺序：

1. Brief、Book Architecture、Cast、Volumes 逐阶段审读；
2. Volumes 先通过 promise/climax/closure 与时间逻辑检查；
3. Rolling Detail 必须一次形成完整 12 章，或通过零调用隔离修复收敛；
4. 先完成 Planning Review，再进入 Text；
5. 12 章正文逐章检查承接、事实、角色、时间、记忆代价和重复；
6. CoverBrief 可验收，但图片继续保持 deferred；
7. 最终以完整后端、前端、浏览器真实流程和 release evidence 收口。

## 7. 本地验证与终态复核

```text
targeted reference/failure/prompt contracts: 65 passed
relevant execution/API regression: 138 passed, 1 warning
backend full suite: 1342 passed, 1 warning
compileall: passed
git diff --check: passed
pipeline directory audit: passed
API adapter top-level audit: passed
```

唯一 warning 为既有 Starlette `TestClient` / `httpx` 弃用提示。当前环境未安装 `ruff` 可执行文件，因此没有把 Ruff 冒充为已运行门禁；Python 编译、完整测试和 diff whitespace 均已实际通过。

冷态重新读取真实 Run 后确认：

```text
status: failed
active_stage_id: rolling_detail
last event: stage.failed / rolling_detail.decision
pending decisions: 0
pending decision receipts: 0
provider operations: 9
text stage operations: 0
image operations: 0
collaboration operations: 0
```

`apps/web/src/features/pipeline` 只包含 AGENTS 允许的九个目录；`src/novel_workflow/api` 顶层只包含适配器合同允许的 `app.py / bootstrap.py / dependencies.py / sse.py / run.py / __init__.py`，业务路由仍集中在 `routes/`。

## 8. 当前验收结论

三档官方模式的基础编排与人工门已建立，但长篇官方模式仍未达到业务闭环：执行、预算、恢复、回执和确定性引用门已经闭合；Rolling Detail 的可修复性、进度语义与规划质量证据尚未闭合。

因此当前结论是：**DeepSeek 调用链稳定，长篇规划质量不稳定；不能进入 Text 验收，也不能宣称三档模式生产闭环。**
