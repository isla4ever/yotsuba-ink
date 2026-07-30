# Phase 11：作品工作室（Studio Shell）与品味升级

> 状态：方案定稿，实施中（2026-07-26）
>
> 承接：Phase 10 已完成 10.0–10.4a（阶段合同、App Shell、Story Bible、签名视图、质量 L2 后端）。本阶段响应两项新产品诉求：(A) 从「单作品工作台」升级为「多作品工作室」双层壳；(B) 视觉与动效品味从「工整常规」升级到「克制的高级科技感」。
>
> 调研依据：外部灵感调研（NovelCrafter/Sudowrite/Scrivener/Linear/Notion/Arc 的库→作品 IA；Linear/Vercel/Raycast/Perplexity/Cursor 的暗色视觉语言；View Transitions/Streamdown/FlowToken 的动效范式）与仓库现状调研（project_id 恒等于 run_id、workflow 单例假设雷区清单、模式遮罩与流式实现定位）。结论均已核实来源，详见调研记录。

## 1. 信息架构：双层壳

```text
Studio Shell（/studio，新默认首页）          Creation Shell（现有壳，进入作品后）
├─ 全局侧栏                                  ├─ 作品侧栏（现 WorkbenchSidebar 改造）
│   作品库（卡片墙）                          │   [作品名 + accent 色标 + 返回工作室]   ← NovelCrafter 惯例
│   工作流模板                                │   创作流程（7 阶段树，保留）
│   知识资料（全局池）                        │   Story Bible（保留）
│   创作历史（全库，按作品分组）              │   知识资料 / 创作历史（本作品过滤）
│   模型与设置                                │   模型与设置
└─ 主区：作品卡片墙 + 新建作品 + 模板管理     └─ 主区：Planning / Cockpit / Running / Bible（不变）
```

核心决策：

1. **作品（Project）成为一等实体**：`{id, title, summary, accent_hue, workflow_id, status, created_at, updated_at, latest_run_id}`。一个作品绑定一份专属 workflow（从模板复制而来），可发起多个 run（重写/续跑），历史按 project_id 过滤（API 已支持，从未被用）。
2. **工作流模板**：模板 = 存在 workflow store 里的可复制配置（`is_template` 标记）。新建作品时选择模板 → 复制为该作品专属 workflow；「另存为模板」从任意作品配置提取。`seed_defaults` 的版本覆写必须限定 default 一个 id，不得覆掉用户模板。
3. **进度可视化**（写作产品普遍薄弱、我们的差异化点）：作品卡显示七阶段进度点阵（真实 run 状态派生）、总字数、最近活动时间、状态徽标（创作中/待确认/已完成/失败）。
4. **每作品 accent 色**（Arc 验证过的上下文锚定）：作品建立时分配 accent_hue，进入作品时 Creation Shell 以 CSS 变量浸润（侧栏色标、当前项指示、进度点）。模式色（快/稳/精）语义不变，两者不混用。
5. **兼容约束**：同时只允许一个 run 在跑（后端 SSE lease 本就按 run 锁；全局单跑是产品约束，切换作品时沿用现有「运行中拒绝切换」保护）。多 run 并行明确延期。
6. **旧数据迁移**：既有 24 条历史 run（project_id==run_id）在 Studio 中归入「未归档作品」组惰性展示，不伪造作品实体；用户可从历史 run 一键「归档为作品」（创建 Project 并回填）。

## 2. 后端最小增量（11.0）

依据现状调研的结论清单：

1. `storage/`：`JsonStore(root/"projects")`；`api/routes/projects.py`：`GET/POST /api/projects`、`GET/PATCH/DELETE /api/projects/{id}`、`GET /api/projects/{id}/summary`（聚合最新 run 摘要：阶段状态、字数、更新时间——读 run_history_store，不新算）。
2. `api/routes/workflow.py` 扩展：`GET /api/workflows/{id}`、`POST /api/workflows/{id}/duplicate`（新 id + 可改名）、`DELETE /api/workflows/{id}`（default 与被作品引用的拒绝删除）；workflow schema 加 `is_template: bool = False`、`display_name` 沿用 name。
3. `bootstrap.seed_defaults` 只覆写 `default-novel-workflow`，其余 id 一律不动（回归测试锁定）。
4. run 创建链路：`RunRequest.project_id` 一级字段；`routes/runs.py` 写入 run.json 顶层与 state；`run_history_store` 已有回退链不变。前端 `buildRunInputs` 附带真实 project_id 与作品 title（消灭「雾港旧声」硬编码同名问题）。
5. 知识库隔离（可选，随 11.2 前端一起）：前端把硬编码 `'default'` 换成作品 id；后端已支持。

业务逻辑不进 api/routes；project 聚合逻辑放 `storage/project_store.py` 或复用 run_history_store。

## 3. 视觉品味升级合同（11.1 基座）

原则来自调研共识：**克制本身是高级感的来源**（Linear 无 glow、Vercel 核心 UI 零渐变、单 accent 纪律）；科技感做在层级精度、边缘高光、动效时机上，不做在装饰堆料上。这与既有性能纪律（空闲零循环、Reduced Motion 归零）完全兼容。

### 3.1 表面体系 v2（design-tokens.css 重铸，兼容别名保留）

- **四级表面阶梯**，蓝黑同色相逐级推亮（每级 +3~5% 亮度），不许跳级：`--surface-0`（canvas #070b14）→ `--surface-1`（面板）→ `--surface-2`（卡片/弹层）→ `--surface-3`（悬浮态/menu）。暗色下 elevation 靠亮度不靠阴影。
- **描边三档**：`rgba(255,255,255,.06/.08/.12)`（默认/卡片/交互强调）；**卡片顶部高光** `inset 0 1px 0 rgba(255,255,255,.07)` 成为卡片标配（模拟顶光源）；容器一律禁 glow 和外阴影（阴影只留 overlay 层）。
- 圆角收敛两档：6px（控件）/ 12px（卡片、弹层）；现有 4/7/10/14 逐步映射迁移。
- 字重纪律 400–500，层级靠颜色与间距；全部指标数字 `font-variant-numeric: tabular-nums` 或 mono。
- accent 纪律：全局 accent 一个；模式色只出现在模式控件、当前阶段指示、进度；作品 accent 只出现在作品标识与壳层点缀。第二个彩色即破功。

### 3.2 模式切换重设计（11.1 核心交付，替换 QualityModeTransitionOverlay）

现状：全屏半透明遮罩 + 居中静态卡（用户判定：丑、平庸）。另有一组无消费者的 `quality-mode-notice` 死样式族（header-controls.css），一并删除。

新方案（全部一次性动效）：

1. **色彩浸润**：切换瞬间壳层模式色 CSS 变量以 260ms 过渡浸润（模式分段控件、侧栏当前项、Header 状态点同步换色）——Arc 的「颜色即上下文」。
2. **径向揭示**：支持 View Transitions 的浏览器，从模式按钮点击点做 `clip-path: circle()` 扩散揭示新模式色的壳层状态（360ms，easing Enter）；不支持/Reduced Motion → 直接切换。
3. **模式徽章**：中央卡重设计——surface-2 + 顶高光 + 模式 glyph（几何符号：快=箭羽三线 / 稳=同心双环 / 精=菱形棱镜，SVG 一次性 draw-in 240ms）+ 模式名 + 一行控制权差异说明 + 标题文字**单次**掠光（shine 一遍即停）；900ms 后 120ms 退场。`pointer-events:none`、`role=status` 保留。
4. 运行中锁档的拒绝反馈沿用现有实现，不加动画惩罚。

### 3.3 流式文字 v2（11.3）

依据 Streamdown/FlowToken 共识：

- 粒度从句读改**词级**：`useStreamReveal` 保留缓冲/backlog 追平/Reduced Motion 跳过骨架，flush 间隔 ~50ms 批量；渲染层只对**新挂载的词 span** 播 150ms opacity fade（backlog 加速时切 blur→sharp 变体掩盖成批感）；**流结束整体剥离动画包装层**（已完成章节零动画 DOM 开销）。
- 光标：细线 1.5px（正文是纸不是终端，弃块状隐喻），仅流式进行中存在（状态信号豁免），完成即移除——「光标消失=完成」语义。首 token 前空窗用 3-5 行宽度递减 shimmer 骨架（加载期动画，合规）。
- 钉底：核对 `useWritingViewport` 与「上滑立即脱钩 + 回到生成位置」既有合同，缺口补齐（用 overflow-anchor 或现逻辑增强）。
- 中断清理：停止时清缓冲、移光标、标注未完成（对齐既有恢复语义）。

### 3.4 图表质感 pass（并入 11.4）

签名图统一：accent 单色 + 纵向渐变面积填充（20-30% 渐隐）+ 网格 `rgba(255,255,255,.05)`；数据点无 glow（Linear 本尊不用）。

## 4. 切片与节奏

当前进度（2026-07-26）：

- `11.0 已完成`：Project 实体（`storage/project_schemas.py` + `project_store.py`，accent_hue 调色序列纯函数分配、`proj-{uuid}` id、模板复制为 `wf-{project_id}`）；`/api/projects` CRUD + summary 聚合（读 run_history 现成摘要）；workflow `GET/{id}`、`POST/{id}/duplicate`、`DELETE/{id}`（default 与被引用者三重保护）+ `is_template` 标记；`RunRequest.project_id` 一级字段贯通（run.json 顶层 + state + history 过滤），`latest_run_id` 在创建与流收尾两个薄层挂点回填；`seed_defaults` 只覆 default 有回归测试锁定。后端全量 `265 passed, 1 skipped`（+14）。
- `11.1 已完成`：表面体系 v2 落地 design-tokens（--surface-0..3 四级蓝黑推亮、--stroke-1..3、--card-top-highlight、--radius-control/surface 两档），三处基类接管（壳层 Header/侧栏 = surface-1、共享 Dialog/Sheet = surface-2 + 顶高光、命令面板 = surface-3）。模式切换四要素交付：260ms 色彩浸润、View Transitions 径向揭示（WAAPI clip-path circle，点击点到最远角；VT 不支持或 RM 瞬时降级）、模式徽章卡重写（surface-2 + glyph stroke draw-in 一次即停 + 标题单次掠光 + 模式色 7% 径向淡出背景，替换 74% 全屏压暗）、quality-mode-notice 死样式族清除。前端 `85 files / 326 passed`、构建零 type error、CSS 审计通过（Infinite 保持 24、keyframe 净持平：+2 一次性 −2 死样式）。
- 11.1 浏览器验收（`output/playwright/phase111/`）：VT 支持环境三档切换徽章出现/清除正常、切换后无限动画 0、Reduced Motion 下瞬时切换且 `document.getAnimations()=0`、控制台 0 errors/0 warnings。
- `11.2 已完成`：`/studio` 成为默认首页（Studio 侧栏：作品库/新建作品/工作流模板/知识资料/创作历史/设置）；作品卡片墙（surface-2 + 顶高光 + accent 色条 + 七阶段真实进度点阵 + 字数/相对时间/状态徽标，hover 仅描边增强）；新建作品向导（书名+概要 → 模板卡片单选 → POST /api/projects 复制专属 workflow → 进入创作壳）；模板管理主区分栏（复制/删除/另存为模板在作品档头）；未归档运行折叠组（旧 run 惰性展示 + 归档语义不伪造迁移）；创作壳侧栏作品档头（accent 色点 + 作品名 + 返回工作室图标 + 另存为模板）。五个单例雷区逐项拆除：storage 四 key 按作品作用域（空 scope=未归档兼容旧数据）、workflowApi 按 id 读写不再覆写 default、runInputs 书名硬编码消灭（title 从 Project 来 + project_id 贯通）、openRun 按 run 的 project_id 切作品上下文。前端 `91 files / 351 passed`、构建零 type error、CSS 审计通过（Infinite 24、keyframe 净零）。
- 11.2 浏览器验收（`output/playwright/phase112/`）：完整闭环走通——冷启动落 /studio、新建向导两步创建「潮汐档案馆」、进入创作壳（档头 + 页面标题 = 作品名）、返回工作室看到进度卡、点卡重进恢复上下文；未归档组显示 10 条历史；控制台 0 errors/0 warnings。注：验收中发现后端旧进程 404（Project 路由是热加载前启动的），重启后正常——部署上无影响。
- `11.3 已完成`：流式文字 v2。词级渲染层 `StreamingProse`（中文 2-4 字块偏移分词/英文空格词、token key=起始偏移的前缀稳定合同——已 reveal 词永不重播；backlog 加速档切 blur→sharp 变体且不改已挂载 span）；**流结束切回纯 textarea，已完成章节零动画 DOM**（测试锁定）；光标重做为 1.5px accent 细线 steps(2) 步进闪烁（替换渐变呼吸，一换一保持 Infinite=24）；首 token 空窗 3 行递减 shimmer 骨架（有界 6 次迭代）；`useStreamReveal` 暴露 pace 信号 + 新增 word 断点模式；钉底/上滚脱钩合同一行未改；顺手清理 5 条死 keyframe（净 68→66）与一个流式 div 误中可编辑提示色的真隐患。前端 `93 files / 368 passed`、构建零 type error、CSS 审计通过。

| 切片 | 内容 | 依赖 | 验收 |
| --- | --- | --- | --- |
| **11.0 后端 Project 与模板 API** | §2 全部；测试锁定 seed 只覆 default、模板不可误删、project 聚合 | 无 | pytest 全量；API 合同测试 |
| **11.1 视觉基座 + 模式切换重设计** | §3.1 表面体系（兼容别名渐进迁移，先壳层与卡片基类）+ §3.2 完整交付 + 死样式清理 | 无（与 11.0 并行） | vitest/build/audit；浏览器实测切换动效三档、VT 降级、Reduced Motion 归零 |
| **11.2 Studio Shell** | /studio 库页（卡片墙+进度点阵+新建作品向导+模板管理）+ 双侧栏切换 + 返回工作室 + 历史按作品分组 + 未归档作品组 | 11.0、11.1 | 全量测试；浏览器走通「新建作品→选模板→五步引导→开跑→返回工作室看进度」 |
| **11.3 流式文字 v2** | §3.3 全部 | 无（可与 11.2 并行） | 流式中/完成/中断/Reduced Motion 四态实测；已完成章节零动画 DOM |
| **11.4 收尾** | 作品 accent 浸润、图表质感 pass、知识库按作品隔离、八视口矩阵 + Reduced Motion 全矩阵 | 11.2 | Phase 8.7 级浏览器矩阵 |

## 5. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 表面体系重铸引发全站视觉回归 | 新 token 以别名映射渐进接管，先壳层/卡片基类，逐页迁移走 CSS 审计所有权流程 |
| View Transitions 兼容性 | 特性检测 + 三级降级（VT→变量过渡→瞬时）；Reduced Motion 全部瞬时 |
| 双壳改造踩 workflow 单例雷区 | 现状调研已列全雷区清单（storage.ts 四 key、useSetupFlow key、useRunHistoryActions 覆写、runInputs 硬编码），11.2 逐项处理并写回归测试 |
| 词级流式的性能回退 | 只动画新增节点、流结束剥离动画层、50ms 批量 flush；保留 backlog 直接追平通道 |
| 「科技感」滑向装饰堆料 | §3 合同：容器无 glow、单 accent、循环动画零新增；全部动效一次性/状态驱动 |
