# Phase 32 Wave 53 — Short-novel Quality and Recovery Addendum

## Scope

本补充记录 Wave 53 在图片验收边界之外对短篇文本链的连续性、承诺引用、人物命名和 Provider 恢复所做的真实复测。图片生成仍不进入本波次；Short/Long 只允许在 CoverBrief 后停在 `image_deferred`。

## Code slice

- Story Map anchor 新候选必须提供至少一个稳定 ASCII `promise_ref`。
- Section Plan unit 必须承接 Story Map Promise，并覆盖全部已声明 Promise；历史 Run 仍可读取空数组，但新候选在写回边界拒绝。
- Character Bible 登记跨 anchor 持续出现的行动者、对手和被追索对象；短篇正文不得给未登记对象创造新姓名或化名。
- Writeback transport recovery 读取并复用同一 pending operation 的 immutable Provider input snapshot，避免 recovery counter 变化产生孤立 pending receipt。

## Real DeepSeek evidence

### r4 diagnostic

`release-smoke-canonical-short_novel-20260827-r4` 证明门禁能抓到真实下游缺口：Story Map 已输出 Promise 引用，但 Section Plan 省略 `promise_refs`，候选在接受边界被拒绝。该 Run 不计为通过，也没有启动图片 Provider。

### r5 contract pass

`release-smoke-canonical-short_novel-20260827-r5` 在补充显式 JSON 示例后通过 Promise 合同：11/11 operation 成功、0 reject、0 pending，终态 `image_deferred`，图片 operation 为 0。Story Map 的 3 个 anchor 与 Section Plan 的 3 个 unit Promise 覆盖完整。冷读仍发现正文给未登记的被追索对象临时命名（`陈国栋`），因此继续升级 Cast/正文 Prompt 到 v4。

### r6 recovery diagnostic

`release-smoke-canonical-short_novel-20260827-r6` 在命名边界 v4 后完成终态，但暴露一个恢复计数 bug：14 个 Provider receipt 中 13 个已返回/成功，仍遗留 1 个 `pending` transport receipt；Outbox 的 3 个 unit 都是 `committed`，因此问题只会在成本与稳定性汇总中显现。根因是 recovery counter 被拼进新 operation key，而旧 pending key 被保留。

### r7 after fix

`release-smoke-canonical-short_novel-20260827-r7` 使用新代码完成真实链路：

| 指标 | 结果 |
|---|---:|
| 终态 | `image_deferred` |
| 阶段 | brief / story_map / cast / section_plan / text / cover 全部 completed；export locked |
| Provider receipts | 12 total；11 succeeded；1 首轮 `contract_rejected` 后纠正成功；0 pending |
| Token / 估算成本 | 43,882 / `$0.07936368` |
| SSE | 46 条，seq 1–46 单调递增，唯一终态事件 `image.deferred` |
| 图片 operation | 0 |
| 冷启动读取 | 状态、阶段、receipt 汇总与同进程一致 |
| Export API | 409，错误码 `image_deferred` |

首次拒绝是 writeback assertion 的 `state.value` 类型错误；该错误被保留在 receipt diagnostic 中，第二次合同纠正后成功，不能被最终状态掩盖。

### r8 after writeback hardening

`release-smoke-canonical-short_novel-20260827-r8` 使用 Wave 54 的末尾硬检查和局部纠正提示完成 3 个文本单元：

| 指标 | 结果 |
|---|---:|
| 终态 | `image_deferred` |
| Provider receipts | 11/11 `succeeded`；首轮 `span_ids` contract reject 0；空 claims 纠正 0；pending 0 |
| Token / 估算成本 | 39,031 / `$0.07033356` |
| SSE | 46 条，seq 1–46 单调递增；唯一终态事件 `image.deferred` |
| 图片 operation | 0 |
| 冷启动读取 / Export | API 读取一致；Export 409 `image_deferred` |

Cast 仅登记 `林默`；三个正文单元没有观察到 `林晚`、`林晓`、`元话语`、`AI` 或 `模型` 等漂移/元话语标记。

## Quality cold read

- Story Map 与 Section Plan 的 Promise 引用完全覆盖：
  - `promise_missing_voice`：anchor 1–2、unit 1–2；
  - `promise_witness_protection`：anchor/unit 2–3；
  - `promise_truth_remnant`：anchor/unit 3。
- Cast 登记 `林默`、`陈屿`；3 个正文单元只观察到已登记姓名，未复现上一轮的 `陈默`、`周远` 或未登记 `陈国栋` 漂移。
- 正文长度约 1,644–2,791 字符，单元边界和 POV 均可读取；本记录是短篇 smoke 的人工冷读信号，不代表完整长篇文学质量。

## Decision

Wave 53 的短篇文本链、承诺连续性、命名边界和恢复 pending 统计门已通过 r7/r8 证据。Wave 54 的新鲜 r8
样本首轮 writeback contract reject 为 0，说明提示词硬化在该样本有效；历史 r7 的 1/12 仍保留为回归
指标，不能从报告中抹除。Screenplay/Long 的同等级证据已补入[三路线闭环记录](phase-32-wave-53-three-route-closure.md)；
Long r9 同样首轮 reject 为 0，但正式长篇规模和三路线人工冷读仍未收口。图片验收保持冻结，Wave 55/56
仍须等待长篇质量门和人工冷读收口。
