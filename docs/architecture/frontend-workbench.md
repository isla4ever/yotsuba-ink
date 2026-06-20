# 前端工作台

## 职责

前端是一个 React 工作台，当前有两个主要产品状态：

- `planning`：配置流水线、调整阶段、查看规划态信息
- `running`：跟踪阶段执行、查看运行中产物和质量反馈

## 入口文件

- 应用壳层：[apps/web/src/App.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/App.tsx)
- 应用状态 Hook：[apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts)
- 规划态工作台：[apps/web/src/features/pipeline/planning/PlanningWorkbench.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/planning/PlanningWorkbench.tsx)
- 运行态工作台：[apps/web/src/features/pipeline/running/RunningWorkbench.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/running/RunningWorkbench.tsx)

## 数据流

1. `useNovelWorkflowApp` 持有应用级状态。
2. `services/` 封装 API 请求和 SSE 消费逻辑。
3. `state/appEvents.ts` 把后端事件规约成前端状态变化。
4. 各个 workbench 再根据 props 组装局部 UI。

## 关键模块

- `layout/AppHeader.tsx`：顶部头部、全局控制、进度展示
- `planning/PipelineCanvas.tsx`：规划态画布与布局持久化
- `planning/StageInspector.tsx`：阶段配置检查器
- `running/StageRunWorkbench.tsx`：运行态主工作台
- `settings/KnowledgeBaseManagerDialog.tsx`：知识库上传和管理
- `settings/SettingsDialog.tsx`：Provider 和运行设置

## 为什么要这样拆

这样拆的目的，是避免 UI 组合、API 请求、事件归并和状态持久化全都塌进一个大 Hook 或一个大页面组件里。

基本规则是：

- workbench 决定页面布局
- 组件负责局部 UI 呈现
- `services` 负责和后端通信
- `state` 负责把后端事件翻译成前端状态

## 当前仓库约定的前端结构

- `layout/`：应用壳层和头部控制
- `planning/`：配置态工作台
- `brief/`：Story Brief 与参考资料输入
- `running/`：运行态工作台和执行诊断
- `settings/`：弹窗设置与 Provider 字段组件
- `state/`：应用级 Hook、持久化、自动保存、事件归并
- `services/`：API 和 SSE IO
- `contracts/`：类型合同
- `lib/`：纯格式化和转换辅助函数
