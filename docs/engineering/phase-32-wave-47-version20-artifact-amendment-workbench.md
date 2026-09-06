# Phase 32 Wave 47：Version 20 正式规划修订工作台闭环

状态：**九个 Phase 32 规划工作台已接入同一正式 amendment / impact / apply / successor 状态机，并完成三视口、刷新恢复、焦点、Reduced Motion、单 Loader 和真实 HTTP 拒绝门；本轮只使用本地 `_FixtureGateway`，未调用真实 Provider**

日期：2026-08-25

## 根因与产品决定

Wave 45-46 已经建立后端正式 amendment 和 successor 权威，但 Version 20 只能显示 stale Run，作者无法从已提交规划稿完成正式修订。继续复用候选稿自动保存、作者协作 patch 或客户端本地表单会绕过 ImpactAnalysis，并让旧 Run 与新规划共享错误的执行身份。

本轮只接入一条用户路径：

```text
completed / failed Run 的 committed planning Artifact
  -> 本地正式修订副本
  -> 服务端 ArtifactAmendment + ImpactAnalysis
  -> affected_only / restart_from_stage
  -> apply 后 source Run 永久 needs_action / stale
  -> 刷新恢复 apply receipt
  -> 服务端创建 successor Run
  -> 校验 Project latest Run 与 receipt
  -> 显式进入 successor frontier
```

约束：

1. 候选稿继续使用既有自动保存和确认流程，不创建 amendment；
2. 只有 `completed / failed` Run 的 committed 规划 Artifact 可发起正式修订；
3. `script / text / cover / export` 不开放本入口；
4. 客户端不提交 impact、stale stage、target Run id、route 或 Provider override；
5. apply 后不允许关闭对话层返回旧 Run 继续创作，只能恢复回执或创建 successor；
6. successor 跳转前重新读取 Project，并同时校验 `latestRunId`、branch receipt 和 target Run 身份。

## 前后端边界

- `contracts/artifactAmendment.ts` 定义 amendment、ImpactAnalysis、apply receipt、branch receipt 和恢复响应；
- `services/artifactAmendmentApi.ts` 是五个 HTTP 操作的唯一 IO adapter，并严格解析 Run 与 receipt 身份；
- `state/useArtifactAmendment.ts` 是唯一远程状态机，负责 idempotency key、并发结果隔离、刷新恢复和错误回退；
- `state/usePlanningArtifactAmendment.ts` 只连接 App 权威与 successor 跳转，不复制业务状态；
- `ArtifactAmendmentPanel.tsx` 通过 `document.body` Portal 呈现，不受阶段布局裁切；
- `ArtifactImpactSummary.tsx` 分开展示 preserved、stale、historical frozen、blocked references 与两个 scope；
- `AmendmentSuccessorView.tsx` 明确区分 source 历史 Run 与 target successor；
- 后端 branch GET 同时从 branch service 恢复 apply receipt、branch receipt 和 target Run，不建立第二恢复权威。

九个接入阶段为 Brief、Story Map、Book Architecture、Cast、Beat Board、Scene Deck、Section Plan、Volumes 和 Rolling Detail。三条路线共用同一组件、状态和 HTTP 合同。

## 浏览器验收

隔离环境：

- API：`http://127.0.0.1:8787`；
- Vite：`http://127.0.0.1:5176`；
- 临时数据根：`/tmp/yotsuba-wave47-amendment.Gdwf7v`；
- Provider：测试专用 `_FixtureGateway` / `_TwoSceneGateway`，未读取 API Key 或发出外部请求。

真实持久化夹具包含三条 completed Route 和一个 blocked-reference 剧本 Run。桌面短中篇 Story Map 完整通过：

1. 点击“修订”进入独立副本，原 committed payload 不变；
2. 修改内容后“预览影响”才可用；
3. 服务端生成 ImpactAnalysis，两个 scope 可以互相切换；
4. Portal 直接挂到 `document.body`，焦点从首项 `Shift+Tab` 循环到末项；
5. apply 后 source `wave47-short-run` 保持 `needs_action`；
6. 冷刷新恢复同一个 apply receipt，未重复提交 mutation；
7. successor 为 `run-amend-98f971310479c3454d3d4e0d`，状态 `created`，frontier 为 `cast`；
8. 点击“进入新 Run”后路由与 Project `latest_run_id` 同时切换到 successor。

响应式结果：

| 视口 | 结果 |
| --- | --- |
| `1440x920` | 完整 apply / refresh / branch / enter 链路；Portal 与焦点循环通过 |
| `1024x700` | 对话层 `900x594.69`，完整落在视口内；无横向溢出 |
| `390x844` | 对话层使用全视口纵向账本；`document/body scrollWidth == 390` |

390px 使用 `prefers-reduced-motion: reduce`，对话层 `animation-name: none`。三个视口稳态 Loader 均为 `0`；路由首次装载观测序列为 `0 -> 1 -> 0`，最大同时 Loader 数为 `1`。控制台 `error / warning` 为 `0`，修订链路 HTTP 失败为 `0`。

blocked-reference 使用真实 API 删除已被接受 Script 和 Export 引用的 `scene-2`：ImpactAnalysis 精确返回两个引用位置；apply 返回 `409 / phase32_artifact_amendment_references_blocked`，source Run 继续为 `completed`。前端组件测试同时证明 blocked references 存在时 apply 按钮不可用。

截图证据：

- `output/playwright/wave47-amendment-impact-1440x920.png`
- `output/playwright/wave47-amendment-applied-1440x920.png`
- `output/playwright/wave47-amendment-successor-1440x920.png`
- `output/playwright/wave47-successor-entered-1440x920.png`
- `output/playwright/wave47-screenplay-cast-impact-1024x700.png`
- `output/playwright/wave47-long-book-impact-390x844-reduced.png`

## 测试与验收边界

- 后端全量：`1103 passed, 1 warning`；warning 为既有 Starlette/httpx TestClient 弃用提示；
- 前端全量：`68 files / 163 tests passed`；
- Python `compileall`：通过；
- 浏览器使用真实 FastAPI、Vite 和持久化 store，不使用前端 mock；
- 目标 TS/TSX 已通过仓库 `oxfmt`；
- TypeScript/Vite production build、structure audit、CSS audit、CSS build check、production closure audit 与 `git diff --check`：通过；
- structure audit：`200` 个生产 TypeScript 文件，无异常 pipeline 顶层目录；
- CSS audit：`450196 bytes / 3274 rules / 3691 selectors`，跨文件重复 selector `0`；首屏 CSS `31.3 KiB gzip`；
- production build 仍有既存主入口与 `CharacterGraph3D` 大 chunk 提示，本轮未增加新的持续动画循环或第二套前端责任边界。

本轮只证明正式规划 amendment 与 successor 的本地确定性和 Version 20 交互闭环，不证明 Canon/Wiki writeback、自动 axe 无障碍、规模/性能、真实 Provider 延迟/成本/稳定性或文学质量。README、CHANGELOG、commit、push、Tag 与 Release 继续等待 Phase 32 发布门。
