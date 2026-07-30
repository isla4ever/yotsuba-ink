# Yotsuba Ink 运行状态与事件矩阵

本文档冻结三档模式的运行状态、路由权限、Header 主操作和主要 SSE 事件职责。它与 `stage-artifact-contract.md` 一起构成 Phase 0 基线。

## 1. 事实源优先级

运行状态按以下优先级确定：

1. 后端 Run Store 中的持久化状态与已保存事件。
2. 当前 SSE 流收到的服务端事件。
3. 刷新恢复接口 `GET /api/runs/{run_id}` 返回的快照。
4. 服务端 `GET /api/runs/history` 返回的历史摘要只用于选择和只读展示，不覆盖当前 Run State。
5. 前端 `workspacePhase` 只决定当前界面形态，不决定业务是否正在运行。

前端不得使用组件挂载时间、局部延时器或演示 Fixture 推导阶段已完成、质量已通过或候选已生成。

## 2. 三档模式矩阵

| 维度 | 极速生产 `fast` | 平衡创作 `balanced` | 精细定稿 `deep` |
| --- | --- | --- | --- |
| 配置主界面 | 单页 cockpit 配置态 | 标准 Planning | 标准 Planning |
| 启动后首个页面 | 原地 cockpit | `/run/info` | `/run/info` |
| Info 闸门 | 无 | 必须人工确认 | 必须人工确认 |
| Info 后界面 | cockpit 自动运行 | cockpit 自动运行 | 对应 `/run/*` 阶段页 |
| Summary 至 Cover 闸门 | 无 | 无 | 每阶段人工定稿 |
| Export 闸门 | 无 | 无 | 不阻断生成；完成后人工返回 |
| 阶段路由 | 禁止 | Info 闸门前仅 `/run/info` | 全部阶段路由 |
| 运行中主操作 | 锁定为“极速生产运行中” | “暂停创作” | “暂停创作” |
| 暂停语义 | 不提供 | 请求后端安全点暂停 | 请求后端安全点暂停 |
| 模式切换 | 未启动或终态 | 未启动或终态 | 未启动或终态 |
| 版本策略 | 单版本 | 用户主动请求对比 | 换稿后手动选稿 |

## 3. Header 主操作矩阵

| 判定状态 | 服务端/前端证据 | 主按钮 | 可点击 | 点击结果 |
| --- | --- | --- | --- | --- |
| 配置态 | 无可恢复 Run | 开始生产/开始创作 | 是 | 创建 Run 并连接 SSE |
| 启动中 | `runControlState=starting` | 运行中 | 否或暂停 | 等待 `run_started` |
| 极速运行 | `fast` + `run_started/node_started` | 极速生产运行中 | 否 | 无 |
| 平衡/精细运行 | `running` | 暂停创作 | 是 | `POST /pause`，等待安全点 |
| 暂停请求中 | `stop_requested` | 正在请求暂停 | 否 | 等待 `run_paused` |
| 已安全暂停 | `run_paused` | 继续创作 | 是 | 恢复现有 Run SSE |
| Info 待确认 | `approval_required` + Info | 等待人工确认 | 否 | 在 Info 主区确认 |
| 阶段待定稿 | `stage_checkpoint_ready` + Deep | 等待阶段定稿 | 否 | 在阶段主区确认 |
| Info 已确认 | `stage_artifact_confirmed` + Info | 继续进入梗概 | 是 | 结算遮罩后继续 |
| 阶段已确认 | `stage_artifact_confirmed` | 继续下一阶段 | 是 | 结算遮罩后继续 |
| Export 就绪 | `run_export_ready`/Export checkpoint | 返回控制台 | 是 | 回到 Planning |
| 失败 | `node_failed/run_error` | 重新开始 | 是 | 回到配置并新建 Run |
| 完成 | `run_completed` | 开始新创作 | 是 | 新建 Run |
| 历史完成项 | `GET /api/runs/history` + `status=completed` | 查看摘要/重新下载 | 不可恢复 | 不装载到运行工作台 |
| 历史待恢复项 | `recovery_required` + 最新稳定快照 | 恢复稳定检查点 | 是 | `POST /restore-snapshot`，只落盘暂停态 |

主按钮展示逻辑由 `state/runPresentationState.ts` 统一派生。组件不得再次组合 `running/paused/approvalPending` 生成另一套文案。

## 4. 路由矩阵

| 模式状态 | `/planning` | `/run/info` | 其他 `/run/*` |
| --- | --- | --- | --- |
| Fast 未启动 | cockpit 配置态 | 重定向 Planning | 重定向 Planning |
| Fast 已启动 | cockpit 运行态 | 重定向 Planning | 重定向 Planning |
| Balanced Info 前 | 标准 Planning | 允许 | 重定向 Planning |
| Balanced Info 后 | 自动 cockpit | 重定向 Planning | 重定向 Planning |
| Deep 未启动 | 标准 Planning | 启动后允许 | 无 Run 时重定向 Planning |
| Deep 已启动 | 可返回工作台 | 允许 | 允许 |

路由只承载导航位置。当前阶段、Artifact、确认状态和恢复位置仍保存在 Run Store 和工作流状态中。

## 5. Checkpoint 合同

| 模式 | Checkpoint 阶段 | 后端等待 |
| --- | --- | --- |
| Fast | 无 | 否 |
| Balanced | Info | 是 |
| Deep | Info、Summary、Outline、Detail、Text、Cover | 是 |
| Deep Export | 无生成阻断 | 完成后停留 Export，用户手动返回 |

唯一 checkpoint 事件为 `stage_checkpoint_ready`。`demo_checkpoint_ready` 已移除，不再生产或消费。

## 6. 主要 SSE 事件账本

### 6.1 Run 生命周期

| 事件 | 生产者 | 主要消费者 | 职责 |
| --- | --- | --- | --- |
| `run_started` | `orchestration/stream.py` | `state/runReducer.ts`、Header、cockpit | Run 已创建并开始执行 |
| `run_resumed` | `orchestration/control.py`、`api/routes/runs.py` | `state/runReducer.ts` | 从安全点恢复 |
| `run_pause_requested` | `api/routes/runs.py` | Run Store、日志 | 已接受暂停请求，不代表已经暂停 |
| `run_paused` | `orchestration/control.py` | `state/runReducer.ts`、`state/runState.ts` | 已到后端安全点，可以继续 |
| `run_completed` | `orchestration/stream.py` | `state/runReducer.ts`、恢复逻辑 | 全链路完成 |
| `run_failed` / `run_error` | `orchestration/stream.py`、`api/sse.py` | `state/runReducer.ts`、Artifact 错误态 | Run 终止失败 |
| `run_snapshot_restored` | `storage/run_snapshot_store.py`、`api/routes/run_history.py` | 历史抽屉、运行恢复状态 | 已恢复到最新稳定检查点，但仍需用户明确继续 |

### 6.2 阶段与 Artifact

| 事件 | 生产者 | 主要消费者 | 职责 |
| --- | --- | --- | --- |
| `phase_changed` | `orchestration/chapters.py` | `state/runReducer.ts` | 进入正文等显式阶段 |
| `node_started` | `orchestration/stream.py` | Header、Canvas、cockpit、Artifact 状态 | 阶段开始 |
| `artifact_validated` | `orchestration/stream.py` | 日志/诊断 | 结构合同通过 |
| `artifact_validation_failed` | `stream.py`、`chapters.py`、`draft_regeneration.py` | `state/runReducer.ts`、Artifact 错误态 | 结构合同失败 |
| `node_completed` | `stream.py`、`chapters.py` | 全局状态、阶段页、cockpit | 真实 Artifact 已完成 |
| `node_failed` | 编排、质量、正文链路 | 全局状态、阶段页、cockpit | 阶段失败 |
| `stage_checkpoint_ready` | `orchestration/control.py` | Header、恢复、cockpit | Artifact 已生成，等待用户定稿 |
| `approval_required` | `orchestration/control.py` | `state/runReducer.ts`、`state/useStageDecision.ts`、阶段页 | 打开人工确认闸门 |
| `stage_artifact_confirmed` | `orchestration/control.py` | Header、恢复、阶段决策 | 用户定稿完成 |
| `artifact_approved` | `control.py`、`api/routes/runs.py` | Info 基线、恢复 | 已批准 Artifact 写回 |

### 6.3 候选与版本

| 事件组 | 生产者 | 主要消费者 | 模式 |
| --- | --- | --- | --- |
| `draft_regeneration_requested` | `draft_regeneration.py` | 精细模式候选页 | Deep |
| `draft_candidate_stream_delta` | `draft_regeneration.py` | 候选列流式预览 | Deep |
| `draft_candidate_generated` | `draft_regeneration.py` | `StageCandidateCompare` | Deep |
| `draft_candidate_selected` | `draft_regeneration.py` | Artifact 当前版本、确认逻辑 | Deep |
| `variant_generated` | `variants.py`、正文编排 | 平衡模式对比页、cockpit | Balanced |
| `best_variant_selected` | `variants.py`、正文编排 | 当前 Artifact、cockpit | Balanced |

### 6.4 正文、质量与写回

| 事件组 | 生产者 | 主要消费者 |
| --- | --- | --- |
| `chapter_started/chapter_delta/chapter_completed` | `orchestration/chapters.py` | 正文阅读器、cockpit 日志、章节进度 |
| `chapter_progress_updated` | `orchestration/chapters.py` | Header、正文导航、cockpit |
| `quality_check_started/quality_check_completed` | `quality.py`、`chapters.py` | 质量阀门、Canvas、cockpit |
| `revision_directive_created/revision_applied/quality_recheck_completed` | `quality.py`、`chapter_review.py` | 正文质量过程条、质量阀门、版本绑定 repair target |
| `chapter_summary_synced/chapter_writeback_proposal_generated` | `chapter_review.py` | 正文上下文栏、Wiki/人物提案预览 |
| `chapter_writeback_proposal_accepted/rejected` | `chapter_review.py` | Deep 定稿门禁、Wiki/人物/伏笔写回 |
| `canon_facts_committed` | `chapter_commit.py`、`chapter_final_artifact.py` | Wiki Canon 事实层、恢复快照、冲突追踪 |
| `memory_context_loaded/memory_writeback_completed` | `orchestration/stream.py` | Wiki、运行日志、cockpit |
| `character_graph_updated` | `stream.py`、`chapters.py` | 人物关系网 |
| `worldbuilding_updated` | `chapters.py` | 世界观运行面板 |
| `wiki_state_updated/story_bible_updated` | `chapters.py` | Wiki 与连续性视图 |
| `stage_usage_updated/stage_usage_finalized` | 编排与正文链路 | Header 使用量和诊断 |
| `run_recovery_required` | `orchestration/stream.py` | Header 暂停态、恢复提示、最后稳定 Checkpoint |
| `run_checkpoint_recovery_requested` | `api/routes/runs.py` | 恢复确认、SSE 重连起点 |

### 6.5 预算与人工介入

| 事件 | 生产者 | 前端结果 | 约束 |
| --- | --- | --- | --- |
| `stage_budget_warning` | `usage/budget.py` | 运行状态区显示当前阶段预警 | 不暂停；同一 scope 只发一次 |
| `run_budget_warning` | `usage/budget.py` | 运行状态区显示全 Run 预警 | 仅配置 Run 总上限时产生 |
| `stage_budget_exceeded` | `usage/budget.py` | 暂停并显示阶段预算已用尽 | 在 Provider 调用前产生 |
| `run_budget_exceeded` | `usage/budget.py` | 暂停并显示本次运行预算已用尽 | 在 Provider 调用前产生 |
| `manual_intervention_required` | `usage/budget.py`、`quality.py` | 暂停，保留当前 Artifact 与最后稳定 Checkpoint | 预算、重试或质量循环耗尽后产生 |

`budget_state` 与事件一起持久化，包含 scope 上限、已消费/预留 Token、候选/评审/修订/retry 计数和人工介入原因。刷新只恢复账本，不重新授权 Provider 调用；显式 Checkpoint 恢复才允许进入受限 retry。

## 7. 已登记的生产缺口

以下事件当前存在前端消费位置，但没有真实后端生产者：

- `artifact_stream_delta`：Summary、Outline、Detail 的结构化渐进输出尚未由 Provider/编排层真实产生。
- `asset_progress_updated`：封面资产生成进度尚未由图片 Provider 链路产生。
- `stage_summary_ready`：cockpit 保留消费逻辑，但当前编排不生产。

处理原则：在对应编排或 Provider 能力落地前，前端只展示真实的 `node_started -> node_completed` 状态，不使用定时器模拟这些事件。

## 8. 恢复路径

1. 前端从本地读取 `run_id`，但不把本地布尔值当成最终事实。
2. 调用 `GET /api/runs/{run_id}` 获取事件、审批、checkpoint 和 `runtime_phase`。
3. `state/runState.ts` 按最新服务端事件恢复选中阶段、暂停态和继续权限。
4. 找不到 Run 时清除本地运行控制，返回 Planning。
5. 恢复后只有收到 `node_started` 且没有对应终态事件，才显示运行中。
6. 服务端存在 `recovery_state.needs_recovery` 时，失败运行仍作为暂停态恢复；点击“继续创作”才调用 `/resume` 清理活动错误并从稳定 Checkpoint 继续。熔断打开时 `/resume` 拒绝自动重试。
7. 历史抽屉先读取轻量摘要；已完成 Run 只读展示，待确认/暂停 Run 才能打开工作台。待恢复 Run 点击“恢复稳定检查点”后，服务端校验 `snapshot_id` 属于当前 Run 且为最新稳定点，保留预算和失败审计并保持暂停，不自动建立 SSE 或调用 Provider。
8. 导出收据绑定 `export_id + snapshot_id + artifact_signature`。历史重新下载读取不可变文件，不根据当前最新状态悄悄重建旧包。

## 9. 验收路径

- Fast：Planning cockpit -> 启动 -> 自动全链 -> 完成。
- Balanced：Planning -> `/run/info` -> 确认 -> 自动 cockpit -> Export。
- Deep：Planning -> Info -> Summary -> Outline -> Detail -> Text -> Cover -> Export，每阶段确认后继续。
- Pause：Balanced/Deep 运行中点击暂停 -> `run_pause_requested` -> `run_paused` -> 继续。
- Recovery：在运行、待确认、安全暂停三种状态分别刷新，页面状态与 Header 操作保持一致。
- Failure：结构校验失败时展示真实错误，不出现成功 Artifact 或自动跳转。
- Circuit breaker：同一阶段/章节连续 3 次失败后停止自动恢复；失败历史、恢复次数和最后稳定 Checkpoint 保留在 Run State。
