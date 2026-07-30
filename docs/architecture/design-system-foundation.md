# 设计系统基础合同

## 1. 目标

Phase 2 的目标不是把 Yotsuba Ink 改成展示型页面，而是让高密度小说生产工作台具备稳定、可扩展、可验证的视觉语言。

设计系统必须同时支持：

- `planning` 与 `running` 两种工作空间。
- Fast、Balanced、Deep 三种生产模式。
- Dark 与 Light 两套主题。
- Header、阶段导航、主操作、Dialog、Sheet、Tooltip 和状态反馈。
- 键盘操作、Reduced Motion 和无横向溢出。

## 2. 产品原则

1. 主产物和当前用户决策始终优先于诊断信息和装饰效果。
2. 模式色表达生产策略，不承担整个页面的品牌底色。
3. Dense 不等于拥挤；密度依靠对齐、间距节奏和层级对比建立。
4. 动效只说明状态变化，不持续抢占注意力。
5. 真实生成、加载、空状态和错误状态必须可区分，不能用完整演示稿伪装成功。

## 3. Token 所有权

唯一 Token 入口是：

- `apps/web/src/styles/design-tokens.css`

基础元素和页面壳层位于：

- `apps/web/src/styles/foundation.css`

`styles.css` 必须先导入 `design-tokens.css`，再导入基础样式和具体表面样式。

## 4. Token 分层

### 4.1 主题语义 Token

| 类别 | Token | 用途 |
| --- | --- | --- |
| Canvas | `--color-canvas`、`--color-canvas-subtle` | 页面底层和次级底层 |
| Surface | `--color-surface-base`、`--color-surface-raised`、`--color-surface-muted` | 面板、浮层和输入区 |
| Border | `--color-border-subtle`、`--color-border-strong` | 分组边界和强调边界 |
| Text | `--color-text-primary`、`--color-text-secondary`、`--color-text-muted` | 主文案、辅助文案和元信息 |
| Action | `--color-action-primary`、`--color-action-secondary` | 全局主操作背景和中性品牌动作 |
| Action content | `--color-action-emphasis`、`--color-action-foreground` | Action 强调文字和主操作前景文字 |
| Status | `--color-status-success`、`--color-status-warning`、`--color-status-danger` | 成功、等待和失败 |
| Focus | `--color-focus-ring` | 全局键盘可见焦点 |

主题切换只允许重定义这些语义值，不允许在组件内复制整套 Dark/Light 颜色。

Action 背景与 Action 强调文字必须使用不同语义 Token。高亮青色可以作为 Dark 主题的小面积强调文字，但不能同时直接承担白字按钮背景；否则无法同时满足“青色文字对暗底”和“白色文字对青底”的对比度要求。

### 4.1.1 对比度基线

正常字号文字按 WCAG AA `4.5:1` 验收，键盘焦点和非文字边界按 `3:1` 验收。Phase 2.4 的最弱组合如下：

| Theme | 组合 | 对比度 |
| --- | --- | ---: |
| Dark | Muted text / Surface | `6.16:1` |
| Dark | Action foreground / Primary action | `4.99:1` |
| Dark | Action foreground / Secondary action | `5.17:1` |
| Dark | Danger / Surface | `5.79:1` |
| Light | Muted text / Surface | `5.65:1` |
| Light | Action foreground / Primary action | `5.63:1` |
| Light | Action foreground / Secondary action | `5.17:1` |
| Light | Success / Surface | `5.51:1` |
| Light | Warning / Surface | `5.13:1` |
| Light | Danger / Surface | `5.21:1` |
| Dark | Focus ring / Surface | `10.92:1` |
| Light | Focus ring / Surface | `6.20:1` |

### 4.2 模式 Token

- `--color-mode-primary`
- `--color-mode-secondary`
- `--mode-aura`
- `--mode-aura-strong`
- `--mode-aura-soft`

模式 Token 只应用于：

- 模式选择器的选中状态。
- 当前运行模式标识。
- 阶段运行、结算和质量反馈中的局部状态。

模式 Token 不应用于：

- 页面整体背景。
- 所有按钮和输入框。
- 普通面板边框。
- 与模式无关的标题、导航和知识库表面。

当前 `--accent`、`--accent-2` 仍保留原始模式行为以保证兼容。后续组件必须优先使用新的 action/mode 语义 Token，并逐步收口旧别名。

### 4.3 密度和形状 Token

- 间距：`--space-1` 至 `--space-8`
- 控件：`--control-gap`、`--control-padding-inline`
- 字段：`--field-padding-block`、`--field-padding-inline`
- 圆角：`--radius-xs`、`--radius-control`、`--radius-panel`、`--radius-dialog`、`--radius-pill`
- 高度：`--control-height-sm`、`--control-height-md`、`--control-height-lg`
- 壳层：`--shell-header-height`、`--shell-min-height`

新增组件不得随意引入新的 6px、11px、13px 等孤立尺寸。确有业务原因时先说明用途，再补充语义 Token。

### 4.4 动效 Token

- `--duration-fast`
- `--duration-standard`
- `--ease-standard`
- `--focus-ring`

普通 hover、focus、展开和状态反馈使用 CSS 或现有 `motion`。全局 Header、模式切换和普通弹层不引入 GSAP。

只有多元素可逆时间线、SVG/Canvas 编排或跨阶段精确同步确实需要时，才评估 GSAP。

## 5. 兼容层规则

旧变量如 `--bg`、`--panel`、`--text`、`--border`、`--accent` 暂时保留，避免一次修改数百个选择器。

迁移规则：

1. 新组件只使用语义 Token。
2. 修改既有组件时，在同一职责文件内迁移相关旧变量。
3. 不做全仓机械替换，不跨历史 cascade 合并选择器。
4. 每批迁移都需要 Dark/Light 和三模式回归。
5. 旧变量使用量归零后，再单独删除兼容层。

## 6. ReactBits 使用门槛

ReactBits 只作为交互和效果参考，不直接决定信息架构。

允许的场景：

- 阶段切换和结算中的一次性进入反馈。
- 空状态、候选比较和加载状态中的局部视觉提示。
- 不影响编辑性能的轻量文本或边框反馈。

禁止的场景：

- 全局持续粒子、光束或闪烁背景。
- 给每个卡片添加独立动画。
- 用动画掩盖不明确的状态和操作层级。
- 不支持 Reduced Motion 的复制式组件引入。

采用 ReactBits 思路时必须重新接入本项目 Token、主题、键盘焦点和 Reduced Motion，不能原样粘贴视觉参数。

## 7. 验收矩阵

每个全局 UI 批次至少验证：

| 维度 | 必测值 |
| --- | --- |
| Theme | Dark、Light |
| Mode | Fast、Balanced、Deep |
| Workspace | Planning、Running |
| Viewport | 320x720、390x844、768x900、1024x900、1280x920、1440x900 |
| State | 默认、运行中、禁用、错误、弹层打开 |
| Accessibility | 键盘焦点、可访问名称、Reduced Motion |

浏览器退出条件：

- 控制台 0 error、0 warning。
- 页面无横向溢出。
- Header 宽度和主操作位置在状态切换时稳定。
- Dialog/Sheet 不被局部容器裁切。
- 最长中文标签和模型名称不覆盖相邻控件。

## 8. Phase 2 实施顺序

1. `Phase 2.1`：Token 合同、兼容层和暗亮视觉基线。
2. `Phase 2.2`：Header、模式控制、阶段进度和主操作。
3. `Phase 2.3`：Dialog、Sheet、Tooltip、空状态和错误状态。
4. `Phase 2.4`：主题、Reduced Motion、键盘与响应式收口。

每一阶段先完成稳定交互，再增加低频视觉反馈。

当前状态：`Phase 2.1` 至 `Phase 2.4` 已完成。Header、Overlay、Tooltip、反馈状态、主题对比度、Reduced Motion、全局键盘焦点和 320-1440px 响应式边界均已收口，下一步进入 `Phase 3` 的 Planning 与 Info 工作流升级。

## 9. Phase 2.4 验收结果

- Dark/Light 主文字、辅助文字、弱文字、Action、Success、Warning、Danger 和 Focus Token 均通过目标对比度。
- Action 背景与强调文字完成语义拆分，主按钮白字不再落在高亮青色背景上。
- 最后导入 `accessibility-responsive-closure.css`，为原生控件、ARIA 交互控件和可聚焦自定义控件提供统一 `:focus-visible` 兜底。
- `prefers-reduced-motion: reduce` 下所有 CSS animation 和非必要 transition 均为 `none/0s`，持续 ECG、环境层、Spinner、呼吸和流光不会快速播放一次。
- 320、390、768、1024、1280 和 1440px 均无页面级横向溢出；React Flow 仍在自己的可缩放画布内管理超宽节点。
- GSAP 不进入 Phase 2。这里没有需要可逆多元素时间线的交互，增加运行时只会扩大维护和性能成本。
