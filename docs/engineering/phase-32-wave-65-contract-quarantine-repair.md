# Phase 32 Wave 65：合同拒绝稿隔离、人工修复与零调用恢复

- **状态**：后端域服务、持久化、LangGraph 恢复与正式 API 已闭合；作者 UI 与浏览器验收待 Wave 66
- **日期**：2026-09-06
- **真实只读证据 Run**：`continuity-acceptance-run-a2c4903f135af471afbc`
- **真实拒绝回执**：`p32-provider-operation-00873f2e2d642a0d3637f09484419a6f1b246812743c674c9d99337be434eee3`
- **图片边界**：未进入图片验收，新增路径不允许图片或文本 Provider 调用

## 1. 本轮要解决的问题

Wave 64 证明 DeepSeek 能返回完整 Rolling Detail JSON，但一次局部确定性错误会让整份 12 章规划进入 `contract_rejected`：原始返回被 Provider receipt 安全保存，却没有 Candidate，也没有可编辑、可审计、可重新验证的恢复路径。

直接重生成存在三个问题：

1. 对局部引用错误重复支付完整规划成本；
2. 新模型结果可能修好 Cast，却重新引入时间账、揭示顺序或卷边界漂移；
3. 当前真实 Run 已用尽 Rolling Detail 的冻结编辑重生成额度，不能追加隐藏调用。

本轮因此建立一条独立于 Provider 重试、合同纠正和编辑重生成的人工修复路径。它不修改原回执，不自动猜测应该删姓名还是增加 Cast，只接受作者提交的完整修复 Artifact，并重新经过生产合同。

## 2. 唯一正向链路

```text
terminal provider_contract_failed
  -> latest contract_rejected Provider receipt
  -> schema eligibility inspection
  -> quarantined source payload + redacted finding
  -> source-bound full human repair payload
  -> stable identity validation
  -> schema / route / scale / upstream-reference revalidation
  -> immutable candidate + contract repair receipt
  -> same LangGraph checkpoint recovery
  -> fresh explicit decision
  -> accept | cancel | remaining policy-authorized regenerate
```

该链路没有第二套 runtime、fallback graph、receipt 改写或 read model 假恢复。最终 `awaiting_decision` 必须来自现有 LangGraph 中断点，不能仅由 API 投影制造。

## 3. 隔离资格

正式查询接口：

```text
GET /api/runs/{run_id}/contract-quarantines/{provider_receipt_ref}
```

只有同时满足以下条件才返回 `eligible: true`：

- Run 为终态 `failed`；
- 当前失败码为 `provider_contract_failed`；
- receipt 属于同一个 Run、当前 Stage，状态为 `contract_rejected`；
- receipt 是该 Stage 最新一次 Provider operation；
- Stage 在冻结 ReviewPolicy 中有显式人工决策门；
- raw payload 已通过 Artifact Schema 与 route binding；
- 失败可由当前跨 Artifact 引用/范围验证稳定复现。

Schema 无效、JSON 截断、Envelope 无效、图片生成失败或无法由受限语义修复证明的拒绝不会开放编辑。系统返回稳定 finding code 与脱敏消息，不向客户端泄露 Provider 私有诊断或密钥。

当前真实 Rolling Detail 回执的只读结果：

```text
eligible: true
stage_id: rolling_detail
source_payload_digest:
  05376c1bd5da40981326c4748e4fc72c37d47bcdc9ae94dba5caeee8c112262a
finding_code: stage_reference_contract_invalid
finding:
  Detail Chapter chapter_01 names registered subjects outside its Cast scope: ['mentor']
```

回放后真实 Run 仍为 `failed`，Provider operation 仍为 9，pending decision 仍为 0。

## 4. 人工修复命令

正式提交接口：

```text
POST /api/runs/{run_id}/contract-repairs
```

命令必须完整绑定：

```text
repair_id
provider_receipt_ref
provider_request_signature
definition_digest
domain_revision
source_payload_digest
payload
```

任一 digest、request signature、domain revision 或 receipt 变化均按 stale/conflict 拒绝。相同 `repair_id` 与完全相同命令可安全重放；相同 ID 携带不同来源或不同修复 payload 会冲突。

## 5. 可编辑范围

人工修复可以改文学内容，但不能借修复重写代码稳定身份。

通用限制继续复用作者 Artifact 编辑合同：

- 不能新增、删除或替换稳定聚合单元 ref；
- 不能替换已冻结的 Unit、Scene、Chapter、Volume 或 POV 身份；
- 不能引用未提交的上游 Artifact；
- 不能新增未注册主体或越过 Volume Cast scope；
- 不能绕过冻结规模合同。

Rolling Detail 的特殊边界：

- Window、Volume scope、Chapter ref/order、Chapter Volume/POV、Scene ref/order保持不变；
- Chapter/Scene 的局部 Cast scope 可以调整；
- 调整后的 ref 必须属于已提交 Cast，并且 Chapter Cast 必须属于对应 Volume Cast；
- Scene Cast 仍必须是 Chapter Cast 的子集；
- 自然语言中出现的已注册姓名仍必须落在对应 Chapter/Scene Cast。

系统不会自动把 `mentor` 塞入 Chapter Cast，也不会自动删除“沈砚”。这类编辑选择仍由人工承担。

## 6. 持久化与谱系

新增 `Phase32ContractRepairRecord`，记录：

- Run / definition / domain revision；
- 原 Provider receipt 与 request signature；
- 原 payload digest；
- 人工修复 payload digest；
- 新 Candidate ref；
- pending/succeeded 状态；
- 恢复后的新 decision id 与终态摘要。

新 Candidate 的 `source_operation_key` 使用 `contract-repair:` 前缀。原 `contract_rejected` Provider receipt 保持不可变，usage、成本、transport attempts 与 raw payload 均不被重写。修复过程中不会创建 Provider input snapshot、Provider operation 或预算 admission。

## 7. LangGraph 恢复语义

本轮分别处理两种真实 frontier。

### 7.1 首次生成即语义失败

失败 checkpoint 位于 Stage `generate`。恢复时使用只允许返回一个指定 immutable Candidate 的本地 driver；如果图意外进入任何其他 Provider generation，立即失败。候选随后走原 `validate -> decision` 路径，并停在新的显式决策。

### 7.2 定向重生成后语义失败

失败发生在 `decision` 节点内部。LangGraph 已保存原 interrupt 与已消费的 regenerate 命令；不能删除 checkpoint，也不能伪造新 decision。

恢复会：

1. 校验原 decision receipt 已成功对账为 regenerate；
2. 重放同一 checkpoint 中的精确命令；
3. 让本地 driver 只替换失败的生成结果；
4. 保留已消耗的 redraft 次数；
5. 重新执行完整 candidate validation；
6. 进入一个以修复 Candidate ref 命名的新 decision interrupt。

因此真实 Wave 64 场景恢复后应显示 `redraft_used: 1`，只剩 `accept / cancel`，不会凭空恢复已消费的 Provider 重生成额度。

## 8. API 与领域边界

- `api/routes/contract_repairs.py` 只做请求解析、服务调用、错误映射和响应投影；
- 隔离资格、source binding、身份/引用验证位于 orchestration；
- repair receipt 位于 storage；
- checkpoint reinjection 单独位于 `phase32_contract_repair_execution.py`；
- 原 `phase32_execution_service.py` 只增加一个通用的“指定 driver 执行一步”内部边界，没有吸收修复业务规则；
- 前端目录与 API 顶层结构均未增加并行 taxonomy。

## 9. 已通过验证

```text
contract repair focused tests: 5 passed
relevant execution/API/graph/artifact regression: 171 passed, 1 warning
backend full suite: 1347 passed, 1 warning
compileall: passed
git diff --check: passed
read-only real receipt replay: eligible, 0 writes, operation count 9
```

正式测试覆盖：

- 首次语义合同失败的零调用候选注入；
- 定向重生成后失败的 checkpoint 重放；
- 修复后生成新显式 decision；
- redraft 次数不回退；
- Provider gateway 调用数与 operation 数不增长；
- 原拒绝回执保持不可变；
- stable Scene ref 漂移拒绝；
- Rolling Detail 局部 Cast 可修、Scene identity 不可替换；
- Schema 无效返回不允许人工重建；
- 相同 repair id 幂等；
- 相同 repair id 不同 payload 冲突；
- GET quarantine 与 POST repair 正式 API 返回 source authority 和恢复结果。

唯一 warning 仍是既有 Starlette `TestClient` / `httpx` 弃用提示。当前环境仍没有 `ruff` 可执行文件，因此未把 Ruff 记为已通过。

## 10. 当前产品结论

本轮关闭的是后端恢复链路，不是完整作者业务闭环：

- **已闭合**：receipt 隔离、资格判断、人工 full-payload 修复、稳定身份、全量确定性重校验、不可变 Candidate、LangGraph 恢复、显式 decision、幂等与零 Provider 调用；
- **未闭合**：失败页入口、隔离稿可视化、Rolling Detail 修复编辑器、提交/冲突反馈、浏览器恢复矩阵；
- **仍未解决**：时间账、揭示顺序、认识论过度断言和 Volume promise/closure 的结构化质量侧车。

因此三档模式仍不能宣称完整生产闭环，但长篇路线已不再因为一个可定位的语义引用错误而只能整份付费重生成。

## 11. Wave 66 计划

下一轮只开放 UI，不调用真实 Provider，也不修改真实失败 Run：

1. 在 `provider_contract_failed` 失败页展示可修复 receipt 与稳定 finding；
2. 仅在 `eligible: true` 时显示“载入隔离稿”；
3. 复用 Rolling Detail Artifact 编辑器，但切换到 quarantine source binding；
4. 提交时携带全部 digest、signature 与 domain revision；
5. 成功后切换到现有 Candidate 决策台，不自动接受；
6. 冲突、stale、Schema 无效与 identity drift 保持可见；
7. 浏览器验证 desktop、short desktop、390px；
8. 用网络面板证明 repair 请求前后 Provider operation 数不变；
9. 通过前端全量测试、TypeScript/Vite build、CSS audit 与真实本地服务浏览器矩阵；
10. Wave 66 通过后，再决定是否用当前真实 Run 做一次零调用人工修复演练。
