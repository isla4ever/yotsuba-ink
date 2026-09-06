# Phase 32 Wave 19：Brief 语义与定价就绪硬门

状态：**离线合同完成；未调用真实 Provider；旧 Wave 18 Run 保持只读候选态**

日期：2026-08-23

## 本轮目标

收口 Wave 32.18 暴露的两个最低责任问题：

1. `ScreenplayBriefArtifact` 的 `sample_type`、`audience_promise`、`visible_conflict` 和 `ending_effect` 缺少足够明确的作者语义；
2. Provider profile 只有无来源的通用价格字段，无法证明某一冻结模型的成本金额。

文学表达仍是编辑 warning，不升级为自动换稿或无限重试。价格来源、精确模型匹配和调用前就绪状态属于确定性合同，可以阻断真实网络调用。

## Screenplay Brief v2

- `ScreenplayBriefArtifact` 的 JSON Schema 增加作者可读字段说明；
- `sample_type` 明确禁止复制 `screenplay_sample`、`brief` 等内部 ID；
- `audience_promise` 要求说明本故事独有的认知参与或情绪兑现；
- `visible_conflict` 要求对抗者/阻力、台面行动、期限、失败后果和不可逆选择；
- `ending_effect` 要求结尾揭示、交付/暴露对象、具体损失、交换所得和后续问题；
- Prompt ID 从 `prompt.phase32.screenplay_sample.brief.v1` 升为 `v2`，Prompt 与 Schema digest 均变化。

新冻结标识：

```text
prompt_template_id: prompt.phase32.screenplay_sample.brief.v2
prompt_template_digest: 8b508fcaec1dc70c1cf5b837f765a1344d900e28fc6a321fa47fe85b7bb10aba
output_schema_digest: a0c38f7ffd0a7c9ac2d6d43abdd6f133fc965484a545773a8d4ab28a2ab7e15f
```

旧 Artifact 没有增加会破坏读取的字段校验器。Wave 18 的 `sample_type=screenplay_sample` 仍可作为历史候选读取，但新 Prompt/Schema 不再鼓励生成该内部值。

## 精确模型价格合同

`ProviderProfile.model_pricing` 现在按模型 ID 保存一组完整声明：

```text
model_id -> currency / input rate / output rate / fixed output rate
         -> source_url / verified_at / estimate_basis / estimate_basis_note
```

Phase 32 binding 只读取当前执行模型的精确键，不再把 profile 顶层价格猜测性套给其他模型。没有精确条目或缺少来源时，快照保持 `source=unavailable`，费率为空，成本继续显示 `unknown`。

DeepSeek `deepseek-v4-flash` 使用 2026-08-23 复核的官方价格页：峰时 cache-miss 输入 `$0.44 / 1M tokens`，峰时输出 `$1.32 / 1M tokens`。这是保守上界，不是 Provider 账单；官方说明价格可能调整，下一次验收前仍应复核来源页：

- https://api-docs.deepseek.com/quick_start/pricing/

当前只冻结 Flash 的已核验价格。`deepseek-v4-pro` 没有被错误套用 Flash 单价，因此使用 Pro 的流水线仍会得到 `source=unavailable`，直到为 Pro 建立独立精确条目。

## 真实调用前硬门

`FrozenPhase32ProviderGateway` 实现显式 readiness gate。`Phase32RouteDriver` 在以下行为之前调用它：

1. 写 Provider input snapshot；
2. 创建 operation receipt；
3. 领取 lease 或增加 transport attempt；
4. 解析 secret；
5. 构造 Provider client 或发出网络请求。

文本真实调用必须同时具备可追溯来源、带时区核验时间、估算基准、输入单价和输出单价。拒绝测试证明价格未知时上述五类副作用均为零。fake gateway 不实现真实 Provider readiness capability，离线 demo/fixture 路径仍可运行。

## 历史 Run 不变证据

Wave 18 Run 未被接受、恢复或改写：

```text
run_id: p32-screenplay-brief-live-20260823-020459
status: awaiting_decision
definition_digest: 24de5756055fa3b010075095c7f3ca069bcbd7bda4c55ea22121821007e36939
definition file sha256: 2c3e009c1bd8681345abbd35b3fa83faaad0b0d6bf8b52a161261b6fd5af6dd1
candidate file sha256: 280038cd958e09aafc108b045fb10f1f26bc3cb3d9be44655e4f884e6b7444dc
```

旧 definition 的 Brief Prompt digest 仍为 `b14fa602...e457`，Schema digest 仍为 `e8bf68f9...ee0a`；新 builder 的两个 digest 均不同。新增字段使用序列化排除默认值，旧 definition 内容寻址校验仍通过。

## 验证

- Phase 32 定向合同：`228 passed`；
- 全量后端：`1013 passed`，另有 1 个既有 Starlette/httpx 弃用告警；
- 前端：`32 passed`；
- 前端 `tsc + vite build`、结构审计、CSS 审计通过；
- `compileall`、`git diff --check`、production closure audit 通过；
- 本轮真实 Provider 调用数：`0`。

## 下一道门

先由用户明确授权一个全新的剧本样片验收 Run，再执行 `Brief + Cast + 第一个 Beat Board 单元`。调用前必须重新读取官方价格页、确认冻结模型仍为 `deepseek-v4-flash` 并通过 pricing readiness；不得恢复 Wave 18 Run，不得接受其 Brief 后继续执行。
