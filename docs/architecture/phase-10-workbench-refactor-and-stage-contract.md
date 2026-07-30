# Phase 10：产品级工作台重构与阶段职责合同

> 状态：方案定稿待评审（2026-07-26）
>
> 定位：本文档是 `target-product-refactor-roadmap.md` 之后的下一轮总方案。Phase 0–8.8A 的既有成果（状态拆分、CSS 审计、草稿安全、不可变交付、Provider 模板体系）全部保留；phase-9 系列已完成切片（9.0–9.5C-2）的产出保留；**phase-9 尚未实施的 9.5C-3 ~ 9.10 目标并入本方案对应切片，不再按旧编号单独推进**。
>
> 与旧路线图的冲突处理原则见 §6.1「视觉方向修正」。其余合同（阶段产物合同、SSE 合同、三档模式权限矩阵、幂等写回、预算熔断）继续以 `stage-artifact-contract.md` 与 roadmap §9–§13 为准。

---

## 1. 方向评审：这条路线能不能产出「可投稿」的小说

### 1.1 结论

**骨架成立，短板不在流程，在质量系统深度和 Prompt 层。**

当前架构（结构化 Artifact 链 → Canon 事实账本 → 质量阀门 → 幂等写回 → 检查点恢复）在同类开源项目中是最完整的一档，它能稳定产出「结构完整、连续性可控、不烂尾」的长篇初稿。但「可投稿质量」要求的是文学层面的达标，而当前有四个系统性缺口决定了正文上限：

| # | 缺口 | 现状证据 | 影响 |
| --- | --- | --- | --- |
| 1 | **质量引擎是确定性规则 v1，没有模型评审** | `quality/engine.py` 分数公式为 `0.92 - 0.06×warning - 0.28×blocking`，findings 只覆盖结构缺失、硬规则冲突、承接信号缺失和粗糙重复度 | 只能判断「结构对不对」，无法判断「写得好不好」。roadmap §9.5 承诺的 `model_review.py` 未落地 |
| 2 | **Prompt 是 10 段拼装的单字符串** | `stages/prompt_plan.py::PromptPlanBuilder` 无 system/user 分离、无约束优先级、Token 超限没有分层裁剪 | 长上下文里硬约束和参考资料同权重，模型对硬规则的遵循率不可控 |
| 3 | **没有风格规格（Voice Spec）** | 全链路没有任何叙事人称/时态/句长节奏/禁词/对话叙述比的规格产物 | 文风漂移和人物 OOC 只能靠事后目检，这是长篇最贵的返工来源 |
| 4 | **张力与节奏无量化** | 无任何按章打分的节奏视图（对照 PlotPilot 的张力心电图 0–10 曲线） | 中段疲软、高潮平淡这类结构病要在几十万字之后才被人发现 |

因此本轮的资源分配定为：**阶段职责合同（§3）+ Prompt 分层（§4）+ 质量系统 L2（§5）是「可投稿」的正面战场；UI 重构（§6–§7）是产品成立的战场**——两者并行推进，但任何 UI 切片不得挤占 §3–§5 的合同实施。

### 1.2 已经做对、必须守住的决策

- Story Brief 是唯一默认人工硬闸门；正文必须在全书细纲完成后开始。
- Canon 事实账本（`target + claim_key` 归并、冲突人工裁决、superseded 时序）——这是同类项目普遍没有的能力。
- 稳定提交边界 + 章节级幂等（重试不重复计费、不重复写回）。
- Fake Provider 下全链路可走通的 demo 语义。

## 2. 三档模式评审

### 2.1 分工是否明确

**后端分工明确，用户侧表达不及格。**

后端矩阵（`orchestration/control.py`、`quality.py`、`helpers.py`）已经把三档差异实现为：确认点（无 / 仅 Info / 逐阶段）、自动修订轮次（0/1/2）、候选策略（无 / judge 择优 / 人工三稿）、阀门严格度。这是清晰的**控制权模型**，不是价格档位——方向正确。

问题在三处：

1. **前端表达弱**：档位差异只有 `lib/qualityModes.ts` 里三行文案，roadmap §17.4 验收项「新用户 30 秒内能理解三档差异」实际未达成。切档时应展示一张「谁在什么时候拍板」的对照卡（确认点 × 候选 × 修订 × 预算），而不是一句 slogan。
2. **极速档没有质量底线**：fast 档 `retry_on_fail=False` 且修订轮次为 0，意味着极速产物可以带着 warning 一路跑完。修正合同：**三档共享同一条硬阻断线**（结构合同失败、世界观硬规则冲突、Canon 冲突必须停下），档位只调节 warning 级别的处理方式。极速=warning 记录不修订；平衡=warning 自动修订 1 轮；精细=warning 升级为人工决策。
3. **精细档缺模型辅助**：balanced 有 judge 择优，deep 反而把全部评审负担压给人。质量系统 L2 落地后，deep 档的人工定稿页应默认附带模型评审报告（人仍然拍板，但不是裸读几千字）。

### 2.2 修正后的三档合同（一句话版）

| 档位 | 用户角色 | 系统承诺 |
| --- | --- | --- |
| 极速生产 | 看结果 | 自动跑完全链路；硬错误必停；产物全部可追溯可导出 |
| 平衡创作 | 定方向 | Info 定稿后自动生产；warning 自动修订一轮；用户可随时抽查 |
| 精细定稿 | 逐稿拍板 | 每阶段等待定稿；附模型评审报告与修订候选；系统不替用户定稿 |

## 3. 阶段职责合同：世界观与人物网的迭代规则（本方案核心）

### 3.1 总原则

**世界观和人物网既不是一次性生成，也不是无约束迭代，而是「Info 基线 + 逐阶段限额拓展」。**

- Info 建立**基线**（baseline）：之后任何阶段不得推翻，只能引用、细化、拓展。
- 每个阶段有**明确的拓展方向和配额**：拓展什么、拓展多少、写到哪，全部入合同校验（前后端双重阻断，沿用 Phase 4 的引用校验机制）。
- 一切拓展必须**可溯源**：新实体/新关系/新设定记录 `first_appearance_stage`（+chapter），这是关系网时间轴和连续性审计的数据基础。

### 3.2 各阶段拓展配额表

| 阶段 | 回答的唯一问题 | 世界观拓展 | 人物网拓展 | 禁止事项 |
| --- | --- | --- | --- | --- |
| **Info** | 这个项目方向成立吗 | 建立基线：时间/空间/规则/社会四类锚点，硬规则 ≤ 12 条（超出说明设定过载） | 5–9 名主要角色（tier：protagonist / major），关系 8–20 条；≥1 个阵营雏形 | 不得出现卷/章结构、具体情节序列 |
| **Summary** | 故事主干和结局成立吗 | **0 新锚点**，只允许引用既有锚点标注「主干依赖」 | **0 新人物**；只写人物弧（arc/pressure/next）与关系压力变化标注 | 不得新增人物、地点、组织；发现基线不够用 → 阻断并提示回 Info 修基线 |
| **Outline** | 中观节奏和各卷职责成立吗 | 每卷 ≤ 3 条世界揭示（必须引用 Info 锚点，或显式声明新锚点并给出揭示时机）；可新增组织/阵营实体 1–2 个/卷 | 每卷可新增 2–4 名配角（tier=supporting，需给最小档案：定位/立场/与主角关系）；伏笔投放注册 | 不得修改 Info 硬规则；不得新增 protagonist/major 级人物 |
| **Detail** | 每一章可以直接施工吗 | 只能引用与细化（把锚点落到具体场景），**不得新增硬规则** | 每章 ≤ 2 名 NPC（tier=minor，自动生成最小档案）；关系变化必须绑定章节号 | 不得出现未注册组织/地点作为关键场景；NPC 不得承担关键剧情功能（承担者必须升级为 supporting 并回填 Outline 层档案） |
| **Text** | 这一章可以定稿吗 | **0 新实体**。正文出现未注册名字 → 生成 `proposed entity` 写回提案，人工/规则确认后升级注册 | 同左；关系变化只能通过 wiki_writebacks 走 Canon 流程 | 未注册实体直接定稿（校验阻断） |
| **Cover/Export** | — | 只读 | 只读 | — |

配额数值（12 条硬规则、2–4 配角/卷、2 NPC/章）作为**默认值进入 `quality_policy`**，允许按工作流配置调整，但必须显式配置，不允许无上限。

### 3.3 人物网数据模型升级

现状问题（调研证实）：`CharacterNode.faction` 默认「未分组」且模型合同不要求输出；关系边只有自由文本 `relation` + `strength`；前端在数据缺失时**伪造**派系（按 index 奇偶）和辐射边——这是「关系网不像大型网络」的根因：数据模型只支撑 7 个节点的演示。

目标模型（`workflows/run_schemas.py` + `contracts/run.ts` 同步）：

```text
Faction                      # 阵营升级为一等实体
  id / name / stance(protagonist_side|antagonist_side|neutral|hidden)
  first_appearance_stage / description

CharacterNode
  id / name
  tier: protagonist | major | supporting | minor | npc     # 新增，驱动分层渲染与配额校验
  faction_id                                               # 引用 Faction，替代自由文本
  role / status / avatar_seed
  first_appearance_stage / first_appearance_chapter        # 新增，驱动时间轴
  voice_ref                                                # 指向该人物语声表（§4.4）

CharacterEdge
  source / target
  kind: kinship | romance | ally | rival | superior | trade | secret | other   # 新增枚举
  relation                                                 # 保留自由文本描述
  polarity: positive | negative | complex | neutral        # 新增，驱动边配色
  strength: 0..1
  valid_from_stage / valid_from_chapter                    # 新增
  history[]: {chapter, change, source_artifact}            # 关系演化记录（Outline/Detail/Text 写回追加）
```

配套清理（P0）：

- 删除 `infoRecommendationModel.ts` 中按 index 奇偶伪造 faction、无关系时编造主角辐射边和公式化 strength 的全部路径——**数据缺失就渲染缺失态**，这与 Phase 8.0 的「无伪指标」纪律一致。
- Outline 写回新关系边 strength 固定 0.58 的魔法值改为模型输出 + 合同校验。
- Info 的模型合同（`StoryBriefContract`）与 prompt 输出结构同步升级：要求输出 faction、tier、kind、polarity。

### 3.4 为什么这样切（防「为分阶段而分阶段」的自检）

每条配额都直接服务正文质量：

- Summary 禁止新增人物 → 强迫主干用基线人物讲完，防止「用新角色解决剧情问题」这一最常见的结构逃逸。
- Outline 配角配额绑定卷 → 配角有明确的结构职责（该卷的对手/助力/信息源），而不是散点登场。
- Detail NPC 上限 + 「关键功能必须升级 tier」→ 保证正文阶段 Context Packet 里的人物全部有档案可注入，防 OOC。
- Text 零新实体 → Canon 账本闭合，连续性审计有完整实体宇宙可查。

## 4. Prompt 体系重构：主次分明、严格可控

### 4.1 结构：从单字符串到 system/user 分离

`PromptPlanBuilder` 改为产出 `{system, user}` 两段（Provider 层已用 OpenAI SDK，天然支持）：

- **system**：角色定义 + L0 硬约束 + 输出合同（JSON schema + 长度预算）+ 禁止事项。稳定、可缓存。
- **user**：阶段任务 + 分层上下文（见下）。

### 4.2 约束金字塔与裁剪顺序

上下文注入按优先级分层，Token 超预算时**从 L5 向 L1 裁剪，L0 永不裁剪**（roadmap §11.4 的 Context Packet 优先级推广到所有阶段）：

```text
L0  世界观硬规则 + Canon 阻断警告 + 阶段配额约束（§3.2）     [system，不可裁剪]
L1  阶段任务与产出合同
L2  上游产物（input_refs 命中的 approved artifacts）
L3  实体状态包：仅本次任务涉及的人物/关系/地点当前状态
    （借 SillyTavern Lorebook 机制：按登场人物命中注入，而非全量图谱倾倒）
L4  风格规格：全局 Voice Spec + 本章 POV 人物语声表
L5  参考资料 / 知识库检索摘要
```

现状的第 7 段「Wiki/World/Character 约束」是全量注入 `character_graph`——人物一多（本方案目标是几十上百实体）就会淹没硬约束。L3 的按需命中是人物网规模化的**前提**，必须与 §3.3 数据模型同批落地。

### 4.3 提示接点（Prompt Slots）体系

借 PlotPilot「20+ YAML 可覆写提示接点」思想，`runtime/novel_workflow/prompts/` 从 6 个单段模板重组为：

```text
prompts/
  base/            # 每阶段基础任务模板（现有 6 个迁入）
  constraints/     # 阶段配额约束段（§3.2 的机器可读版，注入 L0）
  style/           # 全局 Voice Spec 模板 + 修订指令模板
  revision/        # 质量修订、局部选区修订（rewrite/expand/compress/restyle）指令段
```

每个接点独立文件、独立版本，`prompt_template_id` 扩展为接点组合引用。用户在高级设置中可按接点覆写，而不是重写整段。

### 4.4 新增产物：Voice Spec（风格规格）

Info 阶段扩展输出（或配置阶段人工填写）一份全局风格规格，作为 L4 常驻注入：

```text
VoiceSpec
  narration: 人称 / 时态 / 叙事距离
  rhythm: 平均句长带 / 段落密度 / 对话叙述比目标
  diction: 禁用词表 / 高频陈词槽（供文风检测消费）
  per_character[]: {character_id, 语言习惯, 口头禅, 语域, 绝不说的话}
```

`per_character` 就是人物语声表，正文阶段按 POV/登场人物命中注入；同时它是 §5 文风漂移检测的基准。

## 5. 质量系统 L2（可投稿线的守门员）

在既有确定性引擎（保留，作为 L1 快速关卡）之上补三件事，全部落在 `quality/` 域：

1. **模型评审（`model_review.py`，兑现 roadmap §15.2）**：按阶段 rubric（现有 `quality_policy.checks` 升级为带评分维度的 rubric）出结构化评审：`{dimension, score, evidence, revision_instruction}`。deep 档定稿页默认展示；balanced 档作为自动修订的指令来源；fast 档不调用（成本合同）。
2. **张力曲线**：正文章后处理（十步管线第 9 步已有位置）产出每章 0–10 张力分 + 依据，写入 `story_bible.chapter_summaries` 旁的 `tension_track`。全书视图见 §7.5。
3. **文风漂移与陈词检测**：以 Voice Spec 为基准的确定性检测（句长分布、对话比、禁词命中、重复 n-gram）+ 可选模型抽查。漂移不回滚，生成「定向修写」指令（借 PlotPilot 策略），进入现有选区修订链路。

预算合同：模型评审与张力评分按 roadmap §10.3 独立计费、计入预算账本，fast 档默认关闭。

## 6. UI 重构总纲

### 6.1 视觉方向修正：「数据即装饰」的克制科技感

旧 roadmap §7.1 的「专业安静工作台、拒绝装饰特效」与本轮「要科技感、要动效」诉求的调和边界，一句话说清：

> **装饰性动效继续拒绝；把科技感全部做在真实数据的可视化表现上。**

具体裁决：

- **允许且鼓励**（因为是真实信息的表达）：关系网的连线粒子（粒子密度=关系强度）、阵营聚类光晕、张力心电曲线、阶段 DAG 的流动连线（仅运行中节点）、数字滚动结算（一次性）、图谱 3D 全景模式、进度环。这些全部满足旧 roadmap「动效只解释真实数据变化」的门槛——之前被拒的是它们的**无数据装饰版**（星空、流星、ECG 假心电）。
- **继续拒绝**：Aurora/星空/流星背景、跟随光标、卡片呼吸、无限跑马灯、假进度。现有 `StarfieldLayer`、constellation 硬编码装饰点、`StageProgressNavigator` 的伪进度 ECG（且它已是死代码）全部删除。
- **升级**：暗色主题为主战场（深蓝黑 canvas 已有），把「科技感」落在：更强的层级对比（表面三级：canvas/panel/elevated）、等宽数字字体用于全部指标、状态色的内描边发光（仅激活态）、真实 webfont（Inter + 中文字体子集，`index.html` 目前无字体加载）。

### 6.2 App Shell：从「header + 模态抽屉」到工作台骨架

现状：全局导航是汉堡按钮触发的**模态抽屉**（关掉即消失），知识库/历史/设置是对话框——这是「demo 感」的第一来源。

目标壳层：

```text
┌──┬────────────────────────────────────────────┐
│  │  Header（品牌·当前项目 | 阶段事实 | 主操作） │
│側│────────────────────────────────────────────│
│欄│                                            │
│  │           主工作区（阶段签名视图）           │
│56│                                            │
│/ │                                            │
│240│──────────────────────────────────────────│
│px│  StageFinalizeTray（仅人工闸门阶段渲染）    │
└──┴────────────────────────────────────────────┘
```

- **常驻左侧栏**（icon rail 56px 收起 / 240px 展开，用户手动锁定 + 断点自动收起）：
  1. 创作流程（7 阶段树，含状态点，替代模态抽屉的路由职责）
  2. Story Bible（人物 / 世界观 / 伏笔账本 / Canon 事实——升级为**页面级**入口，不再只是运行态侧栏小面板）
  3. 知识库
  4. 创作历史
  5. 设置（沉底）
- **不做 macOS 式悬浮 dock**：hover 放大降低可预测性的旧裁决成立；「工作台该有 dock」的诉求由常驻侧栏 + 底部 `StageFinalizeTray`（已有）+ **全局命令面板（Cmd+K）**共同满足。命令面板覆盖：跳阶段、搜人物/事实/章节、触发生成命令，这是专业工具的标配且键盘可达性最好。
- **路由升级为真正的路由树**：`/planning`、`/run/:stage`、`/bible/:section`（新增）、`/history`（从对话框升级），嵌套 layout 承载侧栏。手写 `pipelineRouteFromPath` 迁移到 react-router 数据路由（依赖已在）。
- Header 减负：品牌+项目、阶段事实、主操作三轨（Phase 2.2 已收口），历史/设置入口移入侧栏。

### 6.3 状态层与 CSS 债务（重构的工程前提）

- **Prop drilling 收口**：`useNovelWorkflowApp` 返回 60+ 字段、`AppHeader` 收 30+ props。引入 3 个 React Context（RunStateContext / WorkflowConfigContext / UICommandContext）+ 既有 selectors，不新增状态库依赖。侧栏、命令面板、签名视图全部走 context 订阅。
- **事件数组即数据库的问题**：`events` 上限 500 条 + 全 UI 线性扫描。在 reducer 层建立**派生索引**（按 stage/type 的 Map），selectors 消费索引；500 条截断改为「稳定产物不依赖事件重放」的原则性修复（产物从 artifacts 读，事件只做时间线展示）。
- **CSS 收敛**：135 文件 / 30512 行 / 538 跨文件重复选择器 / v2–v6 多代补丁。目标结构两级：`styles/system/`（tokens、基础控件、壳层、overlay，≤20 文件）+ `styles/stage/`（每阶段一组签名样式）。依托既有 audit 工具按所有权逐页收敛（Phase 8.7 已建立方法论），**新壳层落地的同时删除对应旧代样式，不允许第 7 代补丁**。
- **死代码清理（P0，随手做）**：`CreationStatusCluster.tsx`、`StageProgressNavigator.tsx`、`RunConsole.tsx` 均无引用，删除；`QualityModeTabs` 双实现合一；`StageInspector` 双渲染改为单实例 + portal。

## 7. 阶段签名视图与人物关系网

### 7.1 原则

7 个阶段的主视图**已经**各自定制（调研证实），问题是共用壳过强、签名不足、正文/封面阶段右栏为空。本轮给每个阶段定义一个「签名可视化」——它必须是该阶段用户决策直接需要的信息，不是装饰：

| 阶段 | 签名可视化 | 用户决策依赖 |
| --- | --- | --- |
| Info | **关系星图**（分层力导向，§7.2） | 人物阵容和阵营结构是否撑得起全书 |
| Summary | 幕结构轨 + 人物弧泳道 | 主干因果链与人物变化是否成立 |
| Outline | 节拍板 + **全书节奏折线**（按卷张力预期） | 中观节奏是否递进 |
| Detail | 章节施工表 + **覆盖热力条**（每章五组检查的真实完成度） | 哪些章还不能施工 |
| Text | 写作桌 + **张力心电图**（§5 真实数据版） | 当前章在全书节奏中的位置 |
| Cover | 2:3 画框（已达标） | — |
| Export | 交付清单 + **投稿检查卡**（§8） | 是否可交付 |

### 7.2 人物关系网：从 7 节点演示到大型网络

**选型结论：保留 `react-force-graph-2d` 作为主视图（已是依赖，官方示例覆盖全部所需能力），新增 `3d-force-graph` 同族 3D 全景模式作为可选入口；不引入 cytoscape/sigma**（几百节点量级三者性能均够，force-graph 族的自绘节点/粒子/3D 表现力最强且迁移成本为零；「分组折叠」用数据侧 tier 过滤实现，不需要 cytoscape 的 compound 节点）。

数据前提：§3.3 的 tier/faction/kind/polarity/时序模型。UI 能力：

1. **分层初始布局**：protagonist 居中，major 内环，supporting 中环，minor/npc 外环（替代现在 7 个硬编码坐标）；faction 用 convex hull 聚类底色。
2. **边表现**：kind → 颜色，polarity → 实线/虚线/双色，strength → 粒子密度与线宽（连线粒子仅在图谱获得焦点时运行，空闲停止 RAF，遵守性能预算）。
3. **节点表现**：tier → 尺寸阶梯；状态环（存活/危机/退场，来自 status）；首字母徽标保留，avatar_seed 预留头像扩展。
4. **过滤与聚焦**：tier 开关（一键隐藏 NPC 层）、阵营过滤、搜索定位、点击节点 → 侧栏人物档案（不再是静态关系列表弹窗）。
5. **时间轴演化**：底部章节 scrubber，按 `valid_from_chapter` / `history[]` 回放关系网生长——这是「迭代式人物网」的直接可视化，也是向用户解释 §3.2 配额合同的最好界面。
6. **3D 全景模式**：全屏入口，`3d-force-graph`（同作者同数据接口），定位为浏览/展示模式，编辑操作仍回 2D。
7. **可访问性**：图谱旁保持等价的人物/关系 Ledger（旧合同 §9.8 继续有效；Canvas 无障碍树为空，这也是 Playwright 验收要用截图模式的原因）。

家园位置：关系网升级为 Story Bible 的「人物」页（`/bible/characters`）的主视图；各阶段右栏保留紧凑版（点击进入完整页）。

### 7.3 正文与封面阶段的右栏补位

`stageRuntimeLayout.ts` 中 chapter_text/cover 侧栏为空数组的问题，按 Phase 8.5 已完成的审校 Inspector 合同补齐登记，不再留空配置。

### 7.4 外部组件库使用策略（修订版）

| 来源 | 用法 | 依据 |
| --- | --- | --- |
| React Bits | **首选素材库**：取 TS-CSS 变体（唯一官方提供无 Tailwind 变体的库），重写进 tokens 体系；重点：数字滚动、列表入场、边框光效（仅激活态） | MIT+Commons Clause 已登记（roadmap §16.2），成本最低 |
| Magic UI | 参考 + 个别翻译：number-ticker、animated-beam（阶段 DAG 连线参考）、animated-circular-progress-bar | MIT，但 Tailwind+motion 强依赖，逐个翻译 |
| Aceternity | 仅交互思想参考，不复制源码 | Tailwind 强依赖 + 许可证分层复杂，旧登记结论维持 |
| Uiverse (galaxy) | 微交互散件（按钮/loader 状态细节） | 仅取可定位 MIT 文件，旧合同维持 |
| shadcn/ui | 不引入（Tailwind 体系）；其 Radix 组织范式作参考 | 已有 Radix 直用 |

许可证登记流程、Reduced Motion、性能预算（空闲零循环、运行态 ≤3 小循环、CLS 0）全部沿用 roadmap §16 既有门禁，本方案不放宽任何一条。

## 8. 功能补缺清单（按「保证正文导向」排序）

1. **Voice Spec 与人物语声表**（§4.4）——防 OOC 的机制化方案。
2. **伏笔账本 UI**：数据已有（`foreshadow_ledger`，投放/推进/回收/延后四态），缺一个全书视图：伏笔 × 章节的甘特式账本，未闭合项高亮 + 定位。放入 Story Bible。
3. **张力曲线视图**（§5/§7.1）。
4. **投稿检查卡**（Export 阶段）：字数达标、章节字数均衡度、伏笔闭合率、Canon 冲突清零、连续性 finding 清零、张力曲线无长平段——每项来自真实数据，替代抽象「质量分」。
5. **全局命令面板**（§6.2）。
6. **Story Bible 页面化**（§6.2 侧栏第 2 项）：人物/世界观/伏笔/Canon 从「运行态小面板」升级为可浏览、可检索的一等页面（只读 + 引用定位；编辑仍走各阶段定稿链路，不开后门绕过写回合同）。

明确不做（维持 roadmap §21 延期项）：多人协作、模板市场、3D 世界地图、常驻 Agent 聊天室、自动发布。

## 9. 开源产品二次开发评估

**结论：不整体迁移任何现成产品，继续在本仓库演进；定点吸收四个机制。**

- 整体迁移不成立的原因：Dify/Flowise（150k/55k★）是通用 LLM 编排台，无小说领域模型，改造成本高于自建增量；PlotPilot（1.3k★，Apache2+Commons Clause）是 Vue+Naive UI 技术栈且源码受 Commons Clause 限制，只能学机制不能搬代码（旧登记结论维持）；本仓库已有的 Canon/幂等/恢复/预算体系在同类中反而是最完整的。
- 定点吸收：
  1. **PlotPilot**：张力心电图、伏笔注册表一等公民、文风漂移「修写不回滚」、提示接点 YAML 化（§4.3/§5）。
  2. **SillyTavern World Info/Lorebook**（31k★）：关键词/登场命中式上下文注入（§4.2 L3）。
  3. **novelWriter**（3k★）：@tag 式实体交叉引用与文档状态标签，对应本方案的实体注册 + 引用校验。
  4. **NovelForge**（1k★）：Schema 驱动卡片 + 字段粒度流式确认——Detail/Info 编辑器的字段级交互参考。

## 10. 实施分期

依赖关系：10.0 是 10.2/10.3/10.4 的数据前提；10.1 是 10.2/10.3 的壳层前提；10.5 随时可并行。

### Phase 10.0 合同与数据模型（后端为主，UI 冻结期）

- §3.3 人物网模型（tier/faction/kind/polarity/时序）+ 合同/夹具/前端类型同步。
- §3.2 配额进入 `quality_policy` 与前后端校验；删除前端伪造数据路径。
- §4 Prompt 分层：system/user 分离 + 约束金字塔裁剪 + L3 按需命中 + 接点目录重组。
- Voice Spec 产物与合同。
- 退出条件：Fake Provider 全链路测试通过；同一 Run 升级前后 Canon/图谱数据可迁移（旧 Run 惰性兼容）；prompt 快照测试锁定 L0 永不被裁剪。

当前进度（2026-07-26）：

- `10.0A 后端已完成`：`run_schemas.py` 落地 `FactionInfo` 一等阵营实体、节点 `tier/faction_id/first_appearance_stage|chapter/avatar_seed/voice_ref`、边 `kind/polarity/valid_from_stage|chapter/history[]`；全部新字段带默认值，旧 Run 数据惰性兼容（有回归测试锁定）。
- 新建 `orchestration/character_network.py` 作为图谱语义唯一所有者：中英同义词归一化（tier/kind/polarity/stance）、基线构建 `graph_from_brief`（不伪造阵营与关系，缺失即缺失）、`register_characters` 阶段注册（tier + 来源盖章）、`upsert_relation` 共享 upsert（history 追加、语义字段按输出更新，替代 Outline/Detail 各自的 0.58/0.62 魔法值）、`compact_graph_lines` 紧凑注入渲染。
- `10.0B 已完成`：`OutlineVolume.new_characters`（≤4/卷）与 `DetailChapter.new_npcs`（≤2/章）进入 Pydantic 合同；Outline 引用校验按卷累积放行新增配角、阻断主角级新增与重名；Detail 校验放行 Outline 注册的配角、阻断 NPC 担任 POV/character_shift；Info 配额（人物 5-9、硬规则 ≤12）作为 `expansion_quota` warning 进入确定性质量引擎。
- `10.0C 已完成`：`PromptPlanBuilder.build_plan` 产出 `{system, user}`——system 承载 L0（世界观硬规则 + 未决 Canon 冲突 + 下游约束 + 阶段配额）与输出合同/禁止事项；user 按 L1-L5 分层，超预算按 L5→L4→L3 裁剪，L0 永不裁剪（测试锁定）。旧 `_constraints` 的全量 `character_graph` 倾倒替换为 L3 按需命中：正文阶段只注入本章相关人物。传输合同 `PROMPT_SYSTEM_SPLIT` 定义在 `providers/base.py`，OpenAI 兼容适配器拆回真实 system/user 消息，Fake Provider 零改动。
- `10.0D 已完成`：`VoiceSpec` 合同（narration/rhythm/banned_words/cliche_slots/per_character 语声表）进入 `StoryBriefContract` 可选字段；L4 注入按正文 POV 命中语声表；`prompt-info` 模板（runtime JSON 与 `templates.py` 常量双侧）升级为 5-9 人物基线 + kind/polarity 关系语义 + voice_spec 输出要求，Info 生成预算同步扩容（target 2200/max_tokens 4600）。
- `10.0A2 前端已完成`：`contracts/run.ts` 与相关 artifact 类型同步全部新字段（均为可选，旧事件数据兼容）；删除 `infoRecommendationModel.ts` 的伪造派系（index 奇偶）与编造辐射边/公式强度路径——数据缺失渲染缺失态；`characterGraphData.ts` 改为 faction 名称稳定哈希配色（无阵营中性灰）+ tier 分环极坐标（支持任意节点数），删除 7 点硬编码与星座装饰点；节点尺寸按 tier 分档；`graphWithOutlineProgressions/DetailShifts` 把 `new_characters/new_npcs` 以 supporting/minor tier 加入预览并透传全部新字段。新增 `characterGraphSemantics.ts` 与后端归一化对齐。
- `Phase 10.0 已于 2026-07-26 完成`。自动化验证：后端全量 `229 passed, 1 skipped`（新增 `test_character_network.py` 8 项、`test_prompt_layers.py` 7 项、`test_stage_expansion_quotas.py` 7 项）；前端全量 `69 files / 240 passed`，生产构建通过（tsc 零错误）。
- 延后项：prompt 接点目录重组（`prompts/base|constraints|style|revision`）与 10.4 修订指令段合并实施，当前接点仍为单模板 + 内置分层；正文「未注册实体扫描」依赖 10.4 模型评审，当前由结构化引用校验 + 写回提案流程兜底。下一步进入 `Phase 10.1 App Shell`。

### Phase 10.1 App Shell（壳层一次到位）

- 常驻侧栏 + 路由树迁移 + 命令面板 + Header 减负 + Context 收口 + 死代码清理。
- `styles/system/` 建立，壳层旧样式随迁随删。
- 退出条件：全部既有页面在新壳层下通过 Phase 8.7 的浏览器矩阵（八视口、Dark/Light、Reduced Motion、键盘）；CSS 审计指标净下降。

当前进度（2026-07-26）：

- 实施修正：不迁移嵌套路由树。Phase 8.7B.4 已刻意建立「单持久 Shell + 手工路由解析」来保证路由过渡与焦点合同，改嵌套路由的风险大于收益；`/bible`、`/history` 等新路由等 10.2 页面落地时在既有 `stageRoutes` 表上扩展。
- `10.1a 已完成`：新增 `layout/WorkbenchSidebar.tsx` 常驻侧栏（≥1280 默认展开 240px，1024-1279 默认折叠 56px，<1024 不渲染并保留汉堡抽屉；偏好持久化）。侧栏承载 7 阶段树（真实状态点 + `modeRoutePolicy` 原生禁用带原因）、创作规划入口和知识资料/创作历史/模型与设置全局入口；`aria-current` 指示条是模式色唯一使用点。Header 同步减负：≥1024 时汉堡与历史/设置图标不再渲染，主题与重置保留。
- 死代码清理：删除 `CreationStatusCluster.tsx`（连带消除 QualityModeTabs 双实现）、`StageProgressNavigator.tsx`（伪进度 ECG）、`RunConsole.tsx` 及其专属样式与 `ecgTailTrace` keyframe。
- CSS 审计净下降：字节 725,817→721,041（新增侧栏文件后仍 -4,776），源码行 -219，规则 -21，跨文件重复选择器 541→531，keyframe -1，Infinite 保持 24（侧栏零动画）。
- 浏览器验收（Playwright，`output/playwright/phase101a/`）：1440/1280/1024/390 四视口横向溢出 0、控制台 0 errors/0 warnings、空闲 Infinite 动画 0；折叠 240↔56 双向工作；390 下侧栏隐藏且汉堡可用；Light 主题 1280 无控制台问题。
- 自动化：前端 `70 files / 247 passed`，生产构建零 type error。
- `10.1b 已完成`：全局命令面板（Cmd+K / Ctrl+K + 侧栏可见入口）。13 条命令三组（导航 7 阶段 + 创作规划｜知识资料/历史/设置｜主题切换/侧栏折叠），全部复用既有回调零新业务行为；阶段命令带真实状态与 `modeRoutePolicy` 禁用原因，禁用项可见不可执行。快捷键在输入框/contentEditable 内和任何弹窗已打开时被抑制（`hasOpenOverlay` + DOM 兜底）。combobox/listbox/aria-activedescendant 语义、焦点陷阱与回焦、Reduced Motion 0s、CSS 零动画。
- 10.1b 浏览器验收（`output/playwright/phase101b/`）：Meta+K 打开即聚焦输入、13 命令、「设置」过滤到 1 条、Enter 打开设置弹窗且面板自动关闭、Escape 关闭、输入框内快捷键被抑制，控制台 0 errors/0 warnings。
- 10.1b 自动化：前端 `72 files / 257 passed`，构建零 type error，CSS 审计通过（新增 command-palette.css，Infinite 保持 24 不变）。
- `10.1d 已完成`：壳层 Context 收口。`state/pipelineShellContext.tsx` 建立 RunState/WorkflowConfig/UICommand 三切面 Context（按切面 useMemo 稳定引用），`usePipelineShellContexts.ts` 统一组装，路由同步 effect 原样迁入 `usePipelineShellRouting.ts`。壳层组件 props 收口：AppHeader 42→1、WorkbenchSidebar 22→0、CommandPalette →0、GlobalToolDock 16→1、CreationActionDock 13→2；`App.tsx` 438→210 行回到守则。`useNovelWorkflowApp` 零 diff，既有测试断言零改动全过；深层渲染组件（running/planning 内部）本切片有意不动。
- 10.1d 验证：前端 `72 files / 257 passed`（与重构前基线一致）、构建零 type error、CSS 审计未动；浏览器烟测（1440，Context 重构后）侧栏/Header/命令面板 13 命令全部正常，横向溢出 0，控制台 0 errors/0 warnings。
- Phase 10.1 剩余：`styles/system/` 样式目录归位与 10.2 合并实施；八视口全矩阵与 Reduced Motion 复验放在 10.2 视觉切片一并跑。

### Phase 10.2 人物关系网大图 + Story Bible 页面化

- §7.2 全部七项能力；伏笔账本视图；Canon 事实浏览页。
- 退出条件：50+ 节点 / 3+ 阵营的测试数据集下布局可读、空闲零 RAF；时间轴回放与 `history[]` 一致；等价 Ledger 键盘可达。

当前进度（2026-07-26）：

- `10.2a 已完成`：新顶层业务目录 `features/pipeline/bible/`；`/bible/{characters|world|foreshadow|facts}` 四个只读路由（任何模式可访问、无 Run 显缺失态、浏览零 Provider 请求，未知 section 重定向 characters）；侧栏新增 Story Bible 分组（4 子项）、命令面板 13→17 条。
- 人物 section：react-force-graph-2d 大图（tier 分环 + faction 配色复用 10.0A2 语义层），tier 过滤开关、阵营图例点击高亮压暗、节点点击右侧档案栏（含首次出场溯源与 kind/polarity/strength 关系明细）、边 hover 语义、静止停 RAF、等价键盘 Ledger 与图共享选中态。世界观/伏笔/Canon 三 section 为真实数据列表：world_rules 带来源标注、伏笔四态账本未闭合前置、Canon superseded 弱化 + pending 冲突置顶。
- 数据来源：优先 `character_graph_updated`/`story_bible_updated`/`canon_facts_committed` 服务端事件，回退各阶段 approved 产物按运行态同一函数链叠加；缺失即缺失态并标注真实来源。
- 10.2a 自动化：前端 `75 files / 279 passed`、构建零 type error（StoryBibleWorkbench 独立懒加载 chunk 19.16 kB）、CSS 审计通过（Infinite 保持 24，新页面零动画）。
- 10.2a 浏览器验收（`output/playwright/phase102a/`）：无 Run 缺失态、未知 section 重定向、四 section 零横向溢出零控制台问题；真实历史 Run（5,036 字全阶段完成）下大图渲染 5 人物/5 关系/5 阵营图例、tier 过滤与档案栏可用。旧 Run 缺 tier/时序字段按默认值诚实降级。
- `10.2b 已完成`：章节时间轴回放（NetworkTimeline，radio-group 语义 + 方向键/Home/End；刻度从图数据派生：四档阶段 + 出现过的章节 + 当前；时点过滤纯本地，节点按 first_appearance、边按 valid_from 判定，边语义回放至时点最近一次 history 记录；旧数据缺时序标记时按基线降级并显示真实说明，不伪造）。3D 全景模式（react-force-graph-3d + three，Phase 10 唯一新增依赖）：React.lazy 独立 chunk（graph-3d-vendor 1,289 kB 仅动态加载，主包与 graph-vendor 零 three.js），浏览定位（点击仅同步选中），tier/faction/polarity 语义配色，静止暂停帧循环，卸载销毁 WebGL 上下文；与 tier 过滤/阵营高亮/时间轴共享同一过滤数据。
- 10.2b 自动化：前端 `76 files / 291 passed`、构建零 type error、CSS 审计通过（Infinite 保持 24，零新增动画）；懒加载边界有测试证明（import CharactersSection 不评估 3D 包）。
- 10.2b 浏览器验收（`output/playwright/phase102b/`）：真实历史 Run 下时间轴 5 刻度渲染、基线视点切换、旧数据降级说明正确出现；3D chunk 仅在点击「3D 全景」后加载，WebGL 渲染正常，「返回 2D」后 WebGL 上下文销毁、2D 恢复；全程控制台 0 errors（3D 交互期间 headless GL 驱动有 ReadPixels 性能 warning，属 three.js 在无头环境的环境噪声，真实浏览器复验归入 10.2 收官项）。
- 10.2 收官前剩余：50+ 节点 / 3+ 阵营合成数据集的布局可读性验收（现有历史 Run 只有 5 节点，需按新 Info 合同生成或构造夹具 Run）；`styles/system/` 目录归位；真实浏览器（非 headless）复验 3D。

### Phase 10.3 阶段签名视图（逐阶段切片，可与 10.4 交错）

- 按 §7.1 表逐阶段落地：Summary 弧泳道 → Outline 节奏折线 → Detail 覆盖热力 → Text 张力心电（依赖 10.4 的张力数据，先接假数据接口后换真）。
- 每阶段沿用 roadmap §22 实施前检查模板 + §18 浏览器验收，逐个提交。

当前进度（2026-07-26）：

- `10.3a 已完成`：Summary 人物弧泳道（SVG，act_structure 真实幕为横轴；key_turns 按序映射为幕轨上方全书转折刻度；人物弧 arc→pressure→next 三点，pressure 仅在原文唯一匹配幕标题时归位、否则置中并标「未指明幕次」——映射规则入代码注释与测试，不虚构幕级明细）+ Outline 全书节奏折线（每卷五段连续排布、卷边界分隔、点击节拍点联动 Beat Board；纵轴固定为叙事学五段轮廓 2/3/4/5/2.5，图例与 aria-label 明确标注「结构预期强度，非内容质量评分」，杜绝伪指标歧义）。配色经 dataviz 调色板校验器对 dark/light 真实表面验证通过；节拍点为真实 button（24px 命中区 + aria-live 读出行）；一次性 220ms 补间、零空闲动画、Reduced Motion 归 0。删除旧 OutlineRhythmBar。
- 10.3a 自动化：前端 `80 files / 303 passed`、构建零 type error、CSS 审计通过（Infinite 保持 24）。浏览器验收（`output/playwright/phase103a/`）：真实历史 Run 下两图正常渲染，「未指明幕次」「结构预期」标注在位，控制台 0 errors/0 warnings。注：/run/* 整页刷新会被路由守卫弹回 Planning（既有守卫行为），验收使用 SPA 内导航。
- `10.3b/c 已完成`：Detail 覆盖热力条（每格完成数直接调用 Phase 8.4C 的 `detailChapterReadiness` 同源函数，测试断言与施工表 5/5 徽标逐格相等；aria-label 列出具体缺项；5 档 sequential 色阶过调色板校验器）；Text 张力心电图（Context Bar 下方整行——全书视图在写作/审校两模式都可见的布局取舍；事件优先/回退 story_bible、缺分章节断线不插值、当前章高亮、点击切章走既有脏态保护入口；无数据一行诚实缺失态）；deep 档模型评审报告分区（overall + 维度条形 + 证据/修订指令 + 语声漂移提示；unavailable 如实显示并映射作家语言；fast 档整段不渲染无禁用壳；评审版本与正文版本不一致时如实标注）。前端合同同步三个新事件与 tension_track/model_review 类型。
- 10.3b/c 自动化：前端 `83 files / 318 passed`、构建零 type error、CSS 审计通过（Infinite 保持 24、keyframe 零新增）。浏览器验收（`output/playwright/phase103bc/`）：旧 Run 下热力条按新合同如实显示 1/5 覆盖并列缺项，张力条显示缺失态说明，控制台 0 errors/0 warnings。
- **Phase 10.3 七阶段签名视图全部落地**（Info 关系星图=10.2 大图紧凑版、Summary 弧泳道、Outline 节奏折线、Detail 覆盖热力、Text 张力心电、Cover 画框与 Export 交付清单沿用 Phase 8 成果）。

### Phase 10.4 质量系统 L2

- `model_review.py` + 张力评分 + 文风漂移检测 + deep 档定稿页评审报告 + 三档质量底线修正（§2.1-2）。
- 退出条件：三章真实 API 小流量下，模型评审/张力/漂移各产出一次真实报告且计费入账；fast 档硬阻断生效。

当前进度（2026-07-26）：

- `10.4a 后端已完成`：`quality/model_review.py`（rubric 取自 quality_policy.checks，system/user 分层 prompt，Pydantic 严格输出合同：维度分 0-10 + 证据 + 修订指令 + overall + tension + voice 判定；解析/调用失败降级为 unavailable，不伪造分数不阻断落盘）；`quality/voice_drift.py`（零成本确定性：禁词/陈词命中、对话叙述比仅在 rhythm 可解析 N:M 时比对、句长仅在明确声明偏好时出 finding——解析不出就跳过不猜）；`orchestration/model_review.py` 编排闭包按 content_signature 缓存，恢复/重放不重复调用不重复计费。
- 数据与事件：`story_bible.tension_track[]{chapter,score,basis,source}` 按章幂等 upsert + `chapter_tension_scored` / `model_review_completed` / `model_review_unavailable` 事件；deep 档完整报告入 `ChapterItem.model_review`（additive 旧数据兼容）。预算 scope `model_review` 按候选/修订模式注册（fast:0 / balanced:2 / deep:3 额度，超限降级不阻断），统一走 execute_text_provider_call 审计链路。
- 三档合同修正（§2.1-2）落实并测试锁定：硬阻断线（结构合同/世界观硬规则/Canon 冲突）三档共享必停；fast 档 warning 只记录不修订**且不再升级人工干预**；balanced 用模型评审指令驱动 1 轮自动修订；deep 2 轮 + 每章人工拍板。
- 10.4a 自动化：后端全量 `251 passed, 1 skipped`（+22：voice drift 9、model review 11、三档合同 2），Fake Provider 全覆盖。
- 待完成：Text 定稿页评审报告与张力心电展示（10.3c 前端）；真实 API 小流量验收（仍受 Provider 余额前置条件约束）。

### Phase 10.5 全链路验收（合并原 Phase 8.8B 目标）

- 三档真实全链路 + 投稿检查卡 + 性能/可访问性回归。仍受真实 Provider 余额前置条件约束（roadmap §17.9 Phase 8.8B 启动条件不变）。

## 11. 工具链配置（Claude Code）

- **Playwright MCP**（microsoft/playwright-mcp，Apache-2.0）：`claude mcp add playwright -- npx @playwright/mcp@latest`。用于每个 UI 切片的浏览器验收；注意 force-graph 画布无障碍树为空，图谱验收用截图模式。
- **shadcn MCP**（可选）：React Bits / Magic UI 均走 shadcn 注册表分发，用它拉组件源码再手工翻译进 tokens 体系：`npx shadcn@latest mcp init --client claude`。
- 内置 dataviz skill：张力曲线、节奏折线、覆盖热力等图表实现前先读取，保证图表语言一致。

## 12. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 配额合同过严导致创作卡死 | 配额可按工作流配置调整；阻断信息必须给出「回哪个阶段改什么」的定位动作 |
| Prompt 重构引起产物质量回退 | 10.0 建立 prompt 快照 + 同输入 A/B 对比夹具后再切换 |
| 壳层重构与阶段切片互相踩踏 | 10.1 一次到位后冻结壳层；签名视图只动主工作区 |
| 「科技感」滑回装饰堆料 | §6.1 裁决表 + 既有性能预算门禁（空闲零循环）不放宽 |
| 3D 模式成为性能黑洞 | 3D 仅全屏可选入口、懒加载、退出即卸载；不进入任何常驻面板 |
| 旧 Run 数据不兼容新图谱模型 | 惰性迁移 + 缺字段渲染缺失态，不伪造 |
