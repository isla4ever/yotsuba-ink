# Phase 9.5B：Settings、Provider 与阶段配置表单收口

> 状态：已完成并通过全量门禁验收
>
> 日期：2026-07-24
>
> 范围：后续进入的 Settings Overview、Provider Manager、Planning Stage Config Sheet 与 StageInspector。运行期章节蓝图、三类写回、Cover 和 Export 表单留给 Phase 9.5C，不在本批宣称完成。

## 1. 本批目标

首次 Guided Setup 已在 Phase 9.5A 建立“流程式配置 + 语义栅格”。本批解决用户再次进入项目后的三个问题：

1. Settings 只承担状态总览与定位，不重新展开一套交叉配置 Tab。
2. Provider 配置按“默认服务 -> 新增服务 -> 单个服务编辑 -> 保存与验证”顺序完成，不让字段宽度和按钮主次随内容漂移。
3. StageInspector 保留阶段参数和阶段例外的唯一写回位置，但统一输入几何、移动重排和标签关联。

本批不是视觉换皮。Provider 生命周期、API Key 草稿保护、模型发现、连接检查、自动保存、阶段继承和删除确认均保持原语义。

## 2. 产品决策

### Settings Overview

- 每个设置域只显示标题、两行以内的当前摘要和一个明确动作。
- 状态图标负责快速扫描；警告、就绪与只读保护不依赖颜色单独表达。
- `高级阶段例外` 只显示例外数量并提供定位/恢复默认，不在 Settings 复制七阶段表单。
- `自动保护` 继续是只读状态，不伪装成可点击开关。
- 创建模式仍可在 Overview 内局部展开；AI 服务进入专用 Provider Sheet。

### Provider Manager

- 顶部两列只决定全局文本和封面默认服务。
- 新增服务使用可搜索厂商模板和一个明确的“添加接口”动作。
- 每个 Provider 默认显示名称、类型、默认模型、密钥状态和启用状态；详细连接字段按需展开。
- 详细编辑按以下顺序排列：厂商模板、名称/类型、Base URL/环境变量、默认模型/API Key、保存、验证。
- “保存连接”“保存密钥”“检查连接”“同步模型”仍是四个独立命令；界面只做分组，不合并网络请求。
- API Key 草稿存在时关闭 Sheet 仍进入原有未保存确认；前端不持久化明文。

### Stage Config

- 普通短字段桌面等宽双列；Textarea 和 Tags 整行；520px 以下统一单列。
- Info Brief 在 Guided Setup 和 Stage Config 两个入口使用同一移动单列规则，不再出现一个入口单列、另一个入口双列。
- “阶段例外与高级规则”继续默认折叠；全局默认服务仍是主路径。
- Checkbox、质量阈值、故障转移和模型字段继续使用既有业务状态，不新增装饰性状态。

## 3. 实现明细

### 3.1 Settings 状态行

`SettingsOverview` 为每行建立稳定的 `aria-labelledby`，模式编辑动作使用 `aria-expanded` 表达展开状态。视觉上使用分隔行和左侧状态槽，不把每项改造成独立浮动 Card。

桌面动作宽度稳定；移动端动作移到摘要下方，长摘要允许换行，避免在窄屏截断关键信息。

### 3.2 Provider Sheet 网格

Provider Sheet 使用命名区域：

- `head`
- `notice`
- `defaults`
- `create`
- `list`
- `foot`

同步失败提示即使出现，也不会把列表或底部动作挤进隐式 Grid 行。Provider 列表设置 `align-content: start`，折叠项按内容高度排列，不拉伸填满空白。

移动端改为 `head / body / foot` 三段：默认服务、新增服务和 Provider 列表进入同一中间滚动区；Header 与完成栏稳定，Safe Area 由底部栏承担。

### 3.3 Provider 字段与命令

- 连接字段使用等宽双列，厂商模板整行展示；620px 以下回落单列。
- 模型选择与自定义模型桌面等宽，移动端单列。
- API Key 使用带左侧模式色的安全信息带，不使用持续 Glow。
- Provider 命令分为“保存”和“验证”两组，主按钮由显式 class 决定，不再依赖 `last-child`。
- Busy 时仍由 `providerBusy` 统一禁用；动态消息使用 `aria-live="polite"`，Error 使用 Alert 语义。
- 空 Provider 列表提供可执行空状态，直接指向上方厂商模板。

### 3.4 OptionField 可访问关联

OptionField 的状态/错误消息获得稳定 ID，Trigger 使用 `aria-describedby` 关联消息。Provider Dialog 的 Outside/Escape 保护同时识别可搜索 Combobox 与短列表 Select 的 Popup，避免选项弹层被误判为外部交互。

短列表继续使用锚定 Select；长列表继续使用可搜索 Combobox。移动端可搜索列表保持底部 Sheet 形态，本批没有引入第二套 Option 实现。

### 3.5 StageInputField 结构

原先布尔字段存在外层 Label 包含内层 Label 的无效结构。本批改为：

- 字段容器使用 `div`。
- 可见 Label 通过 `htmlFor` 指向真实控件。
- Help 使用 `aria-describedby`。
- 必填使用原生 `required` 或 `aria-required`。
- Boolean 使用一个真实关联的 Checkbox Label。

Planning 常驻 Inspector、Planning Sheet 和 Cockpit Drawer 分别使用 `planning-inspector`、`planning-sheet`、`cockpit-drawer` 前缀。桌面同时渲染常驻 Inspector 与 Sheet 时不再产生重复 DOM ID 或错误标签关联。

## 4. 状态矩阵

| 状态 | 可见表达 | 保留行为 |
| --- | --- | --- |
| Default | Provider 摘要与折叠编辑入口 | 不触发 Provider 请求 |
| Empty | “还没有 AI 服务”与添加指引 | 不创建隐式 Provider |
| Loading | 既有可用性检查状态 | 草稿与 Workflow 不清空 |
| Busy | Provider `aria-busy`、按钮禁用、操作图标 | 串行防重保持不变 |
| Saving | 就近状态消息 | 仍分别保存 Profile/Secret |
| Testing | 检查连接或鉴权状态 | 不等价于生成测试 |
| Discovering | 同步模型状态 | 不触发文本/图片生成 |
| Error | Alert + 用户内容保留说明 | 不自动覆盖现有配置 |
| Secret Draft | “密钥尚未保存” | 关闭时进入草稿保护 |
| Delete Pending | 行内危险确认 | 删除阻塞与引用检查不变 |
| ReadOnly | 类型、自动保护等只读内容 | 不伪装成可编辑控件 |

## 5. 不变合同

- `WorkflowDefinition.provider_profiles`、Provider kind、默认模型、模型目录和阶段例外字段不变。
- `useProviderOperations` 的保存、密钥、测试、发现和删除调用顺序不变。
- `useUnsavedDraftGuard`、Secret 草稿清理和关闭后 Readiness Refresh 不变。
- `StageInputField` 仍通过 `updateStageInputDefault` 写回原字段 key；只改变 DOM 结构与布局。
- `StageModelSection`、`StageVariantCompareSection`、Memory Policy、Quality Policy 和自动保存不变。
- 不新增 UI/动效依赖，不新增 `components/`、`screens/`、`dialogs/` 或平行目录。
- 本批不会触发 Run、Resume、SSE、正式 Artifact 写回或额外计费。

## 6. 浏览器验收

### Desktop 1440 x 1000

- Settings Overview 为 7 条高密度摘要行，无重复 Tab，无横向滚动。
- Provider Sheet 宽 820px；默认文本/封面服务等宽双列。
- Provider 折叠项按内容高度排列；展开项使用内部列表滚动，底部完成栏稳定。
- 默认模型 Combobox 可在 Dialog 内打开；Escape 只关闭选项层，不关闭 Provider Sheet。
- Stage Config Sheet 宽 620px；普通参数双列，输入高度一致。
- Planning 常驻 Inspector 与 Sheet 同时存在时，DOM duplicate ID 数量为 0。

### Mobile 390 x 844

- `body.scrollWidth === 390`。
- Provider Sheet 全屏；中间 body 为单一滚动区，Header 与底部完成栏稳定。
- Provider 连接、模型与动作组回落单列；无按钮文字溢出。
- Info Brief 在 Sheet 内单列，长受众字段不再被双列压窄。
- 普通 Stage 参数为 340px 单列，Sheet `scrollWidth === clientWidth === 390`。

### 交互与控制台

- Option Popup、Provider Sheet、Stage Config Sheet 均可由键盘关闭。
- Provider Switch 具有可读名称和 Focus Ring。
- 浏览器 Console 无新增 Error/Warning；React DevTools 开发提示不计为产品警告。

### 最终验收结果

- 前端全量测试：63 个测试文件、215 项测试全部通过。
- TypeScript 与 Vite 生产构建通过。
- CSS 审计基线经视觉复核后更新，随后审计通过；`git diff --check` 通过。
- 1440 x 1000 与 390 x 844 实机浏览器复验通过；移动端 `body.scrollWidth === 390`。
- Info 常驻 Inspector 与 Stage Sheet 同时渲染时，重复 DOM ID 数量为 0。
- 浏览器 Console：0 Error、0 Warning。
- 验收截图：`output/playwright/phase95b/planning-info-desktop.png`、`output/playwright/phase95b/info-stage-sheet-mobile.png`。

## 7. Phase 9.5C 边界

下一批按阶段 Artifact 和写回目标逐个迁移运行期表单：

1. Summary/Outline 的结构编辑与候选方向表单。
2. Detail 的章节蓝图、人物变化、世界观/Wiki、伏笔账本。
3. Text 的正文编辑、选区修订、版本/审核写回。
4. Cover Brief 与 Export 元数据/格式选择。

每个表单迁移前必须记录草稿所有者、正式写回命令、关闭保护、隐藏字段、错误来源和移动重排。不得用全局 CSS 机械替换，也不得把保存草稿误写成接受 Canon。
