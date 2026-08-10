# Phase 15：真实整书链路与人工成稿验收

> 状态：Run I 已完成 3 卷 9 章、模型复检、Deep 正式写回、真实封面与 ZIP 汇合，自动技术验收通过；逐章人工冷编辑、投稿市场规则与作者最终定稿仍待执行
>
> 日期：2026-07-31
>
> 前置合同：[阶段产物合同](./stage-artifact-contract.md)、[Phase 13 文学质量](./phase-13-literary-quality-and-editorial-readiness.md)、[Phase 14 模型路由](./phase-14-mimo-stage-routing-and-live-validation.md)

## 1. 产品判断

结构合同通过、单章样例可读和导出成功，都不足以证明长篇生产链路稳定。Phase 15 用一部规模受控但跨越三个卷界的原创中篇，验证上游 Artifact 是否真的约束正文、章节与分卷是否连续、正式写回是否幂等，以及封面和导出能否形成可追溯交付。

自动化验收只能把结果推进到 `needs_author_review`。完成逐章人工审阅、目标市场规则复核和作者最终定稿后，才允许标记 `ready_for_manual_submission_review`；禁止使用“自动可投稿”“保证过审”或 AI 检测分数。

## 2. 两级真实验收

| 层级 | 规模 | 用途 | 运行时机 |
| --- | --- | --- | --- |
| 小流量冒烟 | 1 卷、3 章 | 验证鉴权、模型目录、SSE、基本 Artifact、封面和导出 | Provider 或协议变化后优先执行 |
| 整书验收 | 3 卷、每卷 3 章、每章恰好 2 场 | 验证跨章/跨卷连续性、Wiki/RAG/Canon、伏笔、恢复和整包交付 | 冒烟通过且需发布质量证据时执行 |

整书验收不替换小流量冒烟。Provider 不可达、模型目录变化或余额不确定时，必须先停在低成本探针，不能直接启动九章运行。

## 3. 固定验收故事与阶段规模

- 原创项目：`潮汐失语者`，近未来海岛档案伦理与现实质感悬疑。
- 分卷：恰好 3 卷，每卷恰好 3 章，章节范围连续且互不重叠。
- 细纲：恰好 9 章，每章恰好 2 个结构化场景。
- 正文：9 章全部完成；单章生成目标 1600-2400 中文字符，技术报告容许 1200-4000 字符的自然节奏差异，同时要求全书正文总量命中 10000-30000 字符；不得只放宽单章上限而忽略整书规模。
- 场间：后一场 `handoff_in` 必须逐字等于前一场 `handoff_out`。
- 章间：第二章起必须保存上一章摘要和尾文；第 4、7 章必须保存上一卷结算并呈现其后果。
- 封面：Detail 定稿后与正文并行，不等待全文完成；必须由真实图片 Provider 生成并落盘。
- 导出：等待正文和封面都完成后汇合，生成带冻结快照、哈希和真实封面资产的 ZIP。

## 4. 模型路由与调用预算

| 阶段 | 模型 | 预算策略 | 原因 |
| --- | --- | --- | --- |
| Info | `deepseek-v4-pro` | 4600 tokens | 建立人物、阵营、Voice 与硬规则基线 |
| Summary | `deepseek-v4-flash` | 3600 tokens | 稳定结构化梗概，控制成本 |
| Outline | `deepseek-v4-pro` | 4200 tokens | 处理三卷因果、节拍和伏笔分布 |
| Detail | Provider 高能力模型 | 每章 12000 tokens，9 批 | 每批只返回 1 章、2 场；成功章节立即落盘，九批合并后统一校验 9 章合同 |
| Text | `deepseek-v4-pro` | 每场独立调用；整章 1600-2400 字符 | 保持场景职责、断点恢复和承接精度 |
| Cover brief | `deepseek-v4-flash` | 2200 tokens | 只生成封面规划和图片 prompt |
| Cover image | 本机已配置图片 Provider | 3 个候选 | 文本模型不得伪造图片资产 |
| Export | 系统本地生成 | 不调用模型 | 冻结选择并生成可验证交付包 |

DeepSeek 官方 OpenAI 兼容入口为 `https://api.deepseek.com`，当前模型目录为 `deepseek-v4-pro` 与 `deepseek-v4-flash`。运行前必须再次调用 `/models` 验证，不把文档快照当作实时可用性证据：

- <https://api-docs.deepseek.com/api/list-models>
- <https://api-docs.deepseek.com/quick_start/pricing>

API Key 只通过验收进程的临时环境变量注入。它不得进入 Provider Profile SQLite、工作流 JSON、Run State、报告、日志、Git 或命令示例中的真实值。

## 5. 自动审批边界

Phase 15 的自动审批不是产品运行时默认行为，只用于无人值守的受控验收进程。每次审批必须同时满足：

1. 当前节点 Artifact 通过正式 Pydantic 合同。
2. Summary 起的当前阶段或每一章最新确定性质量结果通过且不阻断；历史失败在成功复检后不再永久阻断。Info 只执行 Artifact 与人工闸门，Cover 执行真实资产门，不伪造不存在的质量报告。
3. Outline 恰好 3 卷。
4. Summary、Outline 与 Detail 的人物、世界观、关系和章节引用必须在自动确认前通过领域校验；Outline 恰好 3 卷，Detail 恰好 9 章、每章恰好 2 场。
5. Text 恰好 9 章且全部为 `completed`。
6. Cover 已选中真实、可读取、带 SHA-256 的落盘图片资产。

任一条件失败都必须停止当前验收，保留 Run 和失败证据；不得放宽卷数、章节数或场景数来让报告变绿。

## 6. 自动化技术门

最终报告必须逐项验证：

- 七阶段 Artifact 全部存在。
- 三卷、九章、每章两场。
- 九章全部完成，单章无短缺或失控，且全书正文总字符数命中 1-3 万字验收带。
- 九个 Context Packet 完整，两个卷首存在上一卷结算。
- 九章模型评审完成，九章最新确定性质量结果通过。
- Wiki 引用和每章 Memory/RAG 上下文均已记录。
- Canon 冲突全部解决。
- 至少一个伏笔具有正文证据和状态历史。
- 正式封面资产可验证，Export 为 ready。
- 无 Provider 失败事件和 Run Error。

`technical_passed=false` 时 CLI 必须返回非零状态，但仍保留报告和可诊断证据。

## 7. 证据目录

每次运行使用独立 Run ID，证据保存在：

```text
runtime/novel_workflow/real_gate_runs/<run-id>/
├── run.json                    # Run State、事件、Artifact、审批与恢复事实源
├── run_meta.json               # 可列表化摘要
├── cover-assets/               # 真实封面二进制与 metadata
├── exports/                    # 不可变导出版本与 Receipt
└── acceptance/
    ├── acceptance-report.json  # 机器可读检查结果
    ├── acceptance-report.md    # 人工检查入口
    └── <title>.zip             # 最终冻结交付包
```

`run.json` 必须能追溯九章正文、Context Packet、Wiki/RAG、Canon、伏笔历史、Provider 尝试、Token 估算和每次审批。报告只汇总证据，不复制密钥、完整 Prompt 或 Provider 原始响应。

## 8. 恢复与幂等

- 相同 Run ID 和完全相同输入才允许继续；输入不同必须新建 Run。
- `drafting` 从已落盘候选继续质量检查，不重复调用正文 Provider。
- `committing` 只补齐质量、Memory、Wiki、Canon、人物和伏笔写回。
- `completed` 章节不得再次生成、计费或写回。
- 同一场景签名、章节签名、Wiki 文档 ID、伏笔状态转换和导出选择必须幂等。
- 失败刷新或进程重启不自动调用 Provider；必须显式继续，并从最后稳定 Checkpoint 恢复。
- 连续三次同范围失败后保持熔断，不用无限重试消耗余额。
- Detail 逐章生成时，每批使用独立预算范围与幂等键；第二章起必须注入上一批末章的 `hook`、`continuity_notes`、最后一场 `handoff_out`，并携带此前章节的紧凑事实/伏笔/人物 ledger。
- 成功批次与上游 Info/Summary/Outline、模型和 Prompt 来源签名绑定；签名不变时恢复直接复用，任一正式上游产物或 Prompt 变化时旧批次失效。
- 从整段单请求升级为分批策略属于显式策略修订：旧失败和 Token 消耗移入 `legacy_scopes`，写入 `acceptance_strategy_upgraded` 后才允许重置连续熔断计数；不得删除或改写历史失败。

验收至少执行一次受控中断恢复演练：在非首章完成后中断进程，确认恢复后已完成调用数、章节哈希和正式写回数量不增加。

## 9. Prompt 工程验收

Prompt 通过快照或结构合同不等于正文质量通过。真实验收必须核对：

- L0 硬规则、L1 当前任务、L2 上游 Artifact、L3 人物/Canon、L4 Voice、L5 检索证据的优先级没有倒置。
- Context Packet v2 的上一章尾文、未完成动作、情绪、知识、空间、意象、关系、伤势和物件状态被正文实际消费。
- 场景逐次调用只返回正文，不混写摘要、质量说明和后台写回。
- 章后摘要、Wiki、人物、伏笔和 Canon 只从已确认正文及其签名抽取。
- 检索遵守 Canon 优先，RAG 命中只作为证据，不自动晋升为事实。
- 发生 POV、时间或地点切换时，正文存在可感知锚点；未声明切换时默认连续续写。

## 10. 人工逐章审阅矩阵

| 维度 | 每章检查 | 卷界附加检查 | 失败处理 |
| --- | --- | --- | --- |
| 承接 | 开篇是否消费上一章动作、尾文或情绪后果 | 第 4、7 章是否先呈现上一卷结局后果 | 定位受影响场景，重编译 Intent/Scene 后重生成 |
| 人物 | 行动是否符合动机、知识边界与关系压力 | 人物变化是否跨卷保留 | 修正 Context/Canon，不用全章泛化润色 |
| POV | 感知和信息是否属于当前人物 | 换卷不等于重置视角 | 修正具体越界段落并复检 |
| 场景 | 目标、阻力、策略、转折、代价是否成立 | 卷末是否结算卷目标 | 只重写失败场景并保持 handoff |
| 伏笔 | 投放/推进/回收是否有正文证据 | 回收是否改变选择或结局 | 修正证据或状态，不做关键词打卡 |
| 文体 | 解释腔、整齐排比、空泛哲理和重复意象是否过量 | 三卷是否保持 Voice 又有节奏变化 | 定点冷编辑，保留有效句段 |
| 原创性 | 是否出现未经授权的专有表达或可识别仿写 | 核心设定是否保持项目自身因果 | 删除来源不明表达并记录人工决定 |

人工审阅结果需要记录章节、证据片段、判断、操作和新 Artifact 签名。不能只写“感觉不错”，也不能用模型自评替代作者判断。

## 11. 运行顺序

1. 本地编译、定向测试和完整后端回归全绿。
2. 运行 `/models` 与最小结构化探针，确认鉴权、余额、模型和 JSON 协议。
3. 启动独立 Run ID 的整书验收进程。
4. 若 Detail 不是 9 章或任一章不是 2 场，先修 Prompt/预算/合同；输入不变且有稳定检查点时在同一 Run 显式升级策略并恢复，不新建 Run 冒充成功，也不放宽标准。
5. 技术报告通过后，逐章完成人工矩阵审阅。
6. 只重新生成受影响的场景或章节，重新执行下游摘要、写回和导出冻结。
7. 确认服务停止、密钥未落盘，并提醒撤销本次已暴露的旧密钥。

## 12. 当前验证记录

- `tests/test_book_acceptance.py` 与 `tests/test_detail_batch_generation.py`：21 项通过，覆盖 3×3 配置、逐章预算、跨批交接、来源签名、批次复用、旧预算归档、双 Provider readiness、错误卷/章/场景拒绝、待审批恢复和报告。
- Run E 保留三次 Detail 单请求失败：一次约 106 秒连接中断，两次分别在 16000 与 32000 输出上限截断；这些证据不会从 Run 历史中删除。
- Run E 的第一次按卷尝试同样在“3 章 × 14000 tokens × GLM max 思考”下截断且没有形成成功批次，因此 `1.0.2` 改为逐章 12000 tokens 与 `high` 思考；失败范围继续归档，不覆盖历史。
- 验收模块 Python 编译、导入与 CLI `--help` 通过。
- Provider 能力适配后的历史完整后端回归为 `475 passed, 1 skipped`；该数字只保留为阶段基线，最终结果以本节 Run I 证据和当前回归为准。

## 13. Run I 技术验收闭环

- Run ID：`phase17-live-book-deepseek-20260801-i`。
- 第 9 章人工定点修订后为 3578 字；恢复只重新执行当前签名的模型复检，没有重新调用正文生成。最新模型评审为 9.0，阈值 8.4，Voice Drift 为 false，签名与当前章节版本一致。
- Text 确认后依次产生 `memory_writeback_completed`、Story Bible、人物图谱、世界观与第 1-9 章 `canon_facts_committed` 事件；随后封面与 Export 汇合。九章、三卷、每章两场、卷界交接、质量门、伏笔证据、Canon 冲突和真实封面均通过。
- 原报告的唯一失败项为 `wiki_rag_recorded`：旧口径错误地要求 `memory_contexts` 必须有 9 个独立字典键，但相同检索结果会共享 Context Signature，Run I 的五个落盘上下文实际覆盖九个章节包。修复后的验收逐章核对 `wiki-retrieval:<signature>` 是否能映射到真实、非空的落盘 Context，并同时要求 Wiki 正式写回不少于 9 条；没有事后回填未来事实或伪造历史检索。
- 最终 RAG 证据为 58 条 Wiki 引用、9 个章节检索绑定、5 个落盘 Context、2 个唯一 Context Signature；`technical_passed=true`，无失败检查。
- 交付包：`acceptance/潮汐失语者.zip`，292884 bytes，SHA-256 为 `04f28fbd8788599440a711f306764138b27e7e29b39e7827e07f212d292b144e`。ZIP 含九章 Markdown、Manifest、Info、Summary、Outline、Detail、Cover、README 与真实封面资产。
- 自动技术通过仍只把状态推进到 `needs_author_review`；这不是“自动可投稿”。逐章叙事承接、人物声音、潜台词、解释密度、伏笔证据、投稿市场规则与 AI 协作披露仍需作者人工确认。
