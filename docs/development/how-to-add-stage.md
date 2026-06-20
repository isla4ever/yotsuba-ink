# 如何新增一个阶段

当你准备给工作流新增一个阶段时，建议按下面这份检查单来做。

## 1. 先定义 workflow 节点

优先从这里开始看：

- [src/novel_workflow/workflows/templates.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/workflows/templates.py)
- [runtime/novel_workflow/workflows/default-novel-workflow.json](/Users/isla/Desktop/project/multi-stage-creation-model-end/runtime/novel_workflow/workflows/default-novel-workflow.json)

你通常需要补齐：

- 节点 id
- 节点 type
- prompt template id
- provider profile 绑定
- input schema
- quality policy
- 如果适用，还要配置 variant policy

## 2. 注册阶段行为

重点检查：

- [src/novel_workflow/stages/registry.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/stages/registry.py)
- [src/novel_workflow/stages/prompt_plan.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/stages/prompt_plan.py)

确保这个阶段有：

- 清晰的输入合同
- 清晰的输出合同
- 明确的记忆读写意图
- 失败处理预期

## 3. 评估它对编排层的影响

如果这个阶段会影响运行控制、质量闭环或写回逻辑，就继续看：

- `src/novel_workflow/orchestration/`
- `src/novel_workflow/quality/`
- `src/novel_workflow/memory/`

典型问题包括：

- 它是否需要审批暂停？
- 它是否要写回 Story Bible？
- 它的质量问题是否会阻断后续阶段？

## 4. 在前端暴露这个阶段

重点看这些地方：

- [apps/web/src/features/pipeline/contracts/workflow.ts](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/contracts/workflow.ts)
- [apps/web/src/features/pipeline/planning/PipelineCanvas.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/planning/PipelineCanvas.tsx)
- [apps/web/src/features/pipeline/planning/StageInspector.tsx](/Users/isla/Desktop/project/multi-stage-creation-model-end/apps/web/src/features/pipeline/planning/StageInspector.tsx)
- 运行态视图：`apps/web/src/features/pipeline/running/`

前端通常要补：

- 阶段标签与默认值
- Inspector 字段
- 画布位置
- 如果这个阶段产物特殊，还要补运行态展示

## 5. 增加测试

至少要更新：

- [tests/test_workflow_runner.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/tests/test_workflow_runner.py)

测试通常要覆盖：

- 编排顺序是否正确
- 阶段输出或副作用是否符合预期
- 如果有特殊审批或质量行为，也要覆盖

## 一个很实用的判断标准

如果新增一个阶段需要你同时去改很多不相关的页面、零散 helper 和到处字符串匹配的事件逻辑，那先别急着继续堆代码。通常这说明合同边界没有收好，应该先把边界拉回一个明确位置。
