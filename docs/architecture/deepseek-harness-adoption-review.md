# DeepSeek Harness 插件思想评审

状态：2026-08-15 已完成源码级评审、Wave H1 本地实现、浏览器验证与真实 Provider 单阶段换稿；当前 Run 停在 Volumes 待决策。本文只决定 Yotsuba Ink 可采用的工程思想，不引入第二套运行时。

## 评审基线

- 官方仓库：`deepseek-ai/deepseek-harness`
- 审查提交：`47f943859bef60e4160492346772ded9b24f765a`
- 提交时间：2026-08-13 11:38:46 UTC
- 仓库源码版本：`0.1.0-rc.5`
- npm `@deepseek-ai/dsh` 最新版本：`0.1.0-rc.6`
- 许可证：MIT
- 官方提交归档 SHA-256：`534c9f1c9d30fea136026ecf7a23c2137e350f43558e2f1eff6218aef7b15b26`

审查覆盖 Cordis Context、Fiber、Service、Events，profile/bundle 组合，会话事件日志，系统 Prompt 装配，工具执行管线，客户端 Slot 和插件清单。仓库提交与 npm 版本不同，因此本文结论绑定上述提交，不把 npm 新版本的未审查行为当作源码事实。

## 源码证据

| 结论 | Harness 源码证据 | 对 Yotsuba 的含义 |
| --- | --- | --- |
| Profile 是有序组合层 | `packages/boot/app-boot/src/profile.ts` 以 manifest 中的 `bundles` 顺序加载 patch，随后才应用 profile 与 launcher 层 | 三档官方模板应由同一工厂物化并冻结，而不是复制三份后各自漂移 |
| 模型可见请求可从日志恢复 | `packages/core/agent-loop/src/agent.ts` 在调用前把 Provider/model、system 与 tool schema 组成 canonical header，并以 `initial/resume/change` 原因追加 `request/header` | 每次 Provider operation 必须关联不可变模型输入，而不能只存最终结果或散列 |
| Prompt/Context 是具名、有序贡献 | `packages/core/system-prompt/src/index.ts` 用唯一 name、order、scope 和 disposer 管理 section、context、tool schema 与 variable；重复或未知项失败 | 只在出现真实复用后引入内部 contributor registry，并让贡献进入输入快照 |
| Guard 是单调拒绝 | `packages/core/tools/src/index.ts` 的 guard 只能返回拒绝原因，没有 allow 能力；pre/around/post 管线不能推翻先前硬拒绝 | 长度、schema、引用、审批、幂等和写回门禁只能叠加，质量档位不能绕过硬合同 |
| Session 是 append-only 权威日志 | `packages/core/session/src/index.ts` 令 `seq = log.length`，append 成功后 observer 失败也不能回滚已提交事件 | SSE 只做事件投影；执行、恢复和当前决策必须按有序领域事件重建 |
| Slot 声明和贡献共生命周期 | `packages/client/ui-slots/src/index.ts` 要求父项声明 child slot；dispose contribution 时递归撤销声明并使旧授权失效 | 若以后引入内部 Slot，声明者和面板贡献者都必须可撤销，不能留下幽灵 UI 或独立状态源 |
| 动态插件是进程内可信代码 | `packages/extensions/cordis-host-runner/src/index.ts` 会执行 Host/Client code；Client 半部需要显式批准，Host Fiber 启动失败必须卸载 | 这是 Harness 的实验能力，不是小说创作产品应开放的配置能力 |
| Harness Workflow phase 只是观察标签 | `packages/workflow/workflow/src/types.ts` 明确 phase 不施加执行结构；`workflow/*` 事件也只观察 run/phase/log/agent 生命周期 | 它不能替代 Yotsuba 的 typed Artifact、checkpoint、interrupt、Outbox 与阶段写回合同 |

上述证据说明“一切皆插件”的核心不是把所有对象改名为 plugin，而是让每个运行时贡献都有稳定身份、明确依赖、可逆生命周期、确定顺序和可重建证据。

## Harness 真正解决的问题

“Everything is a Plugin”不是把任意功能做成配置项，而是把运行时贡献绑定到一个可观察、可卸载的所有者：

1. 插件声明所需服务；依赖未满足时保持等待，依赖消失时卸载，恢复后重新激活。
2. 服务、事件、工具、Prompt、计时器和 UI Slot 都登记为可逆 effect；Fiber 卸载时按相反顺序清理。
3. profile 只负责组合 bundle。后层按稳定 id 替换完整配置行，不做隐式深合并。
4. 模型实际看到的 system、tool schema 和动态上下文进入 append-only session log，恢复和回放读取同一权威记录。
5. 工具调用经过 pre-execute、单调 guard、execute、post-execute 和最终归一化，扩展点不能绕开拒绝结果。
6. Host 和浏览器两侧都暴露只读插件清单，失败 Fiber、配置 id 和加载状态可诊断。

这些机制的共同价值不是“插件数量”，而是贡献者有身份、依赖、生命周期、顺序和审计证据。

## 与 Yotsuba Ink 的权威映射

| Harness 概念 | Yotsuba Ink 对应权威 | 分类 | 决策 |
| --- | --- | --- | --- |
| profile / bundle | 三套官方 Workflow 模板与项目专属副本 | 直接采用 | 采用确定性组合思想，Run 创建时冻结完整副本 |
| append-only session log | EventProjection、OperationReceipt、ProviderInput、ContextManifest、Outbox | 直接采用 | 补齐模型输入审计，但不合并各领域存储权威 |
| tool guard pipeline | Provider、review、Evidence、writeback 门禁 | 直接采用 | 所有硬阻断保持单调，任一失败即 fail closed |
| plugin inventory | Workflow/Provider/Prompt/节点绑定诊断 | 改造采用 | 只提供从冻结 RunDefinition 派生的只读清单 |
| system prompt registry | 冻结 PromptTemplate、ContextManifest | 改造采用 | 仅允许内部、类型化、编译期贡献；先证明两个消费者再抽象 |
| UI slots | 阶段工作台内的审稿、证据、候选比较区域 | 条件采用 | 只允许产品内部注册表，不加载外部代码，不成为状态源 |
| Fiber lifecycle | LangGraph node、interrupt、checkpoint、Run 状态 | 明确拒绝 | 不引入第二套生命周期；只借鉴 observer/disposer 的清理纪律 |
| Service seam | 领域 Protocol 与 Store 边界 | 条件采用 | 只有出现两个真实实现时才抽象，避免为插件化制造空接口 |
| Agent Preset | 审稿角色与 Prompt 包 | 明确拒绝 | 不允许运行中换整套 Agent；角色差异在冻结 Workflow 中编译 |
| Workflow Engine / Worker | LangGraph 生产图 | 明确拒绝 | 不具备小说阶段 Artifact 与写回语义，不能成为第二执行引擎 |
| Dynamic Cordis Plugin | 无 | 明确拒绝 | 禁止模型或用户向 API 进程注入 Host/Client 代码 |
| Profile patch / HMR | 无 | 明确拒绝 | 运行中不热替换配置；旧 Run 永远读取创建时冻结值 |

## 为什么不能照搬 Harness Workflow

Harness 的 `workflow` package 运行的是可编排子 Agent 的脚本。它的 phase 是 UI/观察分组，不负责强制执行顺序；普通子 Agent 失败还可映射为 `null` 交回脚本。Yotsuba 的八阶段则是有持久 Artifact、人工 interrupt、严格引用、exactly-once 写回和恢复语义的生产图。

若再接入 Harness Workflow，会形成两套 run id、取消语义、事件顺序、恢复边界与失败分类。UI 将无法回答“当前候选由哪个权威生成、确认后写回哪个 Store、断线后从哪里恢复”。正确决定是保留 LangGraph 为唯一执行权威，只把 Harness 的组合与生命周期纪律映射到现有领域边界。

## 立即保留并强化的设计

### 1. 三档官方模板是受控 bundle

`fast`、`balanced`、`deep` 必须由同一个类型化工厂生成，再物化为三套可选择模板。允许的差异只有明确列出的模式字段，例如阶段模型、审稿角色、长度容差和候选策略。阶段拓扑、Artifact schema、Provider 安全边界和写回规则不得被模式覆盖。

官方模板进入项目后形成项目专属副本；之后编辑的是这本书的冻结配置。模板更新不得反向改变已创建 Run。

不采用 Harness 的任意层叠 patch。Yotsuba Ink 的配置页保存完整、可验证的 WorkflowDefinition；不存在 home patch、命令行 overlay 或隐式深合并。

### 2. 模型输入必须可重建且可核验

每次 Provider operation 的权威输入由以下部分组成：

- 冻结 ProviderBinding；
- 冻结 Prompt identity 与正文；
- 本次节点的结构化 context；
- 结构化输出 schema 或纯文本合同；
- operation key、attempt、chapter/version 和输入签名。

正文继续使用不可变 `ContextManifest`。规划阶段、review、Evidence 和 cover 不能只保留一个 request hash；最终验收前应能从 operation receipt 追到本次模型可见输入的冻结快照或等价不可变引用。快照只记录本地模型请求，不记录 API key、Authorization header 或 Provider 原始网络对象。

同一 operation key 若输入不同必须失败；已完成 receipt 不可覆盖。重试必须产生显式 attempt 或新的 operation key，不能在原记录上静默改 Prompt。

### 3. 扩展只能贡献，不能接管

后续质量规则、上下文片段、审稿角色和阶段辅助面板若需要注册机制，注册项至少包含：

- 稳定 id；
- owner；
- 适用 stage/node；
- required dependencies；
- order；
- 输入与输出类型；
- disposer 或 Run 结束时的清理边界；
- 是否进入模型可见输入。

注册表只接受产品内部编译代码。重复 id、未知依赖、循环依赖、越权写回和未声明模型输入全部 fail closed。注册项只能形成 sidecar、finding、proposal 或 UI projection，不能直接改核心 Artifact。

### 4. 阻断规则保持单调

Harness 的 guard 只能拒绝、不能推翻其他 guard 的拒绝。Yotsuba Ink 采用同一原则：

- schema、引用、长度、人物窗口、审批和写回幂等任一硬门失败，本轮不能被另一扩展“放行”；
- reviewer 不可用只能产生 `review.unavailable`，不能伪装为通过；
- UI 隐藏告警不改变领域状态；
- Fast 模式可减少可选审稿，不得关闭 Artifact、引用、长度和 Provider 冻结合同。

### 5. 只读运行清单

工作流配置页与运行控制台应能读取同一份派生清单：阶段、Prompt、Provider/model、预算、必要审稿、上下文贡献和写回目标。清单只用于诊断与展示，不成为第二份配置源。

运行中清单显示冻结值；模板编辑器显示待保存值。二者不得混用，避免“页面看见新配置、正在运行的 Run 仍使用旧绑定”的误判。

## 明确拒绝

以下 Harness 能力不进入 Yotsuba Ink 生产路径：

1. 任意 npm/Python 第三方插件在 API 进程内执行。
2. 插件替换 LangGraph graph、checkpointer、ArtifactStore、OperationStore、Outbox 或 EventProjection。
3. profile patch 覆盖 Provider 凭据、审批策略、核心 Prompt 或写回权限。
4. 运行时热重载正在执行的 Run。
5. 用户在创作页组装底层插件、工具或安全策略。
6. 用事件总线代替显式领域调用，或让监听器承担核心写回。
7. 为兼容旧配置增加 alias、converter、fallback 或双运行时。

原因很直接：Harness 的插件是与 Host 进程同等信任的代码，客户端 guard 也明确不是安全边界。小说流水线面向普通创作者，不能把这种信任和复杂度暴露为产品能力。

## 实施顺序

### Wave H1：验收前必须完成

1. [已完成] 固化三套官方 Workflow 的允许差异，增加结构 diff 测试，防止某一档漏阶段、漏 Prompt 或改写安全边界。
2. [已完成] 补齐 Provider operation 到模型输入的不可变引用，覆盖 planning、text、review、evidence、cover brief 和 cover image。
3. [已完成] 在现有运行详情中提供只读冻结绑定清单，不新增“插件管理”入口。
4. [已完成] 离线测试与全新真实 Provider Brief 换稿共同证明：输入改变产生新签名/新 attempt，旧输入与 receipt 保持可读，失败或新 attempt 不覆盖旧证据；没有复用历史 Run。

### Wave H1 实现证据（2026-08-15）

- `tests/test_workflow_template_api.py` 对三套官方模板做全结构 diff；白名单只有模板 `id/name/quality_mode` 与明确阶段的 `model_settings.model`。拓扑、edges、Prompt、Provider/security binding、input schema、generation budget 和 writeback 相关完整定义不允许分叉。
- `ProviderInputStore` 保存脱敏、内容寻址的模型可见输入；`OperationReceipt.provider_input_ref` 是唯一关联。Provider operation 缺少快照、同 key 不同输入、快照签名不匹配或 receipt 关联不完整都会 fail closed。
- 同一输入编译器覆盖 stage/proposal、正文纯文本、review、Evidence、cover brief 和 cover image；Provider gateway 与快照共用最终渲染 Prompt、context 和输出合同，不再保留旧的并行 request hash helper。
- `/monitor` 的“冻结配置”侧滑详情只读取 `GraphRunDefinition.provider_bindings` 与 `cover_asset_binding`，展示阶段、Provider/model、Prompt identity、预算、审稿和写回摘要，不提供编辑控件。
- 当前离线基线为后端 `345 passed`、前端 `390 passed`；`compileall`、production build、CSS audit、首屏/lazy CSS split、`git diff --check` 与 production closure audit 均通过。浏览器已验证 `1440x1000` 与 `390x844` 的详情层、内部滚动和关闭交互；后端从当前工作树重启后再次从历史页进入 `/monitor`，确认冻结清单可打开、`Esc` 可关闭且焦点返回入口，控制台为 0 error / 0 warning。
- 真实单阶段证据：平衡模式 Run `backend-run-brief-flash-h2-20260815` 的 Brief 三次 Provider 草稿均使用 Flash `thinking=disabled`、无 `reasoning_effort` 和紧凑 `2456` 输出预算，随后一次人工外科式编辑提交为《盐库原件》；每条 Provider operation 都有独立内容寻址输入，递归扫描无 Header 或 secret。Spine 初稿与 UI 换稿又各调用 Provider 一次，换稿 operation 为 `spine:generate:2`、`2983` tokens、无 repair；UI 与输入证据均成功，但文学对比发现终局提前、时序倒挂和重复收束，因此 Run 保持 Spine 待决策，不进入 Cast。
- Spine 证据促成 Harness 边界修正：输出预算必须从冻结 `scale_plan` 派生，候选数量必须由代码硬校验，Prompt 只负责在合法容量内创作；运行中缺少候选是 loading，不是 invalid artifact。修复没有增加插件框架、兼容别名、隐藏 repair 或第二执行路径。
- 平衡模式 Run `backend-run-1786732069818-cast-recovery-v2` 已正式提交 12 名主体、22 条关系的 Cast；两条越权/无依据关系在 UI 冷审后删除。当前 API 复核为 `awaiting_decision / volumes`，Brief、Spine、Cast completed，Detail 及以后 locked，17 次 Provider operation 中 15 成功、2 个历史失败、总计 75,233 tokens，当前 failure 为 `null`。该状态证明最新事件投影不会把已解决的历史失败当成当前状态，但不构成 Volumes 或长篇验收。
- 未解决：全新真实三章门禁、8–12 章单卷冷读、封面图片真实 Provider、三档 10 万字全书、文学连续性/深度与 GitHub 发布。单阶段成功不提前解锁这些门。

### Wave H2：三档 10 万字测试后评估

1. 若审稿角色或上下文贡献继续增长，再引入内部类型化 contributor registry。
2. 若至少出现两个阶段面板消费者，再引入小型内部 UI slot；此前保持显式组件组合。
3. 只有出现两个真实 Provider/存储实现时才抽象新的 service seam。

这三个条件避免为“插件化”提前制造框架。没有真实复用与生命周期问题时，普通函数、Protocol 和 React 组件仍是更清楚的实现。

## 验收门

- 官方三档模板 diff 只包含白名单字段。
- 每个真实 Provider call 都能定位到冻结输入和结果 receipt，且不含密钥。
- 重试、换稿、分支和恢复不会覆盖既有输入或结果。
- 删除任何内部贡献者后，其 side effect、UI projection 和注册清单同时消失。
- 前后端测试、构建、浏览器控制台和移动端布局通过。
- 上述条件未通过前，不启动三档 10 万字全链路。
