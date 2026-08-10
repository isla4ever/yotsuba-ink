# Phase 18：PlotPilot 连续性对照与 Prompt 编排收敛

> 状态：实施中
> 决策日期：2026-08-05
> 适用范围：正文 Context Packet、章间连续性、Wiki/RAG 检索、语义/因果审稿与真实长篇验收
> 不适用范围：复制 PlotPilot 源码、Prompt 文本、数据库结构或产品界面

## 1. 本阶段要解决的问题

Yotsuba Ink 已经具备细纲、场景合同、Context Packet v3、Wiki、Canon、人物知识矩阵、叙事事实投影、质量阀门和有限局部修订。当前瓶颈不是“再加一层状态机”，而是既有层级缺少唯一的事实优先级：

1. 细纲描述的是计划意图，冻结正文记录的是实际发生结果；下一章仍可能被旧计划 hook 引导。
2. Wiki 检索会再次召回当前 Context Packet 已拥有的整份 Outline/Detail，浪费上下文并放大计划态资产。
3. 审稿已经能识别 `character_statement`，但需要用真实冲突案例固化“角色说法不是客观事实”的回归合同。
4. 自动门禁能发现不少局部问题，却没有阻止《潮汐证人》第 2→3 章出现缺少时间与行动桥的跳切。
5. 继续堆叠禁词、铁律或审稿 Agent 会增加 Token 和误修风险，并不能自然提高投稿质量。

本阶段的产品目标是：以不增加正文生成调用为前提，让下一章只从“已发生的现实”出发，再把计划中尚未兑现的意图作为次级目标。

## 2. 外部研究快照

### 2.1 版本与更新

- 官方仓库：[shenminglinyi/PlotPilot](https://github.com/shenminglinyi/PlotPilot)
- 隔离克隆：`/tmp/plotpilot-research.RA9cl3/PlotPilot`
- 核对日期：2026-08-05
- 当前 master：`7dc03a37a06b57e823df222da0e3bde5d1c84715`
- 当前 master 提交时间：2026-07-19 13:04:58 +08:00
- 最新 Release：[v4.6.0](https://github.com/shenminglinyi/PlotPilot/releases/tag/v4.6.0)，发布于 2026-06-10（北京时间）
- `v4.6.0..master` 只有 `README.md` 修改，没有代码更新

结论：相较上一轮 7 月中旬调研，PlotPilot 没有可称为“大更新”的代码发布。README 的架构说明更完整，但不能当作运行质量证据。

### 2.2 源码检查范围

本轮只读检查了下列核心实现：

- `application/engine/services/chapter_bridge_service.py`
- `application/engine/services/context_budget_allocator.py`
- `application/engine/services/memory_engine.py`
- `application/engine/services/chapter_aftermath_pipeline.py`
- `infrastructure/ai/prompt_packages/nodes/chapter-generation-main/system.md`
- `LICENSE`

没有执行外部仓库脚本、安装依赖或把其文件复制进 Yotsuba Ink。

### 2.3 许可证边界

PlotPilot 的 `LICENSE` 是 Apache 2.0 附加 Commons Clause。Commons Clause 明确排除以其软件功能实质为价值来源的收费产品或服务。

Yotsuba Ink 后续存在正式线上商业版计划，因此本阶段只允许：

- 研究公开设计思想和失败模式；
- 使用独立命名、独立数据结构和独立实现完成 clean-room 设计；
- 在文档中进行事实性比较并链接来源。

本阶段禁止：

- 复制 PlotPilot 源码、Prompt 原文或数据库表；
- 对其实现做机械翻译、改名或移植；
- 把 PlotPilot 作为商业版依赖或功能内核；
- 宣称 Yotsuba Ink 采用或兼容 PlotPilot。

## 3. 为什么 PlotPilot 看起来更连续

### 3.1 可借鉴的真实机制

| PlotPilot 机制 | 源码证据 | 连续性收益 | Yotsuba Ink 当前状态 |
| --- | --- | --- | --- |
| T0/T1/T2/T3 上下文预算 | `context_budget_allocator.py` | 预算不足时先牺牲远期召回，保护硬事实与近期状态 | 已有优先级 Slot，但未显式仲裁计划与现实 |
| ChapterBridge 五维投影 | `chapter_bridge_service.py` | 把悬念、情绪、场景、位置、未完成动作交给下一章 | 已有尾文与 carryover，但 transition 仍读取计划 hook |
| `COMPLETED_BEATS` | `memory_engine.py` | 防止同一剧情再次作为新事件展开 | 已有叙事事实与细纲合同，缺少面向下一章的“已完成结果”投影 |
| `REVEALED_CLUES` | `memory_engine.py` | 防止已揭露线索再次包装为新发现 | 已有 Wiki/伏笔账本，Prompt 未始终区分“已揭露”和“待推进” |
| 章后统一管线 | `chapter_aftermath_pipeline.py` | Bridge、人物、伏笔、债务、Voice、Checkpoint 在一次章后流程中更新 | 已有事务化 Canon/Wiki/Memory 写回，方向更严格但结果桥尚未显式化 |
| Prompt Package 节点化 | `prompt_packages/` | 任务 Prompt 可版本化、替换和独立校验 | 已有 Prompt identity、stage template 和 provider capability adapter |
| 定点修复 | `chapter_bridge_service.py` 等 | 首段或局部问题不需要整章重写 | 已有签名绑定的局部 revision patch，边界更安全 |
| 单写者调度 | README/持久化层 | 减少 SQLite 并发写错乱 | Yotsuba Ink 已用 RunStore revision/CAS 和 writeback outbox 解决不同问题 |

PlotPilot 的“连续感”主要来自三个感知层：最近正文进入上下文、前章退出状态被单独投影、已发生事件不会再次当成新发现。它不是靠单个神奇 Prompt 获得连续性。

### 3.2 只是启发式或宣传，不能当作质量保证

1. `ChapterBridgeService.check_continuity()` 只检查本章前 500 字与前章 Bridge，不能证明整章因果连续，也不能验证修订章对下一章的影响。
2. Bridge 的文件头注释称其进入 T0 强制层，但 V9 `build_opening_directive()` 已改为参考信息，源码内部存在语义漂移。
3. 主生成 system Prompt 共 167 行，包含 20 多条“铁律”、禁词、比例和动作替换。规则之间存在直接张力：
   - 一处要求“字数是上限，不是目标”；
   - 后文又要求铺垫章必须达到字数；
   - “每句话至少完成两件事”会压平呼吸段落和低强度场景；
   - “用动作代替情绪”容易批量生成捏关节、摩挲物件等模板动作。
4. 词法 Anti-AI、段落比例和陈词扫描只能做诊断，不能证明稿件具备投稿质量。
5. 公开 Issue 证明其长篇主线仍未闭环：
   - [#205 万字后前后矛盾](https://github.com/shenminglinyi/PlotPilot/issues/205)
   - [#151 Context Builder、误报与章后管线故障](https://github.com/shenminglinyi/PlotPilot/issues/151)
   - [#183 文风公约被覆盖](https://github.com/shenminglinyi/PlotPilot/issues/183)
   - [#186 伏笔持续堆积](https://github.com/shenminglinyi/PlotPilot/issues/186)
   - [#187 故事线匹配失败](https://github.com/shenminglinyi/PlotPilot/issues/187)
   - [#188 Anti-AI 未触发修复](https://github.com/shenminglinyi/PlotPilot/issues/188)
   - [#202 全是短段落](https://github.com/shenminglinyi/PlotPilot/issues/202)

## 4. Yotsuba Ink 的现状与真实三章诊断

### 4.1 已有能力

Yotsuba Ink 的新运行时已经超过简单“大纲 + 最近正文”方案：

- `ChapterContextPacket` 默认 schema v3；
- 包含前章摘要、最多 1200 字尾文、未完成动作、情绪余波、知识变化、知识矩阵、空间锚点、人物关系压力、物件状态、当前有效叙事事实和来源签名；
- 每个场景有 3400 字符 Context 预算；
- 当前章细纲、转场、世界硬规则和前章尾文属于高优先级；
- 正文 RAG 只通过 Wiki 检索层进入，不混入通用参考摘要；
- 冻结正文后的 Canon/Wiki/Memory 写回具备事务边界；
- 局部修订按正文签名和 UTF-16 位置绑定，不允许无脑整章重写。

### 4.2 《潮汐证人》第 1–3 章证据

Run：`wave17-20-submission-long-form-20260804-a1`

当前状态：

- 已完成第 1–3 章；
- 暂停在第 4 章生成前；
- 暂停后 Provider 调用为 0；
- 当前不得重复生成第 1–3 章，也不得提前生成第 4 章。

人工审读确认的主要问题：

1. 第 2 章结尾是沈见潮关闭终端并开始处理风险，第 3 章直接切到第二天早晨的档案室走廊，缺少时间与行动桥。
2. 第 3 章计划 hook 表述“权限提升至受限监督”，但第 2 章最终正文只明确会话被管理员重置；计划与现实没有先仲裁。
3. 多章重复捏手指关节、摩挲徽章、硬盘硌肋骨、防潮堤警示灯、雾和湿冷。
4. 段落长期短促，紧张频率单一，缺少呼吸和场景差异。
5. 秦雾对白承担直接讲解设定的职责，人物声音不足。
6. 第 3 章仍替读者总结“不是数据丢失……是系统在删除……”。
7. 因果审稿可能把角色回避、说谎或不可靠陈述当作客观事实冲突。

这说明“所有门禁通过”只代表现有合同被满足，不代表文学质量达到投稿标准。状态机必须服务证据优先级，不能用状态数量代替人工审读。

## 5. 核心产品决定

### 5.1 引入前章最终结果桥

新增 Yotsuba 自有的 `PreviousChapterResultBridge` 只读投影。它不产生新事实，只从已冻结正文、已验证 carryover 和叙事事实中整理：

- `completed_outcomes`：上一章已经发生且下一章不得重复包装的结果；
- `unresolved_actions`：仍在进行、已承诺或必须处理的动作；
- `revealed_clues`：已经成为角色知识或读者已知信息的线索；
- `exit_state`：章末物理位置、时间、人物/物件状态；
- `relationship_delta`：上一章已经造成的关系变化；
- `next_entry_obligation`：下一章开头必须交代的最小桥，不规定文学写法。

第一版不新增模型调用。投影只读取现有 postprocess、narrative facts、summary 和冻结尾文；不从正文用正则“猜”新事实。

### 5.2 计划/现实仲裁

事实优先级固定为：

1. 冻结正文中可绑定的 narrator/system/物证结果；
2. 已验证叙事事实与章后 carryover；
3. 已提交 Canon/Wiki；
4. 当前章 Detail 的进入状态和目标；
5. 上一章 Detail hook 等计划意图。

仲裁规则：

- 上一章计划 hook 只有在冻结结果桥仍将其标为未兑现时才进入下一章；
- 若计划说“权限已提升”，现实只发生“会话被重置”，下一章不得把权限提升当成既成事实；
- 本章仍可追求计划中的权限变化，但必须把它写成待完成目标；
- 时间/地点/POV 变化可以发生，但必须有可读桥，不能让模型误以为故事重新开始；
- `next_entry_obligation` 只要求交代转换，不强制前三句、同场景或同 POV。

### 5.3 RAG 去重

正文 Context Packet 已直接拥有 Summary、Volume、Detail、人物和世界硬规则。正文 Wiki 检索只补：

- 已提交章节 Wiki/Canon；
- 与当前章明确相关、但未在 Packet 直接出现的世界或人物事实；
- 远期伏笔或早期证据的可追溯片段。

正文检索默认排除 `outline` 和 `detail_outline` 的整份 stage artifact 文档。它们仍保留为正式上游产物和来源签名，只是不重复进入 RAG 命中。

### 5.4 审稿事实等级

冲突两端必须分别归类：

- `narrator_fact`
- `system_record`
- `physical_evidence`
- `character_statement`
- `belief`
- `allegation`

只有两端指向同一主体、谓词、对象与时间锚点，且至少一端具有 narrator/system/物证权威，才允许进入硬错误候选。两个角色陈述互相冲突默认是人物立场或悬念，只能给 editorial 诊断。

现有 `cold_edit_prompt.py` 与 `_bound_finding()` 已覆盖 narrator/system 与 statement 降级；本阶段不再造第二套分类器，只补齐物证类型和回归用例。

### 5.5 Prompt 编排收敛

正文 Prompt 保持四层，不再扩大禁令清单：

1. **身份**：明确该叙事角色的观察方式、知识边界和语言姿态；
2. **当前任务**：只描述本场景必须产生的变化和退出状态；
3. **硬事实**：结果桥、叙事事实、世界规则、角色知识边界；
4. **创作自由区**：允许选择转场技法、句法、对白潜台词、感官和节奏，只要不破坏前三层。

Anti-AI 规则只保留为诊断信号，不作为批量替换配方。对于重复动作、解释性对白和总结句，优先定位证据并做小段修订，不增加整章重写轮次。

## 6. Token 与运行成本

| 能力 | 新模型调用 | 上下文变化 | 成本决定 |
| --- | ---: | ---: | --- |
| 前章最终结果桥 | 0 | 约 400–900 字符，替代重复 hook/检索 | 本轮实施 |
| Outline/Detail RAG 去重 | 0 | 预计减少 300–900 字符/场景 | 本轮实施 |
| 事实等级验证 | 0 | 审稿 JSON 增加少量枚举字段 | 本轮补回归 |
| 章间语义审稿 | 沿用现有主审，不新增角色 | 不变 | 本轮实施 |
| 独立 Bridge LLM | +1/章 | 额外输出约 300 token | 暂缓，只有确定性投影召回不足再评估 |
| 多 Agent 投票 | 多次/章 | 高 | 不引入 |
| 整章重写 | 高 | 高 | 不因连续性单点问题触发 |

## 7. 实施边界

本轮包含：

1. 新增聚焦的最终结果桥领域模块；
2. Context Packet 注入结果桥，并让 transition 优先读取现实；
3. 正文 Wiki 检索排除 Outline/Detail 重复文档；
4. 角色陈述/物证事实等级回归；
5. 使用第 2→3 章缺口构建确定性测试；
6. 修正暂停态验收报告，把已解决历史故障与当前故障分开。

本轮不包含：

- 继续第 4 章或整本真实生成，直到回归全绿；
- 新增 Bridge 模型调用；
- 复制 PlotPilot Prompt Package；
- 引入向量数据库、DAG 或新的 Agent 框架；
- 因单点连续性问题整章重写；
- 把 Anti-AI 检测分数宣传为投稿质量。

## 8. 验收标准

### 8.1 确定性回归

- 第 2 章最终结果为“管理员重置会话”时，第 3 章 Packet 不得声称“权限已提升”。
- 第 2 章结尾与第 3 章开头跨到第二天/新地点时，transition 必须要求交代时间和行动桥。
- 已冻结结果优先于前章 Detail hook。
- Outline/Detail 整份文档不再出现在正文 `retrieved_context`。
- chapter writeback、Canon/Wiki 证据仍可检索并保持来源签名。
- 两条 `character_statement` 冲突不得升级为 `hard_error_suspected`。
- narrator/system/physical evidence 与同一事实上的冲突仍可进入硬审稿。

### 8.2 工程验证

- 定向 Context、Wiki、Cold Edit、Review tests 全绿；
- 全量后端测试全绿；
- Python compile 与 `git diff --check` 通过；
- 不改变 API 路由或阶段 Artifact 用户语义；
- 新模块保持单一职责，不向 `api/routes` 放业务逻辑；
- 第 1–3 章冻结正文、generation attempts 和正式写回不变。

### 8.3 真实链路

回归通过后，才允许从现有暂停点恢复第 4 章：

- 只使用 DeepSeek；
- 不扩大正文生成预算；
- 不重新生成第 1–3 章；
- 第 4 章 Context Packet 必须是 v3，并记录结果桥与去重后的 Wiki 命中；
- 第 4 章完成后先人工审读承接、人物声音、段落呼吸和重复动作，再决定是否继续整本。

## 9. 最终决策

Yotsuba Ink 需要借鉴 PlotPilot 的“状态投影与上下文优先级”，不需要变成 PlotPilot。我们的正确变通是把已有的严格事务、证据绑定和阶段 Artifact 合同连接起来：用前章最终结果桥消除计划/现实漂移，用 RAG 去重释放上下文，用事实等级减少误报，再让 Prompt 把剩余空间交还给创作。

只有当第 4 章真实结果证明确定性投影不足时，才评估一次低成本 Bridge 提取调用；在此之前，不用更多 Token 掩盖数据优先级错误。

## 10. 2026-08-05 第 4 章人工审读与真实复检

本节覆盖第 4 章真实运行后的新证据；若与第 7、8 节的“尚未继续第 4 章”描述冲突，以本节为准。

### 10.1 相邻章审读发现的真实缺口

自动质量门最初以 0.92 通过第 4 章，但人工逐段对照第 3 章后发现：

1. 同一本顾长河日记在第 3 章写成 11 月 15、16、20 日，第 4 章却改成 1、3、8 日；提交日期又从盖章草稿的 11 月 16 日漂移为 11 月 9 日。
2. 第 4 章先把“第四十七次预报后三天”的母带日期写成 11 月 15 日，早于 11 月 16 日预报，时间因果不成立。
3. 旧归档文件夹已放回档案柜，证物袋清单却仍声称携带该文件夹；真正随身且后文再次使用的是断网旧平板。
4. 权限日志把书记员编号 `CT-47-06` 误写成原始母带编号；前文已绑定的母带编号是 `CT-12-1802`。

这说明现有结果桥保护了章末动作与持有人，却没有覆盖“同一耐久物证的内部日期和编号”。通过所有阶段与审稿状态不等于投稿质量完成。

两次受安全补丁上限约束的事务化人工修订完成了以下收敛：

- 统一日记为 11 月 15/16/20 日；
- 将归档、记录修正与权限变更统一到 11 月 19 日，即第四十七次预报后三天；
- 证物袋改为硬盘、日记、旧平板与编号记录纸；
- 原始母带号恢复为 `CT-12-1802`；
- 旧审稿、叙事抽取、Wiki/Canon 派生与导出资格均按合同失效后重建，没有直接编辑 `run.json` 冒充完成。

### 10.2 Token 恢复编排修复

本轮同时修复了三类恢复成本漂移：

1. `completed_review_role_shortfall` 过去从完整 `reviewer_roles` 取缺口，错误地为非阻断的 `independent_cold_editor` 补开 `cold_edit`；现在只读取 `blocking_specialist_roles`。
2. 旧 Run 已保存的诊断角色 allowance 会在新计划合并时继续存活；现在合并会保留未完成的非诊断角色，但剔除诊断角色，并提供零 Provider、零预算变化的持久化清理事件。事件 1691 清理了第 3、4 章的旧诊断 allowance。
3. 已带 `revalidation_budget_opened: {}` 的人工修订事件曾被误判为“从未处理”，导致复检完成后再次扩大 review limit；现在只有该字段缺失的旧事件才进入兼容恢复。

相关确定性回归为 12 项；全量后端验证为 `1037 passed, 1 skipped`。`compileall` 与 `git diff --check` 通过。

### 10.3 真实 DeepSeek 证据

唯一有效 Run：

`/tmp/yotsuba-ink-evidence-rebind.hPL80V/wave17-20-submission-long-form-20260804-a1`

真实复检过程：

- 首轮重新调用语义审稿与因果审稿后，主审把正文逐字存在的“陆沉闯进来，却没有呼叫增援”误判为缺失；因为 revision 已达上限，运行以 `revision_patch_invalid` 停止。
- 使用当前快照、正文签名、合同 `contract-89679ea4eaa7817e` 和逐字证据做零 Provider 重绑，完成率从 88.89% 恢复为 100%。
- 第二次恢复复用了语义与因果审稿，只新增一次叙事抽取；独立冷审只记录 unavailable，没有 Provider operation。
- `chapter_completed` 为事件 1745；`run_paused` 为事件 1756；`acceptance_chapter_checkpoint_reached` 为事件 1757。
- 第 5 章保持 planned，Provider、chapter start 与 generation 事件均为 0。

最终状态：

| 项目 | 结果 |
| --- | --- |
| 第 4 章 | completed，v2，4309 字符 |
| 提交签名 | `230f93c69359f13cf017654a6c72fd4a6cfe6e8e644aa8417046d11d21fe13cc` |
| 叙事验证 | provisional，12 条 assertion |
| 卷级 Canon | provisional，`canon_facts=0`，尚未正式提交 |
| Run Token | 2,163,516 / 3,000,000，剩余 836,484 |
| 第 4 章累计 Token | 141,298 |
| CLI 结果 | 在第 4 章边界主动暂停；`technical_passed=false` 仅因尚未到导出节点 |

### 10.4 第 5 章前的新门槛

当前剩余预算无法按第 4 章的累计成本完成其余 28 章，因此不得直接续跑第 5 章。下一轮先做：

1. 在 `PreviousChapterResultBridge` 之上增加耐久物证投影，至少携带物证身份、关键日期、编号、当前位置与持有人；只读取已冻结正文或已验证叙事事实，不新增模型调用。
2. 让因果审稿显式比较“同一物证跨章属性”，而不是只检查场景目标完成率；日期冲突必须绑定两端正文证据。
3. 用第 3→4 章日记、文件夹、旧平板和母带号建立确定性回归，再评估是否需要一次低成本结构化抽取；不能先增加 Agent 数量。
4. 重新估算快速、平衡、深度三档每章上限。Deep 模式也必须先复用冻结正文、缓存审稿和局部证据恢复，禁止以整章重写解决单点连续性问题。

### 10.5 耐久物证投影与跨章双证据门

本轮已在不增加模型调用的前提下完成第一版耐久物证投影：

- `PreviousChapterResultBridge.durable_evidence` 使用稳定 `evidence_identity` 聚合属性；
- 属性只允许 `critical_date`、`identifier`、`holder`、`physical_location`；
- 每个属性必须携带 `claim_key`、来源章节、逐字正文引文和来源正文签名；
- 投影只读取当前有效、非 invalidate、置信度不低于 0.85 的 prose/author-edit assertion；
- holder/location 只保留同一物证的最新有效值，日期和编号保留有签名的多条非互斥记录；
- 角色对白中顺带提及编号不会被误建为新的物证身份。

现有叙事抽取 Prompt 也已收紧，但没有增加调用次数：日记、母带、文件夹、平板、硬盘和证词草稿必须使用跨章稳定 `subject_id`；关键日期、编号、持有人和位置不得降级成一次性 `event:*`。这会改善新章节抽取，不能倒推旧 Run 已经拥有缺失 assertion。

因果审稿现在会收到至多 12 条签名物证属性。跨章硬错误必须同时满足：

1. 一端是当前正文逐字片段；
2. 另一端逐字等于投影中的前章 `source_quote`；
3. 前章 `source_signature` 必须匹配；
4. `subject_key` 与 `predicate_key` 必须原样等于物证身份和属性；
5. 至少一端属于 narrator/system/physical evidence 权威事实；
6. 修订目标仍必须唯一定位到当前正文。

错误签名、错误物证、错误属性、只有一端证据或两段人物陈述都会降级为 editorial 诊断，不能触发修订门。当前章没有再次提及某项物证也不算缺失，避免为了“证明没矛盾”重复交代前情。

确定性回归覆盖了日记日期、旧文件夹归位、断网旧平板持有、母带编号，以及正确/错误跨章签名绑定。相关连续性、Cold Edit、专项门、抽取合同与恢复定向测试为 `89 passed`。

### 10.6 真实 Run 投影审计与事件 1717 收口

对唯一有效 Run 做零 Provider 投影后，当前旧 assertion 能可靠召回：

| 物证 | 已签名属性 |
| --- | --- |
| `tape-ct-12-1802` | 编号 `CT-12-1802`；位置“深港基站第三备份库” |
| `evidence-bag` | 位置“秦雾处木箱底层” |
| `testimony-draft-guchanghe` | 收件日期 `2057年11月16日` |
| `character-guchanghe:diary` | 日期 `2057年11月15日`；书记员编号 `CT-47-06` |
| `offline-hard-drive` | 位置“沈见潮内袋” |

旧 Run 的第 3/4 章抽取没有把日记 11 月 20 日、旧平板和旧文件夹全部保存为稳定 assertion，因此不能声称当前存量 Run 已满足完整物证召回。新 Prompt 可防止后续重复产生，但第 5 章仍保持禁止；下一门槛是对冻结正文做一次不生成正文的结构化回补或实现同等可审计的确定性回补，并验证 Chapter 5 Packet 确实包含这些属性。

事件 1717 的未消费容量已经通过独立事务入口关闭：

- 开额 policy：`precommit-revalidation:wave17-20-submission-long-form-20260804-a1:1690`；
- 开额事件：1717；
- 事件后没有任何带该 policy 的 `model_review/cold_edit` Provider operation；
- limits 从 `model_review 5 / cold_edit 7` 回收到 `4 / 6`，与 attempts 一致；
- attempts、operations、第 4 章正文与提交签名均未改变；
- 事件 1758 记录容量关闭，事件 1759 将审计来源准确重绑到 1717；
- 修订前备份为 `run.before-event-1717-capacity-cleanup.json`。

最终工程验证：全量后端 `1044 passed, 1 skipped`；`compileall` 与 `git diff --check` 通过。本轮没有启动第 5 章、没有正文生成、没有 Provider 调用，也没有把 provisional Canon 描述成正式提交。

### 10.7 冻结正文物证回补与 Chapter 5 Packet 预检

旧 Run 的缺失物证已经通过独立 acceptance 事务回补，不修改 `run.json` 内部结构、不写 Canon，也不重新调用叙事抽取模型。输入合同逐项只接受 `evidence_identity`、`attribute`、`value`、`source_chapter` 和 `source_quote`，额外字段直接拒绝；系统负责验证来源章节已 completed、逐字引文在冻结正文中唯一出现、属性值属于引文子串，并计算正文签名和提交签名。

真实 Run 写入结果：

| 回补物证 | 属性 | 冻结来源 |
| --- | --- | --- |
| `character-guchanghe:diary` | 日期 `11月20日` | 第 3 章“再往后翻，是11月20日。” |
| `archive-folder` | 位置“档案柜” | 第 4 章文件夹归位引文 |
| `offline-tablet` | 位置“证物袋” | 第 4 章平板与硬盘入袋引文 |

- 事务事件为 1760，`provider_calls=0`，state revision 从 2432 增至 2433；
- artifacts、完整 budget tree、attempts、operations 和 narrative world 与写入前逐项相等；
- 重复提交同一组回补返回 `None`，没有新增事件或 revision；
- 写入前备份为 `run.before-durable-evidence-backfill.json`；
- 日期/编号按 `identity + attribute + value` 去重追加，holder/location 按来源章节保留最新确认值；
- Chapter 5 只做内存 Packet 构建，没有持久化 packet、创建章节或启动 Provider。

Chapter 5 Packet 预检共召回 7 个物证身份：`offline-tablet`、`archive-folder`、`tape-ct-12-1802`、`evidence-bag`、`character-guchanghe:diary`、`testimony-draft-guchanghe`、`offline-hard-drive`。日记同时保留 11 月 15 日、11 月 20 日和书记员编号 `CT-47-06`；母带保留 `CT-12-1802` 与深港基站位置。前章 source signature 仍准确绑定第 4 章提交签名。

本轮新增和相关回归为 `18 passed`，全量后端为 `1051 passed, 1 skipped`，`compileall` 与 `git diff --check` 通过。耐久物证召回门已经通过，但第 5 章仍不解除禁跑：10.4 的三档单章预算重估尚未完成，当前剩余 836,484 Token 不足以按第 4 章成本完成其余 28 章。下一步应先建立 Fast/Balanced/Deep 的按角色调用上限和停止条件，再决定继续当前 Run 还是创建预算可闭合的新验收 Run。

### 10.8 全书预算闭合门与第 5 章前阻断

预算估算已从“用某一章异常总成本乘剩余章数”改为基于已完成 `text:*` scope 的已结算 operation 中位数。这样既不会把第 2 章 9 次重生成固化为常态，也不会用理论 `max_tokens` 和 12 次 regeneration allowance 制造不可执行的虚假上限。

当前 Run 的成本基准：

| 职责 | 中位 Token | 有效样本 | 预测用途 |
| --- | ---: | ---: | --- |
| 单场正文生成 | 12,857 | 8 | 每章固定 2 场 |
| 最终叙事抽取 | 11,030 | 8 | 每章 1 次 |
| 语义/衔接主审 | 7,686 | 7 | Balanced/Deep 每章 1 次 |
| 因果事实专项 | 5,761 | 7 | Deep 结构风险章 |
| 独立文学冷读 | 10,565 | 4 | 高风险诊断，不重复运行 |
| 唯一局部修补 | 5,368 | 4 | 仅一部分高风险章 |

三档不再是同一流程的 Token 缩放：

- Fast：每章 2 次场景生成 + 1 次最终叙事抽取，模型审稿、冷读和自动修补均为 0；只增加 10% 已观测成本波动储备。
- Balanced：Fast 基线上增加每章一次语义/衔接主审；最多为 25% 高风险章各预留一次独立冷读、一次唯一局部修补和一次语义复检。
- Deep：继承 Balanced；最多为 50% 结构密集章预留因果专项，为剩余卷末预留终章兑现专项；修补后只复检语义主审和首次阻断的硬专项，独立冷读不重复。
- 三档都单独保留 50,000 Token 给封面、导出校验与最终 Canon 汇合，不允许正文耗尽交付预算。

真实 Run 试算：

| 模式 | 折算单章 | 剩余 28 章 + 交付总需求 | 可用余额 | 结论 |
| --- | ---: | ---: | ---: | --- |
| Fast | 40,419 | 1,181,716 | 836,484 | 阻断 |
| Balanced | 54,778 | 1,583,777 | 836,484 | 阻断 |
| Deep | 59,305 | 1,710,519 | 836,484 | 阻断，缺口 874,035 |

预测器为纯函数，历史不足时使用明确的低置信度策略兜底；全新 Run 创建时记录 `provisional/observe/low` 预检，即使配置兜底判断过小也不误阻断无历史 demo。未配置 Run 上限时返回 `unbounded`。已有结算历史的验收事务只在恢复/审稿收口后、`run_store.resume()` 前执行，预算不足时进入 `manual_intervention`，不自动扩容、降档或启动下一章。

真实 Run 已先备份为 `run.before-chapter-budget-closure-gate.json`，随后一次事务写入：

- state revision 从 2433 增至 2434；
- 事件 1761 `chapter_budget_closure_forecasted`、1762 `chapter_budget_closure_blocked`、1763 `manual_intervention_required` 均声明 `provider_calls=0`；
- 预测签名为 `fe6486387f42326ac2ad4f35`，重复执行返回 `changed=false`，没有新增事件或 revision；
- artifacts、chapter progress、完整 scopes/attempts/operations、narrative world、已消耗 2,163,516 Token 和预留 0 Token 逐项不变；
- 第 5 章仍为 `planned`、0 字，未创建 Context Packet、未发出 chapter start、generation 或 Provider 调用。

因此当前 Run 的正确定位是前四章工程验收证据，不应通过自动扩容继续伪装成可闭合的 32 章交付 Run。下一步应先建立预算可闭合的新长篇验收配置，或由作者显式决定规模/预算后再运行；任何选择都必须重新通过同一闭合门。

本轮最终验证：预算预测/事务/Book Runner 顺序定向套件 `61 passed`；全量后端 `1061 passed, 1 skipped`；`compileall` 与 `git diff --check` 通过。仓库环境仍未安装 `ruff`，因此未声称 lint 通过；5173/8000 均无监听进程。

### 10.9 Prompt 审计与 Phase 19 入口

对真实 Run 的 Prompt 记录复查后，确认下一瓶颈不是继续增加正文状态机，而是阶段上下文缺少唯一编译入口：

- Detail Prompt 从第 1 章约 25,865 字符线性增长到第 32 章约 45,016 字符，原因是每批携带全部历史章节 ledger；
- Summary、Outline、Detail 基础 Prompt 分别约 21,761、20,843、28,123 字符，存在 Story Brief、上游 Artifact、人物图和 Voice 的重复；
- 正文同时携带 chapter outline、SceneContract、结果桥、摘要、尾文、Voice Spec/Genome 与世界规则的多个版本；
- DeepSeek 正文关闭 thinking 是既定 Provider 策略，不是参数丢失；在重复上下文未收敛前开启 thinking 只会增加成本。

本轮已建立不调用模型的 `PromptBrief` 编译入口，并把 Detail 历史窗口限制为最近两章。真实第 4 章离线复算的两场 Prompt 总字符降为约 5,545 / 4,881；该数据只证明装配收敛，不代表文学质量通过。完整阶段职责、人物轨迹、Reality Reconciliation、Reviewer thinking 与三章 A/B 合同转入 `phase-19-narrative-program-and-prompt-compiler.md`。
