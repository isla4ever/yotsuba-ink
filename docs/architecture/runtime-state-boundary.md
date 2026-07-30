# 运行时状态边界与重构契约

本文冻结 Phase 1A 开始时 `useNovelWorkflowApp` 的公共职责、状态所有权和重构顺序。目标是在不改变路由、SSE、暂停恢复、阶段确认和 Artifact 语义的前提下，将组合 Hook 拆成可测试的状态边界。

## 1. 本阶段产品决策

- Phase 1A 只调整状态架构，不同时重做 UI、动画或阶段交互。
- 服务端 SSE 仍是运行事实源，前端不得用计时器制造业务完成状态。
- `useNovelWorkflowApp` 保留为应用组合门面，`App.tsx` 不直接组装底层 session、recovery 或 decision Hook。
- 先提取纯选择器和资源生命周期，再拆恢复与用户决策；Reducer 只用于必须原子更新的一组运行状态。
- React Bits、工作台布局和视觉 Token 继续后置到 Phase 2 及对应阶段 UI 改造。

## 2. 当前公共 API

公共类型为 `NovelWorkflowApp`。消费者按以下能力组使用，重构期间不得静默删除或改变语义。

### 2.1 工作流配置

- `workflow` / `setWorkflow`
- `selectedId` / `setSelectedId`
- `selectedStage`
- `selectedInspectorTarget` / `setSelectedInspectorTarget`
- `handleStageChange`
- `handleLayoutChange`
- `handleCanvasSelect`
- `handleAddModelOption`
- `handleQualityModeChange`
- `saveStatus`

### 2.2 运行状态

- `activeRunId`
- `events`
- `memoryEvents`
- `latestResult`
- `running`
- `paused`
- `runControlState`
- `runHasStarted`
- `runIsActiveFromEvents`
- `workspacePhase` / `setWorkspacePhase`
- `automationCockpitReady`
- `settlementStageId`
- `infoLoadingVisible`
- `infoLoadingRunKey`

### 2.3 运行命令

- `runWorkflow`
- `resetRunControl`
- `returnExportToPlanning`
- `setRunStageNavigator`

### 2.4 阶段决策

- `approvalDraft` / `setApprovalDraft`
- `approvalPending`
- `infoContinueReady`
- `checkpointContinueReady`
- `checkpointStageId`
- `approveBrief`
- `regenerateBrief`
- `confirmStageArtifact`
- `regenerateStageDraft`
- `selectDraftCandidate`
- `requestVariantCompare`
- `selectBalancedVariant`

### 2.5 壳层与辅助界面

- 设置、知识库、历史抽屉的 open 状态与 setter。
- `knowledgeDocuments`、刷新和删除回调。
- `apiWarning` / `setApiWarning`。
- `theme` / `setTheme`。

## 3. 状态所有权

| 边界 | 唯一职责 | 禁止承担 |
| --- | --- | --- |
| `runSelectors.ts` | 事件排序、阶段选择、恢复点、检查点、运行派生状态 | React 状态、计时器、网络 IO |
| `useRunSession.ts` | AbortController、session id、in-flight 生命周期 | 阶段决策、Artifact 解析、页面导航 |
| `useRunStreamController.ts` | 新建/既有 Run 的 SSE 消费、会话释放和迟到事件隔离 | 运行命令判断、阶段决策、页面过渡 |
| `useRunCommands.ts` | 启动、暂停、恢复、继续、Export 返回和恢复接线 | UI 渲染、Artifact 解析、局部组件状态 |
| `useRunTransitions.ts` | Info 加载、阶段结算遮罩和路由计时器生命周期 | 业务完成事件、运行终态判断、SSE IO |
| `useRunHistory.ts` | 本地运行历史去重、限长和持久化 | Run 控制、阶段导航、远端 IO |
| `useStageDecision.ts` | Info 审批、阶段定稿、继续门槛与决策状态组合 | SSE 生命周期、页面过渡计时器 |
| `useStageCandidates.ts` | Deep Draft 与 Balanced Variant 请求协议 | 阶段继续、运行恢复、模型伪评审 |
| `stageDecisionState.ts` | 决策状态的纯原子转换 | React 状态、网络 IO、路由 |
| `runState.ts` | 本地/后端快照 hydration | 流连接、UI 弹窗、用户命令 |
| `runReducer.ts` | 将单个 SSE 事件原子归并为稳定运行状态 | 阶段决策、网络 IO、路由副作用 |
| `storage.ts` | 本地持久化和历史序列化 | 运行编排、路由选择 |
| `useNovelWorkflowApp.ts` | 组合边界并暴露稳定应用 API | 新增长期纯逻辑或新的 IO 协议 |

## 4. 已完成进度

### Phase 1A.1：Selectors 与 Session

- 新增纯 `runSelectors.ts`，集中事件和阶段派生规则。
- 新增 `useRunSession.ts`，集中流会话的开始、失效、释放和卸载取消。
- `runState.ts` 保留 hydration，并兼容转出已有 selector 导出。
- `App.tsx` 改用显式 `NovelWorkflowApp` 公共类型，不再散落 `ReturnType`。
- 生产构建保持通过，没有修改 API 路由、阶段合同或用户操作顺序。

### Phase 1A.2：Run Recovery

- 新增 `useRunRecovery.ts`，恢复时先调用 `GET /api/runs/{run_id}`，不再直接相信 localStorage 布尔状态。
- 服务端运行中 snapshot 才会自动重连现有 run；待确认、已确认和安全暂停都恢复为明确暂停状态。
- 404、run id 不匹配、空 snapshot、completed 和 failed 状态会清理活动恢复点。
- 普通网络故障不会伪装成 404，也不会清空缓存；本地恢复点只读恢复为暂停态，不自动连接 SSE。
- 普通安全暂停不再被上一个阶段 checkpoint 污染，历史确认事件也不再永久锁住当前运行阶段。
- 前端加入 Vitest，覆盖运行中、待确认、Info 已确认、安全暂停、终态、无效 snapshot、404 和离线缓存恢复。

### Phase 1A.3：Stage Decision

- 新增 `useStageDecision.ts`，统一拥有 Info 审批、阶段定稿、决策状态恢复、继续准备和 Export 返回门槛。
- 新增 `useStageCandidates.ts`，Deep 继续使用 `draft_*` 手动选稿语义，Balanced 只在用户主动请求后映射为 `variant_*` 对比语义。
- 新增纯 `stageDecisionState.ts`，保证审批、定稿、继续和 Export 状态成组更新。
- `approval_required` 不再提前点亮 Info 继续按钮，普通 `run_paused` 不再复活历史 checkpoint。
- `useNovelWorkflowApp.ts` 保持公共 API 不变，并从 843 行降至约 630 行。
- 决策状态测试覆盖待审批、普通安全暂停、Info 批准、Deep 定稿、继续清理和 Export 返回门槛。

### Phase 1A.4：Run Reducer

- 新增纯 `runReducer.ts`，统一拥有 run id、事件、Memory 事件、运行控制、工作区、阶段选择和知识库阻断提示。
- SSE 事件改为一次 `event_received` dispatch，事件列表保持 newest-first 500 条，Memory 列表保持 40 条。
- 阶段决策事件由 `stageDecisionStateForEvent` 和 `useStageDecision` 独立消费，不再与通用运行状态混写。
- 路由回调和阶段结算计时器继续留在组合门面，Reducer 不执行副作用。
- 删除迁移期 `appEvents.ts`，新增 Run Reducer 与决策事件测试，覆盖恢复、重置、暂停恢复、失败和 Export 等状态。

### Phase 1A.5：Facade 收口

- 新增纯 `runCommandIntent.ts`，冻结主操作的继续、Export 返回、恢复、暂停和启动优先级，并加入分支测试。
- 新增 `useRunStreamController.ts`，在现有 session id 和 AbortController 之上统一新建/既有 Run 的流消费与释放。
- 新增 `useRunCommands.ts`，集中运行命令和错误恢复；恢复 API 成功但 SSE 重连失败时明确进入失败态，不再停留在伪运行状态。
- 运行命令增加代次校验和启动互斥：重置会使等待中的继续/恢复任务失效，Provider 就绪检查期间重复点击不会创建两个 Run。
- 新增 `useRunTransitions.ts`，集中 Info 加载与结算遮罩计时器，并在重置和卸载时清理。
- 新增 `useRunHistory.ts`，统一历史去重、最多 8 条和本地持久化。
- `useNovelWorkflowApp.ts` 保留为约 300 行的组合门面，公共 `NovelWorkflowApp` API 和三档模式流程保持不变。
- 本阶段以职责和回归稳定性为退出条件，不以继续压缩代码行数为目标。

## 5. 不变量

后续每个子阶段都必须保持：

1. 事件数组继续按 newest-first 存放，最多保留 500 条。
2. Memory 事件只保留 `memory_context_loaded` 和 `memory_writeback_completed`，最多 40 条。
3. Info 仍是 v1 强制人工闸门。
4. Deep 模式的非 Info 阶段必须在定稿后才能继续，Export 只负责返回工作台。
5. Fast 和 Balanced 的路由策略继续服从 `runPresentationState.ts`。
6. 暂停必须先请求后端，并等待 `run_paused`；恢复必须复用既有 run id。
7. 刷新恢复不得把 completed、failed 或 stale run 误判为运行中。
8. Artifact 缺失或无效时不得回退成固定完整演示稿。
9. 任何过渡计时器只控制视觉和导航，不产生业务完成事件。

## 6. 后续拆分顺序

### Phase 1B.1：Stage View 边界

- Info、Cover、Export 继续使用已有独立视图。
- Summary、Outline、Detail、Writing 已从 769 行 `StageRunViews.tsx` 拆为四个阶段专用文件，旧聚合文件已删除。
- 共享流式分段和结构化写回预览收口到纯 `stageViewData.ts`，共享轻提示收口到 `StageToast.tsx`。
- 所有类名、Artifact 解析、Dialog 回调、只读状态和阶段路由保持不变；辅助函数加入回归测试。
- 没有建立新的通用 `components/`、`dialogs/` 或平行顶层目录。

### Phase 1B.2：Stage Workbench 组合边界

- `StageRunWorkbench.tsx` 已收口为状态协调和页面装配层，由 `StageRunMainArea.tsx` 独立承载主产物区切换。
- `RuntimeInsights.tsx`、`RuntimeInsightPanel.tsx` 和 `RuntimeSideDetailSheet.tsx` 分别拥有阶段侧栏、洞察内容和全局详情层职责。
- Info 生成锁定与编辑同步计时器进入 `useInfoStageFeedback.ts`，卸载时统一清理，不再和工作台 JSX 混写。
- Balanced Variant 与 Deep Draft 聚焦判定进入纯 `stageRunFocus.ts` 并加入回归测试；人物图谱映射也加入测试。
- 阶段面板矩阵、CSS 类、动效参数、Artifact 回调和现有视觉布局保持不变，未提前进入 Phase 2 视觉重设计。

### Phase 1C：运行样式边界

- `Phase 1C.1` 已完成：将 `stage-run.css` 最前面的 922 行连续基础层拆为布局、Info 加载、运行壳层、正文、通用 Artifact、Outline/Detail 和 Cover/Export 七个文件。
- 七段样式继续按原始顺序加载；拆分后重新拼接的 SHA-256 与迁移前文件完全一致，没有改动选择器、声明或视觉值。
- `stage-run.css` 从 13,531 行降至 12,609 行，后续覆盖链继续原样保留，避免一次重排多轮历史覆盖。
- 固定 `1280x920` 的 Export 阶段页迁移前后 PNG 逐字节一致，规划页无横向溢出，控制台无错误或警告。

#### Phase 1C.2：Artifact 与 Detail 样式边界

- 已从剩余文件开头连续提取 1,991 行，形成 Artifact v4、Detail 施工表、Detail 账本、Detail 写回、章节蓝图、写回弹窗、写回中心、正文流式、Cover 质量、Export 工作台和 Summary 优先级文件。
- 所有新文件按 CSS 顶层规则的原始位置顺序导入，最大文件 285 行；没有拆断规则、媒体查询或关键帧。
- Phase 1C.1 与 1C.2 的全部文件重新拼接后，SHA-256 仍与最初 13,531 行文件完全一致；生产构建的 CSS 资源哈希未变化。
- `stage-run.css` 进一步从 12,609 行降至 10,618 行；前两批累计迁出 2,913 行。
- Summary、Detail、Export 固定视口回归通过，Detail 前后 PNG 逐字节一致，三页均无横向溢出且控制台保持干净。

#### Phase 1C.3：Info、运行洞察与阶段交互样式边界

- 已从剩余文件开头连续提取 5,097 行，按原始出现顺序形成 28 个职责文件，覆盖 Summary/Outline 最终布局、Export 兼容层、Info 编辑与推荐、运行侧栏与洞察、阶段过渡与结算、详情 Sheet/Dialog、正文阅读器、候选决策和草稿重生成。
- 所有切点均位于 CSS 顶层规则之间；空行也归入相邻文件，未拆断选择器、媒体查询或关键帧，最大新文件 295 行。
- Phase 1C.1-1C.3 的 47 个 `stage-run*` 文件合计仍为 13,531 行、329,198 字节；按导入顺序重组的 SHA-256 保持 `70978d2d396fc5eb78bfba051c94f0aa3beabaf555845f80dbf8eca73526575e`。
- `stage-run.css` 从 10,618 行降至 5,521 行，三批累计迁出 8,010 行；生产 CSS 资源仍为 `index-DaYcH6wl.css`，证明最终 cascade 产物未变化。
- 前端 41 个测试、Python 63 个测试、生产构建和依赖审计通过；`1280x920` 浏览器验收无横向溢出，控制台无错误或警告，前后截图人工对照无结构位移。

#### Phase 1C.4：Artifact 历史工作台样式边界

- 已从剩余文件开头连续提取 1,813 行，形成 acceptance polish、Artifact v2、Artifact v3 Summary/Outline/Delivery 和 Artifact v6 Summary/Outline/Detail/Cover/Delivery 共 9 个文件。
- 所有文件保持原始顶层规则顺序，最大文件 278 行；媒体查询和关键帧均与所属历史块一起迁移，没有按同名选择器跨版本合并。
- Phase 1C.1-1C.4 的 56 个 `stage-run*` 文件合计仍为 13,531 行、329,198 字节；完整重组 SHA-256 继续保持 `70978d2d396fc5eb78bfba051c94f0aa3beabaf555845f80dbf8eca73526575e`。
- `stage-run.css` 从 5,521 行降至 3,708 行，四批累计迁出 9,823 行；生产 CSS 资源仍为 `index-DaYcH6wl.css`。
- 前端 41 个测试、Python 63 个测试、构建和审计通过；`1280x920` 浏览器无横向溢出且控制台干净，前后截图差异仅来自动态线条、发光与抗锯齿帧。

#### Phase 1C.5：Summary 专项工作台与编辑弹层样式边界

- 已从剩余文件开头连续提取 2,754 行，形成 16 个 Summary 文件，覆盖 specialist 核心与关系写回、IA 与最终构图、轨道 polish、结构轨道、基础编辑弹层、人物深化和 modal v3-v6。
- 所有切点均位于顶层规则之间；同一历史版本内按主工作台、关系区或人物弹层职责拆分，不跨版本合并同名选择器，最大文件 287 行。
- Phase 1C.1-1C.5 的 72 个 `stage-run*` 文件合计仍为 13,531 行、329,198 字节；完整重组 SHA-256 保持 `70978d2d396fc5eb78bfba051c94f0aa3beabaf555845f80dbf8eca73526575e`。
- `stage-run.css` 从 3,708 行降至 954 行，五批累计迁出 12,577 行；生产 CSS 资源继续为 `index-DaYcH6wl.css`。
- 前端 41 个测试、Python 63 个测试、构建和审计通过；浏览器无横向溢出，控制台无错误或警告，完整 CSS 字节等价保证 Summary 层叠结果不变。

#### Phase 1C.6：Outline v3 样式边界与 Phase 1C 收尾

- 已将最后 954 行 Outline workbench v3 拆为主工作台与节拍矩阵、依赖弹层、依赖编辑器、节拍编辑器、洞察与响应式规则 5 个文件，最大文件 279 行。
- 旧 `stage-run.css` 及其导入已删除；没有留下空文件、兼容转发或临时脚本。
- Phase 1C 最终形成 76 个 `stage-run*` 文件，总计仍为 13,531 行、329,198 字节；完整重组 SHA-256 保持 `70978d2d396fc5eb78bfba051c94f0aa3beabaf555845f80dbf8eca73526575e`。
- 前端 41 个测试、Python 63 个测试、生产构建与依赖审计通过，生产 CSS 资源仍为 `index-DaYcH6wl.css`。
- `1280x920` 浏览器验收无横向溢出，控制台无错误或警告；截图差异仅来自 React Flow 动态线条、发光和抗锯齿帧。
- Phase 1A、1B、1C 的状态、视图、工作台和样式边界重构现已完成。下一阶段进入 Phase 2 设计系统与全局壳层升级，视觉变更必须独立于本轮等价重构验收。

## 7. 每步验收

- `npm run build`。
- 前端状态单元测试和公共 API 类型检查。
- Python 全量测试。
- `git diff --check`。
- 对 Fast、Balanced、Deep 的启动、暂停、恢复、Info 确认、Deep 定稿继续做浏览器回归。
- 固定视口无横向溢出，控制台无新增错误或警告。
