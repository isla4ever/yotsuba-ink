# 后端链路

## 职责

后端是一个 FastAPI 应用，负责提供工作流配置、运行执行、知识库接入，以及运行时事件流输出。

## 入口文件

- API 应用入口：[src/novel_workflow/api/app.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/api/app.py)
- 应用状态初始化：[src/novel_workflow/api/bootstrap.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/api/bootstrap.py)
- Runner 门面：[src/novel_workflow/workflows/runner.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/workflows/runner.py)

## 一次运行的生命周期

1. 前端通过 `runs` 路由发起一次运行。
2. 后端读取工作流定义并创建 run 记录。
3. `NovelWorkflowRunner` 开始流式执行并持续发事件。
4. 编排辅助模块在执行过程中处理质量检查、记忆读取、修订和写回。
5. `run_store` 持久化状态快照、事件和产物。

## 模块地图

- `api/bootstrap.py`：应用状态初始化和默认数据种子写入
- `api/dependencies.py`：薄依赖辅助函数
- `api/sse.py`：流式响应和 SSE 事件封装
- `api/routes/workflow.py`：工作流读取与保存
- `api/routes/runs.py`：运行创建、流式执行、暂停、恢复、审批
- `api/routes/knowledge.py`：知识库上传、列表、搜索、删除
- `api/routes/references.py`：参考资料检索接口
- `references/context_injection.py`：参考资料摘要合并与运行前注入
- `providers/registry.py`：Provider 注册和环境变量驱动的实例化
- `workflows/templates.py`：默认 workflow、prompt、provider 配置
- `orchestration/*`：按职责拆开的执行辅助逻辑
- `quality/engine.py`：质量分析与问题发现
- `memory/wiki.py`：Wiki / Story Bible 写回
- `storage/run_store.py`：运行状态持久化

## SSE 事件流

后端会输出一组领域事件，前端必须把它们当成运行态合同来消费，而不是去解析文本产物。

常见事件包括：

- 运行生命周期：`run_started`、`run_completed`、`run_paused`、`run_resumed`
- 阶段生命周期：`node_started`、`node_completed`、`node_failed`
- 质量相关：`quality_check_started`、`quality_check_completed`、`revision_directive_created`
- 记忆相关：`memory_context_loaded`、`memory_writeback_completed`、`story_bible_updated`
- 审批相关：`approval_required`、`artifact_approved`、`brief_regenerated`
