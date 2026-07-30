# Phase 9.5A：Guided Setup 表单系统第一批

> 状态：已实施并完成浏览器验收
>
> 日期：2026-07-24
>
> 范围：仅首次准备 Guided Setup；Settings、阶段配置抽屉和运行写回表单留给 Phase 9.5B，不在本批复制控件或改变业务语义。

## 1. 产品决策

首次配置的核心问题不是缺少更多 Tab，而是用户无法快速判断“当前步骤、完成比例、还差什么”和“哪些字段是同一类信息”。因此本批保留既有五步状态机，只提升信息层级和表单几何：

- 步骤 rail 继续由 `useSetupFlow` 控制，用户仍可回看已完成步骤，阻塞项仍由 `buildSetupSteps` 派生。
- 在步骤列表下增加线性进度条，移动端保留 `1/5` 文本，进度条使用 `role="progressbar"` 与当前步骤值，不承担新的校验逻辑。
- Story Brief 使用 12 列语义栅格：题材、篇幅、目标字数、目标读者等短字段等宽两列；核心创意、关键词和禁忌等长内容整行占满。
- 移动端所有 Brief 字段回落为单列，控件尺寸和触控目标不因字段类型发生跳变。
- 没有把字段包成额外的卡片；继续使用编辑工作区和分隔线，避免 AI 卡片堆叠感。

## 2. 实现边界

### 进度表达

`SetupStepNavigation` 计算当前步骤索引和百分比，渲染：

- 桌面：左侧步骤列表 + 底部细进度条。
- 移动：当前步骤 `1/5` + 细进度条，步骤列表仍由原有导航逻辑控制。
- `aria-valuemin`、`aria-valuemax`、`aria-valuenow` 与 `aria-label="首次准备进度"` 保证辅助技术可以读取进度。

### 表单几何

`guided-setup.css` 只作用于 Guided Setup 的 Brief：

- `repeat(12, minmax(0, 1fr))` 作为桌面基准。
- 普通短字段 `span 6`，文本域、标签输入和显式 `wide` 字段 `1 / -1`。
- 所有输入、Select、Textarea、Tag Box 统一 `width: 100%` 和最小高度；标签区域提供稳定的 24px 纵向占位，避免必填徽标导致上下跳动。
- `max-width`、内部滚动和底部动作栏保持不变，长字段仍在工作区内部滚动。

## 3. 不变合同

- 字段 key、默认值写回、`updateStageInputDefault`、标签去重和自动保存不变。
- `useSetupFlow` 的前进、返回、阻塞聚焦、最后步骤创建运行和失败恢复不变。
- AI 服务检查、参考资料选择、质量模式三档语义不变。
- 不新增组件目录，不安装 UI 或动效依赖。

## 4. 浏览器验收

### Desktop 1440 x 1000

- Story Brief 短字段等宽双列。
- `核心创意/冲突`、`关键词`、`禁忌/不要出现` 整行占满 840px 内容列。
- 步骤 rail 显示 5 个步骤和进度条；当前阻塞项仍以警示状态显示。
- Screenshot：`.playwright-cli/page-2026-07-24T13-21-21-361Z.png`。

### Mobile 390 x 844

- Brief 栅格为单列，长字段宽度为 362px。
- `body.scrollWidth === document.documentElement.scrollWidth === 390`。
- 底部动作栏固定，表单内容由内部滚动区承载，不产生页面级横向滚动。
- Console：0 errors、0 warnings。
- Screenshot：`.playwright-cli/page-2026-07-24T13-21-45-377Z.png`。

## 5. 下一批

Phase 9.5B 先复用本批几何合同，迁移 Settings Overview、Provider Manager、阶段配置抽屉和阶段写回表单；迁移前逐个确认字段归属、错误定位、草稿恢复和异步 Busy 状态，不做全仓 CSS 机械替换。
