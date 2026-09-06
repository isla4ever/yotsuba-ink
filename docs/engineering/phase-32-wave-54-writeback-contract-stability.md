# Phase 32 Wave 54：写回首轮合同稳定性

## 目标与边界

本波只优化文本阶段 `Script/Text -> Evidence -> Canon/Wiki` 的首轮合同稳定性。三条官方路线仍共用同一
writeback 合同；图片生成、CoverAsset 二进制、图片计费和完整 BookDelivery 继续排除，不得因为本波通过而
把 Short/Long 的 `image_deferred` 改成 `completed`。

## r8 现场根因

Long `release-smoke-canonical-long_novel-20260827-r8` 的首轮 writeback receipt 为：

```text
claims.0.span_ids -> too_long
Tuple should have at most 3 items after validation, not 4
```

Provider 返回的第一条 claim 复制了 `span-0038`、`span-0047`、`span-0053`、`span-0056` 四个片段；其余 claims
本身合同有效。DeepSeek 官方文本模板冻结的是 `json_object`，因此只能约束外层 JSON 语法，嵌套的 Pydantic
`max_length=3` 仍由本地合同做最终拒绝。第二次纠正返回 `{"claims":[]}`，虽然技术上成功，但会丢掉本可写回的
持续事实，必须把这种退化作为质量指标记录。

## 实施切片

1. `render_writeback_prompt` 在开头保留 span 上限说明，并在可能很长的 `冻结上下文` 之后再次追加硬检查：
   `span_ids` 只能为长度 1/2/3 的 JSON 数组，不能复制全部 `source_spans`。
2. `_contract_correction` 对 `claims.*.span_ids` 超限使用局部修复指令：删除多余片段、保留其他合同正确
   claims，不因单条超限而清空整包。
3. 保留 `Phase32EvidenceClaimProposal.span_ids` 的 Pydantic `max_length=3`，保留 `contract_rejected` receipt
   和脱敏 validation diagnostics；不静默截断、不篡改 Provider 原始返回、不把确定性合同错误降为 warning。
4. 增加回归测试覆盖：提示词末尾规则、纠正提示的保留语义、首轮 4 span reject 后第二次成功写回，以及
   receipt 状态为一条 `contract_rejected` 加一条 `succeeded`。

## 本地验证

- `uv run pytest -q tests/test_phase32_writeback.py`：17 passed。
- `uv run pytest -q`：1160 passed, 1 warning（既有 Starlette/httpx TestClient 弃用提示）。
- `python -m compileall -q src/novel_workflow` 与 `git diff --check` 通过。
- 新鲜 Long r9 和 Short r8 均无图片 operation，且均无首轮 `span_ids` contract reject。

## 新鲜 Provider 验收协议

使用新的 canonical Long `release-smoke` Run（不可复用 r8），保留相同 bounded 规模以隔离提示词变量：

- 决策顺序：`brief -> book_architecture -> volumes -> rolling_detail -> text(chapter_01...) -> cover`；
- 终态必须为 `image_deferred`，Export 明确返回 409，且没有图片 operation；
- 统计首轮 `contract_rejected` 数、最终成功数、空 claims 次数、总 tokens/成本、pending、SSE seq 和冷启动读模型；
- 如仍发生 `span_ids` 超限，保留原始 receipt 的脱敏诊断和纠正 payload 类型，禁止直接扩大上限或静默截断；
- 该运行只证明传输/合同稳定性，不代表长篇文学质量通过。长篇仍需标准多章 accepted-prefix 与人工冷读。

## 退出条件

Wave 54 的新鲜 Long r9/Short r8 合同门已通过：首轮 span 超限拒绝为 0，纠正为空 claims 为 0；r7/r8 的
历史 reject 保留为回归指标。Wave 54 的技术门可关闭，但整体文学质量门仍未关闭。随后进入 Wave 55 文本
导出交付、Wave 56 前端/浏览器可观测性；图片留到 Wave 57 单独验收。
