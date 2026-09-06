# Phase 32 Wave 58：长篇 12 章连续性与质量证据硬门

- **状态**：实现完成，离线门禁通过；尚未发起新的 DeepSeek 计费调用
- **日期**：2026-09-05
- **适用路线**：`official.long_novel`
- **私有验收档**：`continuity_acceptance`
- **图片边界**：不进入图片生成、图片 Provider、CoverAsset 或图片质量验收；图片 operation 必须为 0

## 1. 本轮结论

历史两章 `release_smoke` 和十章真实运行已经证明了基础传输、结构化响应、写回与 `image_deferred` 终态，但它们不能证明正式长篇所需的滚动连续性。Wave 58 因此先关闭真实 12 章调用前的五个证据缺口：

1. 持久层必须拒绝 accepted prefix 缩短、替换、重排或跨 state/read-model 漂移；
2. 私有验收样本必须是单 Window、单卷、恰好 12 章，不能拿更小 fixture 冒充；
3. Provider 返回成功后的进程重启不得再次调用同一逻辑 operation；
4. `image.deferred` / `export.ready` 最终事件必须全 Run 唯一，SSE 重连只回放事实；
5. 人工冷读和文学 warning 必须绑定到不可变正文版本，并与系统 blocker 分轨保存。

这些门禁已进入代码与 Fake Provider 回归。当前仍不把 Wave 58 声明为“长篇生产文学质量通过”，也不立即消耗新的 DeepSeek 样本；真实调用要等私有启动入口、成本硬上限和证据包导出再完成一次发布候选级预检。

## 2. 为什么旧证据不够

| 旧证据 | 已证明 | 不能证明 |
|---|---|---|
| Long release-smoke 2 章 | canonical route、正文写回、终态和零图片调用 | 跨 12 章状态延续、accepted-prefix 扩展 |
| Long 10 章历史运行 | 多章生成具有可行性 | 当前正式最小滚动窗口；版本锁定后的恢复行为 |
| decision boundary 重启 | 已接受决策可恢复 | Provider 已返回、Artifact 尚未写入窗口的恢复 |
| 最终 read model | 最终状态可读 | state/read model 是否可能共同回退或相互漂移 |
| 人工文档冷读 | 有人工观察 | 观察是否绑定到确切 Artifact 版本、是否已过期 |

正式生产长篇 profile 的滚动窗口是 12–40 章。Wave 58 的私有档只选择其最小合法窗口 12 章，用最小成本验证连续性基础设施；它不改变正式产品 profile，也不向公共创建 API 暴露。

## 3. 冻结验收合同

### 3.1 身份与规模

真实样本必须同时满足：

- workflow：`official.long_novel`；
- route：`long_novel`；
- scale profile kind：`continuity_acceptance`；
- scale policy：`length.long_novel.continuity_acceptance.v1`；
- Rolling Detail：一个 Window、一个 volume ref、12 个连续 chapter ref；
- text model：冻结为预检指定的模型，不允许运行中切换；
- 图片执行绑定缺席，Cover 只生成文本 `CoverBrief`；
- 最终业务状态：`image_deferred`，不得写成完整成书 `completed`。

公共 `POST /api/projects` 不接受 `profile_kind=continuity_acceptance`。这条档位只允许由后续私有验收入口构造，避免用户生产请求意外落入测试规模。

### 3.2 accepted prefix

对 `text` sequential stage，设冻结单元序列为：

```text
chapter-01 ... chapter-12
```

提交后的 `committed_artifact_refs` 必须始终是该序列的连续前缀。持久层要求：

- 已提交键不得删除；
- 已提交值不得替换为另一个 Artifact ref；
- `ordered_unit_refs` 不得改变；
- 一次提交可以追加一个或多个连续单元；
- state 与 read model 的 active unit、Artifact refs、sequential progress 必须一致；
- projection journal 恢复也执行同样的单调校验，旧 journal 不得覆盖更新前缀。

这是一条存储不变量，而不是仅靠 Graph 调用顺序维持的约定。

### 3.3 Provider 恢复语义

本项目能保证的是“同一个逻辑 operation/receipt 的持久恢复”，不是跨网络边界的物理 exactly-once：

- Provider 响应已经持久为 `returned`/`succeeded` 后，重启必须复用该 receipt 和 immutable input snapshot，不再调用 Provider；
- Provider 请求已被远端处理、但本地尚未持久返回值的极短窗口，恢复时仍可能重试传输；
- 因此证据报告必须写“durable return 后不重调”，不得宣称无法证明的全局物理一次性；
- 重试不得改变 operation identity、冻结输入 digest 或 accepted prefix。

### 3.4 最终事件与 SSE

`image.deferred` 和 `export.ready` 被视为相斥的最终事件：

- 完全相同的最终事件重放返回原事件；
- 同一 Run 的第二个不同最终事件直接拒绝；
- 进程重启后再次投影终态不能新增 terminal event；
- 新事件记录实际 UTC 观测时间，不再把所有事件回填成 Run definition 创建时间；
- SSE 按持久 sequence/cursor 回放，重连不触发 Provider 或业务写入。

## 4. 质量证据合同

### 4.1 两条质量通道

| 通道 | 来源 | 效果 | 示例 |
|---|---|---|---|
| `system/block` | 确定性合同、结构或完整性检查 | 阻断接受 | accepted prefix 不完整、来源版本错误 |
| `advisory/warning` | 人工文学判断 | 提示返工，不自动改业务状态 | 重复意象、节奏松散、解释过度 |

文学 warning 即使标记为 `critical` 仍然是 advisory；系统不得把主观文学判断伪装为确定性 blocker。反过来，人工冷读也不得覆盖真实结构 blocker。

### 4.2 不可变来源绑定

每份 quality report 保存：

- definition digest；
- frozen ordered unit refs；
- 每个已接受单元的 Artifact ref、payload digest 和 ordinal；
- continuity 样本当前 committed Rolling Detail 的独立 planning binding（Artifact ref、kind、payload digest）；
- 整个 accepted-prefix snapshot 的 source digest；
- 人工 reviewer、结论、摘要和记录时间；
- warning 指向正文精确 code-point offset，剧本则指向精确 block index/kind/offset。

报告采用 append-only supersession chain。正文前缀增长、正文 Artifact 版本变化，或同一 12 章顺序下 Rolling Detail 内容/版本变化后，旧报告保留但投影为 stale，不能静默覆盖历史判断。

### 4.3 验收范围隔离

`production`、`release_smoke`、`continuity_acceptance` 是三个不同 evidence scope：

- 只有 `production` scope 能记录 production acceptance；
- `release_smoke` 与 `continuity_acceptance` 必须保持 `production_acceptance_status=not_evaluated`；
- 当前 service 尚未装配可信 code-owned deterministic gate receipt，因此即使 production prefix 完整，也会拒绝写入 `accepted`；调用方不能注入或清空系统 blocker；
- 12 章私有样本可以证明连续性工程门禁和形成冷读证据，但不能单独宣称整部长篇生产验收通过。

## 5. 无网络 Provider 预检

新增 readiness report 只读取冻结定义、绑定与本地 secret 可用性，不创建 operation、不写 receipt、不发网络请求。它逐 stage 校验：

- canonical workflow；
- route provider stage 顺序；
- provider binding digest 与 schema；
- base URL 是否存在，但不回显 URL；
- secret 是否可解析，但不回显 secret ref 或值；
- 文本定价字段完整；
- pricing verification age 不超过指定阈值；
- structured-output mode 可确定；
- 模型与私有 profile kind 符合本次协议；
- 所有 stage 的 image execution 都缺席。

当前仓库中的定价核验时间已不足以支撑 2026-09-05 的新真实运行。真实调用前必须在 24 小时窗口内重新核验价格，并把核验来源与时间冻结进 Run；不能把未知或过期价格当作 0。

## 6. 本轮实现切片

| 切片 | 核心文件 | 已关闭风险 |
|---|---|---|
| accepted-prefix 持久硬门 | `storage/phase32_run_repository.py` | projection/journal 回退、state/read-model 漂移 |
| exact-12 私有 scale | `workflows/phase32_scale.py`、`workflows/graph_run_definition.py` | 小 fixture 冒充正式滚动窗口 |
| Rolling Detail 接受边界 | `orchestration/phase32_stage_reference_validation.py` | 8/10/11/13 章或双卷样本进入正文 |
| durable-return 恢复 | `tests/test_phase32_long_chapters.py` | 已返回响应在重启后重复调用 |
| terminal singleton / event clock | `storage/phase32_graph_event_sink.py` | `image_deferred` 与 `export.ready` 双终态、事件时序失真 |
| quality sidecar | `quality/phase32_quality_report.py`、`storage/phase32_quality_report_store.py`、`orchestration/phase32_quality_review.py` | 冷读不绑定版本、warning/blocker 混用 |
| redacted readiness | `orchestration/phase32_provider_readiness.py` | 未验证配置就产生计费调用或敏感信息泄露 |

这些切片没有接入图片执行，没有复用 `artifacts_vnext`，也没有把质量 sidecar 写回核心 Artifact 或 Graph 控制状态。

## 7. 离线验证矩阵

最终交付前至少运行：

```text
tests/test_phase32_run_repository.py
tests/test_phase32_long_chapters.py
tests/test_phase32_graph_execution.py
tests/test_phase32_fixture_integration.py
tests/test_phase32_scale.py
tests/test_phase32_driver.py
tests/test_graph_run_definition.py
tests/test_phase32_creation_prepare.py
tests/test_phase32_provider_readiness.py
tests/test_phase32_quality_review.py
```

关键反例必须覆盖：

- accepted prefix shrink / replace / reorder / remove；
- state/read-model Artifact、active unit、progress 漂移；
- journal 试图恢复旧前缀；
- 8/10/11/13 章、双 Window、双卷拒绝；
- 恰好 12 章单 Window/单卷接受；
- durable returned receipt 重启后零 Provider 重调；
- 重启与 SSE 重连后 terminal singleton；
- stale price、缺 secret、错模型、图片绑定存在时 readiness fail-closed；
- incomplete prefix 形成系统 blocker；
- prose/screenplay 冷读 anchor 不匹配时拒绝；
- 私有 evidence scope 冒充 production acceptance 时拒绝。

### 7.1 实际验证结果

- Wave 58 十个直接相关测试文件：`130 passed`，1 个既有 Starlette/httpx 弃用 warning；
- 后端全量：`1199 passed`，同一既有 warning；
- `python -m compileall -q src tests`：通过；
- `git diff --check`：通过；
- exact-12 Fake 演练在第 4、8 章后重建 Repository、Artifact store 和 Driver，最终 12/12 accepted prefix 完整、12 个 operation key 唯一、每个一次 transport attempt、图片调用为 0；
- 一章 continuity、正文顺序与 Rolling Detail 不一致、调用方伪造系统 blocker、无可信 gate receipt 的 production accepted 均 fail-closed；Rolling Detail 换版会让旧质量报告投影为 `source_changed`；
- 首轮全量回归暴露两个 fixture/边界清单未同步问题，已修复后重新执行全量并通过；没有降低新的持久一致性校验。

## 8. 下一次真实 DeepSeek 运行协议

只有以下预运行门全部为绿才允许启动：

1. 全量后端回归与 `compileall`、`git diff --check` 通过；
2. 生成新的、唯一的 release candidate run id；
3. 通过 private continuity launcher 冻结 `continuity_acceptance` 定义；
4. readiness 指定 `deepseek-v4-pro`、`continuity_acceptance`、text-only，并返回 ready；
5. 所有定价在运行开始前 24 小时内核验；
6. 持久化目录完成写入、fsync、重开读取探针；
7. 成本 guard 已在执行层硬阻断，而不是只写在操作说明中；
8. evidence bundle 能从被冻结的 Run 导出，不靠人工复制临时终端输出。

### 8.1 成本与 operation 上限

按当前路线估算：

- 6 个规划 generation operation；
- 12 个 chapter generation operation；
- 12 个 chapter writeback operation；
- 无纠正时基线约 30 个逻辑 operation；
- 每个 writeback 最多允许一次有解释的合同纠正时，上限约 42；
- 预计总量约 16–17 万 tokens、约 `$0.29–0.31`；
- 建议硬成本上限 `$0.40`，达到上限立即停止，不启动图片或自动切换模型。

这里的价格只是基于最近冻结费率的运行预算草案。真实开跑前必须用新鲜核验价格重新计算，若结果超过硬上限则停止并重新规划，不能靠事后汇总补救。

### 8.2 恢复注入点

受控运行至少在以下位置重启服务：

- chapter 4 接受并完成 writeback 后；
- chapter 8 接受并完成 writeback 后；
- 另选一个 Provider receipt 已 durable returned、候选尚未提交的位置进行故障注入。

每次重启后检查：definition digest 不变、accepted prefix 原样保留、下一个 active unit 正确、returned operation 不重调、pending operation 数可解释、SSE sequence 连续。

### 8.3 最终断言

- 12/12 chapter 均有唯一 committed Artifact ref；
- 12/12 writeback 均 source-bound 且幂等；
- 逻辑 operation identity 无重复，所有 pending 均为 0；
- state/read model、Artifact store、receipts、outbox、events 相互一致；
- 只有一个 `image.deferred` 最终事件，没有 `export.ready`；
- image operation 为 0，正式 Export 仍返回明确的图片依赖阻断；
- quality report 绑定 12 章完整 source digest，并包含一次真实人工冷读；
- evidence scope 为 `continuity_acceptance`，不声明 production acceptance。

## 9. 停止条件

遇到任一情况立即停止，不继续烧 Provider 预算：

- readiness 不是全绿、定价过期或成本无法确定；
- frozen definition/profile/model 与运行协议不一致；
- Rolling Detail 不是单 Window、单卷、12 章；
- accepted prefix 缩短、替换、跳号或 state/read-model 漂移；
- durable returned operation 被再次调用；
- contract correction 超过一次或产生空 claims；
- 出现无法解释的 pending receipt/outbox；
- 出现第二个最终事件、事件 sequence 不连续；
- 产生任何图片 Provider operation；
- 成本达到硬上限。

## 10. 剩余实现与放行顺序

Wave 58 代码硬门完成后，真实运行前仍有五个工具缺口：

1. **私有 continuity launcher**：从 canonical long route 构造并持久化 exact-12 定义，不暴露给公共 API；
2. **强制且持久的 readiness admission**：当前 readiness 只读且无调用点；必须在 Run start 前校验并保存脱敏裁决、观测时间和所用定义摘要；
3. **执行前/执行中成本 guard**：当前成本只在响应返回后汇总；必须按新鲜费率冻结最大美元、调用数和 token 授权，并在每次 operation admission 前按累计消费硬阻断；
4. **append-only attempt ledger**：Graph event 已改为实际观测时间，但当前 receipt 更新仍只保留累计 attempts，成功可能覆盖早先 transport 诊断；首次真实稳定性样本前必须保存每次尝试的开始、结束、错误类与耗时；
5. **版本化 evidence bundle exporter**：当前 quality/readiness 也尚未装配到 production bootstrap；必须导出 definition、readiness/budget verdict、events、attempts、receipts、Artifact refs、writebacks、quality report 和 summary，同时保持 prompt、URL 与 secret 脱敏。

完成顺序固定为：launcher → readiness admission → cost guard → attempt ledger → bundle exporter 与 production 装配 → Fake Provider 12 章演练 → 新鲜配置预检 → 一次新的真实 DeepSeek 受控运行 → 人工冷读。前三项未完成前不得产生 Provider 费用；第四项未完成前不得采集会被称为“稳定性验收”的真实样本；第五项未完成前不得声明正式 exact-12 验收完成。图片能力继续保持 deferred，不与这条文本验收混跑。

## 11. 本轮不作出的声明

- 不声明 Provider 请求跨网络边界物理 exactly-once；
- 不声明 12 章私有样本等于 10–20 万字整书文学验收；
- 不声明自动 warning 可以替代人工冷读；
- 不声明 `image_deferred` 等于完整成书交付；
- 不声明过期价格、估算成本或旧真实 Run 可以代替新鲜 release candidate；
- 不进入图片生成或图片质量验收。
