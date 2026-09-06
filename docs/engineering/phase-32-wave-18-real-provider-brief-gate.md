# Phase 32 Wave 18：真实 Provider Brief 小门

状态：**单次真实 Provider 技术小门通过；成本金额门未闭合；Run 保持候选态，未接受、未进入 Cast**

日期：2026-08-23

## 范围

本轮只验证 Phase 32 第一层真实 Provider 边界：

- 创建全新 `screenplay_sample` Run；
- 冻结 12 分钟目标、`official-deepseek-fast` 和 `provider-deepseek-text`；
- 只执行一次 `brief`，transport attempt 上限为 1；
- 不恢复历史 Run，不切换旧生产主链，不接受候选，不进入 Cast；
- 合同失败立即停止，不隐藏重试。

Run 身份：

```text
project_id: p32-screenplay-project-20260823-020459
run_id: p32-screenplay-brief-live-20260823-020459
creation_route_id: screenplay_sample
workflow_id: official-deepseek-fast
provider_profile_id: provider-deepseek-text
provider_template_id: deepseek-text
model_id: deepseek-v4-flash
scale_target: 12 minutes
```

模型来自工作流 `brief` 节点的冻结配置；Provider profile 的默认模型不是本次请求模型。

## 调用前离线门

- Phase 32 定向合同回归：`217 passed`；
- 全量后端回归：`1007 passed`，另有 1 个既有 Starlette/httpx 弃用告警；
- `.venv/bin/python -m compileall -q src tests` 通过；
- `git diff --check` 通过；
- production closure audit 通过，Phase 32 仍未注册旧生产 runtime selector。

新增离线合同证明：

- 最终 rendered Prompt 与 output Schema 在网络 IO 前进入不可变输入快照；
- binding digest 漂移在 Provider client 创建前拒绝；
- API Key 只进入 client 构造，不进入 request、response 或 receipt；
- `json_parse_failed` 只调用一次并落为不可重试的 `contract_rejected`；
- Brief 的目标时长必须等于冻结 Scale target。

## 真实执行结果

Run 在一次调用后稳定停在：

```text
status: awaiting_decision
active_stage_id: brief
pending_decisions: 1
transport_attempts: 1
provider operation status: succeeded
prompt_tokens: 738
completion_tokens: 286
total_tokens: 1024
reasoning_tokens: 0
```

Provider 返回一个完整 JSON object，Schema 一次匹配，没有解析修复：

```text
finish_reason: stop
candidate_count: 1
parsed_object_count: 1
schema_match_count: 1
repairs_applied: []
parse_error_codes: []
```

输入快照冻结了 route/stage/task/artifact、Provider/template/model、binding digest、rendered Prompt digest、Schema digest、Context 和 direction。检查 Run 相关的 9 个持久化文件，API Key 原值匹配数为 0。

## Artifact 与恢复证据

候选 Artifact：

```text
artifact_kind: screenplay_brief
status: candidate
target_minutes: 12
payload_digest: 6ff72186bdf984802af4edcfa58ee8f7cda9592e7ecb1afbcc884d6be68dd986
```

LangGraph SQLite checkpointer 为该 Run 保存 7 条 checkpoint 记录；read model 的 checkpoint ID 为 `1f19e970-bbb3-6b3e-8000-6775ee3c8d79`。

事件序列连续：

```text
1 stage.started
2 candidate.created
3 decision.required
```

Event page 返回 cursor `3`、`has_more=false`、`terminal=true`；SSE 投影生成 3 帧，并在 `decision.required` 后关闭。read model 同步投影 1 个 succeeded operation 和 1024 tokens，没有 failure。

## 人工 Brief 审读

确定性合同：通过。候选包含完整字段，目标时长、路线与 Artifact 类型一致，没有运行元数据或越权稳定引用。

正向质量：

- 封闭档案馆、清场倒计时、物证核验和不可逆选择形成了可拍摄的台面冲突；
- 结尾把修复胶与主角工作台绑定，能把公共事件转回主角个人责任；
- 语气和执行约束明确，避免了心理旁白和万能超自然解释。

文学 warning，不阻断本次技术门：

- `sample_type` 返回了内部路线值 `screenplay_sample`，没有给出“当代调查悬疑样片”这类创作语义。最低责任层是 `brief` Prompt/Schema 的字段语义约束，不是 Provider 传输层。
- `ending_effect` 把“交出原始件”称为代价，但没有说明交给谁、失去什么控制权、为何能换来下一条线索。最低责任层是 Brief Artifact 对代价/利害的表达力度以及 Prompt 指令，后续 Beat Board 不应替上游发明关键规则。
- `audience_promise` 可执行但仍偏类型化，尚未明确本样片独有的认知反转体验；属于编辑建议，不是确定性失败。

本轮不对候选执行定向换稿，也不接受后继续 Cast。后续先把 warning 固化为离线 Prompt fixture，再由用户决定是否申请新的真实 Run。

## 未闭合成本门

receipt 的 usage 可信，但冻结 Provider profile 没有配置输入/输出单价：

```text
estimated_cost_usd: null
cost_status: unknown
balance_status: unknown
```

因此只能确认调用次数和 token 上限受控，不能把本地结果表述为已完成成本金额或账单对账。下一次真实调用前必须为实际 gateway/model 配置可追溯单价，或接入独立账单证据；不得猜测价格填入生产 profile。

## 结论与下一道门

这次 Run 证明 `CreationService -> frozen definition -> input snapshot -> real gateway -> receipt -> candidate Artifact -> checkpoint -> event/SSE -> read model -> mandatory decision` 的单阶段真实链路成立，且没有隐藏重试或密钥落盘。

它不证明以下事项：

- Brief 已获文学接受；
- Cast 或第一个规划单元可真实执行；
- 三条路线真实 Provider 第一级门完成；
- Phase 32 已切换为生产主链；
- 成本金额、余额或 Provider 账单已经对账。

下一道门先离线修复上述 Brief 语义 warning，并补齐价格来源；完成后才可申请一个新的剧本样片 Run，运行 `Brief + Cast + 第一个 Beat Board 单元`。
