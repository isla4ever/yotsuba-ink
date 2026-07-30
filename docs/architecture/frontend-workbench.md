# 前端工作台

## 职责

前端是一个 React 工作台，当前有两个主要产品状态：

- `planning`：配置流水线、调整阶段、查看规划态信息
- `running`：跟踪阶段执行、查看运行中产物和质量反馈

## 入口文件

- 应用壳层：[apps/web/src/App.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/App.tsx)
- 应用状态 Hook：[apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts)
- 规划态工作台：[apps/web/src/features/pipeline/planning/PlanningWorkbench.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/planning/PlanningWorkbench.tsx)
- 运行态工作台：[apps/web/src/features/pipeline/running/RunningWorkbench.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/running/RunningWorkbench.tsx)
- 阶段运行装配：[apps/web/src/features/pipeline/running/StageRunWorkbench.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/running/StageRunWorkbench.tsx)
- 阶段主产物区：[apps/web/src/features/pipeline/running/StageRunMainArea.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/running/StageRunMainArea.tsx)

## 数据流

1. `useNovelWorkflowApp` 组合应用级状态并保持公共 API。
2. `services/` 封装 API 请求和 SSE 消费逻辑。
3. `state/runReducer.ts` 把后端事件原子归并为稳定运行状态。
4. `state/useStageDecision.ts` 独立处理审批、定稿和继续门槛。
5. `state/useRunCommands.ts` 和 `state/useRunStreamController.ts` 处理命令与流生命周期。
6. `state/useRunTransitions.ts` 只管理加载与结算视觉计时器。
7. 各个 workbench 再根据 props 组装局部 UI。

## 关键模块

- `layout/AppHeader.tsx`：品牌、配置/运行事实进度、全局工具与主操作三轨；运行文案只消费统一 presentation state
- `planning/PipelineCanvas.tsx`：规划态阶段链路、节点选择与布局持久化；标准 Planning 不渲染 Wiki/质量运行层
- `planning/StageInspector.tsx`：阶段主参数、生成模型和折叠高级配置
- `lib/planningReadiness.ts`：阶段必填完成度与业务产物名称的纯派生
- `running/StageRunWorkbench.tsx`：运行态状态协调和页面装配
- `running/StageRunMainArea.tsx`：阶段主产物切换和过渡
- `running/RuntimeInsights.tsx`、`RuntimeInsightPanel.tsx`：按阶段合同组装运行洞察与紧凑入口
- `running/RuntimeSideDetailSheet.tsx`：紧凑洞察入口的全局详情层
- `running/SummaryStageView.tsx`、`OutlineStageView.tsx`、`DetailStageView.tsx`、`WritingStageView.tsx`：阶段专用 Artifact 工作台
- `state/useInfoStageFeedback.ts`：Info 生成锁定与编辑同步反馈计时器
- `running/infoRecommendationModel.ts`：Info 结构化产物归一化、合同字段保留和定稿就绪检查
- `running/outlineArtifactModel.ts`：Info/Summary 基线、Outline 完整度、当前稿写回预览和人物图谱投影
- `running/detailArtifactModel.ts`：Info/Outline 引用基线、Detail 章节完整度、当前稿写回摘要和人物图谱投影
- `running/writingArtifactModel.ts`：正文 Artifact 归一化、按章 Context 匹配、人工版本更新和完整度门禁
- `running/chapterSelectionModel.ts`：textarea UTF-16 选区和章节编辑签名
- `running/ChapterSelectionToolbar.tsx`、`ChapterRevisionPreview.tsx`、`ChapterVersionHistory.tsx`：选区命令、候选确认和前进式版本恢复
- `state/useChapterRevision.ts`：局部修订生成/接受/恢复状态与已落盘基线维护
- `running/WritingChapterNav.tsx`、`WritingContextPanel.tsx`、`WritingRevisionHistory.tsx`：正文连续左栏的章节、上下文与修订轨迹
- `running/WritingWorkbenchLayout.tsx`、`WritingChapterWorkspace.tsx`、`WritingReviewRail.tsx`：正文最大工作面、写作/审校双任务布局和紧凑侧 Rail
- `running/WritingMobileDock.tsx`、`WritingMobileSheet.tsx`：移动端正文单栏、章节/审校任务入口和 Busy 安全的全屏 Sheet
- `running/writingViewMode.ts`、`state/useWritingViewport.ts`：纯布局视图状态、专注返回目标和按章节/布局恢复滚动与选区
- `running/OutlineCharacterCarryDialog.tsx`、`OutlineWorldCarryDialog.tsx`、`OutlineForeshadowLedgerDialog.tsx`：三类独立结构对象编辑，不执行确认前正式写回
- `running/ChapterBlueprintDialog.tsx`：只编辑章节施工字段，POV 从已确认人物中选择
- `running/DetailCharacterShiftDialog.tsx`、`DetailWorldWikiDialog.tsx`、`DetailForeshadowDialog.tsx`：人物、事实/Wiki、伏笔三类独立结构对象编辑，不执行确认前正式写回
- `running/DetailWritebackDialogShell.tsx`、`DetailWritebackFields.tsx`：三类 Detail 写回弹窗共享的全局遮罩、章节切换、字段原语与稳定 Footer，不合并业务语义
- `running/InfoCharacterRoster.tsx`：Info 主区人物档案 ledger 与编辑入口
- `running/stageCandidateModel.ts`：当前三栏候选与历史候选的纯事件派生
- `running/StageCandidateCompare.tsx`、`StageCandidateHistoryDialog.tsx`：手动选稿和历史恢复
- `settings/KnowledgeBaseManagerDialog.tsx`：知识库上传和管理
- `settings/SettingsDialog.tsx`：Provider 和运行设置

## 为什么要这样拆

这样拆的目的，是避免 UI 组合、API 请求、事件归并和状态持久化全都塌进一个大 Hook 或一个大页面组件里。

基本规则是：

- workbench 决定页面布局
- 组件负责局部 UI 呈现
- `services` 负责和后端通信
- `state` 负责把后端事件翻译成前端状态

## Planning 配置合同

标准 Planning 是启动前配置工作台，不是运行观测页：

- Pipeline Canvas 只显示七个生产阶段，节点表达阶段产物和必填配置完成度。
- 640px 以下使用横向阶段标签栏提供稳定选择入口，不要求用户操作被整体缩小的 React Flow 节点。
- Wiki、质量阀门、人物关系和世界观不作为标准 Planning 节点或 Inspector 入口。
- Stage Inspector 首屏只展开当前阶段参数和生成模型。
- 阶段标识、Memory、版本策略和质量阈值保留完整编辑能力，但统一收进“高级阶段设置”。
- 知识库状态带只显示文档、片段、索引后端、当前资料和联网参考状态，不重复展示同一组准备指标。
- 阶段必填项由 `planningReadiness.ts` 单点派生，Canvas 和 Inspector 不允许各自计算一套完成度。

Fast 配置态 cockpit 仍可以使用自己的纵向画布和配置抽屉，但不能把未发生的运行事件伪装成产物、质量分或 Wiki 写回。

## Info 人工闸门合同

- 平衡和精细模式进入 Info 后都必须等待人工确认；极速模式继续自动运行，不显示换稿闸门。
- Info 编辑草稿只使用 `InfoRecommendation` 合同字段，人物成长方向、下游约束和内部风险在编辑回写中保持不丢失。
- 主区人物 ledger、右侧人物关系网和世界观面板消费同一个 `approvalDraft`；保存人物或世界观后由 `useInfoStageFeedback` 提供局部同步反馈。
- 换稿不再调用单稿覆盖接口或固定成功计时器，而是进入最多三栏候选焦点态；事件失败后立即退出焦点态并保留原稿。
- 候选使用后端 `candidate_id` 做稳定选择键，展示标签继续使用“候选 1/2/3”；历史候选可以恢复，但恢复后仍不得绕过确认推荐。
- 确认按钮先通过前端就绪检查，再提交后端产物合同校验；只有审批成功才进入 `infoContinueReady`。

## Summary 定稿与写回合同

- `SummaryStageView` 渲染完整结构化 Artifact，故事核心、完整梗概、结构节拍、关键转折、人物弧、主线冲突、结局承诺和一致性检查都可编辑。
- `StageRunWorkbench` 按阶段保存与来源稿绑定的编辑稿；候选源变化后旧稿失效，避免旧编辑覆盖新候选。人物图谱预览始终从当前 Summary 稿和 Info 已确认人物基线派生。
- `StageDecisionControls` 只有在阶段生成完成、无候选生成任务、Artifact 完整且未提交时才开放“确认定稿”，提交期间显示真实等待状态并防止重复点击。
- 确认调用把当前编辑稿传给真实审批接口。接口失败时保持待确认状态；只有后端成功后才进入已定稿状态并锁定编辑。
- Summary 侧栏展示的是当前稿写回预览，不代表已经成为正式记忆。Deep 需人工确认，Fast/Balanced 需自动定稿，之后后端才更新人物图谱、Story Bible 和 Memory。
- 当前稿选择和候选失效规则由纯函数覆盖测试；Summary 完整度、人物引用和关系压力由前后端双重校验。

## Detail 定稿与写回合同

- `StageRunWorkbench` 不保存独立 Detail 写回预览状态；侧栏摘要和人物图谱直接从与来源稿绑定的当前 Detail 编辑稿派生。
- `DetailStageView` 的章节蓝图和三类写回编辑都会提交完整当前稿，确认请求消费该稿；界面保存文案只声明“保存到当前稿，定稿后写回”。
- POV、人物变化主体和关系对象从 Info 已确认人物选择；事实/Wiki 锚点从 Info 世界观和 Outline 揭示中选择；伏笔可以承接 Outline 或创建 Detail 新线索。
- `detailReadiness` 在前端阻断缺字段、未知引用、重复章节和同章重复伏笔，后端仍执行最终合同与引用校验。
- 390px 下命令指标两列、三类写回入口单列，章节表整表横向滚动；蓝图和写回弹窗均保持视口内单一内容滚动区。

## 正文工作台合同

- `WritingStageView` 消费结构化正文 Artifact；流式事件只补充尚未落盘的章节内容，不再把事件流当成最终稿唯一来源。
- 当前章节由稳定 chapter id 选择；Context Packet 必须同时匹配章节事件和 packet 自身的 `chapter`，历史章节切换不会显示其他章上下文。
- 桌面使用写作/审校双任务布局：写作态展开章节工作区并收起审校 Rail，审校态收起章节 Rail 并展开质量/事实写回 Inspector；正文稿纸始终是最大工作面。
- 专注态只隐藏两侧任务区，`Escape` 恢复进入专注前的视图；写作/审校/专注都是布局状态，不修改 Artifact，也不触发 Provider、`/resume`、SSE 或写回请求。
- 左侧完整工作区按章节导航、当前章上下文、摘要和修订轨迹连续排列；右侧审校区只保留质量审校/事实写回两个 Tab，人物/世界观使用现有运行详情入口。
- 390px 使用正文单栏与底部章节/审校 Dock，两类任务通过 Portal 全屏 Sheet 承载；Busy 时关闭按钮、Backdrop 和 Escape 同步锁定。
- 流式章节只读并自动跟随，已完成章节可编辑。首次人工编辑只增加一个版本；连续输入不反复增加版本，且必须同步章节摘要后才恢复定稿就绪。
- `StageRunWorkbench` 继续用来源签名保存正文当前稿；`StageRunMain` 的确认请求提交该稿，候选源变化后旧编辑稿失效。
- `writingReadiness` 检查目标章节数、正文身份/内容/状态/字数、章节 Context 和摘要同步状态；缺项在 Deep 定稿条明确列出。
- 非空且不超过 6000 UTF-16 code units 的正文选区才显示紧凑工具条；重写、扩写、压缩可直接生成候选，换风格必须填写目标风格。生成中不开放重复命令。
- 候选以全局居中预览展示修订前/候选替换，用户接受前不修改稿纸；接受后刷新完整结构 Artifact，并清空当前选区。API 冲突直接显示可读错误，不用定时器伪造成功。
- 修订轨迹标题提供历史版本入口；历史以 ledger 展示来源、版本和正文摘要。恢复操作关闭弹层前必须等待服务端创建新版本成功，禁止前端本地回退版本号。
- 局部接受后 `summary_dirty=true`，左栏章节摘要立即显示待同步；编辑摘要本身不会本地解除阻断，只有“同步摘要并复检”接口成功后才清除脏标记。
- 左栏在摘要下方就地显示复检分数、阻断问题和 Wiki/人物/伏笔提案数量。提案明确标记“待决策/待定稿写回”，接受或拒绝前 `writingReadiness` 继续阻断；正式 Memory/Wiki 写回仍只发生在定稿链路。
- 质量侧栏优先显示当前章节复检，人物与 Wiki 侧栏只显示提案预览；提案未正式提交前禁止使用“已同步/已写回”文案。
- 质量 finding 可从左栏或质量侧栏发出同一个 repair intent；`StageRunWorkbench` 只负责协调切章，`WritingStageView` 校验章节 ID、版本、签名和 UTF-16 原文后设置 textarea 选区。失效 target 只提示重新复检，不发起修订请求。
- 质量修订命令条只提供问题、选区、后端建议方向和一次“生成候选”确认；接受候选后清理 intent，并继续复用 `summary_dirty -> 摘要同步 -> 复检 -> 写回提案` 闭环。
- 写回提案存在 Canon 冲突时，左栏显示既有事实与新事实的紧凑对照；“接受”按钮在每条冲突选择前保持禁用。用户明确选择后，决策随提案请求提交，Wiki 面板显示事实来源、已解决冲突和仍待处理冲突。
- `useWritingViewport` 按 `chapterId + compact/desktop + viewMode` 保存滚动、光标和选区；切章、切视图和从移动 Sheet 返回时不得把旧章选区错误恢复到新章。
- 修订生成、候选接受、版本恢复、摘要复检和提案决策期间统一锁定切章；对应弹层或 Sheet 必须等待请求结束后才允许关闭。
- 390px 下正文保持单栏，章节导航在任务 Sheet 内横向滚动；所有网格轨道使用 `minmax(0, 1fr)`，textarea 使用 `border-box`，禁止子面板制造隐性横向溢出。
- 完整实现与验收见 [`phase-9-5c3-text-runtime-form-system.md`](./phase-9-5c3-text-runtime-form-system.md)。

## 当前仓库约定的前端结构

- `layout/`：应用壳层和头部控制
- `planning/`：配置态工作台
- `brief/`：Story Brief 与参考资料输入
- `running/`：运行态工作台和执行诊断
- `settings/`：弹窗设置与 Provider 字段组件
- `state/`：应用级 Hook、持久化、自动保存、事件归并
- `services/`：API 和 SSE IO
- `contracts/`：类型合同
- `lib/`：纯格式化和转换辅助函数

## 运行样式边界

`styles.css` 保持显式导入顺序。运行态样式已按原始 cascade 完成责任拆分，历史覆盖仍按下列顺序加载，不得随意调整先后：

- `stage-run-layout.css`：运行工作台根网格
- `stage-run-info-loading.css`：Info 专属加载反馈
- `stage-run-shell.css`：主区、侧栏、Header 和运行状态条
- `stage-run-writing.css`：正文左栏、章节导航和修订轨迹
- `stage-run-artifacts.css`：跨阶段 Artifact 基础表面和编辑控件
- `stage-run-outline-detail.css`：分卷与细纲基础结构
- `stage-run-delivery.css`：Cover 与 Export 基础结构
- `stage-run-artifact-workbench-v4.css`、`stage-run-summary-priority.css`：阶段工作台共享表面和 Summary 优先级覆盖
- `stage-run-detail-*.css`：Detail 施工表、账本、写回、章节蓝图和专用写回弹层
- `stage-run-writing-outline-cards.css`：当前章 Context、摘要同步和 Wiki 写回摘要
- `stage-run-writing-reader.css`：正文稿纸、编辑状态和移动端双栏折叠
- `stage-run-writing-stream.css`：正文流式/可编辑稿纸状态和 Reduced Motion
- `stage-run-writing-phase95c3.css`、`stage-run-writing-phase95c3-responsive.css`：写作/审校/专注视图、紧凑 Rail、移动 Dock 与全屏任务 Sheet
- `stage-run-chapter-revision.css`、`stage-run-chapter-revision-responsive.css`：选区工具条、候选预览、版本 ledger 和窄屏折叠
- `stage-run-cover-quality.css`、`stage-run-export-workbench.css`：Cover 质量与 Export 交付工作台
- `stage-run-info-*.css`：Info 编辑器、人物关系、推荐表单、世界观和确认反馈
- `stage-run-runtime-*.css`：运行侧栏、洞察、知识卡、详情 Sheet/Dialog 和紧凑组件
- `stage-run-transition-loader.css`、`stage-run-liquid-overlays.css`、`stage-run-stage-decision.css`：阶段过渡、结算覆盖和候选决策
- `stage-run-summary-*.css`、`stage-run-outline-matrix.css`：Summary/Outline 工作台、编辑弹层和矩阵覆盖
- `stage-run-export-legacy.css`、`stage-run-stage-artifact-legacy.css`：仍需保留原始位置的历史兼容层
- `stage-run-acceptance-polish.css`：前端验收阶段的稳定性覆盖
- `stage-run-artifact-workbench-v2.css`、`stage-run-artifact-workbench-v3-*.css`、`stage-run-artifact-workbench-v6-*.css`：按原始出现位置保留的 Artifact 工作台历史层
- `stage-run-summary-specialist-*.css`、`stage-run-summary-ia.css`、`stage-run-summary-composition.css`：Summary 专项工作台、关系写回和构图层
- `stage-run-summary-*-polish.css`、`stage-run-summary-structure-rail.css`：Summary 轨道与叙事结构覆盖
- `stage-run-summary-*-modal*.css`、`stage-run-summary-edit-dialog.css`：Summary 编辑弹层和人物关系深化历史层
- `stage-run-outline-workbench-v3.css`、`stage-run-outline-dependency-*.css`、`stage-run-outline-beat-editor.css`、`stage-run-outline-responsive.css`：Outline v3 主工作台、依赖写回、节拍编辑与响应式规则

Phase 1C.1-1C.6 已迁移完最初 13,531 行 `stage-run.css`，旧文件和导入均已删除。76 个运行样式文件按导入顺序重新拼接后仍为 329,198 字节，SHA-256 与原文件完全一致。后续视觉迭代必须在现有责任文件内进行，并继续用生产构建和固定视口截图验证 cascade，不得重新建立巨型聚合样式文件。

## 设计系统边界

- `styles/design-tokens.css`：Dark/Light、模式色、字体、间距、圆角、控件尺寸、壳层尺寸和动效 Token 的唯一入口。
- `styles/foundation.css`：根元素、基础控件和产品壳层结构，不拥有主题色常量。
- 具体表面样式：消费语义 Token，不自行复制主题变量。

旧 `--bg`、`--panel`、`--accent` 等变量是迁移兼容层，不是新组件 API。完整规则和验收矩阵见 `docs/architecture/design-system-foundation.md`。
