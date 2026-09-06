# Phase 32 Wave 62：真实 Exact-12 Brief 人工门

- **状态**：首次真实 Brief 技术门通过；候选随后经人工定向编辑接受，后续 Cast 断点见 Wave 63
- **日期**：2026-09-05
- **Run**：`continuity-acceptance-run-b49b9d28c1bc05cfe57d`
- **范围**：`official.long_novel + continuity_acceptance + deepseek-v4-pro`
- **图片状态**：图片调用 0；写回调用 0；协作调用 0

## 1. 用户授权与执行边界

用户明确确认本次单个 exact-12 候选的硬上限与题材：

```text
creative_intent:
  一名档案修复师收到十二封来自未来的失踪报告。

max_cost_usd: 5.00
max_operations: 48
max_total_tokens: 2,000,000
max_transport_attempts_per_operation: 3
```

本授权不包含图片，不代表允许自动接受文学候选。Release stop policy 保持默认：首个 Brief 候选产生后立即停止，只有用户接受或提交编辑稿后才可进入 Book Architecture。

## 2. 第一次调用前补齐的授权闭环

Wave 61 已有 pricing attestation、environment report、Run readiness 与 budget，但四者此前没有形成一个独立、不可变的最终候选授权对象。本波在 Provider 调用前新增 `phase32-live-candidate-authorization.v1`：

```text
pricing attestation + zero-call environment report
  + frozen definition/input/pricing snapshot
  + current readiness admission
  + immutable Run budget
  -> content-addressed live candidate authorization
  -> continuity admission
  -> execution / Driver / Gateway
```

授权清单绑定 Run、definition digest、environment/pricing/profile refs、readiness admission/report digest、budget ref 与四项限额，并固定 `text_only=true`、`billable_call_count_at_issue=0`。执行校验已下沉到 continuity admission；即使绕过 release harness 直接调用 execution API，缺清单或配置漂移也会在 Driver/Gateway 创建前返回结构化 409。

实现保持职责分离：environment/pricing 仍由 `phase32_live_candidate_preflight.py` 负责，Run 授权编排独立位于 `phase32_live_candidate_authorization.py`。拆分后相关模块分别为 395 与 186 行。

## 3. 冻结身份

```text
definition_digest:
  d9b5c7ab3c58816eef21402d87bc05572ba7325f954e500863ba14701bb3af82

readiness_admission_ref:
  p32-provider-readiness-e53a3684315b922e75d966170ca904ff0eeafbc5d4911dca7f26779def44be3f

budget_authorization_ref:
  p32-run-budget-29afa24579b388f9a55d9345cc8e6435443163a7b1b9d45af4045d2cba4cfbd6

candidate_authorization_ref:
  p32-live-candidate-auth-b7ea035aec54243b20ff62908846c1d24012355aaceacc5fc6c084af4653dc37

environment_report_ref:
  p32-live-preflight-6d2b51d85611e0aded174ea05f0a2c687c6cedfe14c9a4d477e0390011d6a1ae

pricing_snapshot_ref:
  p32-provider-pricing-f31bb0fd3473588deb431b89ad676e80858ff8c0d495a3c26d6c9fd4171ce5eb
```

冻结完成后、启动前 Provider operation 数为 0。

## 4. 真实 Brief 调用结果

| 指标 | 结果 |
|---|---|
| logical operation | 1 |
| transport attempts | 1 |
| attempt event | `claimed -> provider_returned` |
| transport elapsed | 13,983 ms |
| prompt tokens | 792 |
| completion tokens | 384 |
| total tokens | 1,176 |
| conservative estimated cost | `$0.00256608` |
| finish reason | `stop` |
| structured parse | 1 object / 1 schema match / 0 repairs / 0 parse errors |
| Provider pending | 0 |
| image/writeback/collaboration operation | 0 / 0 / 0 |

Receipt：

```text
p32-provider-operation-ab5f504461c710d4af9595b897f314cdf34db575482e73ed15f7070cc6401eeb
```

候选 Artifact：

```text
p32-brief-candidate-64f04e1263b9dc65c96e371522639970-ab5f5044
payload_digest:
64f04e1263b9dc65c96e37152263997008812baea7eeb39b60a0aa8b5ab85faa
```

Run 当前为 `awaiting_decision / brief`，允许动作只有 `accept` 或 `cancel`，`domain_revision=0`。

## 5. Brief 内容审读

候选标题为《失物之书：未来来函》。核心前提把“修复档案”变成会反向写入现实的行为，第十二封指向修复师本人；第一人称、克制观察与记忆代价能支持长篇的证据追踪和心理耗损。题材识别度、职业动作、十二封结构钩子和终局方向均达到继续开发的最低质量。

当前没有 Schema、字段、语言或确定性引用 blocker，但有三项应在 Brief 接受前处理的文学/设定 warning：

1. **规则自相矛盾**：候选同时写“修复后不可逆”与“除非销毁未来记录源”，需要明确销毁发生在修复完成前还是完成后；
2. **终局因果缺口**：拒绝修复第十二封为何导致档案馆崩塌和时间线重置，当前规则没有提供触发机制；
3. **表达偏泛**：`audience_promise` 的“智性小说、推理快感、情感冲击”较模板化，标题也偏类型通用，不影响合同但会削弱作品辨识度。

建议选择“定向编辑后接受”，只修订 Brief 的 world rules、ending direction、audience promise 和标题，不改变核心题材、第一人称声音、十二封结构或 15 万字目标。该编辑属于用户决策层，不应由系统自动接受或隐藏换稿。

## 6. 冷启动与部分证据

关闭本次进程并重新初始化 production stores 后：

- Run 仍为 `awaiting_decision / brief`；
- pending decision 恰好 1；
- Provider receipt 恰好 1，pending operation 为 0；
- live candidate authorization 可重新验证；
- image/collaboration operation 均为 0。

部分 evidence bundle：

```text
p32-continuity-evidence-1924d59e7b6bd84e6988f657f2e82db23863d5d1d81c9b547ae28f0d647ffa45
```

bundle 与冷态重建得到相同的预期阻断项：`text_progress_missing`、`pending_decision_present`、`terminal_status_invalid`、`terminal_event_not_singleton`、`continuity_quality_report_missing`。没有 `evidence_authority_drift`。它是“流程尚未继续”的部分证据，不是失败 Run，也不能冒充最终 release-ready bundle。

## 7. 本地门禁证据

在真实调用前完成：

| Gate | 结果 |
|---|---|
| 授权/漂移/API/continuity/release 专项 | `80 passed, 1 warning` |
| backend full suite | `1331 passed, 1 warning` |
| compileall / diff whitespace / closure audit | 通过；无 legacy marker、无意外 pipeline 目录 |

唯一 warning 为既有 Starlette `TestClient` 弃用提示。

## 8. 后续结果

用户随后授权由当前执行者承担全程内容确认。Brief 采用“定向编辑后接受”：修复不可逆规则、终局因果、标题与读者承诺，并通过正式 Stage Draft/Decision 路径提交；历史 Brief receipt 未重放。

Book Architecture 也经一次人工编辑后接受。Graph 随后按冻结的旧 ReviewPolicy 自动提交 Cast，暴露主体注册表过早冻结问题，因此 Run 在未接受的 Volumes 候选处主动停止。完整证据、根因和 r2/v5 修复见 `docs/engineering/phase-32-wave-63-cast-authority-gate.md`。
