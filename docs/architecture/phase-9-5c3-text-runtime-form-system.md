# Phase 9.5C-3：Text 正文运行期表单与编辑闭环

> 状态：已实施并完成浏览器验收
>
> 实施日期：2026-07-26
>
> 范围：Text 结构化正文 Artifact、专业写作桌、局部修订、版本恢复、摘要复检、写回提案与移动端任务 Sheet
>
> 非本批范围：Cover 候选工作台、Export 交付表单、Header/SSE 状态机重构、Provider 接入重构

## 1. 本批目标

本批把正文阶段从“正文稿纸加若干常驻面板”收口为可长期写作和审校的专业工作台，同时保持已经建立的后端安全闭环。

目标不是增加更多 Card 或动画，而是让用户始终能回答四个问题：

1. 当前正在编辑哪一章、哪个正文版本。
2. 当前操作是在修改本地当前稿，还是会正式写入 Memory、Wiki、人物关系、伏笔和 Canon。
3. 摘要、质量复检、写回提案或 Canon 冲突中的哪一项仍阻断定稿。
4. 在桌面、平板和移动端如何快速切换章节任务、写作任务和审校任务。

## 2. Artifact、决策与写回合同

| 合同 | Text 阶段定义 |
| --- | --- |
| 主 Artifact | 顶层结构化 Text Artifact 与 `chapters[]`，不使用拼接字符串作为运行期最终形态 |
| 单章 Artifact | `id/title/generated_title/content/words/status/version/commit_signature/context_packet/summary`，以及质量、修订、版本和写回结构 |
| 用户决策 | 当前章正文是否接受修订；摘要与复检是否同步；结构化写回提案是否接受；完整当前稿是否可以定稿 |
| 当前稿写入 | 正文编辑、摘要编辑、接受修订和恢复历史只更新当前 Text Artifact，并推进本章版本 |
| 正式写回 | Deep 模式仅在完整当前稿通过合同并被人工确认后写入 Memory、Wiki、Story Bible、人物关系、伏笔和 Canon |
| 下游依赖 | 下一章 Context Packet、Cover 文案上下文、Export 正文与来源快照 |

### 2.1 顶层结构保持稳定

正文运行中和运行完成后均使用同一结构对象：

```text
TextArtifact
├── schema_version
├── status
├── target_chapters
├── chapters[]
├── context_packets[]
├── quality_reports[]
├── wiki_writebacks[]
└── chapter_summaries[]
```

`writingArtifactModel.ts` 负责归一化、精确匹配章节 Context、构造人工版本和执行定稿完整度检查。界面不得从任意最新 SSE 事件猜测当前章 Context，也不得把一段正文字符串临时替换成结构对象。

### 2.2 当前稿不等于正式写回

- 用户直接编辑正文，只创建与当前来源绑定的人工当前稿，清空旧提交签名并设置 `summary_dirty=true`。
- 用户编辑摘要，只更新当前稿中的摘要内容；前端不得自行清除 `summary_dirty`。
- 接受修订候选或恢复历史版本会创建新版本，但不会提前更新正式 Memory、Wiki、人物图谱、伏笔账本或 Canon。
- “接受写回提案”只授权 Deep 定稿时执行该提案，不等于此时已经正式写回。
- 只有最终 Text Artifact 通过后端合同并完成阶段确认，才执行正式写回；UI 文案必须继续区分“保存到当前稿”和“定稿后写回”。

## 3. 专业写作桌信息架构

### 3.1 桌面双任务布局

桌面保留正文为最大工作面，以“展开一侧、收起另一侧”的双任务布局替代同时挤压正文的三块等权区域：

| 视图 | 左侧 | 中间 | 右侧 | 适用任务 |
| --- | --- | --- | --- | --- |
| 写作 | 完整章节工作区 | 最大正文稿纸 | 58px 审校 Rail | 切章、读 Context、编辑正文与摘要、查看版本 |
| 审校 | 58px 章节 Rail | 最大正文稿纸 | 完整审校 Inspector | 质量定位、摘要复检、提案与 Canon 冲突决策 |
| 专注 | 隐藏 | 最大正文稿纸 | 隐藏 | 长时间阅读和连续改稿 |

`WritingViewModeControl` 使用可访问的 Segmented Control 表达三个布局状态。视图切换只改变布局，不修改 Artifact、不触发 Provider、不恢复 Run、不重连 SSE，也不执行正式写回。

### 3.2 写作视图

左侧 `WritingChapterWorkspace` 连续组织：

- 章节导航：标题、状态、字数与版本，当前章明确高亮。
- 当前章 Context：只匹配当前章节的 Context Packet。
- 章节摘要：属于当前稿；修改后必须显式同步并复检。
- 修订轨迹和版本入口：历史恢复是前进式新版本，不做本地版本号回退。

正文 `WritingManuscriptEditor` 保持独立稿纸和内部滚动。流式内容使用短句缓冲淡入；用户上滚离开底部后暂停自动跟随，并提供恢复跟随入口。

### 3.3 审校视图

右侧 `WritingReviewInspector` 只保留两个业务 Tab：

- `质量审校`：摘要同步、确定性质量复检、Finding 与可靠 Repair Target 定位。
- `事实写回`：结构化写回提案、接受/拒绝、Canon 冲突选择和签名过期状态。

人物关系与世界观不是第三、第四个常驻 Tab，只作为底部详情入口打开现有运行洞察层。审校内容始终绑定当前章节，不展示与当前章无关的 Finding 或 Proposal。

### 3.4 专注视图

- 专注视图只保留稿纸和明确的退出按钮。
- `Escape` 退出专注并恢复进入专注前的写作或审校视图。
- 进入/退出时使用同一正文实例和按布局保存的视口快照，避免正文内容、光标或滚动位置跳失。
- 不使用全屏渐变、逐字标题、持续 Glow 或额外动画运行时。

## 4. 移动端任务模型

390px 下不压缩桌面三栏，而是采用“正文单栏 + 底部任务 Dock + 全屏 Sheet”：

- 首屏只有紧凑 Context 条、正文稿纸和底部两个入口。
- “章节”打开 `WritingMobileSheet`，承载章节选择、Context、摘要和版本任务。
- “审校”打开独立 Sheet，承载质量和事实写回两个 Tab。
- Sheet 通过 Portal 挂载到应用最外层，使用单一内部滚动所有者，不被工作台或 Header 裁切。
- Sheet Busy 时关闭按钮禁用，Backdrop 点击和 `Escape` 都不能关闭，避免请求进行中丢失反馈上下文。
- 已折叠 `StageFinalizeTray` 高度归零，正文区域延伸到移动 Dock 上方，不为不可见定稿条保留空白。

## 5. 局部修订闭环

### 5.1 UTF-16 选区合同

浏览器 `selectionStart/selectionEnd` 和后端统一使用 UTF-16 code unit：

- 操作固定为 `rewrite/expand/compress/restyle`。
- 普通手工修订选区必须非空且不超过 6000 UTF-16 code units；复合字符边界不合法时拒绝请求。
- `restyle` 必须提供目标风格，其余操作可以直接生成候选。
- 质量定位同样使用 UTF-16 范围；前端先校验章节 ID、版本、Artifact 签名和选区原文，再聚焦正文。
- 点击 Finding 只定位选区，不自动调用 Provider；用户再次确认才生成候选。

### 5.2 候选先预览、后接受

`POST /api/runs/{run_id}/chapter-selection-revisions` 只生成候选，不覆盖正文。候选保存：

- 章节、选区原文、操作和方向。
- 已落盘基线版本与签名。
- 当前人工稿签名。
- 完整替换预览与候选签名。

`POST /api/runs/{run_id}/chapter-selection-revisions/apply` 接受候选前再次验证上述状态，只替换原选区，选区外正文逐字保持。

### 5.3 双签名并发保护

局部修订同时校验“服务端已落盘稿”和“页面当前人工稿”：

- 服务器正文必须仍等于生成候选时的已落盘基线。
- 当前人工稿必须仍等于候选绑定的编辑稿。
- 章节版本、选区原文和候选签名必须一致。
- 旧页面、过期候选、变化选区和重复 request id 都不能覆盖新正文。

接受成功后保存完整上一版本快照，`version += 1`，清空 `commit_signature`，设置 `summary_dirty=true`，并追加结构化修订记录。

## 6. 版本恢复合同

`POST /api/runs/{run_id}/chapter-versions/restore` 执行前进式恢复：

- 当前 v3 恢复历史 v1 时创建 v4，而不是把版本号改回 v1。
- 创建 v4 前保存当前 v3 快照。
- 正文和摘要从同一历史快照恢复，避免正文与摘要跨版本错配。
- 恢复后清空旧提交签名，并重新进入摘要同步/复检门禁。
- 同一 request id 重复提交复用结果，不会再次升版。
- 恢复弹层只有等待服务端成功创建新版本后才关闭；Busy 期间不能切章或关闭弹层。

## 7. 摘要、质量与写回提案

### 7.1 摘要同步和复检

`POST /api/runs/{run_id}/chapters/{chapter_id}/sync-summary` 同时校验：

- 已落盘基线签名。
- 当前人工稿签名。
- 当前章节版本。
- 当前摘要内容。

成功后把摘要绑定到当前正文版本，并使用现有确定性质量引擎生成 `quality_recheck`。复检失败保留当前稿，但继续阻断定稿。

### 7.2 Repair Target

- 每个可靠 Finding 可以附带版本绑定的 `repair_target`；质量引擎生成的定位范围最多 1200 UTF-16 code units。
- `chapter_handoff/structure` 优先定位首个正文段，`foreshadowing` 优先定位末段。
- 模板味或世界观冲突只有在证据可可靠映射时才返回范围。
- 无法可靠定位时只返回方向，不执行模糊正文替换。

### 7.3 写回提案和 Canon 冲突

复检通过后，从当前章的 `wiki_writebacks/character_shift/foreshadow_updates` 生成版本绑定的 `writeback_proposal`，不会直接修改正式系统。

提案状态固定为 `pending/accepted/rejected/blocked/not_required`：

- 有结构化变化时必须显式接受或拒绝。
- 拒绝允许正文与摘要继续定稿，但对应变化不得从其他提取路径旁路写入 Canon。
- 接受只授权最终 Deep 定稿执行。
- 提案签名与章节版本不一致时必须重新同步，不能沿用旧授权。

Canon 事实使用稳定 `id/target/claim_key/fact/status/sources[]`。同一 `target + claim_key` 出现不同事实时创建 `canon_conflict`，保留既有事实，要求用户选择“保留既有”或“采用新事实”；冲突未决不得覆盖 Canon。

## 8. Busy、焦点与视口保护

### 8.1 Busy 锁

以下请求进行中时统一锁定切章和当前任务层退出：

- 修订候选生成。
- 候选接受。
- 历史版本恢复。
- 摘要同步与复检。
- 写回提案或 Canon 冲突决策。

Busy 锁只保护请求上下文，不把整个应用永久禁用。请求成功或失败后必须释放，并在原任务层展示结果。

### 8.2 焦点与视口

- `useWritingViewport` 以 `chapterId + compact/desktop + viewMode` 保存滚动与选区快照。
- 切换章节、视图和移动 Sheet 后恢复对应上下文，不把上一章选区套到下一章。
- 质量定位先关闭移动审校 Sheet，再聚焦正文并恢复合法选区。
- 版本/候选/Sheet 使用已有 Overlay 焦点圈和退出协议；Busy 时暂停 Escape。

### 8.3 纯视图零副作用

浏览器实测执行“写作 -> 审校 -> 专注 -> Escape -> 写作”，捕获网络请求为 `[]`。该链路不得出现：

- `/resume`。
- SSE 或 Provider 请求。
- Artifact 保存或正式写回。
- Run 恢复、候选生成或重复计费。

## 9. 组件与职责映射

| 文件 | 主要职责 |
| --- | --- |
| `WritingStageView.tsx` | 解析来源/当前 Artifact、选择当前章、持有视图状态和跨章视口快照 |
| `WritingWorkbenchContent.tsx` | 组合修订、审校、选区和 Busy 状态；不继续增加布局职责 |
| `WritingWorkbenchLayout.tsx` | 桌面双任务布局、专注布局和移动端 Dock/Sheet 装配 |
| `WritingChapterWorkspace.tsx` | 完整章节工作区组合 |
| `WritingReviewInspector.tsx` | 当前章质量与事实写回两个 Tab |
| `WritingReviewRail.tsx` | 收起态质量/提案摘要和展开入口 |
| `WritingMobileDock.tsx` | 移动端章节与审校两个任务入口 |
| `WritingMobileSheet.tsx` | Portal、焦点圈、Busy 退出保护和单一滚动层 |
| `writingViewMode.ts` | 纯布局状态机、专注返回目标和 Busy 切章规则 |
| `useWritingViewport.ts` | 按章节与布局恢复滚动、光标和选区 |
| `useChapterRevision.ts` | 修订生成/接受/恢复的请求状态与基线维护 |
| `useChapterReview.ts` | 摘要复检与写回提案决策状态 |

`WritingWorkbenchContent.tsx` 已达到重型文件边界，后续新增能力必须拆到现有状态 Hook、纯模型或专用组件中，不能继续堆入该装配文件。

## 10. 样式与动效边界

- `stage-run-writing-phase95c3.css` 归属 `stage-writing`，负责桌面视图、Segmented Control、紧凑 Rail 和专注态。
- `stage-run-writing-phase95c3-responsive.css` 归属 `stage-writing`，负责移动 Dock、全屏 Sheet、平板收敛和折叠定稿区修正。
- 复用已有 `motion` Overlay 变量，不引入 GSAP、Anime.js 或第二套 UI 框架。
- Hover 和 Focus 只改变边框、背景和文字色，不做位移或尺寸变化。
- 正文不使用 BlurText、SplitText、逐字动画或持续发光。
- `prefers-reduced-motion: reduce` 下视图按钮和网格列过渡均为 `0s/none`，移动 Dock 关闭背景模糊。

## 11. 浏览器验收

### 11.1 视口与布局

| 视口 | 结果 |
| --- | --- |
| 1280 x 920 | 页面横向溢出 `0`，写作/审校双任务布局稳定 |
| 1440 x 1000 | 页面横向溢出 `0`，页面本身不滚动，正文稿纸内部滚动 |
| 1728 x 1100 | 页面横向溢出 `0`，正文保持最大工作面 |
| 390 x 844 | 页面横向溢出 `0`；折叠定稿区高度 `0`；主区两行约为 `93px / 593px`；`padding-bottom: 0` |

移动端最终正文已扩展到 Dock 上方，不再保留约 154px 的无业务空白。

### 11.2 状态矩阵

- Light / Dark：桌面和移动端均通过，模式色只用于选中、焦点和关键状态。
- Reduced Motion：视图按钮与网格布局过渡均为 `0s`。
- Busy：切章、关闭按钮、Backdrop 和 Escape 均按请求状态正确锁定。
- 纯视图切换：零网络请求，Artifact 不变。
- Console：最终 `textfinal` 会话为 0 Error、0 Warning。

### 11.3 截图证据

- `output/playwright/phase95c3/after-desktop-writing-1440x1000.png`
- `output/playwright/phase95c3/after-desktop-review-1440x1000.png`
- `output/playwright/phase95c3/after-desktop-writing-light-1440x1000.png`
- `output/playwright/phase95c3/after-mobile-writing-finalize-collapsed-390x844.png`
- `output/playwright/phase95c3/after-mobile-chapter-sheet-390x844.png`
- `output/playwright/phase95c3/after-mobile-review-sheet-390x844.png`

## 12. 最终门禁

本批必须执行：

```bash
cd apps/web
npm test
npm run build
npm run audit:css
cd ../..
.venv/bin/python -m pytest -q
git diff --check
```

退出条件：

- 前端与后端全量测试通过。
- Vite 生产构建通过。
- 两个新增样式文件完成所有权审核并更新 CSS Audit baseline；Keyframe、动画声明和无限动画数量不得增长。
- 最终 `textfinal` 浏览器会话为 0 Error、0 Warning。
- 目标视口无页面级横向溢出。
- Cover 与 Export 不在本批完成声明中。

最终执行结果：

- 前端：68 个测试文件、232 项测试全部通过。
- 后端：207 项通过、1 项跳过；仅有一条 FastAPI TestClient 所依赖 Starlette/httpx 的弃用警告。
- 生产构建：通过，共转换 3530 个模块。
- CSS Audit：通过；137 个导入文件均有所有者，Keyframe 68、动画声明 71、无限动画声明 24，三项均未增长。
- 浏览器：1280 / 1440 / 1728 / 390 页面级横向溢出均为 0，纯视图请求为 `[]`，最终 Console 为 0 Error、0 Warning。
- `git diff --check`：通过。

## 13. 后续阶段入口

下一批进入 Cover / Export 运行期表单和交付闭环。开始前必须分别定义 Cover 资产选择决定、Export 来源快照/Manifest/版本收据，并继续遵守“当前选择不等于正式交付”“UI 动画不触发生成或下载”的边界。
