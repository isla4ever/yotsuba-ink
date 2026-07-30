# Overlay 与反馈状态合同

本文档冻结 Yotsuba Ink 的 Dialog、Sheet、Tooltip、空状态和错误状态行为。业务弹层继续归属 `planning/`、`running/`、`settings/` 或 `layout/`，不新建通用 Dialog 业务目录。

## 1. Overlay 行为

- 手写 Dialog 和 Sheet 必须 Portal 到 `document.body`。
- Dialog 使用 `role="dialog"`、`aria-modal="true"` 和可读名称。
- 打开时焦点进入弹层容器，关闭后恢复到原触发控件。
- `Tab` 和 `Shift+Tab` 不得离开当前弹层。
- `Escape`、遮罩点击和关闭按钮统一调用同一个 `onClose`。
- 弹层打开期间锁定页面滚动；嵌套弹层使用计数锁，关闭内层不能提前解锁外层。
- 弹层最大高度基于 `100dvh`，内容滚动发生在弹层内部，不得被 Header、侧栏或工作台 `overflow` 裁切。

共享行为由 `state/useOverlayDialog.ts` 提供。Radix Dialog 已自带焦点管理，继续使用 Radix 行为，只接入视觉和状态 Token。

## 2. 视觉层级

- `app-overlay-backdrop`：全局遮罩、视口留白和 Overlay z-index。
- `app-dialog-surface`：全局居中编辑、确认和详情弹层。
- `app-sheet-surface`：历史、运行详情和配置抽屉等侧边 Sheet。
- 业务类名继续负责内容布局；共享类只负责视口、焦点和通用表面合同。
- 模式色只用于当前模式或阶段状态，不用模式色覆盖整个遮罩。

## 3. Tooltip

- 无可见文字的全局图标按钮必须同时具备 `aria-label` 和 Tooltip。
- Tooltip 支持悬停与键盘焦点，通过 `aria-describedby` 关联。
- 普通标题、可见文本按钮和熟悉的表单控件不重复增加 Tooltip。
- Tooltip 使用轻量本地实现，不为简单提示增加大型运行时依赖。

## 4. 空状态与错误状态

- 空状态描述“尚未产生什么”和“什么事件会让它出现”，不展示模拟成功数据。
- 错误状态使用 `role="alert"`，提供返回、重试或可执行的修复入口。
- 加载、空、结构无效、执行失败和显式 Fixture 必须保持不同状态。
- 没有真实质量事件时显示等待状态，不能生成模拟评分或通过记录。
- 知识库上传/删除失败必须保留文件选择或重新操作入口，不能只显示错误文本。

## 5. 验收矩阵

- Desktop：1280x920、1440x900。
- Mobile：390x844。
- Theme：Dark、Light。
- Mode：Fast、Balanced、Deep。
- 行为：打开、Tab/Shift+Tab、Escape、遮罩关闭、嵌套弹层、焦点恢复。
- 视觉：弹层不出视口、不横向溢出、长中文和模型名不遮挡操作。
- 反馈：空态不伪造成功，错误态有明确恢复动作。
- 浏览器：0 error、0 warning。
