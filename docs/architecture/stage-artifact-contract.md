# Yotsuba Ink vNext Stage Artifact Contract

状态：Phase 27 唯一生产合同（2026-08-17 v1.0 Demo 收口）。生产阶段、Artifact、Run 输入与 LangGraph 路径必须遵循本文；Phase 26 和更早文档只保留为失败证据。当前已完成浏览器矩阵、全新 `official-deepseek-balanced` 真实长篇 Run 与 Export；人工逐章冷读、真实图片生图和投稿质量仍是后续软质量工作，不改变本合同硬门。

## 生产阶段

配置页不是运行阶段。LangGraph 只编译并执行下面这一条图：

```text
brief -> spine -> cast -> volumes -> detail -> text -> cover -> export
```

### 新建作品合同

新建作品固定为两步，且不增加 `info` 或其他运行阶段：

1. 先选择一套官方或自定义流水线；需要调整时进入独立配置页，可仅供本书使用或另存为模板。
2. 再提交一段自由创作想法。建书接口只接收该想法和已选流水线，不提前要求用户填写书名、题材或结构表单。

作品创建后以“待定书名”显示，创作想法写入项目专属流水线 `brief.core_concept`。正式书名属于 `StoryBriefArtifact.title`：由 `brief` 生成，必须是 2-30 字的非占位标题，用户确认 Brief 后才投影到作品列表、运行历史和导出元数据。Brief 候选稿或未确认内容不得提前改写作品标题。

| 阶段 | 唯一核心 Artifact | 用户决策 | 正式写回 | 下游依赖 |
| --- | --- | --- | --- | --- |
| `brief` 创作立项 | `StoryBriefArtifact` | 故事承诺、世界规则、主题问题、结局承诺、叙事声音和软长度意图 | `ArtifactStore.brief` | `spine` |
| `spine` 故事脊柱 | `StorySpineArtifact` | 因果推进、最终变化和结局是否兑现立项承诺 | `ArtifactStore.spine` | Role Demand、`cast`、`volumes` |
| `cast` 人物编排 | `CharacterBibleArtifact` | 主角、重要配角、功能/历史主体的职责、关系、变化和首次出现窗口 | `ArtifactStore.cast` | `volumes`、`detail`、`text` |
| `volumes` 分卷架构 | `VolumeArchitectureArtifact` | 每卷卷名、promise/conflict/climax/closure 与自然边界是否构成完整故事 | `ArtifactStore.volumes` | `detail` |
| `detail` 章节施工图 | `DetailArtifact` | 每章章名、字符预算、目的、场景转折和跨章交接是否均衡 | `ArtifactStore.detail` | `text`、`cover` |
| `text` 正文 | `ChapterArtifact`（按章版本） | 接受、人工编辑、定向修订或保留分支 | `ChapterStore`，证据后进入 Outbox | 下一章、`cover`、`export` |
| `cover` 封面 | `CoverArtifact` | 视觉 brief 和最终资产 | `ArtifactStore.cover`、AssetStore | `export` |
| `export` 导出 | `ExportArtifact` | 格式、章节版本、封面和元数据 | `ExportStore` | 无 |

每个阶段只有一个用户可编辑或批准的 Artifact。候选、审稿、预算、调用收据、checkpoint、Evidence、SSE 和写回状态不是 Artifact 字段。

## Artifact 分层

### 核心 Artifact

- `StoryBriefArtifact`：`title`、`premise`、`promise`、`world_rules`、`theme`、`ending_promise`、`voice`、`length_envelope`。其中 `length_envelope` 是 Run 创建时冻结输入的只读镜像；官方流程只让用户填写全书字符目标，章数与卷数由代码根据冻结编辑政策计算，Provider 和阶段编辑都不能另行填写或改写。要改变篇幅目标必须新建 Run。Brief 只冻结主人公处境、读者承诺、最少必要世界规则、核心两难、终局代价与叙事声音，不替 Spine 冻结潜入、取物、工具、权限、抓捕逃脱、设施防护等行动路线；一次性障碍、设备清单和证据获取步骤不得伪装成 `world_rules`。
- `StorySpineArtifact`：确定性 `turn-N`、每个 turn 的 `cause/change/progress_type/milestones`、`ending`、有限 `open_questions` 和 `progress_types`。代码先按冻结章数与章节承载密度计算容量区间，再冻结其中的精确 `turn_target`；Provider 必须一次返回该精确数量，不能自行选择区间端点或靠换稿纠正数量。Provider 只写 `cause/change/progress_type`，六个 `milestones` 的位置由代码按精确 turn 数绑定并写入 Artifact；对应位置必须承担启动、承诺、中心反转、危机、唯一高潮和余波语义。短篇可在保持顺序时合并相邻功能。长篇还必须包含 relationship 与 external 推进，12 turns 以上至少有两次 external 推进，禁止连续三个 information turn；不同 turns 不得复用相同 `cause` 或 `change`，单个 turn 的前因和变化也不能是同一状态。最终渲染 Prompt 必须要求 Provider 在同一次响应内静默核对数量、锚点、因果链与推进节奏；独立语义预审再检查责任归属、动机桥、行动主体、现实可行性、因果交接、重复推进、提前结案和终局推导。未通过的私有草稿不能写入候选：局部问题可在同一冻结合同下有界修复；提前结案、重复推进和因果交接同时失效时，运行时必须丢弃失败稿正文，只把根因清单带入一次全新因果重规划，避免模型锚定旧链。两类内部处理都不属于用户换稿。谜题证据链由冻结的 `inciting -> climax -> aftermath` 结构引用和 Detail 覆盖确定；`progress_type` 是节奏投影，不要求单独出现 `information` turn，外部行动或关系变化同样可以承载证据推进。
- `CharacterBibleArtifact`：Role Demand 先按全书规模获得动态容量区间，再只从已冻结 Spine 提取不可合并职责；独立预审通过后代码才预分配稳定 subject id。每个主体保存 `name/kind/function/background/conflict_history/present_stakes/temperament/speech_style/drive/change/debut/limits/demand_refs`，关系只引用冻结 id。`background` 只写故事开始前已经成立的身份与经历，`conflict_history` 单列其与核心冲突的既往渊源，`present_stakes` 明确当下失败会失去的具体人、关系、资格、位置或信念，`temperament` 与 `speech_style` 必须能被正文直接演绎，`limits` 必须写具体能力、伦理、知识、资源或行为边界；空泛标签、运行时术语、重名主体和多主角都由严格合同拒绝。每个档案分组还必须在候选写入前经过独立语义预审，核对需求对齐、背景时态、冲突史、利害归属、动机桥、行为区分与历史主体边界；私有修复不会生成用户可见候选。关系 `type/pressure` 必须描述已成立的选择、信任、责任或风险，不能使用“可能、或许、潜在、关系复杂”等未决表述。`role_demand.proposal` 与两类预审都属于 Cast Provider binding，不属于 Spine binding；每项 demand 必须显式冻结 `subject_mode=actor|historical_record`、`narrative_role` 与 `irreducibility`，其中 `irreducibility` 必须指出无法并入已有主体或机构的具体选择、压力或后果。预分配 subject ref 携带同一模式，代码强制 actor 生成非历史档案、historical_record 生成历史档案。唯一主角的 demand 必须同时引用首尾 Spine turns；actor 的 `active_turn_refs` 表示第一次真正登台的位置，historical_record 表示其身份、声音、证词、遗物或缺席第一次成为有效叙事依据的位置。代码再依据完整 turn 数与冻结章数确定性投影 `debut` 窄章节窗口。`turn-N` 不是 `chapter:N`，不得直接抄号。`historical_record` 的变化只描述其记录或遗产的叙事意义变化，不得承担 POV、当下行动或当下说话。
- `VolumeArchitectureArtifact`：确定性 `volume-N`、2-12 字唯一卷名、`promise/conflict/climax/closure`、连续 `turn_refs`、`cast_ids` 和粗粒度 `length_hint`。代码先用全书精确章节目标与冻结的单卷 `8-20` 章、首选约 `14` 章产品政策计算 `volume_min/target/max`，再要求 `VolumeBoundaryProposal` 精确返回 `volume_target` 个连续边界。模型拥有自然边界位置、卷名与卷内承诺的创作权，不拥有卷数。代码随后只按各卷 turn 负载和每卷容量边界分配精确章节槽位；`length_hint` 不参与数量计算。DetailLayout 只负责把连续 turns 和独立戏剧任务编排进这些槽位，不拥有增删槽位的数值权威。当前没有独立叙事线程注册表，因此 Artifact、UI 和下游上下文均不得生成或展示 `thread_ids`。
- Volumes 的“换一稿”会先使用同一条阶段修订意见重新生成自然卷界提案，再按新边界逐卷重写合同；不得复用上一稿的 boundary proposal，否则 UI 中“调整自然卷界”会成为无效操作。新的 boundary proposal 输入不携带上一稿边界，避免模型把旧答案当作冻结事实。
- `DetailArtifact`：连续 `chapter-N`、卷引用、2-12 字唯一章名、代码冻结的逐章目标字符数、`purpose`、POV id、动态场景区间内的 `scenes { place/objective/conflict/turn/result }` 和 handoff。系统先以合理章长带推导并冻结全书精确章数，再按确定性卷数、自然边界与逐卷 turn 负载分配精确章节槽位；`length_hint` 只描述内容负载，不参与数量计算。DetailLayout 把必要 POV 交接、地点/时间断点、关系并发和独立台面变化映射进每个槽位，无法无填充地支撑全部槽位时必须返回 `insufficient` 并退回上游重规划，不能自行缩短章节数组。系统再以冻结总章数、全书预算中心和单场景承载区间收窄本 Run 的每章可行场景容量。该区间只是防止单场过载或章节碎片化的容量边界，不是固定的场景配额。Spine 冻结宏观 cause/change 端点，Detail 拥有把端点演成可执行剧本的局部创作权：可以生成因果桥接所必需的尝试、受阻、策略选择、关系反应、失败的中间结果和后果传播，并让相邻章节引用同一 turn；这些局部动作不得改变该 turn 的起点事实和终局变化，也不得新增主线线索、具名主体、机构规则、权限、时间事实、宏观结果或支线。Provider 再按每章的事件单元、对抗层次、时空转换与不可逆转折动态选择场数，不得机械统一。Detail 是可执行的章节剧本卡，不是正文梗概：`purpose`、场景字段和 handoff 只记录本章要演出的事件、人物、冲突、转折、结果与交接。`target_characters` 只属于正文预算元数据，不计入细纲内容字数；Detail 调用应保持短而可核对，禁止扩写对白、氛围、内心或文学化填充。
- `ChapterArtifact`：章节 id、运行时分配的版本 id、从 Detail 原样继承的只读章名、正文和 `author_status`。正文 Provider 只返回纯文本流；版本身份、标题和状态由 LangGraph 确定性绑定。
- `CoverArtifact`：可执行 `brief` 和已选择资产 id；资产 URL、尺寸和生成收据属于 sidecar。
- `ExportArtifact`：格式、已接受章节版本 id、封面资产 id 和导出元数据。

### 确定性投影

关系图、人物压力、章节 cast、卷卡、节奏条、章节号、卷归属、交接链、引用集合、签名、ScaleProfile、Artifact 表单摘要和前端导航均由核心 Artifact 或领域账本派生，可删除后重建。投影不得反写核心 Artifact。

### 运行时 sidecar

`NarrativeRunState` 只保存 routing：`run_id`、阶段状态、Artifact ref、章节版本 ref、当前节点、decision ref、operation ref、失败证据 ref 和状态 revision。Provider receipt、脱敏的模型可见输入快照、token/cost、review lane、checkpoint id、interrupt、Evidence、Outbox 事务和 SSE 序列存放在各自的领域存储；输入快照不得进入 Graph State。

### 窄调用 / 工具结果

标题候选、因果缺口、人物弧检查、连续性检查、章节 Evidence、封面资产生成等只服务一个节点，必须带输入签名和证据 ref，不能扩充主 Artifact，不能直接写 Canon/Wiki。

### 删除字段

删除 `schema_version`、版本转换器、`new_characters`、自由文本人物/关系快照、`wiki_candidates`、`fact_reveals`、`foreshadow_actions`、自评分、UI 坐标、重复 synopsis/act/key-turn 字段、模型自动修复字段和所有 fallback 字段。正文后事实、Wiki、Canon 与伏笔变化都从正文 Evidence 生成提案。

## 人物编排边界

`cast` 是正文前唯一具名主体注册表。`volumes`、`detail`、`text` 只能引用冻结主体 id。新增主体、职责升级、关系重定向或首次出现窗口变化必须生成带触发证据和影响 Artifact 的 `CharacterChangeProposal`，由 LangGraph `interrupt()` 等待明确批准后创建新版本；不得在下游阶段临时补登记、转换旧槽位或用 alias 修复引用。

主角和重要配角必须冻结完整档案；功能角色必须冻结剧情职责；必要功能主体与历史主体必须在正文前冻结稳定名称、类型、用途、窗口和至少一条限制，不能升级职责。人物数量由冻结章数和培养密度动态投影为最小可培养容量、编辑中心与硬上限；Provider 必须至少满足动态下限，实际数量仍由不可合并的 Role Demand 决定，不能用机构代表或空泛人物填槽。默认 10 万字、40 章时建议下限 `3`、编辑中心上限 `7`、硬上限 `11`；超过上限或低于下限都必须重新评估，不能让模型自行放宽。长篇每一个 relationship turn 都必须由至少一个非主角 demand 的 `active_turn_refs` 覆盖，不能出现“Spine 声称关系变化、Cast 却没有另一方”的断链。所有 `debut` 窗口使用精确冻结章数投影，不使用章节可行区间下限。Fast 模式也必须在正文前产生版本和决策回执。

## Memory、Wiki、Canon、RAG

- 用户上传知识库是前置 `brief` 的 Source Pack。RAG 只在 `brief/spine/volumes` 前置规划读取，结果带来源、签名和采用状态；正文节点禁止盲检索。
- Worldbuilding 是创作设定；Character Graph 是角色与关系投影；Wiki 是正文 Evidence 驱动的事实账本；Canon 是用户批准后的事实权威；它们不能互相代替。
- Evidence 先生成 proposal，用户或明确的写回节点批准后才进入 Canon/Wiki；Retrieval、proposal agent 和模型自评分没有写权限。
- 已接受章节的 Evidence 提取使用独立、持久的 `EvidenceAttempt`。Provider 每条 claim 必须显式选择互斥的 `state.type=story|assertion|transition`：`assertion` 完整给出冻结主体、属性、值和认知状态，`transition` 只选择一个冻结 `source_fact_id`、`supersedes|resolves` 动作、新值和认知状态；主体、属性、生命周期与来源链由代码从源事实确定性投影，Provider 不再组合可选三字段、生命周期和多组事实引用。持久状态的保留命名空间只有 `evidence.<clue>.source|owner|custody`、`knowledge.<fact>`、`object.<object>.state` 和 `clue.<clue>.status`；`document.*`、`holder`、`.knows` 等同义别名由合同拒绝。相同主体和 `property_key` 已存在时必须引用其 `source_fact_id` 走 `transition`，不得再次 assertion 制造并行状态。第一次结构合同错误只允许在同一章节版本、正文 hash 和 Evidence operation identity 下做一次合同纠正；第二次错误或 Provider 不可用进入 `needs_action` interrupt。Evidence refs 为空时不得创建 Outbox、Canon 或 Wiki 写回，也不得推进下一章；显式恢复只重试 Evidence，不消耗正文换稿额度。
- 全书字符目标按去除空白后的字符数统计。Run 冻结默认 `2000-3000` 字、首选 `2500` 字的编辑章长政策，由全书目标除以章长上限/下限得到章节可行区间，再以 `round(全书目标 / 2500)` 冻结精确章数；用户与模型都不能覆盖。系统随后使用单卷 `8-20` 章、首选约 `14` 章的产品容量政策，从精确章数推导卷数可行区间和精确卷数。10 万字因此固定为 `34-50` 章可行容量、`40` 章精确目标，以及 `2-5` 卷可行容量、`3` 卷精确目标。该卷政策是 Yotsuba Ink 的编辑策略，不伪称行业统一定律。`VolumeBoundaryProposal` 必须精确返回三个连续自然边界，模型只决定边界落在哪些 turns 之间。代码再按各卷连续 turn 负载、单卷容量与 turn 承载密度分配精确且总和为 40 的卷内章节槽位；`length_hint` 和人物数量都不参与数量计算。失衡到无法承载的边界退回 Volumes，不能把末卷压成三四章或让 Detail 补水。DetailLayout 按卷顺序窄调用，每次只读取当前卷合同、turns、相关人物和精确槽位；Provider 必须逐槽写不同的戏剧任务，不能增删、合并或私改章数。每卷独立 Provider receipt 带 `volume_ref`，恢复时只补调未完成卷；全部卷聚合后仍须精确等于冻结总章数。系统随后从冻结章数、最低可用章节篇幅与单场承载区间推导动态场景边界；默认允许单一重戏用一场完整承载，不因达不到 `2500` 字中心值在 Detail 阶段拒绝。每章具体场景数仍由事件单元、对抗层次、时空转换和不可逆转折决定。Detail 冻结章名、场景负载与交接后，代码综合场景、出场人物、转折、地点和 `length_hint` 在预算中心两侧形成有差异的逐章正文目标；若场景承载无法精确达到全书软目标，则使用不低于全书 `70%` 最低可用门的最近可行预算，而不是要求 Detail 拆场补字。正文容差为极速 ±15%、平衡 ±12%、精细 ±8%。Provider 按冻结场景顺序生成纯文本；每场使用滚动区间，已接受场景的真实字符数确定性传给下一场。确定性量化事实门若拒绝首稿，只允许一次局部句段修复：代码抽取包含全部违规 token 的最小句段，遮蔽违规原词，只提供有限左右边界，Provider 仅返回替换片段；完整失败稿和违规原词不得进入修复输入。修复后相同或新的违规仍存在时立即以 `SceneProseContractError` 停止，不进行第三次调用或整场隐式重写。新具名人物、亲属绑定、权限或钥匙、报告/协议/口供/档案、证据来源与持有人、职业或程序前史属于新增持久事实；若冻结上下文没有对应签名，首次场景收据直接 `contract_rejected`，不得进入量化事实局部修复或任何隐藏重写。所有场景通过后才组装唯一 `ChapterArtifact`。篇幅目标用于引导结构和生成，不作为机械达标线：按模式计算的章节软带与全书 `90%-110%` 区间只记录 warning，不触发换稿。只有单章低于冻结目标 `50%`，或全书低于冻结目标 `70%`，才视为明显残缺的确定性 blocker；单章 blocker 位于审稿、Evidence、accepted 版本和 Outbox 之前，并只使用现有唯一一次章节定向换稿额度。达到最低可用篇幅后，是否接受以细纲承载、内容完整性、连续性和质量证据为主，不得为凑字数隐藏重试、强行扩写、截断正文或改动冻结章名、场景转折和交接。
- Spine 转折数由同一冻结政策中的“每 turn 可承载章节数”动态推导，不把固定 20/24 写成所有篇幅的常量；默认密度为每 turn 承载 `1.50-2.50` 章、首选 `2.00` 章。10 万字固定 40 章时精确目标为 `20` turns、完整可行区间 `16-26`。这一区间描述重大因果变化的承载力，不要求一章一个 turn，也不允许为了填满过密转折数重复取证、听证、处分或终局。极速和平衡模式使用同一代码目标；精细模式仅在用户显式锁定时收缩为可行区间内的单点。Spine 确认后，代码只检查真实 turn 数能否承载冻结的 40 章，不能反向改写章数；默认 20 turns 可承载 `34-50` 章，15 turns 无法承载 40 章，必须退回 Spine。只有当作品短到长篇密度带与最小三段式 Spine 根本没有交集时，三个 turns 才作为结构语法而非章节配额，允许多个 turns 落入同一章。`120` 只作为 Artifact/序列化技术上限。

## LangGraph、LangChain 和 Provider

LangGraph Graph API 是唯一生产运行时：一个 thread、一个持久 checkpointer、一个 `interrupt()`/`Command(resume=...)` 决策路径、一个事件投影和一个写回 Outbox。相邻章节顺序生成；同一冻结版本的审稿角色可用 `Send` 并行读取。

生产源码默认禁止直接使用 LangChain API：`pyproject.toml` 不直接依赖 `langchain*`，`src/` 不导入 `langchain`。LangGraph 传递安装的 `langchain-core` 只视为框架内部依赖，不成为 Yotsuba Ink 的模型、工具、Prompt、memory、structured output 或 Agent authority。若未来出现直接 LangGraph 子图与现有领域端口都无法覆盖的真实需求，必须先通过独立 RFC、源码 spike 和删除矩阵评审，不能在窄节点中顺手引入。

每个生产节点使用 Run 创建时冻结的 `ProviderBinding`（provider、model、temperature、max tokens、top-p、timeout、prompt、idempotency key）。没有隐式默认、Provider fallback、Reviewer fallback、schema alias、converter 或 legacy execution switch。明确的瞬时网络或超时错误可在同一 operation key、同一输入快照和同一 Provider 下内部重试最多三次，并把实际传输次数写入 receipt；合同、格式、余额、鉴权或语义失败不得隐藏重试。传输重试耗尽后才进入 Graph failure/interrupt，由用户决定是否继续。

官方平衡模板把高杠杆的 `brief/spine/cast/volumes/detail/text` 绑定到 DeepSeek Pro；`cover` 仍可使用 Flash。三档官方模板的 Spine/Cast 温度分别冻结为 `0.45/0.55`，Detail/Text 为 `0.30/0.82`；结构与人物阶段不能靠高随机性把合同修复转嫁给换稿。所有 DeepSeek 结构化节点显式关闭 thinking，且不发送 `reasoning_effort`，避免隐藏推理吞占 Artifact 的可见输出预算；质量由阶段职责、冻结上下文、严格 Schema、首稿自检、换稿与人工决策保证，不能用截断或 JSON repair 换取表面成功。极速模式仍可选 Flash，但不得绕过相同 Artifact、容量和人工决策合同。

每个带 Provider 的 operation 必须在调用前写入不可变、内容寻址的输入快照，并由 receipt 保存快照引用。快照包含脱敏冻结绑定、Prompt identity 与最终渲染正文、结构化 context、JSON schema 或纯文本/图片合同、stage/task、attempt、chapter/version 和 request signature；不得包含 API key、secret ref、Authorization/header 配置或 Provider 原始网络对象。同一 operation key 输入变化必须失败，换稿必须使用新的 attempt/operation key，既有快照和完成 receipt 不得覆盖。

当前已迁移的阶段 Artifact 生成、正文场景生成和 Evidence 提取使用完整回执生命周期 `pending -> provider_returned -> succeeded|contract_rejected`：`provider_result` 和 usage 在领域校验前持久化，`result` 只保存合同接受后的输出；未取得可解析 Provider 返回的传输、鉴权、余额或解析错误才记为 `failed`。因此这些 operation 的合同拒绝不得计为成功，也不得丢失实际 Token。proposal、review 和图片 operation 在完成同样迁移前仍使用既有 `pending -> succeeded|failed` 生命周期，不能把已迁移调用的生产能力写成全局既成事实。Evidence 的领域 operation identity 在初次提取、一次合同纠正和显式恢复间保持不变；物理 Provider 请求因输入不同使用确定性的独立 receipt ref，并全部绑定同一章节版本与正文 hash，不能用同一个 Provider 幂等键覆盖不同请求。

Provider 结构化响应去除首尾空白后必须是一个完整 JSON object，只允许一次标准 JSON 解析；Markdown fence、解释文本、对象截取、语法 repair、字段 alias/converter、默认值注入和未知字段丢弃全部禁止。所有核心键必须显式出现，允许为空时返回空字符串或空数组。Cast dossier、关系、卷边界、卷合同和 Detail 只按调用前冻结的容量/叙事边界拆分，单元结果经 operation receipt、冻结目标和引用校验后才确定性聚合；部分结果不得写成候选 Artifact。Volumes 必须按卷顺序执行一个卷一个窄调用：输入只含该卷冻结的 `volume_spine_turns`、单个 boundary、最小人物引用、卷序策略和可选上一卷 closure 交接，不得暴露完整 Story Spine 或相邻卷 turns。正文的核心 Artifact 仍按章冻结，但 Provider 只按当前章冻结场景顺序执行窄纯文本调用，不包 JSON；相邻场景共享最小交接，单场收据不可直接成为章节候选，只有全部场景通过长度合同后的确定性组装结果才能写入 `ChapterStore`。Export 不调用 Provider。

审稿结果同样是严格 sidecar 合同。每个 finding 必须含当前章节正文中的非空精确 `evidence` 和显式 `subject_ids`；人物审稿只可引用冻结主体 id。运行时向人物审稿确定性投影当前章必需、当前可用和未来尚不可用的主体集合。未来窗口主体缺席不构成 finding；无效证据或未知主体使该 review receipt 失败并投影 `review.unavailable`，不得过滤或自动改文。Reviewer 自报的 `severity=blocking` 只作为来源元数据进入 `review_warnings`，没有系统阻断权。若冻结流水线把某 reviewer 标为必需，而该 lane 不可用，运行时生成 `resolution=manual` 的 `required_review_unavailable` 确定性 blocker，只允许取消；不得静默接受、触发正文换稿或再次调用 reviewer。

正文决策唯一使用 typed `QualityDecision`：`structure_contract` 与 `contract_blockers` 只来自确定性合同，`review_warnings` 只承载模型审稿证据，`evidence_status/evidence_degraded` 只投影 EvidenceAttempt，`regeneration_used/regeneration_limit` 固定记录 `0/1` 换稿额度，`accepted` 表示当前正文版本是否已经接受。第一次确定性 blocker 可触发一次定向换稿；额度用尽仍有 blocker 时只允许取消。审稿告警可接受或定向换稿，但不能自动阻断或循环换稿。Evidence `needs_action` 保持 accepted 正文不变，只允许重试 Evidence 或取消，也不消耗正文换稿额度。

最后一章完成 Evidence 与写回后、进入 Cover 前必须执行一次确定性全书终检。`ManuscriptQualityReport` 核对冻结 Detail 章节集合/顺序/章题、accepted 状态、引号配对、重复段落与重复双句片段、ResolvedStoryState 冲突；模型 reviewer finding 和模板动作复用只进入 warning。Fast 只在 deterministic blockers 为空时自动接受；有 blocker 时 `manuscript_quality_decision` 只允许取消，Balanced/Deep 即使合同干净也保留作者确认。该门投影 `quality.manuscript_evaluated` 与 `quality_report`，不会自动改写任何历史章节；修订必须从对应 checkpoint 创建分支。

## 事件和 UI 投影

SSE 只投影稳定领域事件：`run.started/completed/failed`、`node.started/completed/failed`、`artifact.candidate_ready/committed`、`decision.required/resolved`、`review.started/completed/unavailable`、`quality.warning/manuscript_evaluated`、`evidence.proposed/recovery_required`、`writeback.queued/committed/failed`、`checkpoint.saved` 和 `branch.created`。事件 envelope 只有 event/run/thread/sequence/type/stage/node/chapter/status/payload ref/checkpoint ref；前端不得消费原始 Graph State。等待章节决策时，Run read model、`decision.required` payload 与前端合同必须投影同一份 `quality_decision` 或 `quality_report`，不得从旧 `reason.blocking_findings`、`warning_findings` 或 UI 本地状态重建第二套语义。

前端路由使用上述八个 stage id；阶段表单只编辑当前核心 Artifact；人物工作台读取 `CharacterBibleArtifact` 与其 change proposal，3D 星图、关系邻域、出场时间线和档案面板共同覆盖正式角色与功能/历史主体；运行观察显示当前 node、并行 review、预算、checkpoint 和失败 evidence；写回状态只读取 `review.*`、`evidence.*`、`writeback.*` 事件。保存草稿不等于正式写回。

## 合同门

每个迁移 Wave 必须同时证明新路径并删除旧路径：

1. fake Provider 全图可重放；结构化输出、Artifact ref、decision、interrupt、checkpoint、SSE 和 Outbox 幂等测试通过。
2. 静态扫描无 legacy/shadow/dual runtime、Detail v1/v2/v3、fallback、alias、converter 或旧 stage id 生产引用。
3. projection 可删除重建；断线重连不影响执行；同一 operation/decision/writeback 恰好一次。
4. 全量离线测试和前端构建通过后，才可在用户批准、限额和脱敏收据下进行新的真实 Provider Run。真实输出、文学连续性、成本和作者冷读另行验收。
5. Character reviewer 的未来窗口误报必须因缺少章节内精确证据而成为不可用 receipt；真实提前出现、有效 prose 硬边界和硬容量 finding 仍可阻断。必需 reviewer 不可用时只能进入显式人工门。量化事实首稿失败后只允许一次遮蔽局部句段修复；新增持久事实直接拒绝且不能进入修复。相同错误无进展或修复仍不合同时 Run 明确失败，不能发起第三次调用或回退到整章盲目重写。
6. Evidence assertion 必须通过保留命名空间并拒绝对现有主体属性的重复声明；全书终检必须在 Cover 前阻断章节集合、格式、重复正文和 Story State 硬冲突，同时把模型文学判断保留为 warning。

## 2026-08-11 真实三章合同证据

- Run `phase26-deepseek-submission-7c66d1a6-8` 接受 `chapter-1-v3-accepted`（1811）、`chapter-2-edit-bc817e88a1aef999-accepted`（1666）和 `chapter-3-edit-a6d3d5e69adc147d-accepted`（1809）；后两章为人工编辑候选，均通过同一 author decision 提交。
- 46 条 Provider operation 为 42 成功、4 失败、0 pending，合计 271,120 tokens；10 条人工 decision 单独记账，不伪装成 Provider 调用。
- 第 3 章只由 Provider 选择 `span_ids`，代码将 8 条 claim 绑定到已接受正文；Outbox、Canon、Wiki 使用同一 transaction 且各提交一次。第 1、2 章旧 quote mismatch 不重试、不转换、不写回。
- 文本阶段完成后 CoverBrief 文本成功；真实图片 Provider 未配置也未调用，fake binding 失败使 Run 停在 `cover.generate_candidate`，Export 未运行。
- 冷读判定仅为“连贯的三章短篇接受样本”：第 1 章略有公式化表达，第 2 章信息压缩，第 3 章的证据驱动主题收束最强但经过人工编辑。不能据此声称模型独立投稿质量、8-12 章单卷或全书验收完成。

## 2026-08-12 新合同验收边界

- `phase26-deepseek-three-gate-dcf5623f-2` 已取消，只保留为人物注册与审稿误报的失败证据；不得恢复、改写或把其中 Artifact/checkpoint/Evidence 复制到下一次验收。
- 新代码把具名历史主体纳入正文前冻结注册表，并要求审稿 finding 绑定当前章节精确证据与冻结主体 id。相关结果目前只属于离线合同证据，不能回填旧 Run 的成功结论。
- 下一次真实三章门禁必须创建完全全新的 Run，从 `brief` 开始，并让三章全部走新 Evidence、review 和 exactly-once Canon/Wiki 写回。通过人工冷读后才允许创建新的 8-12 章单卷 Run。
- GitHub 只在重构、离线门、浏览器矩阵、全新三章和单卷验收全部结束并完成提交范围审查后推送一次；Gitee 不参与该发布路径。

## 当前篇幅门修订（2026-08-20）

篇幅目标继续作为结构引导与监控 warning。单章只有低于冻结目标 `50%` 才进入确定性严重不足 blocker；全书低于冻结目标 `70%` 仍由终局聚合门阻断。达到单章最低可用门后，是否接受以细纲承载、内容完整性、连续性和质量证据为准，不为凑字数隐藏重试或强行扩写。
