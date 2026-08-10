# Phase 17：叙事编译器与事务式 Canon

> 状态：Wave 17.0–17.18 已落地并完成三章 Canon 修订分支技术验收；人工偏好校准、作者最终审读与整书 Run II 退出指标仍待完成
>
> 前置合同：`stage-artifact-contract.md`、`phase-13-literary-quality-and-editorial-readiness.md`
>
> 触发证据：Run I `phase17-live-book-deepseek-20260801-i` 自动技术验收通过，但人工审读发现多项投稿级硬错误

## 1. 结论

当前正文链路的主要问题不是 Prompt 不够长、质量步骤不够多或状态机节点不够细，而是这些步骤没有共同维护一个可验证的叙事状态。系统目前能证明“字段齐全、调用完成、模型给出高分”，却不能证明“人物、时间、空间、证据和解决机制在文本中真实成立”。

Phase 17 不再增加泛化评分层，也不新增一个用户必须操作的创作阶段。核心改造是把正文运行时升级为：

```text
已确认细纲
  -> 叙事世界状态快照
  -> 场景执行合同
  -> 正文候选
  -> 从正文提取实际状态变化
  -> 硬一致性门
  -> 章节临时提交
  -> 卷级全局审计
  -> Canon 正式提交
  -> 冷编辑与盲化偏好评审
  -> 作者确认与导出
```

产品内部名称为“叙事编译器”，但前端不向普通用户暴露编译器术语。用户只看到：哪一处前文与当前稿冲突、两段原文证据、影响哪些后续章节，以及可以局部修复还是必须回退场景设计。

## 2. Run I 证明了什么

Run I 的九章正文全部通过：

- 九章确定性质量结果均为 `passed=true`。
- 单章模型审校分数为 8.5–9.0，全部高于 8.4 门槛。
- 45 条 Canon 事实写入且冲突数为 0。
- 9 个 Chapter Context Packet、58 个 Wiki 引用和完整导出均被记录。
- 最终 `technical_passed=true`。

但人工审读仍发现：

| 错误 | 当前机制为何漏检 | 应有的约束 |
| --- | --- | --- |
| 第 2→3 章动作与时间回跳 | 开篇只做 900 字关键词命中 | 比较前章实际退出状态与本章实际进入状态 |
| 第 5→6 章重复访问苏葭 | 没有场景功能和信息增益比较 | 结构指纹相似且无新增代价时阻断 |
| 第 4 章没有合法录音，第 6 章却出现阿沅声纹记录 | 没有证据取得与保管链 | 证据必须有采集、持有、存储、可见性和效力历史 |
| “阿沅是贺征外甥女”被写成“阿沅失去了外甥女” | Canon 只比较模型主动写回的同 claim key | 从正文主动抽取关系断言并与有效关系边比较 |
| 苏葭住所出现档案馆通风结构 | 地点只是文本标签，没有空间资产状态 | 场景地点限定可用设施、物件和出入口 |
| 第 8 章凭空出现“五天前采集的苏葭证词” | Wiki 检索存在，但证据来源未建模 | 无来源证据不得进入当前状态 |
| 第 9 章临时出现手动降级校准 | 高潮机制没有前置注册门 | 解决主冲突的能力必须有前置展示或可证明的组合推导 |
| 模板句式和动作意象高频复用 | 中文正文使用 `text.split()` 检查重复 | 使用中文字符 n-gram、句法槽和场景解法指纹 |

这说明当前“状态机”主要控制工作流进度，没有控制故事世界；“质量门”主要判断产物形状和模型意见，没有验证叙事事实；“Wiki/RAG”证明检索发生过，却没有证明检索到了当前场景需要且允许知道的证据。

## 3. 产品决策与边界

### 3.1 本期必须做

- 建立叙事专用的时态世界状态，不用平面 Wiki 代替。
- 场景按 `before -> action -> actual delta -> after` 执行。
- 为事实、人物知识、时间、空间、物件、证据和机制建立硬门。
- 章节先临时提交，卷级审计后再正式写入 Canon/Wiki。
- 人工修订后按依赖图标记下游失效并重新验证。
- 用 Run I 真实失败和自动叙事变异校准评审器。
- 文学质量改用盲化成对偏好，不再让单一总分决定投稿质量。

### 3.2 本期不做

- 不新增第八个创作阶段。
- 不引入更多常驻 Agent 互相讨论。
- 不把第三方 AI 文本检测器当作质量目标。
- 不承诺“自动生成即可投稿”或“保证无法识别为 AI”。
- 不直接引入完整图数据库；先用版本化结构记录和索引验证收益。
- 不让硬门改写剧情。硬门只允许通过、要求定点修复或回退到已确认场景合同。

### 3.3 创意自由的保留方式

硬门约束“不能矛盾”，不规定“只能怎么写”。人物策略、细节选择、意象、对白潜台词和节奏仍由模型发散。新机制也不是一律禁止：如果它在高潮前出现，或能由已注册机制组合推导，并付出前文规定的代价，就允许进入正文。

## 4. Narrative World State

### 4.1 总体结构

```text
NarrativeWorldState
  schema_version
  committed_revision
  provisional_revision
  events[]
  epistemic_edges[]
  relationship_edges[]
  object_states[]
  location_states[]
  evidence_chains[]
  mechanism_registry[]
  promise_threads[]
  dependencies[]
  source_signatures[]
```

它不是另一份梗概。每一条状态都必须能回到正文或已确认 Artifact 的证据选区，并记录生效范围。

### 4.2 通用来源合同

```text
NarrativeEvidence
  source_kind              # confirmed_artifact / prose / author_edit
  source_id
  chapter_id
  scene_id
  version
  start_utf16
  end_utf16
  quote
  signature
  extractor_id
  confidence
```

硬冲突至少需要两份证据：一份建立旧状态，一份建立冲突的新断言。没有可定位原文的模型判断只能降级为软提示。

### 4.3 事件与双时间

```text
NarrativeEvent
  event_id
  event_type
  story_time               # 故事世界中发生的时间
  discourse_chapter        # 读者在哪一章看到
  reveal_chapter           # 信息在哪一章对读者成立
  participants[]
  location_id
  prerequisites[]
  effects[]
  caused_by[]
  valid_from
  valid_to
  evidence[]
  status                   # provisional / committed / superseded / disputed
```

`story_time` 与 `reveal_chapter` 必须分开。倒叙可以让事件发生时间早于当前章，但需要明确的叙述锚点；普通续写不能把当前动作无提示地退回过去。

### 4.4 人物知识边界

```text
EpistemicEdge
  character_id
  claim_id
  stance                   # knows / suspects / believes / conceals / misreads
  acquired_event_id
  acquired_chapter
  reveal_to_reader_chapter
  valid_from
  valid_to
  evidence[]
```

旁白可访问的信息还要受 POV 的叙事距离约束。检测不再依赖“知道、意识到”等动词，而是先抽取正文实际断言，再检查当前 POV 是否有取得路径。

### 4.5 证据保管链

```text
EvidenceChain
  evidence_id
  subject_claim_ids[]
  capture_method
  captured_at
  captured_by
  witnessed_by[]
  custody_events[]         # acquire / copy / transfer / store / destroy / disclose
  current_holder
  storage_location
  integrity_state
  visible_to[]
  admissibility            # none / disputed / internal / hearing_ready
  limitations[]
  evidence[]
```

正文如果声称“有录音、证词、报告或样本”，必须能追溯到创建或取得事件。仅在摘要或后续 Wiki 中出现的来源不能反向证明前文已经发生。

### 4.6 机制注册表

```text
MechanismSpec
  mechanism_id
  capability
  owner_or_operator
  introduced_chapter
  demonstrated_chapter
  availability
  cost
  limitations[]
  compatible_with[]
  invalidated_by[]
  evidence[]
```

高潮解决方案必须满足下列一项：

1. 已在前文展示过该能力；
2. 已在前文注册，当前首次完整使用；
3. 由两个以上已注册机制组合推导，并给出 `derivation_path`；
4. 属于已确认细纲明确批准的新例外。

否则标记为 `unearned_resolution` 并阻断，不能靠模型高分覆盖。

## 5. 场景事务

### 5.1 Scene State Transaction

```text
SceneStateTransaction
  transaction_id
  scene_contract_signature
  parent_state_signature
  before_state_ref
  planned_preconditions[]
  planned_delta[]
  prose_draft_id
  actual_assertions[]
  actual_delta[]
  invariant_results[]
  after_state_ref
  dependency_manifest[]
  status
```

场景的状态流转为：

```text
planned
  -> drafting
  -> state_extracted
  -> invariant_checking
  -> blocked | repairable | provisional
  -> chapter_provisional
  -> volume_committed
```

`planned_delta` 只表示细纲承诺，不能直接写入状态。只有正文中存在证据的 `actual_delta` 才能被下一场景消费。

### 5.2 实际退出状态优先

下一场景的上下文顺序固定为：

1. 上一场景的实际退出状态；
2. 当前有效 Canon 与临时覆盖层；
3. 当前 SceneContract；
4. 细纲中尚未实现的计划。

如果正文没有完成细纲动作，系统不能假装它已经完成。应先补写缺失桥段，或把下一场景标记为 `precondition_unsatisfied`。

### 5.3 风险自适应候选数

不对每场都机械生成三份候选。系统根据以下因素计算风险：

- 卷首、卷末、高潮或 POV 切换。
- 当前场景揭示多个秘密或改变关键关系。
- 涉及证据效力、世界机制或重要物件转移。
- 与近期场景结构相似。
- 状态图依赖边数量高。

低风险场景生成一个候选；中风险生成两个；高风险生成三个并进行盲化成对选择。这样把预算用在最容易破坏整书的地方。

## 6. 硬一致性门

### 6.1 运行顺序

每个硬门采用相同的四步协议：

1. 从候选正文提取类型化断言和原文选区。
2. 用确定性代码与当前有效状态比较。
3. 仅对语义含混项调用隔离验证器，要求返回成对证据和冲突类型。
4. 证据完整且置信度达到阈值才阻断；否则要求人工确认或记录软提示。

### 6.2 一票否决项

| 门 | 阻断条件 | Run I 对应问题 |
| --- | --- | --- |
| Fact Gate | 同一有效 claim 出现互斥值 | 外甥女关系反转 |
| Temporal Gate | 动作、时长或因果顺序不可能成立 | 第 2→3 章时间回跳 |
| Epistemic Gate | POV/人物无取得路径却使用秘密 | 姓名或隐藏事实提前泄漏 |
| Spatial Gate | 人物或物件无移动事件，或地点不具备该设施 | 住所出现档案馆通风结构 |
| Evidence Gate | 证据没有创建、取得或保管历史 | 凭空出现录音与五天前证词 |
| Mechanism Gate | 高潮能力未注册、未展示且不可组合推导 | 手动降级校准 |
| World Rule Gate | 新断言直接违背有效硬规则 | 制度与声纹规则被绕过 |
| Precondition Gate | 下一场景依赖的动作在正文中没有发生 | 用细纲计划替代实际结果 |

硬门不使用加权平均。一个高置信硬错误不能被语言质感 9 分抵消。

### 6.3 重复场景信息增益门

每个场景保存结构指纹：

```text
participants + location + goal + tactic + obstacle + result
+ revealed_claims + relationship_delta + paid_cost + mechanism_used
```

近期场景指纹高度相似，并且没有新增事实、关系变化、不可逆代价或策略升级时，标记为 `low_information_gain`。有意复现的镜像场景必须明确 `echo_intent`，并至少提供反转、对照或代价升级之一。

### 6.4 中文重复与模板味

替换 `text.split()`：

- 使用 4–12 字字符 n-gram 检查章内与跨章重复。
- 维护项目内句法槽计数，如“不是 X，是 Y”“他没有……只是……”。
- 单独统计身体动作、环境声响和章末钩子的复用。
- 比较“场景解决方式”，而不只比较字面句子。
- 把高频模式反馈给下一场景的 `originality_constraints`，但不机械禁词。

目标是减少可感知的机械写作，不是迎合不可靠的 AI 检测器。

## 7. 事务式 Canon

### 7.1 两层状态

```text
Committed Canon
  + Provisional Overlay（当前卷）
  = 下一章可读取的有效叙事状态
```

章节通过硬门后只写入当前卷的临时覆盖层。覆盖层能供后续章节检索，但不立即写入正式 Wiki/Canon。卷末执行全局审计：

- 所有事件顺序可满足。
- 人物知识取得路径闭合。
- 关键物件位置唯一且可追溯。
- 证据保管链连续。
- 本卷承诺有推进，回收项有正文证据。
- 卷末状态能够作为下一卷合法入口。

全部通过后，整卷事务一次提交；任一失败则保留前一正式版本，并将最小受影响场景标记为待修复。

### 7.2 为什么不能逐章立即正式写回

当前逐章写回会把后续才发现的错误变成“既成 Canon”。而且同一模型提取出的错误事实可能被 Wiki 再次检索，形成自证循环。临时覆盖层允许后章承接，又给卷级交叉检查留下回滚边界。

### 7.3 防止未来事实污染过去

所有检索必须带 `as_of_chapter` 和 `as_of_scene`。检索器只能返回该检查点已经发生或已向当前 POV 揭示的记录。`ingested_at` 不能替代 `story_time/reveal_chapter`。

## 8. 人工修订后的失效传播

### 8.1 依赖记录

每个派生产物保存：

```text
ArtifactDependency
  producer_id
  producer_signature
  consumer_id
  consumer_signature
  dependency_type          # hard / soft
  used_fields[]
  source_evidence_ids[]
```

### 8.2 修改第 N 章后的处理

系统不直接删除后文，也不假装后文仍然有效：

1. 当前章的质量报告、模型审校、状态提取和写回提案立即失效。
2. 从依赖图遍历所有 hard consumer，标记为 `stale`。
3. 重建第 N 章退出状态和第 N+1 章 Context Packet。
4. 重新验证后续章节；只要依赖仍满足，可以保留正文并更新签名。
5. 首个不满足前置条件的章节及其后续进入局部重写范围。
6. 当前卷临时 Canon、正式写回预览、质量汇总和导出全部失效。
7. 已正式提交的卷必须通过新分支修订，不在原版本上静默改写。

封面只有在其 Brief 实际依赖被修改的标题、主视觉或人物设定时才失效，避免无意义重生成。

## 9. 文学评审改造

### 9.1 硬错误与文学偏好分离

硬门只回答“是否自洽、是否有证据”；文学评审回答“哪个版本更值得读”。两者不能再混入一个总分。

### 9.2 盲化成对评审

- 候选稿随机标为 A/B，不提供生成模型、成本和修订次数。
- 同一对候选交换顺序再评一次；结论翻转则记为不确定。
- 评审输出胜者、具体证据、必须保留的强项和最小修订目标。
- 生成模型与评审模型优先使用不同模型家族；做不到时必须记录 `same_family_review=true` 并降低置信度。
- 评审主要维度为叙事推进、人物具体性、潜台词、细节选择、节奏和语言新鲜度。

### 9.3 不再信任裸分数

单模型 8.8 分只能作为诊断信号，不能作为正式门禁。系统必须先在项目自己的错误注入集上证明它能抓住已知错误，再允许参与生产决策。

## 10. 叙事变异测试

### 10.1 Run I 回归夹具

第一批至少固化以下九类真实失败，保存成最小原文对和预期冲突：

1. 相邻章时间回跳。
2. 重复访问同一人物且无信息增益。
3. 无采集行为却出现录音。
4. 亲属关系主客体反转。
5. 地点设施错置。
6. 无来源的历史证词。
7. 高潮临时新增解决机制。
8. POV 提前获得未揭示姓名或秘密。
9. 高频句式、动作和意象跨章复用。

### 10.2 自动变异集

从通过人工审读的短篇中自动注入：

- 数量、日期、地点、亲属关系和所有权替换。
- 删除证据取得事件但保留后续使用。
- 把角色知识提前一章。
- 调换因果事件顺序。
- 复制相邻场景并只改同义词。
- 删除物件转移后让它出现在新地点。
- 在高潮插入未注册能力。
- 删除伏笔投放但保留回收。
- 无锚点切换 POV、倒叙或跨日。
- 把已付出的代价恢复为初始状态。

评审器版本必须绑定变异集版本。新评审器抓不住旧版已知错误时不得部署。

### 10.3 初始退出指标

| 指标 | 退出线 |
| --- | --- |
| Run I 九类真实错误召回 | 100% |
| 高严重度自动变异召回 | ≥95% |
| 人工确认干净样本硬误报率 | ≤5% |
| 冲突证据可定位率 | 100% |
| A/B 顺序翻转率 | ≤5% |
| 项目内盲化偏好与人工一致率 | ≥75%，并报告样本数和置信区间 |
| 修改章节后的过期导出漏检 | 0 |

## 11. 与现有七阶段合同的关系

- Info、Summary、Outline、Detail 的用户产物合同不变。
- Detail 新增内部可编译字段时必须先更新 Artifact Schema，并在 UI 中保持为用户可理解的场景施工信息。
- Chapter Text 主体仍是正文编辑器；质量侧栏只显示当前阻断、成对证据、修复范围和 Canon 状态。
- Wiki 继续承担用户可浏览的事实账本；Narrative World State 是运行时验证结构，二者不合并。
- Cover 可以在正文完成前并行生成概念候选，但最终 Brief 依赖正式标题、主要人物与核心视觉状态；相关依赖改变时才标记待刷新。
- Export 必须要求不存在 stale 依赖、未解决硬冲突和未提交临时卷状态。

## 12. 事件与可观察性

新增 SSE 事件，旧客户端可忽略：

```text
scene_state_extracted
narrative_gate_failed
narrative_gate_cleared
chapter_provisional
volume_audit_started
volume_audit_failed
canon_volume_committed
downstream_invalidated
downstream_revalidated
```

每个失败事件包含 `gate_id`、`chapter`、`scene_id`、证据 ID、最小修复范围和是否允许自动定点修复。不得把内部整份状态图或原始 JSON 直接推给 UI。

## 13. 后端模块边界

按现有领域目录扩展，不把业务逻辑放进 `api/routes`：

```text
src/novel_workflow/literary/
  narrative_state_schemas.py   # 类型合同
  state_assertion_extractor.py # 正文 -> 类型化断言
  scene_state_transition.py    # 纯 before/delta/after reducer

src/novel_workflow/memory/
  narrative_world_state.py     # 版本、覆盖层、as-of 查询
  narrative_retrieval.py       # 章节安全的混合检索包

src/novel_workflow/quality/
  narrative_invariants.py      # 硬门编排
  evidence_chain.py            # 证据保管链检查
  mechanism_registry.py        # 机制前置与组合推导
  scene_information_gain.py    # 场景结构指纹
  chinese_repetition.py        # 中文 n-gram 与句法槽

src/novel_workflow/orchestration/
  scene_transaction.py         # 场景事务执行
  volume_canon_commit.py       # 卷级审计与两阶段提交
  artifact_invalidation.py     # 依赖图与失效传播

src/novel_workflow/acceptance/
  narrative_mutations.py       # 自动错误注入
  evaluator_calibration.py     # 评审器资格与指标
  narrative_acceptance.py      # 新整书退出门
```

正常模块目标保持 200–250 行；提取、比较、持久化和编排不进入同一文件。

## 14. 数据迁移与兼容

- `ChapterContextPacket.schema_version` 升为 3，旧 v2 字段全部保留。
- `NarrativeWorldState` 从 v1 起独立版本化，新字段都提供空默认值。
- 现有 Run 只读可浏览，不把旧 Wiki 自动提升为已验证 Canon。
- 旧 Run 继续导出时标记 `legacy_unverified_narrative_state`，需要显式重审后才能获得新验收状态。
- 原有 API 路由和七阶段 Artifact key 不改；新事件与字段采用向后兼容追加。
- Demo/provider 不可用时仍可展示流程，但硬门状态必须明确为 `degraded_unverified`，不能显示“质量通过”。

## 15. 实施波次

### Wave 17.0：先让旧系统失败

- [x] 固化 Run I 九类错误夹具和十类自动变异。
- [x] 增加四组人工确认的干净对照样本。
- [x] 证明当前质量门会漏检这些错误，并保存基线报告。

退出：测试可以稳定复现“旧系统误通过”，且不调用真实正文生成。

实施证据（2026-08-01）：旧门在 19 个问题样本中仅有 5 个进入现有检测器，
14 个样本明确标记为不支持；最终召回率为 `0.0`，4 个干净对照无误报。
基线通过语料 SHA-256 冻结，任何样本或旧门行为变化都会使资格测试失败。

### Wave 17.1：世界状态与场景事务

- [x] 落地 Narrative World State、证据来源和场景状态事务的纯类型合同。
- [x] 事务只把绑定当前正文草稿或作者修订证据的实际断言写入临时层。
- [x] 加入父状态签名、事务幂等、同 ID 内容冲突拒绝和阻断门保护。
- [x] 加入临时覆盖层与 `as_of_chapter/scene` 纯查询，拒绝未来章/场景事实。

退出：时间、人物知识、物件位置和关系变化能跨场景追溯到正文证据。

当前边界（2026-08-01）：纯 reducer 和时态查询已经满足上述可追溯合同，
定向资格/状态测试与正文编排测试均已通过；旧 Run 仍不得被自动提升为新叙事验收通过。

### Wave 17.2：第一批硬门

- [x] Fact、Temporal、Epistemic、Spatial、Evidence、Mechanism、Precondition 与 World Rule 纯硬门。
- [x] 中文 4–12 字 n-gram/句法槽联合重复门和结构化场景信息增益门。
- [x] 结构化断言候选的正文签名、UTF-16 选区、quote 与草稿来源绑定。
- [x] `blocked/repairable/provisional` 资格结果接入场景状态 reducer；阻断不可被平均分覆盖。
- [x] 接入正文十步编排、真实 Provider 抽取、SSE 和运行态持久化。

退出：Run I 九类错误全部被正确拦截，干净样本误报率达标。

资格证据（2026-08-01）：独立金标准覆盖 Run I 9 个真实失败、10 个项目变异和
4 个干净对照；Run I 召回 `100%`、变异召回 `100%`、硬误报率 `0%`、成对原文
证据定位率 `100%`。结果与源语料/标注双 SHA-256 冻结。该结论只证明类型化状态
上的门规则已资格通过；真实模型能否稳定抽取正确断言，仍必须在整书 Run II 中另做
抽取准确率验收，当前不得显示为生产质量已通过。

正文接线证据（2026-08-01）：`chapter_text` 在步骤 7 质量审计后调用同一 Provider
路由的结构化 `narrative_state_extraction` 任务；每个场景必须覆盖并绑定 UTF-16 原文
证据，事务通过后才写入 `NarrativeWorldState.provisional_assertions`。新增
`scene_state_extracted`、`narrative_gate_failed`、`narrative_gate_cleared`、
`chapter_provisional` 事件均通过 `RunStore.commit_state_events()` 与运行状态原子落盘。
章节结算前再次拒绝过期或非 provisional 状态，因此硬门失败不会发出 `chapter_settled`、
`node_completed`，也不会进入正式 Canon/Wiki 写回。没有新提取能力的 demo/mock Provider
明确标记 `degraded_unverified`，只为兼容演示，不得被当作生产质量通过。定向编排测试
覆盖 provisional 成功和事实冲突阻断；全量后端回归为 `574 passed, 1 skipped`。

### Wave 17.2P：Prompt 身份、认知与受约束创作自由

- [x] 为 Info、Summary、Outline、Detail、Text、Cover 和 Export 建立阶段专属专业身份，不再使用通用“AI 写手”角色。
- [x] 每个身份明确当前判断任务、权威来源顺序、已知与未知边界；低优先级参考不能覆盖已确认 Artifact、Canon 或硬规则。
- [x] 将硬边界与创作自由分开表达。正文在不改变既定事实、因果、知识边界和 SceneContract 结果的前提下，开放感官、微动作、对白、潜台词、局部策略、节奏、意象和沉默。
- [x] Info 允许把留白发展为明确的新建约束；后续阶段信息不足时必须保持未知或在检查字段中指出，不能擅自补成既定事实。
- [x] 章后事实抽取、叙事状态提取、模型评审、整章修订、定点补丁和选区精修共享同一契约语法，但按任务关闭或缩小创作自由。
- [x] 独立文学任务通过真实 `system/user` 消息边界发送；结构化任务继续保留 JSON 关键词、字段示例、Provider `response_format` 适配与本地合同校验。
- [x] 单个身份契约限制在约 300–520 字，放在 system 层，不占用章节 `16,000` 字 user 上下文预算，也不改变 L5 -> L4 -> L3 的裁剪顺序。
- [x] 默认工作流升级为 `1.2.2-prompt-identity`，新增 `literary_phase_17_2p_manifest.json`；Phase 16.1 及更早基线保持冻结。
- [x] 新增六种只读叙事角色：故事建筑师、现场观察者、心理戏剧家、悬念导演、群像编年者、意象织造者。角色只改变观察、取舍与表达策略，不改变 Artifact、Canon、人物知识边界、SceneContract 或用户明确要求。
- [x] 角色在 Info 配置中单选；前端展示与后端执行段落逐字对齐，允许查看完整角色 Prompt，但不开放自由编辑、混合角色或按阶段临时覆盖。
- [x] 未选择角色的旧 Run 不注入新段落，因此冻结文学 Prompt 基线不漂移；未知角色在 Provider 调用前拒绝。

回归证据（2026-08-02）：`tests/test_prompt_identity.py` 覆盖所有阶段和独立任务的
身份、认知、权威来源、未知处理、执行边界、创作自由与静默自检；现有 Prompt 快照、
正文纯文本、结构化 JSON、上下文裁剪、章后处理、叙事提取、模型评审和修订测试继续作为
兼容门。该波次只证明 Prompt 编译与 Provider 请求合同已经收敛；正文质量改善幅度仍须在
Wave 17.5 的全新整书 Run II 中通过抽取准确率、硬错误、盲化偏好和人工冷编辑共同验证。
本轮全量回归为后端 `579 passed, 1 skipped`、前端 `497 passed`，前端生产构建、JSON
解析、工作流镜像一致性、Python 编译与 `git diff --check` 均通过。

叙事角色证据（2026-08-02）：后端角色合同、阶段 Prompt 注入和未知角色拒绝测试通过；前端
角色选择器测试确认六个选项、只读 Prompt、单一 Tab 停靠点和键盘方向键语义。Playwright
在 1440×1000、1280×800、390×844、320×720 四档视口验证无横向溢出，窄屏自动单列，展开的
角色 Prompt 保持内部滚动；实际选择“现场观察者”和 ArrowDown 切换均正确更新选中态，浏览器
控制台无错误。该证据证明配置体验和 Prompt 接线成立，不代表整书文学质量已通过。

恢复一致性补强证据（2026-08-02）：服务端 `run.json` 的原始 `inputs` 现在进入前端恢复合同，
与已保存 `workflow` 一起作为运行时事实读取；真实 SSE 重连继续只由服务端 Run State 驱动，
不会用当前工作流默认值覆盖已创建 Run。浏览器本地恢复快照也保存并结构校验 `RunInputs`，
服务端不可达时仍能保留用户选择的叙事角色和阶段配置；撤销“重置运行”复用同一快照。缺少
`inputs` 的旧快照仍按兼容路径恢复，不伪造角色选择，也不改变旧 Prompt 基线。新增前端状态
回归覆盖服务端输入读取、缓存恢复、损坏输入拒绝和项目隔离；生产构建通过。

### Wave 17.3：事务式 Canon 与失效传播

- [x] 章节临时提交、卷级审计和正式 Canon 提交。
- [x] 人工修订后的依赖遍历、重新验证与最小重写范围。
- [x] 导出和正式写回拒绝 stale 依赖。

退出：修改第 N 章后，不可能继续使用旧 Review、旧 Canon 或旧导出。

实施证据（2026-08-02）：`NarrativeWorldState` 增加幂等 `volume_commits`，卷审计同时验证
章节正文签名、场景事务、临时覆盖层、同场景互斥事实以及按章节顺序模拟后的 Canon 冲突。
审计失败不修改正式层；通过后把选定临时断言一次迁移到 committed 层。Fast/Balanced 在卷末
自动提交，Deep 只保存 `prepared` 审计，正文阶段人工定稿后再次按当前 Canon 复审再提交，
避免“当前稿”提前写入正式 Wiki/Canon。提交开始、失败、完成均与 Run State 一起落盘，
中断后可按相同审计签名重放，重复提交不增加 revision 或重复事实。

派生产物现在保存 hard/soft 依赖边：Chapter、Context、Narrative Verification、Review、
Volume Canon、Cover 和 Export 均有来源签名。局部修订与历史恢复保留正文，但把当前章及
下游 Context、Review、临时事务、Canon 投影和 Export 标记 stale；后续章以保留正文重新
验证，首个不满足硬门的章节停止并进入最小修复范围。已提交卷不在原版本静默改写，而是
建立可追溯的 `branch_active` Canon 修订分支：旧卷提交和断言保存在分支档案中，但立即退出
活动 Narrative World State；旧章节 Wiki 引用同步 stale，后续模型检索只能读取当前活动引用。
旧章节摘要、时间线、张力、人物变化、世界观影响与伏笔状态等正式派生投影一并进入分支档案，
从活动 Story Bible/运行投影中撤出，避免绕过 Canon/Wiki 重新污染上下文。替代卷重新审计
提交后逐卷结算分支，全部替代完成才恢复导出资格。封面仅有软依赖时不因普通
章节措辞修改而重生成。正式导出同时拒绝
stale hard dependency、未解决叙事验证和未提交卷；旧 Run 仍可兼容导出，但明确为
`legacy_unverified_narrative_state` 语义，不获得事务式叙事验收资格。

Wiki 文件不再参与 Run State 之前的副作用写入。卷提交先把 Canon、运行状态、提交事件和
`wiki_writeback_outbox` 一次原子落盘，再按稳定文档键投影到 Wiki；写文件前中断不会产生
可检索的孤儿文档，写文件中断则保留 pending outbox，并在恢复、卷重放或下次上下文检索前
幂等补投。磁盘上保留的旧分支文件不计入活动 Wiki 状态，也不能绕过活动引用集合进入 RAG。
outbox 在投影成功或取消后清空正文载荷，只保留操作身份、元数据和结果引用，避免 Run State
随章节数重复保存整章正文。

回归证据（2026-08-02）：新增 Run State 提交前故障、Wiki 投影中断/重放、旧 Canon 不可见、
旧 Wiki 不可检索、替代卷结算与导出重新放行测试。全量后端为 `600 passed, 1 skipped`，
前端为 `497 passed`；前端生产构建、首屏 CSS 分包（gzip `31.9 KiB`）、Python 编译、JSON
解析和 `git diff --check` 均通过。构建仍只有既有 `graph-3d-vendor` 大分包警告。

### Wave 17.4：冷编辑与偏好评审

- [x] 平衡模式仅在用户启用版本比对后按风险生成 1–3 个候选，并执行匿名正反顺序成对评审。
- [x] 冷编辑先保留强项，再生成绑定章节版本、正文签名和 Artifact 签名的 UTF-16 定点修订目标；建议不自动改稿。
- [x] 顺序翻转标记不确定，同模型家族评审置信度乘以 `0.7`，未选候选正文不进入 Chapter、Memory、Wiki、Canon 或 Story Bible。
- [x] 模型综合分与主观语声漂移降为非门禁诊断；只有细纲/场景承诺与叙事状态硬冲突继续阻断。
- [x] 前端冷编辑进入正文既有“质量审校”页签，复用定点候选链路；旧 Run 缺失态和 Provider 不可用态均不伪造结论。
- [ ] 用项目内人工偏好样本完成 Wilson 区间校准，并证明一致率与顺序稳定性达到退出线。

退出：项目内人工偏好一致率和顺序稳定性达标。

工程证据（2026-08-02）：冷编辑、风险预算、盲化配对、正反顺序复评、同源降置信度、
状态持久化、恢复失效和 SSE 已接入正文提交前链路。隔离测试证明中风险章只生成两个候选，
每对候选执行两次评审，只有选中稿进入下游；Emoji 前缀下 UTF-16 定位保持正确，冷编辑
建议不会修改正文。上述证据只证明机制与隔离边界成立，不替代真实人工偏好校准。

校准工具证据（2026-08-02）：已新增独立的本地盲样本导出、三候选成对标签、
人工答卷保护、样本签名防篡改、同源/跨源分层与 95% Wilson 报告。退出门同时
要求全量已审、一致率下界不低于 75% 且顺序翻转率上界不高于 5%。真实人工
答卷仍未完成，本 Wave 不打勾。具体执行见
[人工偏好校准协议](./preference-calibration-protocol.md)。
新增校准回归后全量验证为后端 `638 passed, 1 skipped`、前端 `128 files / 503 passed`；
生产构建、CSS 审计、首屏 CSS 分包（gzip `31.9 KiB`）、Python 编译、锁文件、
目录边界和 `git diff --check` 均通过。构建仍只有既有 `graph-3d-vendor` 大分包警告。
本地共扫描 126 个现有 Run 快照，其中可导出的真实成对偏好样本为 0；因此没有用
测试夹具或单候选旧 Run 伪造人工校准结论。

真实 Pilot 证据（2026-08-02，Run B `phase17-preference-pilot-20260802-b`）：Info 已冻结
7 人唯一名册并形成 13 条合法关系；Summary、Outline 通过；Detail 的 9 个逐章批次全部
持久化，恢复时 9 批全部复用，只对第 7、8 章共 4 个错误世界观引用执行一次白名单补丁。
随后实际生成 9 章、每章 3 份候选，共 27 份隔离草稿与 27 组成对盲样本；Text 候选没有
进入正式 Chapter Artifact，Memory/Wiki/Canon/Story Bible 写回计数与 Text 启动基线一致。

本次 Pilot **尚未技术通过，且不能原地恢复**。复检发现 27 份候选全部超过存档中的
`1600-2400` 字符合同，范围为 `2556-4900`、均值 `3780.3`；24 份候选的正文首行还被
`chapter_content()` 重新注入了章节标题。场景原始草稿与 Artifact 内容是纯正文，污染发生在
候选组装层；旧质量引擎也会以章节长度、禁用语或对白比例拒绝全部 27 份候选。即使换入
可用 Judge，这批语料也不能用于人工偏好校准。

独立 Judge 的 27 组评审同时全部为 `unavailable`：GLM 的 forward 首次调用均在推理前失败，
没有任何 reversed pass。已保留 Provider 失败审计与 `all_pairwise_reviews_available` 硬门，
但原“复用 Run B 候选补跑 Judge”方案现已作废。正文标题与 `content` 已集中分层，逐场生成
同时修复过短和过长输出；Pilot 新增 `candidate_length_contract` 与
`candidate_prose_envelope_clean`，旧 Run 在 Provider 检查和 Judge 调用前即被拒绝。
Run B 保持失败证据，不改写、不重签；后续必须使用新 Run ID 创建 Run C。人工答卷继续为空，
模型不得代填。

Run C 前置闸门进一步下沉到逐章编排：内部校准每生成一批 3 份候选，先检查数量、章节预算
与正文信封，再允许进入盲化 Judge；失败产生 `preference_candidate_contract_failed`，并以
`calibration_candidate_contract` 非重试错误结束当前 Run。该门禁不改变普通正文多候选选择。
本地 DeepSeek、GLM、MiMo 均存在配置或密钥记录，但 GLM/MiMo 尚无独立文学 Judge 成功证据，
因此 Run C 仍未创建，也未发生新的外部模型调用。

独立 Judge 烟测证据（2026-08-02）：新增 `judge-smoke` 一次性测试作用域，对匿名强/弱
候选执行 forward/reversed 两次评审，校验合法 JSON、候选顺序归一化、结果稳定性以及
Writer/Judge Provider 隔离。GLM 烟测在首次推理前以 `insufficient_balance` 失败，未调用
reversed，也未触碰 Run B；MiMo Coding Plan 的用途合同不允许将其当作文学 Judge；DeepSeek
当前只作为 Writer，不能满足独立 Judge 条件。因此 `ok=false` 是真实可用性证据，不能用工程
测试替代，Run C 继续保持“未创建”。

Judge 创建前闸门证据（2026-08-03）：使用当前已保存 GLM 5.2 配置重新执行最低预算
forward/reversed 烟测，仍在首次推理前返回 `insufficient_balance`，没有 reversed 调用、
没有创建 Run C。进一步审计发现 Pilot CLI 过去只在文档层要求先烟测，函数本身仍可能先
进入 Writer 链路；现已把 `judge-smoke` 下沉为 `run_preference_calibration_pilot()` 的强制
前置闸门。Judge 不可用、输出无效或顺序不稳定时，系统在 Provider readiness、Writer 调用
和 Run 创建前停止，并保留公开错误码。定向测试锁定“Judge 失败时 Writer 零调用、Run 文件
不存在”；该改动只防止无效消耗，不把独立 Judge 或人工偏好门伪造为通过。

### Wave 17.5：真实整书 Run II

- 使用新 Run ID，从 Info 开始走完整链路。
- 先自动验收，再进行逐章人工冷编辑和盲化对比。
- 与 Run I 比较硬错误数、人工修订量、重复模式和读者偏好。

退出：不得只报告“技术通过”；必须同时给出硬一致性、评审校准、人工偏好和尚未解决问题。

三章真实检查点（2026-08-03，Run `phase17-deepseek-three-chapter-20260803-c`）：
DeepSeek 真实链路完成 Info -> Summary -> Outline -> Detail -> Text，生成 1 卷 3 章，正文
`3205 / 3016 / 3059` 字，总计 `9280` 字；18 条 Canon 完成卷级事务提交，25 条
Wiki/RAG 引用进入活动状态，三章叙事验证均为 `provisional`。自动报告为
`technical_passed=true`、`submission_readiness=needs_author_review`。这只证明检查点链路、
结构合同、证据定位、恢复与正式写回可运行。

逐章全文与五阶段 Artifact 人工复核给出 `58/100`，结论为**人工文学未通过**。主要硬伤不是
措辞分数，而是上游约束传递和故事因果：权限“已暂停”与 24 小时剩余访问语义冲突；出海前
已经刻好的贝壳手链却播放风暴现场遗言，物证时间链不可能成立；终章只发出委员会通知，未
实际兑现 Summary/Outline 已确认的投票、公开、职位代价、秦望辞职与系统重建。苏亦舟交出
最高权限、陆衍弃枪和秦望退场均缺少足够的前置选择与代价，高潮表现为连续便利事件。完整
审读证据保存在 Run-local
`acceptance/manual-literary-review.md`；该 Run 作为失败样本保留，不修改、不重签。

机制复盘还定位到两个系统性漏口。第一，Summary/Outline/Detail 会把规划中的未来弧线写入
人物图 `status`，旧 Chapter Context Packet 又把该字段作为“当前人物状态”发给第 1 章，
导致模型提前知道陆衍最终倒戈等结果。现在人物上下文只投影稳定身份字段和已提交前章变化。
第二，旧正文上下文没有渲染 `summary` 字段，模型审校也主要核对 Detail，因而“委员会通知”
被错误视作终章结算。现在上下文加入精简 Summary 承诺；终章把
`ending_resolution + volume resolution` 加入受保护合同，并明确“已通知/将召开/准备处理”
不能作为实际兑现。自动报告继续保留兼容的 `passed` 字段，同时新增 `score_target_met` 与
`gate_policy=contract_completion_and_pov_only; literary_score_diagnostic`，解释本次
`8.0 / 8.0 / 7.8` 低于 `8.4` 仍合同通过的原因，避免把诊断分伪装成硬门。

默认工作流因此升级为 `1.2.3-upstream-closure`，新增
`literary_phase_17_5_manifest.json`；`1.2.2-prompt-identity` 与更早 Prompt 基线继续冻结，
不以覆盖旧指纹的方式掩盖本轮上下文变化。

上述修复的定向回归为 `73 passed`，并用本 Run 快照重建 Context Packet：第 1 章不再包含
任何未来人物状态，终章能够看到必须实际兑现的 Summary/Outline 结算合同。它们尚未经过新
Provider Run 验证，因此 Wave 17.5 不打勾；下一次必须使用新 Run ID，先生成三章检查物证
时间链、权限状态、终章结算和人物转向，再决定是否扩展到完整 Run II。

最终工程回归（2026-08-03）：后端全量 `700 passed, 1 skipped`，前端全量
`129 files / 506 passed`，前端生产构建与 Python 编译通过。该结果只证明当前代码、冻结
Prompt 基线和前后端工作流镜像没有工程回归，不改变本 Run `58/100`、人工文学未通过与
`needs_author_review` 的结论。

### Wave 17.6：Token 节俭质量修订

三章失败样本还暴露出成本策略问题：默认正文节点虽然已有局部补丁能力，但没有启用，Deep
模式在质量不达标时会自动执行最多两次整章修订；场景长度修复也允许连续两次完整场景调用。
这种策略既可能破坏已成立内容，也会把“提高质量”错误等同为“增加调用次数”。

现在默认正文质量修订固定为一次 `1-4 edits` 局部补丁，完整原稿始终作为基线保留；补丁
Provider 的输出上限为 `1200 tokens`，Deep 不再获得第二次自动修订额度。补丁格式无效、
审校指标退化或复检仍失败时立即转人工处理，不自动重试。逐场长度越界也只允许一次定向
扩写或压缩，并依据场景预算缩小 `max_tokens`。用户明确点击“换一稿”仍走独立候选链路，
不与自动质量补丁共享语义。

该机制只减少无效调用并保护已有正文，不把“调用更少”视为文学质量通过。下一次新 Run
仍需三章人工审读；只有物证时间链、权限状态、终章兑现和人物选择都成立后才能扩展整书。

### Wave 17.7：风险路由审稿与并发隔离

固定增加审稿 Agent 不是正确的质量策略。审稿者数量必须由本地状态机依据章节风险决定，
而且任何文学软分歧都不能靠第三个模型投票来“解决”。模式能力固定为：Fast 只运行零 Token
确定性门与叙事状态门；Balanced 每章运行一个语义/衔接审稿者，只有高风险章才增加独立冷
编辑；Deep 低风险章同样只有一个语义审稿者，中高风险章最多增加一个冷编辑。偏好 Judge
只属于用户主动版本比较或内部校准，不进入 Deep 默认主链。

本轮已完成三项成本与隔离修正：

- [x] 章后结构化抽取移到质量修订之后，只对最终正文执行一次；自动补丁不再造成前后两次
  Summary/Wiki/人物/伏笔抽取。
- [x] 新增纯 `reviewer_policy`，让 Balanced 低/中风险章和 Deep 低风险章跳过冷编辑调用；
  Fast 继续保持零模型审稿。
- [x] 人工局部修订只同步当前已选候选；未选候选正文和 Artifact 保持原样，继续与 Chapter、
  Memory、Wiki、Canon、Story Bible 隔离。
- [x] 建立不可变 `ReviewInputSnapshot`，在启动任务前串行预留每名审稿者的预算与幂等键。
- [x] 审稿任务只返回纯结果，不直接修改 `budget_state`、Run State 或事件队列；协调器等待同章
  最多两个结果后执行一次确定性合并和一次状态写入。
- [x] 完成上述隔离后，Deep 中高风险章才允许语义审稿与冷编辑并行。第 N+1 章正文永远等待
  第 N 章最终摘要、临时叙事事务和卷内 Canon 覆盖层稳定，禁止跨章抢跑。

并发的目标是缩短同章审读等待，不是增加调用。任一审稿者不可用、两者证据冲突、目标无法
唯一定位或补丁复检仍失败时，保留当前稿并转人工；不得补开第三名审稿者，也不得自动整章
重写。

实现收口（2026-08-03）：`ReviewInputSnapshot` 冻结正文版本、Artifact、Context Packet、
Scene Contract、风险和候选预算；主调用预算在任务启动前串行预留，语义审稿与冷编辑任务只
读取冻结输入并返回结果，预算事件按 `review_snapshot_id` 隔离，协调器使用 Run revision CAS
统一结算。正文或上下文在等待期间变化时，迟到结果丢弃且不能覆盖作者新稿。Deep 双审主
调用失败时只对 Provider 策略明确允许的超时、限流、网络和服务故障启用同角色备用链；JSON/
合同错误不切换 Provider，未知计费按预测 Token 保守结算，备用链不会产生第三审稿角色。

正文主动换稿也完成章级隔离：请求必须显式指定 `chapter_id`，Provider 只读取目标章和必要
上下文；候选绑定请求、原 Artifact 签名和 Run revision。用户选中后只替换目标章并清空该章
旧摘要、质量、审稿和叙事派生状态，其他章节逐字保留，未选候选继续隔离于 Chapter、Memory、
Wiki、Canon 与 Story Bible 之外。

### Wave 17.8：模式化审稿编排与真实失败回灌

用户提出“高档模式由多个子 Agent 并行审稿”的方向是合理的，但产品不能把 Agent 数量本身
当成质量。当前正式合同以本地风险状态机决定职责和成本：

| 模式 | 审稿能力 | 自动修订 | 失败边界 |
| --- | --- | --- | --- |
| Fast | 只运行零 Token 确定性门与叙事状态门 | 0 次 | 保留警告继续，不调用审稿模型 |
| Balanced | 每章 1 名语义/衔接审稿者；高风险章在质量门后顺序追加 1 名独立冷编辑 | 最多 1 次局部补丁 | 冷编辑只给证据与定位建议，不以文学偏好阻断 |
| Deep | 低风险章 1 名语义审稿者；中高风险章由语义审稿者与 1 名动态专业角色并行 | 最多 1 次、1-4 处句段 | 硬合同补丁后原两角色各复检 1 次；纯文风补丁只做语义复检；仍失败转人工，禁止第三角色 |

Deep 的第二角色不是固定“多一个 Judge”，而是根据受保护上下文选择：普通文风使用独立冷
编辑；时间、权限、身份、物件和机制密集章使用因果事实审稿；卷末与终章使用结算兑现审稿。
所有角色共享同一不可变 `ReviewInputSnapshot`，预算和幂等键在调用前串行预留；并行任务只读，
主协调器统一提交。候选生成仍是用户主动能力，不会因为审稿角色增加而偷偷多生成正文。

真实失败样本 `wave17-8-compact-three-chapter-20260803-b1` 完成 3 章 8138 字，消耗 72583 tokens，
自动状态为 `technical_passed=true`，人工文学评审只有 `62/100`。它暴露出四类旧门禁漏口：
档案编号三月与事故八月冲突；母亲称呼“阿涧/小涧”漂移且陆衍也使用；把 0.3 秒夸大为浪越堤、
船撞礁的灾难因果；终章用广播、后退、磁头归位和守则落地替代问责、停机检修、手动预警和
守则销毁。完整证据保存在该 Run 的 `acceptance/manual-literary-review.md`，旧 Run 不恢复、不
重签、不改写。

上述问题现已成为 `wave17_8_editorial_regressions.json` 的真实语料回归。专业硬审计只有在缺失
项可绑定上游合同，或因果事实冲突具备正文逐字双证据时才可阻断；文学总分、偏好或不可定位
意见仍只作诊断。前端审校页同步显示真实角色、合同兑现比例、缺失要求、正文证据与原因，不再
把因果事实审稿和终章兑现审稿笼统显示为“冷编辑”。

质量循环集成回归进一步锁定：硬缺失只创建一次局部补丁指令；补丁后只复检语义角色与原专业
角色；仍缺失时只产生一次人工接管，不调用第三角色。该边界的目标是用最少的模型调用修复可
验证问题，而不是靠反复重写购买一个更高分数。

预算与缓存收口（2026-08-03）：Deep 章节预算只为专业角色预留“冻结稿首审 + 唯一局部补丁后
复检”两次容量，协调器在第二次之后直接拒绝继续调用；显式用户 Token 上限仍优先，不能用自动
扩容绕过。Balanced 的串行冷编辑缓存同时绑定正文、上下文、角色、审稿焦点和合同版本，旧合同
或上下文变化必须重新审稿，不得仅凭正文签名复用。这里增加的是既定能力的正确预算与缓存隔离，
不是增加重试次数，也不会把冷编辑建议升级为自动改写许可。

可信审批与稳定合同收口（2026-08-03）：Chapter Artifact 中的 `model_review`、
`editorial_pass` 和 `review_coordination` 只是展示副本，正式审批必须与服务端
`model_review_state`、`editorial_review_state`、`chapter_review_state` 对账；客户端自行构造
公开哈希、角色名或完成状态不能通过。Context Packet 或 Scene Contract 显式标记 stale 时，
即使正文签名未变也必须重新审稿。

协调器在模型调用前把 Context Packet 与 Scene Contract 编译为最多 16 条稳定审稿合同，ID 由
字段路径和冻结值共同生成。两名审稿者只能回传目录中的 `contract_id`；旧格式仅在 requirement
与目录唯一逐字匹配时兼容绑定，未知 ID、同义改写和自造要求不进入硬门。冲突检测按稳定 ID
连接，不再依赖去标点后的自然语言相等。每条硬合同未被逐项回传时按 missing 处理，避免模型
通过省略困难条目伪造满覆盖。Provider 启动事件只记录 `billing_status=pending`，最终成功、
推理前拒绝或未知计费由结算事件给出，避免一次调用同时出现互相矛盾的 billed 状态。

下一次真实验收必须使用新 Run ID。先完成新的三章 DeepSeek 小流量检查点并人工审读；只有
日期、称呼、机制因果、终章兑现、人物代价和重复意象同时改善，才允许扩展为整书 Run II。

### Wave 17.9：证据裁决与零重生成恢复

真实 Run `wave17-9-adaptive-review-three-chapter-20260803-c1` 暴露出审稿编排的恢复事故：第 1 章
已经形成 2597 字 `prose_ready` 正文，语意主审把“陈默删除录音后林潮音转而联系苏晚”概括为
人物关系变化的触发证据；因果专审因该句不是正文逐字引用而标记 missing。旧协调器只比较
`direct/missing` 标签，将证据绑定失败误判为硬冲突；第三次验收恢复又把人工裁决态误判为正文
尾部损坏，归档原作用域并重新生成了第 1 章。

本轮把 Agent 编排固定为职责图而不是投票池：

| 角色 | 启动条件 | 并发与成本 | 输出权限 |
| --- | --- | --- | --- |
| 语意/衔接主审 | Balanced/Deep 每章 | 单次；Deep 风险章可与专项角色并行 | 逐项合同状态、逐字证据、局部修订方向 |
| 独立冷编辑 | Balanced 高风险；Deep 普通中高风险 | Balanced 顺序、Deep 并行 | 文学诊断与可定位建议，不拥有硬事实真值 |
| 因果事实审稿 | Deep 时间、权限、物证、机制密集章 | 与主审共享冻结快照并行 | 只审所属的最多 6 条硬合同 |
| 终章兑现审稿 | Deep 卷末/终章 | 与主审共享冻结快照并行 | 只审结局承诺、卷目标、未决行动与末场交接 |
| 偏好 Judge | 用户主动版本比较或发布前校准 | 不进入默认正文主链 | 盲化偏好，不阻断硬门 |

协调结果新增严格分流：双方结论相反且双方证据都能在冻结正文逐字定位时才是 `conflicted`；
任一证据无法绑定时是 `verification_required`。前者等待人工解释同一文本为何支持相反结论，
后者只允许一次原角色证据复核或人工核验。两者都不是正文缺陷证明，因此禁止启动自动补丁、
第三角色、整章重写或尾部恢复。

验收恢复现在对上述状态返回幂等 `chapter_review_adjudication_required`：保留当前章节、审稿结果、
generation 次数和全部用量历史，不归档作用域、不进入下一章。当前 C1 Run 暂停在这一人工裁决
边界，不把定向测试通过描述为三章真实验收完成；只有裁决当前稿后才决定是否执行一次原角色
证据复核。

### Wave 17.10：原角色证据复核与量表防错

`verification_required` 不再是只能安全停住的终点。新增
`POST /api/runs/{run_id}/chapters/{chapter_id}/review-evidence-recheck` 领域命令，要求客户端
同时提交当前 `review_snapshot_id`、正文 `content_signature`、上下文 `context_signature` 和原始
`reviewer_roles`；服务端以 Run State revision 做 CAS 校验，拒绝过期快照、角色漂移和重复复核。

复核只针对 `evidence_binding_failures.unbound_roles` 开放一次额度：语意主审对应
`model_review`，专项审稿对应 `cold_edit`；未受影响的角色继续复用缓存。命令会把运行置于
`checkpoint_recovery`，保留正文、generation attempts、旧报告和用量历史；`review_generation`、
`evidence_recheck_count`、`initial_reviewer_roles` 与复核来源签名持久化在
`chapter_review_state`，进程重启后不会重新路由或偷偷增加角色。`conflicted` 仍不允许该命令，
必须由作者人工解释同一证据的相反结论。

审稿输出合同从 `3-stable-review-contracts` 升级为 `4-explicit-ten-point-scale`：模型必须返回
`score_scale="0-10"`，并遵守 6/8/9 分锚点。若所有分数都落在 0-1 且结论全为正向，结果标记为
量表无效并只触发原审稿复核；系统不会把 1.0 静默乘十，也不会以此重写正文。

本 Wave 的产品能力因此固定为有限 Adaptive Review Mesh：Fast 零模型审稿，Balanced 默认单主审、
高风险串行冷读，Deep 中高风险最多两名冻结稿审稿者并行。没有第三票、常驻 Agent 聊天室或
跨章节正文并发；下一章必须等待上一章的临时 Canon、摘要和离场状态落盘。

### Wave 17.11：真实审稿传输止损与稳定 ID 绑定次序

新真实 Run `wave17-10-bounded-review-three-chapter-20260803-a1` 使用 DeepSeek 模型目录实时确认后的
`deepseek-v4-pro` / `deepseek-v4-flash` 启动。Run 完成 Info、Summary、Outline 与三章 Detail，
并形成第 1 章 1995 字 `prose_ready` 冻结稿；它没有完成三章正文，仍是失败样本，不能计入真实
验收通过。

Detail 首次失败来自无语义变化的引用格式：上游白名单为 `3. …`，模型返回 `硬设定：3. …`。
本轮把该固定前缀纳入无歧义本地归一化；恢复时复用已经落盘的三个章节批次，不重新生成细纲。
只有仍不能唯一映射的来源才允许调用字段级引用补丁，剧情、人物和章节合同保持不变。

第 1 章的 Deep 双审正确共享同一冻结快照并并行启动：语意/衔接主审返回明确
`score_scale=0-10`、`overall_score=8.4`、合同覆盖率 `1.0`；因果事实审稿则连续暴露三项传输问题：

- 首次返回的文学诊断超过 UI 展示字段长度。现在只在本地截断非硬门诊断文本；合同 ID、逐字
  证据和状态仍严格校验，不为展示长度再调用模型。
- 一次原位复检被 `2000 tokens` 截断。Prompt 现在要求最多 4 条短诊断、120 字以内合同原因与
  证据、最多 4 条短修订目标，确保 JSON 在既有预算内闭合；不通过提高调用次数解决。
- 最后一次返回按 Prompt 正确省略 `requirement`，旧代码却先执行 `requirement` 必填校验，晚于
  稳定 `contract_id` 绑定。现在先把 Provider 传输对象绑定到冻结合同目录，再构造严格
  `ContractAuditCheck`；自造 ID、错误 requirement 和无逐字证据仍不能进入硬门。

该 Run 的正文 `regeneration=0`、`revision=0`、`retry=0`；两次 generation 是同章两场景的既定
生成，不是整章重写。专业审稿达到既定 `cold_edit=3` 上限后系统停止，未追加第四次调用、第三
角色或正文重生成。下一次必须使用新 Run ID；先验证第 1 章双审能完整结算，再继续第 2、3 章，
不能把本次工程修复描述为三章文学验收完成。

工程回归（2026-08-03）：后端全量 `821 passed, 1 skipped`，前端全量 `129 files / 509 passed`，
前端生产构建、Python 编译与 `git diff --check` 通过。真实 Run 的失败报告保存在其
`acceptance/acceptance-report.md`。

### Wave 17.12：成本敏感审稿恢复与证据共识硬门

本轮继续验证有限 Adaptive Review Mesh，没有增加第三审稿角色。真实 Run
`wave17-12-adaptive-review-checkpoint-20260803-a1` 的第 1 章形成 2490 字正文，并由语意/衔接主审
与因果事实审稿并行完成；主审为 8.9/10，双方证据冲突与绑定失败均为 0。该章仅有两次场景
generation，`regeneration=0`、`revision=0`、`retry=0`。第 2 章因证据无法逐字绑定进入
`verification_required`，没有继续第 3 章。

真实恢复暴露出两层执行缺陷：显式 `recheck_requested` 会被历史完成快照抢占；即使跳过缓存，
验收尾部恢复仍会把 `prose_ready` 冻结稿删除并重走场景生成。现已固定恢复优先级：证据复核请求
高于历史审稿缓存；正文、Artifact、上下文、冻结角色和复核谱系全部匹配时，验收恢复必须保留
当前章并只调用 `roles_to_recheck`；`review_generation` 只在申请时递增一次，
`evidence_recheck_count/recheck_lineage` 在 pending 与最终协调结果中持续保留。任一签名漂移则拒绝
原位复用，不得静默重开正文。

`wave17-14-adaptive-review-checkpoint-20260803-a1` 又暴露一次无效修订：专项审稿把正文已逐字存在的
进入状态标为 missing，却没有提供反证；旧质量门仍把该单方意见升级成硬缺失并消费唯一局部补丁。
新合同改为证据共识硬门：上游合同 missing 只有在语意主审对同一稳定 `contract_id` 也判缺失，
或专项角色给出可在正文定位的相反证据时，才允许阻断和自动补丁；单方空证据 missing 只保留为
诊断。正文内日期、称呼、数值或机制冲突仍可凭成对原文证据直接阻断。

审稿目录同时停止把超过 240 字的复合梗概、整章细纲或结构对象截断成半句合同；这些值只保留
已拆出的场景与原子条目。语意合同升级为 `5-atomic-evidence-consensus`，专项合同升级为
`4-evidence-consensus-gate`，旧审稿缓存不能跨版本复用。`wave17-12`、`wave17-13` 与 `wave17-14`
均保留为失败样本，不能描述为三章或投稿级验收完成。

### Wave 17.13：风险自适应审稿职责图收口

本轮将“最高档增加多个子 Agent”收敛为按风险分配的审稿职责图，而不是常驻 Agent 群或多数票系统。
Agent 数量不是质量指标；冻结输入、明确权限、证据绑定和成本上限才是可生产的能力。

| 模式 | 默认审稿能力 | 风险升级 | 并发与自动修改 |
| --- | --- | --- | --- |
| Fast | 零模型审稿，只运行确定性硬门 | 不追加审稿角色 | 不调用模型审稿，不自动修订 |
| Balanced | 每章一名语意/衔接主审 | 仅高风险章在硬门后串行独立冷编辑 | 不并行双审；最多一次局部补丁 |
| Deep | 每章一名语意/衔接主审 | 中高风险章动态选择因果事实、终章兑现或独立冷编辑中的一个专项角色 | 两名角色共享冻结快照并行；最多一次局部补丁 |

动态路由只读取当前章 `ReviewInputSnapshot`：正文、Context Packet、Scene Contracts、版本与签名。
卷末/终章优先分配终章兑现审稿；日期、权限、物证、机制和结构化状态增量密集章分配因果事实审稿；
其余中高风险章分配独立冷编辑。审稿角色不得读取未冻结的运行态对象，不得直接修改正文，也不得写入
Memory、Wiki、人物图谱或 Canon。下一章必须等待本章审稿协调、章后临时叙事层和离场状态结算完成。

协调器最多同时运行两个角色。Provider 故障转移只能替换原角色，结构合同错误不能借备用 Provider
扩大重试；`verification_required` 只开放一次 `evidence_binding_failures.unbound_roles` 原角色复核，
空角色集合直接转人工，不得退化为全角色重跑。任何自动补丁失败都保留原 `prose_ready` 冻结稿，
不消费 regeneration，也不启动第三角色或整章重写。

工程收口将审稿目录、缓存、报告解析、并行调用和状态协调拆成单一职责模块；API 路由仍只适配领域命令。
2026-08-03 回归结果为后端 `826 passed, 1 skipped`、前端 `129 files / 509 passed`，Python 编译与
`git diff --check` 通过。该结果证明工程合同稳定，不代表真实三章或投稿级文学验收已通过；下一次付费验收
应先复用已确认的 Info/Summary/Outline/Detail Artifact，仅新建正文检查点，再按章一章一审。

### Wave 17.14：隔离正文检查点与前置 Token 止损

本轮没有复制失败 Run，也没有原地复用旧正文分支。新增的正文检查点只接受 `detail` 的
`stage_artifact_confirmed/artifact_approved` 稳定快照，并在 Provider 调用前完成以下硬校验：

- 来源与目标工作流的 Info、Summary、Outline、Detail `id/type/output_key` 完全一致；
- 除 `project_id` 外验收输入完全一致，四阶段均为 confirmed，当前稿与 approved Artifact 一致；
- 四个 Artifact 仍通过当前结构合同及 Summary/Outline/Detail 引用合同；
- Summary/Outline 的正式写回签名存在且匹配；来源没有正文 Artifact、章节摘要、章节 Wiki、Canon、
  Review、恢复错误或正文正式写回。

通过后，新 Run 使用独立 `run_id/project_id`，只继承四个确认稿以及 Story Bible、世界观、人物关系、
伏笔和连续性等前置叙事状态；预算、用量、质量报告、错误、恢复、Detail 批次、正文、候选、审稿、
修订、Memory/Wiki/Canon 事务全部从零开始。四份前置 Artifact 会在新项目 Wiki 命名空间重新投影，
Detail 派生状态也按当前写回规则重建，旧 `wiki_refs` 不跨项目继承。Runner 的
`completed_stage_ids` 固定为 `info/summary/outline/detail`，首次 Provider 任务必须是 `chapter_text`。

CLI 新增 `--text-checkpoint-source-run` 与可选 `--text-checkpoint-source-snapshot`，只允许搭配
`--three-chapter-checkpoint`；重复执行同一来源和目标时幂等返回，来源或输入变化则拒绝覆盖。创建事件
`acceptance_text_checkpoint_created` 保存来源快照摘要、四个 Artifact 签名、工作流版本和清空类别，
并自身形成可恢复稳定快照。

2026-08-04 已用真实历史快照
`wave17-12-adaptive-review-checkpoint-20260803-a1/snapshot-00000069-087b7877fea0` 在临时目录完成离线
dry run：目标 Run 直接停在 Text，四份新 Wiki 文档齐全，预算与章节状态为空，来源 Run 摘要未变化。
同日真实 runtime 已创建 `wave17-15-three-chapter-text-checkpoint-20260804-a1`：只包含分支来源事件和
检查点创建事件，当前阶段为 Text，尚无任何 Provider、正文、审稿或 Canon 事件。Runner 集成测试证明
前置四阶段零 Provider 调用。最新工程回归为后端 `837 passed, 1 skipped`，Python 编译与
`git diff --check` 通过；本 Wave 未调用 DeepSeek，因此仍不能描述为三章文学验收通过。

### Wave 17.15：质量修订候选事务与旧运行有界恢复

真实 Run `wave17-15-three-chapter-text-checkpoint-20260804-a1` 随后形成第 1 章 2337 字
`prose_ready` 原稿。两次 generation 分别对应两场正文，额度保持 `2/2`；因果事实审稿发现删除日期与
录音采集日期倒置、权限绕过缺少机制说明，系统消费唯一一次局部修订。修订 Provider 成功后，语意审稿
发生 `provider_unavailable`，因果审稿成功，但旧实现只在 `revision_applied` 事件保存 420 字尾部预览，
没有持久化完整候选。候选语意签名 `581e538f...`、因果签名 `3dee159e...` 与候选 Artifact 签名
`7c2074c3...` 仍可证明审稿对象不是原稿，却不能据此逆推出完整正文；因此禁止拼接预览、复制因果审稿
描述或把旧候选伪造成可恢复稿。

质量修订现在改为提交前候选事务：局部补丁成功后，先把完整 `candidate_content`、候选/基线签名、
原冻结稿 Artifact 签名、旧质量报告、旧审稿结果和旧审稿快照写入
`chapter_revision_state["quality:text:第N章"]`，再启动候选复审。复审通过前，正式 Chapter Artifact
始终保留原稿；Provider 中断后恢复直接复用完整候选，不再次调用正文修订。并行审稿只为
`provider_unavailable` 的失败角色开放一次额度，成功角色继续按同一候选签名复用；候选通过后才替换
质量报告并进入章后抽取，回退则恢复旧审稿快照和原稿。

旧 Run 另有一次严格的一次性恢复通道。只有同时满足下列条件才允许动作：历史事件存在
`revision_applied -> chapter_review_coordination_started -> model_review_unavailable`，期间没有
`quality_revision_candidate_persisted`；当前章仍是未正式写回的 `prose_ready` 原稿；当前原稿的语意与
专项双审可从签名匹配快照完整恢复；正文节点启用手术式补丁；章节没有待审候选。系统随后创建绑定原稿
签名和来源事件序号的新故障作用域，只把 `revision/model_review/cold_edit` 各增加一次，generation 保持
不变。若任一证据缺失，则不自动扩额，也不伪造候选。

真实 Run 临时副本演练已先恢复原稿双审，再命中事件 133 的候选缺失：原稿仍为 2337 字，generation
保持 `2/2`，revision 从 `1/1` 开到 `1/2`，model review 与 cold edit 分别从 `3/3` 开到 `3/4`，
`chapter_revision_state` 仍为空，等待新的局部补丁先按新合同完整落盘。该演练没有调用 Provider，也不
代表第 1 章或三章文学验收通过；真实恢复必须先完成第 1 章候选复审，再按章继续第 2、3 章。工程回归
为后端 `847 passed, 1 skipped`，Python 编译与 `git diff --check` 通过；当前环境未安装 Ruff，未声称
完成 Ruff 验证。

### Wave 17.16：证据硬门纠偏、叙事抽取止损与真实第 2 章停靠

真实 Run `wave17-15-three-chapter-text-checkpoint-20260804-a1` 已恢复第 1 章并形成 2383 字正式章；
第 2 章保留 2599 字冻结正文、当前后处理结果和完成的双审，不重新生成正文。旧因果审稿把“冻结相关
转运箱调取权限”推导成“禁止进入开放礁石区”，但没有给出同一对象的反证。专项硬发现现在必须同时
绑定正文中的正证与反证；只有单证据的因果疑点保留为诊断，不进入自动修订硬门。系统随后用冻结双审
和新证据合同本地复算质量门，写入 `acceptance_quality_contract_recomputed`，Provider 调用为 0，
generation/revision/model review/cold edit 额度均未改变。相同正文签名再次恢复时直接幂等返回，不重复
追加质量报告、恢复事件或 `recovery_count`。

第 2 章章后叙事抽取随后暴露两类 Provider 传输错误：把仍在继续的中文对白提前补上结尾引号，以及把
两段分开的对白或场景摘要伪装成逐字证据。前者只在去掉一个错误边界符后能唯一命中正文时允许本地
归一化；连续对白中的说话插语可在不改任何字词时恢复。跨段、省略号和摘要证据继续严格阻断。绑定器
现在一次收集全部 assertion/fingerprint 错误，不再只报告首个错误，从而避免一次付费复检后才发现下一
个同批问题；Prompt 也明确要求场景指纹的 `evidence_quote` 必须是可直接复制的连续正文，而不是合同
摘要或计划措辞。

该 Run 当时已消费一次有界叙事抽取复检，复检 payload 仍包含一条带 `...` 的跨段断言和两条摘要式
场景指纹。系统没有追加第二次盲重试，而是返回 `narrative_extraction_retry_exhausted` 人工核验停靠；
再次执行同一 Run 时 Provider started/succeeded 保持 `18/17`，第 2 章 generation 保持 `2`、retry
保持 `1`。这是 Wave 17.16 的历史停靠点，不再代表 Run 的当前状态；后续字段级证据复核、冻结双审
故障关闭、三章完成和卷提交结果见 Wave 17.17。该停靠期间仍严格禁止丢弃第 2 章、自动扩增正文额度或
绕过叙事门。阶段性工程回归为后端 `857 passed, 1 skipped`，Python 编译与 `git diff --check` 通过。

### Wave 17.17：冻结审稿故障关闭与伏笔证据投影恢复

真实 Run `wave17-15-three-chapter-text-checkpoint-20260804-a1` 已在不重生成第 3 章的前提下完成冻结双审
故障关闭。只有章节、错误码、正文/上下文/Artifact 签名、审稿快照与双审结果全部一致，旧
`model_review_unavailable` 才会从当前错误集中关闭；历史失败、失败总数、生成/修订/审稿次数和预算
均保留。随后一次专用章后抽取恢复完成摘要、叙事状态、卷审计和 Canon/Wiki/Memory 原子写回，三章
字数为 2383 / 2599 / 2513，Run 进入 `completed`。

最终技术红灯来自章后伏笔投影，而不是正文或验收器。旧抽取允许模型把稳定线索改写成“第33号记录异常”
“母亲纪清汐的真相”等新名称，并把正文概括当作 evidence；严格写回因此正确拒绝全部更新。新合同要求
`foreshadow_updates[].id/name` 只能逐字复制 Chapter Context Packet 的稳定目录，evidence 必须是正文
连续逐字片段，禁止同义改名、跨段拼接、删节号摘要和本地模糊补证。`detail:第N章:*` 中文稳定 ID 也已
纳入当前章节优先选择。写回按稳定 ID 优先、唯一精确名称降级处理；未知、歧义或 ID/名称不匹配均拒绝，
规划目标状态与运行时状态分开保存。

已提交卷不粗改 `run.json`，而是通过一次派生投影恢复事务补写 Story Bible。事务同时绑定冻结正文 SHA、
章节提交签名、已接受写回提案签名、卷审计和卷提交签名，并使用 Run State CAS；重复 correction digest
只返回原事件。真实恢复事件 `committed_foreshadow_projection_recovered` 写入 7 个逐字证据转换，形成
“第33号记录”“海螺线索”“预警系统缺陷”的跨章投放/回收历史；Provider 调用为 0，正文、Canon、
预算和 394100 token 记录均未改变。重建后的自动技术验收全部通过，投稿状态仍为
`needs_author_review`。

自动技术通过不等于文学闭合。人工审读记录在该 Run 的
`acceptance/manual-literary-review.md`：终章只呈现路径修正，没有呈现风暴实际过境；林潮音被安保按住
不等于停职调查，陆怀山被监察员带走不等于撤职；第 2 章章后抽取还把“纪清汐”误写成“林清汐”并
进入派生 Canon。当前冻结稿因此不能称为投稿定稿。下一 Wave 必须创建版本化 Canon 修订分支，先修正
实体身份污染，再对终章做局部结算修订并重新失效/验证 Review、Wiki、Canon 与 Export，不能覆盖本次
已提交基线。

### Wave 17.18：Canon 修订分支、逐章 RAG 对账与伏笔投影幂等收口

真实修订 Run `wave17-18-canon-revision-20260804-a1` 已从已提交基线创建
`committed_revision` 分支，完成实体名污染和终章结算问题的版本化修订。分支重用已冻结
正文，只重建受影响的摘要、叙事抽取、审校、Wiki/RAG、Canon 和导出派生结果；
验证专线不重开 generation/candidate/regeneration 正文额度，不覆盖父 Run。

最终自动报告为 `technical_passed=true`：三章、每章两场、模型复检、伏笔证据、
Wiki/RAG、Canon 冲突、预算和运行错误检查全部通过；Provider 历史为 `7 succeeded / 0 failed`，
`48 committed / 0 provisional` Canon 事实，记录 Token 为 `507698`。后置 RAG 对账同时绑定
父 Run 状态摘要、Context Signature 和历史命中文档 ID，禁止当章或后章 Wiki 倒灌历史上下文；
对账事件严格幂等，Provider 和 Token 增量均为零，三章正文 SHA 不变。

伏笔投影恢复在此后又收紧两个恢复边界：corrections 先按卷内章节顺序和稳定伏笔 ID
规范化，同组记录重排不会绕过幂等键；命中历史恢复事件时，必须再核对 Story Bible、
运行态 ledger、投影元数据和全部 transition signature。任一数据后续漂移都明确拒绝返回
旧成功结果。旧真实 Run `wave17-15-three-chapter-text-checkpoint-20260804-a1` 已通过只读一致性核对，
`run.json` SHA-256 仍为 `7461b726a3209dfdb923ca93d7092bc17b955353157ab5040b3bc50206c8a4e2`。

自动技术通过仍只推进到 `needs_author_review`。Wave 17.4 人工偏好校准仍被独立 Judge 阻断：
2026-08-04 对 `glm-5.2` 重跑最低成本正反顺序烟测，首次推理前返回 `insufficient_balance`，
因此没有创建 Run C，也没有 Writer 调用。MiMo Token Plan 是编程工具专用入口，不得绕过
产品策略用于小说 Judge；DeepSeek 也不得同时担任 Writer 和独立 Judge。

### Wave 17.19：DeepSeek-only 写文边界与作者审读闭环

后续真实写文与普通模型审校统一使用 DeepSeek；不再使用 GLM 或 MiMo 生成小说正文。该决定不取消
Writer/Judge 独立性：DeepSeek 可以承担 Writer 和普通审校，但不能同时伪装为独立偏好 Judge，
第二厂商不可用时偏好校准保持阻断，不以同源自评换取绿色状态。

不依赖第二模型的作者人工审读闭环已落在 `acceptance/` 领域，且不新增第八个创作阶段。命令
`novel-workflow-author-review prepare --run-id <run-id>` 从冻结 Run 生成：

- `author-review-bundle.json`：逐章正文 SHA、版本、提交签名、Context Signature、前后章交接、
  Scene Contract、伏笔正文证据和自动冷编辑 Finding。
- `author-review-manuscript.md`：按章排布的完整审读稿与证据入口。
- `author-review-response.json`：作者填写 `accept / revise / unresolved`，并逐项核对承接、人物声音、
  潜台词、解释密度、伏笔和原创性。
- `author-review-report.json/.md`：只读验证答卷、投稿市场规则、AI 协作披露、作者责任和最终签名。

重复 prepare 在 Bundle 身份不变时保留已有答卷；正文、章节版本、提交签名、Context 或正式
Memory/Wiki/Canon/Story Bible 状态变化时，旧 Bundle 或 `review_signature` 明确失效。任一章节为
`revise` 或 `unresolved`、任一维度缺少正文证据、市场规则/披露未确认或作者未签名时，状态保持
`needs_author_review`。只有全部章节 `accept` 且所有人工确认完整，独立审读报告才可推进到
`ready_for_manual_submission_review`；该状态仍不表示自动可投稿或保证过审。

真实 Run `wave17-18-canon-revision-20260804-a1` 已生成审读包，三章答卷保持未决。prepare 与 verify
前后 `run.json` SHA-256 均为
`10f626d3d2bb73050cd10ed95720cc36dfa7eb4357d3a62e4497d1e285fc4122`，原自动报告 SHA-256 均为
`7542dd8c040c5dcf1afe801d86a449ba1b3c10ec7efe5507b05160a725a2bdb2`；Provider、Token 和正式
写回签名未变化，审读过程没有模型调用或 Token 增量。

### Wave 17.20：结构触发的并行审稿与局部修订止损

“最高档由多个子 Agent 审稿”在本轮正式收敛为结构触发的有限职责图，不实现常驻 Agent 群、
角色聊天或多数票。生成 Agent 先产出唯一冻结候选；审稿角色只读同一份 `ReviewInputSnapshot`，
不能直接改正文、写 Memory/Wiki/Canon 或启动下一章。

| 模式 | 默认能力 | 条件升级 | 墙钟与失败边界 |
| --- | --- | --- | --- |
| Fast | 零模型审稿，只运行确定性合同与叙事状态门 | 无 | 零审稿调用 |
| Balanced | 每章一名语意/衔接主审 | 仅高风险章顺序追加独立文学冷读 | 约 60 秒；冷读不可用只记诊断 |
| Deep | 每章一名语意/衔接主审 | 卷末/终章增加兑现审稿；时间、权限、物证、机制或结构化状态密集时增加因果事实审稿；高风险时增加独立文学冷读 | 同章最多四个固定职责并行，约 90 秒 |

硬阻断权只属于语意主审可绑定的上游合同，以及结构触发的因果事实/终章兑现专项。独立文学
冷读始终是诊断角色，不拥有事实真值、不进入自动补丁硬门、不可用时不阻断，也不走备用链。
语意主审和硬专项仅在超时、限流、网络、服务或配置不可用时允许一次同角色故障转移；结构化
输出错误不换源。角色差异只触发证据协调，不得临时增加投票 Agent。

局部补丁继续保持每章最多一次、`1-4 edits` 和 `1200 tokens` 上限，并新增三层确定性准入：目标
必须唯一可定位，专项置信度至少 0.8，累计 `search` 不超过正文 15% 或 600 字，同时限制
`replacement` 总量和全文净变化。无法定位、跨度过大或需要跨场景重写时直接保留原稿转人工。
补丁后只复检语意主审和首次阻断的硬专项；Deep 最坏路径为初审四角色加补丁后三角色，共七次
审稿调用，正文 generation 次数不增加，独立文学冷读不重复计费。

旧 Run 的零调用合同复算同时绑定正文、Context、Scene Contract 和审稿合同版本。旧复合合同只在
其稳定 ID 可证明为当前原子子路径父级时迁移；旧 `missing` 拆分后所有子项保持 `missing`，相同
文案出现在无关路径不得迁移，无法在当前冻结正文绑定的旧正向证据不得通过。重复 `contract_id`
出现相反状态时按 `missing` 保守处理，避免模型返回顺序决定硬门结果。

工程复检已覆盖角色路由、四角色同稿并行、硬专项聚合、可选冷读降级、角色级超时、故障转移、
补丁后原角色复检、候选恢复、旧合同迁移和局部补丁边界：相关回归 `119 passed`，完整后端套件
`994 passed / 1 skipped`，Python 编译与差异检查通过。场景压缩和质量小修使用不同变更预算：
前者只能删除受保护首尾之外的冗余并满足场景字数合同，后者继续遵守正文 15% / 600 字及净变化
上限，禁止以场景压缩需求放宽审稿补丁。

冻结快照 `snapshot-00001188-51368a429507` 的内存零调用试算保持正文、预算和 generation 次数不变，
但没有通过当前合同：第 3 章正文 4486 字，正文/Context/审稿签名一致，语意主审仍有 4 条正向证据
无法在冻结正文逐字绑定，复算完成率为 63.64%。该结果应视为正确的 fail-closed，而不是恢复失败；
后续真实验收只允许为当前冻结稿开放一次语意/衔接复审，不重写正文、不重复独立文学冷读，也不
重跑前两章或整本小说。

## 16. 测试矩阵

| 层级 | 必测内容 |
| --- | --- |
| 单元 | 双时间排序、知识取得、物件转移、证据保管、机制推导、n-gram、结构指纹 |
| 属性测试 | 状态 reducer 顺序稳定、相同事务幂等、无来源断言不能提交 |
| 变异测试 | 关系反转、时间回跳、证据删除、空间错置、高潮新机制、场景复制 |
| 集成 | SceneContract -> Draft -> Actual Delta -> Gate -> Overlay |
| 恢复 | 中断后事务不重复提交，失败场景不会污染下一场景，Run State 前无 Wiki 副作用，pending outbox 可幂等补投 |
| 修订 | 第 N 章修改后所有 hard consumer 失效，未受影响软依赖可保留 |
| 卷提交 | 任一硬冲突导致整卷不正式写回，修复后可幂等提交；已提交卷改写进入隔离分支且旧 Canon 不可消费 |
| 导出 | 临时卷、stale 依赖、未解决冲突任一存在时拒绝 ready |
| 作者审读 | 答卷完整性、正文/上下文签名、防旧版本、重复 prepare 保留答卷、revise 阻断、零 Provider/Token/正式写回 |
| 真实链路 | 新整书 Run II、模型故障转移、预算中断与恢复 |

## 17. 研究依据与采用边界

- [Re³](https://aclanthology.org/2022.emnlp-main.296/) 证明规划、分段生成、候选排序和事实编辑应分离；本项目采用职责分离，不照搬其固定流程。
- [DOC](https://aclanthology.org/2023.acl-long.190/) 证明详细大纲之后仍需要正文控制器；本项目把控制器升级为场景状态事务。
- [Narrative World Model](https://arxiv.org/abs/2607.05577) 说明人物知识、事件时间/揭示时间、关系变化和承诺回收应是一等结构；本项目先实现轻量版本化记录，不立即引入图数据库。
- [ConStory-Bench](https://aclanthology.org/2026.findings-acl.410/) 说明长篇错误主要集中在事实与时间，并要求成对文本证据；本项目将其作为硬门证据协议和变异分类基础。
- [LitBench](https://aclanthology.org/2026.eacl-long.362/) 说明通用 LLM Judge 不能被视为可靠真值；本项目用项目内校准、盲化成对偏好和人工样本替代裸总分。
- [WebNovelBench](https://aclanthology.org/2026.findings-eacl.94/) 提供中文长篇多维评测和人类作品分布思路；本项目只借鉴分布式基准，不把单一 Judge 分数升级为硬门。
- [MAGNET/ATLAS](https://arxiv.org/abs/2607.00918) 说明共享世界状态和场景图比较有助于长篇一致性；本项目采用共享状态与场景事务，但不引入常驻多 Agent 表演层。

## 18. 完成定义

Phase 17 只有同时满足下列条件才算完成：

1. Run I 九类已知错误全部成为自动回归失败，而不是 warning。
2. 新硬门在干净样本上的误报率达到退出线。
3. 场景实际退出状态真实驱动下一场景。
4. 卷级 Canon 提交可回滚、可恢复、可审计。
5. 人工修订会让所有受影响的 Context、Review、Canon 和 Export 失效。
6. 文学评审通过项目内人工偏好校准，不再依赖一个 8.4 总分。
7. Run II 经过完整自动验收和逐章人工冷编辑，且相对 Run I 有可复核的改善证据。
8. UI 只显示用户能理解的证据和修复动作，不泄露内部图或原始 JSON。

在这些条件达成前，产品可以称为“完整工作流原型”，不能把自动技术通过描述成“投稿级成书”。
