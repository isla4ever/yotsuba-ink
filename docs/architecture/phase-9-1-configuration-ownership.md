# Phase 9.1 配置语义、字段唯一归属与双态设置合同

> 状态：已完成（2026-07-24）
> 上游基线：`phase-9-0-baseline-and-decision-freeze.md`
> 不改变：阶段 Artifact、Provider 请求、预算与 Fallback、SSE、Run、恢复、导出和正式写回语义

## 1. 本阶段目标

Phase 9.1 消除“首次用户面对四个技术 Tab、同一模型在多个位置重复配置、只读能力伪装成可选开关”的问题。配置体验固定为两种状态：

1. 尚有真实阻塞项时，在 Planning 主工作面显示五步首次准备。
2. 准备完成后，设置入口显示一张可扫描的单页总览。

是否需要首次准备只能由当前 Workflow、Knowledge 和服务端 Provider Readiness 派生。不得新增 `setupCompleted`、动画完成标记或人工维护的步骤完成布尔值。

## 2. 五步顺序与完成条件

| 顺序 | 用户任务 | 真实数据源 | 完成条件 | 唯一主编辑面 |
| --- | --- | --- | --- | --- |
| 1 | 故事起点 | Info Stage 输入 | 当前启动必填 Story Brief 有效 | `StoryBriefFields` |
| 2 | 创作依据 | Info 参考字段、Knowledge 列表 | 方式有效；已选资料均可用；空参考只产生 Warning | `ReferenceResearchPanel` / Knowledge Manager |
| 3 | AI 服务 | Provider Profile、服务端 Readiness | 当前 Workflow 使用的文本和封面服务配置就绪 | `ProviderManagerSheet` |
| 4 | 质量方式 | `workflow.quality_mode` 及其派生策略 | Fast / Balanced / Deep 之一有效 | `CreationModeSetupSection` / Header 模式控件 |
| 5 | 确认启动 | 前四步聚合 | 无 Blocking；Warning 可明确保留 | `SetupReviewSection`，只汇总不重复输入 |

步骤导航只保存最后访问位置、方向、焦点和提交 UI 状态。字段值仍由现有 Workflow、Knowledge 与 Provider 生命周期拥有。

## 3. 字段唯一归属

| 配置对象 | 唯一主编辑位置 | 其他页面只允许 | 删除的重复入口 |
| --- | --- | --- | --- |
| Story Brief | 首次“故事起点”与 Planning Info 共用的字段组件 | 一行摘要、缺项定位 | Settings 中复制题材/简介表单 |
| 参考方式与资料选择 | 首次“创作依据”与 Info 参考组件 | 模式、资料数、状态摘要 | Settings 再建参考 Tab |
| Knowledge 文档生命周期 | Knowledge Manager | 可用数量、索引状态、打开管理器 | 首次流程维护第二份上传队列 |
| Quality Mode | 首次“质量方式”与 Header 共用模式合同 | 模式与人工干预摘要 | 独立运行策略 Tab |
| Provider Profile、Base URL、Secret | AI 服务管理面 | 厂商、类型、密钥状态、就绪摘要 | 每阶段复制连接表单 |
| 默认文本/封面模型 | AI 服务管理面 | Stage 显示继承结果 | “全局模型”与“模型接口”分别编辑 |
| 阶段 Provider、模型、Fallback | 对应 Stage Inspector 的“阶段例外” | Settings 显示例外数量并定位 | Settings 展开七阶段覆盖表单 |
| 自动保存、运行前检查、资产校验 | 系统能力 | 只读状态行 | `checked readOnly` Checkbox |
| 阶段 ID、Output Key | 诊断合同 | 普通界面不展示 | 普通用户高级表单 |

## 4. 普通用户术语

| 内部或旧名称 | 普通界面名称 |
| --- | --- |
| Provider / 模型接口 | AI 服务 |
| 默认文本接口 | 文本生成服务 |
| 默认图片接口 | 封面生成服务 |
| 全局模型 | 默认生成模型 |
| 阶段覆盖 | 阶段例外 |
| 运行策略 | 自动保护 |
| 轻量连通测试 | 检查连接 |
| 获取模型列表 | 同步可用模型 |
| Memory Read / Write | 使用已有设定 / 定稿后更新设定 |

错误必须回答发生了什么、当前内容是否保留、下一步可执行什么。Secret 草稿不得进入 Workflow 或浏览器持久化；切步骤、关闭 Sheet、Escape 和遮罩关闭继续走 Dirty Guard。

## 5. 副作用边界

- 切换步骤和 Settings Section 不创建 Run、不连接 SSE、不恢复快照、不触发生成、不正式写回 Artifact。
- Provider Readiness 只做配置完整性检查；“检查连接”和“同步可用模型”仍是用户显式命令。
- “开始创作”复用现有 `runWorkflow`，并在调用前重新检查当前纯派生结果。
- 首次从服务端加载默认 Workflow 只建立自动保存基线。在首次 Hydration 完成前自动保存关闭；服务端对象进入前端状态后，首次 Effect 不发起 `POST /api/workflows`。
- 历史 Run Hydration 在写入 React 状态前，把同一个 Workflow 对象登记为只读 Hydration 对象。只要后续 Effect 仍重放这个对象身份，就持续抑制自动保存，而不是只跳过一次 Effect。
- 用户真实编辑必须产生新的不可变 Workflow 对象。新对象不再命中 Hydration 身份，恢复正常的 800ms 防抖自动保存。
- Hydration 会使旧保存 Revision 失效；即使旧请求稍后返回，也不能把 Header 从空闲态错误改成“已保存”或“保存失败”。
- React Flow 的 `fitView`、ResizeObserver 重排和阶段自动定位属于程序化画布移动。`onMoveEnd` 没有真实交互事件时不得持久化 Viewport，也不得间接创建新 Workflow 对象。
- 历史 Run 打开后 Header 必须立即回到“配置尚未修改”；只有历史恢复之后发生真实字段编辑、节点拖动或用户画布移动，才允许进入“正在保存”。

## 6. 验收记录

### 6.1 自动化门禁

| 门禁 | 结果 | 证据 |
| --- | --- | --- |
| Frontend 全量单元测试 | 通过 | `61` 个测试文件、`211 passed`；包含 `workflowAutosave.test.ts` 的 3 条身份与 Revision 回归测试 |
| Backend 目标回归 | 通过 | Provider Readiness、Recovery、Run History、History Contract、Stream Lease 共 `31 passed`；仅保留既有 Starlette/httpx 弃用警告 |
| Frontend Production Build | 通过 | TypeScript 与 Vite Build 完成，`3311 modules transformed` |
| CSS Audit | 通过 | `npm run audit:css` 退出码为 0；审计结果继续作为 Phase 9 后续样式收敛基线，不把重复选择器数量误写为已清零 |
| Diff 格式检查 | 通过 | `git diff --check` 无错误 |

### 6.2 首次准备与设置双态

- Guided Setup 已覆盖故事起点、创作依据、AI 服务、质量方式和确认启动五步；完成状态来自 Workflow、Knowledge 与 Provider Readiness，不存在第二套 `setupCompleted` 数据。
- 首次准备在 `320 / 390 / 768 / 1024 / 1440` 视口完成布局检查；`200% Zoom` 下仍保留单一可达主流程，没有横向页面溢出或被遮挡的主操作。
- Dark、Light、Keyboard 与 Reduced Motion 均沿用设计系统状态合同；步骤按钮、字段、Sheet 和 Dialog 保留可见 Focus，Reduced Motion 不依赖动画完成来推进业务状态。
- Settings 已从交叉 Tab 配置改为单页总览；摘要只负责定位唯一编辑面，不复制 Story Brief、参考方式、默认服务或七阶段覆盖表单。
- 视觉证据保存在 `output/playwright/phase91/`，覆盖 Guided Setup Story/AI/Review、Settings、Provider Manager、共享 Readiness 阻断态和多视口阻断态。

### 6.3 配置命令与网络副作用

- Guided Setup 步骤切换、Settings Section 定位、Readiness 展示和摘要展开不创建 Run、不连接 SSE、不恢复快照、不触发模型生成。
- Provider 创建、编辑、删除、连接检查与模型同步仍走各自显式命令；Secret 草稿不写入 Workflow，本地关闭继续经过 Dirty Guard。
- 默认文本/封面服务只在 AI 服务管理面编辑；阶段 Inspector 只承担阶段例外，Settings 仅显示例外数量和定位入口。
- 自动保存、运行前检查和资产校验以只读能力状态展示，不再伪装成可勾选配置。

### 6.4 历史运行与默认工作流保护

真实回归链路：

`/planning -> 创作历史 -> phase86b-export-acceptance -> 打开运行 -> /run/export`

验收结果：

- Header 始终显示“配置尚未修改”，没有无请求的持续“正在保存”。
- 页面恢复为“导出产物待确认 · 3/4 · 等待人工确认”，历史 Run 的阶段、人工决策与路由一致。
- 页面横向溢出为 `0`，应用控制台错误和警告均为 `0`。
- 打开历史 Run 后等待 1.6 秒，服务端默认 Workflow 的修改时间与 SHA-256 均未变化，证明没有隐式保存请求。
- 默认 Workflow 保持 `balanced`；文本服务为智谱 GLM（`glm-5.2`），封面服务为智谱 CogView（`glm-image`），七个阶段模型均保持 `gpt-4.1-mini`。
- 默认 Workflow 文件 SHA-256 为 `f6e51c0e3dba9ec88581a801285f422e4cc88a1aab8503f63cebfc87f4a67233`。

## 7. Phase 9.2 准入

Phase 9.1 的字段唯一归属、双态设置和历史 Hydration 副作用问题已关闭。下一阶段可以进入 Phase 9.2 OptionField 与表单几何统一，但继续遵守以下边界：

- 不顺带重做 Dock、Header 视觉或三档模式遮罩；这些按总体路线图单独验收。
- OptionField 只统一字段容器、Label、Help、Error、长度和响应式几何，不复制字段所有权。
- 每一批替换都必须验证 Guided Setup、Settings Overview、Stage Inspector 与 Provider Manager 的真实可达性。
- 任何表单视觉改动都不得重新引入历史 Hydration 保存、程序化 Viewport 保存或 Secret 持久化副作用。
