# Phase 9.3：产品导航、Header 与 Tool Dock

> 状态：已实施并完成浏览器验收
>
> 日期：2026-07-24
>
> 前置：Phase 9.2 Option 系统已完成；本阶段不改变阶段 Artifact、Provider 生命周期、Run、历史、恢复或导出合同。

## 1. 本阶段产品决策

本阶段解决的是全局入口分散和 Header 重复表达阶段状态的问题，而不是再增加一套视觉化阶段导航。

- 七个创作阶段继续只属于 Planning Canvas、自动驾驶舱或运行阶段路由。
- Header 不再消费 `StageProgressNavigator`，也不再展示 ECG、配置节点或运行节点。
- Header 中间只保留当前表面摘要：创作准备完成度，或当前运行阶段状态。
- 全局工具集中在 `GlobalToolDock`：主题、运行重置/撤销、历史、设置。
- 产品级导航只包含创作流程、当前运行、知识资料、创作历史、模型与设置。
- 没有运行时，当前运行入口明确禁用；入口禁用不改变本地运行恢复状态。

## 2. 交互合同

### ProductNavigationRail

- 默认只保留 38px 导航触发器，不占用工作台主面。
- 桌面打开 304px 左侧 Rail，Backdrop 只降低对比度，不做大面积模糊。
- 菜单项使用 25ms 级短 Stagger，总进入时间不超过 260ms；Reduced Motion 直接显示。
- `Escape`、Backdrop、关闭按钮和再次点击触发器都能关闭；关闭后焦点回到触发器。
- 菜单不拥有路由。所有导航动作由 `App.tsx` 统一分派到既有路由、历史、知识库和设置入口。
- 触发菜单、Hover、关闭和切换入口不调用 Provider、`/resume`、SSE、正式写回或计费逻辑。
- 移动端在底部转为 Sheet，保留 44px 级触控目标和单一内部滚动区。

### GlobalToolDock

- 工具图标固定为 36px，桌面 Hover 最高放大到 1.055，使用 transform，不改变 Header 几何。
- 移动端取消邻近放大，工具压缩为 32px，并去除尚未运行时的重置入口。
- 主题是一个 `role="switch"` 控件，不同时出现两套日/月按钮。
- 历史、设置使用 `aria-pressed` 表达当前打开状态；重置继续复用既有确认、Busy、撤销和恢复合同。
- 模式选择和唯一主动作仍由 `CreationActionDock` 所有，避免工具与主动作混成一个分段控件。

## 3. 文件与边界

| 文件 | 责任 |
| --- | --- |
| `apps/web/src/features/pipeline/layout/ProductNavigationRail.tsx` | 产品级导航触发器、桌面 Rail、移动 Sheet、焦点和键盘行为 |
| `apps/web/src/features/pipeline/layout/GlobalToolDock.tsx` | 主题、重置/撤销、历史、设置工具编排 |
| `apps/web/src/features/pipeline/layout/ThemeModeSwitch.tsx` | 可访问的日夜模式切换控件 |
| `apps/web/src/features/pipeline/layout/AppHeader.tsx` | 稳定 Header、当前表面摘要、Dock、模式和主动作装配 |
| `apps/web/src/App.tsx` | 导航状态、产品入口派生和既有路由/Overlay 命令分派 |
| `apps/web/src/styles/product-navigation.css` | Header 几何、Rail、移动 Sheet 和响应式断点 |
| `apps/web/src/styles/global-tool-dock.css` | Dock、Theme Switch、Hover/Focus 和移动工具尺寸 |

没有新增 `components/`、`screens/`、`dialogs/` 或 `reactbits/` 目录；没有安装新动效依赖。

## 4. 视觉与内容评审

- 1440px 首屏最大的内容仍是 Planning Canvas，右侧仍是阶段配置，不因导航增加内容墙。
- Rail 只包含改变工作区或打开全局资源的入口，不复制七阶段，也不放知识库重复入口。
- 当前运行、知识资料、历史和设置分别对应不同业务事实，不用同一套状态文案混淆。
- 空运行状态的“当前运行”入口是禁用态并给出原因；历史入口可以展示服务端历史数量，但不伪装成本地生成进度。
- Hover 只改变边框、背景和局部缩放，不抬高、不挤压 Header，也不持续发光。

## 5. 浏览器验收

### 桌面 1440 x 1000

- Header 高度：78px。
- `body.scrollWidth === document.documentElement.scrollWidth === 1440`。
- `.header-progress-slot` 不存在，`.app-header .stage-mini-progress` 不存在。
- Rail 打开后为左侧 304px 面板，Backdrop 不影响工作台滚动事实。
- Screenshot：`output/playwright/phase93-planning-desktop-final.png`、`output/playwright/phase93-navigation-desktop.png`。

### 移动 390 x 844

- Header 高度：124px；旧的 184px 移动变量已由产品壳层覆盖。
- `body.scrollWidth === document.documentElement.scrollWidth === 390`，无横向溢出。
- 导航触发器、Dock、模式选择和主动作均在可点击区域内。
- Rail 转为底部 Sheet；Escape 关闭后焦点回到“打开产品导航”按钮。
- Screenshot：`output/playwright/phase93-planning-mobile-final3.png`、`output/playwright/phase93-navigation-mobile.png`。

## 6. 未在本阶段处理的内容

- Planning Canvas 顶部重复阶段条的删除属于 Phase 9.4，必须与移动 Stage Rail 一起验证。
- Fast/Balanced/Deep 沉浸式遮罩属于 Phase 9.4，本阶段只保留现有模式切换语义。
- Detail/Text 专属 Sidebar 属于 Phase 9.8，本阶段的产品 Rail 不替代阶段内上下文侧栏。
