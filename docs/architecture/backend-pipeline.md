# 后端链路

## 职责

后端是一个 FastAPI 应用，负责提供工作流配置、运行执行、知识库接入，以及运行时事件流输出。

## 入口文件

- API 应用入口：[src/novel_workflow/api/app.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/api/app.py)
- 应用状态初始化：[src/novel_workflow/api/bootstrap.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/api/bootstrap.py)
- Runner 门面：[src/novel_workflow/workflows/runner.py](/Users/isla/Desktop/project/multi-stage-creation-model-end/src/novel_workflow/workflows/runner.py)

## 一次运行的生命周期

1. 前端通过 `runs` 路由发起一次运行。
2. 后端读取工作流定义并创建 run 记录。
3. `NovelWorkflowRunner` 开始流式执行并持续发事件。
4. 编排辅助模块在执行过程中处理质量检查、记忆读取、修订和写回。
5. `run_store` 持久化状态快照、事件和产物。

## 模块地图

- `api/bootstrap.py`：应用状态初始化和默认数据种子写入
- `api/dependencies.py`：薄依赖辅助函数
- `api/sse.py`：流式响应和 SSE 事件封装
- `api/routes/workflow.py`：工作流读取与保存
- `api/routes/runs.py`：运行创建、流式执行、暂停、恢复、审批
- `api/routes/chapter_revisions.py`：正文选区修订候选、接受和版本恢复的薄 HTTP 适配
- `api/routes/knowledge.py`：知识库上传、列表、搜索、删除
- `api/routes/references.py`：参考资料检索接口
- `api/routes/run_history.py`：运行历史、稳定快照查询、显式快照恢复和历史导出收据查询
- `references/context_injection.py`：参考资料摘要合并与运行前注入
- `providers/registry.py`：Provider 注册和环境变量驱动的实例化
- `workflows/templates.py`：默认 workflow、prompt、provider 配置
- `orchestration/*`：按职责拆开的执行辅助逻辑
- `orchestration/chapters.py`：正文节点执行顺序、章节恢复点与 SSE 事件
- `orchestration/chapter_generation.py`：单章候选生成、校验和选择
- `orchestration/chapter_artifact.py`：Chapter Artifact 规范化、签名、upsert 和进度恢复
- `orchestration/chapter_commit.py`：单章 usage、质量、Memory、Wiki、Story Bible 与连续性幂等提交
- `orchestration/chapter_revision_model.py`：UTF-16 选区校验、局部替换、签名、版本快照和前进式恢复纯逻辑
- `orchestration/chapter_revision.py`、`chapter_revision_support.py`：候选生成、双签名并发保护、请求幂等、Artifact/审批稿原子更新
- `orchestration/recovery.py`：失败分类、连续失败计数、熔断状态、稳定 Checkpoint 签名和显式恢复准备
- `quality/engine.py`：质量分析与问题发现
- `memory/wiki.py`：Wiki / Story Bible 写回
- `storage/run_store.py`：Run 事务入口、原子 JSON/二进制写入、状态版本和事件游标
- `storage/run_control_store.py`：暂停、审批、阶段控制等持久化原语
- `storage/run_snapshot_store.py`：稳定检查点索引、不可变快照文件和幂等恢复
- `storage/run_history_store.py`：轻量历史摘要投影、排序、过滤和游标分页
- `storage/run_export_store.py`：导出文件及 Export Receipt 持久化

## SSE 事件流

后端会输出一组领域事件，前端必须把它们当成运行态合同来消费，而不是去解析文本产物。

常见事件包括：

- 运行生命周期：`run_started`、`run_completed`、`run_paused`、`run_resumed`
- 恢复生命周期：`run_recovery_required`、`run_checkpoint_recovery_requested`、`run_snapshot_restored`
- 阶段生命周期：`node_started`、`node_completed`、`node_failed`
- 质量相关：`quality_check_started`、`quality_check_completed`、`revision_directive_created`
- 记忆相关：`memory_context_loaded`、`memory_writeback_completed`、`story_bible_updated`
- 审批相关：`approval_required`、`artifact_approved`、`brief_regenerated`

## 下一阶段后端主线

前端 mock 验收已收口，后端开发进入真实 API 接入阶段。当前目标是让 FastAPI domain runner 直接调用 OpenAI-compatible provider，并保持三档体验、结构化 artifact、SSE 事件和人工 checkpoint 不回退。

### 1. Run / Stage / Artifact / Writeback

- `run` 保存模式、启动意图、当前阶段、暂停/确认状态、完成状态和历史摘要。
- `stage` 保存阶段开始/完成/失败、耗时、token、质量分数和 checkpoint。
- `artifact` 保存结构化阶段产物，字段必须对齐 [stage-artifact-contract.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/architecture/stage-artifact-contract.md)，不存需要正则反解析的 markdown 自由文本。
- `writeback` 保存世界观、人物关系网、Wiki、质量阀门的阶段来源和目标系统。

### 2. 三档模式编排

- 极速生产：`info -> summary -> outline -> detail -> text -> cover -> export` 全自动，SSE 持续输出，前端保持 cockpit。
- 平衡创作：`info` 输出 `approval_required`，用户确认后自动继续后续阶段；版本对比只在用户主动请求时生成。
- 精细定稿：每个阶段完成后输出 checkpoint 并暂停；只有 `stage_artifact_confirmed` 后才能继续下一阶段；export 完成后停留导出页等待用户人工返回。

### 3. Prompt / Context / Loop

- Prompt 直接要求模型返回阶段结构对象：info、summary、outline、detail、text、cover、export 都使用稳定字段。
- Context 分层读取：知识库负责 grounding，世界观负责设定约束，人物关系负责角色状态，Wiki 负责事实账本，质量阀门负责执行评审。
- Loop 分层写回：人物变化写回人物关系网，事实增量写回世界观/Wiki，伏笔状态写回 Wiki open-loop，章节摘要写回正文上下文。
- Summary、Outline 与 Detail 使用阶段专属最终提交函数：先完成自动确定或 Deep 人工确认，再按 Artifact 签名幂等写入 Memory、Story Bible 和对应人物/世界/Wiki/伏笔系统；确认前草稿不进入正式状态。
- Outline 审批同时校验 Info 人物引用、世界观原文锚点、重复关系和重复伏笔；API 路由只负责合同/引用错误转换，聚合与写回规则位于 `orchestration/outline_artifact.py`。
- Detail 审批校验章节唯一性、POV/人物实体、关系配对、Info/Outline 世界观锚点和同章重复伏笔；最终写回规则位于 `orchestration/detail_artifact.py`，正常、pending、confirmed 与 completed 恢复共用同一提交函数。
- Detail 正式提交更新人物档案 `detail_shifts`、人物图谱、`worldbuilding_state.detail_facts/wiki_candidates`、结构化伏笔账本、Story Bible 时间线、Wiki 与连续性状态；同一 Artifact 刷新或重连不会重复写 Memory。
- `quality/engine.py` 直接从 `detail_outline.chapters[]` 构造正文 context，包含目标、进入状态、冲突、风险、人物变化、事实/Wiki、伏笔、钩子与连续性，不再从字典字符串正则抽取章节。
- 正文节点使用 `drafting -> committing -> completed` 三态检查点。`drafting` 已保存模型候选，恢复不再调用 Provider；`committing` 只补写回；`completed` 直接跳过。
- 正文顶层 `chapters` Artifact 在初始化、部分完成和最终完成期间保持同一对象结构，每章自带 Context、摘要、结构化写回、质量、修订历史、版本和提交签名。
- 章节进度、Context Packet、候选和选中版本按章节 upsert。单章 usage 使用稳定 stage key 覆盖；Memory/Wiki 使用稳定 output key/文档 ID 去重；Story Bible 摘要、时间线和世界观影响按章节替换。
- 模型返回的 Wiki 写回和伏笔变化由单章提交显式消费；同一提交恢复不会重复增加 Wiki 引用、开放伏笔、章节摘要或世界观影响。
- Deep 正文生成阶段只保存章节进度、候选、质量和下一章所需临时摘要，不提前写正式 Memory/Wiki。人工审批后的完整正文 Artifact 通过 `chapter_final_artifact.py` 按签名一次性提交；人工正文和摘要会替换生成稿对应的 Story Bible 内容，重复恢复返回空写回事件。
- 正文选区修订使用独立接口，不复用整阶段 `regenerate-draft`。生成候选不改正式 Artifact；接受时校验当前服务器签名、用户本地稿签名、版本、选区原文和候选签名，只替换 UTF-16 选区并同步更新 `state.artifacts`、待审批 Artifact 与对应 `ChapterDraft`。
- 局部接受和版本恢复以 `request_id` 幂等。接受保存服务器版本和本地人工版本快照，恢复始终创建更高版本；两者都清空旧提交签名。局部接受设置 `summary_dirty=true`，因此 Deep 审批仍由既有正文合同阻断，直到用户同步章节摘要。
- 摘要同步使用 `/chapters/{chapter_id}/sync-summary` 执行版本、双签名和摘要一致性校验；同一次提交更新正文 Artifact、待审批 Artifact、`quality_recheck`、`writeback_proposal` 与三类事件，不调用 Provider。
- `quality/chapter_repair_targets.py` 把复检 finding 映射为最多 1200 UTF-16 units 的正文选区，绑定当前章节版本和编辑签名；不可靠证据返回 `locatable=false`，API 层不参与文本搜索或修订决策。
- `writeback_proposal` 与正文编辑签名和章节版本绑定。`pending/blocked` 或签名过期时正文审批拒绝；接受/拒绝接口以 request id 幂等。接受只在 `chapter_final_artifact.py` 定稿提交时消费，拒绝会清空 Wiki/人物/伏笔的有效写回视图并阻止自动伏笔提取旁路写入。
- `memory/canon.py` 维护结构化 Canon 事实与冲突历史。章节写回先按 `target + claim_key` 预览：相同事实只追加来源，新的 claim 生成 active fact，同一 claim 的不同事实生成 pending conflict；只有明确的 `keep_existing/replace_existing` 决策才允许解决冲突，旧事实被替换时标记 `superseded`，不删除历史。
- `canon_facts_committed` 是 Canon 提交事件，携带新增事实、冲突解决和仍待处理的冲突；Run State 同时保存 `canon_facts` 与 `canon_conflicts`，刷新和断点恢复不依赖 Wiki Markdown 反向解析。
- Recovery 状态保存在 Run State 的 `recovery_state`：记录失败类别、阶段/章节、连续失败次数、失败历史和最后稳定 Checkpoint 的 Artifact 签名。失败后的 SSE 重连只返回 `run_recovery_required`，用户点击“继续创作”后才由 `/resume` 显式解锁；同一范围连续 3 次失败打开熔断。
- 稳定 Checkpoint 在阶段确认/完成和章节提交写回后更新。正文候选全部无效或章节质量阻断时不得把 `text` 标记为完成，也不得进入正文确认或正式写回。
- 每章十步管线统一发出 `chapter_pipeline_step_completed`，携带 `step/step_key/step_label/chapter`。步骤依次覆盖章节定位、Context、执行剧本、正文生成、合同校验、草稿落盘、质量审计、章后处理、张力评分和章节结算；恢复只继续尚未完成的后半段，不补发已落盘步骤。

### 3.1 真实 Provider 与密钥策略

- Provider profile 保存到本地 SQLite，只包含供应商类型、Base URL、默认模型、模型选项和环境变量名，不保存明文 API Key。
- 前端设置页的 API Key 输入是一次性 secret 输入：提交到后端后写入本地 `runtime/novel_workflow/provider_secrets.sqlite3`，随后清空前端输入态。
- 后端运行时按优先级解析密钥：SQLite secret -> `api_key_env` 指向的环境变量 -> 通用 OpenAI 环境变量 fallback。
- `/api/providers/test` 只做低 token smoke test，用于验证 Base URL、模型名和密钥可用性；不得在测试响应、日志或 Provider 列表中回显密钥。
- 生产 provider 只保留 `openai-compatible`。默认模型为 `deepseek-v4-pro-202606`，本地 TokenHub profile 与 secret 分别存入 SQLite。
- 生产代码不再提供 mock provider 或 demo runtime；测试中的 fake provider 只能放在 `tests/` 边界内，不能进入 `src/novel_workflow`。
- 真实模型接入顺序必须是：保存 profile -> 保存 secret -> 低 token 连通性测试 -> 单阶段结构化输出校验 -> 小预算全链路 SSE -> 放大正文/长篇预算。

显式 smoke 命令：

```bash
.venv314/bin/python -m novel_workflow.providers.smoke --stage-id info --max-tokens 1600
```

该命令只读取 SQLite provider profile/secret 或 `api_key_env`，不会输出 API Key。它用于真实链路前的最低成本门禁：确认外部模型能返回符合阶段合同的结构化 JSON。`summary / outline / detail / text` 只能在 `info` 探针稳定后逐步放开，并按阶段提高 `--max-tokens`。

### 3.2 阶段长度预算

阶段输出长度由 `StageConfig.generation_budget` 持久化，并被 `PromptPlanBuilder` 写入 prompt。模型必须按配置生成结构化 JSON，不能忽略预算自由扩写。

默认建议范围：

- `info`：目标 1200 中文字符，合理范围 800-1800，`max_tokens` 2600。
- `summary`：目标 1800 中文字符，合理范围 1200-2800，`max_tokens` 3600。依据小说 synopsis 通常需要覆盖完整故事、人物变化与结局，不能退化成一句简介。
- `outline`：目标 2200 中文字符，合理范围 1400-3600，`max_tokens` 4200。按 opening / development / midpoint / climax / resolution 等 beat 字段输出。
- `detail`：目标 3000 中文字符，合理范围 1800-4800，`max_tokens` 5200。默认三章，覆盖 POV、目标、冲突、事实、伏笔、人物变化和连续性。
- `text`：单章目标 2200 中文字符，合理范围 1500-3200，`max_tokens` 4200。真实链路首轮只生成前 3 章，后续再放开完整章节。
- `cover`：目标 900 中文字符，合理范围 500-1400，`max_tokens` 2200。当前由真实文本模型生成 cover brief、prompt 和视觉候选；图片 provider 后续独立接入。

真实 API 小流量验收不要把 `info` / `summary` 压到 1800 tokens 以下；本地 TokenHub `deepseek-v4-pro-202606` 在 1400 tokens 下容易触发截断，2200 tokens 已通过结构化探针。

### 3.3 执行预算账本

- `GenerationBudget.max_tokens` 是单次生成上限；`NovelRunState.budget_state` 是可恢复的阶段/章节总账本，两者不能互相替代。
- 每次文本 Provider 调用必须先写入 `reserved` operation 并持久化，再发出网络请求；成功或失败后都要结算。失败按预留量保守计入，避免异常响应和断线造成隐形成本。
- 候选生成、确定性模型评审标记、自动修订和显式恢复重试使用独立计数。未真正调用模型的评审/修订只记操作次数，不伪造 Token 消耗。
- 阶段/章节预算达到阈值先发 warning；调用前预测值超过阶段或 Run 上限时直接阻断，不允许 Provider 已经执行后才宣告超预算。
- 崩溃或 Provider 失败不会由 SSE 重连自动重跑。`POST /resume` 只在 Recovery 允许时开放一次预算内 retry；retry 上限耗尽后进入人工介入。
- 运行可通过 `inputs.budget_limits` 设置 `run_max_tokens`、`warning_ratio` 和 `stages.{node_id}.max_tokens`。没有显式 Run 上限时仍执行每个阶段/章节的 scope 上限。

### 3.4 导出交付包

- Export Artifact 只描述 Manifest、格式、文件清单和校验结果；真正的下载内容由 `orchestration/export_delivery.py` 重新从已落盘状态构建，不能信任前端拼接内容。
- 交付前必须确认所有目标章节为 `completed` 且正文非空、封面已选择候选、质量报告没有最新失败记录、Canon 没有 pending conflict。任一阻断项存在时返回 409，不产生下载包。
- `POST /api/runs/{run_id}/export-package` 接受 `format=md|json|zip` 与可选 `chapter_ids`。ZIP 使用标准库 `zipfile` 生成真实压缩包，文件名通过 `Content-Disposition` 的 UTF-8 参数返回。
- 导出请求必须携带或由服务端生成 `request_id`。服务端保存 `Export Receipt`（`export_id`、源稳定快照、Artifact 签名、章节选择、文件大小和 SHA-256），重复 request id 返回同一不可变文件；历史可通过 `GET /api/runs/{run_id}/exports` 查看并重新下载。

### 3.5 创作历史与快照

- `GET /api/runs/history` 只返回轻量摘要，支持 `limit/cursor/project_id/status`，不批量泄露完整输入、事件或 Artifact。
- 稳定事件（阶段 checkpoint、确认、章节完成、交付就绪和最终完成）会把完整 `NovelRunState` 写入 Run 私有 `snapshots/` 文件，并在 `run.json` 中保留摘要索引；运行失败事件只记录不可恢复状态，不伪装成稳定检查点。
- Run Store 为每次持久化维护 `created_at/updated_at/state_revision` 和单调 `event_seq`，同一进程内按 Run 串行写入，临时文件使用进程/线程唯一名称后原子替换。
- `POST /api/runs/{run_id}/restore-snapshot` 只允许当前 Run 的最新稳定检查点，要求 `expected_revision`（可选）和幂等 `request_id`。恢复保留预算消耗、失败历史和重试账本，先落盘为暂停态；只有用户随后明确点击“继续创作”才调用 `/resume` 和 Provider。任意旧快照分叉及外部 Wiki 命名空间隔离留在后续阶段。

### 4. SSE 与恢复

- 真实 SSE 优先对齐前端事件消费：`run_started`、`node_started`、`artifact_stream_delta`、`chapter_delta`、`node_completed`、`approval_required`、`stage_artifact_confirmed`、预算 warning/exceeded、`manual_intervention_required`、`run_export_ready`、`run_completed`。
- 刷新恢复必须能重建事件列表、当前阶段、已完成节点、确认点、暂停状态、失败原因和历史记录。
- 重置/取消必须隔离迟到事件，不能污染新的 run。
- `chapter_completed` 只能在该章结构 Artifact 和全部单章写回完成后发出；已落盘 `completed` 章节恢复时不重放生成事件。

### 5. 后端验收顺序

1. schema 与默认 workflow 对齐阶段合同。
2. runner 事件快照测试通过。
3. 持久化 run 恢复测试通过。
4. 真实 provider 小预算跑通 `info -> summary -> outline -> detail -> text(前 3 章) -> cover -> export`。
5. 再接真实知识库检索、图片生成、成本统计和恢复压测。
