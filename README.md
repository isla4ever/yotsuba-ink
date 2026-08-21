<div align="right"><a href="./README.en.md">English</a></div>

<div align="center">
  <img src="docs/assets/branding/yotsuba-ink-logo.png" alt="Yotsuba Ink" width="112" />
  <h1>Yotsuba Ink</h1>
  <p><strong>AI 原生长篇小说创作工作台</strong></p>
  <p>用可审阅的阶段产物、连续性上下文和可恢复运行，完成从故事立项到整书导出的长篇创作流程。</p>
  <p>
    <img src="https://img.shields.io/badge/version-v1.1.0-2f9e78" alt="v1.1.0" />
    <img src="https://img.shields.io/badge/Python-3.12%2B-3776ab" alt="Python 3.12+" />
    <img src="https://img.shields.io/badge/Node.js-22%2B-43853d" alt="Node.js 22+" />
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-68717a" alt="Apache-2.0" /></a>
  </p>
</div>

<p align="center">
  <a href="#产品工作流">产品工作流</a> ·
  <a href="#三档创作模式">创作模式</a> ·
  <a href="#v11-version-20-创作工作台">v1.1</a> ·
  <a href="#v10-长篇实证">v1.0 实证</a> ·
  <a href="#快速开始">快速开始</a>
</p>

<p align="center">
  <img src="docs/assets/branding/yotsuba-ink-product-hero.png" alt="Yotsuba Ink 长篇创作生产工作台概念主视觉" width="100%" />
</p>

Yotsuba Ink 面向需要持续控制结构、人物、连续性和版本的长篇创作。它把模型调用组织为一条有明确产物、人工决策、质量边界和恢复记录的生产链路，而不是把整本书交给一次对话生成。

## v1.1： Version 20 创作工作台

v1.1 将 Figma Make Version 20 设计完整迁入唯一生产前端，并继续沿用同一套 FastAPI、LangGraph、Artifact、SSE 与 Provider 合同。仓库内不再保留旧前端入口、双 Router 或第二套主题。

- **连续流水线目录**：八个阶段以单轨生产链展示，模板主体、查看配置和使用流程均连接真实工作流接口。
- **阶段化创作工作台**：Spine 因果链、Cast 名册、Volumes 卷册、Detail/Text 章节各自保留统一宽度的二级导航；Header 使用克制的实时 ECG 轨迹。
- **运行监控与 Story Bible**：监控台按阶段切换真实 Artifact、正文、Provider 使用量与事件日志；人物、事实、伏笔和世界规则来自后端读模型。
- **精细模式作者协作**：在 Spine、Cast、Volumes、Detail、Text 中提供讨论、方案与可审阅改稿；上下文回执、选区绑定、历史线程、SSE 和 patch 写回均由后端合同约束。
- **统一加载与过渡**：全局和局部加载器互斥，异步内容淡入，Reduced Motion 下停止持续动画。

<table width="100%">
  <tr>
    <td width="50%"><img src="docs/assets/screenshots/v1.1-workflow-pipelines.jpg" alt="v1.1 连续流水线目录" /></td>
    <td width="50%"><img src="docs/assets/screenshots/v1.1-workflow-config.jpg" alt="v1.1 八阶段稿件栈配置" /></td>
  </tr>
  <tr>
    <td align="center">连续流水线目录</td>
    <td align="center">八阶段稿件栈配置</td>
  </tr>
</table>

本版本的本地合同、fake Provider、前端构建与浏览器门禁独立记录；精细模式作者协作的真实 Provider 质量与成本仍需全新 Deep Run 验收，不由离线测试替代。完整版本记录见 [CHANGELOG](CHANGELOG.md)。

## 产品工作流

每个阶段只负责一个核心 Artifact。上游定稿后才进入下游，正文按章节顺序生成并继承上一章的最终状态。

```mermaid
flowchart TB
  idea["创作想法"] --> brief

  subgraph planningStage["01 规划"]
    direction LR
    brief["Brief<br/>立项与故事承诺"] --> spine["Spine<br/>全书因果脊柱"] --> cast["Cast<br/>人物与关系边界"]
  end

  subgraph architectureStage["02 架构"]
    direction LR
    volumes["Volumes<br/>自然分卷与闭合"] --> detail["Detail<br/>章节剧本与交接"]
  end

  subgraph productionStage["03 生产与交付"]
    direction LR
    text["Text<br/>相邻章节顺序生成"] --> qualityGate{"合同与质量门"} -->|通过| cover["Cover<br/>视觉元数据与资产"] --> export["Export<br/>版本与交付文件"]
  end

  cast --> volumes
  detail --> text
  qualityGate -->|明确硬问题| revision["最多一次定向修订"] --> text
  qualityGate -.->|软问题| evidence["Evidence<br/>证据与告警"]

  classDef planning fill:#102a24,stroke:#2fd68f,color:#f2fff9;
  classDef writing fill:#172433,stroke:#69a7e8,color:#f4f8ff;
  classDef decision fill:#302819,stroke:#d8ad54,color:#fff9ec;
  classDef delivery fill:#26203a,stroke:#9a7ce2,color:#fbf8ff;
  class brief,spine,cast,volumes,detail planning;
  class text,evidence writing;
  class qualityGate,revision decision;
  class cover,export delivery;
```

<table width="100%">
  <thead><tr><th width="14%">阶段</th><th width="25%">核心产物</th><th width="43%">作者在此阶段决定什么</th><th width="18%">下游使用</th></tr></thead>
  <tbody>
    <tr><td>Brief</td><td><code>StoryBriefArtifact</code></td><td>书名、故事承诺、规则、主题、结局方向与叙事声音</td><td>Spine</td></tr>
    <tr><td>Spine</td><td><code>StorySpineArtifact</code></td><td>关键变化是否形成完整因果链，结局是否兑现立项承诺</td><td>Cast、Volumes</td></tr>
    <tr><td>Cast</td><td><code>CharacterBibleArtifact</code></td><td>主体职责、欲望、变化、限制、关系与首次出场</td><td>Volumes、Detail、Text</td></tr>
    <tr><td>Volumes</td><td><code>VolumeArchitectureArtifact</code></td><td>每卷的承诺、冲突、高潮、闭合和卷间承接</td><td>Detail</td></tr>
    <tr><td>Detail</td><td><code>DetailArtifact</code></td><td>每章目的、POV、场景序列、结果与下一章交接</td><td>Text、Cover</td></tr>
    <tr><td>Text</td><td><code>ChapterArtifact</code></td><td>接受正文、人工编辑或按证据定向换稿</td><td>下一章、Cover、Export</td></tr>
    <tr><td>Cover</td><td><code>CoverArtifact</code></td><td>视觉方向、图像提示、候选资产与最终选择</td><td>Export</td></tr>
    <tr><td>Export</td><td><code>ExportArtifact</code></td><td>章节版本、书名/作者元数据、封面和交付格式</td><td>不可变交付文件</td></tr>
  </tbody>
</table>

## 核心优势

<table width="100%">
  <thead><tr><th width="20%">能力</th><th width="44%">如何工作</th><th width="36%">带来的价值</th></tr></thead>
  <tbody>
    <tr><td>结构先于正文</td><td>Brief、Spine、Cast、Volumes、Detail 逐层冻结</td><td>长篇不会只靠提示词临场续写</td></tr>
    <tr><td>有界上下文</td><td>当前章节只读取签名后的 Context Manifest 和必要引用</td><td>控制上下文膨胀，降低跨章信息漂移</td></tr>
    <tr><td>相邻章节连续</td><td>第 N+1 章依赖第 N 章已接受正文、handoff 与临时状态</td><td>人物位置、知识状态和行动结果可以顺序承接</td></tr>
    <tr><td>证据化审校</td><td>确定性合同可阻断；模型 reviewer 默认提供证据与告警</td><td>不因模糊文学判断触发无限重写</td></tr>
    <tr><td>作者协作</td><td>精细模式以有界上下文回执和 source-bound patch 支持持续讨论、方案与改稿</td><td>模型不能绕过作者确认直接改写权威产物</td></tr>
    <tr><td>运行监控</td><td>从同一 Run 事件、Artifact、章节和 usage 读模型投影阶段内容与健康日志</td><td>自动运行过程可观察，不依赖计时器或假进度</td></tr>
    <tr><td>一次定向换稿</td><td>页面展示问题、正文证据和建议方向；每阶段/章节最多一次</td><td>修复明确缺陷，同时保护已冻结结构</td></tr>
    <tr><td>可恢复运行</td><td>LangGraph checkpoint、operation receipt、SSE sequence 和静态终态投影</td><td>失败可定位、断线可续接、完成作品不会重放历史过程</td></tr>
    <tr><td>可核验交付</td><td>Export 固定已接受章节版本、元数据、文件哈希和下载回执</td><td>交付内容与创作过程可追溯</td></tr>
  </tbody>
</table>

## 三档创作模式

仓库内置 `official-deepseek-fast`、`official-deepseek-balanced` 与 `official-deepseek-deep` 三套 DeepSeek 示例流水线。三档模式定义的是阶段职责、决策密度、质量门与默认参数；所有 Provider 绑定都可以替换为兼容 OpenAI API 的其它模型，不把产品能力绑定在某个型号上。

<table width="100%">
  <thead><tr><th width="14%">模式</th><th width="27%">默认模型策略</th><th width="20%">决策方式</th><th width="24%">质量与换稿</th><th width="15%">适合场景</th></tr></thead>
  <tbody>
    <tr><td>极速</td><td>低延迟、低成本模型优先；内置 DeepSeek 示例配置</td><td>阶段与章节自动接受</td><td>保留硬门；明确硬问题最多自动定向修订一次</td><td>快速验证创意与完整初稿</td></tr>
    <tr><td>平衡（推荐）</td><td>高杠杆规划与正文优先高质量模型，轻量节点可选经济模型</td><td>每阶段、每章可接受、编辑、换稿或取消</td><td>连续性与人物审稿必需；证据和修订方向可见</td><td>日常中长篇创作</td></tr>
    <tr><td>精细</td><td>Provider 阶段优先高质量模型，并提高人工控制密度</td><td>每阶段、每章人工定稿；五个核心阶段可开启作者协作</td><td>三路审稿全部返回；改稿必须预览确认并绑定源版本</td><td>正式稿精修与专业作者协作</td></tr>
  </tbody>
</table>

## 质量与连续性边界

Yotsuba Ink 把“必须修复”和“值得留意”分开处理：

- **硬门**：流程无法恢复、结构化输出不可解析、关键 Artifact 或正文缺失、明确上游合同冲突、主体越权、章内物理状态直接矛盾、未达到冻结总量目标、导出不可用。
- **告警**：低置信 reviewer finding、轻微节奏或文风差异、AI 味、篇幅接近合理边界、没有直接命名主体的证据、可由后文解释的身份隐藏或延迟揭示。
- **换稿上限**：自动或人工定向换稿最多一次；第二次仍触发硬门时明确停止，不用无限生成掩盖底层故障。

```mermaid
flowchart TB
  workbench["React 工作台"] <--> apiLayer["FastAPI 与 SSE 适配层"]
  apiLayer <--> runtimeGraph["LangGraph 唯一生产运行时"]
  runtimeGraph --> contextCompiler["Context Compiler：冻结引用与预算"]
  contextCompiler --> providerGateway["Provider Gateway：OpenAI-compatible"]
  providerGateway --> runtimeGraph
  runtimeGraph --> domainStores["Artifact / Chapter / Decision / Receipt Stores"]
  domainStores --> readModel["可重建 Read Model"]
  readModel --> apiLayer
  domainStores --> exportFiles["Export 文件与完整性回执"]

  classDef surface fill:#121d1a,stroke:#2fd68f,color:#f4fff9;
  classDef runtime fill:#172433,stroke:#69a7e8,color:#f4f8ff;
  classDef data fill:#2a2338,stroke:#9a7ce2,color:#fbf8ff;
  class workbench,apiLayer surface;
  class runtimeGraph,contextCompiler,providerGateway runtime;
  class domainStores,readModel,exportFiles data;
```

## v1.0 长篇实证

`official-deepseek-balanced` 已完成一轮真实 10 万字以上长篇生产：

<table width="100%">
  <thead><tr><th width="18%">指标</th><th width="45%">结果</th><th width="37%">验收含义</th></tr></thead>
  <tbody>
    <tr><td>作品</td><td>《明日来电》</td><td>全新都市悬疑题材，不沿用历史失败 Run</td></tr>
    <tr><td>Run / Project</td><td><code>balanced-110k-v1-demo-20260817-040033</code> / <code>proj-e1007717ad</code></td><td>运行与项目可独立追溯</td></tr>
    <tr><td>阶段</td><td>8/8 完成</td><td>从 Brief 到 Export 全链路闭环</td></tr>
    <tr><td>正文</td><td>44 章，107,613 个非空白字符</td><td>达到冻结的 10 万字交付目标</td></tr>
    <tr><td>单章分布</td><td>1,710-3,692，平均 2,445.75，P90 2,962</td><td>保留自然差异且无 1000/6000 字极端离散</td></tr>
    <tr><td>分卷</td><td>14 / 14 / 16 章，卷与章标题完整率 100%</td><td>卷名、章名与顺序完整</td></tr>
    <tr><td>Provider</td><td>314 次调用，311 成功，3 次失败后恢复，1,760,252 tokens</td><td>失败与恢复均保留回执</td></tr>
    <tr><td>Export</td><td>ZIP 可用，44 个已接受章节版本，SHA-256 已核验</td><td>交付文件可下载并校验完整性</td></tr>
  </tbody>
</table>

<p align="center">
  <img src="docs/assets/screenshots/export-workbench.png" alt="Yotsuba Ink 导出工作台" width="100%" />
</p>

本轮按配置跳过封面生图，Cover 元数据和 Export 仍完整闭环。完整硬门、连续性抽检、字数分布、Provider 回执与浏览器证据见 [v1.0 长篇验收报告](docs/engineering/yotsuba-ink-v1-balanced-110k-acceptance.md)。

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+
- pnpm 9+

### 1. 安装

```bash
git clone https://github.com/isla4ever/yotsuba-ink.git
cd yotsuba-ink

python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e ".[dev]"

cd apps/web
pnpm install --frozen-lockfile
```

### 2. 启动后端

```bash
cd yotsuba-ink
.venv/bin/python -m uvicorn novel_workflow.api.app:app \
  --host 127.0.0.1 \
  --port 8787 \
  --reload
```

### 3. 启动前端

```bash
cd yotsuba-ink/apps/web
pnpm dev
```

打开 [http://127.0.0.1:5176](http://127.0.0.1:5176)。开发服务器默认把 `/api` 代理到 `http://127.0.0.1:8787`。

## Provider 配置

推荐在应用内进入 **模型与设置**，选择官方或自定义 OpenAI-compatible Provider，填写 API Key 和模型后执行就绪检查。密钥只保存在本地运行时数据中。

也可以使用环境变量：

```bash
export NOVEL_LLM_BASE_URL="https://your-provider.example/v1"
export NOVEL_LLM_API_KEY="your-text-api-key"
export NOVEL_LLM_MODEL="your-text-model"

# 仅在需要封面生图时配置
export NOVEL_IMAGE_BASE_URL="https://your-image-provider.example/v1"
export NOVEL_IMAGE_API_KEY="your-image-api-key"
export NOVEL_IMAGE_MODEL="your-image-model"
```

不要提交 `.env`、API Key、运行历史、Provider 输入快照或用户稿件。

## 开发与验证

```bash
# 后端
.venv/bin/pytest -q
.venv/bin/python -m compileall -q src tests

# 前端
cd apps/web
pnpm test
pnpm build
pnpm audit:css
pnpm audit:structure
pnpm check:css-build
```

发布前必须通过后端全量测试与 compileall，以及前端测试、TypeScript/Vite 生产构建、CSS/目录审计和桌面/移动端真实浏览器验收。真实 Provider 与文学质量使用独立的新 Run 记录，不能由离线门禁替代。

## 仓库结构

```text
apps/web/                    React 创作工作台
src/novel_workflow/          LangGraph 运行时、领域合同与 FastAPI 适配层
runtime/novel_workflow/      官方工作流、Prompt 与本地运行时数据
tests/                       合同、编排、Provider、恢复和质量测试
docs/                        架构合同与验收记录
```

## 关键文档

- [架构概览](docs/architecture/overview.md)
- [阶段 Artifact 合同](docs/architecture/stage-artifact-contract.md)
- [Phase 27 自适应长篇架构](docs/architecture/phase-27-adaptive-story-planning-reconstruction.md)
- [Phase 28 文学可靠性与作者控制](docs/architecture/phase-28-v1.1-literary-reliability-and-author-control.md)
- [Phase 29 分层长篇规划](docs/architecture/phase-29-v1.1-million-character-author-led-deep-mode.md)
- [Phase 30 Version 20 前端迁移](docs/architecture/phase-30-figma-ui-production-migration.md)
- [Phase 31 精细模式作者协作](docs/architecture/phase-31-deep-mode-author-collaboration.md)
- [v1.0 平衡模式长篇验收](docs/engineering/yotsuba-ink-v1-balanced-110k-acceptance.md)
- [版本变更记录](CHANGELOG.md)

## 许可证

Yotsuba Ink 采用 [Apache License 2.0](LICENSE) 开源。
