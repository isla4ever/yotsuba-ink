# Phase 32 Wave 66：合同隔离修复工作台与浏览器闭环

- **状态**：完成；Wave 65 的零 Provider 修复能力已接入作者工作台，并通过真实浏览器闭环
- **日期**：2026-09-06
- **只读正式证据 Run**：`continuity-acceptance-run-a2c4903f135af471afbc`
- **拒绝回执**：`p32-provider-operation-00873f2e2d642a0d3637f09484419a6f1b246812743c674c9d99337be434eee3`
- **源 Payload digest**：`05376c1bd5da40981326c4748e4fc72c37d47bcdc9ae94dba5caeee8c112262a`
- **本轮 Provider 调用**：0
- **图片边界**：图片生成不进入本轮验收

## 1. 本轮关闭的业务问题

Wave 65 已能在后端把 Schema 合法、跨 Artifact 引用不合法的 Provider 返回隔离出来，接受人工修复后的完整 Artifact，再经生产合同验证回到 LangGraph 人工决策点。但作者还无法在产品界面完成这件事，浏览器也没有证明该恢复链路不会偷偷续跑、自动接受或新增 Provider 调用。

Wave 66 关闭以下缺口：

1. `provider_contract_failed` 在 Rolling Detail 页面有明确、可执行的恢复入口；
2. 作者能看到稳定 finding、Provider 操作数和不可变原回执；
3. 只有 `eligible: true` 的隔离稿能进入编辑；
4. 修复复用正式 Rolling Detail 编辑器，不暴露原始 JSON；
5. Chapter/Scene 人物范围只能在已冻结 Volume Cast 内调整；
6. 提交完整绑定 receipt、signature、definition digest、domain revision 和 source payload digest；
7. 修复只产生不可变 Candidate 与新 decision，不自动接受；
8. 失败摘要、编辑态、候选决策态在 desktop、short desktop、mobile 均可操作；
9. 浏览器和持久化证据共同证明 Provider operation 数不增长；
10. 正式证据 Run 保持只读，所有写入仅发生在隔离副本。

## 2. 阶段产品合同

| 维度 | Wave 66 定义 |
| --- | --- |
| Stage Artifact | 原 `contract_rejected` receipt 中 Schema 合法的完整 Rolling Detail payload |
| 作者决策 | 是否进入受限修复；如何在冻结 Volume Cast 内纠正 Chapter/Scene 人物范围；修复候选生成后再选择接受或取消 |
| 写回目标 | 新的 immutable Rolling Detail Candidate、Contract Repair receipt、LangGraph pending decision |
| 不可写对象 | 原 Provider receipt、usage、成本、transport attempts、冻结身份、正式证据 Run |
| 下一阶段依赖 | 只有修复 Candidate 被显式接受后，Text 才能读取当前章节蓝图、相关人物和上一 handoff |

该页面不是通用 JSON 修复器，也不是新的运行时。它是 Rolling Detail 阶段对一个已存在、可证明可修复的失败 Artifact 的受限作者决策面。

## 3. 唯一生产链路

```text
Rolling Detail provider_contract_failed
  -> GET current contract quarantine
  -> verify latest rejected receipt + frozen Run authority
  -> show stable finding + immutable receipt + Provider operation count
  -> load quarantined payload into Rolling Detail workbench
  -> human adjusts only allowed literary fields / local Cast scope
  -> POST source-bound full repair payload
  -> schema + route + scale + upstream-reference + stable-identity validation
  -> immutable contract-repair Candidate
  -> resume the same LangGraph checkpoint with local candidate driver
  -> new explicit route_stage_decision
  -> awaiting_decision
  -> accept | cancel
```

没有新增 fallback graph、影子 read model、客户端拼装 Candidate、receipt 改写或自动 decision。

## 4. 后端增量

### 4.1 当前失败隔离查询

新增正式端点：

```text
GET /api/runs/{run_id}/contract-quarantine
```

服务端从当前 Run 的 `provider_contract_failed` 中读取失败 Stage，再从该 Stage 的 Provider operations 中确定最新权威 receipt。客户端不需要也不能猜测 receipt ref。

原按 receipt 查询端点继续保留给审计与精确回放：

```text
GET /api/runs/{run_id}/contract-quarantines/{provider_receipt_ref}
```

两者在专项 API 测试中返回相同 quarantine 投影。

### 4.2 decision 响应一致性

真实浏览器第一次提交暴露了一个测试未覆盖的边界：

- graph interrupt 的临时字典使用 `type: route_stage_decision`；
- 正式 Run read model 使用 `kind: route_stage_decision`；
- 前端只接受正式 read model 合同中的 `kind`；
- 已成功 repair 的幂等重放还会返回顶层 `decision: null`。

修复后，Contract Repair 服务始终优先从持久化后的 Run read model 返回与 repair receipt 精确绑定的 pending decision；只有尚未形成正式投影时才回退到 graph result。成功 repair 的相同命令重放也返回同一个 decision，不再让网络不确定性变成前端假失败。

前端解析器同时以 `run.read_model.pending_decisions` 做同一 Candidate 的受约束恢复来源，并继续验证：

- Run、Stage、Candidate、decision id 必须一致；
- repair 状态必须为 `succeeded`；
- Provider receipt 必须与 quarantine 完全一致；
- decision 必须存在且使用正式 `kind` 合同。

## 5. 作者工作台

### 5.1 失败摘要

失败页只呈现作者完成恢复决策所需的信息：

- 稳定 finding code 与可读消息；
- 当前 Provider operation 数；
- 原始 receipt 的短引用，完整值保留在 title；
- “隔离修复不会增加该计数”和“原回执保持不可变”的明确承诺；
- 只有 eligible 时可用的“载入隔离稿”。

### 5.2 修复编辑态

修复态复用 `RollingDetailArtifactEditor`，并增加受限人物范围编辑：

- Chapter Cast 只能从对应 Volume 的冻结 Cast 中选择；
- POV 永远锁定；
- Scene Cast 只能从 Chapter Cast 中选择；
- 作为 Scene 唯一参与者的角色不能被删除；
- Window、Chapter、Scene、Volume、POV 的稳定身份仍不可改；
- 原始 finding 和 Provider operation 数始终固定在工具栏附近；
- 不显示 raw JSON，也不提供“跳过验证”入口。

当前真实 finding 中的 `mentor` 对应已冻结主体“沈砚”。模拟人工修复是在 `chapter_01` 的 Chapter Cast 中加入“沈砚”，不删除叙事内容，也不改写 Scene ref。

### 5.3 修复后人工门

提交成功后页面回到现有 Candidate 决策台：

```text
status: awaiting_decision
decision kind: route_stage_decision
allowed actions: accept, cancel
redraft_used: 1/1
```

界面只显示“取消 / 确认当前细纲”，不显示已经用尽的“定向换稿”，也没有自动确认行为。候选状态文案使用“当前候选”，避免把人工修复产生的 Candidate 误标为“原始候选”。

## 6. 前端状态机与错误边界

`useContractRepair` 管理单一路径：

```text
loading
  -> unavailable | ready
  -> editing
  -> submitting
  -> restored
```

它负责：

- 生成一次稳定 repair id，并在不确定重试中复用；
- 保存 quarantine 的完整 source authority；
- 提交完整修复 payload；
- 提交前后读取 Run usage，验证 Provider operation 数不变；
- 把 stale、conflict、Schema invalid、identity drift、网络失败显示在工作台内；
- 成功后刷新 Run、重连 SSE，再由现有 StageView 接管 Candidate。

## 7. 真实浏览器验收

验收使用正式代码与正式 API，在临时复制的 Phase 32 runtime 上注册同一个 Project/Run 绑定。副本起始状态与正式 Run 一致，但所有写入只落在临时目录。

### 7.1 交互矩阵

| 状态 | 1440 × 920 | 1024 × 700 | 390 × 844 |
| --- | --- | --- | --- |
| 失败摘要 | finding、9 次调用、receipt、入口完整 | 完整 | 单列布局，主操作 44px+，完整 |
| 修复编辑 | 12 章导航、主编辑区、Inspector 完整 | 短桌面可滚动、提交固定可达 | Chapter 导航横向分段；人物范围控件 357px，完整落在视口内 |
| 候选决策 | `awaiting_decision`、接受/取消完整 | 完整 | 顶部接受/取消完整，正文账本可纵向浏览 |

三档所有状态均满足：

```text
documentElement.scrollWidth == documentElement.clientWidth
body.scrollWidth == body.clientWidth
```

页面级横向溢出为 0。移动端的 Chapter 分段导航可以内部横向滚动，但不会撑宽文档。

### 7.2 浏览器结果

完整交互：

1. 打开 Rolling Detail 失败摘要；
2. 点击“载入隔离稿”；
3. 验证 12 个 Chapter 和上游 Volume/Cast context 已载入；
4. 验证 POV“林墨”锁定；
5. 勾选“沈砚”；
6. 确认“重新校验并恢复候选”从 disabled 变为 enabled；
7. 提交一次 repair；
8. 页面进入“当前 Window 等待作者决策”；
9. 只出现“取消 / 确认当前细纲”；
10. 浏览器 console error/warn 为 0。

## 8. 零 Provider 调用证明

隔离副本提交前后：

```text
Provider operations: 9 -> 9
contract_rejected: 2 -> 2
repair records: 0 -> 1 succeeded
original receipt: unchanged
new decision: 1
```

服务日志只出现一次：

```text
POST /api/runs/{run_id}/contract-repairs 200
```

没有 `/start`、Provider generation 或 decision resolve 请求。修复后读取到：

```text
status: awaiting_decision
failure: null
pending_decisions: 1
allowed_actions: accept, cancel
```

## 9. 正式 Run 不变性

验收结束后对仓库内正式 runtime 做只读复核：

```text
status: failed
failure.code: provider_contract_failed
failure.stage_id: rolling_detail
pending_decisions: 0
provider_operations: 9
contract_rejected: 2
contract_repairs: 0
```

因此本轮没有把浏览器验收结果伪装成正式业务写回，也没有消耗新的 DeepSeek 预算。

## 10. 质量门

```text
contract repair backend focused: 5 passed, 1 warning
contract repair frontend focused: 6 files, 17 tests passed
frontend full suite: 75 files, 193 tests passed
backend full suite: 1347 passed, 1 warning
TypeScript + Vite production build: passed
compileall: passed
structure audit: passed, 208 TypeScript source files
CSS audit: passed
CSS build check: passed, first-screen CSS gzip 31.6 KiB
git diff --check: passed
closure audit: no legacy runtime markers; no unexpected pipeline directories
browser console errors/warnings: 0
```

CSS 新增的是失败摘要、修复工具栏和移动端单列适配。审计确认跨文件重复 selector、重复 keyframe 均为 0；评审新增所有权和指标后已更新基线。Vite 仍报告既有大 chunk 警告，它不是本轮新增失败。

唯一 Python warning 仍是既有 Starlette `TestClient` / `httpx` 弃用提示。当前环境没有 Ruff 可执行文件，因此不把 Ruff 记为已通过。

Closure audit 仍列出一批历史超过 500 行的源文件，作为既有责任边界复核清单；本轮新增的 contract、API、hook、workbench、scope editor 和样式文件均未进入该清单。

## 11. 视觉与交互评审结论

本轮按阶段工作台和高完成度界面标准复核后，没有阻断问题：

1. 失败摘要以一个主判断和一个主操作为核心，没有堆叠卡片；
2. warning 色只用于合同隔离和风险信息，Candidate 恢复后回到常规 mint 决策语义；
3. receipt 与 Provider operation 数靠近操作，降低作者对“是否又付费调用”的不确定性；
4. 编辑态复用原工作台，作者不需要切换到技术表单；
5. 390px 下关键操作、finding、人物范围和决策入口都可达；
6. 修复后不显示不存在的重生成能力，也不误称为原始候选。

## 12. 产品结论

Wave 66 关闭了 Wave 65 留下的作者 UI 与浏览器验收缺口：

- **已闭合**：失败入口、quarantine 查询、受限可视化编辑、source-bound submit、确定性重校验、Candidate 恢复、LangGraph decision、幂等重放、零 Provider 调用、三档响应式和 console gate；
- **未自动执行**：正式 Run 的实际修复与 Candidate 接受；
- **仍需后续处理**：Rolling Detail 的时间账、揭示顺序、认识论断言和 Volume promise/closure 质量侧车；
- **三档模式影响**：官方 screenplay sample、short novel、long novel 流水线共用的 Run、decision、artifact、SSE 和 Provider operation 合同没有分叉；本轮只为长篇 Rolling Detail 的真实失败补齐受限恢复 UI。

这意味着当前产品已能在不重复调用 DeepSeek 的前提下，把一个可定位的 Rolling Detail 引用错误从终态失败恢复到人工 Candidate 门，而且作者仍保有最后接受权。

## 13. Wave 67 建议门禁

下一轮应继续保持图片调用为 0，并按以下顺序推进：

1. 对 Wave 66 改动做只读代码与责任边界复核；
2. 在明确保留原 receipt、Provider operations 9 不变的前提下，对正式证据 Run 执行一次零调用修复；
3. 人工审查修复 Candidate 的 Chapter/Scene Cast、时间账、揭示顺序、认识论和 Volume closure；
4. 未通过文学质量门则只编辑 Candidate，不新增 Provider 调用；
5. 通过后再显式接受 Rolling Detail，进入 Text 前重新冻结正文监督清单；
6. 只有 Text 前置合同、预算和连续性门全部绿，才恢复 DeepSeek 正文调用稳定性/质量测试。
