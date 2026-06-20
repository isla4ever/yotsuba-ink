# 参考来源与复用说明

本仓库只保留轻量级来源说明，不再内置大体量第三方快照代码。

## 前端参考

- `xyflow/react`：画布和 minimap 的基础能力
- `react-force-graph-2d`：当前人物关系图的渲染基础
- `Radix UI`：Dialog、Tabs、Switch、Tooltip 等基础交互原语
- `lucide-react`：图标系统

## 产品参考项目

- `bytedance/flowgram.ai`：适合作为 AI workflow 产品体验参考
- `synergycodes/workflowbuilder`：适合作为 schema-driven workflow builder 参考

这些只是产品和工程参考，不是运行时依赖。

## 后端参考

- 当前后端结构部分借鉴了 FastAPI + Pydantic 的常见服务组织方式
- Provider 适配层仍然保持项目自有、轻量、可控

## 许可证原则

只有在符合本仓库许可证策略的前提下，才会真正引入外部代码。绝大多数外部项目只作为参考，不默认并入仓库。
