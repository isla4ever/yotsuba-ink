# Phase 12：次世代体验进阶（引导 · 可视化 · 品味 · 性能）

> 状态：实施中（2026-07-26）
>
> 输入：六维并行审计（引导/配置过载/文案/运行可视化/交互摩擦/性能，7 agent，97 条文件级发现）与综合规划。完整审计数据与综合报告存于 workflow 运行记录（wf_4c57e618-52b journal），本文档只保留执行合同。
>
> 产品目标（用户原话的合同化）：一切操作简洁快速、聚焦式分步指引随时可唤起、不上来就砸配置项、作业时有足够可视化、文字专业精简、性能优秀——次世代感来自交互/动效/引导/性能的整体，不是 UI 堆料。

## 1. 六切片总览（来自综合规划，编号沿用）

| 切片 | 目标 | 状态 |
| --- | --- | --- |
| S1 种子数据治理与首启收敛 | 新作品=真实空白+真实必填；新建→开跑 7 屏收敛 4 屏；引导必然出现 | Wave 1 部分（M1）+ Wave 2 |
| S2 阶段配置面三档重分配 | 首屏必需/折叠高级/默认值不展示；消除质量双真相源；Provider 单动作路径 | Wave 3 |
| S3 运行数据管道修复与作业可视化 | 每个数字真实、关键事件都有消费者；N/M 位置感、用量条、章节进度带；状态层不拖垮壳层 | Wave 1 部分（D1/D2/F2）+ Wave 2 |
| S4 创作者语言词汇表 | `lib/terminology.ts` 词汇表 + 全线收敛；内部词零泄漏 | Wave 1 部分（C1-C4）+ Wave 2 |
| S5 聚焦式分步指引系统 | 自研轻量 tour 引擎（data-tour 锚点注册表 + flows + 状态持久化）+ 空态 CTA + 提示迁移 | Wave 4（依赖 S1/S4） |
| S6 壳层过渡完整性与首屏性能 | studio↔creation 过渡、向导/拦截框入对话框体系、首屏 CSS/JS 减负 | Wave 1 部分（F1）+ Wave 3 |

关键调和决议（全文见综合报告）：演示种子值采「create 时清空叙事默认」方案；五步引导收敛为 3 步（故事起点/连接 AI 服务/确认启动），参考与模式以「已用默认可改」卡入确认页；三档模式统一叫「创作模式·极速/平衡/精细」，唯一来源 qualityModeProfiles；Token 用户面叫「用量额度」；tour 遮罩静态 ring 无脉冲、RM 全归零、flows 懒加载不进首屏。

## 2. 聚焦式指引系统合同（S5，实现时以此为准）

- 锚点：`data-tour="<surface>.<anchor>"`，`lib/tour/anchors.ts` as-const 注册表派生联合类型，组件用 `tourAnchor(id)` helper 挂载；每步支持锚点回退链。
- 步骤：TourStep{id, anchors[], title, body, placement, route, when(ctx), advanceOn, modes}；TourFlow{id, trigger: first-visit|manual, steps}。flows 内容采用审计交付的锚点清单：studio 6 步、setup+planning 8 步、run 按阶段分段 9 步、bible 4 步。
- 呈现：单定位层 box-shadow 挖洞 + 静态描边 ring（复用焦点环 token）；步骤卡 role=dialog + 焦点陷阱 + Esc；不对页面设 aria-hidden；RM 下滚动/位移/淡入全归零。
- 入口：GlobalToolDock「引导」项 + 命令面板「重新播放引导」+ setup 完成页「带我看一遍工作台」+ 空态旁轻入口。
- 持久化：localStorage `nw.tour.v1`{version, completedFlows, dismissed, lastStep}；与 GuidedSetup 的「稍后继续」共用该约定；版本号 bump 触发重播提示。
- 纪律：运行推进中不自动弹；overlay 打开时挂起；空态时降级为指向空态 CTA 的单步。

## 3. Wave 实施顺序

- **Wave 1（P0，并行四线）**：M1 种子治理（后端 templates/project_store + 前端 setupProgress）；D1/D2/F2（usage 事件订阅修复、伪进度清除、localStorage 写入节流）；C1-C4 + A2（内部词裸奔修复 + /run/* 空态出口）；F1（首屏 CSS 拆分）。注：审计的 D3 build 红灯是与 11.3 并行时的中间态，已消。
- **Wave 2**：S4 词汇表全量 + S3 余项（N/M 位置感、用量条、结算驻留、章节进度带、Context 拆分 F5/F6）+ S1 余项（3 步引导重构、hint/placeholder、向导收敛）。
- **Wave 3**：S2 配置三档重分配 + S6 过渡与可达性（studio 过渡、向导对话框体系、focus 单轨、移动端 studio 导航）。
- **Wave 4**：S5 tour 引擎与四份 flows（届时 S1 新引导与 S4 词汇已就位）。
- 锚点属性不等 Wave 4：Wave 1-3 触碰组件时按 anchors.ts 约定顺手挂。

## 4. 实施进度

当前进度（2026-07-27）：

- `Wave 1 已完成`（三线并行，统一复核通过）：
  - **M1 种子治理**：`workflows/seed_policy.py` 划定叙事种子清单（info 六字段 + summary.ending_direction + global title/theme），`project_store.create` 复制模板时深拷贝清空（模板本体与旧 demo 路径不动，测试锁定）；引导对新作品必然出现（浏览器实证：新建作品后五步引导出现、core_concept 为空）。B4 单模板跳步模型层就绪（组件接线归 Wave 2）。
  - **运行真实性**：D1 usage 订阅切到真实事件（`stage_usage_updated/finalized`），结算卡 token/成本/耗时接通、无数据显「暂无」不显假 $0；D2 伪进度 0.42/0.52 清零（改 `ready_count+failed_count/total` 真实派生，无 counts 不渲染进度条）；F2 localStorage 写入 trailing throttle ≤1 次/秒 + 暂停/完成/失败/beforeunload 强制 flush（120 条高频事件 2 秒 2 写测试锁定）；C1-C4 内部词清零（新增 `lib/runEventLabels.ts` 48 项作家语言映射，禁用词 grep 零命中）；A2 七阶段空态前置说明 + 回到创作规划 CTA（`stageEmptyState.ts` 纯函数）。
  - **F1 首屏 CSS 拆分**：144 文件 → 5 入口（core 38 / planning 7 / running 96 / bible 2 / settings 1），首屏 gzip **91.1KB → 44.8KB（-51%）**；级联顺序用「重复选择器×装载秩」不动点算法验证 530 个跨文件重复选择器零胜者翻转；13 个文件保守晋升 core（逐一验证的真实依赖/级联冲突，非猜测）；审计脚本升级 schema v2（入口归组锁定）+ 新增 `check:css-split` 构建断言（97 个懒文件零首屏泄漏）；12 项预算逐字节一致证明纯搬运。<40KB 差 4.8KB 的回收路径（planning 面懒化）归 Wave 3。
  - 统一复核：后端 `269 passed, 1 skipped`；前端 `97 files / 387 passed`；构建零错；CSS 审计通过；css-split 断言通过（首屏合计 46.4KB gzip 含 flow-vendor）。
  - 已知项：planning 页残留「旧港」字样来自知识库 demo 回退文档标题（`services/knowledge.ts`），属 Wave 3 知识库按作品隔离范畴；`InfoCharacterEditor.tsx` 内一处示例文案随 Wave 2 hint pass 复核。

- `Wave 2 已完成`（两线并行，统一复核通过）：
  - **W2A 三步引导**：五步收敛为「故事起点 → 连接 AI 服务 → 确认启动」，参考方式/创作模式降级为确认页可展开卡（复用原组件），reference_summary 内联可编辑并标注去向；篇幅只选一次（保留字数区间、target_length 自动派生，依据全消费者核实）；InputField 合同加 hint/placeholder（六字段引导文案）；「稍后继续」持久化 + 图标语义修正；向导单模板一步直达；表单回车前进。
  - **W2B 作业可视化 + 状态性能**：RunEventsContext 拆分（40 条流式 delta 壳层重渲 0 次，渲染计数测试证明）+ 事件增量索引消灭 4 处 O(n×m) 扫描；Header「第 N/M 阶段」位置感 + 用量额度显示（零 Token 字样）+ 预算持久状态条（死代码清除）；结算卡可驻留（真实数据 + 用户驱动关闭 + 4s 一次性 stroke-drain 进度环）；正文章节格进度带与张力心电合并为双行签名带；AI 服务重试作家语言可见。新增 devDependency happy-dom（渲染计数测试必需）。
  - 统一复核：后端 `269 passed`；前端 `109 files / 428 passed`；构建零错；CSS 双审计通过（Infinite 24）。浏览器实测（`output/playwright/phase12-w2/`）：三步引导结构、Header 位置/用量、单模板一步建作品全部生效；全新作品字段为空 + hint/placeholder 到位（API 级验证）。
  - 环境事故记录：验证期间发现磁盘 default 工作流被旧后端进程时代污染为「新版本号 + 旧内容」，`seed_defaults` 因版本号一致跳过覆写导致 hint 不生效——已删除后重播种恢复。**已知加固候选**：seed_defaults 的版本比较可升级为内容哈希比较，防同类污染（排 Wave 3 顺手做）。验证用垃圾作品已全部清理。
- `Wave 2C（S4 词汇表全量）进行中`。

## 5. 验收基线

进入本阶段时：后端 265 passed / 前端 93 files 368 passed / build 零错 / CSS audit 通过（Infinite 24）。每个 Wave 收口跑全量 + 浏览器实测；Phase 11.4 的 accent 扩展与全视口矩阵并入 Wave 3/4 收口一并执行。
