# 如何新增一个阶段

Yotsuba Ink 当前只允许在 Phase 27 LangGraph 主线上新增阶段。先更新阶段产物合同，再同步运行时、模板和前端投影，不再向旧的 `info/summary/outline` 阶段或旧 Runner 增加兼容入口。

## 1. 先定义合同

- 阅读 [`stage-artifact-contract.md`](../architecture/stage-artifact-contract.md)。
- 在 `src/novel_workflow/output_contracts/` 定义输入、输出、引用和写回约束。
- 明确阶段 id、上游依赖、用户决策和下游消费方。

## 2. 接入 LangGraph

- 在 `src/novel_workflow/runtime/graph/` 更新图状态、上下文编译和阶段执行。
- 通过 `src/novel_workflow/runtime/graph/execution_service.py` 进入生产执行路径。
- Provider 请求必须走冻结的合同编译器和 usage receipt，不能添加隐式 fallback 或旧 runtime selector。

## 3. 更新官方模板

三套官方模板位于 `runtime/novel_workflow/workflows/official-deepseek-fast.json`、`official-deepseek-balanced.json` 和 `official-deepseek-deep.json`，需要保持阶段顺序、Provider 绑定和 prompt id 一致。

## 4. 更新前端投影

- `apps/web/src/features/pipeline/contracts/`：共享类型与事件合同。
- `apps/web/src/features/pipeline/running/`：运行态产物和决策面板。
- `apps/web/src/features/pipeline/planning/`、`settings/`：配置、模板和 Provider 回显。
- 纯布局/校验逻辑放到 `lib/`，不要在组件内复制合同解析。

## 5. 验证

至少补齐后端合同、图执行、Provider 编译和 API 测试，并运行 `.venv/bin/pytest -q`、`cd apps/web && npm test && npm run build`。真实 Provider 验收另行记录，离线测试不能替代真实模型质量结论。
