# Phase 32 Wave 28：Brief Artifact 编辑闭环

状态：**Brief 正式 Artifact 读取、作者草稿、定稿物化、committed 只读、事件续接与 Version 20 工作台验收通过；后续阶段工作台仍未迁移**

日期：2026-08-23

## 产品决定

Phase 32 的第一个内容工作台只关闭 Brief 的完整垂直链路，不用旧 `BriefStageView`、legacy
`narrative_stores` 或通用 JSON 表单填补其余阶段。Brief 的唯一权威链路为：

```text
pending decision candidate
  -> GET /api/runs/{run_id}/stages/brief/artifacts/current
  -> Version 20 schema-specific Brief form
  -> source-bound draft autosave
  -> PUT /api/runs/{run_id}/stage-drafts/{decision_id}
  -> POST /api/runs/{run_id}/decisions + draft_ref
  -> materialized candidate
  -> LangGraph decision resume
  -> committed immutable Artifact + decision receipt
  -> Run read model + SSE + monitor
```

项目标题仍显示“待定标题”。当前 Brief Schema 没有正式标题字段，因此本切片不从创作意图、
候选内容或 UI 文案推导标题，也不擅自扩展 Artifact 合同。

## 后端闭环

- `Phase32ArtifactEditingService.current()` 只读取当前 pending decision candidate 或 committed
  Artifact，并重新校验冻结 route、stage、Artifact kind、status 和 payload Schema；
- `Phase32ArtifactDraftStore` 保存不可变、内容寻址的作者草稿；草稿绑定 Run、决策、domain
  revision、路线、阶段与 source Artifact，旧 revision 或旧 candidate 不能继续写入；
- 保存前用正式 Pydantic Artifact 合同和 route binding 校验全部 payload；Brief 的
  `target_minutes` 或 `target_characters` 必须等于 Run 冻结 Scale target；
- `accept` 只有在 `draft_ref` 指向当前 source-bound 草稿时才会物化新的 candidate。执行服务
  将 `source_artifact_ref`、`draft_ref` 与 `candidate_ref` 写入不可变 decision receipt，再用同一
  checkpoint/driver 路径恢复；
- committed Artifact 不原地覆盖。决策完成后 current API 返回 committed payload，
  `editable=false`；重复同一决策复用成功 receipt，不重复提交；
- 当前只为 Brief 开放编辑。其它阶段即使存在 pending decision，也不能绕过工作台迁移直接
  写 draft。

正式 HTTP 边界：

```text
GET /api/runs/{run_id}/stages/{stage_id}/artifacts/current
GET /api/runs/{run_id}/stage-drafts/{decision_id}
PUT /api/runs/{run_id}/stage-drafts/{decision_id}
POST /api/runs/{run_id}/decisions
```

API route 只做 payload 校验、服务调用和错误映射；Artifact 验证、草稿身份与物化规则位于
`orchestration/` 和 `storage/`，没有进入 route 文件形成第二业务层。

## Version 20 工作台

- 剧本样片显示样片类型、时长、命题、观众承诺、可见冲突、结尾效果与语气；短中篇和长篇
  显示前提、读者承诺、主题问题、世界硬规则、结局方向、叙事声音与冻结字符目标；
- 字段变化在 650ms 静默窗口后自动保存；确认立项前会 flush 最新本地 revision，刷新页面读取
  同一 decision 的最新草稿，不以 local storage 或 timer 作为权威；
- 候选态提供 ReviewPolicy 允许的操作。官方短中篇 Brief 的定向换稿上限为 `0`，浏览器验收
  因此只显示并验证“确认立项 / 取消”，没有伪造不可用的换稿按钮；
- 取消对话框支持 `Esc` 关闭，首次焦点落在“返回”；Busy 时不会重复提交；
- committed 状态展示完全相同的结构化内容，但输入只读，并提供进入下一阶段的导航；
- Inspector 只显示当前阶段需要的冻结规模、创作意图、版本来源和换稿额度，不引入 Story Bible、
  Wiki 或运行日志；
- Run 尚未生成 Brief Artifact 时，hook 由 read model 显式禁用，不再请求不存在资源造成预期
  `404` 控制台错误。

## SSE 与监控发现

首次浏览器验证暴露了两个投影问题：

1. Brief 决策成功后只刷新 Run envelope，没有重新建立已结束的 SSE 连接，导致下游 Story Map
   新事件需要刷新页面才能出现；
2. SSE 重连窗口内，监控只从 event list 查 candidate，暂时会把 read model 中已存在的 pending
   Story Map 决策显示为“尚无阶段产出”。

修复后，决策成功同时调用 `reconnectRun()`，从最后 sequence cursor 续接；监控 candidate
优先读取 pending decision，再以事件作为补充。第二条全新 Fake Run 在不刷新页面的情况下从
事件 `3` 续到 `8`，中央区立即显示 Story Map candidate 和 3 条阶段事件。

## 合同与浏览器证据

目标测试：

- 后端 Artifact Store、草稿 Store 与正式 execution API：`11 passed, 1 warning`；
- 前端 Run API 与草稿 Hook：`2 files / 6 tests passed`；
- disabled Hook 用例证明 read model 未暴露 Artifact 前不会发出 current/draft 请求；
- stale source 返回 `409`，冻结 Scale 漂移返回 `422`；定稿后 committed ref 与原 candidate ref
  不同，receipt 保留三段来源身份。

最终回归：

- 后端全量：`1021 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`17 files / 51 tests passed`；
- `pnpm exec tsc --noEmit`、production build、CSS audit、frontend structure audit、CSS build
  check、Python `compileall`、`git diff --check` 与 production closure audit：通过。

隔离浏览器环境：

- Fake Provider API：`127.0.0.1:8788`；
- Vite：`127.0.0.1:5177`；用户自己的 `5176` 未修改；
- 视口：`1440x920`、`1024x700`、`390x844`；三者均满足
  `scrollWidth === innerWidth`；
- 控制台：`0 error / 0 warning`；
- 验收覆盖：未启动空态、candidate、作者编辑与刷新恢复、取消对话框、`Esc`、committed 只读、
  移动端阶段导航、Story Map pending fallback 和 SSE replay；
- 截图位于 `output/playwright/wave32-28/`，浏览器 trace 位于其 `.playwright-cli/traces/`。

用于证明 SSE 实时续接的第二条 Fake Run：

```text
project_id: p32-proj-da3515ac0c15905cc0ea
run_id: p32-run-9cbdec1b948776d6e113
event cursor: 3 -> 8
```

本轮所有浏览器数据位于独立临时数据根；没有恢复历史 Run，没有点击或调用真实 Provider。

## 未闭合边界

本切片不能宣称 Wave 32.6、三路线工作台或 Phase 32 整体完成：

1. Story Map、Book Architecture、Cast、Volumes、Rolling Detail、Section Plan、Beat Board、
   Scene Deck、Text、Script、Cover 与 Export 尚未迁移为专业内容工作台；
2. Story Map 虽已由 Fake Provider 生成并在监控显示，但尚没有可编辑、可确认的正式工作台；
3. 作者协作、Story Bible、Cover assets、amendment、selection/diff 和 Import Package 仍待按
   source-bound 合同迁移；
4. 本轮没有真实 Provider 调用，不能证明真实输出质量、成本、连续性或文学验收；
5. Brief 的正式标题仍需先在 Artifact/下游依赖合同中设计，不能由前端单独补字段。

下一切片应迁移短中篇 `StoryMapArtifact` 的内容工作台和 decision 闭环，复用本轮正式
Artifact/current/draft/receipt/SSE 边界，并补齐 anchor、Promise 覆盖和 committed/amendment
语义；不能把 Brief 表单复制成 Story Map，也不能回读旧 Spine 因果链。
