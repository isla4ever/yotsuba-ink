# CSS 选择器所有权与性能基线

本文件是 Phase 8.7 的样式治理合同。它不要求为了减少行数删除稳定逻辑；它要求每次新增、覆盖或删除选择器时，能回答消费者、级联位置、动效成本和回归验证方式。

## 可执行事实源

- 入口顺序：`apps/web/src/styles.css`。所有 `apps/web/src/styles/*.css` 必须且只能从该入口导入一次。
- 审计器：`apps/web/scripts/audit-css.mjs`，使用 PostCSS AST，不通过正则猜测 CSS 结构。
- 冻结基线：`apps/web/scripts/css-audit-baseline.json`，记录每个已审核文件的所有者和只允许自动下降的债务预算。
- 日常门禁：在 `apps/web` 执行 `npm run audit:css`。
- 有意新增样式或调整所有权后：先审查报告、完成浏览器矩阵，再执行 `npm run audit:css -- --update-baseline`。更新基线不是绕过评审的手段。

## 所有权表

| 所有者 | 唯一职责 | 可拥有的文件 |
| --- | --- | --- |
| `design-system` | Token、基础元素、表单、全局 Focus/Reduced Motion 和共享 Keyframe | `design-tokens`、`foundation`、`forms-and-docs`、`keyframes-and-responsive`、`control-state-system`、`accessibility-responsive-closure` |
| `layout-shell` | Header、History、知识库入口、全局 Dialog/Overlay 与危险操作保护 | `header-*`、`history-*`、`knowledge-rail`、`inspector-reference`、`dialogs`、`overlay-*`、`unsaved-*`、`destructive-*` |
| `planning` | Planning 画布、配置 Sheet、Cockpit 配置态 | `planning-*` |
| `stage-shared` | 所有运行阶段共用的 Shell、Artifact 状态、决策、候选、结算和运行洞察 | 无明确单阶段前缀的 `stage-run-*` 与 `stage-artifact-state` |
| `stage-info` | Info 推荐、人物与世界观定稿 | `stage-run-info-*` |
| `stage-summary` | Summary 稿纸、结构和人物弧 | `stage-run-summary-*` 与 Summary workbench 层 |
| `stage-outline` | Outline 卷、节拍和三类承接 | `stage-run-outline-*`、`stage-run-volume-chapters` 与 Outline workbench 层 |
| `stage-detail` | Detail 章节施工表、蓝图和三类写回 | `stage-run-detail-*` 与 Outline/Detail 共享产物层 |
| `stage-writing` | Text 正文、选区修订、质量与版本历史 | `stage-run-writing-*`、`stage-run-chapter-revision*` |
| `stage-cover` | Cover 简报、候选、预览和正式资产 | `stage-run-cover-*` 与 Cover workbench 层 |
| `stage-export` | Export 选择、Receipt、交付版本和下载 | `stage-run-export-*`、`stage-run-delivery` 与 Delivery workbench 层 |

基线 JSON 中的 `ownership` 是逐文件明细表。新增文件若不属于上述唯一所有者，审计直接失败；同一功能不得再通过新建 `vNext/legacy/phaseXX` 覆盖层规避原所有者。

## 级联与删除规则

1. 先定位 React 消费者和页面状态，再定位当前最终生效选择器；文件名中的 `v2/v3/v4/v6/legacy/phaseXX` 不能作为删除证据。
2. 同一选择器跨文件出现时，入口中最后一个文件拥有最终级联，但业务所有者仍以表格和基线为准。迁移必须一次只处理一个页面或一个小组件。
3. 删除前覆盖 Default、Loading、Streaming、Dirty、Busy、Error、Recovery、ReadOnly 和 Reduced Motion 中实际存在的状态；不存在的状态记录为不适用，不能伪造展示。
4. Hover 不得是唯一入口。删除 Hover 规则时必须同时检查 Focus Visible、Active、Touch 和 Keyboard 等价路径。
5. 动画只允许解释状态变化。空闲页面不得保留 Infinite 动画或持续 RAF；全局 Reduced Motion 兜底不得移除。

`stage-run-writing-phase95c3.css` 与 `stage-run-writing-phase95c3-responsive.css` 继续归 `stage-writing`：前者只负责桌面任务视图与 Rail，后者只负责平板/移动 Dock、Sheet 和折叠定稿区，不建立新的跨阶段样式层。

## 自动预算

审计对 CSS 字节、源码行、规则、选择器、跨文件重复选择器、Keyframe、动画声明和 Infinite 声明执行“不得高于已审核基线”。指标下降会自动通过；新增文件、所有权变化或指标增长必须在浏览器验收后显式更新基线。

结构错误不受预算豁免：未导入文件、重复导入、导入不存在文件、无所有者文件始终失败。`globalReducedMotionGuardCount` 是最低保证，只能保持或增加。

## Phase 8.7 验收矩阵

- 视口：`320 / 390 / 768 / 1024 / 1180 / 1280 / 1440 / 1728`，覆盖 Dark、Light 和 200% Zoom。
- 输入：Keyboard、Touch、软键盘、Browser Back/Forward；Dialog/Sheet 验证 Focus Trap、Escape、脏态确认和 Focus Return。
- 运行质量：页面横向溢出、Console Error/Warning、意外 Provider/Resume/SSE/写回请求均为零。
- 性能：空闲 Infinite/持续 RAF 为零，Long Task 和 CLS 为零，运行循环不超过 3，掉帧率低于 5%。
- 视觉状态：按表面保留可复现的 Default/Loading/Streaming/Dirty/Busy/Error/Recovery/ReadOnly/Reduced Motion 截图或“不适用”记录。
