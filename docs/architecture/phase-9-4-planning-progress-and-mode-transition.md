# Phase 9.4：Planning 唯一进度与模式遮罩

> 状态：已实施并完成浏览器验收
>
> 日期：2026-07-24
>
> 前置：Phase 9.3 产品导航、Header 与 Tool Dock 已完成；本阶段不改变阶段 Artifact、Provider 生命周期、Run、SSE、恢复、历史或导出合同。

## 1. 本阶段产品决策

本阶段解决两个容易造成误判的问题：Planning 同时显示两套阶段进度，以及三档模式切换缺少明确的沉浸式状态反馈。

- 桌面 Planning 只把中央 React Flow 节点作为七阶段进度来源；Header 和 Canvas 顶部不再重复显示阶段横条。
- 移动端不强行压缩 React Flow，而是使用单列 Stage Rail 保留阶段名称、配置状态和当前选择；React Flow 仅保留不可见的测量容器，避免重复视觉表达和窄屏交互冲突。
- Fast、Balanced、Deep 切换只产生视觉过渡，不调用 Provider、SSE、运行启动、恢复、正式 Artifact 写回或计费逻辑。
- 模式遮罩使用当前模式 Token，明确呈现模式名称、消耗级别和人工介入方式；动画结束后恢复原工作台。
- Reduced Motion 下不播放缩放、淡入和延迟，遮罩直接显示并按既有短时状态关闭。

## 2. Planning 进度合同

### 桌面

- `PlanningStageNavigator` 在桌面隐藏。
- `.planning-canvas-shell` 使用两行布局：Canvas 标题 + React Flow 画布。
- React Flow 节点仍提供阶段名称、阶段产物、配置就绪状态和节点选择，不改变原有 `InspectorTarget` 写入路径。
- 画布控制器、MiniMap、节点拖拽和锁定行为继续复用原合同。

### 移动

- `PlanningStageNavigator` 转为可滚动的单列 Stage Rail。
- 每行固定显示序号、阶段名称、配置状态和就绪图标，触控高度不低于 44px。
- Canvas 的 React Flow 容器为 1px 测量区域并设置 `visibility: hidden`，不再抢占首屏高度，也不向用户重复展示同一条阶段链路。
- 390px 视口下页面级 `scrollWidth` 与视口宽度一致，Stage Rail 内部独立滚动。

## 3. React Flow 首帧稳定性

浏览器复核发现，桌面隐藏 Stage Rail 后仍保留三行 Grid 模板，React Flow 被分配到第二个 `auto` 行，实际高度为 0。结果是节点 DOM 存在但不可见，控制器位置异常，并触发父容器宽高警告。

修复包含两层保护：

1. 桌面 `.planning-canvas-shell` 收敛为 `auto minmax(0, 1fr)`；移动端通过媒体查询恢复三行结构。
2. `PipelineCanvas` 使用 `ResizeObserver` 监听 `.flow-frame`，只有在首次测得有效宽高后才挂载 React Flow；容器暂时无尺寸时不创建图实例。

这保证了 `fitView`、MiniMap 和 Controls 都在有效容器内初始化，同时保留响应式尺寸变化时的自动适配。

## 4. 模式遮罩合同

`QualityModeTransitionOverlay` 通过 Portal 挂载到 `document.body`，并使用 `motion` 的现有 `AnimatePresence` 体系。

| 模式 | 过渡内容 | 视觉 Token |
| --- | --- | --- |
| 极速生产 | 低消耗、无需人工干预 | Fast 蓝色主色 |
| 平衡创作 | 中等消耗、仅信息推荐定稿 | Balanced 青绿色主色 |
| 精细定稿 | 高消耗、每阶段人工确认 | Deep 紫色主色 |

遮罩使用 `pointer-events: none`，只承担状态表达，不阻塞 Header 和工作台命令。`AppHeader` 仅保存短时的 `modeNotice`，模式真正写入仍由既有 `handleQualityModeChange` 完成。

## 5. 文件与边界

| 文件 | 责任 |
| --- | --- |
| `apps/web/src/features/pipeline/layout/QualityModeTransitionOverlay.tsx` | 模式遮罩 Portal、模式文案、Reduced Motion 分支 |
| `apps/web/src/features/pipeline/layout/AppHeader.tsx` | 触发短时遮罩，不改变模式业务命令 |
| `apps/web/src/features/pipeline/planning/PipelineCanvas.tsx` | React Flow 尺寸就绪门控、画布初始化和原有交互 |
| `apps/web/src/features/pipeline/planning/PlanningStageNavigator.tsx` | 移动 Stage Rail 的可访问阶段选择 |
| `apps/web/src/styles/planning-stage-rail.css` | 桌面去重、移动 Stage Rail、隐藏测量容器 |
| `apps/web/src/styles/quality-mode-transition.css` | 遮罩、模式色、Reduced Motion |
| `apps/web/scripts/css-audit-lib.mjs` | 将模式遮罩 CSS 归入 `layout-shell` |

没有新增 `components/`、`screens/`、`dialogs/` 或 `reactbits/` 目录，没有安装新的动效依赖。

## 6. 浏览器验收

### 桌面 1440 x 1000

- `.planning-stage-nav`：`display: none`。
- `.flow-frame`：`996.89 x 699px`，React Flow 节点可见。
- 页面无横向溢出。
- React Flow 控制器和 MiniMap 位于画布内部，不再被标题区域拦截。
- 模式遮罩截图：`output/playwright/phase94-mode-overlay-final.png`。

### 移动 390 x 844

- `.planning-stage-nav`：`display: grid`，单列 Stage Rail 可见。
- `.flow-frame`：`360 x 1px`，`visibility: hidden`。
- `body.scrollWidth === document.documentElement.scrollWidth === 390`。
- Console：0 errors、0 warnings。
- Stage Rail 截图：`.playwright-cli/page-2026-07-24T13-11-17-571Z.png`。

## 7. 退出门禁

- `npm run audit:css`：通过。
- `npm test -- --run`：63 个测试文件、215 个测试通过。
- `npm run build`：通过。
- `git diff --check`：通过。
- 桌面和移动浏览器均无 React Flow 宽高警告。

Phase 9.5 可以在此基础上开始表单系统、基础控件和内容过渡；不得重新引入第二套常驻阶段进度，也不得在无尺寸容器中挂载重量级画布。
