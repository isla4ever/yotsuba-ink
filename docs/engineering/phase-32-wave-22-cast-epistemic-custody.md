# Phase 32 Wave 22：Cast 未决主张保管与路线 r2

状态：**Prompt/Context 最低责任层已离线关闭；真实模型遵守性与三阶段文学门仍未证明**

日期：2026-08-23

## 根因与产品决定

Wave 32.21 的 Cast 请求同时收到作者输入和完整 Brief prose，但只有来源 Artifact ref/digest，
没有声明这些内容的认识论地位。模型因此把 Brief 中的开放问题、未来风险和计划结局升级为
人物隐藏动机、罪责与必然后果。具体表现包括把“主管是否掩盖旧事故”写成确定动机，把
“断电后可能死亡”和“可能承担法律责任”写成既定结局。

这不是 JSON Schema、transport、重试或 Cast UI 问题。正确边界是：

- 作者输入是规划约束，但不是 Canon；
- accepted Brief/Story Map/Book Architecture 是已接受计划，但不是事实证据；
- projected risk、planned outcome 与 open question 必须保留各自状态；
- Cast 只能把它们用于可见目标、人物认知、压力、可能后果和未来变化条件；
- 怀疑、罪责、隐秘动机、死亡和法律结果不得在没有作者硬约束时被写成事实。

文学语义不能靠关键词过滤可靠阻断，因此本轮不增加字符串扫描、自动换稿或隐藏 Provider
调用。确定性层只负责让每个 source 的状态可追溯；下一次真实门再人工判断模型是否遵守。

## 单一正向生产路径

三条官方路线从 `r1` 升级为 `r2`，仅 Cast Context policy 升级为：

```text
context.screenplay.cast.v2
context.short_novel.cast.v2
context.long_novel.cast.v2
```

对应 Route digest：

```text
screenplay_sample c65a70afa0c525c6ba8c452616ac0872c3af0830587e11227b5f1bb3aba21980
short_novel      14dddbb98b495560a876e7e0ec22a9d6064c95dfec24abf9b582032b53b68b5a
long_novel       34a2b6344ef3efd832b700460e377ba58fca8bb0601c3ccbbc877dba8a2339b3
```

未来 Cast 请求的 `frozen_context.epistemic_custody` 为内容寻址合同，每项包含：

```text
source_path
source_ref
value_digest
status
canon_authority=false
allowed_use
prohibited_promotion
```

Context 自身带 `contract_digest`。任何字段状态、来源或规则被改写都会导致合同验证失败，并会
改变 Provider input snapshot/request signature。`character_bible` Prompt 升为 v2，Character 与
Relationship 字段 Schema 同步明确风险、未来结果、隐秘动机和罪责边界。

旧冻结 `r1 / cast.v1` definition 不被转换、补写或改 digest；编译器对 v1 返回原有上下文形状。
Wave 32.21 历史失败 Run 保持原始 repository projection、decision receipt、checkpoint 和 receipt，
不恢复、不取消、不重投影。

## 离线失败样本与回归

`tests/fixtures/phase32_wave22_cast_claim_custody.json` 从 Wave 32.21 已脱敏 Brief/Cast 证据提炼，
保留原 payload hash 与三类观察到的错误升级。回归证明：

- `creative_intent` 为 `author_constraint`；
- Brief `premise` 为 `accepted_plan`；
- Brief `visible_conflict` 为 `projected_risk`；
- Brief `ending_effect` 为 `planned_outcome`，其内嵌开放问题不得成为现时事实；
- 所有输入均 `canon_authority=false` 且具有 value digest；
- 修改任何 custody 状态而不更新 digest 会被拒绝；
- fake Provider 收到的真实 Cast request、rendered prompt 与 input snapshot 均包含 v2 custody；
- v1 frozen context 不被暗中改写；
- Route compiler 拒绝任何新建 `character_bible + cast.v1` 定义，不能绕过 custody；
- 本轮没有真实 Provider 调用。

## 验证

- Prompt/Context/Route/Driver/Graph/Failure 定向回归：`97 passed`；
- 全量后端：`1024 passed`，另有 1 个既有 Starlette/httpx 弃用 warning；
- `compileall`：通过；
- 真实 Provider：`0` 次；
- 历史 Run：未修改。

## 未关闭的门

离线合同只能证明模型明确收到了可追溯语义，不能证明真实模型一定遵守，也不能把文学误判
升级为确定性 blocker。下一次真实 Provider 门仍需用户单独授权并创建全新 `r2` Run：先人工
审读 Cast 是否保留未决性，再验证 Beat Board v2 稳定 refs，最后联合审读 Brief/Cast/Beat 的
连续性、可拍性和成本。旧 Run 不得恢复。
