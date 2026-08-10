# ADR-001：LangGraph 只接管执行控制面

- 状态：已接受，作为 Phase 20 Wave 20A 的架构基线
- 日期：2026-08-06
- 范围：Yotsuba Ink 新 Run 的运行时演进，不迁移旧 Run

## 背景

Yotsuba Ink 已经具备阶段路由、章节顺序生成、并行审稿、预算、人工确认、SSE、恢复和 Canon/Wiki 写回。现有问题不是缺少一个有向图，而是这些控制策略分散在 Runner、orchestration、quality、usage、acceptance 和 RunStore 中，导致角色、预算、恢复和事件状态可能从不同来源推导。

同时，小说事实不能交给一个自由决策的 Supervisor Agent。计划、正文现实、审稿证据、Wiki 投影和 Canon 正式事实有不同的权威等级；如果 Agent 可以直接改共享状态，就会形成“自己提出、自己检索、自己证明”的循环。

## 决策

采用“LangGraph 控制面 + Yotsuba Ink 叙事领域内核”的组合：

```text
API / UI
  -> Yotsuba Domain Command
  -> LangGraph Global / Stage / Chapter Graph
  -> Context Broker / Provider Adapter / Reviewer
  -> Artifact / Evidence / Canon / Wiki Domain Store
```

### LangGraph 可以负责

- Global、Stage、Chapter 和 Review 子图的显式节点、条件边和有限循环；
- 章节内的顺序控制、并行只读 Reviewer、人工 interrupt、恢复和 checkpoint；
- graph node 与现有领域 SSE 事件之间的适配；
- 新 Run 的 `runtime_engine=langgraph` 运行选择和可解释的节点 receipt。

### LangGraph 不负责

- 事实权威、人物关系、世界观、Wiki、Canon 或 Reality Reconciliation；
- Prompt 文案、Context 裁剪规则和模型供应商协议；
- 直接写正文、Artifact、Canon/Wiki 或共享预算；
- 替代 RunStore 的领域事件、正式写回和导出状态；
- 自由修改工作流、后续 Detail 或阶段合同。

## Agent 写权限

所有模型或子 Agent 只返回结构化 `Proposal` 或 `Evidence`：

- Writer 返回正文候选和章后提案，不直接提交 Canon/Wiki；
- Retriever 返回带来源、版本和签名的候选证据，不决定事实可信度；
- Reviewer 返回绑定 `ReviewInputSnapshot` 的诊断，不直接修改正文；
- Context Broker 和确定性协调器决定哪些提案可以进入下一步；
- Reality Reconciliation 验证正文证据后，才允许 Canon/Wiki 正式写回。

## 运行与持久化边界

- `RunStore` 在 Shadow/Dual 阶段继续是领域事件和兼容读模型；
- Run 创建时将 `runtime_engine` 和可审计的选择原因冻结在输入快照中；旧 Run 恢复不得被新请求覆盖；
- LangGraph Checkpointer 只保存执行线程、interrupt 和恢复所需的控制状态，不是小说事实数据库；
- Artifact、Evidence、Canon、Wiki 和 Domain Outbox 保持独立；
- Provider 请求必须绑定幂等 operation key 和 NodeReceipt；重启先检查 receipt，禁止盲目重发；
- SSE 只暴露稳定领域事件，前端不感知底层是 legacy Runner 还是 LangGraph。

## Run 兼容与回滚

- 创建 Run 时冻结 `runtime_engine=legacy|langgraph`，运行中不能切换；
- 旧 Run 永远按 legacy 恢复，不原地迁移、不重签历史、不重写正文；
- LangGraph 只对 feature flag 开启的新 Run 生效；
- 新引擎失败时创建同输入的 legacy Run，保留原失败 Run 的审计记录；
- Canon/Wiki 已正式提交后不能静默回滚，只能建立修订分支；
- Checkpointer 故障不能自动退回并重复 Provider 调用，必须先检查 NodeReceipt 和领域事件。
- 当前 JSON 运行时提供 `RunStoreCheckpointSaver`、`FileProviderOperationCache` 和 `FileDomainCommitPort` 作为可替换端口；它们只保存控制面 receipt/checkpoint，正式跨域事务仍由 Domain Outbox 负责。

## Agent 拓扑约束

- 相邻章节不并行生成；第 N+1 章必须消费第 N 章完成对账后的状态；
- 同一冻结稿上的 Reviewer 可以并行，但最多四个固定职责：语义主审、结构触发的硬专项、因果/终章专项和可选文学冷读；
- 文学冷读是诊断角色，不可用时不得阻断硬门；
- Reviewer 不得因分歧自动增加投票角色；
- 每次局部修订最多一次，修订后只复检受影响角色，且必须保留原始候选和签名。

## 迁移顺序

1. 在 legacy runtime 内冻结 `ContextSnapshot`、`AgentProposal`、`EvidenceLedger`、`ReviewLaneSpec` 和 `NodeReceipt`；
2. 用脱敏 B1 失败夹具做零 Provider Shadow 路由回放；
3. 通过固定三章的 Shadow 后，再添加可选 LangGraph 依赖和 Chapter Graph Dual Run；
4. 新 Run 的 Chapter Graph 稳定后，才迁移 Stage/Global Graph；
5. 完成单卷 8-12 章验收后，才允许完整长篇运行。

## 取舍与后果

选择控制面而不是全量 Agent 抽象，会保留更多确定性领域代码，短期迁移速度较慢；但它能保持阶段产物合同、预算和写回门稳定，避免“换框架”掩盖 Context 和连续性问题。LangGraph 的 checkpoint 也不能单独证明文学质量，三章 A/B、单卷验收和人工盲读仍是必要门槛。

暂不引入 LangChain AgentExecutor、CrewAI 或 AutoGen；不把 PlotPilot 源码复制到产品树，只吸收其结构化 Story Bible、章后状态和上下文分层思想。

## 验收与退出

本 ADR 的实现退出条件：

- B1 零 Provider 回放不丢硬角色、不重复正文生成、不扩大 generation/revision 预算；
- 同一恢复请求幂等，诊断角色不升级为阻断角色；
- Shadow 只比较路由、门、预算、事件和写回提案，不修改原 Run；
- 所有 Reviewer 使用同一冻结 Snapshot，所有正式写回经过 Reality Reconciliation；
- 旧 Run 的 legacy 恢复路径可继续使用。
