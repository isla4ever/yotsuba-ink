# Phase 26：LangGraph 原生叙事架构重启

> 状态：**架构已批准，Wave 26.1-26.6 离线重构与本地浏览器矩阵已闭合；真实 Provider 已获“推送成功后执行”的授权，尚未执行；人工文学验收仍待完成**。
>
> 日期：2026-08-11。
>
> 用户已于 2026-08-11 明确授权“开始完全的重构迭代，使用好 LangGraph”，因此 Wave 26.1-26.6 已完成离线实现与本地验收；随后又明确授权在完整重构、清理和离线门通过并推送 GitHub 后开始真实链路测试。推送前的浏览器矩阵只使用隔离临时目录和 Fake Provider 检查点，验收后关闭本地服务；不启动或恢复历史 Run，不调用真实 Provider。Phase 20、ADR-001 与 Phase 25 中的 Shadow、Dual、feature flag、legacy 回滚、Run H 和兼容读取路线均只保留为历史证据，不再指导实现。

## 1. 决策摘要

Phase 26 不是在旧 Runner 外再包一层图，而是重新建立单一生产权威。

1. **运行时选择 LangGraph，不选择 LangChain Agent 作为运行时。** LangChain 的 `create_agent` 本身运行在 LangGraph 上，适合通用模型/工具循环；Yotsuba Ink 需要显式阶段、持久化 checkpoint、人工 interrupt、并发只读审稿、事务写回和可恢复长任务，应直接使用 LangGraph Graph API。现有 Provider、Prompt、Pydantic 合同继续作为领域端口，不引入第二套 Agent 编排。
2. **LangGraph 是唯一生产执行运行时。** 不再存在 `runtime_engine=legacy|langgraph`、Shadow、Dual、feature flag 或失败后静默回退。生产命令只能进入一个已编译图。
3. **LangGraph checkpoint 是运行状态唯一权威；领域存储仍各自权威。** Artifact、Evidence、Canon、Wiki 和 Outbox 不是 checkpoint 的复制品；事件流和前端状态只是投影，不能反向决定路由。
4. **新增独立“人物编排 / 角色圣经”阶段。** 它位于创作立项之后、全书梗概之前。Info 不再同时承担完整人物、关系、人物弧和世界设定；后续阶段只引用冻结角色，或提交有证据、需确认的变更提案。
5. **阶段 Artifact 大幅瘦身。** 每阶段只保留该阶段不可替代的用户决策；可计算字段由确定性代码投影，审稿、预算、调用、哈希、UI 状态和写回回执进入 runtime sidecar。
6. **删除 Detail v1/v2 和生产兼容兜底。** 不增加 alias、converter、normalizer、fallback 或旧字段读取。历史 Run 只进入物理隔离、只读、无 Provider 的离线归档查看器。
7. **Memory/Wiki/Canon/RAG 是低敏感、证据驱动的辅助系统。** 它们提供建议、出处和连续性提示，不把创作变成僵硬规则集合。RAG 仅在用户上传并选中知识库时用于前置规划，不在正文阶段盲检索。
8. **字数是软目标，硬门只防异常。** 合理浮动不触发自动补写、压缩或删改；截断、空输出和显著失控才阻断，所有文学修改保留人为决策。

## 2. 先评估 LangChain 与 LangGraph，再决定运行时

### 2.1 比较对象不是两个互斥包

这里不能把“用了 LangChain”与“用了 LangGraph”误写成二选一。官方源码和文档明确说明：LangChain `create_agent` 会构建并运行一个 LangGraph；本仓库安装 `langgraph` 时也会传递依赖 `langchain-core`。真正需要决定的是生产控制面的抽象层级：

- **候选 A：LangChain `create_agent` 作为顶层运行时。** 以 message/tool loop 为主语，让模型动态决定工具使用和停止；checkpoint、interrupt 和 stream 最终仍来自底层 LangGraph。
- **候选 B：直接使用 LangGraph Graph API。** 以 Yotsuba Ink 的 Stage、Artifact、Decision、Chapter、Review 和 Writeback 为主语，显式定义 State / Node / Edge / interrupt / checkpoint。
- **非候选：自研 Runner、LangChain 与 LangGraph 双轨。** 它们已经违反单一权威要求，不进入选型打分。

这也意味着依赖图里出现 `langchain-core` 不等于项目选择了 LangChain。Phase 26 的生产边界更严格：业务源码只直接使用 `langgraph.*` 与 Yotsuba Ink 领域端口，不直接导入高层 `langchain` 包或 API；LangGraph 自身不可剥离的传递依赖不算第二运行时。

### 2.2 选型硬门

候选必须同时通过六项硬门；任一项只能通过增加第二运行时、第二状态或生产兼容层实现，即判定不适合：

1. 一个生产 thread 对 active node、interrupt、resume 和 checkpoint 只有一个权威；
2. 八阶段顺序、相邻章节串行、固定审稿角色并发和有限修订循环能用显式边表达；
3. 浏览器/SSE 断线不拥有执行生命周期，进程故障后可从持久 checkpoint 精确续跑；
4. 继续复用现有 ProviderRegistry、Prompt compiler 和 Pydantic Artifact 合同，不为框架再造模型、消息和结构化输出权威；
5. Provider 调用、预算扣减和 Domain Outbox 写回可使用 operation receipt 做幂等重放；
6. 前端只消费稳定领域事件和 read model，不依赖 message history 或 raw graph state 猜测阶段。

### 2.3 同层能力比较

| 维度 | LangChain | LangGraph | Yotsuba Ink 决策 |
| --- | --- | --- | --- |
| 定位 | 模型、工具、middleware 和通用 Agent loop 的高层框架 | 长时、有状态工作流的低层编排运行时 | 需要后者作为控制面 |
| 执行底座 | `create_agent` 最终编译并运行 LangGraph | 直接定义 State / Node / Edge / Send / interrupt | 不在 LangGraph 上再叠一套通用 Agent loop |
| 路径控制 | 适合模型动态选工具、迭代到停止条件 | 适合预定义阶段、条件边、有限循环和并发分支 | 小说生产是领域工作流，不是开放式工具对话 |
| 恢复与人工审批 | 能力来自底层 LangGraph | 原生 checkpoint、thread、interrupt、`Command(resume=...)` | 直接持有并暴露这些语义 |
| 结构化输出 | 可在 ProviderStrategy / ToolStrategy 间自动选择，并对格式错误重试 | 不规定 Provider 和输出抽象 | 便利性成立，但自动策略与重试会重复并弱化现有 Provider receipt / Pydantic 合同边界 |
| 迁移成本 | 会复制现有 Provider、Prompt、重试和状态抽象 | 可替换当前 Runner/control/recovery | 选择更小且边界更清晰的改造 |

### 2.4 硬门判定

| 硬门 | LangChain `create_agent` 顶层控制面 | 直接 LangGraph Graph API |
| --- | --- | --- |
| 单一执行/恢复权威 | **条件通过**：底层确为 LangGraph，但仍需在 Agent message/tool state 外表达八阶段领域状态 | **通过**：thread、checkpoint、interrupt 与领域 ref 直接进入同一图 |
| 显式阶段与并发边 | **不通过顶层形态**：`create_agent` 的核心是模型-工具循环；加入外层阶段图后，顶层权威实际已变为 LangGraph | **通过**：固定边、条件边、`Send` 和 subgraph 与需求同构 |
| 持久恢复与人工决策 | **能力可用但非独有**：全部由底层 LangGraph 提供 | **通过且直接**：不需要再映射一层 Agent 状态 |
| 复用现有 Provider/Prompt/合同 | **部分通过**：需要把现有 Provider 适配成 LangChain model/tool/structured-output 语义，形成重复抽象 | **通过**：Node 直接调用现有领域端口并返回 Artifact ref/receipt |
| 副作用幂等与精确重放 | **部分通过**：可用 middleware/tool 包装，但 operation receipt 仍需在外部领域层另建 | **通过**：在副作用 Node 边界直接声明 operation key 与失败 edge |
| SSE/前端领域投影 | **部分通过**：message/tool 事件不是 Yotsuba Ink 的稳定阶段合同，仍需二次映射 | **通过**：Node/interrupt/checkpoint 更新直接映射领域事件 |

判定不是“LangChain 做不到复杂工作流”，而是：一旦为 `create_agent` 补齐上述硬门，就必须再建立一个定制 LangGraph 外层；此时 LangChain 顶多只剩 Node 内部组件价值，却仍会重复本仓库已经存在的 Provider、Prompt 和结构化输出端口。Phase 26 因此连这条默认入口也拒绝，它没有为当前产品增加与成本相称的能力。

### 2.5 最终选择与依赖边界

因此最终选择：

- `langgraph` 是必装、唯一编排运行时；
- `pyproject.toml` 不直接依赖任何 `langchain*` 包，生产 `src/` 不允许 `import langchain` 或 `from langchain`；静态边界测试必须阻止其回归；
- 不引入 `langchain.agents.create_agent`、AgentExecutor、LangChain memory、middleware 或 structured-output API，不为“未来窄节点”预留默认入口；模型、工具、Prompt 与结构化结果继续经现有领域端口进入 LangGraph Node；
- 当前 `uv.lock` 中 `langgraph==1.2.10` 传递依赖 `langchain-core==1.5.3`。这是 LangGraph 的内部依赖，不是 Yotsuba Ink 的直接业务依赖，不删除 lockfile 中的真实传递关系，也不把它包装成项目 API。

### 2.6 反事实：何时重新评估 LangChain

以下任一产品前提发生变化时，只能通过独立 RFC、源码 spike 和删除矩阵重新开启选型，不能在实现 Wave 或单个 Node 中顺手引入：

- Yotsuba Ink 的主产品从可审计的八阶段小说生产，转为用户提出不可预知任务、模型自主选择大量工具的开放式对话 Agent；
- 项目明确废弃现有 ProviderRegistry、Prompt compiler 和 Artifact 输出端口，并有独立 spike 证明 LangChain 能删除而不是复制生产抽象；
- 某个边界清晰的 Node 出现真实、多步、动态工具选择需求，且评审证明直接 LangGraph 子图与现有领域端口都无法合理表达。

在当前产品需求和源码边界下，没有出现这些反事实。因此 Phase 26 的结论是直接 LangGraph，而不是先实施两套运行时再比较。

### 2.7 官方能力与本项目映射

| 官方能力 | 本项目用途 | 明确边界 |
| --- | --- | --- |
| checkpoint / thread / pending writes | 崩溃恢复、并行审稿完成项复用、状态历史 | 不代替 Artifact、Canon、Wiki |
| `interrupt()` + `Command(resume=...)` | 阶段定稿、角色变更、硬冲突、预算扩展 | resume 会从节点开头重跑；interrupt 前副作用必须幂等或移入独立节点 |
| `Send` / 并行 super-step | 对同一冻结稿执行固定审稿角色 | 不并行生成相邻章节 |
| subgraph | Stage、Chapter、Review 的局部状态与职责边界 | 子图不得维护独立领域事实副本 |
| `astream` 的 `updates/messages/custom/checkpoints/tasks` | 后端映射稳定 SSE 领域事件 | 前端不消费原始内部 State；实验性的 `stream_events(version="v3")` 不进入生产合同 |
| Store | 如未来需要跨 thread 的低敏感偏好 | 不作为 Canon 或用户上传知识库的替代品 |

部署决策：单进程自托管版本使用持久化 `AsyncSqliteSaver`，测试使用 `InMemorySaver`；只有明确进入多进程部署时，单独迁移到 `AsyncPostgresSaver`。这两者实现同一 checkpointer 权威，不是运行时双轨。生产禁止 `InMemorySaver`。

## 3. 当前真实权威路径

以下结论来自 2026-08-11 离线重构后的脏工作树审计。旧权威路径及失败证据保留在 Phase 25 和本仓库 Git 历史中；下表只描述现在可进入生产的路径。

| 能力 | 唯一入口和路径 | 当前权威 | 已删除/隔离的竞争路径 |
| --- | --- | --- | --- |
| Run 创建 | `api/routes/runs.py::create_run()` | `NarrativeRunRepository` 的不可变 `RunDefinition` | 旧 `RunStore` 命令权威、runtime selector |
| 启动与恢复 | `NarrativeExecutionService.dispatch_start/dispatch_resume()` | 一个 `NarrativeRuntime` 编译图，`thread_id = run_id` | Runner、legacy stream、pause/resume 轮询控制 |
| 全局阶段 | `runtime/graph/narrative_graph.py` | `STAGE_ORDER` 严格串行八阶段 | Shadow、Dual、feature flag、拓扑录制回放 |
| Stage 执行 | `stage_graph.py` + `StageExecutor` | candidate ref、显式 decision、commit receipt | Detail v1/v2/v3、repair、converter、自动补字段 |
| 正文章节 | `chapter_graph.py` | 相邻章节串行；每章 attempt/version 独立 | legacy 章节链、commit gate、自动接受 Balanced/Deep |
| 人工决策 | `interrupt()` / `Command(resume=...)` | `stage_artifact_decision`、`chapter_author_decision` | approval JSON、轮询确认、旧 decision alias |
| 并发审稿 | `chapter_review.py` 的固定 `Send` lanes | 同一不可变章节版本；operation receipt 防重 | fallback review waves、审稿后自动改文 |
| Checkpoint/分支 | `AsyncSqliteSaver` + `NarrativeBranchService` | LangGraph checkpoint；分支创建新 Run 身份 | 手写 recovery state、原 Run 破坏性回滚 |
| Artifact/正文 | `ArtifactStore`、`ChapterStore` | 不可变候选、编辑候选与已接受版本 | 大型顶层 state、旧 schema 兼容读取 |
| Evidence/写回 | `EvidenceStore` + `DomainOutbox` | 正文 span 提案；receipt 后 Canon/Wiki 投影 | 分散 flush、无证据直接写回 |
| SSE | `api/sse.py::observe_run_events()` | `EventProjection` 只读观察、sequence 重连 | SSE generator 拥有 Runner 生命周期 |
| 前端 | 八阶段 route + Graph read model + 稳定事件 reducer | 后端 read model 决定运行状态 | 七阶段表、旧事件名和 runtime phase 猜测 |
| 历史 Run | `/api/archive/runs` | 物理隔离的 `LegacyRunViewer`，只读零 Provider | 生产 start/resume/decision/branch/writeback 均不可见 |

当前剩余工作不再是运行时迁移，而是离线退出门收口：故障注入覆盖、浏览器矩阵、真实 Provider 新 Run 和人工文学验收。它们不能重新引入第二条生产路径。

## 4. 外部项目源码研究

### 4.1 来源账本

访问日期均为 2026-08-11。

| 项目 | 仓库 / 版本证据 | License | 阅读的源码重点 | 复用边界 |
| --- | --- | --- | --- | --- |
| LangGraph | <https://github.com/langchain-ai/langgraph>；HEAD `d56666f7fbf0d380ad84cdf0cbe5aa48ab0cc086`，2026-08-08；本仓库锁定 `1.2.10` | MIT | graph state、persistence、interrupt、subgraph、streaming 官方文档与仓库 | 直接采用运行时 API，领域合同自行实现 |
| LangChain | <https://github.com/langchain-ai/langchain>；HEAD `56daacc8dff4103f430b121711f601ae503bddf9`，2026-08-10；`langchain==1.3.14`、`langchain-core==1.5.3` | MIT | `create_agent`、runtime、structured output、middleware 官方文档与源码 | 不采用、不直接依赖、不在生产源码导入；`langchain-core` 仅允许作为 LangGraph 传递依赖存在 |
| PlotPilot | <https://github.com/shenminglinyi/PlotPilot>；HEAD `7dc03a37a06b57e823df222da0e3bde5d1c84715`，2026-07-19；最新标签 `v4.6.0` | Apache-2.0 + Commons Clause v1.0；后者明确禁止 `Sell`，GitHub API 为 `NOASSERTION` | chapter preplan/continuity ledger、character narrative kernel、memory/context assembler、checkpoint、streaming bus、prompt variables、review、foreshadow registry、Vue 工作台 | 法务确认前只学习抽象思想；不复制源码、Prompt、结构化合同或 UI 实现，不形成价值实质来自该软件的销售/服务 |
| FictionForge | <https://github.com/wanqili857-byte/fictionforge>；HEAD `c381297e2c6c670f374933d850b9b85756dead27`，2026-08-06；最新标签 `v0.2.0` | MIT | `TickRunner`、`ChapterCoordinator`、`SpecBuilder`、角色 Agent、Theory of Mind、Vault、质量门、SSE client | 可重写通用思想；不复制其双管线、静默降级或机械兜底 |

官方文档：

- LangGraph overview：<https://docs.langchain.com/oss/python/langgraph/overview>
- Persistence：<https://docs.langchain.com/oss/python/langgraph/persistence>
- Interrupts：<https://docs.langchain.com/oss/python/langgraph/interrupts>
- Streaming：<https://docs.langchain.com/oss/python/langgraph/streaming>
- Subgraphs：<https://docs.langchain.com/oss/python/langgraph/use-subgraphs>
- Workflows and agents：<https://docs.langchain.com/oss/python/langgraph/workflows-agents>
- LangChain agents：<https://docs.langchain.com/oss/python/langchain/agents>
- LangChain runtime：<https://docs.langchain.com/oss/python/langchain/runtime>

### 4.2 PlotPilot：可取与不可取

源码级观察：

- `chapter_preplanning_service.py` 在写正文前将幕级计划和连续性账本收敛成七段执行计划；长结构不是一次模型输出到底，而是“宏观计划 -> 章节 preplan -> 正文”。
- `chapter_continuity_ledger.py` 将前章交接、当前章义务和后章 handoff 形成明确账本，说明连续性应是小而确定的上下文，不是全量历史正文。
- `character_narrative_kernel.py`、`character_registry.py` 和 `appearance_scheduler.py` 对人物分层、出场窗口、关系和章节 cast 做投影；但它也允许章后发现并注册新角色，Yotsuba Ink 不接受这一默认权限。
- `memory_engine.py` 区分事实锁、已完成 beats、已揭示线索和章后抽取；`context_assembler.py` 按故事锚、人物状态、到期债务和最近章节装配，而不是统一“记忆”字段。
- `vector_retrieval_facade.py` 是通用向量检索，不足以证明正文应每章 RAG；Yotsuba Ink 只把用户知识库检索放在前置规划。
- `unified_checkpoint_service.py` 同时快照章节指针、Bible、伏笔和故事状态，并提供分支/checkout；值得借鉴非破坏分支体验，但它与 LangGraph checkpoint 语义不同，不能照搬为第二运行权威。
- `prompt_assembler.py` 的节点版本、绑定 ID、变量快照 hash、模板 hash、最终 Prompt hash 和缺失诊断值得采用；Yotsuba Ink 应投影来源与签名，不把变量中心本身做成用户主界面。
- `structured_json_pipeline.py` 的 JSON repair、外层截取和格式重试会把无效合同伪装成可执行结果；本项目明确拒绝这一生产兜底。
- 质量门和伏笔 TTL 含题材特定自动降级/放弃策略；这种强规则不适合通用小说产品，不能进入 Canon 自动修改。
- 前端将章节编辑、上下文 rail、人物、伏笔、checkpoint 时间线和调用审阅拆开，信息架构可参考；但 Yotsuba Ink 不显示原始 runtime JSON，也不提供无确认“回滚”按钮。

### 4.3 FictionForge：可取与不可取

源码级观察：

- `TickRunner` 先在弧级模拟世界和角色行动，再按天/地点聚类事件；`SpecBuilder` 再生成章节结构。这支持“大结构分段生成，小结构临近执行”的方向。
- Tier 1 / Tier 2 角色、`TruthTable`、knowledge/belief/ToM 分层，有助于区分“世界真实”“角色已知”“角色相信”和“角色对他人认知的判断”。
- 真相表不直接全文注入正文 Prompt，只注入推导出的 `info_gaps`，这一低敏感上下文原则适合 Yotsuba Ink。
- 场景对手戏可并行决策，但章节正文仍顺序生成；`scripts/gen.py` 还按 section 顺序写作并只携带前一段尾部，符合相邻章节和依赖段落不并行、上下文紧凑的原则。
- 其 `gen/engine/hybrid` 双管线、机械 spec、缺表静默降级、失败后 fallback 和内置自动修复与本次目标冲突，明确不复用。
- 质量检查中的固定禁词、比喻计数和 ±20% 只能作为诊断参考，不能直接成为通用文学硬门。

### 4.4 采用清单

采用并自行实现：

- 宏观计划与临近章节执行计划分层；
- Character Bible 冻结身份、职责、关系、人物弧与首次出现窗口；
- 世界真实 / 角色知识 / 角色信念分层；
- 只向 Prompt 投影紧凑 `info_gaps`，不注入完整真相表；
- 章节 handoff、未完成动作、伏笔窗口和事实证据分开；
- 正文按依赖小段顺序生成，字数采用软目标与合理容错；
- Prompt 输入来源、节点版本、绑定 ID、变量/模板/最终 Prompt hash、预算和输出去向可观察；
- 审稿只读冻结快照，写回必须证据化且幂等。

拒绝：

- 双运行时、Shadow、Dual 或 feature flag 切换；
- JSON repair、外层 JSON 截取、旧 schema 自动补齐和格式错误后静默转合同；
- 章后自动创建重要角色；
- 正文盲向量检索；
- LangGraph 之外的第二 checkpoint / checkout 权威；
- 伏笔 TTL 自动放弃、固定禁词自动改写和因字数自动删改；
- 审稿或质量门自动重写正文；
- `gen/engine/hybrid` 等多管线与 deterministic fake 生产降级；
- 模型自评分直接修改 Canon；
- 从 PlotPilot 复制受 Commons Clause 限制的实现。

## 5. 阶段重排与产品取舍

### 5.1 vNext 八阶段

配置不是运行阶段。正式生产顺序为：

```text
创作立项 -> 人物编排 -> 全书梗概 -> 分卷大纲
         -> 章节施工图 -> 正文 -> 封面 -> 导出
```

| 阶段 | 唯一产物 | 用户必须决定什么 | 正式写回 | 下游只依赖什么 |
| --- | --- | --- | --- | --- |
| Story Brief | 作品创作契约 | 题材承诺、世界前提、主题问题、结局承诺、叙述声音 | `ArtifactStore.story_brief` | Character Bible、Summary |
| Character Bible | 冻结人物编排 | 谁承担何种叙事职责、关系、人物弧、首次出现窗口 | `ArtifactStore.character_bible` | Summary、Outline、Detail、Text |
| Summary | 全书故事脊柱 | 开端到结局的因果链和人物结局是否成立 | `ArtifactStore.summary` | Outline |
| Outline | 分卷节拍图 | 各卷目标、关键转折、人物区间和线索窗口 | `ArtifactStore.outline` | Detail |
| Detail | 章节施工图 | 每章目的、场景转折、义务和跨章交接 | `ArtifactStore.detail` | Text |
| Text | 冻结章节正文版本 | 接受、人工编辑、提出定向修订或保留分支 | `ChapterStore`，经 Evidence 后提交 Outbox | 下一章、Cover、Export |
| Cover | 封面选择 | 视觉 brief 与最终资产 | `AssetStore` | Export |
| Export | 可复现导出清单 | 格式、章节版本、封面和元数据 | `ExportStore` | 无 |

### 5.2 为什么必须新增 Character Bible

当前 Info 同时承担书名、简介、世界观、人物、关系、voice 和风险，后续 Outline 还可新增人物，Detail 又可新增 NPC。结果是人物权威随阶段漂移，UI 只能把不同阶段的推断叠成关系图。

Character Bible 的产品价值不是“多一个页面”，而是建立正文前唯一角色注册表：

- 主角、重要配角：必须命名并冻结职责、目标、内在缺口、关系和人物弧；
- 功能角色：可以命名或保留功能占位，但必须声明承担的剧情功能和使用边界；
- 必要 NPC：以角色槽位冻结用途、首次出现窗口和不得承担的关键功能，可在 Detail 命名，但不能升级职责；
- Outline、Detail、Text 只能引用 `character_id`；
- 新人物、职责升级、关系重定向或首次出现窗口变化必须生成 `CharacterChangeProposal`，绑定触发证据、影响章节和受影响 Artifact，经 interrupt 明确批准后创建新 Character Bible 版本；
- 仅拼写、显示名和 UI 布局不属于人物语义变更，由确定性投影处理。

模式取舍：Deep 与 Balanced 必须人工确认 Character Bible；Fast 可按冻结策略自动接受首版，但必须产生版本和决策回执，且在正文前完成，不能边写边增补重要角色。

## 6. Artifact vNext：核心、投影与 sidecar

### 6.1 分类规则

字段只有满足以下条件才进入核心 Artifact：用户会编辑或批准；下游创作语义不可从其他权威确定性得到；改变它会使下游失效。

其余字段归类：

- **Projection**：由核心 Artifact、BookScalePlan 或领域账本确定性计算，可随时重建；
- **Runtime sidecar**：调用、预算、审稿、哈希、checkpoint、SSE、候选和写回状态；
- **小调用 / 工具结果**：只服务一个窄决策的临时提案，不扩充主 Artifact；
- **删除**：仅为 UI 方便、重复语义、自评分、冗余摘要或兼容旧版本存在的键。

### 6.2 Story Brief

核心 Artifact：

```text
StoryBriefArtifact {
  title
  premise
  story_promise { genre, audience, tone }
  world_rules[]
  thematic_question
  ending_promise
  voice { viewpoint, tense, texture, avoid[] }
  cast_requirements[] { function, importance }
}
```

- Projection：tags、one-liner、世界观卡片、风险提示、人物槽位数量、标题候选历史。
- 小调用：题材资料提炼、标题候选、风险审读；结果只作为候选或 Evidence。
- 删除：`title_candidates`、`synopsis`、`downstream_constraints`、`risk_notes`、重复 voice 派生字段、在 Info 内展开的完整人物弧与关系。

### 6.3 Character Bible

核心 Artifact：

```text
CharacterBibleArtifact {
  characters[] {
    id, name, tier, narrative_function,
    external_goal, inner_need,
    arc { start, turning_point, end },
    first_appearance_window,
    hard_boundaries[]
  }
  relationships[] { source_id, target_id, nature, initial_state, pressure }
  npc_slots[] { id, function, first_appearance_window, limits[] }
}
```

- Projection：关系图、阵营图、章节 cast、人物卡摘要、未出场/即将出场列表。
- 小调用：角色方案候选、关系冲突检查、弧线完整度审读。
- Sidecar：变更提案、批准回执、版本依赖、影响分析。
- 删除：活动分数、UI 坐标、模型自评、每阶段重复 `character_shift` 总表、自由文本 `relations`。

### 6.4 Summary

核心 Artifact：

```text
SummaryArtifact {
  beats[] { id, phase, event, consequence }
  climax
  resolution
  character_outcomes[] { character_id, outcome }
}
```

- Projection：完整梗概文本、结构时间线、core conflict、key turns、覆盖率。
- 小调用：因果缺口审读、结局承诺对账。
- 删除：与 beats 重复的 `full_synopsis`、`act_structure`、`key_turns`、`consistency_checks`。

### 6.5 Outline

核心 Artifact：

```text
OutlineArtifact {
  volumes[] {
    id, chapter_window, objective,
    turns[] { id, event, consequence },
    ending_state,
    character_windows[] { character_id, entry_state, exit_state, turn_id },
    thread_windows[] { thread_id, kind, action, chapter_window }
  }
}
```

- Projection：卷卡、节奏条、章节分配、关系变化图、伏笔时间线。
- 确定性来源：卷数和章区间来自 `BookScalePlan`，模型不得另造。
- 小调用：按卷生成 turns；各卷可独立调用，随后确定性合并和引用校验。
- 删除：自由新增 `new_characters`、重复 opening/development/midpoint/climax/resolution 文案、UI 专用 rhythm 分数。

### 6.6 Detail

核心 Artifact：

```text
DetailArtifact {
  chapters[] {
    id, number, purpose, pov_character_id,
    scenes[] { id, location, goal, obstacle, turn, outcome },
    obligations[] { kind, ref_id, action },
    handoff { unresolved_actions[], emotional_carryover[], next_pressure }
  }
}
```

- Projection：稳定 beat/action ID、章节状态 in/out、连续性热图、角色出场表、事实/伏笔/Wiki 预览、章节字数预算。
- 确定性代码：章节号、卷归属、前后 handoff 链、引用集合、关系图投影、签名。
- 小调用：按卷或固定小批生成章节；引用修正、人物弧检查和线索窗口检查返回 Proposal，不直接改 Artifact。
- 删除：`schema_version=1|2|3`、`character_shift` 兼容投影、`character_beats`/`relationship_beats` 的重复状态快照、`wiki_candidates`、`fact_reveals`、`foreshadow_actions`、自动新增 `new_npcs`、为校验堆叠的 lineage/repair 键。事实、Wiki 和伏笔变化应在正文后从证据生成提案，而不是在 Detail 假装已发生。

### 6.7 Text

核心 Artifact：

```text
ChapterArtifact {
  chapter_id
  version_id
  title
  content
  author_status
}
```

- Projection：字符数、字数区间、hash、摘要、diff、阅读时间、段落索引。
- Sidecar：ContextSnapshotRef、ProviderReceipt、ReviewBundle、RevisionProposal、EvidenceBundle、WritebackReceipt、checkpoint_id。
- 小调用：生成、固定角色并发审稿、章后证据抽取、摘要；每项独立预算和回执。
- 删除：在章节对象内嵌 `quality_report`、`model_review`、`editorial_pass`、`preference_review`、`narrative_verification`、`wiki_writebacks`、`character_shift`、`foreshadow_updates`、版本历史和 UI 状态。

字数政策：目标和软区间只影响 Prompt 与报告；位于软区间外只产生 warning。只有空输出、Provider 截断、低于可读最小值或高于灾难上限才进入 interrupt。禁止因轻微长短自动补写、删段或压缩。

### 6.8 Cover 与 Export

Cover 核心：`CoverArtifact { brief, selected_asset_id }`。prompt、候选排序、质量摘要、尺寸和 Provider 回执进入 sidecar/AssetStore。

Export 核心：`ExportArtifact { format, chapter_version_ids[], cover_asset_id, metadata }`。文件名、manifest、校验、包大小和下载状态由确定性导出器生成，不调用模型。

### 6.9 八阶段实现闭环矩阵

下表同时约束 Prompt、Provider 返回、用户决策、领域写回和前端投影。`revision_request` 只在用户明确要求定向换稿时出现，并携带不可变来源；它不是失败兜底。

| 阶段 | Provider 唯一返回 / 调用拆分 | 唯一 Prompt material keys | 用户决策与正式写回 | 前端权威投影 |
| --- | --- | --- | --- | --- |
| Info | 1 个 `StoryBriefArtifact` | `project_brief`、`book_scale_plan`；仅已选择知识库时有 `source_pack`；可选 `revision_request` | Fast 自动接受；Balanced/Deep 接受、定向换稿或取消；提交 `ArtifactStore.info` | 创作契约表单、世界规则、声音约束、来源采用状态 |
| Characters | 1 个 `CharacterBibleArtifact` | `book_scale_plan`、`story_brief`；可选 `revision_request` | 冻结角色职责、关系、弧线与首次出现窗口；提交 `ArtifactStore.characters` | 分层人物名册、档案编辑器、关系矩阵、NPC 槽位、出场窗口与只读关系图 |
| Summary | 1 个 `SummaryArtifact` | `book_scale_plan`、`story_brief`、`character_bible`；可选 `revision_request` | 确认因果链、高潮、结局及全部主角/重要配角结局；提交 `ArtifactStore.summary` | 故事脊柱、因果节拍、人物结局对账 |
| Outline | 单卷时 1 次；多卷时每卷 1 次，每次只返回一个 `volumes[]` 项，再确定性聚合 | `book_scale_plan`、`story_brief`、`character_bible`、`summary`；分卷调用增加 `target_volume`；可选 `revision_request` | 确认卷目标、转折、人物/线程窗口；提交完整 `ArtifactStore.outline` | 分卷节拍表、只读章节区间、人物窗口和线索窗口 |
| Detail | 总章数不超过 8 时 1 次；否则按最多 8 章一批，每批只返回冻结目标章节，再确定性聚合 | `book_scale_plan`、`story_brief`、`character_bible`、`summary`、`outline`、`obligation_registry`；分批增加 `target_chapters`；可选 `revision_request` | 确认章节目的、场景、义务和 handoff；提交完整 `ArtifactStore.detail` | 高密度章节施工表、场景编辑、冻结义务选择、跨章交接；不提供正文前 Wiki 写回 |
| Text | 相邻章节严格串行；每章 1 次 `ChapterArtifact` 生成，随后 3 个冻结角色并发审稿和 1 次 Evidence 抽取；审稿/Evidence 都是窄 sidecar，不并入正文 JSON | `book_scale`、`story_constraints`、`character_bible`、`summary_commitments`、`volume_plan`、`chapter_plan`、`previous_handoff`、`previous_accepted_chapter`；可选 `revision_request` | 接受、人工编辑、定向换稿或取消；提交不可变 `ChapterStore` 版本，Evidence 经 Outbox 后才可进入 Canon/Wiki | 正文编辑器、三路审稿、Evidence 和写回事务状态；不显示原始 Graph State |
| Cover | 1 次文本调用只返回 `CoverBrief`；随后按冻结 `candidate_count` 独立生成图片资产；代码组装 `CoverArtifact` | `story`、`cast`、`narrative_arc`、`volume_objectives`、`chapter_motifs`；可选 `revision_request` | Fast 选择首个不可变资产；Balanced/Deep 选择 brief 与资产；提交 `ArtifactStore.cover` 和 AssetStore ref | brief 表单、候选资产轨、选中状态、生成回执与导出就绪状态 |
| Export | Provider 调用为 0；代码从已接受章节版本、封面资产和冻结导出偏好构建 `ExportArtifact` | 无，确定性 context 为 `{target: export, sources: {}, material: {}}` | Fast 自动接受；Balanced/Deep 只允许确认或取消，可在确认前编辑格式/元数据，不允许“换一稿”；提交 `ArtifactStore.export` 并物化 `ExportStore` 回执 | 格式与元数据表单、不可变版本集合、manifest、校验、包状态和下载 |

任何分卷/分批调用都先产生带 `operation_key`、请求签名和 Provider receipt 的单元结果；只有全部单元通过目标范围、引用和合同校验后才确定性聚合。部分成功不能成为候选 Artifact，也不能进入下一阶段。

### 6.10 稳定 JSON 返回协议

1. Provider 绑定、模型、Prompt、输出 schema 和结构化能力策略在 Run 创建时冻结。优先使用 Provider 声明支持的 strict JSON Schema；显式配置为 `json_object` 或 `prompt_only` 的 Provider 仍执行同一接收合同，运行时不得因失败降级输出模式、切换 Provider 或切换模型。
2. 文本响应去除首尾空白后必须是 **一个完整 JSON object**。只调用一次标准 `json.loads()`；顶层数组、Markdown fence、前后解释、多个对象、截断 JSON 和空响应全部拒绝。
3. 不做花括号截取、balanced-object 搜索、语法 repair、字段 alias、旧版本 converter、默认值注入或未知字段丢弃。诊断只记录长度、hash、顶层类型、键名和错误码，不保存或回灌失败正文。
4. 所有核心键都必须显式出现；语义允许为空时返回空字符串或空数组，不能省略。所有 vNext 模型使用 `extra="forbid"`，缺键、额外键、类型错误、枚举错误、范围错误和跨 Artifact 引用错误都形成 `candidate failure`。
5. Provider 层只证明“完整对象”；Artifact 层再执行 Pydantic schema、BookScalePlan、Character Bible、obligation registry、章节版本和资产集合约束。两层都通过才写成功 operation receipt 和不可变 candidate。
6. 合同失败进入 LangGraph 明确 failure/interrupt，保留脱敏 evidence ref。用户可取消，或修正 Prompt/Provider 配置后创建新的明确 attempt；不得把失败响应修成看似成功的 Artifact。

## 7. LangGraph 原生运行设计

### 7.1 唯一 State

Graph State 只保存路由所需的小型值和领域引用：

```text
NarrativeRunState {
  run_id, project_id, workflow_revision, quality_mode
  book_scale_plan_ref
  artifact_refs, candidate_artifact_refs
  chapter_version_refs
  stage_attempts, chapter_attempts
  stage_revision_directions, chapter_revision_directions
  active_stage_id, active_chapter_id, active_chapter_number
  stage_status, status, domain_revision
  decision_ids, decision_actions
  pending_operation_refs, review_operation_refs
  pending_evidence_refs, pending_writeback_ref
  failure { node_id, code, retryable, evidence_ref } | null
}
```

禁止进入 State：正文全文、全量 Wiki/Canon、UI 展开状态、SSE 历史、Provider 密钥、审稿全文、候选全集、派生关系图和旧 Run JSON。节点按 ref 读取不可变快照。

权威层级：

| 数据 | 唯一权威 | 其他层的权限 |
| --- | --- | --- |
| active node、pending task、interrupt、resume | LangGraph checkpointer | SSE/UI 只读投影 |
| Artifact 与版本 | ArtifactStore | Graph 只存 ref |
| 章节正文版本 | ChapterStore | Review/Context 只读冻结版本 |
| Evidence | EvidenceStore | Reviewer 只写提案，Reconciler 提交 |
| Canon | CanonStore | 只能接受 Evidence 绑定的事务 |
| Wiki | WikiStore | Canon/用户批准后的可检索投影 |
| 写回事务 | Domain Outbox | Graph 等待 receipt，不直接跨库乱写 |
| 预算/Provider 调用 | BudgetLedger / ProviderReceipt | Graph 根据 receipt 路由 |
| SSE 历史 | EventProjection | 不能用于恢复或决定 next node |

### 7.2 Global Graph

```text
START
  -> load_run
  -> story_brief_subgraph
  -> character_bible_subgraph
  -> summary_subgraph
  -> outline_subgraph
  -> detail_subgraph
  -> chapter_loop_subgraph
  -> cover_subgraph
  -> export_subgraph
  -> finalize_run
  -> END
```

每个创作阶段子图采用同一骨架：

```text
load_context -> generate_candidate -> validate_contract
  -> decision_policy
     -> accept -> commit_artifact -> checkpoint_stage
     -> regenerate(direction) -> increment_attempt -> generate_candidate
     -> cancel -> END
```

Balanced/Deep 的 `decision_policy` 使用 `interrupt()`；Fast 自动接受但仍生成同一 `decision.resolved` 回执。Export 虽是确定性 Artifact，Balanced/Deep 仍需确认格式、元数据和已接受版本集合，但只允许 `accept/cancel`，不允许 `regenerate`；Fast 自动接受并生成回执。人工编辑先保存新的不可变 candidate ref，再通过同一 accept decision 提交。`regenerate` 必须带非空方向，不是异常 fallback；Provider 失败进入显式 failure edge，不自动换 Provider 或模型。

### 7.3 Chapter Subgraph

```text
prepare_chapter
  -> generate_prose
  -> plan_review_roles
  -> Send(review_role...)        # 同一章节版本并发只读
  -> evaluate_review_gate
  -> chapter_author_decision
     -> accept -> commit_chapter
     -> regenerate(direction) -> generate_prose(attempt + 1)
     -> cancel -> END
  -> extract_evidence
  -> enqueue_domain_commit
  -> await_commit_receipt
  -> next chapter | finish text stage
```

约束：

- 第 N+1 章必须消费第 N 章已提交的 Reality Snapshot；相邻章节不并行；
- 审稿角色在 `plan_review_roles` 一次冻结，不得失败后增加角色或进入 `fallback_review_waves`；
- 所有 Reviewer 读取同一个 `ReviewInputSnapshotRef`；输出只包含 Finding/Evidence，不修改正文；
- required/optional 角色不可用和 blocking finding 都进入统一 `chapter_author_decision.reason`，由作者接受、定向换稿或取消；
- Balanced/Deep 每章都必须经过作者 decision；Fast 走相同节点自动接受并生成回执；
- 人工编辑和 Provider 修订都是独立候选，不覆盖 base；定向修订绑定 `direction` 与 `source_version_ref`，attempt 2 必须产生新版本并重新跑全部审稿；
- 长度 warning 不进入自动修订；硬事实冲突、截断和无证据写回才可阻断；
- Provider 调用前创建 operation key，调用后持久化 receipt；节点重放先读 receipt，禁止重复扣费。

### 7.4 Interrupt 合同

当前生产允许的 interrupt 类型只有：

- `stage_artifact_decision`
- `chapter_author_decision`

人物变更、Canon 冲突、预算扩展等未来决策必须先扩展同一 Graph/API 合同并完成评审，不能通过临时 route、旧 decision alias 或直接改 state 实现。

payload 必须是小型、JSON 可序列化对象：`decision_id`、`thread_id`、`node_id`、Artifact/Evidence ref、`domain_revision`、允许动作和影响摘要。API 用同一 `thread_id` 调用 `Command(resume={...})`；不得直接修改 checkpoint 或 Run JSON。

因为 interrupt 恢复会从节点开头重放：

- interrupt 前的写操作必须使用 Outbox/operation key 幂等；
- 一个节点内 interrupt 顺序固定；
- 不捕获 interrupt 异常；
- 大对象只传 ref；
- UI 的“已确认”必须来自 resume 后的 `decision.resolved`，不能先乐观写正式状态。

### 7.5 Checkpoint 与恢复

- `thread_id = run_id`，subgraph 使用稳定 namespace；
- 每个 super-step 自动 checkpoint，Stage/Chapter 提交后额外写领域 receipt；
- API 恢复只允许 `Command(resume=...)` 或从明确 checkpoint 创建新分支；
- 原 thread 的已提交 Canon/Wiki 不做破坏性回滚；回到历史 checkpoint 必须创建新 Domain Branch；
- pending writes 可复用同一 super-step 已完成的 Reviewer，但 Provider 与 Outbox 仍以业务 receipt 防重；
- 删除 `/resume` 中的手写 checkpoint 解锁和 `recovery_state` 路由；
- 进程崩溃、SSE 断线和浏览器关闭都不得改变 graph thread 的可恢复性。

## 8. Memory、Wiki、Canon 与 RAG

### 8.1 四类系统不再互相代称

| 系统 | 内容 | 写入条件 | 对创作的约束强度 |
| --- | --- | --- | --- |
| Planning Ledger | Brief、Character Bible、Summary、Outline、Detail 的未来计划 | 用户/模式接受 Artifact | 软约束；正文可提出有证据变更 |
| Evidence Ledger | 正文可定位片段、来源版本、抽取提案 | 章后抽取 + 确定性绑定 | 证据，不自动等于 Canon |
| Canon | 已发生且经 reconcile/批准的世界事实 | 事务提交 | 高权威，但允许显式修订分支 |
| Wiki | 面向检索和用户浏览的 Canon 投影 | Canon commit 后 Outbox | 可重建，不是事实源 |
| Runtime Memory | checkpoint、receipt、预算、节点结果 ref | Graph/运行端口 | 只影响执行，不影响故事真实 |
| User Knowledge RAG | 用户上传资料的检索片段与来源 | 用户选中文档，前置规划查询 | 建议/素材，不能成为正文已发生事实 |

### 8.2 RAG 决策

- 仅当用户上传、索引并明确选中知识库文档时启用；
- 仅允许 Story Brief、Character Bible、Summary、Outline、Detail 的规划节点读取；
- 查询、命中、来源、摘要和被采用项都要有 Evidence ref；
- 正文节点不做开放式向量检索，只读取已批准规划 Artifact、Canon、最近章节摘要和明确 handoff；
- 如写作中确需外部资料，先产生 `ResearchRequest` 并 interrupt，由用户批准后在规划侧生成 Source Pack，再创建新 ContextSnapshot；
- 联网搜索与用户知识库是不同来源，默认不混成无来源摘要。

### 8.3 低敏感原则

- Memory/Wiki 的缺失默认降级为提示，不应阻止写作；
- 只有与 Character Bible 硬边界、已提交 Canon 或明确安全/法律约束冲突时才形成 hard finding；
- 伏笔窗口、关系趋势和风格偏好默认 warning；
- 不做模糊字符串命中后自动改正文；
- 所有自动派生投影可删除重建，不能拥有比源 Artifact 更高权威。

## 9. SSE 与 API

### 9.1 执行与观察解耦

当前 SSE generator 拥有 Runner 生命周期。vNext 改为：

- `POST /api/runs`：创建不可变 Run definition；
- `POST /api/runs/{run_id}/start`：仅从 `created` 调度唯一 compiled graph；
- `GET /api/runs/{run_id}`：读取 Graph snapshot + 领域 read model；
- `GET /api/runs/{run_id}/events?after=<sequence>`：只观察、可断线重连；
- `POST /api/runs/{run_id}/decisions/{decision_id}`：校验 revision 后 `Command(resume=...)`；
- `POST /api/runs/{run_id}/branches`：从 checkpoint 创建显式新分支；
- 不再提供直接改 state 的 approve/resume/recovery API。

SSE 稳定事件 envelope：

```text
{
  event_id, sequence, occurred_at,
  run_id, thread_id,
  type, stage_id, node_id, chapter_id,
  status, payload_ref | payload,
  checkpoint_id
}
```

后端从 LangGraph 稳定的 `updates/messages/custom/checkpoints/tasks` stream mode 映射领域事件；不把 raw Graph State 直接推给浏览器，也不以仍属实验性的 `stream_events(version="v3")` 作为生产 SSE 合同。Provider token 只映射为 `provider.delta`，节点状态、interrupt、写回和 checkpoint 分别映射：

- `node.started/completed/failed`
- `artifact.candidate_ready/committed`
- `decision.required/resolved`
- `review.started/completed/unavailable`
- `evidence.proposed`
- `writeback.queued/committed/failed`
- `checkpoint.saved`
- `branch.created`
- `run.started/completed/failed`

EventProjection 负责 sequence、短期重放和前端读模型；Graph 绝不能从这些事件反推 next node。

## 10. 前端同步设计

### 10.1 导航

`stageRoutes.ts` 从七阶段改为八阶段，增加稳定路由 `/run/characters`：

```text
info -> characters -> summary -> outline -> detail -> text -> cover -> export
```

导航状态只来自后端 read model：`locked / available / running / awaiting_decision / completed / failed`。URL 选择不修改运行状态，不能通过访问后续路由跳过 graph edge。

### 10.2 Artifact 工作台

| 阶段 | 主编辑面 | 辅助投影 | 不显示 |
| --- | --- | --- | --- |
| Info | 创作契约表单 | 世界规则、voice 摘要、来源 | 原始 JSON、完整人物编辑 |
| Characters | 人物表 + 关系矩阵 + 出场窗口 | 关系图、章节 cast 预览、变更影响 | 运行日志堆叠、模型自评分 |
| Summary | 故事脊柱时间线 | 人物结局对账、因果缺口 | 重复 full synopsis 字段 |
| Outline | 分卷节拍表 | 体量分配、人物区间、线索窗口 | 自由新增角色 |
| Detail | 章节/场景施工表 | handoff、义务、引用和覆盖投影 | Wiki/Canon 假写回、v1/v2 字段 |
| Text | 章节编辑器 | Review、Evidence、写回状态抽屉 | 全量 Graph State、自动删改 |
| Cover | brief + 资产选择 | 生成回执、质量摘要 | Provider 内部 payload |
| Export | 版本/格式选择 | manifest、校验和包状态 | 模型配置 |

“保存到当前稿”只生成本地/候选 Artifact 版本；“确认并写回”才通过 decision/resume 进入 Graph commit。两者文案、状态和事件必须完全分开。

### 10.3 人物工作台

人物阶段是可编辑权威页，现有 `/bible/characters` 改为跨阶段只读投影与变更入口：

- 主区域按主角、重要配角、功能角色、NPC 槽位分组；
- 关系使用紧凑矩阵/列表，图只做辅助，不作为编辑数据源；
- 首次出现使用章节窗口控件，展示与 BookScalePlan 的冲突；
- 冻结后编辑会创建 `CharacterChangeProposal`，显示证据、受影响 Summary/Outline/Detail/未完成章节和重新确认范围；
- 不允许从关系图拖拽直接写语义。

### 10.4 运行观察与写回

- 运行观察显示当前 node、已完成任务、并发审稿 lane、预算和 checkpoint，不把内部调用细节塞进 Artifact 表单；
- 写回状态统一为 `not_proposed / proposed / queued / committed / rejected / failed`；
- Canon、Wiki、Character Bible 变更分别显示目标、证据和 transaction id；
- SSE 重连按 sequence 去重，不能用事件文案猜测 runtime phase；
- interrupt 出现时只展示服务端允许动作；提交后等待 `decision.resolved`；
- 390px 与桌面宽度都使用同一语义，窄屏把辅助投影放入抽屉，不删减决策信息。

## 11. 保留、迁移、删除与归档矩阵

### 11.1 运行时

| 当前对象 | 决策 | vNext 去向 / 删除条件 |
| --- | --- | --- |
| `workflows/runner.py`、`orchestration/stream.py` | 删除 | Global Graph 实际 `astream` 后删除，不保留 facade |
| `runtime/graph/runtime_engine.py` | 删除 | 只有 LangGraph，不再有 engine selection/flags |
| `chapter_shadow_*` | 删除 | 路由夹具改为 Graph 单元测试 |
| `chapter_dual_*`、`chapter_graph_commit_gate.py` | 删除 | 提取幂等思想后，由 Chapter Subgraph 直接执行 |
| `runtime/graph/stage_graph.py` | 替换 | 改为真实 Global/Stage Graph，不返回 plan 给 legacy |
| `orchestration/control.py` 轮询 | 删除 | `interrupt` / `Command(resume=...)` |
| 手写 `recovery_state`、checkpoint 解锁 | 删除 | Graph checkpoint/thread |
| `RunStore` 的命令/路由权威 | 删除 | Checkpointer + Domain Stores；仅保留新的只读 projection，不沿用旧类 |
| `api/sse.py` Runner 包装 | 替换 | 独立 Graph event projector + observer SSE |

### 11.2 合同与兼容

| 当前对象 | 决策 | 说明 |
| --- | --- | --- |
| Detail v1/v2/v3 union 和 `normalize_legacy_contract` | 删除 | vNext 只有一个无版本分支的当前合同；合同版本属于 Artifact metadata，不进 payload |
| Detail batch schema 升级/归一化/repair | 删除 | 无转换；无效输出形成显式 candidate failure |
| Outline/Detail 自动 reference/trajectory repair | 删除或改 Proposal | 不再静默改模型产物 |
| `fallback_review_waves` | 删除 | required/optional 角色失败走明确 edge/interrupt |
| Provider/model `fallback_targets` | 删除 | 调用绑定冻结 Provider；失败不暗换模型 |
| OpenAI-compatible 协议适配器 | 保留 | 它是用户显式配置的 IO adapter，不是运行 fallback |
| UI 旧字段猜测、事件别名、quality `legacy-v1` | 删除 | 前后端共享 vNext 类型与稳定事件 |

### 11.3 历史 Run

历史 Run 不迁移、不恢复、不转换成 vNext：

- 原 JSON、事件、附件和 graph_checkpoints 以内容哈希封存；
- 只允许独立 `archive/legacy_run_viewer` 读取原始格式并展示“不可执行/不可写回/不可恢复”；
- viewer 不导入 production runtime、Provider、Outbox、Canon/Wiki writer；
- 历史 Run 只在 `/api/archive/runs` 可见；生产 `/api/runs/{id}` 及 start/events/state/decision/branch/artifact 路由统一返回 404，不泄漏为可执行 Run；
- viewer 内允许按原 schema 专用渲染，但不得输出可交给 vNext 执行的转换结果；
- Run B-G 和 Phase 25 证据保留，用作测试夹具时只能脱敏、只读、零 Provider。

## 12. 迁移 Waves 与退出门

所有 Wave 都在服务停止、Provider 禁用的架构分支完成。不存在“新旧生产同时运行”的阶段。

### Wave 26.0：评审冻结（已完成）

- 产物：本文、Phase 25 废弃标记、仓库专属 Skill；
- 删除：旧文档的实现指导权，不删证据；
- 退出门：用户已明确批准 LangGraph 完全重构；生产 Provider 与真实 Run 仍需单独批准。

### Wave 26.1：历史隔离与合同断代（已完成）

- 建立只读 archive viewer 边界；
- 删除生产 Detail v1/v2 解析、schema 升级、alias/converter；
- 删除旧 Run 的 start/resume/approve/writeback 能力；
- 证据：`LegacyRunViewer` 仅挂载 `/api/archive/runs`；生产 Run API 对历史 id 返回 404；Phase 26 boundary/API tests 锁定只读能力和 v1/v2 缺席。

### Wave 26.2：Artifact vNext 与领域存储（已完成）

- 建立八阶段最小 Artifact、版本、依赖和 Domain Outbox；
- 把 projections/sidecars 从 `NovelRunState` 拆出；
- 删除 Summary/Outline/Detail/Chapter 对旧顶层 state 的重复写回和自动 repair；
- 证据：`artifacts_vnext.py` 只有八个当前模型；Artifact/Chapter/Evidence/Export/Outbox/Canon/Wiki 各自持有领域数据，Graph State 只保存引用和路由 sidecar。

### Wave 26.3：唯一 LangGraph Runtime（已完成）

- 实现 Global、Stage、Chapter、Review subgraphs 与持久 checkpointer；
- 删除 Runner、legacy stream、runtime selector、Shadow、Dual、commit gate、polling control、手写 recovery；
- 证据：所有生产 start/resume/branch 只经 `NarrativeExecutionService` 和 `NarrativeRuntime`；Runner、legacy stream、runtime selector、Shadow、Dual、commit gate 和轮询 control 已删除；Fake Provider 全图通过。

### Wave 26.4：Checkpoint、interrupt 与事务写回（已完成）

- 接入 operation receipt、Domain Outbox、Evidence reconcile 和显式 branch；
- 删除 RunStore 命令权威和重复章节/卷/Wiki flush 分支；
- 证据：SQLite interrupt 重启不重复 Provider 调用；checkpoint 分支隔离；operation receipt 防止阶段/正文/审稿重复调用；Evidence 失败保留已接受正文但不产生 Canon/Wiki 写回；人工编辑与定向换稿绑定不可变来源。
- 故障注入：Canon commit 前终止时无正式写回，重启后 Outbox 可提交；Canon 已提交但 Wiki 未投影时重启，Canon 不重复且 Wiki 补齐；并行审稿 super-step 中两个已完成 lane 作为 pending writes 恢复，仅重跑未完成 lane；`NarrativeExecutionService` 启动时只恢复有 checkpoint、无人工 interrupt 且仍有 next task 的 Run；required 与 optional reviewer 不可用进入同一作者 decision reason，不触发 fallback wave。
- decision 幂等：当前 interrupt/checkpoint 仍是路由权威，OperationStore 只持久化命令签名与完成回执，不把历史 decision 再复制进 Graph State；相同命令重复提交返回当前投影，不再次推进章节或写回，同一 decision 的不同命令在进入 `Command(resume=...)` 前拒绝，Run 不被误标为 failed。

### Wave 26.5：SSE 与前端八阶段切换（已完成）

- 执行与 SSE 观察解耦；更新 route、Artifact 表单、人物工作台、运行观察和写回状态；
- 删除旧 reducer phase 猜测、事件别名、七阶段表和 Story Bible 人物权威投影；
- 证据：SSE 已成为 `EventProjection` 观察器；八阶段 route、Artifact vNext 表单、人物工作台、Graph decision、运行观察与写回投影已切换；前端 `97 files / 348 tests`、TypeScript/Vite production build 通过。
- 生产配置语义已删除 `control_mode`、`info_step`、`checkpoint_stages` 和 `execution_mode`；`run_intent` 只保留 project brief、knowledge strategy 与 export preferences，冻结输入补齐 `narrative_profile`。前端不再伪造暂停、自动改写、未使用分数阈值或模式成本。
- Fast、Balanced、Deep 共用同一张图与固定三路审稿。Fast 自动接受阶段/章节 decision；Balanced 与 Deep 均在八阶段和每章等待人工 decision；Balanced 要求 continuity/character、允许 prose 不可用，Deep 要求三路 reviewer 全部返回。Balanced/Deep 均暴露八个阶段工作台，运行存在时 cockpit 是并列观察入口而不是阶段替代品。
- 浏览器退出门（2026-08-11）：隔离临时数据创建未启动生成的新项目；1440x900 与 390x844 均确认“创作立项”、独立“人物圣经”、八阶段导航和世界规则/人物冻结提示；两档 viewport 的 `scrollWidth` 分别等于 1440/390，无页面横向溢出或控件重叠；console 为 0 error / 0 warning，创建项目、workflow、knowledge、provider readiness API 均返回 200。一次旧 history 请求在路由切换时被浏览器取消，随后相同请求返回 200，不构成恢复或 SSE 故障。
- 截图：`output/playwright/phase26-browser/phase26-balanced-desktop-1440x900.png`、`output/playwright/phase26-browser/phase26-balanced-mobile-390x844.png`。没有点击“开始创作”，没有 Provider 生成调用。
- 人物恢复与编辑退出门（2026-08-11）：从 `characters` 的 LangGraph interrupt 检查点创建新分支后，目标 Run 依次投影 `branch.created`、`artifact.candidate_ready`、`decision.required`，历史页直接进入 `/run/characters`，没有重跑 Provider。1440x900 与 390x844 均真实编辑重要配角、关系矩阵和 NPC 槽位；桌面/移动页面 `scrollWidth` 分别等于 1440/390，关系与 NPC 宽表只在自身容器滚动；待决策按钮可用，console 为 0 error / 0 warning。当前候选稿与右侧“已冻结”人物基线使用不同文案，不把本地编辑伪装成正式写回。
- 人物截图：`output/playwright/phase26-browser/phase26-characters-desktop-1440x900.png`、`output/playwright/phase26-browser/phase26-characters-mobile-390x844.png`。`gpt-image-gen` 原型调用因网关只返回 URL、不符合 Skill 要求的 `b64_json` 合同而明确失败；没有下载 URL 兜底，也不把生图失败声明为原型完成。最终视觉证据来自真实前端浏览器状态。

### Wave 26.6：离线生产闭环（已完成）

- Fake Provider 完成三章、单卷、interrupt、并发审稿、失败恢复、分支和导出；
- 删除所有仅为测试保留的生产 fallback；
- 当前证据（2026-08-11）：后端 `278 passed`；前端 `97 files / 348 tests`；三章 Fast Fake Run 已验证 3 章串行、9 条审稿 lane、3 次 Evidence/Canon 写回和 Export；八阶段 JSON Schema 已证明所有核心键显式必填，缺键不再由 Pydantic 注入默认值；TypeScript/Vite production build、Python `compileall`、CSS audit、CSS split 与 `git diff --check` 均通过；无真实 Provider 调用。后端仅保留一条既有 Starlette deprecation warning，Vite 仅保留既有 `graph-3d-vendor` 大 chunk warning。
- 缺席证据：production source 不含 `runtime_engine`、`fallback_targets`、`fallback_review_waves`、`normalize_legacy_contract`、宽松 `generate_structured` 或 JSON 提取/修复入口；Phase 26 boundary tests 锁定旧文件和旧入口不可回归；closure audit 无 runtime legacy marker；仓库专属 Skill 通过 `quick_validate.py`。
- 新增证据：Phase 26 静态门禁止直接 `langchain*` 依赖和生产业务导入；Outbox 前后崩溃、并行 reviewer pending writes、required/optional 不可用和 API/Runtime decision 幂等矩阵已通过；`OperationStore` 是文本/图片 Provider usage 与安全 diagnostic 的唯一收据权威，Fake 全图精确投影 19 次调用、175 tokens、0 次失败，人工 decision 不进入 Provider 统计，SSE/read model/历史页只消费可重建投影；没有冻结计价表时成本明确为“未计价”而非伪造 `$0`。production closure audit 无 runtime legacy marker 或无效 pipeline 顶层目录；仓库专属 Skill 通过 `quick_validate.py`。本 Wave 的离线退出门已关闭。

### Wave 26.7：真实 Provider 验收（已获推送后执行授权，尚未执行）

只有 26.0-26.6 通过、提交推送成功且仍满足限额和脱敏收据边界后执行：

1. 各阶段单次 schema probe，失败即停止，不切换 Provider；
2. 新建全新三章 Run，不恢复 Phase 25 旧 Run；
3. 通过后新建单卷 8-12 章 Run；
4. 完成人工盲读、成本、重复调用、恢复和写回审计后，才讨论全书；
5. 任何连续两次同类失败都停止局部补丁，回到 State/Node/Artifact/Context/Provider contract 根因评审。

## 13. 测试与验收矩阵

### 13.1 静态与合同

- production import graph 不含 `legacy_run_viewer`、Shadow、Dual、runtime selector；
- Detail payload 无 v1/v2/v3 union、兼容 validator、alias 或 converter；
- 八阶段前后端 ID、路由、Artifact schema、decision 和事件生成自同一合同；
- 每个 Node 声明 input refs、output refs、副作用、operation key、可重放性和失败 edge；
- State 不含正文全文、Wiki/Canon 全量或 UI 状态。

### 13.2 Graph 与恢复

- 每条 conditional edge、有限循环和 terminal state 可达；
- interrupt 后使用同一 thread resume，重放不重复副作用；
- 并行 reviewer 的 pending writes 可恢复，所有输出绑定同一 snapshot；
- required/optional reviewer 不可用行为不同且无 fallback wave；
- checkpoint 分支不改变原 Canon/Wiki；
- SSE 断开、进程终止、Provider 超时、Outbox 提交前后崩溃逐点注入。

### 13.3 Artifact 与叙事

- Character Bible 冻结后，Outline/Detail/Text 的未知 `character_id` 全部拒绝；
- NPC 槽位命名不自动升级人物职责；
- 人物变更提案准确列出受影响 Artifact，并要求明确 decision；
- Detail handoff 前后连通，章节数严格来自 BookScalePlan；
- 正文事实提案必须绑定可定位证据；无证据不进入 Canon；
- RAG 只在已选择用户知识库且处于规划阶段时可调用；正文节点测试断言检索次数为 0；
- 软字数偏差只告警，不触发 Provider 或文本修改。

### 13.4 真实 Provider 通过标准

三章和单卷均需同时满足：

- `duplicate_provider_operations = 0`、`duplicate_domain_commits = 0`；
- 中断恢复后 operation receipt、budget ledger、checkpoint 和 SSE sequence 对齐；
- 所有章节引用已冻结角色，无未批准职责漂移；
- required review 全部完成或经过用户明确决策；
- Canon/Wiki 每条正式写回均可追到正文版本和证据 span；
- 轻微字数浮动没有自动补写/删改；
- 人工盲读单独记录连续性、人物可信度、结构、语言和结局兑现；模型自评分不能替代；
- 三章通过不等于单卷通过，单卷通过不等于全书或投稿通过。

## 14. 明确不做

- 不在离线退出门关闭、用户另行批准前调用真实 Provider；
- 不把旧 Run 原地迁移到新 graph；
- 不保留一个“紧急 legacy 回退”开关；
- 不为旧字段增加 converter、alias、normalizer 或读取 fallback；
- 不把 LangChain Agent、PlotPilot engine 或 FictionForge 双管线包进 LangGraph 节点；
- 不把 Checkpointer、Memory、Wiki、Canon、RAG 合成一个万能状态库；
- 不让模型直接决定事实权威、人物注册、写回或预算扩展；
- 不用自动改写掩盖字数、审稿或 Provider 合同问题；
- 不用本地全绿宣称真实 Provider、单卷、全书或投稿验收完成。

## 15. 当前评审结论与下一次退出门

以下取舍已经批准并进入实现：LangGraph 是唯一生产运行时；生产代码默认禁止直接 LangChain API，高层 `langchain` 包不作为直接依赖；新增 Character Bible 并采用严格串行八阶段；Detail vNext 与历史 Run 断代；Memory/Wiki/Canon/RAG 采用低敏感、证据驱动边界。

用户已经批准在完整离线门通过并推送 GitHub 后执行 **Wave 26.7 真实 Provider 验收**。在推送成功前继续保持：

1. 不启动或恢复 Phase 25 历史 Run；
2. 不调用任何真实文本、图像、搜索或嵌入 Provider；
3. 不把本地测试/build 通过写成真实输出、浏览器体验或文学质量已验收；
4. 真实验收只创建全新 Run，设置成本上限，保留脱敏 receipt，并在失败时停止而非切换 Provider 或恢复 legacy。
