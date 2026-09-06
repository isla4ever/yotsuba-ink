# Phase 32 Wave 60：发布证据、冷态验真与 Exact-12 离线演练

- **状态**：离线工程闭环与 Wave 61 零费用环境预检已完成；真实 DeepSeek exact-12 与人工文学质量验收尚未执行
- **日期**：2026-09-05
- **适用范围**：`official.long_novel + long_novel + continuity_acceptance` 私有文本验收
- **公共产品影响**：无新增公共 API、无 profile selector、无 UI 入口；普通 production/release-smoke 行为不变
- **Provider 边界**：真实 DeepSeek 调用 0，真实图片调用 0
- **图片边界**：Run 只能以 `image_deferred` 结束；任何 image operation 都使 evidence verifier 阻断

## 1. 本轮结论

Wave 60 已把 Wave 58/59 的连续性、readiness、预算和恢复部件组装成一条可审计、可冷启动复核、默认等待操作者决策的私有发布候选链。现在可以在不调用真实 Provider 的前提下证明：同一 production bootstrap 中的官方 exact-12 Run 能穿过规划、12 章正文、12 次 writeback、Canon/Wiki、质量记录与终态，重启后仍由同一组持久 authority 恢复，并形成一个内容寻址、脱敏且可重新计算的 evidence bundle。

当前可以声明：

1. 每次 Provider transport claim 与 terminal 结果都有原子追加的 attempt event，累计 receipt 不再覆盖早期失败；
2. bundle verifier 从冷态当前权威重建证据，缺失、漂移、旧式无 attempt 证据的收据、未知成本、待决状态或越界 operation 都 fail-closed；
3. 私有 harness 复用 production repository、execution、admission、budget、Provider operation、Artifact、writeback、Canon/Wiki 和 quality stores，没有第二套运行时；
4. 默认 stop policy 不自动接受候选；只有显式列入 `auto_accept_stages` 的阶段才可用于离线演练自动推进；
5. exact-12 Fake 演练在接受 4 章、8 章后分别关闭并重建应用，最终保持 12/12 单调 accepted prefix、12/12 committed writeback、pending 为 0、唯一终态为 `image_deferred`；
6. bundle 在再次重建应用后仍可通过冷态验证，且没有保存 secret、URL、Prompt、request、原始 Provider payload 或 Artifact 正文。

当前仍不能声明：

- 真实 DeepSeek 在 exact-12 长链中的稳定性、延迟、真实 token/cost 或合同一次通过率；
- Fake 文本具备文学质量，或离线 `continue_reading` 记录等同于真实编辑冷读；
- 跨远端处理与本地 durable return 窗口的物理 exactly-once；
- `continuity_acceptance` 等同 production acceptance；
- 图片、CoverAsset 或完整成书交付已通过。

## 2. 唯一权威链路

私有 harness 只协调既有 production authority，不复制业务规则：

```text
operator request + explicit budget
  -> Phase32ContinuityAcceptanceService.prepare
  -> persisted definition/readiness/budget authorization
  -> Phase32RunExecutionService.start_or_resume / decide
  -> Phase32RouteDriver
  -> Provider input + operation receipt + attempt events
  -> Artifact candidate -> operator decision -> committed Artifact
  -> Writeback outbox -> Evidence -> Canon -> Wiki
  -> image_deferred singleton terminal
  -> quality report bound to exact committed source refs
  -> evidence exporter -> immutable bundle store
  -> cold rebuild + verifier
```

`api/bootstrap.py` 只实例化并注入 `phase32_release_evidence`、`phase32_release_evidence_store` 和 `phase32_release_harness`。没有增加 route，也没有让公共项目创建选择 `continuity_acceptance`。harness 持有 service 引用，不持有独立 repository、gateway、graph 或 budget 算法。

## 3. Append-only transport attempt 证据

### 3.1 事件合同

`Phase32ProviderTransportAttemptEvent` 支持四类 content-addressed 事件：

| 事件 | 记录时机 | 关键字段 |
|---|---|---|
| `claimed` | admission fence 在 receipt lock 内成功 claim | Run/operation/request/attempt、admission ref、lease owner hash、观测时间 |
| `lease_expired` | 旧 claim 的租约在下一次 claim 前确认过期 | 同一 attempt 身份、结束时间、elapsed ms、公开错误码 |
| `transport_failed` | gateway 未形成 durable return | 同一 attempt 身份、结束时间、elapsed ms、脱敏错误码 |
| `provider_returned` | Provider payload 已 durable 写入 receipt | 同一 attempt 身份、结束时间、elapsed ms |

事件和 receipt lifecycle 在同一次 JSON 原子替换中提交，不依赖第二个 ledger 文件，因此不会产生“receipt 已 claim 但 ledger 未写”或反向 split-brain。lease owner 只保存 SHA-256 摘要；异常只保存稳定公开错误码。

### 3.2 顺序与兼容边界

读取 receipt 时会校验：

- attempt 从 1 连续递增；
- 每次 attempt 恰有一个 `claimed` 和一个 terminal event；正在持有有效 lease 的最后一次 claim 允许暂时没有 terminal；
- claim/terminal 的 Run、operation、request signature、attempt、admission ref 和 owner digest 一致；
- terminal 时间不早于 claim，`elapsed_ms` 与两个观测时间一致；
- event ref 与完整公开 payload 的 digest 一致且不可重复；
- claimed admission 顺序与 receipt 的 `transport_admission_refs` 完全一致。

为保持历史 receipt 可读，Wave 60 之前没有 event history 的记录仍可由 store 读取；但最终 evidence verifier 会以 `transport_attempt_evidence_incomplete` 阻断，不能把兼容读取误当成发布通过。

## 4. 版本化脱敏 evidence bundle

### 4.1 合同与存储

bundle 版本固定为 `phase32-continuity-evidence.v1`，`bundle_ref` 是除自身外全部 bundle 内容的 canonical digest。store 只允许幂等写入完全相同的内容；同 ref 不同内容会冲突。导出的对象包括：

- definition 的身份、route/profile 与冻结 Provider binding 摘要；
- readiness admissions；
- Run budget authorization 与逐 attempt admissions；
- transport attempt events；
- 脱敏 Provider receipt；
- Run event 元数据及 payload digest；
- Artifact 元数据及完整 record digest；
- Evidence、writeback、Canon/Wiki transaction 的身份与 digest；
- 绑定当前 accepted sources 的 quality report 摘要；
- closure summary、计数、token/cost 和 issue codes。

bundle 不包含 `api_key`、secret、base/source URL、headers、Prompt、request、result、原始 Provider payload 或 Artifact 正文。合同对所有嵌套 key 递归检查，出现禁用字段即拒绝构造。

### 4.2 冷态 verifier

`verify(run_id, bundle_ref)` 不信任 bundle 自带结论。它按 bundle 的 `generated_at` 重新读取并投影当前持久 authority，再以 JSON canonical 形式比较完整重建结果；任何 authority 增删或内容变化都会增加 `evidence_authority_drift`。`require_valid` 只有在原 summary 与冷态重建都为 ready 时返回。

最终 ready 至少要求：

| 维度 | Fail-closed 条件 |
|---|---|
| Run 身份 | 官方长篇、`continuity_acceptance`、definition 无漂移 |
| Readiness | admission 当前有效，策略、stage manifest、Provider identity 和价格均匹配 |
| 正文 | 恰好 12 个 ordered units，accepted prefix 完整，12 个 committed Text Artifacts 存在 |
| 决策 | 没有 pending decision |
| Writeback | 每个已接受章节恰有一个 committed receipt；无 pending、cancelled 或 accepted prefix 外来源 |
| Canon/Wiki/Evidence | source Artifact/digest/unit、evidence refs、fact refs、transaction 和 projection 互相匹配 |
| Provider identity | 每个 receipt/input 都匹配冻结 profile、template、model、pricing snapshot 和 binding digest |
| Attempt/budget | 每个 succeeded receipt 至少一次 transport；claim/terminal、admission、authorization、request signature 一一对应 |
| 用量 | terminal usage 完整、cost 已知，operation/token/USD/attempt 均未超过授权 |
| 越界能力 | image operation 为 0，collaboration operation 为 0 |
| 终态 | Run 为 `image_deferred`，且只有一个 `image.deferred` terminal event |
| 质量记录 | 最新 continuity report 精确绑定 12 个当前 source refs，accepted prefix 完整、deterministic blockers 为 0，且冷读结论为 `continue_reading` |

任一条件不满足时仍允许导出一个 `blocked` bundle，便于审计失败原因；但不能通过 `require_valid`。

## 5. 私有 release harness

`Phase32ReleaseHarness` 提供三个内部动作：

1. `prepare`：必须显式传入预算，没有默认美元、operation 或 token 额度；
2. `advance`：通过正式 execution service 推进，并根据 stop policy 在操作者决策、失败、终态或 transition 上限处停止；
3. `finalize_evidence`：导出 bundle，并立即要求冷态可验证的 ready 结论。

默认 stop policy：

- `auto_accept_stages=()`，第一个候选即返回 `awaiting_operator`；
- `stop_before_image=true`；
- `stop_on_failure=true`；
- 有界 `max_graph_transitions`；
- writeback recovery 只有显式打开才会重试。

任何已存在的 image/collaboration operation history 也会让 harness 停止。离线测试可显式列出允许自动接受的阶段，但这个测试便利不会改变默认操作者语义，也没有被做成公共接口。

## 6. Exact-12 离线真实流程模拟

演练使用 production `create_app()` 与同一 bootstrap，只把 Provider gateway 替换为可计量 Fake：正文规划强制生成 12 章，所有文本 generation/writeback 返回完整 token usage，图片方法若被调用会直接使测试失败。

执行结果：

| 检查点 | 结果 |
|---|---|
| 默认策略首个 Brief 候选 | 停在 `awaiting_operator`，仅 1 次文本请求 |
| 第一次冷重启 | accepted prefix 为 4/12 |
| 第二次冷重启 | accepted prefix 为 8/12，前 4 个 refs 不变 |
| 最终正文 | 12/12 committed，前 8 个 refs 不变 |
| Writeback | 12/12 committed，pending 0 |
| Provider receipts | 全部 succeeded，attempt 数等于 budget admission 数 |
| 终态 | `image_deferred`，terminal event 恰好 1 |
| 越界 operation | image 0，collaboration 0 |
| 冷态 bundle | 关闭并重建应用后 `require_valid` 通过 |

另有独立 attempt 故障测试验证 `claimed -> transport_failed -> claimed -> provider_returned` 的完整顺序，以及篡改后重新计算 event ref 但 elapsed 不一致仍会在 receipt 读取时失败。质量反例还会在追加 `revision_recommended` 冷读后重新导出 bundle，并确认 release-ready 结论被阻断。

本演练证明的是业务状态与证据连续性，不是文学质量。测试中的 quality report 明确写入“离线 Fake exact-12 仅验证系统连续性，不代表真实文学质量”，以防测试结果被误读为内容验收。

## 7. 验证记录

| Gate | 命令/范围 | 结果 |
|---|---|---|
| Wave 60 contract/rehearsal | `uv run pytest -q tests/test_phase32_release_evidence.py` | `6 passed` |
| split + ledger/budget focus | release evidence、operation leases、Run budget | `39 passed` |
| Phase 32 联合回归 | evidence、continuity、leases、cost、budget、driver、writeback、long chapters、quality、execution、API、repository、boundaries | `223 passed` |
| backend full suite | `uv run pytest -q` | `1322 passed, 1 warning` |
| warning | Starlette `TestClient` 的既有 `httpx` 弃用提示 | 非本轮功能失败 |
| real DeepSeek calls | 未执行 | `0` |
| real image calls | 未执行 | `0` |

## 8. 业务闭环判断

截至 Wave 60，三档官方模式共用的 Phase 32 文本生产路径没有被本轮分叉；剧本、短篇、长篇既有回归全部保持通过。Wave 60 专门补齐的是长篇 `continuity_acceptance` 发布前的审计闭环，因此结论分三层：

- **代码与离线状态闭环：通过**。exact-12 可以从私有准备到 `image_deferred`，可重启、可写回、可导出证据、可冷验真。
- **真实 Provider 稳定性闭环：未通过/未执行**。当前没有新的真实 DeepSeek exact-12 数据。
- **内容质量闭环：未通过/未执行**。Fake 只证明合同与连续性，必须由真实正文和绑定 source digest 的人工冷读补齐。

这意味着系统已经具备“安全开始一次受控真实验收”的基础设施，但尚不具备“宣称真实 exact-12 已稳定、质量已达标”的证据。

## 9. 下一迭代：Wave 61 真实文本候选放行计划

Wave 61 的零费用部分已经完成：官方 pricing 已在 24 小时窗口内复核并生成 immutable attestation，本地环境报告为 `ready_for_budget_authorization`，且 Provider/图片调用均为 0。详情见 [Wave 61 真实文本候选零费用预检](phase-32-wave-61-live-candidate-preflight.md)。

真实 Run 不自动开始。只有操作者明确授权真实计费后，按以下顺序执行：

1. **绑定零费用证据**：使用当前 pricing attestation 与 environment report；如果进入执行时已超过 24 小时则重新复核，不复用过期报告。
2. **显式预算授权**：操作者给出本次 USD、logical operation、total token 三项上限；保持每 operation 最多 3 次 transport，不自动扩大额度。
3. **冻结新 Run**：预算确认后重新 prepare，让新 pricing snapshot 与授权进入 immutable definition；不得原地修改旧 definition。
4. **最终零调用门**：把 pricing、environment、readiness、definition 和 budget 绑定为同一候选授权清单，再确认 image/collaboration 不可达、公共 API 未暴露私有 profile。
5. **单次真实 exact-12**：只执行一个 Run；默认逐候选等待操作者，是否批量接受某一阶段必须显式列入 stop policy。
6. **实时停止条件**：价格/readiness 过期、预算不足、未知 usage/cost、attempt 无 admission、合同连续失败、writeback needs_action、accepted prefix 漂移、pending 无法恢复、第二终态或任何图片/协作 operation 出现即停止。
7. **稳定性报告**：统计每个 generation/writeback 的 attempt 数、失败类、elapsed ms、token、成本、合同纠正次数与恢复点，不以最终 succeeded 掩盖中途失败。
8. **人工冷读**：对 12/12 immutable source refs 写入真实 reviewer、结论、结构 blockers 与文学 warnings；Fake reviewer 记录不能复用。
9. **冷态签收**：关闭进程、重开 stores、导出最终 bundle 并执行 `require_valid`；只有 bundle ready 且人工结论可接受，才可声明一次真实 continuity acceptance 完成。

图片仍留在独立 Wave 57，不因真实文本通过而自动启用。完整短篇/长篇成书交付仍必须等待 CoverAsset 与图片质量验收。

## 10. 实现索引

- `storage/phase32_provider_attempt_ledger.py`：append-only attempt event 合同与验证
- `storage/phase32_provider_operation_store.py`：attempt event 与 receipt lifecycle 原子提交
- `output_contracts/phase32_release_evidence.py`：版本化、脱敏、content-addressed bundle
- `storage/phase32_release_evidence_store.py`：immutable bundle store
- `orchestration/phase32_release_evidence.py`：authority 收集、投影、导出与冷态重建
- `orchestration/phase32_release_evidence_validation.py`：最终 fail-closed closure rules
- `orchestration/phase32_release_harness.py`：私有操作者适配器与停止策略
- `api/bootstrap.py`：唯一 production authority 装配
- `tests/test_phase32_release_evidence.py`：故障证据、默认停点、exact-12 双重启与冷态验真
