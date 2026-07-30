# Phase 9.0 基线和决策冻结报告

> 冻结日期：2026-07-24
> 覆盖范围：Planning、Settings、Creation History、Info、Summary、Outline、Detail、Text、Cover、Export
> 关联总方案：`docs/architecture/phase-9-product-shell-and-surface-redesign.md`
> 业务合同：`docs/architecture/stage-artifact-contract.md`
> 状态：Phase 9.0 完成；Phase 9.1 可进入，Phase 8.8 仍独立未完成

## 1. 冻结目的

本报告不是视觉提案，也不修改阶段业务行为。它冻结 Phase 9 大规模 UI 重构前的真实页面状态、Artifact 责任、请求边界、几何布局、滚动所有者、动画债务和基础控件分布，后续每个 Phase 都必须与本基线对照。

必须同时满足以下原则：

1. 先定义阶段 Artifact、用户决策、写回目标和下游依赖，再调整布局。
2. UI 打开、切换、Hover、Focus、Tab、Sheet 和过渡动画不得触发 Provider、`/resume`、SSE 重连、正式写回或重复计费。
3. Phase 8.8 的真实 Provider 全链路验收不能由 Demo、Mock、截图、Prompt-only Cover 或跳过 Cover 代替。
4. 视觉升级不以减少代码量为目标；优先保证功能完整、状态稳定、草稿安全和可恢复性。
5. 不新增 `components/`、`screens/`、`dialogs/` 等并行目录；继续使用 `layout/`、`planning/`、`brief/`、`running/`、`settings/`、`state/`、`services/`、`contracts/`、`lib/`。

## 2. 冻结结论

### 2.1 可保留并精修的基础

- Summary 已形成“完整梗概稿纸 + 结构支撑区”的阶段专属构图。
- Outline 已形成分卷节拍、人物承接、世界揭示和伏笔账本的专业工作台。
- Detail 已形成章节施工表和章节台账，移动端允许施工表内部横向滚动。
- Text 已形成章节 Rail、正文稿纸和审校 Inspector 三栏，具备长时间写作工作台基础。
- Cover 已能展示真实可解码图片资产、候选状态和正式选择。
- Export 已能展示不可变版本、冻结选择、校验结果、文件清单和历史关联。
- History 已具备服务端运行、快照恢复入口和导出历史版本关联；桌面双栏、移动单滚动区的基础正确。

### 2.2 必须优先修复的产品结构

- Planning 同时在 Header、顶部阶段条和中央 Canvas 重复表达进度。
- Settings 的四个 Tab 按技术名词切分，Provider、默认模型和阶段覆盖存在交叉编辑入口。
- 首次配置不是连续流程；再次进入又缺少清晰的单页设置摘要。
- Header 在移动端占用 `184px`，Text 首屏又叠加状态条和章节区，正文到达成本偏高。
- Info 仍有较多同规格框线和子表面，内容优先级弱于组件边界。
- 原生 Select、Checkbox、Radix Switch、自制 Tooltip 和多类 Loader 并存，状态与几何不统一。
- 历史 Run 打开后存在无真实保存请求却持续显示“正在保存”的错误反馈。

### 2.3 冻结的实施顺序

1. Phase 9.1 先做配置语义、字段唯一归属、Guided Setup 和 Settings Overview。
2. Phase 9.2 再迁移统一 Option 系统，避免把重复字段包装成更漂亮的重复控件。
3. Phase 9.3-9.4 再收敛 Header、隐式导航、唯一阶段进度和模式切换遮罩。
4. Phase 9.5 以后按表单、页面壳层、阶段工作台和交付恢复链路逐步精修。

## 3. 证据来源与采样规则

### 3.1 视口

- 桌面：`1440 x 1000`
- 移动：`390 x 844`
- 页面级横向溢出：本轮全部采样页面均为 `0`
- 浏览器控制台：纠正后的七阶段桌面/移动页面均为 `0 errors / 0 warnings`

### 3.2 Run 来源映射

已完成的真实 Provider Run 在 History 中按产品规则只读，不能直接作为活动运行恢复。为验证真实 History API 和“打开运行”链路，曾创建五个只用于采样的暂停镜像；原 Run 未修改，采样结束后镜像已移出 `runtime/novel_workflow/runs/`，历史 API 中不再出现 `phase90-baseline-*`。

| 页面 | 截图使用的 Run | 原始数据来源 | 说明 |
| --- | --- | --- | --- |
| Info | `phase90-baseline-info-20260723` | `manual-real-single-info-compact-1600` | 真实 Info Artifact 的暂停镜像 |
| Summary | `phase90-baseline-summary-20260723` | `manual-real-info-summary-retry` | 真实 Info + Summary Artifact 的暂停镜像 |
| Outline | `phase90-baseline-outline-20260723` | `manual-real-info-summary-outline-structured` | 真实 Outline Artifact 的暂停镜像 |
| Detail | `phase90-baseline-detail-20260723` | `manual-real-info-summary-outline-detail-structured` | 真实 3 章 Detail Artifact 的暂停镜像 |
| Text | `phase90-baseline-text-20260723` | `backend-run-text-retry-1782664048742` | 真实 3 章正文与完整历史 Artifact 的暂停镜像 |
| Cover | `phase86-cover-acceptance-a1` | 同名验收 Run | 3 个候选、3 个可解码图片元素，无 Fixture 提示 |
| Export | `phase86b-export-acceptance` | 同名验收 Run | 不可变版本、格式、校验和交付文件关联 |

临时镜像隔离位置：`/tmp/phase90-baseline-mirrors-20260723/`。该位置不是产品运行目录，也不作为长期测试资产。

### 3.3 截图索引

截图根目录：`output/playwright/phase90-baseline/`

| 表面 | 桌面 | 移动 |
| --- | --- | --- |
| Planning | `planning-1440x1000.png` | `planning-390x844.png` |
| Settings / 全局模型 | `settings-global-1440x1000.png` | `settings-global-390x844.png` |
| Settings / 模型接口 | `settings-providers-1440x1000.png` | `settings-providers-390x844.png` |
| Creation History | `history-1440x1000.png` | `history-390x844.png` |
| Info | `info-1440x1000.png` | `info-390x844.png` |
| Summary | `summary-1440x1000.png` | `summary-390x844.png` |
| Outline | `outline-1440x1000.png` | `outline-390x844.png` |
| Detail | `detail-1440x1000.png` | `detail-390x844.png` |
| Text | `text-1440x1000.png` | `text-390x844.png` |
| Cover | `cover-1440x1000.png` | `cover-390x844.png` |
| Export | `export-1440x1000.png` | `export-390x844.png` |

## 4. 阶段 Artifact 合同基线

以下表格只记录当前产品责任，不在 Phase 9 中改变字段合同。

| 表面 | 主 Artifact | 当前用户决策 | 正式写回目标 | 下一依赖 |
| --- | --- | --- | --- | --- |
| Planning | Workflow、Brief、Knowledge、Provider Readiness、质量策略 | 是否具备启动条件；是否调整阶段例外 | Workflow、Provider 引用、知识资料选择、阶段参数 | Info 输入与 Run 创建 |
| Info | 立项设定、候选书名、简介、人物、关系、世界观、下游约束 | 选择/编辑推荐结果并确认立项 | `info_recommend`、Story Brief、人物和世界事实 | Summary 的故事基线 |
| Summary | 完整梗概、结构幕、关键转折、人物弧线 | 确认全书叙事承诺和结局方向 | `summary` Artifact | Outline 的分卷节拍 |
| Outline | 分卷目标、节拍、人物承接、世界揭示、伏笔计划 | 确认卷级推进和承接 | `outline` Artifact | Detail 的章节拆解 |
| Detail | 章节目标、冲突、事实揭示、伏笔、人物变化、章末钩子 | 确认每章施工图和上下游连续性 | `detail_outline` Artifact 及专用写回 | Text 的章节生成上下文 |
| Text | 章节正文、摘要、版本、质量 Finding、事实写回提案 | 编辑/审校/接受修订并确认章节 | Chapter Artifact、版本、Canon/Wiki 写回 | Cover 与 Export 的正式稿 |
| Cover | 封面 Brief、候选元数据、图片资产、正式候选 | 选择正式封面或重试失败候选 | `cover` Artifact、正式候选 ID、资产引用 | Export 交付门禁 |
| Export | 冻结章节/元数据/封面选择、Receipt、文件清单和校验 | 选择交付范围并生成不可变版本 | Run Export Store 与下载 Receipt | History、重下和外部交付 |

禁止在 Phase 9 页面中加入不影响上述用户决策的装饰性面板，也禁止把内部 JSON、Output Key、Provider ID 或状态机字段直接作为普通内容展示。

## 5. 几何与滚动基线

### 5.1 Header

| 视口 | Header | Brand | 中央状态区 | 右侧动作区 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| `1440 x 1000` | `1440 x 78` | `210 x 42` | `640 x 52` | `486 x 40` | 桌面高度可接受，但中央重复进度占用高价值位置 |
| `390 x 844` | `390 x 184` | `186 x 42` | `366 x 50` | `display: contents` | 移动首屏占用过高，必须在 Phase 9.3 收敛 |

Header 在两个视口均存在 `scrollHeight` 略高于 `clientHeight` 的装饰/动作溢出，但页面横向溢出为 `0`。Phase 9.3 验收必须同时检查可见边界、Focus Ring 和 Tooltip，不只看页面级 Overflow。

### 5.2 Planning

桌面 `1440 x 1000`：

- Workbench：`1440 x 922`，页面自身不滚动。
- 中央 Canvas 壳：`999 x 768`。
- 顶部重复阶段条：`997 x 55`。
- React Flow 可视区：`997 x 644`。
- Knowledge Rail：`999 x 118`。
- Inspector：`389 x 898`，`overflow-y: auto`，`scrollHeight 1208 / clientHeight 896`。
- 主画布与 Inspector 之间实际间距约 `12px`。
- Planning ambience 的内容尺寸大于容器，但由 `overflow: hidden` 裁切；它不能成为后续“内容存在但不可达”的掩盖手段。

移动 `390 x 844`：

- Header：`184px`；Workbench：`390 x 660`。
- Workbench 为主滚动所有者：`overflow-y: auto`，`scrollHeight 688 / clientHeight 660`。
- Canvas：`362 x 430`；阶段条：`360 x 55`；React Flow：`360 x 306`。
- React Flow 内容宽 `408px`，由画布自身隐藏/平移，不造成页面横向溢出。
- Knowledge Rail：`362 x 222`。
- Inspector 在移动端 `display: none`，阶段编辑应通过明确的 Sheet/流程入口承接，不能仅隐藏。

### 5.3 Settings

桌面 `1440 x 1000`：

- Dialog：`1040 x 560`，位置 `x=200 / y=220`。
- Header：`1006 x 73`。
- Tabs 区：`1006 x 385`。
- 左侧 Tab List：`132 x 385`；右侧内容：`874 x 385`。
- 当前 Tab 内容声明 `overflow: auto`；采样状态下内容高等于容器高。

移动 `390 x 844`：

- Dialog：`362 x 744`，位置 `x=14 / y=50`。
- Header：`332 x 90`。
- 横向 Tab List：`332 x 45`；内容：`332 x 569`。
- 四个 Tab 在窄屏形成连续切换负担，进一步证明问题是信息架构交叉，不只是样式不统一。

Phase 9.1 将四 Tab 改为首次 Guided Setup 与后续 Settings Overview；不保留一套隐藏 Tab 再叠加一套新流程。

### 5.4 Creation History

桌面 `1440 x 1000`：

- Drawer：`1120 x 1000`，从 `x=320` 开始，占视口约 `77.8%`。
- Body：`1083 x 883`。
- Run List：`331 x 883`，唯一列表滚动区，`scrollHeight 2992 / clientHeight 883`。
- Detail：`738 x 883`；当前采样内容不需要第二个纵向滚动区。

移动 `390 x 844`：

- Drawer：全屏 `390 x 844`。
- Body：`361 x 739`，唯一滚动所有者，`scrollHeight 4247 / clientHeight 739`。
- List 与 Detail 纵向堆叠；List 实际高 `3835px`，Detail 高 `384px`。
- 关闭按钮固定在顶部，交付版本与动作可滚动到达。

### 5.5 Summary：稿纸 + 阶段支撑 + 外部 Rail

桌面 `1440 x 1000`：

- Stage Main：`1044 x 898`；外部 Stage Rail：`360 x 898`。
- Summary Board：`1044 x 740`。
- 完整梗概稿纸：`580 x 661`。
- 结构支撑区：`452 x 661`，其中结构幕 `255px`、关键转折 `185px`，人物关系区 `452 x 158`。
- 外部 Stage Rail 使用 `overflow: auto`；页面级无横向溢出。

移动 `390 x 844`：

- Stage Workbench 是唯一页面内滚动所有者：`scrollHeight 3858 / clientHeight 660`。
- Stage Main、Summary Board、稿纸、结构支撑和外部 Rail 依次纵向堆叠，统一宽 `366px`。
- 稿纸高 `1206px`，结构支撑高 `1490px`，外部 Rail 高 `769px`。
- 移动端没有压缩并排，但总行程很长；Phase 9.7 应按用户决策折叠次要支撑，而不是删除 Artifact。

### 5.6 Detail：施工表 + 外部 Rail

桌面 `1440 x 1000`：

- Stage Main：`1044 x 898`；外部 Stage Rail：`360 x 898`。
- Detail Board：`1044 x 740`。
- 施工表壳：`1044 x 531`；当前 3 章表格无需横向溢出。
- Chapter Ledger：`1044 x 123`。

移动 `390 x 844`：

- Stage Workbench 为纵向滚动所有者：`scrollHeight 1396 / clientHeight 660`。
- Detail Board 自身还存在 `overflow-y: auto`：`scrollHeight 1016 / clientHeight 482`，形成嵌套滚动风险。
- 施工表可视宽 `364px`，内容宽约 `820-860px`，由 `.detail-construction-scroll` 独立横向滚动。
- Chapter Ledger 与外部 Rail 在主表后纵向堆叠，宽 `366px`。
- Phase 9.8 必须保留施工表横向滚动，但应消除不必要的纵向双滚动。

### 5.7 Text：内部三栏专业写作台

桌面 `1440 x 1000`：

- Text 不使用外部 Stage Rail，Stage Main 直接扩展到 `1416 x 898`。
- Writing Layout：`1416 x 666`。
- 左侧章节/上下文 Rail：`236 x 664`。
- 中央正文 Editor：`848 x 664`；稿纸纵向滚动区 `848 x 582`，`scrollHeight 2433 / clientHeight 582`。
- 右侧审校 Inspector：`330 x 664`。
- 该结构应保留并精修，不回退为通用 Card 列表。

移动 `390 x 844`：

- Stage Main：`366 x 636`。
- Writing Workbench 为主滚动区：`scrollHeight 1522 / clientHeight 379`。
- 章节导航、Editor、上下文、审校依次堆叠；统一宽约 `364px`。
- 正文稿纸内部仍有独立滚动：`scrollHeight 3074 / clientHeight 476`。
- 首屏在 Header、阶段标题、上下文状态和章节导航后才到正文；Phase 9.8 应通过紧凑 Header、章节 Sidebar/Sheet 和阅读焦点模式降低到达成本。

### 5.8 滚动所有权冻结

| 表面 | 桌面滚动所有者 | 移动滚动所有者 | Phase 9 要求 |
| --- | --- | --- | --- |
| Planning | Inspector；Canvas 自身平移缩放 | Workbench | Inspector 改 Sheet 后保持单主滚动 |
| Settings | 当前 Tab Content | 全屏内容区 | Overview/Sheet 各自单滚动，不嵌套 Tab 滚动 |
| History | Run List | Drawer Body | 保持现有正确策略 |
| Summary | 稿纸/外部 Rail 的局部内容 | Stage Workbench | 折叠次要支撑，避免多个长纵向区竞争 |
| Detail | 施工内容/外部 Rail | Stage Workbench + 施工表横向 | 保留横向施工表，移除纵向双滚动 |
| Text | 稿纸 + 局部 Inspector | Writing Workbench + 稿纸 | 专注模式明确选择页面滚动或稿纸滚动 |
| Cover | 候选/预览/Inspector 的阶段内滚动 | 单阶段滚动，Rail -> Preview -> Inspector | 保持资产完整可达 |
| Export | 选择/Receipt/校验阶段内滚动 | 单阶段滚动 | 生成、重下和校验必须完整可达 |

## 6. 请求和副作用基线

代表路径：在独立稳定浏览器会话中，从 Creation History 打开历史 Summary Run，等待页面稳定并观察网络。

出现的请求：

- `GET /api/runs/history`
- `GET /api/workflows/default`
- `GET /api/knowledge/documents`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/exports`

路由生命周期中出现一次被取消的 History GET，随后只读 GET 成功。未出现：

- Provider 文本或图片生成请求
- 新 Run 创建
- `/resume`
- SSE 连接或重连
- Artifact 审批/正式写回
- Export 生成
- Snapshot Restore
- Workflow POST/PUT 保存

因此 Phase 9 的纯 UI 验收以“请求类型不增加”为门槛，而不是只看请求总数。初始化的只读 GET 可以存在；Provider、运行命令和写请求必须为 `0`。

后续 DOM 几何采样使用了另一持久化浏览器会话，该会话保留质量模式偏好并触发了现有 Workflow Autosave `POST /api/workflows`，因此不纳入上述纯历史查看请求基线。它没有触发 Provider、`/resume`、SSE、Artifact 写回、Export 或 Restore，但暴露了验收环境隔离要求：Phase 9 后续网络验收必须使用独立 Session，采样前记录 LocalStorage 与 Workflow 哈希，采样后恢复并复核，不能把偏好同步和纯查看混为同一条证据。

## 7. 动画与反馈基线

CSS 审计冻结值：

| 指标 | 当前值 |
| --- | ---: |
| 导入 CSS 文件 | 127 |
| CSS 字节 | 663,213 |
| 源码行 | 28,165 |
| Rules | 3,834 |
| Selectors | 4,881 |
| Unique Selectors | 3,409 |
| 跨文件重复 Selectors | 543 |
| 重复出现次数 | 1,635 |
| Animation 声明 | 71 |
| Infinite Animation 声明 | 26 |
| Keyframes | 68 |
| 重复 Keyframe 名称 | 1 |
| Reduced Motion Media | 13 |
| 全局 Reduced Motion 兜底 | 2 |

判定：

- Phase 8.7 已清理默认页面无业务意义的空闲无限动画；真实 Busy、保存、同步、生成、解码和下载仍可使用循环反馈。
- 当前模式切换只有短时 Notice，不具备用户要求的沉浸式全屏模式过渡；Phase 9.4 将用现有 `motion` 实现 480-620ms 遮罩。
- Panel、Dialog、Tab 和路由过渡统一使用 100-220ms 的 Opacity + 3-8px 位移；默认不叠加 Blur。
- 不引入 GSAP、Anime.js、Tailwind 或大型 UI Kit。现有 `motion` 已足够承担状态过渡，避免多动画运行时和第二套样式架构。
- React Bits、Aceternity、Uiverse 只作为构图和动效参考；必须重写为现有 Token、语义和 Reduced Motion 合同，不能原样复制霓虹、持续 Glow、大 Spinner 或全局 Button 选择器。

## 8. 控件迁移清单

### 8.1 Native Select

当前共有 `16` 个 `<select>`，分布在 `11` 个文件：

- `brief/InfoBriefEditor.tsx`
- `planning/StageFallbackTargetsEditor.tsx`
- `planning/StageInputField.tsx`
- `planning/StageVariantCompareSection.tsx`
- `running/ChapterBlueprintDialog.tsx`
- `running/DetailWritebackFields.tsx`
- `running/OutlineForeshadowLedgerDialog.tsx`
- `settings/ProviderCreateControl.tsx`
- `settings/ProviderTemplateSelect.tsx`
- `settings/SettingsDialog.tsx`
- `settings/fields/ModelOptionInput.tsx`

迁移规则：

1. Provider、模型、Fallback 等长列表进入 Phase 9.2 `OptionField`，支持搜索、分组、状态、Portal Collision、IME 和 390px Sheet。
2. 题材、篇幅、状态等短枚举可保留原生 Select 或使用 Radix Select，但必须统一高度、Label、Error 和 Focus。
3. 不能机械替换；先完成 Phase 9.1 字段归属，避免重复入口同时迁移。
4. `@radix-ui/react-select` 已安装但当前无实际 import，不能把“依赖存在”记作迁移完成。

### 8.2 Checkbox

当前共有 `11` 个原生 Checkbox，分布在 `6` 个文件：

- `brief/ReferenceResearchPanel.tsx`
- `planning/StageFallbackTargetsEditor.tsx`
- `planning/StageInputField.tsx`
- `planning/StageInspector.tsx`
- `planning/StageVariantCompareSection.tsx`
- `settings/SettingsDialog.tsx`

迁移规则：

- 多选集合、记忆读写、质量门禁继续使用 Checkbox。
- 单一即时启停改为 Switch。
- Settings 中三个 `checked readOnly` 的“运行策略”不是用户输入，Phase 9.1 改为自动保护状态摘要，不伪装成 Checkbox。
- Uiverse 霓虹 Checkbox 只提取勾选路径和短时反馈，不保留持续发光、浮动光点和大字号 Label。

### 8.3 Switch

- 当前仅 `settings/ProviderEditor.tsx` 使用 1 个 Radix `Switch.Root`，语义为 Provider 启用/停用。
- Theme 仍是 Icon Button，不是 Switch。
- Phase 9.3 将 Theme 变为紧凑日夜 Switch；Phase 9.5 统一控制类 Switch。
- Switch 必须保留原生/ Radix 语义、键盘操作、Disabled、Focus、读屏名称和模式色 Token；不复制 Uiverse 中无业务含义的频谱循环动画。

### 8.4 Tooltip

- 当前 `ControlTooltip` 为自制 CSS Tooltip，共 4 个使用点：主题、重置、历史、设置。
- `@radix-ui/react-tooltip` 已安装但当前未使用。
- Phase 9.3 在 Dock 内统一 Tooltip；触屏必须有可见名称或等价长按/辅助说明，不能让 Hover 成为唯一入口。
- Tooltip 只解释图标命令，不承载关键错误、表单帮助或必须阅读的流程说明。

### 8.5 Loading / Busy

当前 `LoaderCircle` 分布在 `17` 个文件，共 `22` 个直接渲染点；`spin` 类使用约 `25` 次；`aria-busy` 使用 `16` 次。

已有类型：

- Header 自动保存状态。
- Creation Action Dock 的运行/继续命令。
- History、Export 版本同步和下载。
- Info 全屏阶段生成遮罩。
- Draft Regeneration 提交遮罩。
- Cover 候选生成、图片解码和失败重试。
- Text 复检、修订和事实写回。
- 通用 Stage Artifact Loading/Error/Empty 状态。

迁移规则：

1. 页面/阶段 Loading 使用 Mode Spinner + 真实步骤文本。
2. 按钮 Busy 使用 12-16px Spinner，不改变按钮宽度。
3. 内容 Streaming 只高亮当前段/行，已完成内容静止。
4. 图片解码与 Provider 生成必须分开表述。
5. `AgentProcessLoader.tsx` 当前没有产品消费者，Phase 9.5 先判断是否并入真实阶段 Loader，不能为了展示动效强行接入。
6. 所有循环动画必须由真实 `aria-busy`、生成、同步或保存状态驱动；Idle、ReadOnly、Invalid/Disabled 不得旋转。

## 9. Phase 8.8 独立状态冻结

Phase 8.8 当前仍未完成。

已完成：

- 多 Provider 模板目录。
- 模型发现。
- Provider 生命周期。
- 显式 Fallback Targets。
- 文本/图片独立预算记账。
- Provider 错误合同。
- 零成本 Readiness 检查。

阻塞：

- 真实文本和图片 Provider 调用受账户余额阻断。
- 已记录的最小真实探针返回 `402 / INSUFFICIENT_BALANCE`。
- 账户/余额未变化前不重复调用，避免无意义请求和误判。
- 不允许使用 Mock 成功、跳过 Cover、只生成 Prompt 或本地占位图宣称真实全链路通过。

最近冻结的自动化基线：

- Backend：`206 passed / 1 skipped / 1 warning`。
- Frontend：`59` 个测试文件、`201` 个测试通过。
- Production Build：通过，`3299 modules transformed`。
- CSS Audit：通过。

Phase 9 可以继续做无副作用 UI 重构，但 Phase 9.10 的真实 Provider 路径只能在账户条件恢复后补齐。

## 10. 已知缺陷和风险

### P1：历史 Run 打开后错误显示持续保存

现象：

- 从 History 打开历史 Run 后，Header 保存状态持续为 `save-state saving`。
- `saveShimmer` 和 Spinner `spin` 至少持续 5 秒，未自行结束。
- 同期网络只有只读 GET，没有 Workflow 保存 POST/PUT。

判定：这是错误的 Busy 反馈，不是慢保存。它会让用户误以为历史查看正在修改配置，也违反“循环动画必须由真实命令驱动”的合同。

处理阶段：Phase 9.1。修复时必须区分：历史 Hydration、Workflow Autosave、Provider/Run 命令和 ReadOnly 状态；不能只用定时器隐藏。

### P1：Settings 字段所有权交叉

同一 Provider/模型信息在“全局模型”“模型接口”“阶段覆盖”和 Stage Inspector 重复出现。任何视觉替换前必须先建立唯一编辑入口，否则会放大认知和状态同步风险。

处理阶段：Phase 9.1。

### P1：移动端首屏内容到达成本

Header `184px`，Text 首屏在正文前还有 Stage Head、Context Bar、Chapter Nav；Summary 与 Detail 的支撑内容总行程较长。

处理阶段：Phase 9.3、9.7、9.8。

### P2：Detail 移动纵向嵌套滚动

Stage Workbench 和 Detail Board 同时纵向滚动，施工表另有必要的横向滚动。后续应保留横向施工表，收敛纵向滚动所有者。

处理阶段：Phase 9.8。

### P2：控件基础不统一

Native Select、Radix Switch、自制 Tooltip、多种 Spinner 和只读 Checkbox 并存；`@radix-ui/react-select`、`@radix-ui/react-tooltip` 已安装但未接入。

处理阶段：Phase 9.2、9.3、9.5。

### P2：CSS 多代覆盖债务

127 个 CSS 文件、543 个跨文件重复 Selector 和多代 `stage-run-*` 样式意味着任何“大范围全局选择器美化”都可能产生回归。后续每个 Phase 只能在明确所有权文件内修改，并保持 CSS Audit 不恶化。

## 11. Phase 9.1 准入条件

以下条件已满足：

- [x] 10 类表面桌面/移动截图齐全；Settings 额外覆盖 2 个代表 Tab。
- [x] 七阶段截图使用真实 Artifact；Cover 使用可解码资产；Export 使用真实版本/校验数据。
- [x] Planning、Settings、History、Summary、Detail、Text 的精确几何与滚动所有者已记录。
- [x] 历史查看请求基线已记录，纯 UI 路径没有 Provider、`/resume`、SSE、恢复或写回。
- [x] Select、Checkbox、Switch、Tooltip、Loading 迁移清单已建立。
- [x] CSS Audit、Frontend Test、Build 通过。
- [x] Phase 8.8 未完成状态和余额阻塞已独立冻结。
- [x] 临时基线镜像已移出产品运行目录，原 Run 未修改。

Phase 9.1 允许修改的范围：

- 配置术语和字段所有权文档/合同。
- `buildSetupSteps` 纯派生逻辑与测试。
- `useSetupFlow` 的纯 UI 导航状态。
- `GuidedSetupWorkbench` 五步壳层。
- `SettingsOverview` 单页摘要壳层。
- Provider Manager 的局部入口编排。
- 历史 Hydration 与 Autosave 状态区分缺陷。

Phase 9.1 禁止顺带修改：

- Stage Artifact Schema。
- Provider 请求、预算、Fallback、模型发现或 Secret 生命周期。
- SSE、Run 创建、Resume、Pause、Snapshot Restore。
- Chapter、Cover、Export 正式写回。
- Route-per-stage 业务语义。
- Phase 9.2 的长列表 Combobox 完整实现。
- Phase 9.3 之后的 Navigation Rail、Dock、Header 和沉浸模式遮罩。

## 12. Phase 9.1 验收门槛

1. 每个配置字段只有一个主编辑入口，其他位置只读摘要或跳转。
2. 首次用户按“故事起点 -> 创作依据 -> AI 服务 -> 质量方式 -> 确认启动”完成五步配置。
3. 再次进入直接显示 Settings Overview，不强迫重复走流程。
4. 中途退出、刷新、返回前一步、可选步骤跳过和前一步失效均不丢字段值。
5. 不新增 `setupCompleted` 伪真值；完成度由 Workflow、Knowledge 和 Provider Readiness 派生。
6. 删除四 Tab 后所有原能力仍可达：Provider 创建/编辑/删除、Secret Dirty Guard、连接检查、模型同步、默认模型、阶段例外、自动保护状态。
7. 打开/切换 Guided Setup 和 Settings Section 时 Provider 请求、`/resume`、SSE、正式写回均为 `0`。
8. 历史 Run 打开后没有无请求的持续“正在保存”反馈。
9. Demo/Mock 在真实 Provider 不可用时继续工作，但明确标识，不能冒充真实验收。
10. `320 / 390 / 768 / 1024 / 1440`、Dark/Light、Keyboard、Reduced Motion 和 200% Zoom 通过。
11. Frontend Test、Build、CSS Audit、相关 Backend Test 和 `git diff --check` 通过。
12. 每个页面人工评审回答：首屏最大内容是否为当前任务、是否存在重复编辑入口、每个支撑模块是否改变用户决策、错误是否说明内容是否保留和下一步动作。

## 13. 冻结后的第一实施切片

Phase 9.1 不应一次重写整个 Settings。建议按以下切片推进：

1. 建立字段唯一归属矩阵和普通用户术语映射，先由测试和文档冻结。
2. 提取只读的 Setup Step 派生函数，使用现有 Workflow、Knowledge 和 Provider Readiness 输入。
3. 实现 Guided Setup/Overview 壳层，只组合现有业务 Section，不复制状态和保存命令。
4. 把 Provider 管理收敛为 AI 服务局部 Sheet，把阶段 Provider/模型改名为“阶段例外”并只保留在 Stage Inspector。
5. 把只读运行策略改为自动保护状态摘要。
6. 修复历史 Hydration 导致的假保存反馈。
7. 完成桌面/移动、网络副作用、Dirty Guard、焦点和回归测试后，才进入 Phase 9.2 Option 系统。

Phase 9.0 至此冻结。后续如基线发生变化，必须在对应 Phase 验收记录中说明变化原因、用户收益、业务语义是否改变，以及与本报告的差异，不能直接覆盖本报告中的原始数值。
