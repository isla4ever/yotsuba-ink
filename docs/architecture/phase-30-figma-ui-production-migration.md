# Phase 30：Figma Make UI 生产接入与前端收口方案

状态：Version 20 已于 2026-08-21 完成单向切换并成为唯一生产前端；旧前端已移出仓库，仅保留仓库外可恢复备份。真实 Provider 与文学质量验收仍按各自 Phase 独立判定。

设计参考：[Yotsuba Ink - Make Interaction Lab](https://www.figma.com/make/D4jMEfXlu7V9ev5uO5jv06/Yotsuba-Ink---Make-Interaction-Lab)

权威产品合同：`docs/architecture/stage-artifact-contract.md`

## 1. 决策结论

以用户下载的 **Figma Make Version 20** 源码作为唯一视觉与交互基线。实施阶段曾在隔离目录完成迁移；全部离线、结构和浏览器门通过后，Version 20 已切换为最终 `apps/web`。旧前端在迁移期间只作为生产合同和 API/SSE 行为的读取来源，从未继续作为视觉基线。

采用**隔离重建、逐链路接入、一次切换**：Version 20 的 Shell、页面层级、Tailwind tokens、响应式和微交互保持不变；Figma 的 mock context、演示数据、本地定时器和无动作按钮逐项替换为真实 Projects、Workflows、Providers、Knowledge、Run、SSE、Artifact Draft、Decision、Context Manifest、Cover Asset 和 Export 适配器。

迁移期间曾允许两个可运行目录用于对照验收，但从未允许两个生产入口。当前仓库只保留 Version 20 的 `apps/web`：旧呈现层、旧 CSS、旧 mock、旧本地状态路径和隔离迁移目录均不再存在于产品树中。旧前端完整备份位于仓库外 `$HOME/Desktop/project-backups/Yotsuba-Ink/apps-web-legacy-20260821-221754`，不能作为构建输入、运行入口或 Git 发布内容。

### 为什么改为隔离重建

1. 下载包已包含用户认可的完整 Version 20 页面和交互源码，继续从旧组件树还原会产生不可接受的视觉偏差。
2. 当前 `apps/web` 的呈现层与多轮旧设计、CSS 和局部补丁耦合，已经出现大量无响应按钮和页面层级漂移。
3. 隔离目录让 Version 20 可与旧前端逐页并排验收，同时保护 Phase 28/29 未提交的后端和合同变更。
4. Figma mock 只保留为视觉 fixture；任何进度、模式、Artifact、Decision、日志和写回状态都必须来自真实后端。
5. 最终切换必须同时删除旧 UI，不能长期保留 `v20`、`legacy-ui`、双路由或 Feature Flag。

## 2. 设计与产品事实优先级

实施遇到冲突时按以下顺序裁决：

1. `stage-artifact-contract.md` 的阶段顺序、Artifact、用户决策、写回和下游依赖。
2. 当前后端 API、LangGraph 运行状态、SSE 事件和持久化事实。
3. 用户已确认的 Figma 交互修订意见。
4. Figma Make 的布局、视觉、组件和动效表现。
5. 当前前端实现。

这意味着“完全复刻 Figma”指视觉语言、信息层级、交互模式和响应式行为完整覆盖，不指复制已经过时的 mock 字段。

必须拒绝的原型漂移示例：

- 生产阶段固定为 `brief -> spine -> cast -> volumes -> detail -> text -> cover -> export`，不恢复旧 `info/summary/outline` 名称。
- Detail 不恢复已经从合同删除的自由 `wiki_candidates/fact_reveals/foreshadow_actions` 字段；正文 Evidence、Canon/Wiki 和写回继续使用当前生产合同。
- Fast/Balanced/Deep 在建书/流水线配置时选定，Run 创建后只读，不在侧栏、Header 或运行页提供切换。
- 监控进度由真实 Run/Artifact/Chapter 状态投影，不使用 Figma demo 的固定 67%。
- Project、Artifact、Decision 和 SSE 不从 Figma mock data 或组件本地定时器推导。

## 3. 当前基线

### 3.1 Figma Make 基线

已确认的 Make 文件包括：

- `components/CommandPalette.tsx`
- `components/Shell.tsx`
- `views/Studio.tsx`
- `views/WorkflowTemplates.tsx`
- `views/WorkflowTemplateDetail.tsx`
- `views/Planning.tsx`
- `views/RunMonitor.tsx`
- `views/StoryBible.tsx`
- `views/Knowledge.tsx`
- `views/History.tsx`
- `views/Settings.tsx`
- `views/stages/Brief.tsx`
- `views/stages/Spine.tsx`
- `views/stages/Cast.tsx`
- `views/stages/Volumes.tsx`
- `views/stages/Detail.tsx`
- `views/stages/Text.tsx`
- `views/stages/Cover.tsx`
- `views/stages/Export.tsx`

当前 Make Version 21 存在未保存的 `Spine.tsx` 修改，Preview 因 `exportXdefault function Spine()` 无法构建，AI 输入又因额度耗尽被禁用。因此 Phase 30 不把当前 Make build 当成可运行依赖；设计基线由版本历史、已确认截图、用户修订记录和可读源文件共同冻结。

实施 Wave 0 会给每个生产页面建立一条 `设计状态 -> 生产组件 -> 数据来源 -> 验收截图` 记录，避免后续凭印象还原。

### 3.2 切换前旧前端基线（历史）

2026-08-19 只读审计结果：

- `pnpm build`：通过，Vite 转换 3553 个模块。
- `pnpm test`：116 个测试文件、439 个测试全部通过。
- `pnpm check:css-split`：通过，首屏 CSS gzip 约 28.4 KiB。
- `pnpm audit:css`：失败。
- CSS 当前约 497,804 bytes、19,956 行、3,808 个 selector、134 组跨文件重复 selector、20 个 infinite animation 声明。
- 当前工作区包含大量未提交 Phase 28/29 变更；迁移必须原位协作，禁止 reset、覆盖或批量回退。

现有生产底座应保留：

- `contracts/`：Project、Workflow、Run、Knowledge、Provider 和阶段数据合同。
- `services/`：HTTP、SSE、上传、导出和 Provider IO。
- `state/`：Project session、Run reducer、恢复、命令、决策、草稿和持久化。
- `lib/`：阶段路由、进度、质量、展示投影和纯转换。
- `dev/StagePreviewApp.tsx`：八阶段离线真实组件验收入口。

## 4. 目标前端结构

不新增 `ui/`、`components/`、`screens/`、`figma/` 或 `v2/` 顶层目录。目标仍为：

```text
apps/web/src/features/pipeline/
  layout/       全局壳层、Studio 壳层、Header、导航、命令面板
  planning/     建书后的 Run 前配置与准备
  brief/        Brief 输入和 Source Pack
  running/      八阶段 Artifact、监控、Story Bible、阶段局部导航
  settings/     全局/本书设置、Provider、Knowledge 配置
  state/        UI 与业务状态 hooks/reducers/selectors
  services/     HTTP/SSE/上传适配器
  contracts/    TypeScript IO 合同
  lib/          纯函数与展示投影
```

### 4.1 保留与替换边界

| 层 | 策略 | 原因 |
| --- | --- | --- |
| Router / App shell dispatch | 保留并精简 | 已正确区分 studio/project/monitor 三种 shell |
| contracts | 保留，随真实 API 窄改 | 是生产数据边界 |
| services | 保留，补缺失 API | 已有完整 IO 责任 |
| run reducer / SSE | 保留 | 是运行事实源，不能由视觉层重写 |
| stage Artifact parser/validation | 保留 | 与后端合同一致 |
| stage draft/decision/writeback | 保留 | 已接真实决策链 |
| layout components | 按 Wave 替换 | Figma 壳层、Header、导航需要统一 |
| Studio / stage / monitor views | 按路由纵切片替换 | 需要完整复刻交互和视觉 |
| CSS | 所有权内重写并删除旧 selector | 当前主要债务来自叠加级联 |
| Figma mock context/data/timers | 不迁入生产 | 只能用于视觉参考和 fixture |

## 5. 壳层与全局交互合同

### 5.1 Studio Shell

未打开作品时只展示：

- 作品库
- 工作流模板
- 知识总览
- 创作历史
- 全局 AI 与服务设置
- 新建小说

不得展示制作流程、八阶段、Story Bible、运行监控、本书知识库或本书设置。

### 5.2 Project Shell

打开作品后展示：

- 当前作品身份与返回创作台
- 只读的创建模式、Provider/模型和锁定状态
- 八阶段制作流程
- Story Bible
- 运行监控
- 本书知识库
- 本书设置

创建模式不得在 Run 中修改。若需修改，用户从 Studio 复制/配置新的本书流水线并创建新作品或新 Run。

### 5.3 Header

Header 使用短而克制的心电图式进度表现：

- 最大宽度约 640-720px，不横跨整个视口。
- 1px 基线、八个阶段位置、局部活动游标和有限状态脉冲。
- 第二阶段仍参与真实进度计算，但 Header 不承载因果链浏览器，也不提供重复的脊柱工作区入口。
- 不使用面包屑胶囊或粗分段进度条。
- 动效只在阶段变化或新事件到达时播放一次，不持续频闪。
- Reduced Motion 下只保留静态状态和位置变化。

### 5.4 页面切换与微交互

- Route/Tab/内容切换：160-240ms opacity + 2-6px 位移。
- Hover：不改变布局尺寸；优先使用局部边界、背景、透明度和阴影。
- Active/Focus：必须与 Hover 等价可见。
- 弹层：全局 Portal、居中、单一内部滚动、稳定 footer。
- 文字显现：只在内容切换、流式生成和确认回执时使用，不对静态正文逐字动画。
- 监控更新：无感更新；新日志局部进入，不让整页闪烁或重排。
- 所有动效受 `prefers-reduced-motion` 控制。

### 5.5 模式与主题

- 全局基底保持中性暗黑石墨，不随模式整页换色。
- Fast 仅使用冷蓝局部能量，Balanced 使用薄荷绿，Deep 使用克制紫。
- 模式色只用于锁定徽标、当前阶段、焦点主操作、局部 aura 和进度游标。
- Success/Warning/Danger 保持固定语义色，不被模式色覆盖。
- 保留 Dark/Light token 能力，但 Figma 生产主验收以 Dark 为第一基线。

## 6. 页面完全覆盖矩阵

每一行都必须同时覆盖 Default、Loading、Empty、Error、Busy/Streaming、ReadOnly/Committed 和 Reduced Motion 中适用的状态。

| # | 生产路由/表面 | Figma 目标 | 生产组件边界 | 真实数据/动作 | 完成标准 |
| ---: | --- | --- | --- | --- | --- |
| 1 | `/studio` 作品库 | 立体书架为主体、紧凑数据条、满高视口 | `layout/studio/StudioWorkbench`、`ProjectBookshelf`、`StudioLibraryOverview` | Projects + Project summaries | 统一窄高书脊、拖动/键盘排序、滚动、悬浮信息不越界、无底部大空白 |
| 2 | `/studio?view=templates` | 工作流牌组而非传统卡片墙 | `TemplateManagerSection`、`WorkflowTemplateDeck` | Workflow list/duplicate/delete | 八阶段关系清晰，节点与连接层级正确，操作可达 |
| 3 | `/studio/workflow/:id` | 工作流全貌 + 阶段配置工作台 | `WorkflowTemplateEditorPage`、`StageInspector` | Workflow get/save/duplicate | 官方只读、本书副本、自定义模板三种权限闭环 |
| 4 | `/studio?new=1` | 两步策划向导 | `NewProjectWizard` | select/configure workflow -> submit idea -> create project | 任何“新建小说/项目”入口都进入同一向导，不再有重复弹窗语义 |
| 5 | `/studio/knowledge` | 跨作品知识总览 | `StudioKnowledgeOverview` | project summaries + knowledge | 不出现项目制作流程，状态和入口明确 |
| 6 | `/studio/settings` | 全局 Provider/模型服务 | `SettingsPage scope=global` | Provider APIs + readiness | 不混入本书运行模式切换 |
| 7 | `/history` | 创作、快照、导出记录 | `CreationHistoryPage` | run history/export/branch | 终态只读、可恢复态可操作，不能把历史 Run 当当前事实 |
| 8 | `/planning` | Run 前流水线准备与最终复核 | `PlanningWorkbench` | Workflow、Knowledge、Provider readiness、Run create | 模式仍可配置；Run 创建后冻结；Artifact 不提前伪造 |
| 9 | `/run/brief` | 立项 Artifact 编辑与硬确认 | `StoryBriefStageView` | StoryBriefArtifact draft/decision | 只显示合同字段；正式标题在 Brief 确认后投影 |
| 10 | `/run/spine` | 因果链局部侧栏 + 单节点编辑区 | `SpineStageView` | StorySpineArtifact draft/decision | 因果链不在 Header；使用与 Detail 章节栏相同宽度的内部二级侧栏；节点与主编辑同步 |
| 11 | `/run/cast` | 名册 + 档案 + 关系投影 | `CharacterStageView` 及 graph | CharacterBibleArtifact | Cast 是正文前唯一具名主体权威；图谱不直接改事实 |
| 12 | `/run/volumes` | 分卷架构轨道/节拍板 | `VolumeStageView` | VolumeArchitectureArtifact | 卷合同、自然边界、turn/cast refs 可读，不堆通用卡片 |
| 13 | `/run/detail` | 高密度章节施工表 + 蓝图 | `DetailStageViewVnext` | DetailArtifact | 章节栏固定宽度、场景可编辑、handoff 明确、无已删除字段 |
| 14 | `/run/text` | 章节栏 + 稿纸 + 审稿/上下文 | `ChapterStageViewVnext` + insights | Chapter versions、review、context manifest、decision | 流式正文稳定、候选/修订/人工编辑/写回状态闭环 |
| 15 | `/run/cover` | Cover brief + 候选 + 正式资产 | `CoverStageViewVnext` | Cover Artifact + asset API | 真实失败不展示假图；比例、选定与导出状态一致 |
| 16 | `/run/export` | Manifest、版本、校验、下载 | `ExportStageViewVnext` | Export Artifact + receipts | 不调用 Provider，不暗改上游 Artifact |
| 17 | `/monitor` | 专注三栏监控：阶段/卷章、内容、健康与日志 | `running/console/*` | Run read model + SSE + sticky artifacts | 隐藏项目大侧栏；中央铺满；左栏按阶段适配；右栏日志/检查点/质量/写回/连接完整 |
| 18 | `/bible/cast` | 人物档案和关系浏览 | `StoryBibleWorkbench` | CharacterGraph projection | 只读投影、键盘/2D 降级、3D 懒加载 |
| 19 | `/bible/world` | 世界规则账本 | `StoryBibleWorkbench` | world projection | 不与 Source Pack 或 Canon 混用 |
| 20 | `/bible/foreshadow` | 伏笔/open-loop 账本 | `StoryBibleWorkbench` | evidence-derived projection | 不让 UI 自行创造事实 |
| 21 | `/bible/facts` | Canon 事实与冲突 | `StoryBibleWorkbench` | Canon/Wiki stores/read models | 证据、批准和冲突状态可读 |
| 22 | `/knowledge` | 本书 Source Pack | `KnowledgeLibraryPage` | knowledge upload/list/delete/search | 上传、索引、失败、重试和空态完整 |
| 23 | `/settings` | 本书工作流与服务只读/配置边界 | `SettingsPage scope=project` | active workflow + provider readiness | Run 存在时模式锁定；不绕过向导改生产合同 |

## 7. 关键页面细则

### 7.1 作品库书架

- 书架占作品库主要视觉高度，统计条保持从属。
- Desktop 书脊目标约 `56 x 320px`，Mobile 约 `42 x 220px`，所有书统一顶部和基线，不使用随机高度。
- 书本标题、章节/进度和状态在窄宽度内保持可读，不旋转整段横排文案。
- Hover 只上移 6px，不 scale；整本书不裁切。
- Tooltip 使用 fixed 定位与碰撞约束，不能覆盖 Header、侧栏或离开视口。
- 横向滚动支持触控、触控板、滚轮映射、左右按钮和键盘。
- 拖动排序必须有插入位置、自动滚动、Escape 取消、键盘等价操作和失败回滚。
- 当前后端没有作品排序合同。新增窄接口 `PUT /api/projects/order`，由 ProjectStore 原子校验并保存完整 project id 顺序；route 只做适配。不得只存在 localStorage。

### 7.2 工作流模板

- 列表页显示真正的八阶段结构、模式、模型策略和状态，不使用同质卡片墙。
- 连接线永远在节点下层，active 阶段局部强调，避免黄色状态穿透线条。
- 详情页继续使用现有真实 `StageInspector`，Figma 只替换排版、层级、选择和转场。
- 官方模板只读；“配置本书”创建一次性副本；一次性副本可直接建书或另存模板；自定义模板影响之后新建的作品。

### 7.3 Spine 因果链

- 项目外层侧栏保持不变，不用因果链替换整个制作流程。
- `SpineStageView` 内部增加与 Detail `vnext-chapter-nav` 同宽的二级侧栏，纵向展示所有 turns。
- 二级侧栏只承担节点选择、序号、推进类型、里程碑和短摘要。
- 主区只编辑当前 turn 的 cause/change，并展示结局、开放问题和下游影响。
- 选中节点可通过 URL search 或 running-local UI state 深链；不写入 Artifact，不进入 Graph State。
- Header 不渲染横向因果链、全局视图卡轨或重复入口。

### 7.4 实时监控

- `/monitor` 使用自己的紧凑导航栏，Project Shell 大侧栏隐藏。
- Desktop 主栅格目标为 `rail minmax(0,1fr) inspector`；中央表面 `min-width:0`、`max-width:none` 并填满剩余高度。
- 左栏在 Brief/Spine/Cast/Volumes 阶段显示阶段/产物导航；Detail/Text 阶段显示卷->章树；Cover/Export 显示资产/交付导航。
- 中央按阶段渲染只读真实内容，不把编辑工作台完整复制进监控。
- 右栏固定包含运行健康、人工决策、review/evidence、checkpoint、writeback、SSE/连接和日志；窄桌面折叠为 drawer。
- 新事件批量消费并局部更新；进入历史 Run 时等待 replay 安静后一次呈现，不逐条重放造成闪烁。
- 日志默认存在且可收起，不能因切换阶段丢失。
- 文本保持舒适行长，但承载它的 panel 必须占满可用中央宽度和高度。

## 8. 真实数据与 API/SSE 映射

| UI 能力 | 生产事实源 | 禁止替代 |
| --- | --- | --- |
| 作品列表/统计 | `/api/projects` + `/:id/summary` | Figma mock projects |
| 书架顺序 | 新增 `/api/projects/order` | 仅 localStorage |
| 新建作品 | `POST /api/projects`，只提交 idea + workflow | 预填正式书名/题材表单 |
| 工作流模板 | `/api/workflows*` | 组件本地模板数组 |
| Provider/模型 | `/api/providers*` + readiness | 假“在线”绿点 |
| 知识库 | `/api/knowledge*` | 演示上传完成状态 |
| Run 状态 | `GET /api/runs/:id` | 组件挂载时间 |
| 实时事件 | `/api/runs/:id/events?after=` SSE | 随机数/定时器推进 |
| 当前 Artifact | artifact record/ref + reducer projection | 原始 Graph State 或 JSON textarea |
| 草稿 | stage draft API | 仅组件 state |
| 定稿/换稿/取消 | decision API + domain revision | 本地切换状态 |
| 正文上下文 | Context Manifest API 的可读投影 | 完整 Prompt/hash/JSON |
| 正文版本 | chapter version API | 用当前 textarea 伪造历史版本 |
| Cover | cover asset API | fake image 成功 |
| Export | immutable export receipt | 根据当前状态重建旧包 |
| Story Bible | Artifact/Evidence/Canon/Wiki 的确定性投影 | 手工可编辑第二事实源 |

所有流式状态必须覆盖：starting、running、candidate ready、awaiting decision、committed、review unavailable、writeback queued/success/failed、reconnecting、recovery required、failed、completed。

## 9. CSS 与动效收口策略

禁止新增 `figma-theme.css` 或在入口末尾用更高 specificity 覆盖旧样式。

每个 Wave 的样式处理顺序：

1. 在 `design-tokens.css` 补齐真正可复用的 surface/text/stroke/spacing/motion/rail tokens。
2. 在当前所有权文件中实现目标组件样式。
3. 删除该组件旧 selector 和重复 responsive override。
4. 检查 Dark/Light、三模式和 Reduced Motion。
5. 运行 CSS audit；指标必须下降或在审查后保持，不允许只更新 baseline 掩盖增长。

最终门槛：

- `pnpm audit:css` 通过。
- `pnpm check:css-build` 通过。
- 跨文件重复 selector 明显下降，不再依赖入口末尾覆盖。
- 空闲页面无装饰性 infinite animation 或持续 RAF。
- Infinite 只允许真正的进度 Spinner/运行连接指示，并具备 Reduced Motion 静态替代。
- 普通交互继续使用 CSS + 现有 `motion`；GSAP 只保留给确需精确时间线的场景，不用于页面淡入淡出。

## 10. 实施 Waves

### Wave 0：设计冻结与验收基础

- 固定 Figma Make URL、版本说明、用户截图和每页状态清单。
- 建立 23 个生产表面的设计覆盖 manifest。
- 扩充 `StagePreviewApp`，使八阶段均可切换 streaming/candidate/committed 和 warning/blocked/evidence。
- 为 Studio、Wizard、Workflow、Monitor 增加离线 fixture 预览入口，fixture 与生产组件共用，不进入生产数据。
- 记录现有截图、DOM、overflow、console 和 CSS 指标。

退出条件：任一页面都能在无 Provider 下复现用于验收的真实组件状态。

### Wave 1：Token、双壳层与 Header

- 收口设计 token、字体、密度、边界、阴影和动效曲线。
- 固化 Studio Shell / Project Shell / Monitor Shell。
- 替换 Header 为短 ECG 进度 + 状态 + 锁定模式 + 稳定操作区。
- 统一 sidebar width、collapse、mobile drawer、route transition、tooltip 和 focus。
- 删除重复 Header/Sidebar cascade。

退出条件：所有路由进入正确壳层；未打开书时无项目工具；打开书时无 Studio 导航混淆。

### Wave 2：Studio 创建闭环

- 作品统计条、满高书架、真实比例、tooltip、拖动/键盘排序。
- 工作流模板牌组与详情页。
- 新建小说两步向导和“一次性配置/另存模板/直接建书”闭环。
- 必要的 Project order 后端窄合同与测试。

退出条件：所有新建入口进入同一向导；从选模板到进入 Brief 没有语义断点。

### Wave 3：Planning + Brief + Spine + Cast

- Planning 只负责 Run 前配置与 readiness。
- Brief 按 StoryBriefArtifact 重排主编辑区和确认门。
- Spine 改为内部因果二级侧栏 + 当前节点编辑区。
- Cast 改为 roster/dossier/relationship projection 三段工作台。

退出条件：三个 Artifact 的编辑、草稿、换稿、确认、只读和下游约束全部使用真实 API。

### Wave 4：Volumes + Detail

- Volumes 改为自然卷界与卷合同节拍板。
- Detail 改为高密度章节施工账本、章节二级栏和聚焦蓝图。
- 统一 Spine/Detail 二级栏宽度、滚动和键盘选择。

退出条件：多卷、长章名、多场景、长中文和只读/编辑状态不溢出；不恢复已删除字段。

### Wave 5：Text + Run Monitor

- Text 完成章节导航、稿纸、流式生成、审稿、候选、定向修订、版本和写回状态。
- Monitor 完成专注三栏、阶段适配内容、卷章导航、右侧健康/日志和窄屏 drawer。
- 检查 SSE 批处理、恢复和历史 replay，消除全页闪烁。

退出条件：实时生成、断线、reconnect、decision、evidence、writeback 和 terminal 状态均可复现且无假进度。

### Wave 6：Cover + Export + Story Bible + 辅助页

- Cover 与真实资产状态、比例、候选和失败反馈闭环。
- Export 与 immutable receipt、校验、下载闭环。
- Story Bible 四分区统一账本视觉与只读事实边界。
- Knowledge、History、Global/Project Settings 完成同主题迁移。

退出条件：23 个表面全部进入同一设计语言，不存在旧主题孤岛。

### Wave 7：删除旧实现与总验收

- 删除已无消费者的旧组件、selector、compat alias 和临时 fixture。
- 不保留双实现、重导出 shim 或长期 feature flag。
- 完成全路由、全状态、全视口和完整键盘检查。
- 只有所有 Gate 通过后才审查提交范围；不自动 push。

## 11. 验收 Gate

### 11.1 功能与合同

- 八阶段顺序、Artifact 字段、决策、写回和下游依赖不变。
- Run 中无法修改创建模式。
- Studio 与 Project 两套导航完全隔离。
- 所有正式动作调用真实 services；fixture 只能出现在 dev preview/test。
- 不展示 raw JSON、Graph State、Prompt 全文、Provider secret 或不可读 hash。

### 11.2 视觉与响应式

必测视口：

- `390x844`
- `768x900`
- `1024x900`
- `1280x920`
- `1440x1000`
- `1728x1100`
- 200% Zoom

退出条件：

- 页面级横向 overflow 为 0；表格/画布只在自己的容器滚动。
- 每个页面只有明确的主滚动 owner；Dialog/Sheet 内部滚动不泄漏到 body。
- Artifact 在首屏占主导，诊断不抢夺正文/编辑区。
- 书架、因果栏、章节栏、Monitor 和 Header 无大块无意义留白。
- 文本、图标、tooltip、modal、active/hover/focus 不重叠或裁切。
- Dark/Light 与 Fast/Balanced/Deep 不改变状态色含义。

### 11.3 动效与性能

- Reduced Motion 下页面可完整操作。
- 路由、Tab、文字显现、hover、active、dialog 都有克制过渡。
- Monitor 无高频闪动；新事件不会触发整个 Header/Sidebar 重渲染。
- 3D 图谱继续 lazy load，可暂停、卸载并有 2D/列表降级。
- Console 0 error、0 warning；空闲 Long Task 和 CLS 为 0。

### 11.4 自动检查

每个 Wave 至少运行：

```bash
cd apps/web
pnpm test
pnpm build
pnpm audit:css
pnpm check:css-build
```

阶段 UI 还必须通过真实 `StagePreviewApp` 浏览器矩阵；Monitor、Studio 和 Wizard 需要对应的离线 API fixture 浏览器场景。

## 12. 实施纪律

- 每次只迁移一个壳层或一组强相关页面，不做全仓机械改名。
- 开始一个 Wave 前记录目标组件、旧 selector 和删除清单。
- 页面通过后立即删除该页面旧视觉实现，避免新旧并存。
- 任何后端改动都保持 route 薄、领域/存储拥有规则。
- 不修改历史 Run；真实验收必须创建全新 Run。
- 不把局部 build、fixture 或浏览器截图描述为 Provider/文学质量验收。
- 当前 dirty worktree 全程保留，不 reset、不 checkout 覆盖、不清理用户文件。

## 13. 开工顺序

批准本方案后直接从 Wave 0 开始，不再重新讨论“另建目录还是原位迁移”。第一批可交付应是：

1. 设计覆盖 manifest 与离线预览入口补齐。
2. Token/双壳层/Header ECG 的生产实现。
3. Studio 书架、工作流模板与新建小说闭环。

三项完成并通过桌面/390px 验收后，再进入八阶段工作台迁移。

## 14. Wave 6 Story Bible 真实投影记录

2026-08-20 当时已完成 Story Bible 的首个真实后端/前端纵切片；该记录发生在最终目录切换之前，最终切换结果见第 28 节：

- 新增领域只读投影 `src/novel_workflow/memory/story_bible_projection.py`，从 `EvidenceStore -> CanonStore -> ResolvedStoryState -> WikiProjectionStore` 确定性汇总事实、冲突、来源链和伏笔生命周期；不在 React 中推导主体或事实。
- 新增薄接口 `GET /api/runs/{run_id}/story-bible`，沿用当前 Run 合同守卫；未知 Run 返回 404，retired Run 返回 `run_contract_retired`，损坏投影返回 `story_bible_projection_invalid`。
- Version 20 `StoryBible` 已接真实 `/story-bible` service、严格 TypeScript parser、可取消 hook 和只读 Facts/Foreshadow ledger；缺失 Evidence、Canon/Wiki 写回状态和冲突均显式展示。
- 离线合同测试 `6 passed`；全量后端 `598 passed, 1 warning`；`compileall`、`git diff --check`、Version 20 `pnpm build` 通过。
- 浏览器真实检查：完成项目 `proj-e1007717ad` 显示 `339` 条 Canon、`339` 条 Wiki 投影和 `12` 条伏笔；桌面截图、`390x844` 截图、横溢出和 console error/warn 均通过。

这条证据只证明当前可用 Run 的只读投影与 UI 链路，不启动真实 Provider 或修改历史 Run。

## 15. Story Bible 分页读模型

2026-08-20 已补齐百万字符规模所需的读取边界：

- 新增 `src/novel_workflow/memory/story_bible_read_model.py`，把旧 Run 或首次读取的完整投影一次性重建为每 Run 的 manifest、摘要和事实/伏笔单条索引文件；后续页面读取只加载请求游标对应的有限条目，不再为每个请求扫描 Evidence、Canon、Wiki 全部交易。
- `GET /api/runs/{run_id}/story-bible` 现在接受 `section=facts|foreshadow`、`limit=1..100` 和不透明 `cursor`，响应包含全量计数/冲突摘要、当前页条目和 `next_cursor`。源账本发生变化时旧游标明确返回 `story_bible_cursor_stale`，不静默拼接不同快照造成重复或漏项。
- Version 20 Facts/Foreshadow ledger 只渲染首批 50 条，指标使用摘要，用户通过“加载更多”继续读取；列表保留来源、当前/历史状态和 Wiki 写回语义，不创建第二个可编辑事实源。
- 读模型可由目录版本变化自动重建，因此旧 Run 无索引、正文 Evidence-only 变更、Canon/Wiki 写回和分支复制均有确定性恢复路径；Canonical Artifact、Evidence、Canon、Wiki 和 Outbox 的权威边界保持不变。
- 新增分页顺序、重复消除、空 Run、跨 section/损坏游标、过期游标和 Wiki 写回后幂等刷新测试。

## 16. 极速 5 万字真实 Run 稳定性记录

2026-08-20 使用项目 `proj-5175cc5ace` 和本书极速流水线创建全新 Run
`fast-50k-ui-20260820-025430`。本次验收**未通过完整链路 Gate**，Run 保留在
Detail 的 `awaiting_decision` 状态，不复制历史 Artifact，也不改写为成功：

- DeepSeek 额度与真实文本调用已恢复；Brief、Spine、Cast、Volumes 均生成、校验并提交。Cast 的 Role Demand 本次首稿成功，证明前一 Run 的合同失败不是余额问题。
- 为前一 Run 暴露的 parsed-object 合同失败增加明确诊断码 `structured_contract_invalid`；Role Demand 仅在第一次命中该码时使用独立 `contract-repair-1` operation 做一次完整替代候选。鉴权、余额、网络和 JSON 解析错误仍直接终止。回归测试同时证明失败 receipt、不同输入快照和无第三次隐藏重试。
- Detail attempt 1 的第七个分段违反冻结的每章 `2-5` 场容量；attempt 2 的 DetailLayout 在到达 `turn-10` 后回退到 `turn-1`；attempt 3 的布局通过，但第六个分段返回不可解析 JSON；收紧因果单调 Prompt 后，attempt 4 仍产生第二遍 `turn-1...turn-10`，因此不再继续消耗额度。
- 停止时共 `27` 个 Provider operations：`25` succeeded、`2` failed，累计 `151,728` tokens。成功 operation 和失败 receipt、输入快照、解析诊断及 SSE 事件均保留在该 Run 的 native runtime 目录。
- Version 20 `/monitor?project=proj-5175cc5ace` 正确投影等待决策、27 次调用、2 次失败、92 条事件和 Brief/Spine/Cast/Volumes 正式内容；六个阶段切换、Detail 空态、Text 未解锁态、健康/日志面板与浏览器 console `0 error / 0 warning` 通过。
- Text、Cover、Export、正文实际非空白字符数、Cover asset 和 Export package 未到达，不能据此宣称完整 5 万字链路、成本、连续性或文学质量通过。

未解决硬 Gate：整卷 DetailLayout 对 `20` 个章节槽和 `10` 个 Spine turns 的一次性自由映射不稳定。单纯增加 Prompt 已被真实 attempt 4 证伪；下一轮必须先评审将其改为连续 turn window 的窄调用，或采用不改变章节戏剧语义的确定性顺序合同，然后用另一个全新 Run 从 Brief 重新验收。

## 17. 极速 5 万字真实 Run：预算边界与监控台复核

2026-08-20 使用全新项目 `proj-ec9ab406d8`、冻结极速工作流
`wf-proj-ec9ab406d8` 创建 Run `fast-50k-live-20260820-051515`，目标为
`word_target_soft=50,000`，并关闭图片资产生成。该 Run 不恢复或复制任何历史
Artifact，最终因 Detail 合同失败取消：

- Brief、Spine、Cast、Volumes 均完成并提交；Detail 第一次因场景负载超出冻结容量区间失败，第二、三次因同一卷重复戏剧任务失败，达到有界重生成上限后显式取消。
- Cast 的两次关系 pressure 合同失败均按允许动作恢复，第三次候选通过；Detail 共三次有界尝试，没有绕过结构化校验或无限重试。
- 共 `30` 个 Provider operations：`26` 成功、`4` 失败，累计 `138,289` tokens；`98` 条 SSE 事件、`5` 个决策请求、`9` 个决策处理，最终无 pending decision。
- 新增 `text.check_book_budget` 尚未执行，因为 Run 在正文前的 Detail 阶段结束；因此本次不能宣称正文预算、正文字符数、Cover 或 Export 通过。预算阻断 payload 已在本地合同测试中验证会在事件持久化前包含 claim/evidence/severity。
- Version 20 `/monitor?project=proj-ec9ab406d8` 正确显示取消态、细纲失败态、阶段与已提交卷册 Artifact、Provider 调用/失败调用/Token、98 条实时日志和检查点；桌面阶段切换与移动端健康/日志抽屉可用。
- 浏览器验收：桌面 `1280x720` 与移动 `390x844` 均页面级无横向溢出，console `0 error / 0 warning`。运行监控台截图与 DOM 证据保留在本次验收会话中。

未解决硬 Gate：真实 5 万字 Run 仍未进入 Text，DetailLayout 的连续 turn window 合同仍是当前最低责任边界；下一轮继续使用全新 Run，不改写本 Run 的取消状态。

## 18. 极速 5 万字真实 Run：正文中段与监控台事件投影复核

2026-08-20 在完成 Detail 连续窗口修复后，使用全新项目
`proj-ec9ab406d8` 创建并启动 `fast-50k-live-20260820-final`。该 Run 首次穿过
Detail 并进入正文，随后在第 14 章因 Provider 连续三次生成同一个未冻结序数事实而按硬合同失败：

- Brief、Spine、Cast、Volumes、Detail 均完成；正文接受 13 章，非空白字符 `28,662`，未执行 Cover、Export。
- 共 `115` 个 Provider operations，`109` 成功、`6` 失败，累计 `835,553` tokens。
- 失败责任边界为 `SceneProseContractError`：三次候选都写入未由冻结上下文授权的“第一条”；这不是文学审稿意见，也不是余额失败，Run 保持只读失败状态。
- 该 Run 期间暴露 Version20 监控台的两个真实投影缺口：读模型 checkpoint 在正文中段滞后于 SSE，且章节提交后 `useRunArtifacts` 不会重新读取章节列表。两者均未改写后端 Artifact。

随后将正文 Prompt 的序数禁令明确扩展到“第一条/第二条/第三条”，并要求日志、记录和物件使用非编号表述；Version20 新增 `projectLiveRun`，从已消费 SSE 事件投影当前阶段、章节、Provider 用量和终态，并在 text `artifact.committed` 后刷新章节列表。全新页面会话浏览器验收为 `0 error / 0 warning`，桌面监控台能显示正文、章节树、右侧健康和日志，HMR 期间的旧依赖数组提示不计入首载结果。

第二个全新 Run `fast-50k-live-20260820-retry` 验证了上述修复：

- Detail 通过，正文推进至第 10 章并完成一次有界 `retry_evidence`；监控台实时显示章节 1-10，当前阶段、章节、调用数和 Token 与 SSE 最新事件一致。
- 第 9 章的 Evidence 合同失败只产生 `evidence_recovery_decision`，按允许动作重试一次后继续；没有重写已经接受的正文。
- 运行最终在第 11 章因 DeepSeek Provider 余额/调用额度耗尽停止：`90` operations，`83` 成功、`7` 失败，累计 `530,499` tokens，接受正文 10 章、非空白字符 `19,814`。
- 因额度耗尽未到达 `text.check_book_budget`、Cover 或 Export；本次不能宣称完整 5 万字、成本、连续性或文学质量通过。两个 Run 均保持历史只读证据，不恢复、不复制、不改写。

确定性回归：后端全量 `611 passed, 1 warning`，正文 Prompt/场景合同定向 `22 passed`，`compileall` 和 `git diff --check` 通过；Version20 `pnpm build` 通过。剩余真实 Gate 是补充足够的 DeepSeek 额度后，从全新 Run 继续验证预算、Cover、Export 和最终浏览器状态。

## 19. 极速 5 万字真实 Run：DeepSeek 额度复核（2026-08-20）

在用户确认额度补充后，使用全新项目 `proj-a8eb2e5419`、全新项目流水线和全新
Run `fast-50k-live-20260820-065034` 重新开始验收，没有恢复或复制前两次 Run。
Run 创建与启动均成功，但 Brief 的第一次真实 DeepSeek 调用和随后一次低成本
Provider 连通性测试都返回同一公开错误 `insufficient_balance`：
“Provider 余额或调用额度不足，请充值或切换到有可用额度的账号后重试”。

- Run 在 `brief.generate_candidate` 停止，状态为 `awaiting_decision`，保留
  `stage_failure_decision`，没有执行无效 regenerate；9 条 SSE 事件完整落盘。
- Provider usage 为 1 次调用、0 次成功、1 次失败、0 Token；章节列表为空，Cover
  artifact 和 Export 均不存在。配置 readiness 仍报告文本/图片 provider 配置完整，
  但该检查只验证保存密钥和模板，不证明真实账户余额。
- Version 20 `/monitor?project=proj-a8eb2e5419` 正确投影等待决策、当前简报阶段、
  1 次调用/1 次失败、checkpoint 和 9 条实时日志；桌面首载截图无页面横向溢出。
  该页面的浏览器日志只出现一次来自旧 HMR 会话的 Hook 依赖数组警告，当前新页面
  首载没有新增错误；本轮未将其误记为 provider 失败修复。
- Version20 `pnpm build` 通过（TypeScript + Vite，2247 个模块）；保留既有 3D 图谱
  大 chunk 提示，但没有构建错误。

本轮不能宣称正文、`text.check_book_budget`、Cover、Export、5 万字字符数或文学
质量通过。继续真实 Run 的前置条件是当前保存的 DeepSeek 密钥对应账户在真实接口上
通过 smoke test；满足后仍需从全新 Run 重新验收完整链路。

## 20. 知识库搜索与全局加载过渡收口（2026-08-20）

- Version20 本书知识库搜索框改为独立的搜索容器、固定 `42px` 左内边距和不可点击
  的搜索图标，避免 Tailwind utility 拆分时图标与 placeholder 文字重叠；补充
  `type=search` 与可访问名称“搜索知识库资料”。
- 新增 `useLoadingPresence`，全局工作台遮罩在数据准备完成后保留 `220ms`，使用
  `loader-exit` 淡出；Shell 路由内容使用 keyed `route-content-enter` 淡入。两者均
  在 `prefers-reduced-motion: reduce` 下关闭动画。
- 浏览器真实检查：知识库搜索框 computed `padding-left=42px`、图标与文字分离、页面
  横向溢出为 `0`；加载遮罩观察到 `loader-exit`，约 `220ms` 后卸载，内容层为
  `content-enter`；全新页面 console `0 error / 0 warning`。
- Version20 `pnpm build` 通过（2248 个模块）；仅保留既有 3D 图谱 chunk 较大的构建
  提示。

1.1 GitHub 发布仍被真实 Provider Gate 阻断：最近全新极速 Run
`fast-50k-live-20260820-065034` 在 Brief 首次调用即返回 `insufficient_balance`。
在 5 万字 Run 完整通过、内容质量/连续性/稳定性完成单独验收并确认工作树发布范围
前，不执行 GitHub push。

## 21. 全局加载生命周期与发布门复核（2026-08-20）

- `useLoadingPresence` 已覆盖工作台全局遮罩、知识库、故事圣经、创作历史、工作流
  模板与配置、AI 服务设置、监控内容区，以及 Brief 至 Export 的阶段级首载；生成中
  Brief/Spine/Cover/Export 和故事圣经分页也保留退出帧。数据完成后 Loader 先进入
  `book-loader-exit`，约 `220ms` 后卸载，再由页面 `page-in` 或路由
  `route-content-enter` 呈现内容，避免条件渲染直接跳变。
- `prefers-reduced-motion: reduce` 不仅关闭 CSS 动画，也跳过退出等待；加载重新触发时
  `loading || visible` 在同一渲染帧保持 Loader，避免内容先闪现一帧。
- Detail 的前端默认 Prompt 材料表补齐 `historical_record_ids` 与
  `present_actor_ids`，并同步历史主体/当代主体的 `cast_ids` 约束；它现在与后端
  `PROMPT_MATERIAL_KEYS`、运行时 `prompt-detail.json` 和测试夹具一致，不新增兼容路径。
- 确定性门：后端 `611 passed, 1 warning`，旧前端 `121 files / 455 tests passed`，
  旧前端与 Version20 production build、`compileall`、CSS audit、CSS split 和
  `git diff --check` 全部通过。CSS 新基线包含 `66` 个导入文件、`18,934` 行、
  `120` 个跨文件重复选择器；相较旧基线文件数、行数和重复项下降，迁移后的规则与
  字节增长已显式纳入评审基线。
- 浏览器桌面与 `390x844` 复核：知识库搜索框 `padding-left=42px`，图标右缘与
  文本起点分离，页面横向溢出为 `0`，console 为 `0 error / 0 warning`。
- 使用当前本机保存密钥直接请求 DeepSeek 官方 `/chat/completions`，以及通过应用
  `POST /api/providers/test` 测试 `deepseek-v4-pro`/`deepseek-v4-flash`，均返回
  HTTP `402` / `insufficient_balance`。本机保存密钥更新时间仍为 2026-08-12；
  因最小冒烟请求未通过，本轮没有创建新的无效 5 万字 Run，也没有执行 GitHub
  commit、tag 或 push。发布前仍必须保存当前有额度的密钥并从全新 Run 重验
  5 万字、`text.check_book_budget`、Cover、Export、连续性和文学质量。

## 22. 正文与 Evidence 重试根因、计费回执和有界修复（2026-08-20）

额度恢复不解释前两次正文与 Evidence 的重复合同失败。历史 Run 保持只读，本节只从
既有 operation receipt、输入快照和领域错误重新计算失败频率与成本：

- `fast-50k-live-20260820-final` 第 14 章第一场的三个旧 generation receipt 都被记为
  `succeeded`，但诊断均包含同一个未冻结序数 `第一条`。三次分别消耗
  `10,697`、`11,852` 和 `11,832` tokens，共 `34,381`；第二、三次的
  `23,684` tokens 没有带来任何合同进展。旧路径在领域事实门之前标记成功，又把
  完整失败场景和精确违规 token 带入下一次整场生成，形成模型锚定和高成本重复。
- Evidence 在 `fast-50k-live-20260820-final` 的 13 个首次请求中有 6 个合同失败；
  `fast-50k-live-20260820-retry` 的 10 个首次请求中有 4 个合同失败，随后还有 1 个
  correction 再次失败。两个 Run 因这些失败实际增加 11 个 correction/recovery
  Provider 调用，额外消耗至少 `87,623` tokens。
- 旧 Evidence receipt 的拒绝路径在 Gateway 内执行 Pydantic 领域校验，异常越过调用者
  后只留下 `failed + usage=0`。因此监控无法区分“没有拿到 Provider 返回”和“已经
  付费返回但本地合同拒绝”，也低报了失败调用的真实成本。
- DeepSeek 当前结构化能力是 `json_object`，只保证可解析对象，不保证 Pydantic 的
  discriminated union、跨字段互斥、列表上限或冻结引用约束。把这些约束当成上游硬
  Schema 保证，是 Evidence 反复纠正仍失败的最低责任边界，不是余额问题。

新的生产边界如下：

1. 正文场景和 Evidence operation 先持久化 `provider_result`、usage 与诊断，状态进入
   `provider_returned`；领域合同通过后才进入 `succeeded`，拒绝则进入
   `contract_rejected`。传输、鉴权、余额或未取得可解析返回的错误才进入 `failed`。
   Version 20 监控台单列返回调用、合同拒绝调用和传输失败调用。
2. 每场正文只允许一次完整生成。量化事实门失败后，代码抽取包含全部违规 token 的
   最小句段，遮蔽原 token，只保留左右各不超过 180 字边界；修复片段最多 600 字，
   Provider 输出上限 900 tokens。修复后相同或新违规仍存在即抛出
   `SceneProseContractError`，没有第三次隐藏调用，也不回退到整场重写。
3. Evidence 的 Provider 输出改为互斥 `state.type=story|assertion|transition`。
   `transition` 只选择冻结 `source_fact_id`、`supersedes|resolves`、新值与认知状态；
   subject、property、lifecycle 和来源链由运行时代码从冻结事实确定性投影。Gateway
   不再拥有 Evidence 领域校验，初次合同失败只允许既有的一次 correction，仍失败则
   进入显式 `needs_action`，不会改写已接受正文。

确定性证据：正文局部修复、同一违规无进展、Evidence 首次拒绝保留 usage、一次纠正
上限、回执汇总和监控投影的定向回归共 `115 passed`；全量后端 `615 passed, 1 warning`；
旧前端 `121 files / 455 tests passed`，旧前端与 Version 20 production build、
`compileall`、CSS audit、CSS split 和 `git diff --check` 通过。Version 20 没有 test
script，因此没有伪称其存在单元测试套件。

这些结果只关闭本地合同与计费可观测性，不构成真实 Provider 或文学验收。下一道硬门
是创建一个全新三章极速 Run，从 Brief 开始检查每个 physical receipt、Token、正文
连续性、Evidence、Canon/Wiki exactly-once 写回和监控投影。三章失败时必须先固定在
最低责任边界复现，不能直接再开 5 万字 Run；只有三章通过人工冷读后，才允许创建新的
5 万字极速 Run。历史 Run 不恢复、不复制、不改写。

## 23. 三章实跑的篇幅门根因与宽松修复（2026-08-20）

全新极速 Run `fast-three-receipt-v2-20260820-173109` 的 Provider、Evidence 和
exactly-once 写回均成功，但最终失败于 `text.finish_chapters`。冻结全书目标为
`7500` 字，旧硬接受下限为 `6750`；三章冻结目标分别为 `2412 / 2500 / 2588`，
实际为 `1728 / 2050 / 1923`，合计 `5701`。旧路径把编辑软目标误当成完成硬门，
因此一个结构完整、仍需人工冷读的样本在全部写回后仅因 `76%` 的目标比例失败。这不是
DeepSeek 余额、传输、解析或 Evidence 合同问题；继续按 `90%` 强制重生成还会增加
Token 消耗，并可能用填充破坏节奏。

产品决策改为“目标引导、严重不足才阻断”：按模式计算的章节软带以及全书
`90%-110%` 区间只投影 warning；单章低于冻结目标 `50%` 时生成
`chapter_severely_underlength` typed blocker，并在 Evidence/accepted/Outbox 前使用
现有唯一一次章节定向换稿额度；全书低于冻结目标 `70%` 才由最终聚合门拒绝。滚动场景
预算也只追回 `70%` 最低可用篇幅，不把前章短缺强塞给末章。达到这两个最低可用门后，
验收优先看细纲是否讲清、章节之间是否连续、确定性合同和人工内容质量，而不是机械凑字。

确定性夹具复刻了实跑的 `compact / standard / expansive` 布局、三章冻结目标与
`1728 / 2050 / 1923` 输出。新路径只发出 6 个首次场景请求，没有篇幅换稿；三章均完成
Evidence、accepted 版本和 Outbox，正文总量仍为 `5701`，全书只记录
`book_length_soft_band` warning，随后完成 Cover/Export。另有两个回归分别证明：极短
单章在 Evidence 前显式阻断；各章均超过 `50%` 但全书仍低于 `70%` 时最终聚合门仍拒绝。
定向章节/长度/质量合同回归 `64 passed`，全量后端 `617 passed, 1 warning`；旧前端
`121 files / 455 tests passed`，旧前端与 Version 20 production build、`compileall`、
CSS audit 和 CSS split 均通过。

这些结果关闭了本地最低责任边界，但还不是新的真实 Provider 或文学验收。后端必须先
重启到本节代码，再创建完全全新的三章极速 Run；两个历史失败 Run 均不得恢复。新 Run
需检查内容完整性、连续性、Cover/Export 和监控投影，通过人工冷读后才允许进入新的
5 万字极速 Run。

## 24. Detail 场景容量与 Provider 回执责任边界（2026-08-20）

全新 Run `fast-three-soft-v3-20260820-1809` 在 Detail 首个执行单元停止。Provider 已以
`finish_reason=stop` 返回一个可解析且命中结构 Schema 的对象，消耗 `6089` tokens；旧
阶段执行器却在持久化返回前执行场景容量校验，把领域拒绝写成 `failed`，并丢失
`provider_result`。冻结投影要求每章 `2-5` 场，这个下限又由 `2500` 字预算中心除以单场
上限得到，等于把已经降级为软目标的篇幅要求重新变成 Detail 硬门。

修复后的唯一边界是：默认场景下限按章节 `50%` 最低可用篇幅与单场承载上限推导，
`7500` 字三章短篇的范围由 `2-5` 调整为 `1-5`；单一重戏可以一场承载。逐章目标优先
靠近全书软预算，场景容量不能精确达到时使用最近可行总量，只要仍高于全书 `70%`
最低可用门就不要求拆场补字。场景数超出真实结构容量、章槽错误、因果引用错误仍是
确定性拒绝，不因篇幅放宽而取消。

Stage generation 现在先持久化 `provider_result`、usage 与解析诊断并进入
`provider_returned`，再执行领域校验；通过后进入 `succeeded`，拒绝则进入
`contract_rejected`，传输、鉴权、余额或未取得返回才进入 `failed`。进程在返回持久化
后中断时，恢复会复用同一返回，不再重复调用 Provider。确定性回归覆盖单场三章完成、
最近可行 `7200` 字目标、低于全书最低可用容量的拒绝、合同拒绝计费归类，以及
`provider_returned` 恢复不重复调用。旧 Run 保持只读，不执行 regenerate。

## 25. 三章真实 Run、谜题证据门与人工冷读（2026-08-20）

`fast-three-soft-v4-20260820-1832` 证明了 Cover 回执上限修复后的候选可以走到正文，
但其封面 Provider 返回 `negative_constraints=17` 时仍被旧 gateway 在持久化前错误记为
`failed`；该 Run 保持只读。重启当前代码后创建的 `fast-three-soft-v6-20260820-185744`
从全新 Brief 开始完成八阶段，未恢复或复制任何历史 Run。

- DeepSeek 文本与封面图片共 `35` 个 Provider operation，`35` 个均有成功回执，
  `129,143` prompt tokens、`13,625` completion tokens、合计 `142,768` tokens；没有
  `failed` 或 `contract_rejected`，三张真实封面资产和 JSON Export 均已落盘。
- 三章 accepted 正文去空白字符数为 `2,130 / 2,231 / 2,615`，合计 `6,976`，达到
  `7,500` 字软目标的约 `93%`，各章均高于冻结目标 `60%` 最低可用门；系统没有为凑字数
  发起换稿。正文证据链是“记忆空白 -> 私下调查与违规记录 -> 同事承认与支持断裂 ->
  强制重置、反抗及不可逆记忆代价”，人工冷读认为内容完整、主线连续、结局落地；第三章
  从离开公司到被捕的过程被压缩为 handoff 后的场外推进，记录为轻微跳接警告而非硬失败。
- 三章 Evidence 均成功，三笔 Outbox/Canon/Wiki 写回均 `committed`，read model 的
  `quality_decision.structure_contract=passed`、`evidence_status=succeeded`，审稿发现
  只投影为 `review_warnings`，没有隐式重写或循环换稿。

同一轮曾先创建 `fast-three-soft-v5-20260820-184655`。Provider 的十二次规划调用全部
返回并成功解析，但 Detail 预检报 `central_mystery_missing`。根因不是 Provider 额度：
`build_mystery_promise_ledger()` 额外要求 Spine 必须存在 `progress_type=information`
的 turn，把节奏投影类型错误当成谜题证据链。修复后谜题硬门只检查冻结的
`inciting -> climax -> aftermath` 引用及 Detail 覆盖；`external` 或 `relationship`
turn 同样可以承载证据推进。v5 保持只读；尝试直接对其 `stage_failure_decision` 提交
`accept` 又被正确拒绝为 `DecisionReplayConflict`，因为该决策只允许 `regenerate/cancel`，
没有改写历史候选。规划合同定向回归 `134 passed`，随后 v6 全链路通过。

本节关闭三章真实 Provider、篇幅宽松、Evidence/写回 exactly-once、Cover/Export 和
人工冷读门；下一道门是创建全新的 `5 万字极速` Run，持续观察正文阶段、监控 read model、
Provider 回执、连续性与成本。5 万字 Run 不读取 v5/v6 的候选、checkpoint 或正文。

## 26. 5 万字极速 Run 的 Cast 合同阻断（2026-08-20）

全新项目与 workflow 创建的 `fast-50k-acceptance-v1-20260820-191020` 冻结
`word_target_soft=50000` 后从 Brief 开始执行。Brief、Spine 已返回；Cast 阶段的两个
窄调用虽然拿到了可解析 JSON，但在领域合同边界停止：

- `role_demand:proposal:1` 返回一个 `subject_mode=historical_record` 却带有 present
  actor 行为的 demand，`RoleDemandProposalBatch` 拒绝；
- `cast_relation:proposal:1` 的第二条关系压力只写“赵启明作为调度组……双方形成对抗”，
  没有已成立的具体选择、信任、责任或风险，`CharacterRelationBatch` 拒绝。

截至停止共有 `9` 个 Provider operation、`7` 个成功、`2` 个失败，`39,296` tokens；
没有篇幅相关错误，也没有余额或网络错误。Run 保持 `awaiting_decision`，只允许该阶段
合同定义的 `regenerate/cancel`，没有自动 regenerate，避免在未修复上游合同输入前重复
消耗 5 万字链路预算。该 Run 不是 5 万字通过证据；下一步需先修复 Cast Prompt/领域
边界并用小规模 fixture 验证，再由明确决策触发一次有界恢复。

## 27. 5 万字极速 Run 完整链路与 Version20 监控台验收（2026-08-20）

在 Cast 合同修复、Provider 回执分类和篇幅门放宽后，使用全新项目
`proj-7041215a8b` 与全新 Run `fast-50k-acceptance-v14-1787234362` 从 Brief
重新开始，没有恢复、复制或改写任何历史 Run。该 Run 八阶段全部完成：

```text
brief -> spine -> cast -> volumes -> detail -> text -> cover -> export
```

硬链路结果：

- Run `completed`，`pending_decisions=[]`，`failure=null`，
  `quality_decision.accepted=true`，结构合同通过，Evidence 状态为 `succeeded`。
- 20 章均有 `v1-accepted` 正文。按生产合同去除空白后共 `42,443` 字，是
  `50,000` 字软目标的 `84.9%`；最短章 `1,375` 字，全部高于单章严重不足门，
  未为凑字数触发整章重生成。
- Cover 已提交并生成真实资产 `cover-16c54b0fa6b17734591f7c3e`；Export 已提交，
  ZIP 约 `2,415,458` bytes。
- Provider 共 `143` 个 operation：`134 succeeded`、`5 contract_rejected`、
  `4 failed`、`0 pending`，返回 `139` 次，合计 `1,148,670` tokens。合同拒绝均为
  有界局部修复或审稿不可用记录，没有整章无限重试。

exactly-once 写回和读模型检查：

- Story Bible 分页读模型返回 `160` 条事实、`3` 条伏笔；事实 id 和伏笔 id 均无重复。
- 20 个 accepted chapter version 各有 `8` 条 Evidence，共 `160` 条；没有空
  `evidence_refs`，每条事实恰有一个 Wiki transaction id。
- Canon、Wiki、Outbox 各 `20` 个文件，三者 transaction id 集合完全一致且均唯一，
  覆盖 `chapter-1` 至 `chapter-20`，全部 `committed`。

Version20 浏览器验收：

- `/monitor?project=proj-7041215a8b&run=fast-50k-acceptance-v14-1787234362` 使用
  真实 Run read model、Artifact、章节、SSE 日志和 Provider usage；桌面三栏显示
  阶段/产物、中央只读正文和右侧健康/日志，日志保留 `1000` 条，未出现频闪或假进度。
- 桌面阶段切换逐项通过：简报、脊柱、角色、卷册、细纲、正文、封面、导出均显示
  对应真实 Artifact 投影；移动端 `390x844` 隐藏大侧栏并提供阶段下拉与健康日志抽屉。
- 发现并修复 Version20 移动端阶段下拉选择被实时跟随 effect 覆盖的问题：下拉
  `onChange` 现在与桌面侧栏共享 `stageFollowRef=false` 状态所有权。修复后移动端
  选择“正文”保持选中并显示第 20 章真实 accepted 内容。
- 浏览器控制台 `0 error / 0 warning`，桌面截图无异常遮挡，移动端无横向溢出。

内容质量边界仍需人工冷读：

- 42,443 字与结构/Evidence/Export 通过只证明最低可用硬门，不等价于文学质量验收。
  当前样本仍有明显软警告：正式标题投影为“悬疑现实主义”这类类型标签；Detail 中
  `chapter-18` 的 handoff 与 `chapter-15` 重复，正文也出现发布会后处理的重复叙事迹象。
  这类连续性和标题语义问题必须作为人工修订证据处理，不能靠隐藏自动换稿抹平。

本节关闭真实 Provider 完整八阶段、宽松篇幅门、Evidence/Canon/Wiki exactly-once、
Cover、Export 和 Version20 监控投影硬门；**文学冷读与用户验收仍未关闭**。在人工确认
标题、章节交接和重复叙事前，不执行 GitHub v1.1 commit、tag 或 push。

## 28. Version 20 唯一生产前端切换（2026-08-21）

本节关闭 Phase 30 的目录级迁移门，不改变第 27 节对文学质量和 GitHub 发布的限制。

- 用户下载的 Figma Make Version 20 源码继续保留在仓库外
  `$HOME/Desktop/project/Yotsuba Ink - Make Interaction Lab`，只作为设计来源和追溯证据。
- 原 `apps/web` 已完整移至仓库外
  `$HOME/Desktop/project-backups/Yotsuba-Ink/apps-web-legacy-20260821-221754`；备份约
  `659 MB`，包含切换时的未提交源码、依赖和构建产物，可人工恢复，但不进入 Git。
- 完成接入的 Version 20 已成为唯一 `apps/web`。仓库内不存在隔离迁移目录、旧入口、
  Feature Flag、双 Router 或 legacy UI runtime；生产目录也不存在顶层
  `components/`、`views/`、`data/` 及其 import。
- Figma Make 的 `src/data/mock.ts`、本地计时进度和演示按钮没有迁入生产；Projects、
  Workflows、Providers、Knowledge、Run、SSE、Artifact、Decision、Story Bible、Cover
  与 Export 均通过 `services/` 读取真实后端合同。
- Phase 31 作者协作位于该 Version 20 前端的 `running/collaboration/`、`settings/`、
  `state/`、`services/` 和 `contracts/` 边界中，不存在旧前端上的第二份实现。

切换后的确定性门：前端 `5 files / 23 tests passed`；TypeScript/Vite production build
通过并转换 `2936` modules；CSS audit 为 `0` 个跨文件重复 selector、`0` 个重复
keyframe、`11` 个持续动画与 `11` 个 Reduced Motion 保护；结构审计与首屏 CSS 构建门
通过，CSS gzip 约 `27.3 KiB`。后端全量门为 `702 passed, 1 warning`，`compileall` 与
`git diff --check` 通过。浏览器在 `1440x900` 和 `390x844` 复核 Studio、Spine、
Phase 31 协作台、全局协作设置与 Monitor，页面级横向溢出为 `0`，控制台为
`0 error / 0 warning`。这些本地门不得冒充真实 Provider 或文学质量验收。

## 29. Volumes 工作台与 Header ECG 精修、旧路径复审（2026-08-21）

本轮继续只修改 Version 20 唯一生产前端，没有恢复旧前端目录、旧 Router 或旧运行时。

- Volumes 左侧二级栏改为按内容排列的 `72px` 连续卷索引，不再由 Grid stretch 将卷卡
  均分整屏；移动端使用横向可滚动索引。真实点击第二卷后，卷名、卷合同、Turn、人物
  与章节投影同步切换，仍读取同一 `VolumeArchitectureArtifact`。
- 右侧卷合同改为一个统一的卷内节奏编辑面。`promise/conflict/climax/closure` 保持原
  字段和写回路径，但使用 2x2 非对称层级、统一约 `184px` 的节拍区和约 `108px` 的
  textarea；移动端顺序折叠为四拍纵向编辑面。没有新增 Artifact 字段或本地 mock。
- Header 轨迹改为短 SVG ECG：浏览页与真实 Run 活跃阶段分别投影；当前阶段只保留一条
  低频局部 pulse，Reduced Motion 为静态态，不引入全 Header 频闪或计时假进度。
- 清理了新前端中无任何 TS/TSX 消费者的旧 `stream-cursor`、`pulse-dot`、`shimmer`
  样式，并移除 Phase 31 stylesheet 对 Volumes textarea/title 的跨边界接管。CSS audit
  为 `0` 个跨文件重复 selector、`0` 个重复 keyframe、`9` 个持续动画和 `11` 个
  Reduced Motion 保护；首屏 CSS gzip 为 `28.2 KiB`。
- production closure audit 仍无 legacy/shadow/dual runtime marker 或异常 pipeline
  目录。`archive/legacy_run_viewer.py` 是 `/api/archive/runs` 使用的只读历史投影，明确
  禁止 execute/resume/decision/branch/writeback/provider；`openai_compat.py` 是当前
  DeepSeek 等 OpenAI 协议服务商的生产适配器。两者均不是可删除旧运行逻辑，本轮没有
  为满足清理字样破坏历史审计或 Provider 链路。
- 旧前端可恢复备份仍位于
  `$HOME/Desktop/project-backups/Yotsuba-Ink/apps-web-legacy-20260821-221754`，约 `659 MB`；
  仓库内仍只有一个 `apps/web`。

验收证据：浏览器 `1440x900`、`1280x920`、`390x844` 页面级横向溢出均为 `0`，
控制台 `0 error / 0 warning`；前端 `6 files / 25 tests passed`，TypeScript/Vite build
转换 `2936` modules，CSS、structure 与 CSS build gate 通过；后端 `702 passed,
1 warning`，`compileall`、closure audit 和 `git diff --check` 通过。本轮没有调用真实
Provider，不能替代 Phase 31.8 或文学质量验收。

## 30. v1.1 发布收口（2026-08-22）

用户在完整查看 Version 20 迭代、50k 极速模式样本与已记录文学软问题后，明确授权整理并
发布 v1.1。本节关闭代码、文档、浏览器与 GitHub 发布门，不改写第 27 节对真实 Provider
与文学质量的证据边界。

- 版本号统一为 `1.1.0`；README 中英文版新增当前 Version 20 流水线目录与配置页真实
  截图，`CHANGELOG.md` 记录 Phase 28-31 的新增、变更、修复、删除和未关闭门。
- `runtime/novel_workflow/project-order.json` 被确认为本地作品排序数据并加入忽略规则；
  本地 SQLite、项目、运行历史、稿件和 Provider secrets 均未进入发布范围。
- 后端全量为 `702 passed, 1 warning`，`compileall` 与 `git diff --check` 通过；前端
  `8 files / 29 tests passed`，TypeScript/Vite build 转换 `2936` modules，CSS、structure
  和 CSS build gate 通过，首屏 CSS gzip 为 `28.8 KiB`，生产依赖审计无已知漏洞。
- 浏览器在桌面 `1280x720` 与移动端 `390x844` 复核流水线目录、官方平衡配置入口和
  阶段卡切换；移动端页面级横向溢出为 `0`，Header 导航触发器只在移动端出现，控制台
  `0 error / 0 warning`。
- Phase 31.8 真实作者协作 Provider 验收仍未执行；Phase 29 分层规划生产迁移仍按其
  Phase 文档继续。50k 样本的标题语义、Detail 交接和重复叙事继续作为人工文学软问题，
  不伪装为已解决，也不因本次版本发布触发隐藏重试。
