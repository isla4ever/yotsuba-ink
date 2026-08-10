# Phase 22：细纲节奏、短章生产与连续交接

> 状态：本地节奏、审稿 v13 与叙事证据恢复合同已闭环；三章 DeepSeek 文学验收仍未通过，禁止把定向恢复或单章产物宣称为全链路完成。
>
> 日期：2026-08-07。

## 1. 产品判断

正文不是把整章细纲逐条翻译成一篇长说明文。Detail 才是剧本层：它决定本章必须发生的叙事位移、人物选择、代价、信息变化和章末压力；Writer 只在这个范围内自由安排动作、对白、感官和节奏。

一章可以暂时不结清全部线索。只要读者能看清“人物现在处于什么状态、刚刚改变了什么、下一步为什么必须发生”，未完成动作就应通过 `continuity_handoff` 交给下一章，而不是强行在本章塞完。

## 2. 新合同

### 2.1 每章只承担一个叙事位移

- Detail 默认一章一个主场景；只有发生紧密且不可拆的空间/关系转换时才使用第二场。
- 第三场及以上属于明确的高潮、群像汇合或调查链例外，必须给出额外预算和拆章理由。
- 每场必须有 `entry_state -> choice -> cost -> exit_state`，没有有效变化的场景应回到上一章或拆成新章。
- 章末写出 `state_out`、`unresolved_actions`、`emotional_carryover`、`knowledge_carryover`、`next_pressure`；未完不是失败，失去可读交接才是失败。

### 2.2 篇幅合同

篇幅是创作节奏的软目标，不要求机械命中；生成上限是防失控边界，不是鼓励写满的目标。

| 规模 | 结构 | 目标/生成区间 | 说明 |
| --- | --- | --- | --- |
| 三章检查点 | 1 卷 × 3 章 | 1700 / 1400-2200 | 用于低成本观察连续性 |
| 受控中篇 | 3 卷 × 3 章 | 1800 / 1450-2300 | 保留现有九章验收形状，降低单章密度 |
| 投稿长篇 | 4 卷 × 12 章 | 2000 / 1600-2400 | 增加章节，不把更多剧情塞进单章 |

验收区间比生成区间略宽，用于容纳自然收束。普通超长只记录警告；只有越过硬上限、截断、空稿、明确交接断裂或事实冲突才进入修复。

### 2.3 场景预算

场景预算必须按整章剩余预算计算：当前场上限扣除已写内容、分隔符和未来场景最低值。不得再使用“每场等额上限 × 弹性倍数”导致多场景总和超过章节上限。

## 3. Prompt 分层

Writer 只收到确定性编译出的 `SceneExecutionBrief`、上一章交接和当前 POV 的最小事实投影。它不接收全量 Story Bible、全量 Wiki、审稿清单、AI 检测指标或写回协议。

Detail Prompt 负责把相邻章节拆开，并把未完动作写入下一章施工单；不要求逐字复刻自然语言，也不为每章强行安排多个转折。篇幅提示使用“建议在附近自然收束”，不使用“必须严格命中”。

## 4. 质量与恢复

- Fast：只做确定性硬门和轻量诊断，普通篇幅偏差不阻断。
- Balanced：连续性/事实冲突可触发一次局部修订；普通超长不自动整章压缩。
- Deep：允许一次有证据的局部修订和模型审校；只有硬失败才进入 Provider 恢复。
- 自动删减默认关闭。人工删减仍可用；模型删减仅在明确的 `surgical` 目标、可定位锚点和硬上限失控时开放。
- 任何修复都必须保留冻结正文签名、章节交接和已成立事实，禁止为追求数字删除关键行动。

## 5. 验收顺序

1. 预算函数证明多场景总和不超过生成上限。
2. Detail 回归证明默认一场、例外两场可通过，跨章 handoff 不断裂。
3. Prompt 编译审计证明 Writer 上下文短于旧合同且没有内部质量术语泄漏。
4. 运行后端与前端全量测试、构建和类型检查。
5. 只使用 DeepSeek 从 Info 开始逐阶段真实测试；正文先生成三章并人工审读，再决定是否进入全书。

## 6. 本地实施结果

2026-08-07 已完成以下合同收口：

- 默认正文目标调整为 `1700` 字符，生成区间为 `1400-2200`，`max_tokens=3600`；默认关闭自动场景压缩，保留一次有证据的局部修订。
- Detail 默认一章一个主场景，普通编辑入口最多添加到两场；第三场仅作为高潮、群像汇合或不可拆调查链的兼容例外。
- 相邻场景和章节使用稳定 `handoff_in_id/handoff_out_id` 连接；自然语言交接只要求因果连续，不再要求逐字复制。
- Detail 分批上下文只保留当前卷、上一章交接和最近两章轨迹，不再随全书章节数线性增长。
- Writer 以 Detail 编译出的 `SceneExecutionBrief` 为唯一剧本输入；人物选择、代价、状态和交接属于必须兑现项，对白、动作、感官、意象与局部节奏保留创作自由。
- 正文事实写回继续受 `RealityReconciliation`、证据签名和卷级 Canon 审计约束；计划态内容不得提前成为事实。
- 前端 Detail Artifact、章节蓝图、人物/关系轨迹、事实/Wiki、伏笔和连续性交接已同步到 v2 结构，旧展示字段不再作为主合同。
- 默认工作流版本为 `1.2.4-phase22-rhythm`，后端、前端、运行时工作流 JSON 与 Detail Prompt 镜像一致。

本地质量门结果：

- 后端全量：`1393 passed, 1 skipped`。
- 前端全量：`134 files / 523 tests`。
- Phase 22 关键链定向回归：`79 passed`。
- TypeScript `tsc --noEmit`、Vite 生产构建、Python `compileall`、`git diff --check` 均通过。
- CSS 审计通过；首屏 CSS 为 `31.9 KiB gzip`，懒加载阶段样式未回流首屏。
- `default_workflow().model_dump()` 与运行时工作流镜像一致；`DETAIL_STAGE_PROMPT` 与运行时 Prompt 镜像一致。

这些结果只证明本地结构、预算、状态和前后端合同一致，不证明文学质量或真实 Provider 生产已经通过。

## 7. 真实验收边界

下一步必须创建新的 Phase 22 Run，不恢复旧失败 Run。只使用 DeepSeek，从 Info、Summary、Outline、Detail 逐阶段检查结构、Prompt 长度、人工可读性和正式写回边界；正文先生成三章并停下，重点审读章节与分卷承接、人物选择、伏笔推进、事实一致性和 AI 化表达。三章不达标时先回到对应上游 Artifact 或编译规则修正，不直接生成整本，也不通过无脑重试消耗额度。

## 8. 首个真实 Run 暴露的问题

`phase22-deepseek-three-chapter-20260807-a1` 在 Info 只执行了一次真实调用后停止：

- Provider：DeepSeek `deepseek-v4-pro`；
- 任务：`info_recommend`；
- 渲染 Prompt：5477 字符；
- 实际消耗：2464 prompt tokens、4183 completion tokens，共 6647 tokens；
- 失败：`json_parse_failed`，未触发备用厂商或隐藏重试；
- Run 没有写入任何 Info Artifact、Memory、Wiki、Canon 或后续阶段状态。

离线重建确认请求已经使用官方 `json_object` 模式、Prompt 中存在 JSON 关键字与输出示例、思考模式为 `thinking=enabled + reasoning_effort=high`，Provider 层没有重复追加 Schema。根因不能仅凭失败码推断；旧事件没有保留解析形态，因此无法判断原响应是多个对象、数组、解释加 JSON 还是残缺 JSON。

本轮先完成以下基础修复，不消耗 Provider 额度：

1. 结构化解析生成候选对象集合；只有唯一对象满足当前阶段顶层 required/type 合同时才可从多个对象中选择。
2. 多个候选同时满足合同时继续 fail closed，不按出现顺序猜测“最后一个就是答案”。
3. Provider 异常携带脱敏形态诊断：finish reason、响应字符数、reasoning 字符数、候选/平衡对象/已解析对象/Schema 命中数量、顶层类型、截断后的字段键和 SHA-256。
4. Run 的 `provider_attempt_failed` 持久化上述诊断，但不写原始响应、正文摘录、API Key、Base URL 或请求头。
5. `partial_content` 只保留在当前进程异常对象中供显式本地恢复工具使用，不进入事件、快照或公开错误。

## 9. 正式调用前门槛

新的 Run 只能在以下本地门槛全部通过后创建：

### 9.1 阶段与 Context

- Info、Summary、Outline、Detail、Text 的权威 Artifact、用户决策、正式写回和下一阶段投影均由测试覆盖。
- Detail 只携带当前卷、上一章交接和最近两章轨迹，不随章节数线性增长。
- Writer 只消费 `SceneExecutionBrief`、上一章交接和当前 POV 最小事实，不读取 RAG、全量祖先 Artifact 或 Reviewer Rubric。
- 未上传且未选择资料时用户 RAG 调用与事件均为 0；正文阶段不直接检索用户资料库。

### 9.2 生产与写回

- Fast、Balanced、Deep 使用同一 `production_status` 语义，但拥有不同阻断合同。
- 多 Reviewer 使用同一冻结 Snapshot；所有硬角色参与协调，文学冷读不可用只降级诊断。
- 局部补丁每章最多一次，补丁后只复检实际阻断角色和受影响的确定性门。
- Reality Reconciliation、assertion evidence 和卷级 Canon 审计继续是 Wiki/Canon 正式写回前置。

### 9.3 Provider 与恢复

- 结构化响应的单对象、解释加对象、多个对象、数组、残缺 JSON、空内容和长度截断均有回归测试。
- 失败事件能区分响应形态且不保存原始内容；鉴权、余额、端点、限流和网络错误继续使用稳定公开码。
- 新 Run 不配置备用厂商、不复用 `a1`，每个阶段失败后停止并人工判断；禁止盲重试。
- Provider operation、Token 结算和正式写回保持幂等，恢复不得重复调用或重复扣费。

### 9.4 本地发布门

- 后端全量、前端全量、TypeScript、Vite build、CSS 审计、Python compileall、运行时 Prompt/Workflow 镜像和 `git diff --check` 全绿。
- 前端各阶段只显示后端真实字段，`accepted_with_warnings` 不被误当阻断，弹窗、Tab 与章节切换不触发重复 Provider 调用。
- 以上证据写入本文后，才创建新 Run，从 Info 开始逐阶段运行；不能直接跳到正文或整书。

## 10. 本轮壳层与响应式收口（2026-08-08）

在真实 Provider 之前完成了以下本地重构收口：

- 品牌壳层统一为 `YI / Yotsuba Ink / 长篇创作工作台`，Studio 保留“作品工作室”语义。
- History 选中记录现在以该 Run 的 `quality_mode` 作为页面主题源，并通过 History Shell 令牌覆盖侧栏、按钮和进度轨，避免当前工作流模式与历史记录出现两套活动色。
- Story Bible 路由 Header 读取 `routeBibleSection`，显示对应分区和 `Story Bible · 只读浏览`；只有 `/run/*` 才显示生成阶段运行态，避免把 Bible 误标为“导出”等阶段。
- 人物关系 3D 节点、人物标签和关系标签提高了桌面可读尺寸；1280 / 1440 / 1728 宽度下画布与档案栏不重叠、不越界。390 宽度下显式切换为“3D 画布 → 人物档案”流式行，修复画布最小高度导致的 10px 交叠。
- 阶段切换点击实测侧栏保持 `240px`、内容区保持 `1040px`，Route Transition 只发生透明度变化；未复现侧栏先抖动或横向位移。
- 代表性人物档案弹窗实测覆盖整个视口，遮罩外命中元素为 backdrop；Tab 从末尾回到首控件，Esc 与点击遮罩均关闭。

浏览器证据写入 `output/playwright/phase22-route-matrix-1280.json`、`output/playwright/phase22-route-matrix-390.json` 和对应 PNG。1280×920 与 390×844 的七阶段、规划、History、Studio、Story Bible 路由均无横向溢出；浏览器 error/warn 日志为空。

本轮本地发布门最终结果：后端 `1400 passed, 1 skipped, 1 warning`；前端 `135 files / 525 passed`；`tsc --noEmit`、Vite build、Python `compileall`、CSS audit、CSS split check、`git diff --check` 均通过。首屏 CSS 为 `32.0 KiB gzip`；`default_workflow().model_dump()` 与运行时工作流 JSON 完全相等，六份运行时 Prompt 内容和变量逐项相等。

这些 UI 与本地合同证据仍不代表文学质量或真实 Provider 已接受。下一步只允许创建新的 DeepSeek Run，从 Info 单阶段开始；每阶段失败即停，正文最多先生成三章并人工审读，禁止恢复 `phase22-deepseek-three-chapter-20260807-a1` 或盲重试。

## 11. 新 Run B 的真实失败与预算修正（2026-08-08）

`phase22-deepseek-three-chapter-20260808-b1` 使用全新 Run、单一 DeepSeek Provider、无备用链，从 Info 开始真实执行。Info 使用 `deepseek-v4-pro` 成功并写入确认产物；Summary 切换到 `deepseek-v4-flash` 后在一次调用中停止，未进入 Outline、Detail 或正文。

本次失败证据：Summary 请求 `max_tokens=8000`，Provider 报告 `completion_tokens=7999`、`reasoning_tokens=6509`、`response_chars=2717`、`finish_reason=length`，公开错误码为 `output_truncated`。因此不是 JSON 解析或质量阀门拒绝，而是“思考预算占满结构化响应”的阶段策略错误；该 Run 未恢复、未重试、未写入后续 Artifact。

产品修正：Summary 是把 Info 压缩为可引用因果主线的结构化节点，不需要把思考过程暴露给用户，也不应让 reasoning 挤占 JSON 输出。DeepSeek Pro/Flash 的 Summary 请求现在显式关闭 thinking 并移除 `reasoning_effort`；Info、Outline、Detail 仍按复杂结构推演保留 thinking，正文继续关闭 thinking。这样保留真正需要推演的节点，同时把预算用于完整、可校验的 Summary Artifact。

LangGraph Stage/Global 主路径迁移不是本次三章检查点的前置条件。它继续以后置的 Shadow/Dual、回滚演练和单卷验证为退出门；不能用框架迁移掩盖 Provider、Prompt 或文学质量问题。

## 12. Run C、Run D 与审稿 v13（2026-08-08）

### 12.1 Run C：误判缺项与补丁锚点失败

`phase22-deepseek-three-chapter-20260808-c1` 已完成 Info、Summary、Outline、Detail，并生成第 1 章 2316 字符正文；它没有完成三章验收。语义审稿把正文已有的“决定找陈远舟”误判为缺项，随后局部修订使用低于旧 8 字门槛的短锚点而被安全校验拒绝，最终以 `revision_patch_invalid` 停止。原稿、上游四阶段 Artifact、Provider 用量和稳定检查点均保留，没有自动整章重写。

本地修正如下：

- 复合审稿合同拆成带显式主语的原子动作，系统提示、人物动作和决定不再共用含混主语。
- 自动修订只处理真实 Detail 硬缺项与 POV 越界；文学风格、解释密度和审美建议保留为诊断，不再无条件改写冻结正文。
- 局部修订最短锚点由 8 字放宽到 4 字；唯一锚点无需伪造 `occurrence`，重复锚点必须提供真实出现序号，仍禁止按模糊相似度猜位置。

### 12.2 Run D：中间交接误审与叙事证据阻断

`phase22-deepseek-text-checkpoint-20260808-d1` 从确认的上游 Artifact 创建独立 Text Run。首次生成因中间场景 `handoff` 被重复当作硬合同而停止；恢复过程中重新调用了语义审稿、章后处理和叙事抽取，并产生新的第 1 章 2732 字符正文。该 Run 最终在 `narrative_extraction` 停止，未进入第 2 章：

- 一条对话证据把 `“那段录音里，”她说，“有人叫我的乳名。”` 压成了不存在于正文的连续引语；
- 一条场景指纹把正文的“她把那段杂音……”改写成“林汐把那段杂音……”；
- 断言和指纹均无法逐字定位，因此 Reality Reconciliation、Memory/Wiki/Canon 正式写回和三章汇合没有执行。

Run D 不再恢复。它已经发生正文重生成和多次章后调用，继续在同一状态上叠加恢复既不利于审计，也会增加无效 Token。后续只从 Run C 已确认的 Info 至 Detail 检查点创建新的 Text Run。

### 12.3 v13 合同与兼容迁移

语义审稿合同升级为 `13-final-handoff-only`：

- 中间场景交接由后续场景的进入状态和现实对账吸收，不再重复作为硬缺项；
- 只有章节最终场景 `handoff_out` 进入硬审，确保下一章仍有明确可执行交接；
- v12 `12-atomic-subject-actions` 的签名一致审稿结果可零 Provider 迁移到 v13；更早的 v11 缓存继续失效，避免把旧复合语义带入新合同。

这不是降低连续性门槛。场景事务、计划/现实对账、最终交接和正文证据仍必须全部成立，只删除重复审查同一中间动作造成的误报。

## 13. 叙事证据的受控本地恢复

证据门继续以正文原文和 UTF-16 范围为权威。本轮只增加两类可以回到唯一连续原文的零 Provider 容错：

1. 对话被一个说话归属动作打断时，可从模型压平的引语恢复为包含“她说/人物说”等插语的唯一连续正文；允许成对外层引号，不允许跨无关句或补写词语。
2. 只有场景指纹允许把开头的姓名与单字代词互换；除开头人物指代外，剩余短语必须逐字连续、位于句界且全章唯一。状态变更断言不使用该容错，主体或动作不同仍直接失败。

Run D 隔离区中的 12 条断言和 2 条场景指纹现可在原 2732 字符正文上本地绑定；绑定结果保存的仍是正文真实片段，而不是模型改写句。这只证明隔离负载可以零费用恢复，不代表 Run D 已通过，也不会触发其正式写回。

本轮验证结果：

- 证据绑定、章节叙事运行时与证据重绑定定向回归：`35 passed`；
- 后端全量：`1388 passed, 6 skipped, 1 warning`；警告为 FastAPI/Starlette 既有 `httpx` 适配弃用提示；
- 全量中唯一同步修正的旧断言，是 v13 下中间交接缺项从 2 个降为 1 个；最终交接缺失仍由独立测试保持 fail closed。

## 14. 下一次真实 Text Run 门槛

新的 Run 必须满足以下条件后才调用 DeepSeek：

1. 从 Run C 的 Info、Summary、Outline、Detail 确认检查点创建新命名空间，不复制正文、旧审稿、叙事抽取、Wiki/Canon 写回或失败状态。
2. 固定三章上限和 Deep 模式；不配置备用厂商，不恢复 Run D，不在失败后自动扩容重试。
3. 每章生成后依次检查冻结正文、语义审稿 v13、确定性质量门、叙事抽取、Reality Reconciliation 与正式写回，再允许下一章。
4. 三章全部完成后才评估章节衔接、人物选择、伏笔证据、信息重复、AI 化表达和投稿可读性；技术通过与文学通过分开记录。
5. 任一硬失败先定位到 Detail 剧本、Prompt 编译、Provider 输出或本地证据绑定中的责任层，再决定修复；不得以无脑重试替代诊断。

## 15. Run E1 与场景双层预算（2026-08-08）

`phase22-deepseek-text-checkpoint-20260808-e1` 从 Run C 的已确认 Info 至 Detail 检查点创建，没有复制正文、审稿、叙事抽取或正式写回。它在第 1 章第二场停止，未进入模型审稿、章后处理、Reality Reconciliation 或第 2 章：

- 第一场完成并保存 `1259` 字符；
- 第二场初次返回 `2385` 字符，超过当时 `700-1374` 的单场等额信封；
- 唯一一次完整场景修复返回 `2470` 字符，仍未进入信封；
- 最终以 `artifact_validation` 停止，原候选保存在 `scene_repair_pending`，没有连续重试；
- 本轮约消耗三次 Provider operation，分别记录 `2925`、`4228`、`5810` tokens。

E1 不再恢复。它已经消费生成与修复调用，继续在同一命名空间套用新预算会混淆策略版本、用量与文学结果。

根因是单个预算三元组同时承担了三种不兼容职责：等额场景节奏、Provider 输出提示和最终章级安全门。模型自然展开第二场时，系统要求它把完整因果强行压回窄等额区间；修复失败后整章随即作废。这与“篇幅是节奏软目标，章级上限才是安全边界”的产品合同不一致。

本地实现现拆为两层：

1. `scene_generation_budget` 保留等额软预算，用于节奏诊断、超额事件、人工可读性和恢复审计；它不会因 Prompt 放宽而失去 `chapter_scene_length_variation_accepted` 观测。
2. `scene_generation_prompt_budget` 只用于当前 Provider 调用。存在显式 `hard_max_chars` 时，它在预留后续场景最低字符数与分隔符后，允许当前场使用有界自然波动；上限取“章级剩余安全预算”和“场景目标 `2.4x`”的较小值。
3. E1 同形条件下，第一场调用信封为 `700/850/2040`，第一场完成 `1259` 字符后，第二场调用信封为 `700/850/1939`。目标仍是 `850`，但模型不再被错误告知 `1374` 是唯一可用的完整场景边界。
4. 最终验收没有放宽：超出软预算但位于章级剩余安全范围的完整场景可零调用通过并记录变体事件；真正越过章级硬边界、截断或缺失交接时仍只允许一次修复，失败候选保留为检查点并停止。

本轮无 Provider 验证结果：场景预算、截断恢复、压缩补丁与 Phase 22 节奏定向回归 `41 passed`；后端全量 `1389 passed, 6 skipped, 1 warning`。这只证明预算职责已解耦且恢复语义未回归，不证明 DeepSeek 会遵守新信封，也不证明三章文学质量通过。

下一次必须创建新的 Text Run，不恢复 C、D 或 E1。仍只生成三章并逐章停靠；若同一 Provider 再次明显越过章级调用信封，应先记录原始完成原因、输出字符数与 Prompt Trace，再评估是否需要 Provider 专属长度提示或局部结构修复，不能扩大自动重试次数。

## 16. Run F1 三章停靠与 Phase 23 交接（2026-08-08）

`phase22-deepseek-text-checkpoint-20260808-f1` 使用 E1 后的场景双层预算重新创建 Text Run。它没有复用旧正文或失败状态，已有 14 次 Provider operation 全部成功：第 1 章完成 3073 字符，第 2 章完成 3337 字符，第 3 章生成 3353 字符并冻结在 `prose_ready`。第 3 章尚未调用模型审稿、叙事抽取或正式写回。

本次停止点是确定性重复门把同一段物证从“旧录音被发现”到“接入全岛广播后公开播放”的复现误判为无推进复写：

- 原录音：`“旧阵列的模型有问题。干扰会让路径偏差十七度以上。不要相信修正数据——”`；
- 广播复现：`“旧阵列的模型有问题。干扰会让路径偏差十七度以上——”`。

两处引语承担不同叙事功能，且前后分别绑定录音/硬盘和广播/播放载体，因此不能通过删除正文解决。与此同时，普通对白复述、动作链重放和叙述扩写仍必须阻断，不能把“物证复现”扩展成宽泛重复豁免。

F1 也暴露出三个独立控制面问题：逐场 `scene_generation_max_tokens` 被长篇配置当作固定请求值，绕过了当前字符信封；章级闭合容差已经接受第 2、3 章，总字数门却仍以 9600 字符硬上限重复处罚；规则修正后缺少绑定 Chapter Artifact、Context、Intent、Scene/Prose/Chapter Draft 和检查点签名的零 Provider 复检入口。

这些问题进入 `phase-23-preflight-production-closure.md` 统一收口。F1 正文、Scene Draft、Chapter Draft、Token、operation 和既有写回在本地修正期间全部冻结；只有 Phase 23 定向、后端全量、前端共享合同和静态发布门全部通过，且零调用复检差异审计为零后，才允许恢复第 3 章原本尚未发生的审稿、抽取、Reality Reconciliation 与正式写回。技术通过后仍需单独进行三章人工文学审读，不能据此宣称达到投稿质量。
