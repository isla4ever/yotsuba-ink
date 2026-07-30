# 架构总览

## 仓库里有什么

Yotsuba Ink 是一个单仓产品，当前可以理解成五层：

```text
apps/web                    前端工作台
src/novel_workflow         后端 API 与领域逻辑
runtime/novel_workflow     默认运行时资源
tests                      回归测试与测试夹具
docs                       产品与工程文档
```

## 从哪里开始看

- 产品生产模式主线：[docs/architecture/product-production-workflow.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/product-production-workflow.md)
- 阶段 Artifact 合同：[docs/architecture/stage-artifact-contract.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/stage-artifact-contract.md)
- 三档模式、运行状态与 SSE 事件矩阵：[docs/architecture/run-state-event-matrix.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/run-state-event-matrix.md)
- 设计 Token 与全局 UI 验收合同：[docs/architecture/design-system-foundation.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/design-system-foundation.md)
- Overlay、Tooltip、空状态与错误状态合同：[docs/architecture/overlay-feedback-contract.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/overlay-feedback-contract.md)
- 前端入口：[apps/web/src/App.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/App.tsx)
- 前端应用状态：[apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/state/useNovelWorkflowApp.ts)
- 后端入口：[src/novel_workflow/api/app.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/api/app.py)
- 后端运行时初始化：[src/novel_workflow/api/bootstrap.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/api/bootstrap.py)
- Workflow Runner 门面：[src/novel_workflow/workflows/runner.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/workflows/runner.py)

## 一次产品请求是怎么流动的

1. 用户在规划态工作台中配置工作流。
2. 前端通过 API 把 workflow 和阶段配置保存到后端。
3. 用户点击开始运行。
4. 后端读取 workflow、prompt、provider 和运行时存储。
5. Runner 开始编排阶段并持续发出 SSE 事件。
6. 前端把 SSE 事件归并成运行态状态，并驱动阶段页面更新。
7. 执行过程中会持续写回 Story Bible、Wiki、质量报告和运行产物。

## 主要后端模块

- `api/`：FastAPI 启动和路由注册
- `api/routes/`：按资源拆分的 HTTP 入口
- `workflows/`：workflow schema、默认模板、编译和 runner 门面
- `orchestration/`：阶段切换和执行辅助逻辑
- `quality/`：质量引擎
- `memory/`：Wiki / 连续性写回
- `knowledge/`：文档接入、切块、存储和检索
- `references/`：外部参考资料检索与注入
- `providers/`：模型适配和注册表
- `usage/`：token 与使用量数据模型
- `storage/`：基于 JSON 的持久化存储

## 主要前端模块

- `layout/`：头部和全局壳层
- `planning/`：规划/配置态界面
- `brief/`：Story Brief 和参考资料录入
- `running/`：运行态界面和执行诊断
- `settings/`：设置弹窗和 Provider 配置
- `services/`：API 请求与事件流处理
- `state/`：应用状态、持久化、SSE 事件归并
- `contracts/`：workflow 和事件合同
- `lib/`：纯函数与格式化辅助

## 运行时资源

`runtime/novel_workflow/` 下面受版本管理的内容属于产品默认资源：

- `workflows/default-novel-workflow.json`
- `prompts/*.json`
- `providers/*.json`
- `examples/*.md`

运行后生成的 `runs/`、`wiki/`、`references/`、`knowledge/` 属于本地状态数据，不是源码。
