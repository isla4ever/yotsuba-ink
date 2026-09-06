# Phase 32 Wave 61：真实文本候选零费用预检

- **状态**：价格 attestation 与环境预检已完成；等待显式 Run 预算授权
- **日期**：2026-09-05
- **适用范围**：`official.long_novel + continuity_acceptance + deepseek-v4-pro`
- **计费状态**：Provider 调用 0；当前报告只允许进入预算决策，不允许执行 Run
- **图片状态**：未启用，图片调用 0

## 1. 产品决定

“价格新鲜”和“允许花钱”是两个独立权限。Wave 61 不把配置更新直接变成真实调用授权，而是先生成两项不可变证据：

1. pricing attestation：记录谁在何时依据哪个官方来源确认了什么费率，以及 Provider profile 更新前后的完整 digest；
2. zero-call environment report：只报告 Provider/model/pricing/secret 环境是否可以进入预算授权，固定 `billable_call_count=0`。

环境报告只能返回 `blocked` 或 `ready_for_budget_authorization`。它不存在 `ready_to_execute`，因此后续代码不能把一次价格刷新误当成无限额运行许可。

## 2. 官方价格复核

复核来源：<https://api-docs.deepseek.com/quick_start/pricing/>

官方页面在 2026-08-16 之后使用 peak/off-peak 费率。当前 `deepseek-v4-pro` 的 peak cache-miss 输入价为 `$1.32 / 1M tokens`，peak 输出价为 `$3.96 / 1M tokens`；off-peak 价格更低。本项目继续冻结 peak cache-miss/peak output 作为 `conservative_upper_bound`，避免依赖运行时段或假设缓存一定命中。

本次没有改变费率数值，只把已经 stale 的 `verified_at` 更新为本次官方复核时间，并强化了来源和恢复证据：

```text
pricing verified_at:
  2026-09-05T13:51:25.323328+00:00

attestation_ref:
  p32-pricing-attestation-eb034c7907d0a0c5a0a2d887d960038a88bb83857b964d19521fe5bf98e683c7

profile_after_digest:
  fe071e9c8dd9500a777c25a112482fda6911996fddb2ddbc69ec484b46425b80
```

代码内默认 `verified_at` 仍是历史 seed；bootstrap 不覆盖已存在的 operator pricing，因此本次持久化配置会保留。未来超过 24 小时后必须重新 attestation，不能靠修改检查时钟或复用旧报告放行。

## 3. Pricing attestation 合同

命令必须显式提供：

- idempotency key；
- 读取 Provider profile 时得到的 `expected_profile_digest`；
- 固定的 `provider-deepseek-text / deepseek-text / deepseek-v4-pro` 身份；
- 正数 input/output USD per million token 费率；
- DeepSeek 官方 pricing URL；
- 带时区且不超过 24 小时的 `verified_at`；
- `conservative_upper_bound` 估算口径和说明；
- 可审计的 `attested_by`。

attestation 自身按完整 payload 内容寻址，并保存 `profile_before_digest` 与 `profile_after_digest`。相同幂等 key 只能重放完全相同的 command；不同 command 会冲突。

## 4. 并发、覆盖与中断恢复

所有 pricing attestation 使用同一 Provider 级 POSIX 文件锁，而不是按 idempotency key 分锁。Provider profile 的实际更新通过 SQLite `BEGIN IMMEDIATE` compare-and-swap 完成：只有数据库中的完整旧 payload 仍等于调用方读取的版本时才更新。这样可以阻止：

- 两个不同幂等 key 同时读取旧 profile 后互相覆盖；
- 设置页或其他进程在 attestation 准备后修改 profile，却被静默覆盖；
- stale command 在新 pricing 已生效后再次写回旧值。

更新顺序固定为“先写 immutable intent，再 CAS Provider catalog”。如果进程在两者之间退出，同一 command 重放会识别 `profile_before_digest` 并补完 catalog 更新；存在待恢复 intent 时，其他 pricing command 被阻断。若当前 profile 既不是 before 也不是 after，则停止并要求人工核对，不猜测合并。

幂等重放和执行放行分属不同职责：已经记录的同一 command 即使在 24 小时后重放，也允许读取或补完它自己的本地原子迁移，避免遗留 intent 永久锁死；但环境报告会把该价格标为 stale，真实 Run 仍无法通过 readiness。新 command 始终必须携带 24 小时内的官方复核时间。

## 5. Zero-call environment report

环境检查只读取本地配置和 secret 是否存在，不建立网络连接，不创建 Run、Provider input、Provider operation、budget admission 或 gateway 对象。报告递归避免输出 secret 与 URL，只保存来源 digest、pricing snapshot ref 与公开费率。

当前报告：

```text
report_ref:
  p32-live-preflight-e4d81eb04fbdbdb7a4dd39f8c76903b2dd484a18126190df72a9a201cd51a89f

verdict: ready_for_budget_authorization
next_gate: explicit_run_budget
issue_codes: []
billable_call_count: 0
secret_configured: true
pricing_age_hours: 0.0
pricing_snapshot_ref:
  p32-provider-pricing-f31bb0fd3473588deb431b89ad676e80858ff8c0d495a3c26d6c9fd4171ce5eb
```

`secret_configured=true` 只说明本地 resolver 能取得非空值；报告和日志没有读取或输出密钥正文。它也不证明账户余额、远端服务健康或模型输出质量，这些只能在显式预算后的受控实测中观察。

## 6. 实现边界

| 能力 | 文件 | 边界 |
|---|---|---|
| Attestation/report contracts | `usage/phase32_live_candidate_preflight_contract.py` | 内容寻址、语义一致性、固定 0 调用 |
| Immutable audit store | `storage/phase32_live_candidate_preflight_store.py` | attestation、report、Provider 级跨进程锁 |
| Profile CAS | `storage/provider_profile_store.py` | SQLite 原子 compare-and-swap |
| Zero-call orchestration | `orchestration/phase32_live_candidate_preflight.py` | 官方身份/来源/新鲜度/secret 与恢复规则 |
| Production assembly | `api/bootstrap.py` | 只注册 private app-state service，无公共 route |

## 7. 测试证据

专项测试覆盖：

- pricing CAS 更新与持久 attestation；
- report 为 `ready_for_budget_authorization` 且 `billable_call_count=0`；
- report 不含 secret、URL 或 Provider 地址；
- 冷启动幂等重放；
- 同 key 不同 command 与 stale expected digest 冲突；
- intent 已写、catalog 写入中断后的冷恢复；
- pending intent 阻断另一个 command；
- stale pricing、缺 attestation、缺 secret 保持 blocked；
- production bootstrap 使用同一 Provider store；
- 不创建任何 Provider operation。

验证结果：

| Gate | 结果 |
|---|---|
| preflight + evidence + boundaries + run preflight | `38 passed, 1 warning` |
| Phase 32 continuity/readiness/admission/budget/execution 联合回归 | `214 passed, 1 warning` |
| backend full suite | `1329 passed, 1 warning` |
| compileall / diff whitespace / closure audit | 通过；无 legacy marker、无意外 pipeline 目录 |

唯一 warning 是既有 Starlette `TestClient` 对 `httpx` 的弃用提示，不是本波功能失败。

图片和真实 DeepSeek 调用均为 0。本波测试只能证明本地环境授权边界，不证明远端稳定性或文学质量。

## 8. 下一道唯一门禁：显式 Run 预算

Wave 60 Fake exact-12 已验证正常路径需要 18 次 generation 和 12 次 writeback，即 30 个基础 logical operations。考虑最多一次 writeback contract correction 和少量受控恢复，建议的单次候选上限是：

```text
max_cost_usd: 5.00
max_operations: 48
max_total_tokens: 2,000,000
max_transport_attempts_per_operation: 3  # code-owned，不可提高
```

这些数字是待用户确认的硬上限，不是预计账单，也尚未写入 Run budget。只有用户明确授权三项额度后，下一步才会：

1. 用全新 idempotency key prepare 一个 exact-12 Run；
2. 将当前 pricing snapshot、环境 report、readiness 和 budget 绑定到同一 definition；
3. 在第一次真实调用前再次检查 24 小时新鲜度；
4. 默认停在 Brief 候选等待内容确认；
5. 任何预算、合同、pending、writeback、图片或协作异常立即停止；
6. 最终形成 12/12 冷态 bundle 与真实人工冷读。

没有明确额度授权时，本轮到此停止是正确行为，不应以测试便利值或历史预算代替用户决定。
