# Phase 9 产品壳层、工作台布局与交互动效重构计划

> 状态：Phase 9.0、9.1、9.2、9.3、9.4、9.5A、9.5B、9.5C-1、9.5C-2、9.5C-3 已分阶段实施；Cover / Export 与 9.6-9.10 按退出门禁推进
>
> 制定日期：2026-07-22
>
> 适用范围：Yotsuba Ink 全局壳层、Planning、自动 Cockpit、Settings、Knowledge、Info、Summary、Outline、Detail、Text、Cover、Export、History、Recovery
>
> 前置条件：不得绕过 `stage-artifact-contract.md`；Phase 8.8 的真实 Provider 全链路验收仍须独立完成，Phase 9 视觉工作不得被标记为该验收的替代品

## 1. 文档目的

本轮目标不是给现有页面批量增加发光、粒子、卡片和入场动画，而是在保留阶段 Artifact、三档模式、人工闸门、恢复、预算、SSE 和写回语义的前提下，完成一次产品体量、导航结构、页面构图、控件一致性和动效语言的系统升级。

本方案必须同时解决以下问题：

1. Provider、模型、阶段等 Option 浮层位置、尺寸、滚动、搜索、分组和状态不统一。
2. 顶部阶段进度与 Planning Canvas 重复，浪费首屏并制造两套进度事实。
3. 当前产品接近单页控制台，缺少可扩展但不打扰创作的产品级导航。
4. 三档模式虽然有颜色和按钮差异，但切换缺少空间层面的沉浸反馈。
5. 页面仍有大量同构面板和框线，阶段之间的 Artifact 特征不够鲜明。
6. 移动端把桌面画布直接缩小，阶段节点和连接关系不可读。
7. Detail 和 Text 虽已有专业工作面，但侧栏职责、折叠、尺寸和移动端形态仍需统一。
8. Input、Button、Switch、Checkbox、Tooltip、Loader、Tabs、Dialog 的视觉反馈需要统一，但不能把 Uiverse 的霓虹演示样式原样铺满生产工具。
9. 外部组件需要形成可追溯的采用、改造和拒绝决策，不能把不同组件站的默认风格拼成组件展示页。
10. 当前四个 Settings Tab 语义交叉、同一 Provider/模型在多个入口重复配置，首次用户缺少连续的启动准备路径。
11. 输入框宽度、双列关系、Label、错误和保存状态缺少统一合同，导致表单长度不一、对齐混乱和移动端压缩。
12. 用户指引依赖零散说明和工程名词，缺少可跳过、可恢复、可定位错误的任务内引导。

本轮只制定实施方案，不修改前端业务代码、后端、数据合同或运行状态。

## 2. 最高约束

### 2.1 产品约束

- 每个阶段先定义 Artifact、用户决策、写回目标和下一阶段依赖，再决定页面内容。
- 每个阶段首屏只允许一个主 Artifact、一个主要支撑区和一个推进流程的主决策。
- Planning Canvas 是配置态七阶段链路的唯一视觉进度源。
- Header 不再展示第二套七阶段链路、ECG 阶段线或节点点阵。
- 首次 Guided Setup 与七阶段运行进度是两类概念，必须在位置、文案和数据来源上分离；首次完成后不常驻第二套 Stepper。
- 打开导航、切换主题、Hover、Focus、切换 Tab、播放遮罩和展开侧栏不得触发 Provider、`/resume`、SSE 重连、正式写回或重复计费。
- Fast、Balanced、Deep 的权限合同不因视觉重构改变。
- Demo 和 Mock 流程继续可用，但不能冒充真实生成、真实检索、真实进度或真实写回。

### 2.2 工程约束

- 前端继续只使用 `layout/`、`planning/`、`brief/`、`running/`、`settings/`、`state/`、`services/`、`contracts/`、`lib/`。
- 不新增顶层 `components/`、`dialogs/`、`screens/`、`reactbits/`、`uiverse/` 或 `aceternity/`。
- 现有 Radix 继续拥有 Dialog、Tabs、Tooltip、Switch 和短列表 Select 的交互语义。
- 现有 `motion` 继续是 React 状态过渡的唯一默认运行时。
- Anime.js 暂不安装；只有隔离 SVG/Canvas 多步骤时间线通过专项评审后才允许引入。
- 正常文件目标为 200-250 行，重型文件最多 300 行；按责任拆分，不以减少代码量作为目标。
- 不批量重写现有 CSS，不以删除历史样式数量作为完成指标；按页面所有权逐步迁移并保留可回滚边界。

### 2.3 视觉约束

- 产品应像长期使用的小说生产工具，而不是 AI 营销站、游戏启动器或霓虹控制台。
- 模式色只用于当前模式、当前选择、关键状态和少量边缘反馈，不染满整个页面。
- 不使用 Card 套 Card；页面区块采用分栏、轨道、表格、稿纸、账本和工具栏组织。
- Hover 不抬高布局、不改变元素尺寸、不让相邻内容位移。
- Glow 只用于当前选择、关键命令或一次性成功反馈，空闲时不得持续呼吸。
- 正文、长表格、设置项和账本禁止逐字、逐字符、BlurText 或 SplitText 动画。
- Reduced Motion 下非必要动画必须为 `0s/none`，不能只缩短时间。

## 3. 当前审查结论

### 3.1 用户截图一：Option 浮层

当前 Provider 模板使用原生 `select`，在长列表下出现以下问题：

- 浮层超过目标输入宽度并占据大面积页面。
- 顶部和底部缺少稳定的视口碰撞约束。
- 没有搜索、分组、类型和接入级别信息。
- Hover、当前项、键盘焦点和选中态受浏览器控制，无法与模式色统一。
- 选项数量增长到 20-30 个后，用户只能线性扫描。
- 移动端由系统原生选择器接管，无法呈现 Provider 的描述和状态。

结论：短列表继续使用 Radix Select；超过 7 项、需要搜索或需要两行元数据时，统一使用本地 `OptionCombobox`。不再允许业务页面直接新增长列表原生 `select`。

### 3.2 用户截图二：重复阶段链路

Planning 目前同时存在：

- Header 内的准备/阶段点阵。
- Canvas 顶部七阶段横条。
- Canvas 中央七个流程节点。

其中后两者表达相同的七阶段顺序，Header 又增加配置进度，导致用户难以判断哪一处才是导航和进度事实。

结论：

- 删除 Canvas 顶部七阶段横条。
- Header 删除七阶段点阵和 ECG 进度。
- Canvas 中央节点是桌面端唯一阶段进度与阶段选择入口。
- 移动端不缩小 Canvas，改为可读的纵向/横向阶段轨道。
- 配置完成度 Stepper 进入 Planning 的启动准备区，不常驻全局 Header。

### 3.3 实机页面审查

#### Planning

- 桌面端右侧 Inspector 字段密度高，Canvas 中央存在大量空域。
- 节点视觉尺寸偏小，缩放后信息价值不足。
- 移动端节点被缩到无法阅读，只能看到装饰性的流程缩略图。
- Header 在 390px 下分为三行，工具和模式切换占据过多首屏。

#### Summary / Outline / Detail

- 已经形成稿纸、Beat Board、施工表的差异化基础，不应推倒重做。
- 当前外围框线和独立面板仍多，右侧观察区在部分状态下会与主 Artifact 争夺注意力。
- 后续优化重点是留白、边界层级、行 Hover、Sticky 工具和支撑区收纳，而不是增加更多内容。

#### Text

- 章节导航、正文稿纸和质量/Wiki Inspector 的三栏方向正确。
- 左侧上下文段落过密，右侧空态面积大；需要更清晰的可折叠侧栏和阅读/审校模式切换。
- 继续保持正文为最大工作面，不把 AI 工具改成常驻聊天栏。

#### Cover

- 三候选结构清晰，但缺图时出现三块大面积空容器。
- BorderGlow 只应表达候选选中或可定稿，不应让三列持续发光。
- 移动端采用单候选分页/滑动，不能把三列压缩。

#### Export

- 交付范围、交付包、校验状态三列具备业务含义。
- 需要通过轨道、表格和状态行减少面板感，而不是套用 Bento Card。

#### History / Recovery

- 当前大面积点阵背景和半透明容器让内容层级下降。
- 历史更适合稳定列表 + 详情区 + 版本时间线；恢复动作必须比统计数字更突出。

#### Settings

- 当前四个 Tab 不是稳定的信息架构，只是把同一组配置按技术名词拆开：`全局模型`、`模型接口`、`阶段覆盖` 会重复要求用户理解 Provider、模型和继承关系，`运行策略` 又把系统固定能力伪装成可配置项。
- 全局 Provider、Provider Profile、默认模型、阶段 Provider/模型在 Settings 和 `StageInspector` 多处出现；用户无法判断哪个入口是最终事实源，也无法预测修改影响范围。
- `StageInspector` 直接暴露 Stage ID、Output Key、Memory 读写、Temperature、Max Tokens 等工程字段；这些字段对首次创作不是必要决策，却与题材、参考资料和创作方式处在同一层级。
- Provider 列表和模型列表仍是统一 Option 系统的最高优先级落点，但 Option 视觉统一不能替代字段归属重构。
- 只读运行策略使用 Checkbox，会让用户误以为可以关闭；应改为“自动保护”状态摘要，而不是保留 Disabled/ReadOnly 假控件。
- 设置体验必须拆成“首次引导式配置”和“完成后的单页配置总览”两种状态；不能把四个 Tab 仅换皮为 Stepper。
- 设置页适合纵向 Section、摘要行和局部编辑 Sheet，不适合 MagicBento、Hover 放大卡片或所有字段同时展开。

### 3.4 配置语义审查

当前界面还存在一组跨页面问题，必须与视觉重构同时解决：

1. **名词站在工程实现一侧**：Provider、接口、覆盖、运行策略、Output Key 等词要求普通创作者理解内部路由和模型编排。
2. **一个值有多个编辑入口**：默认模型和阶段模型既可在 Settings 修改，也可在 Stage Inspector 修改，但缺少清晰的继承/例外说明。
3. **字段按代码结构分组而非按用户任务分组**：用户为了“开始写一本书”需要在 Brief、Knowledge、Settings 和 Stage Inspector 之间来回切换。
4. **控件外观不能表达权限**：只读 Checkbox、看似可编辑但未写回的 Select、技术字段和真正必填字段处于同一视觉强度。
5. **表单几何没有合同**：短数字、长模型名、叙事 Textarea 和双列字段按局部 CSS 各自生长，导致控件宽度不一、标签错线和移动端压缩。
6. **说明文本承担了架构补丁**：字段归属不清时用长说明补救，增加阅读量但没有减少决策数。

产品判断：用户提出的“像流程一样一步一步配置”只适用于首次准备。日常修改若仍强制走完整 Stepper，会让熟悉用户重复经过无关步骤。因此 Phase 9 固定采用双态体验，并以字段唯一归属消除重复，而不是增加更多导航组件。

## 4. 外部组件采用矩阵

### 4.1 来源与许可证门禁

| 来源 | 当前许可结论 | 使用规则 |
| --- | --- | --- |
| React Bits | MIT + Commons Clause；可进入最终应用，不得出售、再许可或重新分发组件本身，保留声明 | 只借机制或在明确登记后改造源码；不得形成内部可对外分发的 React Bits 组件包 |
| Uiverse Galaxy | MIT；仓库内元素可修改和用于产品，建议保留作者与来源记录 | 只从 Galaxy 中可定位的源码进入评审；网页效果截图不作为源码许可凭证 |
| Aceternity UI | Item Licence 允许创建和分发最终产品，但官网通用 Terms 更严格，第三方组件另有许可 | 只使用明确标记 Free 且可定位 Item 的内容；保存 Item、Licence、Terms 和依赖记录，优先只借交互思想 |
| Motion Primitives | MIT，基于 Motion 和 Tailwind | 可作为 Motion 机制参考；本项目没有 Tailwind，不复制其样式体系 |
| Radix Primitives | MIT，现有依赖 | 继续承担已有基础语义和焦点管理 |
| Base UI | 开源组件原语；实施前固定版本并再次核对仓库 LICENSE | 只作为长列表 Combobox 候选依赖，先做包体、键盘、IME 和 Portal 技术验证 |
| Anime.js | MIT | 本轮不安装；只为未来隔离的 SVG/Canvas 时间线保留评审入口 |

### 4.2 用户提供的 Prompt 组件决策

| Prompt | 原组件 | 决策 | Yotsuba Ink 采纳方式 |
| --- | --- | --- | --- |
| 1 | StaggeredMenu | 改造机制 | 变为隐式 `ProductNavigationRail`，使用 Motion + Radix Dialog/Sheet 语义；拒绝营销式全屏大字、社交链接和长 Stagger |
| 2 | Stepper | 改造机制 | 只用于首次 Guided Setup 的 5 个真实配置步骤；完成后退出，不表达七阶段运行进度 |
| 3 | MagicBento | 局部采用 | 借非等宽 Grid、边缘反馈和稳定 Hover；拒绝粒子、磁吸、3D Tilt、全局 Spotlight 和卡片墙 |
| 4 | Dock | 改造机制 | 用于主题、历史、重置、设置等全局工具；放大幅度最多 1.06，Header 高度固定，移动端退化为普通工具条 |
| 5 | BorderGlow | 严格限制 | 只用于模式选择、当前候选、当前步骤或 Ready 主动作；静止边缘光，不持续绕边跑 |
| 6 | AnimatedContent | 本地重写 | 使用现有 Motion，180-240ms、位移 3-8px、默认无 Blur；只用于 Panel/Artifact 切换 |
| 7 | SplitText | 极少使用 | 仅模式切换遮罩的 2-6 字标题，按词/短语进入；Reduced Motion 和移动端低性能直接显示 |
| 补充 | FadeContent | 本地重写 | 仅首次局部区域进入或空态转 Ready；不安装 GSAP/ScrollTrigger，不按滚动反复播放 |
| 补充 | BlurText | 拒绝正文使用 | 可在模式遮罩短标题中借鉴一次性节奏；不用于字段、长标题、正文和设置 |

### 4.3 Uiverse 片段决策

| 片段 | 决策 | 改造要求 |
| --- | --- | --- |
| 100px Gradient Spinner | 缩小重写 | 16/20/24px 三档，颜色来自模式 Token；只用于短命令 Busy，长任务用真实进度或 Skeleton |
| Input Hover/Focus | 采用机制 | 1px 默认边框、2px Focus Ring、最多 4px 外扩；错误/只读/禁用优先于模式光 |
| Sun/Moon Switch | 简化重写 | 保留太阳/月亮位移和一次旋转，删除多层云、星星 SVG；固定 48x28，Reduced Motion 即时切换 |
| Neo Toggle | 不原样复制 | 只借 Track/Thumb/状态点；删除频谱、拖拽、Progress Arc 和持续 Pulse |
| Neon Checkbox | 降噪重写 | 20/22px、模式色 Check、一次 100ms Scale；删除发光点、40px Shadow 和文字位移 |
| Hover Tooltip | 采用层级 | Tooltip 保持 280px 以内、300-500ms 延迟；详细信息改 Popover，Touch 有点击入口 |
| Glow Button | 限制使用 | 只为首页启动/继续/确认等唯一主动作提供弱边缘光；无镜面投影、无大面积 Shadow |

## 5. 目标信息架构

### 5.1 全局结构

```text
Product Shell
  |- Product Navigation Trigger
  |- Hidden Navigation Rail / Mobile Sheet
  |- Stable Header
  |    |- Project Identity / Current Surface
  |    |- Compact Status (not stage chain)
  |    |- Global Tool Dock
  |    |- Quality Mode + Primary Action
  |- Workspace
  |    |- Planning / Cockpit / Stage Workbench
  |    |- Contextual Sidebar or Inspector
  |    `- Finalize Tray
  `- Global Overlays
       |- Settings
       |- Knowledge
       |- History / Recovery
       `- Quality Mode Transition
```

### 5.2 隐式产品导航

新增 `ProductNavigationRail`，但默认只显示 44-48px 的导航触发区或品牌标记，不常驻占用主工作面。

导航只包含产品级入口：

1. 当前项目/Planning。
2. 当前运行/阶段工作台，仅有 Run 时可用。
3. 知识资料。
4. 创作历史与恢复。
5. 模型与运行设置。

不得把七个创作阶段复制到产品侧栏。七阶段只属于 Planning Canvas 和 Deep 运行路由，不成为第二套全局菜单。

桌面行为：

- 点击品牌/菜单图标后，从左侧展开 288-320px Rail。
- Backdrop 只降低主区对比度，不使用大面积动态 Blur。
- 当前入口以模式色 2px 内描边和图标状态表达。
- 菜单行按 25-35ms Stagger 进入，总时长不超过 260ms。
- Escape、Backdrop、再次点击触发器关闭；关闭后焦点返回触发器。
- Dirty/Busy 页面不被导航直接绕过，继续走现有路由保护。

移动端行为：

- 从底部或左侧打开全屏 Sheet，最小触控区 44px。
- 不播放逐行长 Stagger；最多 120ms 整体淡入。
- 工具入口和主导航分区，避免把所有 Header 图标重复一遍。

### 5.3 Header 重构

Header 分成三个稳定区，不再承担七阶段进度：

| 区域 | 内容 | 约束 |
| --- | --- | --- |
| 左 | 导航触发器、项目名、当前页面名 | 项目名可省略副标题；移动端只留标记和页面名 |
| 中 | 保存状态、当前运行状态或配置完成度一句话 | 不画七节点，不显示 ECG；Planning 可点击进入首次准备或配置缺项 |
| 右 | Global Tool Dock、模式选择、唯一主动作 | 固定高度；Busy 不变宽；工具不与模式主动作混在同一个分段控件 |

原 `StageProgressNavigator` 的目标拆分：

- 首次配置完成度迁移为 `GuidedSetupWorkbench` 的步骤导航；完成后只保留配置摘要/缺项入口。
- 运行中的当前阶段状态迁移为 `CurrentRunStatus` 文本/徽标。
- 七阶段总进度只由 Planning Canvas 或自动 Cockpit Rail 表达。
- 组件完成迁移后删除 Header 消费，不立即删除其运行辅助函数，先由测试证明无其他消费者。

### 5.4 Global Tool Dock

Dock 固定承载：主题、撤销/重置、历史、设置。知识库入口留在导航和 Planning 准备区，不重复塞入 Dock。

交互规则：

- 图标使用 Lucide，固定 36x36；桌面 Pointer 接近时最大 38x38 或 `scale(1.055)`。
- Header 预留最大尺寸，Hover 不改变 Header 高度或相邻按钮位置。
- 当前打开的 History/Settings 使用 `aria-pressed` 和稳定底色，不持续发光。
- 主题切换使用 `ThemeModeSwitch`，不在 Dock 内同时放 Sun/Moon 两个按钮。
- 重置保持现有确认、撤销和 Busy 合同。
- 移动端取消邻近放大，只保留普通 40x40 工具按钮。

### 5.5 配置体验的双态信息架构

配置入口根据项目是否完成首次准备呈现两种稳定状态：

```text
首次进入 / 尚未完成必要准备
  -> GuidedSetupWorkbench
     1. 故事起点
     2. 参考方式
     3. 创作方式
     4. AI 服务
     5. 开始前确认
  -> Planning / 创建 Run

完成首次准备后再次进入
  -> SettingsOverview
     - 创作设定
     - 参考与资料
     - 创作方式
     - AI 服务与默认模型
     - 输出偏好
     - 高级阶段例外
  -> 点击“修改”打开局部 Section / Sheet
```

状态选择规则：

- 是否进入首次流程由真实 Workflow 必填值、Knowledge 选择和服务端 Provider Readiness 派生，不新增一个与业务状态脱节的 `setupCompleted` 布尔值。
- 可以持久化 `lastVisitedSetupStepId` 作为纯 UI 恢复位置，但它不能证明某一步完成。
- 用户中途退出后，下次从最后访问步骤恢复；若前面字段后来失效，流程自动定位到最早阻塞步骤。
- 已完成项目再次打开设置时直接进入 `SettingsOverview`，不强制重播首次流程。
- Overview 的“重新检查配置”可以打开确认步骤，但不能把用户带回一条必须重新点击五次的流程。
- Provider 管理可作为专用 Sheet/子页面存在；它是 AI 服务的明细管理，不再与默认模型、阶段例外并列成多个重复 Tab。

### 5.6 字段唯一归属与命名重构

每个可写字段必须有一个主编辑位置，其他页面只能显示摘要、继承结果或跳转入口：

| 配置对象 | 唯一主编辑位置 | 其他页面允许展示 | 禁止重复 |
| --- | --- | --- | --- |
| Story Brief | 首次流程“故事起点” / Planning Info 配置 | Header/Overview 摘要、Info 下游只读基线 | Settings 再建一份题材和简介表单 |
| Reference / Knowledge | 首次流程“参考方式” / Knowledge 管理 | 已选资料数、索引状态、联网状态 | Stage Inspector 再次选择同一资料源 |
| Quality Mode | 首次流程“创作方式” / Header 模式控件 | Overview 摘要和影响说明 | Settings 再建独立模式 Tab |
| Provider Profile | 首次流程“AI 服务” / Provider Manager | 当前服务、健康状态、密钥来源摘要 | 每个阶段复制完整 Base URL/API Key 表单 |
| 默认文本/图片模型 | AI 服务区域 | Stage Inspector 显示“继承默认” | 全局模型和模型接口分别编辑同一值 |
| 阶段 Provider/模型 | 对应 `StageInspector` 的“阶段例外”高级区 | Overview 只显示“有 N 个阶段使用例外” | Settings 展开七个阶段的重复表单 |
| 自动保存/运行前检查/资产校验 | 系统能力，只读状态 | Overview 的“自动保护”状态行 | 用 Checkbox/Switch 暗示可关闭 |
| Output Preferences | 首次流程相关步骤或对应阶段唯一字段 | Overview 摘要 | Planning、Settings、Export 各存一份互不关联的值 |

普通界面术语固定为：

| 当前术语 | 面向用户的名称 | 使用规则 |
| --- | --- | --- |
| 模型接口 | AI 服务 | 普通界面统一使用；Provider 仅出现在高级说明或错误详情 |
| 厂商模板 | 服务厂商 / 服务模板 | 先选择厂商，再显示必要连接字段 |
| 全局模型 | 默认生成模型 | 强调未设置例外的阶段会继承它 |
| 默认文本接口 | 文本生成服务 | 与“默认文本模型”组成一个区域 |
| 默认图片接口 | 封面生成服务 | 未启用 Cover 时不要求配置 |
| 阶段覆盖 | 阶段例外 | 默认收起，只在确有特殊需求时开启 |
| 运行策略 | 自动保护 | 固定能力使用状态行；真正可配置的行为按用户结果命名 |
| 轻量连通测试 | 检查连接 | 明确这是连接检查，不等同于完整生成成功 |
| 获取模型列表 | 同步可用模型 | 成功后显示更新时间和来源 |
| Memory 读取/写回 | 使用已有设定 / 定稿后更新设定 | 仅阶段高级配置可见 |
| Stage ID / Output Key | 默认隐藏 | 仅开发模式或诊断详情可见，不作为普通表单字段 |

文案规则：标题说明用户正在完成的任务，Label 命名输入结果，帮助文本解释影响；禁止用“配置配置项”“模型接口 Provider”“覆盖策略”等同义叠加表达。

## 6. 统一 Option / Select 系统

### 6.1 组件边界

建立一个本地调用面，不让业务页面关心底层是 Radix Select 还是 Combobox：

```ts
type OptionItem = {
  value: string;
  label: string;
  description?: string;
  group?: string;
  keywords?: string[];
  icon?: ReactNode;
  status?: 'ready' | 'warning' | 'disabled';
  disabled?: boolean;
};

type OptionFieldProps = {
  id?: string;
  label: string;
  value: string;
  items: OptionItem[];
  mode?: 'auto' | 'select' | 'combobox';
  searchable?: boolean;
  allowCustomValue?: boolean;
  placeholder?: string;
  description?: string;
  error?: string;
  disabled?: boolean;
  readOnly?: boolean;
  onValueChange: (value: string) => void;
  onCustomValueCommit?: (value: string) => void;
};
```

`mode="auto"` 规则：

- 7 项以内且每项单行：Radix Select。
- 超过 7 项、存在 Group/Description 或明确 `searchable`：Combobox。
- 允许录入新模型：Combobox + 显式“添加模型”命令，不把任意输入自动当成保存成功。

### 6.2 浮层几何合同

- 桌面宽度：`max(triggerWidth, 280px)`，上限 `min(420px, viewport - 24px)`。
- 最大高度：`min(360px, viewportAvailableHeight - 16px)`。
- Trigger 与 Popup 间距 6px；Collision Padding 12px。
- 默认向下、左对齐；空间不足自动翻转，但选中项不再覆盖 Trigger。
- Popup 使用 Portal，z-index 只取 Overlay Token，不按页面临时追加数字。
- 搜索栏 Sticky；分组标题 Sticky 仅在组内滚动需要时开启。
- 选项行高度 40px，带 Description 时 52-56px，不能由 Hover 改变。
- 当前项使用 Check 图标 + 2px 模式色内描边；Hover 只改变背景；Focus-visible 使用统一 Ring。
- 列表首尾提供 12px 渐隐提示，不使用动态 GradualBlur。

### 6.3 Provider 专用展示

Provider 模板按以下顺序分组：

1. 官方直连。
2. 官方兼容层。
3. 聚合或自建网关。
4. 自定义兼容接口。

每项展示：厂商名、文本/图片类型、接入级别、Ready/缺配置状态。Base URL、密钥名和长说明不进入选项主行，选择后在字段下方的 Meta 区展示。

搜索范围：Label、厂商名、Template ID、类型和关键词；中文 IME 组合期间不提交过滤；`Escape` 首次清空搜索、再次关闭浮层。

### 6.4 移动端

- 390px 以下，长 Combobox 使用底部 Sheet，高度不超过 `min(72dvh, 620px)`。
- 顶部固定标题、搜索和关闭；中间单一滚动列表；底部不增加重复确认，点选即回写并关闭。
- 允许 Custom Model 时，底部显示独立输入和“添加”命令，防止误触普通选项。
- 软键盘打开后使用 `dvh` 和 Safe Area，不让列表被键盘遮挡。

### 6.5 首批迁移清单

优先级 P0：

- `ProviderCreateControl` 厂商模板。
- `ProviderTemplateSelect` 厂商模板。
- AI 服务区域的默认文本/图片 Provider。
- Stage Inspector“阶段例外”的 Provider。
- `ModelOptionInput` 模型列表和新模型录入。

优先级 P1：

- Planning 阶段输入枚举。
- Stage Inspector 主 Provider、Fallback Provider 和模型。
- Detail 人物/关系、Outline 伏笔状态等长或结构化选项。

不迁移：

- 2-3 项且移动端原生体验更优、无需元数据的简单枚举，除非视觉一致性验收不通过。

## 7. 首次引导式配置与后续设置总览

### 7.1 与创作阶段链路的区别

`GuidedSetupWorkbench` 是首次启动准备流程，不表达 Info -> Export 的运行进度。它只在项目尚未满足启动条件时占据 Planning 主工作面；完成后退出，不成为全局常驻的第二套阶段链。

`SetupStepNavigation` 表达五类用户任务，而不是当前四个 Settings Tab 的技术分类：

1. 故事起点。
2. 参考方式。
3. 创作方式。
4. AI 服务。
5. 开始前确认。

每一步由 Workflow、Knowledge 和服务端 Readiness 的真实结果派生。禁止用 `setTimeout`、前端计数或动画完成回调将步骤标为完成。

### 7.2 首次流程整体构图

桌面使用“窄步骤轨 + 单一表单工作面 + 固定底部动作”的连续布局：

```text
┌──────────────────────────────────────────────────────────┐
│ 项目名称                           已自动保存 / 帮助入口 │
├──────────────┬───────────────────────────────────────────┤
│ 1 故事起点   │ 当前步骤标题 + 一句影响说明              │
│ 2 参考方式   │                                           │
│ 3 创作方式   │ 单一 Form Section                         │
│ 4 AI 服务    │ 条件字段 / 就近错误 / 状态               │
│ 5 开始前确认 │                                           │
├──────────────┴───────────────────────────────────────────┤
│ 保存后退出             上一步          继续 / 开始创作 │
└──────────────────────────────────────────────────────────┘
```

- 左侧步骤轨宽 208-240px；只显示步骤名、完成/阻塞状态和最多一行摘要，不显示所有字段。
- 右侧表单工作面最大内容宽度 760-880px，避免输入框在大屏无限拉长。
- 页面不使用大 Card 包住表单；步骤之间以标题、说明、分隔线和留白形成层级。
- 底部操作固定但不遮挡内容：左侧“保存后退出”，右侧“上一步 / 继续”；每一步只有一个主动作。
- 进入下一步前只校验本步阻塞字段；可选内容允许明确“暂不添加”。
- “继续”失败时滚动并聚焦第一个阻塞字段，顶部只显示问题摘要，不复制完整错误。
- 自动保存状态占固定高度，`保存中 -> 已保存 -> 保存失败` 不推动布局；保存失败必须保留草稿并给出重试。
- 390px 以下变为顶部 `x/5 + 当前步骤`、单列表单和安全区底部动作；步骤清单从标题打开 Sheet，不横排五个长标签。

### 7.3 第一步：故事起点

目的：让系统获得立项所需的最小 Story Brief，而不是一次要求用户填写完整世界观。

推荐字段和布局：

| 区域 | 字段 | 布局 | 校验/说明 |
| --- | --- | --- | --- |
| 基本方向 | 题材、目标篇幅 | 两列等宽；移动端单列 | 题材必填；篇幅使用范围或明确单位 |
| 读者与风格 | 目标读者、叙事风格 | 两列等宽 | 允许智能推荐，不把 Placeholder 当答案 |
| 核心创意 | 一句话创意 / 想写的故事 | 全宽 Textarea | 必填；给内容例子，不解释按钮操作 |
| 创作边界 | 关键词、明确避开的内容 | 全宽 Tag/Input + Textarea | 可选；禁忌必须能清除和复查 |

表单参考用户提供的 Uiverse `AI Story Maker Dream Form` 只吸收以下结构：清晰标题、纵向字段、等宽双列、全宽叙事输入、底部唯一主动作。不得复制深色大 Card、Tailwind 类、示例中的 AI 输出 Textarea 或固定英文语义。

步骤完成条件：核心创意、题材和所有当前合同中的启动必填值有效。世界观、人物名和章节细节不在此步强迫填写，它们由 Info Artifact 生成和定稿。

### 7.4 第二步：参考方式

目的：让用户选择“系统如何获得参考”，而不是先展示 RAG、Embedding、Chunk 等内部名词。

首先只展示三种互斥/可组合方式：

- 智能联网参考。
- 指定网页链接。
- 上传项目资料。

条件显示规则：

- 未启用联网时不显示搜索范围和新鲜度等附属字段。
- 未选择链接方式时不显示 URL 输入列表。
- 未上传文件时展示紧凑上传区；上传后切换为资料队列、解析状态和删除/重试。
- 索引、分片和检索策略进入“高级参考设置”，默认收起；普通用户只看到资料是否可用以及会影响哪些阶段。
- 上传/索引状态来自真实服务端结果；可选参考为空时允许继续，并明确显示“将仅依据你的故事设定创作”。

步骤完成条件：所有已选择的参考源可用，失败项已处理或明确排除。可选步骤的“跳过”是显式决定，不等同于完成了不存在的上传任务。

### 7.5 第三步：创作方式

目的：选择控制权和工作节奏，不展示 Token 档位或一组散落开关。

- 使用 Fast / Balanced / Deep 三项模式选择，每项只说明“系统自动到哪里、用户在哪些节点定稿、适合什么任务”。
- 模式切换使用第 8 节遮罩，但表单状态在遮罩前完成受控更新；动画不保存 Workflow、不创建 Run。
- Balanced 的“版本对比”只在选择 Balanced 后出现，并解释只有主动触发才增加候选和评审调用。
- Deep 的阶段确认要求由模式合同派生，不让用户逐阶段重复勾选七个相同开关。
- 章节长度、分卷倾向、导出偏好等结果型配置按现有合同归入“输出偏好”；技术参数不进入首屏。

步骤完成条件：质量模式有效，所有因当前模式而出现的必填输出偏好有效。

### 7.6 第四步：AI 服务

目的：用最少配置完成真实服务接入，并在进入运行前给出可信的可用性判断。

推荐顺序：

1. 选择文本生成服务厂商/模板。
2. 只显示该模板必要的 Base URL、API Key、默认模型字段。
3. 保存密钥后执行用户主动触发的“检查连接”。
4. 可用模型很多时使用 `OptionCombobox`；列表不可用时允许显式录入自定义模型。
5. 只有启用 Cover 阶段时才展开“封面生成服务”；未启用时不阻塞。

行为规则：

- 密钥“已保存”与“当前输入草稿”必须分开表达；关闭/切步骤继续使用 Dirty Guard。
- “检查连接”只证明轻量请求可达，不文案承诺完整结构化生成一定成功。
- “同步可用模型”与“检查连接”是两个命令，Busy 互斥，失败各自保留原因和重试。
- Provider Profile 只配置一次；各阶段默认显示“继承文本/封面服务”。
- Fallback、评审模型、Temperature、Max Tokens 进入对应阶段“阶段例外”高级区，不出现在首次流程。
- Demo/Mock 可继续工作，但必须明确当前使用演示服务，不得用演示成功掩盖真实 Provider 未就绪。

步骤完成条件来自服务端 Readiness：至少一个当前工作流所需的文本服务就绪；启用 Cover 时图片服务也就绪。缺余额、鉴权失败、模型不存在和网络失败必须分类，不使用同一个“配置失败”。

### 7.7 第五步：开始前确认

此步只汇总和定位，不要求重新输入：

| 摘要区 | 展示内容 | 可用动作 |
| --- | --- | --- |
| 故事起点 | 题材、篇幅、核心创意摘要 | 修改第一步 |
| 参考方式 | 联网状态、链接数、可用资料数 | 修改第二步 |
| 创作方式 | 模式、人工确认点、输出偏好 | 修改第三步 |
| AI 服务 | 文本/封面服务、模型、连接状态 | 修改第四步 / 检查连接 |
| 启动检查 | Blocking、Warning、Ready | 定位问题 / 开始创作 |

- Blocking 最多在主区展示 3 项，其他进入详情；每项必须带“去处理”并定位到真实字段。
- Warning 可以继续，但必须在启动命令前明确；不能在动画后才暴露。
- “开始创作”只有 readiness 真正通过时可用，点击后走现有 Run 创建合同。
- Run 创建 Busy 时锁定所有会改变请求快照的字段；成功/失败来自真实响应。
- 最终提交快照应记录当前 Workflow/Knowledge/Provider 引用，避免用户在请求发出后看到另一个配置版本。

### 7.8 后续 Settings Overview

首次流程完成后，设置入口使用一个可扫描的单页总览，不再显示四个平级 Tab：

```text
设置
  创作设定          摘要 + 状态                         修改
  参考与资料        联网 / 资料数量 / 最近索引          管理
  创作方式          Balanced / Info 定稿后自动          修改
  AI 服务与默认模型 文本 Ready / 封面未启用             管理
  输出偏好          章节长度 / 分卷 / 导出格式           修改
  高级阶段例外      2 个阶段使用例外                    查看
  自动保护          自动保存 / 启动检查 / 资产校验       已启用
```

- 每个 Section 默认只显示 2-4 个最有价值的摘要、状态和一个明确动作。
- 点击“修改/管理”打开局部 Sheet 或内联编辑 Section；保存/取消后返回原滚动位置和焦点。
- AI 服务管理可列出多个 Provider Profile，但默认模型只在 AI 服务区域指定一次。
- “高级阶段例外”只显示例外数量、受影响阶段和“全部恢复默认”；具体编辑回到对应 Stage Inspector。
- “自动保护”使用状态图标和说明，不渲染 Checkbox/Switch。
- Overview 不展示 Stage ID、Output Key、Memory 原始字段、API Key 明文或七阶段完整表单。

### 7.9 步骤导航与动效

- 连接线完成：180ms `scaleX`，只在完成状态真实变化时播放一次。
- Check 进入：100ms `scale(.92) -> 1`，不弹跳、不持续发光。
- 前进时内容 `opacity + translateX(6px)`，返回时方向相反；160-200ms。
- 表单外壳和底部操作不重挂载，避免输入焦点、草稿和高度跳动。
- Reduced Motion 下立即切换；焦点仍移动到步骤标题或第一个错误字段。
- 浏览器 Back/Forward 只在设计了稳定内部路由时接入；否则步骤状态由本地 Hook 控制，禁止污染全局创作阶段路由。

## 8. 三档模式沉浸切换遮罩

### 8.1 目标

恢复模式切换的仪式感，但让动画解释工作方式变化，而不是只展示颜色特效。

### 8.2 状态合同

新增纯展示状态：

```ts
type ModeTransitionState = {
  from: QualityMode;
  to: QualityMode;
  phase: 'covering' | 'revealing';
  requestId: number;
};
```

业务 `quality_mode` 更新仍由现有状态函数完成。遮罩只消费已接受的本地模式变更，不拥有 Provider、Workflow 保存、路由和网络请求。

### 8.3 视觉序列

正常动态总时长目标 480-620ms：

1. 当前页面对比度降低，120ms。
2. 模式色从模式控件所在方向扩展为半透明遮罩，180ms。
3. 中央显示模式图标和短标题，例如“极速生产 / 平衡创作 / 精细定稿”，短语按词进入，100-140ms。
4. 遮罩向目标布局方向退场，180ms；新模式页面在遮罩后已经稳定，不等待动画再挂载。

不同模式只改变方向和语义：

- Fast：水平快速扫过，强调自动推进。
- Balanced：中央对称展开，强调关键节点人工确认。
- Deep：由边缘向内聚焦，再揭示，强调逐阶段定稿。

限制：

- 不使用大面积实时 Blur、粒子、Starfield、Glitch 或持续 Glow。
- 连续快速点击只保留最后一次目标模式，不堆叠三个遮罩。
- 模式锁定时不播放遮罩，只显示锁定原因。
- Reduced Motion 下立即更新，保留一条 `aria-live` 状态，不渲染中间帧。
- 页面有 Dirty 编辑时继续使用现有保护，遮罩不能掩盖确认层。

## 9. 基础组件视觉与交互合同

### 9.1 Button

只保留五类：Primary、Secondary、Ghost、Icon、Danger。

- Primary：页面同一决策区最多一个；弱边缘光只在 Hover/Focus/Ready 时出现。
- Secondary：稳定边框和中性背景，不使用 Glow。
- Ghost：工具命令；Hover 背景变化，不变尺寸。
- Icon：固定方形，必须有 `aria-label`，陌生图标有 Tooltip。
- Danger：只有进入确认层后成为主动作；不通过抖动或强发光施压。

统一状态：Default、Hover、Active、Focus、Busy、Success、Error、Disabled。Busy 固定宽度并防重复提交；Success 只由真实响应触发。

### 9.2 Input / Textarea

- 默认边框 1px，Hover 提高对比度，Focus 立即出现 2px Ring。
- 模式色 Ring 透明度控制在 20%-28%，错误色覆盖模式色。
- Label、Description、Error 各自占稳定行，不依赖 Placeholder 代替标签。
- Dirty/Saving/Failed 使用字段右上角紧凑状态，不改变控件高度。
- Textarea 长内容不使用 Inner Glow，保持阅读舒适度。

### 9.3 Switch

- 主题：专用 `ThemeModeSwitch`，48x28，太阳/月亮一次位移与旋转。
- 业务布尔项：`ControlSwitch`，40x22 或 44x24，只包含 Track、Thumb 和可选状态文本。
- 不复制 Neo Toggle 的频谱条、Progress Arc、拖拽和持续 Pulse。
- ReadOnly 不伪装成可操作 Switch，改为文本状态或 Disabled + 明确说明。

### 9.4 Checkbox

- 20x20 桌面、22x22 触屏。
- Checked 使用模式色底 + Check；Indeterminate 使用短横线。
- Hover 只加强边框；Active 一次 `scale(.96)`。
- 不让 Label 位移，不显示左右发光点，不使用无限 Pulse。

### 9.5 Tooltip / Popover

- 简短命名和状态解释用 Tooltip，300-500ms 延迟，宽度不超过 280px。
- 包含多段说明、链接、状态或操作时使用 Popover/Sheet，不做可交互 Tooltip。
- Touch 设备必须存在点击或长按之外的明确入口。
- Tooltip 不承载唯一错误、价格、风险或保存结果。

### 9.6 Loading

建立三层反馈：

| 时长/场景 | 组件 | 行为 |
| --- | --- | --- |
| < 800ms 命令 | 16-20px Mode Spinner | 按钮内或行内，不遮罩页面 |
| 0.8-8s 未知进度 | Skeleton / 中性步骤 | 保持目标布局，不伪造百分比 |
| 有真实步骤/进度 | Progress/Step List | 只消费 SSE、上传或导出真实状态 |

Uiverse Gradient Spinner 重写为：

```css
.mode-spinner {
  inline-size: var(--spinner-size, 18px);
  block-size: var(--spinner-size, 18px);
  border-radius: 50%;
  background: conic-gradient(from 0deg, transparent 0 22%, var(--mode-accent) 48%, var(--mode-accent-2) 100%);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #000 0);
  animation: mode-spinner-rotate 900ms linear infinite;
}
```

禁止在每个加载位置放 100px 发光环。Info 首次生成可保留阶段级遮罩，其他阶段优先 Skeleton、流式稿纸或真实步骤。

### 9.7 Tabs / Content Transition

- Tabs 继续使用 Radix 语义和 Roving Focus。
- Active Indicator 使用共享 Layout 动画，180-220ms。
- Panel 内容 160ms 淡入 + 3px 位移，退出 100ms。
- Tab 切换不重挂载整个工作台，不清空输入、不重置滚动、不触发请求。
- AnimatedContent/FadeContent 只以本地 `PanelTransition` 实现，不引入 ScrollTrigger。

### 9.8 Grid / Hover / BorderGlow

建立 `AdaptiveSurfaceGrid` 作为布局模式，不建立万能 Card：

- 使用 CSS Grid 的固定轨道、`minmax()`、`aspect-ratio` 和稳定 Gap。
- 子项可为 Setup Block、Candidate、Metric、Asset，不强制统一 DOM。
- Hover 只改变边框、背景和局部图标；不 `translateY`、不 Tilt。
- Spotlight 仅可在 Pointer Hover 当前项内以静态 Radial Background 更新，移动端和 Reduced Motion 禁用。
- BorderGlow 只在 `selected/current/ready` 进入一次并保持静态边缘，不循环跑光。

### 9.9 Form Layout Contract

本合同同时约束首次配置、Settings 和所有阶段编辑器。目标不是让每个 Input 看起来完全相同，而是让字段宽度由语义决定、同一行几何稳定、错误和保存状态不破坏排版。

#### 字段标准结构

```tsx
<FormField
  id="story-premise"
  label="核心创意"
  requirement="required"
  description="用一两段话说明主角面对的问题和你希望故事走向。"
  error={errors.premise}
  status={saveState.premise}
>
  <textarea rows={5} value={premise} onChange={handlePremiseChange} />
</FormField>
```

渲染顺序固定为：

1. Label + 必填/可选标记 + 稳定的字段状态位置。
2. Control。
3. 必要说明或错误；错误出现时占用预留说明区域，不能覆盖下一个字段。

Placeholder 只提供输入例子，不承担 Label、必填说明或操作教程。没有价值的帮助文本应删除，不通过每个字段下方堆一段说明制造“完整感”。

#### 宽度语义

| 宽度 | 适用字段 | 桌面建议 | 规则 |
| --- | --- | --- | --- |
| Short | 数值、年份、短枚举、温度等高级参数 | 160-220px | 不单独拉满整行；与相关字段并排 |
| Medium | 名称、模型、单行描述、URL | 320-480px | 在 Section 内按 Grid 轨道伸缩 |
| Full | 核心创意、禁忌、世界观、Prompt、长说明 | 当前内容区 100% | 设置 `max-width` 保护可读行长 |

- 同一行字段使用 `grid-template-columns: repeat(2, minmax(0, 1fr))` 或明确的 `minmax()` 轨道，控件等宽等高。
- 只有语义并列、预计输入长度相近且错误互不依赖的字段可以双列；不能因为“还有空位”把长 URL 与短数字拼在一行。
- 表单内容宽度建议 760-880px；长叙事 Textarea 可达到该宽度，短控件不因大屏自动扩到 1000px。
- 720px 以下全部单列；禁止在 390px 上维持双列后缩小字体。
- Select/Combobox Trigger 占满其 Grid 单元，但 Popup 继续遵守第 6.2 节几何合同。
- Textarea 使用稳定 `min-block-size` 和可调整上限；自动增长必须有最大高度和内部滚动，不能推走固定主动作。

建议 CSS 合同：

```css
.form-section {
  inline-size: min(100%, 52rem);
  display: grid;
  gap: var(--space-6);
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
  align-items: start;
}

.form-field[data-width='short'] { max-inline-size: 13.75rem; }
.form-field[data-width='medium'] { max-inline-size: 30rem; }
.form-field[data-width='full'] { inline-size: 100%; }

.form-control {
  inline-size: 100%;
  min-inline-size: 0;
  min-block-size: var(--control-height-md);
}

@media (max-width: 720px) {
  .form-row { grid-template-columns: minmax(0, 1fr); }
  .form-field[data-width] { max-inline-size: none; }
}
```

实际实现优先复用现有 Token，类名按所属表面调整；不得为复制示例引入 Tailwind。

#### 内容和操作节奏

- 一个表单 Section 回答一个问题，例如“如何参考资料”或“默认使用哪个文本服务”，不以底层对象名分组。
- 一屏/一步只有一个 Primary；删除同时出现“保存”“应用”“下一步”“完成”的多主动作竞争。
- 局部编辑 Dialog/Sheet 使用“取消 / 保存”或自动保存二选一，不同时混用隐式自动保存和必须点击保存而无说明。
- 条件字段紧跟触发选项出现；隐藏后必须明确是保留原值、清空还是不参与提交。
- Error 就近显示并进入 `aria-describedby`；顶部错误摘要只做跳转，不复制字段全文。
- ReadOnly 用文本/状态行展示；Disabled 控件必须给出不可用原因，不能仅降低透明度。
- Busy 锁定命令，不默认锁死所有可读内容；提交快照后会影响请求的字段必须一致锁定。

#### Uiverse 表单参考的采纳边界

用户提供的 `theMrsami` 表单适合用作排版节奏参考，但不是要复制的视觉模板：

- 采用：表单标题明确、字段纵向推进、语义并列字段等宽双列、主叙事字段全宽、操作收口在底部。
- 重写：颜色、圆角、间距、Label、Focus、Error、Dark/Light 和响应式全部使用本项目 Token 与语义。
- 删除：外层深色大 Card、无条件固定两列、将 AI 输出放在只读 Textarea、英文示例内容和 Tailwind 依赖。

### 9.10 全应用表单审查矩阵

Stepper 只用于首次跨域准备。以下日常表单按各自产物和写回目标选择 Section、Dialog 或 Sheet：

| 表单/模块 | 当前主要问题 | 目标形态 | 唯一写回与验收重点 |
| --- | --- | --- | --- |
| `InfoBriefEditor` | 书名、简介、世界观和人物入口层级不一 | Story Brief Section；叙事全宽、短字段成组 | 保留 `StoryBriefContract` 隐藏字段，不丢人物成长和下游约束 |
| `StageInputField` | 暴露 `field.key · field.type`，控件宽度随类型漂移 | 按 Writer Label/Description 渲染的 Schema Field | 内部 Key 仅诊断可见；枚举、数字、长文本使用宽度语义 |
| `StageInspector` | 基础决策和技术参数混排 | Artifact 摘要 + 必要字段 + “阶段例外”高级折叠 | 默认继承全局；例外有重置和受影响说明 |
| `ProviderEditor` | Profile、密钥、模型、操作同时铺开 | 摘要行 + Provider Manager Sheet | 密钥草稿保护；保存、检查连接、同步模型三命令分离 |
| `SettingsDialog` | 四 Tab 交叉、重复 Provider/模型/阶段表单 | `SettingsOverview` + 局部编辑 Section/Sheet | 字段唯一归属；自动保护只读状态化 |
| `ChapterBlueprintDialog` | 章节字段多且不同长度混排 | 章节施工 Section，按场景/目标/冲突/连续性分组 | 切章前草稿保护；稳定 Chapter/Scene ID |
| Detail 三类写回表单 | Wiki、人物、伏笔提案可能挤在同层 | 三个语义 Editor/Sheet，共用当前章上下文条 | 保存提案不等于接受 Canon；冲突决策保持显式 |
| Summary 结构编辑弹窗 | 幕、转折、人物弧可能依赖泛化字段 | 结构化行/轨道编辑器 | 保留数组稳定 ID 和顺序；不回退自由 Markdown |
| Outline Beat/人物/世界/伏笔编辑器 | 多类实体像通用 Card 表单 | 目标对象专用 Ledger/Sheet | 写回目标、受影响卷/章可见；切换对象不丢草稿 |
| Cover Brief | Prompt、构图、文案与 Provider 技术项混杂 | Brief 编辑区 + 候选生成参数高级区 | 文本 Brief 与图片候选来源分离；未启用图片服务明确阻塞 |
| Export Metadata | 元数据、格式和范围混在生成操作周围 | Metadata Section + 格式/范围 Ledger | 修改元数据使旧校验失效；生成快照冻结 |
| 换稿方向 Dialog | 建议和自定义方向易竞争 | 3 个阶段化建议 + 一个全宽自定义方向 | 选择方向不等于调用；确认生成才产生 Provider 请求 |

每个表单迁移前必须记录：Artifact、用户决策、字段主所有者、草稿状态、保存命令、正式写回、退出保护、错误来源、移动端重排和测试消费者。视觉统一不能以丢失隐藏字段或改变提交合同为代价。

### 9.11 用户指引与错误恢复

不引入覆盖式产品 Tour，也不在页面堆教程文案。指引嵌入真实任务：

- 步骤名说明目标，标题下只保留一句“该选择会影响什么”。
- 使用智能默认值和条件显示，减少不相关字段，而不是用说明解释为什么字段很多。
- 输入示例放 Placeholder 或短 Example，不能替代 Label。
- 必填阻塞发生在步骤边界；用户输入时不连续弹 Toast 打断。
- 可选步骤允许“暂不添加”，并说明系统将采用什么默认行为。
- 错误必须回答“发生了什么、当前内容是否保留、下一步能做什么”。
- 外部服务错误按鉴权、余额、模型、网络、结构化输出分类；保留服务端可诊断详情但普通界面先显示用户语言。
- 离开后恢复到上次位置；若字段已失效，优先定位最早阻塞项。
- 完成后提供配置摘要，后续只从 Overview 修改，不强制重播指引。
- Hover 只补充信息，任何唯一指引、错误和修复入口都必须可点击、可聚焦并在触屏可达。

## 10. 逐页面重构方案

### 10.1 Planning

| 合同 | 内容 |
| --- | --- |
| Artifact | Workflow 配置、Brief、Provider/模型、知识资料、质量策略 |
| 用户决策 | 是否具备启动条件、使用哪种工作方式 |
| 写回 | Workflow、Provider 引用、知识库选择、阶段参数 |
| 下游依赖 | Info Run 输入和全链路执行策略 |

桌面构图：

- Header 去掉阶段点阵。
- 尚未完成首次准备时，Planning 主工作面直接渲染 `GuidedSetupWorkbench`；Canvas 只以简短“后续创作链路”预览存在，不要求用户在流程和 Inspector 之间跳转。
- 首次准备完成后进入正常 Planning：顶部只保留紧凑配置摘要和“修改设置”，不再常驻五步 Stepper。
- 中央 Canvas 扩大，节点提高可读尺寸，删除 Canvas 顶部重复七阶段横条。
- 右侧 Inspector 从大框改为固定工具面：当前阶段 Artifact 摘要、必要字段和默认收起的“阶段例外”。
- 知识库状态从底部厚 Card 改为横向状态带，提供文档、片段、索引和管理入口。
- Canvas 空域只用于连线、阶段状态和定位，不填充无价值组件。

移动端构图：

- 不渲染缩小 Canvas。
- 首次准备使用单列 Guided Setup；步骤清单通过顶部进度按钮打开 Sheet。
- 使用 `MobileStageRail`：可横滑的 7 个阶段按钮或纵向步骤列表，当前项、状态和必填缺口可读。
- 点阶段打开全屏配置 Sheet。
- 首次流程完成后不再显示 `x/5`，只显示配置摘要/缺项；若配置失效，点击缺项回到对应步骤。
- 主动作固定在安全区上方，但不能遮挡表单最后一项。

### 10.2 Fast / Balanced Cockpit

| 合同 | 内容 |
| --- | --- |
| Artifact | 自动生产中的阶段产物快照 |
| 用户决策 | 观察、暂停/恢复（按模式）、打开只读详情 |
| 写回 | 不由 UI 观察动作触发 |
| 下游依赖 | SSE 当前阶段和最终产物 |

- 左侧使用单一阶段 Rail，替代 Header 总进度。
- 中间只展示当前 Artifact 流和最近有价值事件，不展示技术日志瀑布。
- 右侧按阶段动态切换 1-2 个观察模块，不常驻 Wiki/质量/人物/世界观全家桶。
- 当前阶段变化时 Rail 指示器平移、Artifact Panel Crossfade；不重播整个壳层。
- Fast 强调自动流动，Balanced 在 Info 后强调已放行和自动生产状态。

### 10.3 Settings / Knowledge

- Settings 删除“全局模型 / 模型接口 / 阶段覆盖 / 运行策略”四 Tab，改为第 7.8 节的单页 `SettingsOverview`。
- Overview 使用全宽 Section 和摘要行，不使用 Bento Dashboard；每区只展示当前值、健康/缺项和一个“修改/管理”动作。
- Provider 编辑器改为摘要行 + `ProviderManagerSheet`；默认只显示名称、类型、模板、默认模型、密钥状态和最近连接检查。
- 所有 Provider/Model 使用统一 `OptionField`，但 Provider Profile 的编辑生命周期仍由现有 Settings 状态和服务函数负责。
- API Key、Base URL、同步模型、检查连接和保存按真实操作顺序排列；Busy 互斥，失败不清空输入。
- 默认模型只在 AI 服务区编辑一次；`StageInspector` 默认显示继承结果，只有展开“阶段例外”后才允许修改。
- 只读运行策略改名“自动保护”，使用状态行显示自动保存、运行前检查和封面资产校验，不显示假 Checkbox。
- Knowledge 使用上传队列、资料表和右侧详情，不用大 Dropzone 动画占首屏；首次流程的参考步骤复用同一 Knowledge 状态和命令，不维护第二份上传列表。

#### Settings Overview 页面细化

| Section | 默认摘要 | 局部编辑入口 | 不得出现 |
| --- | --- | --- | --- |
| 创作设定 | 题材、篇幅、读者、核心创意一行摘要 | 打开 Brief Section | Provider、阶段参数 |
| 参考与资料 | 联网开关、可用资料数、失败数、最近索引 | 打开 Knowledge 管理 | Chunk/Embedding 原始对象 |
| 创作方式 | 模式、人工作业节点、版本对比状态 | 打开模式/输出偏好 Section | 七个重复确认开关 |
| AI 服务与默认模型 | 文本/封面服务、模型、Ready/Warning | 打开 Provider Manager | API Key 明文、七阶段模型列表 |
| 输出偏好 | 章节长度、分卷偏好、导出格式 | 打开 Output Section | 与 Export 当前选择重复的临时状态 |
| 高级阶段例外 | 例外数量和阶段名 | 定位对应 Stage Inspector / 全部恢复默认 | 默认展开七阶段技术表单 |
| 自动保护 | 三项系统能力的已启用/异常状态 | 查看说明/诊断 | Checkbox、Switch、可点击假状态 |

Settings 在桌面可使用宽 Dialog 或独立产品 Surface，但内容必须有单一滚动所有者；390px 使用全屏 Sheet。局部编辑关闭后返回原 Section 和触发按钮，保存状态、错误和 Dirty Guard 不得因 Overview 重构丢失。

### 10.4 Info

| 合同 | 内容 |
| --- | --- |
| Artifact | Story Brief |
| 用户决策 | 项目方向是否成立 |
| 写回 | 世界观、人物、关系、约束 |
| 下游依赖 | Summary 的故事主干输入 |

- 保留书名、简介、世界观、人物 Ledger 的主线。
- 书名候选使用轻量 Choice Chips，不做发光 Card。
- 简介是最大编辑区；人物和世界观进入专用编辑 Overlay。
- 右侧只保留草稿派生的世界/关系摘要，确认前明确“当前稿预览”。
- 首次真实生成可用模式色 Loading Overlay；完成后主区整体淡入一次，不逐字播放。
- 换稿候选使用静态 BorderGlow 表达当前选择，未选列保持中性。

### 10.5 Summary

| 合同 | 内容 |
| --- | --- |
| Artifact | 全书梗概、幕结构、转折、人物弧 |
| 用户决策 | 故事主线和结局是否成立 |
| 写回 | Memory、Story Bible、人物弧、连续性摘要 |
| 下游依赖 | Outline 分卷和节拍 |

- 主稿纸继续占最大宽度，减弱外围大框。
- 幕结构用紧凑轨道，关键转折用顺序 Ledger，不堆独立 Card。
- 人物关系支撑区默认收起为窄 Rail，点击展开详情 Sheet。
- 稿纸流式内容按句/短行淡入，不对每段包容器。
- 编辑、质量和人物入口使用 Sticky 工具条，滚动时不覆盖正文。

### 10.6 Outline

- 保持分卷 Rail + Rhythm + 五 Beat Board。
- 卷行 Hover 只突出整行和关联节拍，不抬升。
- 当前卷用模式色左边线和静态 BorderGlow；完成卷用 Check，不循环发光。
- 横向 Beat Board 在 1024px 以下变为可滚动表格，在 720px 以下按当前卷单列分段，不变成五张卡片。
- 人物、世界和伏笔依赖从主板进入专用 Sheet/Popover，保存后只高亮对应单元格一次。

### 10.7 Detail

| 合同 | 内容 |
| --- | --- |
| Artifact | 章节施工表、事实/Wiki、伏笔、人物变化 |
| 用户决策 | 每章是否可执行并可交给正文 |
| 写回 | 章节蓝图、事实提案、关系变化、伏笔账本 |
| 下游依赖 | Text 章节上下文包 |

Detail 必须具备专属 Sidebar：

- 左侧 `DetailChapterSidebar`：章节分组、Ready 状态、POV、冲突/缺项提示；宽 248-280px，可折叠到 48px。
- 中间 `DetailConstructionTable`：最大工作面，Sticky 表头和当前章行。
- 右侧按需 `DetailContextInspector`：当前章人物、事实、伏笔、世界锚点；默认 300-340px，可关闭。
- 三栏不嵌套 Card，侧栏以分区和行组织。
- 点击施工表单元格只定位对应编辑器，不触发生成。
- 移动端使用章节选择条 + 单章施工表 + 底部 Context Sheet，不并排三栏。

### 10.8 Text

| 合同 | 内容 |
| --- | --- |
| Artifact | 章节正文、修订、质量结论、写回提案 |
| 用户决策 | 当前章/阶段是否定稿 |
| 写回 | 正文版本、摘要、Wiki、人物状态 |
| 下游依赖 | 下一章、Cover 和 Export |

Text 必须具备专属 Sidebars：

- 左侧 `WritingChapterSidebar`：章节树、字数、版本、当前状态；可折叠到图标 Rail。
- 中间 `WritingManuscriptSurface`：正文始终最大，阅读宽度 680-820px，背景和行高按长时间写作优化。
- 右侧 `WritingReviewSidebar`：质量审校/事实写回两个 Tab；只显示当前章相关 Finding 和 Proposal。
- 人物/世界观为右侧底部详情入口，不常驻再增加第四栏。
- 提供“写作 / 审校 / 专注”三种视图密度，使用 Segmented Control；切换只改变布局，不改变 Artifact。
- 专注模式收起两侧栏和 Header 次要工具，Esc 恢复；不使用全屏渐变背景。
- 流式生成时只对新增句子淡入，用户上滚后停止自动跟随。
- 移动端默认正文单栏，章节和审校分别使用全屏 Sheet；底部仅保留当前章和审校入口。

### 10.9 Cover

- 桌面使用候选 Rail/三列候选 + 中央预览 + 简报 Inspector，按当前状态决定，不同时铺满所有区。
- 候选图片容器固定比例，Decode 完成后 Crossfade。
- 缺图状态缩减装饰面积，显示失败原因、重试和 Provider 来源。
- 选中候选使用静态 BorderGlow；Hover 只显示操作工具，不改变图片比例。
- 移动端单候选分页，提供上一张/下一张、页码和明确“设为当前稿”；不自动轮播。

### 10.10 Export

- 左侧交付范围使用章节 Ledger，不做卡片列表。
- 中间交付包使用文件表、Receipt 和版本差异；生成新版本是唯一主动作。
- 右侧校验使用顺序状态轨，不用三个独立统计 Card。
- 当前选择与旧版本 Receipt 使用明显分区和源快照标识。
- 生成期间锁定所有影响选择的控件，进度只消费真实服务端状态。

### 10.11 History / Recovery

- 桌面为 360-420px 历史列表 + 自适应详情，不再使用全屏点阵背景。
- 列表按项目、状态、日期分组；当前 Run、可恢复、已完成、失败具有稳定状态语法。
- 详情顶部优先显示“继续工作 / 恢复快照 / 打开产物”，统计数字下移。
- Export 版本使用时间线/版本表，哈希和源快照可展开。
- 恢复确认层明确将回到哪个稳定点、会保留什么、不会触发什么。
- 移动端先列表后详情，返回保持滚动位置和筛选条件。

## 11. 动效系统增量

### 11.1 Token

沿用现有 `motion.ts`，新增语义别名而非第二套数值：

| 语义 | 时间 | 属性 |
| --- | --- | --- |
| `controlFeedback` | 100-120ms | Color/Background/Border |
| `selectionMove` | 180ms | Transform/Opacity |
| `panelEnter` | 200-220ms | Opacity + 3-8px |
| `sheetEnter` | 220ms | X 24px 或 Y 16px |
| `modeTransition` | 480-620ms | 遮罩 Transform/Opacity |
| `statusHighlight` | 240ms 一次 | Border/Background |
| `spinner` | 900ms | Rotate Linear |

### 11.2 进入与退出

- 页面路由：稳定 Header 不动，主工作区退出 100-120ms、进入 180-220ms。
- Sidebars：折叠只动画宽度容器的一次 Layout，内部内容延迟淡入；主稿件最小宽度先锁定。
- Dialog/Sheet：继续使用现有 Overlay 生命周期，不复制 React Bits/Aceternity 的 Body Lock。
- Tabs：Indicator 与 Panel 分离，Panel 不等待 Indicator 完成。
- Grid：只对首次真实数据 Ready 的可见项做最多 4 项、25ms Stagger；长列表不 Stagger。
- 状态写回：对应行/字段短暂高亮一次，然后回到稳定状态。

### 11.3 静态动效

允许：

- 当前模式的静态边缘色。
- 当前 Canvas 节点的轻量内描边。
- Ready 主动作的非循环微光。
- 空态图标的静态线性纹理。

禁止：

- Aurora、Starfield、Meteor、Orb、Galaxy、粒子背景。
- 卡片持续呼吸、背景位置无限移动、边框无限跑光。
- 非运行状态的 Spinner、ECG、频谱条和光标。
- 大面积 `filter: blur()`、`backdrop-filter` 或 `box-shadow` 逐帧动画。

## 12. 响应式策略

| 视口 | 壳层 | 主工作台 | Overlay |
| --- | --- | --- | --- |
| >= 1440 | 隐式 Rail + 单行 Header | 2-3 栏，主 Artifact 优先 | 居中 Dialog / 侧 Sheet |
| 1180-1439 | 单行或紧凑 Header | 2 栏，次侧栏按需 | 侧 Sheet |
| 768-1179 | 工具收纳，模式控件压缩 | 主 Artifact + 抽屉 Inspector | 全高 Sheet |
| 390-767 | 三段紧凑 Header 或底部工具 | 单栏，阶段/章节使用选择条 | 全屏 Sheet / Bottom Sheet |
| 320-389 | 品牌只留标记 | 单栏，文本动态换行 | 全屏 Sheet，44px 操作 |

关键规则：

- Mobile Canvas 改语义 Rail，不缩放桌面节点。
- Detail/Text 的侧栏在 1024px 以下逐步转 Sheet，不压缩稿纸到不可读。
- 长词、Provider 名和模型 ID 可换行或省略并提供 Tooltip，不缩放字体适配。
- Sticky Header、Finalize Tray 和 Bottom Sheet 同时存在时必须使用 Safe Area 和明确的滚动所有权。
- 浏览器 200% Zoom 时按布局断点重排，不能依靠横向页面滚动维持三栏。

## 13. 文件落点与实施边界

### 13.1 新增候选文件

```text
apps/web/src/features/pipeline/
  layout/
    ProductNavigationRail.tsx
    GlobalToolDock.tsx
    ThemeModeSwitch.tsx
    QualityModeTransitionOverlay.tsx
    PanelTransition.tsx
  planning/
    GuidedSetupWorkbench.tsx
    SetupStepNavigation.tsx
    StorySetupSection.tsx
    ReferenceSetupSection.tsx
    CreationModeSetupSection.tsx
    SetupReviewSection.tsx
    MobileStageRail.tsx
  settings/
    SettingsOverview.tsx
    AiServiceSetupSection.tsx
    ProviderManagerSheet.tsx
    fields/
      OptionField.tsx
  running/
    DetailChapterSidebar.tsx
    DetailContextInspector.tsx
    WritingChapterSidebar.tsx
    WritingReviewSidebar.tsx
  state/
    useSetupFlow.ts
    useQualityModeTransition.ts
  contracts/
    setup.ts
  lib/
    optionCollection.ts
    setupProgress.ts
```

名称是实施目标，不要求一次全部创建。`GuidedSetupWorkbench` 只负责步骤编排，四个业务 Section 分别消费现有状态；Provider 配置仍归 `settings/` 所有，Planning 只组合 `AiServiceSetupSection`。不得新增 `components/`、`screens/`、`dialogs/` 或第二套顶层目录。优先演进已有 `DetailChapterLedger`、`WritingChapterNav`、`WritingQualityInspector`，只有责任确实改变时才改名或拆文件。

### 13.2 现有文件主要变更

| 文件 | 计划变更 |
| --- | --- |
| `AppHeader.tsx` | 移除七阶段/ECG 消费；装配导航触发器、CurrentRunStatus、Tool Dock 和主动作 |
| `StageProgressNavigator.tsx` | 拆解配置/运行派生逻辑，迁移后决定删除或收敛为纯状态组件 |
| `CreationActionDock.tsx` | 只保留模式和主动作；全局工具迁出 |
| `PlanningWorkbench.tsx` | 根据真实准备度装配首次 Guided Setup 或完成后的 Canvas；桌面 Canvas/Inspector 与移动 Rail/Sheet 分支 |
| `PipelineCanvas.tsx` | 删除顶部重复阶段条，增强节点可读性和唯一进度语义 |
| `SettingsDialog.tsx` | 从四 Tab 容器收敛为 Settings Overview 壳层；保留焦点恢复、Dirty Guard 和 Provider 状态所有者 |
| `ProviderTemplateSelect.tsx` | 使用 Provider Option Combobox |
| `ProviderCreateControl.tsx` | 使用 Provider Option Combobox |
| `ModelOptionInput.tsx` | 搜索、分组、自定义模型明确提交 |
| `ProviderEditor.tsx` | 摘要与编辑责任拆分；保存、检查连接、同步模型命令语义化 |
| `StageInspector.tsx` | 默认只显示继承摘要；技术参数进入“阶段例外”高级区，隐藏内部 ID/Key |
| `StageInputField.tsx` | 移除普通界面的 `field.key · field.type`；接入宽度、错误和帮助文本合同 |
| `InfoBriefEditor.tsx` | 按 Story Brief 语义重排字段，保持完整 Contract 写回 |
| `ChapterBlueprintDialog.tsx` | 应用章节施工表单分组和草稿保护，不改变章节写回合同 |
| `DetailStageView.tsx` | 三栏 Sidebar/主表/Context 责任装配 |
| `WritingStageView.tsx` | 章节 Sidebar、稿纸和审校 Sidebar 装配 |
| `motion.ts` | 添加模式遮罩和侧栏语义 Variant，不复制时长体系 |
| `visualEffects.tsx` | 逐消费者退出 Ambient/Starfield，保留仍有业务价值的隔离实现或最终删除 |

### 13.3 样式所有权

新增样式建议：

- `product-navigation.css`
- `option-fields.css`
- `global-tool-dock.css`
- `quality-mode-transition.css`
- `guided-setup.css`
- `settings-overview.css`
- `form-layout.css`（只有跨表面 Token/几何规则；业务字段样式仍归所属表面）

阶段布局继续进入现有阶段专属样式，不新建 `cards.css`、`effects.css` 或 `reactbits.css` 等无业务归属文件。

每个实施切片都要登记：

- 新选择器所有者。
- 被替代的旧选择器。
- 响应式断点。
- Reduced Motion 分支。
- 删除旧规则的验证截图和消费者搜索证据。

### 13.4 共享组件代码合同

#### ProductNavigationRail

```ts
type ProductNavigationItem = {
  id: 'planning' | 'running' | 'knowledge' | 'history' | 'settings';
  label: string;
  icon: LucideIcon;
  disabled?: boolean;
  disabledReason?: string;
  badge?: string;
};

type ProductNavigationRailProps = {
  open: boolean;
  activeItem: ProductNavigationItem['id'];
  items: ProductNavigationItem[];
  qualityMode: QualityMode;
  onOpenChange: (open: boolean) => void;
  onNavigate: (item: ProductNavigationItem) => void;
};
```

状态所有权：

- `open` 可由 App Shell 控制，但 Rail 不拥有路由。
- `onNavigate` 必须进入现有 Dirty/Busy 路由保护；Rail 不直接调用 `navigate()` 绕过保护。
- Disabled 原因来自 Run/权限派生，不在组件内猜测。
- 打开动画只消费 `open`，不通过动画回调触发导航。

#### GuidedSetupWorkbench / SetupStepNavigation

```ts
type SetupStepId = 'story' | 'references' | 'creation-mode' | 'ai-service' | 'review';

type SetupIssue = {
  code: string;
  severity: 'blocking' | 'warning';
  label: string;
  target: { stepId: SetupStepId; fieldId?: string };
};

type SetupStep = {
  id: SetupStepId;
  label: string;
  status: 'complete' | 'current' | 'blocked' | 'pending';
  summary?: string;
  issues: SetupIssue[];
};

type SetupFlowState = {
  activeStepId: SetupStepId;
  direction: 'forward' | 'backward' | 'none';
  submitState: 'idle' | 'validating' | 'creating-run' | 'failed';
  lastFocusedFieldId?: string;
};

type GuidedSetupWorkbenchProps = {
  steps: SetupStep[];
  flow: SetupFlowState;
  onStepRequest: (stepId: SetupStepId) => void;
  onBack: () => void;
  onContinue: () => void;
  onSaveAndExit: () => void;
  onStart: () => Promise<void>;
};
```

派生函数必须是纯函数：

```ts
function buildSetupSteps(input: {
  workflow: WorkflowDefinition;
  knowledgeDocuments: KnowledgeDocument[];
  readiness?: ProviderReadinessReport;
}): SetupStep[];

function firstBlockingSetupTarget(steps: SetupStep[]): SetupIssue['target'] | null;

function shouldShowGuidedSetup(steps: SetupStep[]): boolean;
```

- `useSetupFlow` 只拥有活动步骤、方向、焦点恢复和提交 UI 状态；它不复制 Workflow 字段、Knowledge 列表、Provider Profile 或 Readiness。
- `lastVisitedSetupStepId` 可以进入现有本地 UI 持久化，但步骤完成度每次从真实业务状态重算。
- `onStepRequest` 不得把步骤直接改为 Complete，也不得触发 Provider 测试或 Run 创建。
- `onStart` 必须先使用当前派生结果做最终校验，再调用现有 Run 创建命令；动画完成回调不能调用它。
- `shouldShowGuidedSetup` 的命名应表达“是否仍需引导”，不把已经存在但暂时失败的 Provider 误判为从未配置。

#### SettingsOverview

```ts
type SettingsSectionId =
  | 'story'
  | 'references'
  | 'creation-mode'
  | 'ai-service'
  | 'output'
  | 'stage-exceptions'
  | 'automatic-protection';

type SettingsSectionSummary = {
  id: SettingsSectionId;
  title: string;
  summary: string[];
  status: 'ready' | 'warning' | 'blocked' | 'informational';
  action?: { label: string; target: string };
};

type SettingsOverviewProps = {
  sections: SettingsSectionSummary[];
  activeEditorId: Exclude<SettingsSectionId, 'automatic-protection'> | null;
  onEditRequest: (sectionId: SettingsSectionId) => void;
  onEditorClose: () => void;
  onResetStageExceptions: () => void;
};
```

- Section 摘要由纯 Selector 生成，不能在 View 中重新解释 Workflow 继承规则。
- `automatic-protection` 没有编辑动作；异常时只提供诊断入口。
- `stage-exceptions` 的重置必须经过确认，并复用现有 Workflow 更新函数，不在 Overview 内直接改嵌套字段。
- 局部编辑器保持受控草稿；关闭、Escape、Backdrop 和切 Section 都走 Dirty Guard。

#### Form field geometry

表单几何优先作为稳定 DOM/CSS 合同落在各业务组件中，不急于创建一个接管所有输入类型的万能 `FormField`。如果实施中确认 Label、Description、Error、Status 在三处以上稳定重复，再提取只负责结构与可访问关联的轻量组件；它不得拥有校验、保存、格式转换或 Provider 命令。

#### PanelTransition

```ts
type PanelTransitionProps = {
  transitionKey: string;
  children: ReactNode;
  direction?: 'forward' | 'backward' | 'none';
  preserveLayout?: boolean;
  className?: string;
};
```

推荐实现边界：

```tsx
<AnimatePresence initial={false} mode="popLayout">
  <motion.div
    key={transitionKey}
    variants={panelMotionVariants(direction)}
    initial="initial"
    animate="animate"
    exit="exit"
  >
    {children}
  </motion.div>
</AnimatePresence>
```

- `transitionKey` 只描述可视内容身份，不使用 `Date.now()` 强制重播。
- 表单 Panel 需要保留草稿时，动画包裹稳定 Panel 容器，而不是通过 Key 重挂载表单。
- Reduced Motion 由全局 Provider 和 `motionTransitionFor` 同时兜底。

#### QualityModeTransitionOverlay

```ts
type QualityModeTransitionOverlayProps = {
  transition: ModeTransitionState | null;
  reducedMotion: boolean;
  onVisualComplete: (requestId: number) => void;
};
```

调用顺序：

```text
用户选择目标模式
  -> canSwitchMode 校验
  -> 更新受控 quality_mode
  -> 创建唯一 visual requestId
  -> Overlay 消费 from/to 渲染
  -> onVisualComplete 只清理视觉状态
```

`onVisualComplete` 不允许保存 Workflow、导航、创建 Run、重连 SSE 或显示伪成功。Workflow 自动保存继续由现有 Autosave 所有者消费真实状态变更。

#### ModeSpinner

```ts
type ModeSpinnerProps = {
  size?: 'sm' | 'md' | 'lg';
  label: string;
  decorative?: boolean;
};
```

- 非装饰 Spinner 使用 `role="status"`，可见文本可由调用方决定是否视觉隐藏。
- 按钮自身已有 `aria-busy` 时，内部 Spinner 设为装饰，避免重复播报。
- Spinner 不拥有 Timer；卸载完全由真实 Busy 状态决定。

### 13.5 Token 增量建议

```css
:root {
  --option-popup-min-width: 280px;
  --option-popup-max-width: 420px;
  --option-popup-max-height: 360px;
  --navigation-rail-width: 304px;
  --detail-sidebar-width: 264px;
  --review-sidebar-width: 320px;
  --manuscript-readable-width: 760px;
  --control-focus-ring-width: 2px;
  --control-focus-ring-offset: 2px;
}

.mode-fast {
  --mode-accent: var(--mode-fast-accent);
  --mode-accent-2: var(--mode-fast-accent-strong);
}

.mode-balanced {
  --mode-accent: var(--mode-balanced-accent);
  --mode-accent-2: var(--mode-balanced-accent-strong);
}

.mode-deep {
  --mode-accent: var(--mode-deep-accent);
  --mode-accent-2: var(--mode-deep-accent-strong);
}
```

实际变量名必须先对照 `design-tokens.css`，优先扩展现有 Token，不能复制一套 `fast/balanced/deep` 色板。尺寸 Token 用于稳定几何，不要求所有页面机械取同一宽度。

## 14. 依赖策略

### 14.1 默认不新增

以下能力使用现有依赖完成：

- Navigation Rail、Dock、Mode Overlay、Panel Transition：`motion`。
- Dialog、Tabs、Tooltip、Switch、短 Select：Radix。
- 图标：Lucide。
- Grid、Input、Checkbox、Spinner：CSS + 原生语义。

### 14.2 可评估新增

`@base-ui/react` 只为长列表 Combobox 进入 Phase 9.2 技术验证。验证必须覆盖：

- 中文 IME。
- Keyboard、Screen Reader、Touch。
- Portal/Collision/Scroll Lock 与现有 Radix Dialog 嵌套。
- 390px 软键盘和 Bottom Sheet。
- Bundle 增量和 Tree Shaking。
- Controlled Value、Async Options、Custom Model。

若验证失败，使用 Radix Select + 本地搜索 Popover 或 Ariakit 专项方案；不得手写不完整的 ARIA Combobox。

### 14.3 明确不新增

- GSAP/ScrollTrigger：现有 Motion 足以承担本轮状态过渡。
- Anime.js：没有必须的复杂时间线场景。
- Tailwind：项目当前使用普通 CSS，不能为复制组件引入第二套样式架构。
- 大型 UI Kit：不能为 Option 一个问题引入整套视觉系统。

## 15. 分阶段实施计划

### Phase 9.0：基线和决策冻结

目标：冻结页面状态、请求边界和视觉基线。

实施：

- 保存 Planning、Settings Option、Info、Summary、Outline、Detail、Text、Cover、Export、History 的桌面/移动截图。
- 记录 Header 高度、Canvas 可读性、侧栏宽度、滚动所有者和页面动画数量。
- 为所有原生 `select`、Checkbox、Switch、Tooltip、Loading 建立迁移清单。
- 冻结 Phase 8.8 未完成真实 Provider 验收状态，避免 UI 工作误报全链路通过。

退出：文档、截图、请求基线、CSS 审计和状态矩阵齐全。

冻结报告：[`phase-9-0-baseline-and-decision-freeze.md`](./phase-9-0-baseline-and-decision-freeze.md)。Phase 9.0 已于 2026-07-24 完成，后续实施必须以该报告的 Artifact、请求、几何、滚动和 Phase 8.8 独立状态为对照。

### Phase 9.1：配置语义、字段归属与双态设置

目标：先消除四 Tab 交叉、重复配置和工程术语泄漏，再开始视觉替换。

实施：

- 建立字段唯一归属矩阵，并为现有 Workflow/Knowledge/Provider 字段标记唯一编辑入口和只读消费者。
- 冻结普通界面术语，完成“AI 服务、默认生成模型、阶段例外、自动保护”等命名映射。
- 实现 `buildSetupSteps` 的纯派生合同、`useSetupFlow` 的 UI 状态边界和首次/后续状态选择规则。
- 建立 `GuidedSetupWorkbench` 五步骨架和 `SettingsOverview` Section 骨架，先复用现有字段和命令，不复制状态。
- 删除四 Tab 信息架构；Provider Manager 作为 AI 服务局部编辑入口，阶段例外回归 Stage Inspector。
- 将只读运行策略从 Checkbox 改为状态摘要；内部 ID/Key 默认隐藏。

退出：同一个配置值只有一个主编辑入口；首次用户能按五步完成启动准备；再次进入直接看到单页摘要；旧 Workflow、Autosave、Dirty Guard、Provider 生命周期和 Demo/Mock 行为保持不变。

### Phase 9.2：统一 Option 系统

目标：解决用户截图一的长列表位置和选择效率问题。

实施：

- 完成 `OptionField` / `OptionCombobox` 技术验证。
- 迁移服务模板、默认 Provider、模型列表和 Stage Inspector 的阶段例外选项。
- 补搜索、分组、Meta、Empty、Error、Disabled、Custom Model。
- 完成 Portal、Collision、Keyboard、IME 和移动 Sheet。

退出：28+ Provider 在桌面和 390px 可搜索、可选择、无溢出；所有旧值、保存、删除保护和模型发现行为不变。Phase 9.2 已于 2026-07-24 完成，详见 [`phase-9-2-option-system.md`](./phase-9-2-option-system.md)。

### Phase 9.3：产品导航、Header 与 Tool Dock

目标：建立多页面产品壳层并删除顶部重复阶段进度。

实施：

- 接入隐式 Navigation Rail。
- Header 移除七阶段/ECG，保留页面身份、状态、工具和主动作。
- 全局工具迁入 Dock，主题 Switch 完成。
- Planning/Cockpit/Deep 页面验证路由和焦点恢复。

退出：Header 高度稳定、无第二套阶段链路、Dirty/Busy/恢复路径不变、移动端首屏明显释放。

### Phase 9.4：Planning 唯一进度与模式遮罩

目标：解决用户截图二并恢复三档模式沉浸切换。

实施：

- 删除 Canvas 顶部重复七阶段横条。
- 中央节点成为桌面唯一阶段进度源。
- 移动端改 Stage Rail。
- 首次准备显示 Guided Setup；准备完成后只保留紧凑摘要，不常驻第二套 Stepper。
- 接入 Quality Mode Transition Overlay。

退出：模式动画无网络副作用；Reduced Motion 即时；桌面/移动端都能准确判断当前阶段与下一配置缺项。Phase 9.4 已于 2026-07-24 完成，详见 [`phase-9-4-planning-progress-and-mode-transition.md`](./phase-9-4-planning-progress-and-mode-transition.md)。

### Phase 9.5：表单系统、基础控件和内容过渡

目标：统一表单几何、语义、错误恢复和 Input、Button、Switch、Checkbox、Tooltip、Loader、Tabs、Panel 状态。

实施：

- 先迁移 Guided Setup 和 Settings Overview，验证 Short/Medium/Full、双列/单列和移动端 Form Layout Contract。
- 按第 9.10 节矩阵逐个审查 `InfoBriefEditor`、`StageInputField`、`StageInspector`、Provider、Chapter Blueprint、阶段写回、Cover 和 Export 表单。
- 按状态合同逐类迁移，不做全仓机械替换。
- 建立 Mode Spinner、Theme Switch、Control Switch、Checkbox 和 PanelTransition。
- 清除原样霓虹、持续 Glow、假 Checkbox 和大 Spinner。

退出：同一行控件等宽等高，长/短字段按语义布局；Focus、Busy、Error、ReadOnly、Disabled 清晰；错误可定位、草稿可恢复、没有布局位移、Reduced Motion 完整。首次 Guided Setup 的表单几何与进度反馈已完成 Phase 9.5A，详见 [`phase-9-5a-guided-setup-form-system.md`](./phase-9-5a-guided-setup-form-system.md)。Settings、Provider 与 Planning Stage Config 已完成 Phase 9.5B，详见 [`phase-9-5b-settings-and-stage-form-system.md`](./phase-9-5b-settings-and-stage-form-system.md)。Summary / Outline 运行期表单已完成 Phase 9.5C-1，详见 [`phase-9-5c1-summary-outline-runtime-form-system.md`](./phase-9-5c1-summary-outline-runtime-form-system.md)；Detail 章节施工与三类写回表单已完成 Phase 9.5C-2，详见 [`phase-9-5c2-detail-runtime-form-system.md`](./phase-9-5c2-detail-runtime-form-system.md)；Text 正文编辑、审校、局部修订、恢复与写回提案闭环已完成 Phase 9.5C-3，详见 [`phase-9-5c3-text-runtime-form-system.md`](./phase-9-5c3-text-runtime-form-system.md)。Cover、Export 继续按 Phase 9.5C 退出门禁逐批验收。

### Phase 9.6：Planning、Cockpit、Settings、Knowledge 布局

目标：收口配置和自动生产表面。

实施：

- Planning 空间重新分配。
- Cockpit 动态观察模块。
- Settings Overview 摘要行、局部编辑 Sheet 与 Provider Manager。
- Knowledge 队列/资料表/详情布局。

退出：没有为了填空而展示运行态内容；键盘和触屏可完成完整配置与观察。

### Phase 9.7：Info、Summary、Outline 差异化精修

目标：在不改 Artifact 的前提下，强化 Story Brief、稿纸和 Beat Board 的独特构图。

实施：

- 减少外围框线和重复信息。
- 统一候选 BorderGlow、局部 Fade 和 Sticky 工具。
- 调整右侧支撑区默认权重。

退出：三个阶段一眼可区分，且各自主要决策、缺项和写回预览清楚。

### Phase 9.8：Detail / Text 专属 Sidebars

目标：完成章节施工和长时间写作的专业工作台。

实施：

- Detail 章节 Sidebar、施工表、Context Inspector。
- Text 章节 Sidebar、最大稿纸、Review Sidebar、专注模式。
- 1024/768/390 的折叠与 Sheet 策略。

退出：桌面主 Artifact 不被挤压；移动端不并排缩放；切章、草稿、Finding、Proposal 和焦点全部保持。

Text 专属写作/审校双任务布局、专注模式与移动端章节/审校 Sheet 已在 Phase 9.5C-3 先行完成并通过 1280/1440/1728/390 验收。Phase 9.8 后续只继续评估 Detail 专属 Sidebar 的收口，不重复重构 Text，也不得改变既有修订、复检、提案和 Canon 合同。

### Phase 9.9：Cover、Export、History、Recovery

目标：统一资产选择、交付和恢复页面的状态层级。

实施：

- Cover 候选选择和移动分页。
- Export Ledger、Receipt、校验轨。
- History 列表/详情/版本时间线。
- Recovery 主动作和风险说明。

退出：资产、版本、快照和下载关联不变；动画不触发恢复或生成。

### Phase 9.10：全链路验收

目标：证明大规模 UI 重构没有改变业务事实。

必须覆盖：

- Fast、Balanced、Deep 的 Demo/Mock 完整路径。
- Phase 8.8 可用真实 Provider 后的真实路径。
- Provider Option 搜索与保存。
- 首次五步配置的退出/恢复/跳过/阻塞/启动和后续 Settings Overview 修改路径。
- 字段唯一归属、阶段继承/例外、Provider 管理和全应用表单矩阵。
- 模式快速连续切换和锁定状态。
- Dirty、Busy、Error、Recovery、History、Export。
- Dark/Light、Reduced Motion、Keyboard、Touch、200% Zoom。
- 320、390、768、1024、1180、1280、1440、1728。

退出：自动化、构建、浏览器、视觉、性能、可访问性和网络副作用门禁全部通过。

## 16. 人工页面评审门禁

每个阶段完成后必须由人工回答以下问题，不能只看截图“更好看”：

### 16.1 内容价值

- 首屏最大的内容是否就是当前 Artifact？
- 用户现在必须做的决策是否明确？
- 每个支撑模块是否会改变用户判断？如果不会，是否应收起或移除？
- 是否出现重复标题、重复状态、重复阶段导航或教程式说明？
- 空态是否说明缺什么和下一动作，而不是用装饰填空？

### 16.2 交互真实性

- Hover、Tab、Sheet、模式遮罩是否只改变展示？
- Busy/Success/Error 是否来自真实命令和响应？
- 切换对象、章节、路由和关闭 Overlay 是否保护草稿？
- 当前稿、候选、正式写回和历史版本是否没有混淆？

### 16.3 视觉层级

- 页面是否存在超过一个抢夺注意力的主色区域？
- 是否出现 Card 套 Card、同规格面板墙或无意义 Bento？
- Glow 是否只在当前选择和关键动作出现？
- 长时间阅读区域是否舒适、安静、稳定？

### 16.4 可用性

- Keyboard 是否有等价路径？
- Touch 是否存在非 Hover 入口？
- 200% Zoom 和 390px 是否重排而非压缩？
- Focus、选中、禁用、只读和错误是否无需颜色也能区分？

## 17. 自动化和验收门槛

### 17.1 单元/组件测试

- Option 自动选择 Select/Combobox 的阈值。
- 搜索、分组、中文 IME、Custom Value、Disabled。
- Mode Transition 连续点击、锁定、Reduced Motion。
- Guided Setup 真实完成度、步骤恢复、跳过、错误定位和最终启动快照。
- Settings Overview 摘要派生、局部编辑、阶段例外计数/重置和 Dirty Guard。
- Form Layout 的双列/单列、错误关联、状态稳定性和内部字段隐藏。
- Navigation Dirty Guard 和 Focus Return。
- Sidebar 折叠不改变当前章节/Artifact。
- Tab/Panel 切换不重置草稿。

### 17.2 浏览器验收

- Screenshot + DOM 几何：Header、Popup、Sheet、Sidebars、稿纸、Finalize Tray 无重叠。
- `scrollWidth === clientWidth`：页面级无横向溢出。
- Console：0 Error / 0 Warning。
- Network：纯 UI 操作不新增 `/runs`、`/resume`、Provider、SSE 或写回请求。
- Focus：打开/关闭 Navigation、Dialog、Sheet、Combobox 后焦点合理恢复。
- Animation：空闲 Infinite 0；真实运行最多 3 个必要循环。

### 17.3 性能预算

- 首次交互反馈 < 100ms。
- Option Popup < 150ms 可操作。
- Dialog/Sheet < 250ms 可操作。
- Mode Overlay 总时长 <= 620ms，新页面不等待遮罩才挂载。
- CLS = 0；动画 Long Task = 0；目标帧耗时 <= 16.7ms。
- 新依赖 Gzip 增量需记录；Combobox 方案超出约定预算时回到技术评审。

## 18. 后续实施 Prompt 库

以下 Prompt 必须与阶段合同、当前源码和测试一起使用，不能脱离仓库直接生成组件。

### Prompt 01：隐式产品导航

```text
在 Yotsuba Ink 中实现 ProductNavigationRail，借鉴 React Bits StaggeredMenu 的分层展开和短 Stagger，但不要复制营销式全屏菜单。

目标：建立产品级隐式导航，只包含 Planning、当前运行、知识资料、创作历史、设置；七个创作阶段不得进入侧栏。

工程约束：
- 放入 features/pipeline/layout/，不新增 components 目录。
- 使用现有 motion、Radix Overlay/焦点能力和 Lucide。
- 桌面宽 288-320px，移动端全屏 Sheet。
- 菜单总入场不超过 260ms，Reduced Motion 为 0s/none。
- Dirty/Busy 继续走现有路由保护。
- 打开、Hover、关闭不得发出业务请求。

验收：Keyboard、Escape、Backdrop、Focus Return、Touch、320/390/1440、Dark/Light、无横向溢出。
```

### Prompt 02：首次引导式配置

```text
为 Yotsuba Ink 实现 GuidedSetupWorkbench 和 SetupStepNavigation，借鉴 React Bits Stepper 的连接线和完成标记，但不要把四个旧 Settings Tab 换皮后原样搬进步骤。

五步固定为：故事起点、参考方式、创作方式、AI 服务、开始前确认。它只服务首次启动准备，不得表达 Info 到 Export 的七阶段运行进度；首次完成后 Settings 使用单页总览，不再强制重播 Stepper。

数据与状态约束：
- 步骤完成度从现有 Workflow、Knowledge 和服务端 Provider Readiness 派生，禁止新增脱节的 setupCompleted 真值。
- useSetupFlow 只拥有 activeStepId、方向、焦点和提交 UI 状态，不复制业务字段。
- 可以持久化 lastVisitedSetupStepId，但进入时必须重新定位最早阻塞项。
- onContinue 只校验本步；onStart 复用现有 Run 创建命令；动画回调不得保存或创建 Run。
- Demo/Mock 保持可用，但必须明确真实服务未就绪状态。

字段与布局：
- 故事起点：题材/篇幅、读者/风格双列，核心创意和创作边界全宽。
- 参考方式：先选联网/链接/上传，只显示当前选择相关字段。
- 创作方式：Fast/Balanced/Deep 与结果型输出偏好，不暴露 Token 和七个重复确认开关。
- AI 服务：文本服务优先；启用 Cover 时才要求图片服务；保存、检查连接、同步模型命令分离。
- 确认页只汇总、定位 Blocking/Warning，不重新输入。
- 桌面左侧 208-240px 步骤轨、右侧 760-880px 表单工作面；移动端只显示 x/5 和当前步骤，完整清单进入 Sheet。
- 底部稳定显示“保存后退出 / 上一步 / 继续或开始创作”，每步只有一个主动作。

应用 Form Layout Contract：Label/Control/Description/Error 稳定结构；Short/Medium/Full 宽度语义；同一行等宽等高；720px 以下单列。参考用户提供的 Uiverse themrsami 表单只吸收纵向节奏、等宽双列和全宽叙事字段，不复制 Tailwind、外层深色 Card 或示例输出 Textarea。

工程边界：文件进入 planning/settings/state/contracts/lib 既有目录；Provider 配置继续由 settings 所有；不新增 components/screens/dialogs 目录。动画遵守 motion.ts，Reduced Motion 即时。

验收：中途退出/恢复、前一步失效、可选步骤跳过、错误聚焦、密钥 Dirty Guard、服务失败分类、390px 软键盘、Keyboard、200% Zoom，以及纯步骤切换 0 Provider/0 resume/0 SSE/0 正式写回。
```

### Prompt 03：稳定 Grid 与 Hover

```text
借鉴 React Bits MagicBento 的非等宽 Grid 和边缘反馈，为 {surface} 设计 AdaptiveSurfaceGrid。

只保留 CSS Grid、稳定轨道、局部 Hover 背景和 selected/current 静态边缘光。删除粒子、磁吸、3D Tilt、全局 Spotlight、Cursor 追踪和无限动画。

先说明每个 Grid Item 的业务价值；不能为了填满布局添加内容。Hover 不改变尺寸、位置和行高，Touch/Keyboard 有等价选中状态。
```

### Prompt 04：Header Tool Dock

```text
借鉴 React Bits Dock 的邻近反馈，重构 Yotsuba Ink 的 GlobalToolDock。

只包含主题、重置/撤销、历史、设置；固定 Header 高度，图标 36x36，最大放大 1.055，移动端取消放大。使用 Lucide、Tooltip、aria-label 和现有危险操作合同。

主题改为 ThemeModeSwitch，不能同时保留两套主题按钮。Dock Hover/Active 不得触发业务请求或改变布局。
```

### Prompt 05：BorderGlow 选择态

```text
借鉴 React Bits BorderGlow 的边缘层次，为 {target} 实现 selected/current/ready 状态。

Glow 颜色来自 Fast/Balanced/Deep Token；只在状态变化时短暂进入，空闲保持静态内描边。禁止持续绕边、强 Box Shadow、粒子和大面积模糊。

选中态还必须有 Check、文本或 aria-selected，不能只靠颜色。
```

### Prompt 06：Panel / Tab 淡入

```text
借鉴 React Bits AnimatedContent 和 FadeContent 的内容进入概念，用现有 motion 实现 PanelTransition。

进入 180-220ms、Opacity + 3-8px；退出 100-120ms；默认无 Blur。Tab 切换保留本地状态、滚动位置和草稿，不重挂载整个工作台，不调用 Provider。

Reduced Motion 下直接切换。不要安装 GSAP、ScrollTrigger 或 Anime.js。
```

### Prompt 07：短标题文字切换

```text
借鉴 React Bits SplitText/BlurText，为 QualityModeTransitionOverlay 的短模式标题实现按词进入。

只允许 2-6 字模式名和一句短说明；不得用于正文、设置字段、表格或长标题。总 Stagger 不超过 120ms，默认不做 10px Blur，Reduced Motion 直接显示完整文本。
```

### Prompt 08：统一 Option / Combobox

```text
实现 Yotsuba Ink 的 OptionField，解决 Provider 长列表浮层过大、位置失控、无搜索和状态不一致的问题。

7 项以内使用现有 Radix Select；超过 7 项或包含 Group/Description 时使用经过验证的可访问 Combobox。Popup 宽度 max(trigger, 280px)，上限 420px；最大高度 360px；Portal、Collision Padding 12px。

支持 Provider 分组、搜索、当前项、Ready/Warning/Disabled、中文 IME、Keyboard、Escape、Custom Model 和 390px Bottom Sheet。不得手写不完整 ARIA，不得改变现有保存和 Provider 生命周期。
```

### Prompt 09：模式沉浸遮罩

```text
恢复 Yotsuba Ink 三档模式的沉浸切换遮罩，实现 QualityModeTransitionOverlay。

Fast 水平扫过，Balanced 对称展开，Deep 聚焦揭示；总时长 480-620ms。遮罩只消费本地模式切换，不拥有 Workflow 保存、路由、Provider、SSE 或写回。

连续点击只落到最后目标；锁定不播放；Dirty Confirm 优先；Reduced Motion 即时。禁止粒子、Glitch、Starfield、大 Blur 和持续 Glow。
```

### Prompt 10：输入、开关和复选框

```text
参考用户提供的 Uiverse Input、Sun/Moon Switch、Neo Toggle 和 Neon Checkbox，但只提炼清晰 Focus、Thumb 位移和 Check 反馈。

使用现有 Token；Input 2px Focus Ring；主题 Switch 48x28；业务 Switch 40x22；Checkbox 20/22px。删除云星多层 SVG、频谱、Progress Arc、发光点、文字位移和无限 Pulse。

覆盖 Default/Hover/Active/Focus/Busy/Error/Disabled/ReadOnly，错误语义优先于模式色。
```

### Prompt 11：加载反馈

```text
参考用户提供的 Uiverse Gradient Spinner，为 Yotsuba Ink 实现 16/20/24px ModeSpinner，并建立 Spinner、Skeleton、真实 Progress 的使用规则。

短命令用 Spinner；未知长任务保持目标布局用 Skeleton；有 SSE/上传/导出步骤时只显示真实进度。禁止在所有加载位置放 100px 发光环，禁止计时器伪进度。
```

### Prompt 12：Detail Sidebars

```text
根据 Detail Artifact 合同重构章节细纲工作台：左侧 DetailChapterSidebar，中间 DetailConstructionTable，右侧 DetailContextInspector。

左侧展示章节、POV、就绪和缺项；中间是最大施工表；右侧只展示当前章人物、事实、伏笔和世界锚点。桌面可折叠，1024 以下转 Sheet，390px 单章视图。

不得把三栏做成 Card 墙；切章和打开详情不得触发生成；草稿保护、稳定行 ID 和正式写回语义保持不变。
```

### Prompt 13：Text Sidebars

```text
根据 Text Artifact 合同重构专业写作桌：左侧 WritingChapterSidebar，中间 WritingManuscriptSurface，右侧 WritingReviewSidebar。

正文是最大工作面；右侧只有质量审校/事实写回两个 Tab；人物和世界观为详情入口。增加写作/审校/专注视图，但切换只改变布局，不改变 Artifact。

移动端正文单栏，章节与审校使用 Sheet。流式只让新增句子淡入，用户上滚后停止跟随。保持修订、提案、复检、草稿和定稿合同。
```

### Prompt 14：单页人工评审

```text
评审 Yotsuba Ink 的 {surface}，先列出 Artifact、用户决策、写回目标和下一阶段依赖，再检查：

1. 首屏是否只有一个主 Artifact、一个支撑区和一个主决策。
2. 是否有重复导航、重复状态、教程文案、假指标或无价值空位填充。
3. Hover/Active/Focus/Busy/Error/Empty/Reduced Motion 是否完整。
4. 320/390/768/1024/1440/1728 和 200% Zoom 是否重排而非压缩。
5. 纯 UI 交互是否产生 Provider、resume、SSE、写回或重复请求。

先给出阻断问题和证据，再提出最小正确改动；不要直接套用卡片、Bento、Glow 或动画。
```

### Prompt 15：Settings Overview 语义重构

```text
把 Yotsuba Ink 当前“全局模型 / 模型接口 / 阶段覆盖 / 运行策略”四 Tab 重构为 SettingsOverview，不保留旧 Tab 的平级结构。

默认 Section：创作设定、参考与资料、创作方式、AI 服务与默认模型、输出偏好、高级阶段例外、自动保护。每区只显示 2-4 个摘要、真实状态和一个修改/管理动作；编辑进入局部 Section 或 Sheet，关闭后恢复滚动和焦点。

字段归属：
- Provider Profile 与默认模型只在 AI 服务管理。
- 阶段 Provider/模型改名“阶段例外”，具体编辑只在对应 StageInspector 高级区；Overview 只显示数量、阶段名和全部恢复默认。
- 自动保存、运行前检查、封面资产校验是只读“自动保护”状态，不显示 Checkbox/Switch。
- Stage ID、Output Key、Memory 原始字段、API Key 明文默认隐藏。

保留现有 Provider 生命周期、Autosave、Dirty Guard、Focus Return、保存/删除保护、模型发现和 Demo/Mock。删除 Tab 不等于删除能力，也不能新建第二份 Workflow 状态。

使用全宽 Section 和摘要行，不做 Bento/Card 墙。桌面单一滚动所有者，390px 全屏 Sheet。所有纯打开/切区操作不得请求 Provider 或重连 SSE。
```

### Prompt 16：全应用表单语义与几何审查

```text
审查并逐个重构 Yotsuba Ink 的 {formSurface}。开始前列出 Artifact、用户决策、字段唯一所有者、草稿、保存命令、正式写回和退出保护，不做全仓机械替换。

Form Layout Contract：
- Label + requirement/status + Control + description/error 固定结构。
- Short 160-220px、Medium 320-480px、Full 为内容区宽度；同一行 minmax(0, 1fr) 等宽等高。
- 只有语义并列且预计长度相近的字段允许双列；720px 以下单列。
- Placeholder 只给例子，不替代 Label/教程；错误就近并可聚焦；自动保存状态不改变高度。
- 一屏只有一个 Primary；ReadOnly 使用状态行；Disabled 给出原因。

必须覆盖 InfoBriefEditor、StageInputField、StageInspector、ProviderEditor、SettingsDialog、ChapterBlueprintDialog、Detail 三类写回、Summary 结构、Outline Beat/人物/世界/伏笔、Cover Brief、Export Metadata 和换稿方向 Dialog。

Stepper 仅用于首次跨域准备；日常编辑使用聚焦的 Section/Dialog/Sheet。不得创建万能 Form 组件接管校验和保存；只有稳定重复的 Label/Description/Error/Status 结构才可提取轻量 Shell。

验收必须证明隐藏字段未丢失、数组稳定 ID/顺序未变化、切章/切对象/关闭弹层不丢草稿、提交快照和正式写回语义不变。
```

### Prompt 17：用户指引与错误恢复

```text
为 Yotsuba Ink 的 {surface} 设计任务内指引和错误恢复，不使用覆盖式产品 Tour，不堆教程文案，不依赖 Hover 承载唯一信息。

只保留：明确步骤/Section 名、影响决策的一句说明、智能默认值、条件显示、输入示例、真实阻塞原因、下一动作、离开后恢复和完成摘要。

错误文案必须回答：发生了什么、用户内容是否保留、下一步能做什么。Provider 错误区分鉴权、余额、模型、网络和结构化输出；普通界面使用用户语言，诊断详情可展开。继续失败时聚焦第一阻塞字段；顶部摘要只提供跳转，不复制全部错误。

可选步骤支持明确跳过并说明默认行为；首次流程完成后不重复播放指引。Keyboard、Touch、Screen Reader、390px 软键盘和 Reduced Motion 必须有等价路径。
```

## 19. 明确拒绝清单

- 把 StaggeredMenu 原样做成全屏营销菜单。
- 在 Header、Canvas 和侧栏同时放七阶段链路。
- 把 Stepper 当成第二套运行进度。
- 只把四个 Settings Tab 换皮成 Stepper，继续保留重复字段和技术分组。
- 首次配置完成后仍强制用户每次重走五步流程。
- 为步骤完成度复制一份 `setupCompleted` 业务真值，或用动画/计时器伪造完成。
- 在 Settings 和 Stage Inspector 同时提供七阶段 Provider/模型完整编辑表。
- 让短数字、长模型名和叙事 Textarea 任意拉伸，或为了填满一行拼接无关字段。
- 用 Placeholder、Tooltip 或长帮助段落替代清晰 Label、错误和字段归属。
- 给所有 Grid、Card、Button 和 Input 加模式 Glow。
- 在所有页面使用 MagicBento、Spotlight、Particles、Tilt 或 Cursor Effect。
- 把 Dock 邻近放大用于移动端或改变 Header 高度。
- 正文逐字 BlurText/SplitText，长列表无限 Stagger。
- 使用大面积持续 Aurora、Starfield、Meteor、Orb 或 Galaxy 背景。
- 用 100px Spinner 覆盖所有加载。
- 把只读运行策略显示成可点 Checkbox。
- 为复制示例引入 Tailwind、GSAP 或第二套完整 UI Kit。
- 在视觉阶段改变 Artifact、SSE、预算、恢复、写回或 Provider 语义。

## 20. 完成定义

Phase 9 只有同时满足以下条件才算完成：

1. Provider 和模型长列表具有统一、可搜索、可分组、可访问的 Option 体验。
2. 首次用户可以按五个语义步骤完成配置、中途退出恢复并定位真实阻塞；完成后不再强制重走流程。
3. 后续设置为单页 Overview + 局部编辑，不再存在四个交叉 Tab、重复默认模型或七阶段完整覆盖表单。
4. 每个配置字段有唯一主编辑位置；继承、阶段例外、自动保护和内部诊断语义清晰。
5. 全应用表单遵守 Short/Medium/Full、等宽 Grid、移动单列、就近错误和草稿保护合同。
6. Header 不再重复七阶段进度，Planning/Cockpit 各自只有一个阶段进度事实源。
7. 产品具备隐式导航，但没有复制阶段链和工具入口。
8. 三档模式遮罩具有沉浸感且无任何网络或写回副作用。
9. Planning 移动端不再缩小桌面 Canvas。
10. Detail 和 Text 的专属 Sidebars 在桌面、平板和移动端都可用。
11. 每个阶段保持差异化 Artifact 构图，没有退化成 Card/Bento 墙。
12. Button、Input、Switch、Checkbox、Tooltip、Loader、Tabs、Dialog 状态统一。
13. Dark/Light、Reduced Motion、Keyboard、Touch、200% Zoom 和所有目标视口通过。
14. 空闲 Infinite 动画为 0，布局位移为 0，控制台无新增错误和警告。
15. UI 行为不触发额外 Provider、`/resume`、SSE、正式写回或重复计费。
16. Phase 8.8 的真实全链路验收仍以真实 Provider 成功证据独立完成，不能由 UI 截图替代。

## 21. 参考来源

- React Bits：https://reactbits.dev/
- React Bits Staggered Menu：https://reactbits.dev/components/staggered-menu
- React Bits Repository：https://github.com/DavidHDev/react-bits
- React Bits License：https://github.com/DavidHDev/react-bits/blob/main/LICENSE.md
- Uiverse：https://uiverse.io/elements
- Uiverse Galaxy：https://github.com/uiverse-io/galaxy
- Uiverse Galaxy License：https://github.com/uiverse-io/galaxy/blob/main/LICENSE
- Aceternity UI：https://ui.aceternity.com/components
- Aceternity Free Catalog：https://ui.aceternity.com/ai-recommendations
- Aceternity Item Licence：https://ui.aceternity.com/licence
- Aceternity Terms：https://ui.aceternity.com/terms
- Motion Primitives：https://github.com/ibelick/motion-primitives
- Radix Select：https://www.radix-ui.com/primitives/docs/components/select
- Base UI Combobox：https://base-ui.com/react/components/combobox
- Base UI Select：https://base-ui.com/react/components/select
- Anime.js：https://github.com/juliangarnier/anime

所有来源在真正复制源码前必须再次固定 URL、Commit、版本、许可证和声明要求。未确认时只独立实现交互思想。
