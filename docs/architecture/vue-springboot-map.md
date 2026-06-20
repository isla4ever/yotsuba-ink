# Vue / Spring Boot 对照理解

这篇文档是给熟悉 Vue 和 Spring Boot、但不熟悉 React 和 FastAPI 的开发者看的。

## 前端心智对照

- React component 大致等于 Vue component
- React hook 大致等于 Vue composable
- `useState` / `useMemo` / `useEffect` 大致等于 `ref` / `computed` / `watchEffect`
- `useNovelWorkflowApp.ts` 可以理解成一个比较大的 feature composable 加局部 store
- `PlanningWorkbench.tsx`、`RunningWorkbench.tsx` 这类文件，可以理解成页面级容器组件
- `services/*.ts` 基本就是你的 API client 层

## 后端心智对照

- FastAPI route 大致等于 Spring `@RestController`
- `api/routes/*.py` 可以理解成按资源拆分的控制器
- `orchestration/*.py` 大致等于 Spring `Service`
- `storage/*.py` 大致等于 `Repository + 文件型持久化`
- Pydantic model 大致等于 DTO / 请求响应模型
- SSE 流大致等于 `SseEmitter` 风格的事件推送

## 如果你是 Vue 背景，建议先看

1. [apps/web/src/App.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/App.tsx)
2. [apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts)
3. [apps/web/src/features/pipeline/planning/PlanningWorkbench.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/planning/PlanningWorkbench.tsx)

## 如果你是 Spring Boot 背景，建议先看

1. [src/novel_workflow/api/app.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/api/app.py)
2. [src/novel_workflow/api/routes/runs.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/api/routes/runs.py)
3. [src/novel_workflow/workflows/runner.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/workflows/runner.py)

## 推荐阅读顺序

如果你想搞懂“点击开始运行之后到底发生了什么”，建议按这个顺序看：

1. 前端 `runWorkflow()`
2. 前端 `services/runApi.ts`
3. 后端 `api/routes/runs.py`
4. 后端 `workflows/runner.py`
5. 前端 `state/appEvents.ts`

这条链路就是当前产品的核心主循环。
