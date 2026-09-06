# Phase 32 Wave 45: committed Artifact 正式修订权威

状态：后端纵向切片已完成本地离线门。本文不代表 repair/branch、正式 Canon/Wiki writeback、Version 20 修订交互或真实 Provider 验收已经完成。

## 根因

Phase 32 已经拥有不可变 candidate/committed Artifact、Run checkpoint、read model、事件流和 source-bound 待决策草稿，但 committed 规划 Artifact 之后没有正式版本化修订链路。当前若直接复用待决策草稿、作者协作 patch 或 Story Bible，会同时破坏以下边界：

- committed Artifact 会被误当成可覆盖表单；
- 模型或客户端可以自报影响范围；
- 已接受剧本/正文可能被规划修订静默改写；
- Graph、Provider input 与 UI 不知道哪些下游已经 stale；
- 进程中断后无法判断 apply 是否已经推进权威投影。

因此本轮不增加另一个编辑入口，而是建立唯一正式链路：

```text
current committed planning Artifact
  -> source-bound ArtifactAmendment
  -> deterministic ImpactAnalysis
  -> immutable apply plan
  -> new committed Artifact version
  -> Run stale projection + artifact.committed event
  -> idempotent apply receipt
```

## 产品决定

1. 仅 `Phase32PlanningArtifact` 可创建正式 amendment。`script`、`text`、`cover`、`export` 不接受此接口原地修改。
2. amendment 必须绑定当前 active committed Artifact ref、payload digest、Run domain revision 和 frozen route identity。
3. proposed payload 继续经过阶段 Schema、frozen Scale 和上游稳定引用校验；客户端不能提交影响列表。
4. `ImpactAnalysis` 从 route manifest、当前 committed Artifact、sequential accepted prefix 和 payload refs 确定性派生。
5. 删除被 committed 下游或 accepted prefix 引用的稳定 ref 时，amendment 可以保存和查看影响，但 apply 必须阻断。
6. apply 仅接受 `affected_only` 或 `restart_from_stage`。前者只标记已有权威材料，后者标记源阶段之后的完整 route frontier。
7. accepted `script` / `text` Artifact refs 与 sequential prefix 永不删除、覆盖或回退；它们同时进入 `historical_frozen` 证据和 stale gate。
8. apply 后 Run 进入 `needs_action`，受影响 stage 进入 `stale`。在后续显式 repair/branch 合同完成前，Provider preflight 必须拒绝继续执行。
9. Phase 27 archive、Story Bible、作者协作聊天 patch、Canon/Wiki 和模型输出都没有 amendment apply 权限。

## 权威与持久化

| 概念 | 唯一权威 | 说明 |
| --- | --- | --- |
| amendment draft | `Phase32ArtifactAmendmentStore` | 内容寻址、source-bound、幂等创建 |
| impact | amendment store 内不可变 `ImpactAnalysis` | 只由 domain service 生成 |
| 新 Artifact version | 既有 `Phase32ArtifactStore` | 继续使用 candidate -> committed，不建立第二 Artifact Store |
| stale routing | `RouteRunStateSnapshot` | checkpoint 可恢复的运行阻断事实 |
| stale UI projection | `RouteRunReadModel` | API、监控、Header 和后续修订 UI 的同源投影 |
| apply plan/receipt | amendment store | plan 先持久化；投影成功后完成 receipt；重复 key 复用 |
| apply event | 既有 Run event journal | 使用 `artifact.committed`，status=`amended` |

apply 允许产生一个内容寻址的孤立 candidate/committed 文件后再推进 Run projection，因为 Artifact 本身不可变且可重用。不可接受的是 projection 已推进但 receipt 丢失：重放必须通过 `active_amendment_id + expected committed ref` 识别并补齐 receipt，不能再次改变 domain revision。

## 影响分类

`ImpactAnalysis` 必须返回：

- `preserved`: source 之前的 stage 和 accepted prefix refs；
- `stale`: 受 source 传递依赖影响的现有 Artifact/stage；
- `historical_frozen`: 已接受 `script` / `text` 单元；
- `blocked_references`: proposed payload 删除、但下游 committed/accepted Artifact 仍引用的稳定 ref；
- `affected_only_scope`: 当前已有权威材料中的受影响 stage；
- `restart_from_stage_scope`: source 之后完整 route frontier；

所有列表按 route ordinal、unit ordinal 和 ref 稳定排序；同一输入必须得到同一 digest。

## HTTP 适配

API route 只解析命令、调用 domain service 和映射错误：

```text
POST /api/runs/{run_id}/planning/{stage_id}/amendments
GET  /api/runs/{run_id}/planning/amendments/{amendment_id}/impact
POST /api/runs/{run_id}/planning/amendments/{amendment_id}/apply
```

创建和 apply 都要求调用方提供 idempotency key。重复 key 只有在命令完全一致时复用，否则返回 conflict。

## 本轮退出门

- 正向：三条路线至少各一个 committed 规划 Artifact 可创建 amendment、读取确定性 impact、apply 为新 committed version 并投影 stale。
- 反向：candidate、非当前 source、正文/剧本、未知 stage、frozen Scale 漂移、悬空上游引用和删除已引用 ref 均被拒绝。
- 幂等：create/apply 重放复用；不同 payload/scope 复用同一 key 冲突；projection 已提交但 receipt 未完成可恢复。
- 运行阻断：`needs_action` 或任一 stale stage 不能进入 Graph/Provider preflight。
- 持久化：旧 committed Artifact、accepted sequential prefix、历史事件不被覆盖或删除。
- 本地门：定向测试、后端全量、`compileall`、前端合同/build、closure audit 和 `git diff --check` 通过。

## 后续阻断项

Version 20 修订/影响预览 UI、repair/branch 决策、作者协作 patch 正式转 amendment、Canon/Wiki 精确 writeback、浏览器矩阵、规模/性能、真实 Provider 和文学冷读均在本后端合同通过后继续；本轮不提前宣称完成。

## 实施结果

- 新增 `Phase32ArtifactAmendment`、`ArtifactImpactAnalysis`、`Phase32AmendmentApplyPlan` 与 `Phase32AmendmentApplyReceipt` 严格合同；
- 新增单一 `Phase32ArtifactAmendmentStore`，持久化 source-bound command、impact、apply plan、receipt 与 create/apply idempotency pointer；
- `Phase32ArtifactImpactAnalyzer` 只从 frozen route manifest、当前 committed Artifact、downstream refs 和 sequential accepted prefix 推导影响；
- `Phase32ArtifactAmendmentService` 复用既有 `Phase32ArtifactStore` 生成 candidate -> committed 新版本，通过同一个 projection recovery journal 原子提交 state/read model/event；
- receipt 在 projection 后中断时，通过 `active_amendment_id + expected committed ref + domain revision + event id` 确定性补齐，不重复推进 revision；
- `RunStatus` 新增 `needs_action`，`StageStatus` 新增 `stale`；state/read model 同时投影 amendment、stale stage 和 historical frozen stage，Repository 与 preflight 检查两者一致；
- `Phase32RunPreflight` 对 `needs_action` 或 stale stage 返回 `stale_artifact_execution_blocked`，Graph 和 Provider 不能继续；
- 三个 HTTP endpoint 已接入 `/api/runs` 权威路由，客户端传入自造 stale/impact 字段会被严格 payload 合同拒绝；
- amendment HTTP 适配已独立到 `api/routes/artifact_amendments.py`；`runs.py` 只保留 Run 生命周期、Artifact draft、交付和事件适配，共享 Run envelope 由 `api/dependencies.py` 提供，三条 URL 与响应合同不变；
- Version 20 Run 合同、解析器、历史状态和监控 rail 已能读取 `needs_action/stale`，stale 映射为 blocked；本轮没有提前增加修订表单或本地状态副本。

## 验证证据

- 三条官方路线均由 fake Provider 真实运行到 `completed / export` 后，从 committed Brief 创建和 apply amendment；Script/Text sequential accepted prefix 在 apply 前后完全一致；
- Scene Deck 删除已被 accepted Script 和 Export 引用的 `scene-2` 时，ImpactAnalysis 返回精确引用位置且 apply 被阻断；
- 未知 Cast ref、非 planning Artifact、非当前 source、frozen Scale target 漂移、create idempotency 冲突和 apply scope 冲突均被拒绝；
- apply 重放不增加 domain revision；模拟 projection 已提交、receipt 未写入后，下一次同命令能从 durable projection 恢复 receipt；
- amendment 定向测试：`8 passed, 1 warning`；warning 为既有 Starlette/httpx TestClient 弃用提示；
- amendment/API/边界组合回归：`60 passed, 1 warning`；生产 OpenAPI 中三条 amendment 路径各且仅各注册一次，方法保持 `POST / GET / POST`；
- 后端全量：`1101 passed, 1 warning`；
- 前端全量：`65 files / 155 tests passed`；
- Python `compileall`、TypeScript/Vite production build、frontend structure audit、CSS audit、CSS build check、production closure audit 与 `git diff --check`：通过；
- structure audit：`193` 个生产 TypeScript 文件，无异常 pipeline 顶层目录；
- CSS audit：`435351 bytes / 3168 rules / 3575 selectors`，跨文件重复 selector `0`；首屏 CSS `29.4 KiB gzip`；
- production build 仍有既存主入口与 `CharacterGraph3D` 大 chunk 提示，本轮没有增加新的 UI chunk 或 CSS；
- 本轮未启动 API/Vite，最终 `5176/8787` 均无监听。

## 验收边界

本轮证明 committed 规划 Artifact 的版本化修订、确定性影响、stale 阻断和恢复合同在本地成立；不证明 stale frontier 已能 repair/resume，也不证明 Canon/Wiki 写回、浏览器修订交互、真实 Provider 延迟/成本/稳定性或文学质量。README、CHANGELOG、commit、push、Tag 与 Release 继续等待 Phase 32 发布门。
