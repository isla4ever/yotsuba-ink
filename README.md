# Novel Workflow

Novel Workflow 是一个开源的长篇小说生产工作台。

它面向的不是“一次性让 AI 写完整本书”的演示场景，而是希望把小说创作流程做成可配置、可审阅、可追踪、可约束的生产线团队或个人开发者。

核心能力包括：

- 在流水线正式推进前先做 `Story Brief（创作立项）定稿确认`
- 用 `Story Bible / Wiki` 作为运行中的事实层
- 用 `质量阀门` 做 `通过 / 修订 / 阻断` 决策
- 用 `与模型提供方解耦的编排层` 管理规划态和写作态
- 用 `知识库 + 参考资料注入` 提高提示词的落地性

## 产品流程

```text
配置准备
  -> 创作立项定稿
  -> 全书梗概
  -> 分卷大纲
  -> 全书章节细纲
  -> 正文分章生成
  -> 封面 / 导出
```

核心产品决策：

- 只有 `创作立项定稿` 是默认的人类审批闸门。
- `Wiki / Story Bible` 是可写入的连续性事实系统，不是装饰性信息栏。
- `质量阀门` 是执行决策层，不是泛化打分面板。
- `正文` 必须在全书章节细纲完整后才开始生成。

## 仓库结构

本仓库有意保持为单仓 monorepo：

```text
apps/web/                    React 工作台前端
src/novel_workflow/          Python 后端领域逻辑与 API
runtime/novel_workflow/      默认 workflow、prompt、provider 配置与示例
tests/                       面向主产品的回归测试与夹具
docs/                        架构说明与协作开发文档
```

如果你要快速理解工程结构，建议先看：

- [docs/architecture/overview.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/overview.md)
- [docs/architecture/vue-springboot-map.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/vue-springboot-map.md)
- [docs/architecture/story-bible-quality.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/story-bible-quality.md)

## 本地开发

### 后端启动

```bash
.venv/bin/python -m uvicorn novel_workflow.api.app:app --host 127.0.0.1 --port 8787 --reload
```

### 前端启动

```bash
cd apps/web
npm install
npm run dev
```

前端默认地址：[http://127.0.0.1:5173](http://127.0.0.1:5173)

## 运行时目录说明

`runtime/novel_workflow/` 下存放受版本管理的运行时资源：

- `workflows/`：默认工作流定义
- `prompts/`：阶段 prompt 模板
- `providers/`：provider 配置
- `examples/`：最小示例输入

运行后产生的状态数据默认不纳入源码管理：

- `runtime/novel_workflow/runs/`
- `runtime/novel_workflow/wiki/`
- `runtime/novel_workflow/references/`
- `runtime/novel_workflow/knowledge/`

## 质量理念

这个项目优先解决真正会把长篇小说生产链路搞坏的失败模式：

- 人物连续性断裂
- 世界观硬设定冲突
- 伏笔投放后失联或被遗忘
- 章节承接断层
- 细纲覆盖不完整
- 明明局部修订即可修复，却被迫整章重写

## 工程规则

本仓库遵循 Ponytail 风格的仓库级工程纪律：

- 文件保持小而清晰
- 职责一旦混杂，尽早拆分
- 优先显式合同，而不是隐式耦合
- 新增依赖前先复用现有本地能力

详细规则见：

- [docs/engineering/ponytail.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/engineering/ponytail.md)
- [docs/engineering/sources.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/engineering/sources.md)
- [AGENTS.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/AGENTS.md)

## 验证命令

```bash
cd apps/web && npm run build
.venv/bin/python -m pytest tests/test_workflow_runner.py -q
```
