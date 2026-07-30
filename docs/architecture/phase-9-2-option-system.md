# Phase 9.2：统一 Option 系统实施与验收

更新时间：2026-07-24

状态：已完成，可进入 Phase 9.3。

## 1. 阶段目标

本阶段只解决配置类 Option 的四个问题：

1. Provider 模板和长列表无法快速定位。
2. Provider、模型、阶段例外和故障转移的字段高度不一致。
3. 选项描述、分组、当前值和异常状态缺少同一套表达。
4. 自定义模型只能依赖回车这一隐式操作。

本阶段不重做 Header、Dock、三档模式遮罩、普通 Input、Textarea、Switch、Checkbox，也不改变任何 Workflow 字段归属、自动保存、Secret Dirty Guard、Provider 生命周期或阶段运行语义。

## 2. 迁移范围

| 入口 | 迁移结果 | 选择策略 |
| --- | --- | --- |
| 新增服务 → 厂商模板 | 28 个模板统一搜索 | Base UI Combobox，按官方直连、兼容层、网关、自定义分组 |
| 已有服务 → 厂商模板 | 当前 Provider 类型内搜索 | Base UI Combobox，描述、类型 Meta、官方文档摘要保留 |
| AI 服务管理 → 默认文本/封面服务 | 统一短 Option | Radix Select，服务名、默认模型、启用状态保留 |
| Provider 编辑 → 默认模型 | 选择与自定义添加分离 | 短列表使用 Radix，长列表自动切换 Base UI，保留回车快捷添加并增加“添加”按钮 |
| 阶段例外 → 文本/封面服务 | 统一服务字段几何 | Radix Select，切换仍调用原阶段例外写回逻辑 |
| 阶段版本比对 → 评审服务 | 继承默认与显式 Provider 同一入口 | Radix Select，`inherit` 仍保持原语义 |
| 故障转移 → 备用 Provider | 备用服务统一搜索/选择 | Radix Select，优先级、启用、删除和去重逻辑不变 |

以下保持原控件：创作 Brief、业务短 Select、运行阶段 POV/状态、普通文本输入和多行输入。这些属于 Phase 9.5 表单系统，不因为 OptionField 迁移而混入本阶段。

## 3. OptionField 合同

实现文件：

- `apps/web/src/features/pipeline/settings/fields/OptionField.tsx`
- `apps/web/src/features/pipeline/settings/fields/optionFieldModel.ts`
- `apps/web/src/styles/option-field.css`

### 3.1 组件边界

`OptionField` 只拥有展示与交互：

- `label`、`description`、`error`、`statusText`。
- `value` 与 `onValueChange`。
- `disabled`、`readOnly`、`ready/warning/disabled` 状态。
- 短列表和长列表的渲染选择。
- Group、Description、Meta、Empty、Keyboard、IME、Portal 和响应式几何。

它不拥有：

- Workflow 保存。
- Provider 创建、更新、删除、测试、模型发现。
- 阶段例外清理或故障转移去重。
- API Key、Secret 或任何持久化状态。

### 3.2 短列表与长列表判定

- 7 项以内且没有描述/分组：`@radix-ui/react-select`。
- 超过 7 项、存在分组或存在描述：`@base-ui/react` Combobox。
- 所有入口复用 `prepareOptionItems`，保证重复值被去重；当前值即使暂时不在发现结果中，也会以“当前配置”保留，避免切换后空白。

### 3.3 长列表交互

- 打开后搜索 input 自动获得焦点。
- 输入值受控，选择值与搜索值分离。
- 中文 IME 组合期间不误触发 Enter 选择。
- `Escape` 第一次清空搜索词，第二次只关闭 OptionField。
- 搜索无结果显示明确 Empty 文案。
- 选中项使用勾选图标和文本状态，不只依靠颜色。
- 描述仅用于选项说明，Meta 用于服务类型、默认模型或当前状态。

### 3.4 Dialog Portal 边界

现有 Provider Manager 使用 Radix Dialog 的焦点陷阱和 body pointer lock。Base UI Portal 默认挂到 body 会导致搜索 input 被外层 Dialog 送回触发按钮，因此：

- Provider Manager 存在时，长 Option Portal 定位到 `.provider-manager-sheet`。
- 其他页面仍使用默认 body Portal，避免被普通页面的 `overflow` 裁剪。
- Provider Manager Content 仅对白名单的 `.option-field-positioner`、`.option-field-backdrop` 和 `.option-field-search-input` 放行焦点/交互；普通外部点击仍沿用原 Dialog 保护。
- Radix 短 Select 的 Escape 已验证只关闭 Select，不关闭 Provider Manager。

### 3.5 响应式几何

- 桌面 Popup 宽度为 `max(trigger, 280px)`，最大 420px；短 Select 最大 360px。
- 列表最大高度 360px，并拥有唯一内部滚动区。
- 390px 以下长列表固定为底部 Sheet：`max-height: min(72dvh, 620px)`，保留安全区和拖拽提示条。
- 所有触发器保持 `--control-height-md`，不因选项文本变长而改变布局。
- `prefers-reduced-motion` 下关闭弹层缩放过渡。

## 4. 数据展示辅助函数

`providerOptionItems.ts` 负责把服务端 Provider/Template 映射成 OptionField 展示数据：

- Provider：服务名、默认模型 Meta、禁用服务状态。
- Template：模板描述、文本/图片类型 Meta、集成层级 Group。
- 集成层级稳定排序：官方直连 → 官方兼容层 → 聚合或自建网关 → 自定义兼容接口。

该映射不改变服务端模板顺序、Provider ID、模板 ID 或任何写回值；只改变列表展示顺序和可读字段。

## 5. 自定义模型操作

`ModelOptionInput` 现在把“选择已有模型”和“录入新模型”分成两个明确区域：

- 已有模型使用 OptionField。
- 自定义模型输入提供显式“添加”按钮。
- Enter 仍作为快捷操作，但不再是唯一入口。
- 空白字符串、禁用状态和缺少添加回调时按钮不可用。
- 添加后仍走既有 `withProviderModelOption`，阶段模型仍走既有 `onChange`。

## 6. 构建与依赖

- 新增依赖：`@base-ui/react@^1.6.0`。
- Radix 继续承担短 Select，不引入第二套 CSS 或大型 UI Kit。
- Vite 将 Base UI 与 Radix 拆为独立 vendor chunk，减少主入口体积并改善缓存：本次主入口由 650KB 级降至 458.53KB（minified）。
- `npm audit` 的既有 Vite 5/React Router 6 风险未执行破坏性升级，也未将其与本阶段混合处理。

## 7. 验收证据

### 自动化

- `npm test`：63 个测试文件、215 个测试通过。
- `npm run build`：TypeScript 与 Vite 构建通过。
- `npm run audit:css`：通过；新增 `option-field.css` 已登记为 `design-system` 所有者。
- `git diff --check`：通过。

### 浏览器

真实页面：`http://127.0.0.1:5177/planning`，后端：`http://127.0.0.1:8787`。

- Provider Manager 桌面截图：`.playwright-cli/page-2026-07-24T12-02-52-387Z.png`。
- Provider Manager 390px Bottom Sheet：`.playwright-cli/page-2026-07-24T12-25-08-575Z.png`。
- Stage Inspector 390px Option：`.playwright-cli/page-2026-07-24T12-27-56-892Z.png`。
- 28 个模板在 DOM 中按四组稳定出现；输入“智谱”后只剩 2 个匹配项。
- 搜索 input 自动聚焦，第一次 Escape 清空且保持 Provider Manager，第二次 Escape 只关闭 OptionField。
- 短 Select 打开后有 2 个服务选项，Escape 不关闭外层面板。
- 桌面与 390px 的长列表均无横向溢出；移动端 Popup 底部对齐、列表单一滚动。
- 浏览器 Console：0 errors、0 warnings。

## 8. 未纳入本阶段的后续事项

- Header/Dock 与顶部重复阶段进度：Phase 9.3/9.4。
- 普通 Input、Textarea、Switch、Checkbox、Tooltip、Loader、表单语义：Phase 9.5。
- Info/Summary/Outline/Detail/Text/Cover/Export 的页面差异化布局和 Sidebar：Phase 9.6-9.9。
- 真实 Provider 生成链路和 Phase 8.8 可用额度验收：独立 Provider/全链路门禁。

## 9. 进入 Phase 9.3 的条件

Phase 9.2 已满足：Option 展示统一、长列表可搜索、弹层边界可控、焦点与 Escape 可恢复、移动端可用、构建与 CSS 门禁通过。下一阶段可开始产品导航、Header 清理与 Dock 迁移，但不得把本阶段的 OptionField 再扩展成全表单替换器。
