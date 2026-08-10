# Phase 25：真实 Provider 恢复与局部补丁安全闭环

> [!CAUTION]
> **已废弃，仅作失败证据，不再指导实现。** Phase 25 记录的 Run B-G、局部补丁、恢复分支和验收结果必须保留用于追因，但其 Shadow/Dual、legacy 恢复、Run H 续跑和补丁式演进路线已被 Phase 26 取代。文档评审通过前不得据此启动服务、调用真实 Provider 或继续生产实现。
>
> 状态：**已废弃，仅作失败证据，不再指导实现。**
>
> 原冻结状态：Run B 至 Run G 均已冻结为真实失败样本；动态章节容量、候选证据保护、新增事实矛盾 ratchet 与恢复回放分支已完成本地闭环。原计划中的 Run H 已取消，禁止据此恢复旧 Run 或宣称全链路、投稿验收通过。
>
> 日期：2026-08-09。

## 1. 本阶段目标

Phase 24 已完成动态成书体量、本地全量门禁和浏览器验收。Phase 25 恢复 DeepSeek 三章真实链路，目标不是通过修改运行 JSON 追求绿色状态，而是验证以下生产合同：

- 前置阶段和已完成章节可以被恢复复用；
- 质量修订只生成局部、可定位、可验证的补丁；
- 坏候选在正式正文、Wiki、Canon 和 Narrative World 写回前被隔离；
- 恢复操作绑定 failure、正文和 Artifact 签名，且不隐式扩大 Provider 预算；
- 本地全绿、真实运行完成和人工文学审读是三个独立门禁。

## 2. 真实 Run B 结果

Run：`phase25-real-deepseek-20260808-b`。

冻结结果：

- Info、Summary、Outline、Detail 已完成；
- 第 1、2 章已完成；
- 第 3 章冻结 base 稿为 `prose_ready`，正文 3007 字；
- 第 3 章未完成章后抽取、正式 Wiki/Canon/Narrative World 写回和卷提交；
- Run 保持 `failed`，Volume Canon 保持 `provisional`；
- 当前候选已拒绝，正文、预算、失败历史和正式写回状态未变化。

第 3 章真实预算状态：

| 类型 | 已用 / 上限 | 结论 |
| --- | ---: | --- |
| generation | 2 / 2 | 不再重写原始正文 |
| revision | 2 / 2 | 一次性补丁协议恢复额度已用完 |
| model_review | 3 / 3 | 不再追加语义审稿调用 |
| cold_edit | 5 / 5 | 不再追加专项审稿调用 |

因此 Run B 是冻结的失败验收样本，不允许再通过无界重试、手工改运行 JSON 或增加隐式预算推进。

## 3. 真实故障时间线

### 3.1 第 2 章叙事抽取

Provider 曾把 Detail 的目标描述误当成正文已发生事实，产生正文中不存在的 assertion。现有叶节点裁剪恢复在事件 242 完成：

- 只移除无正文证据、无下游引用的单个叶 assertion；
- 保留其余 20 个 assertions、2 个 fingerprints 和冻结正文；
- `provider_calls=0`、`budget_changed=false`；
- 第 2 章随后完成。

该故障已经闭合，不得重复执行恢复。

### 3.2 第 3 章补丁协议

第一次质量补丁包含互相嵌套的 `search`。修复后，确定性代码可以在不增加 Provider 调用的前提下组合无歧义的包含关系，交叉或不一致包含仍然拒绝。

事件 414 绑定原 failure、冻结 Artifact 签名和正文签名，只开放一次新的 revision：

- generation 上限与已用次数不变；
- 正文、Wiki、Canon 和 Narrative World 不变；
- 同一恢复不可重复开放；
- 签名漂移时拒绝恢复。

### 3.3 候选对白归属破坏

第二次补丁生成 3182 字候选并在事件 431 以 `pending_review` 保存，但候选把以下叙述全部包入陈铭章的直接引语：

- 两名纪律审查员进入；
- 方敏春的动作；
- 审查决定；
- 三名人物的职位结算。

该错误的引号数量仍然成对，单纯检查奇偶或开闭数量无法发现。根因是短对白的闭引号归属被异常后移，导致对白范围从 14 字扩大到 126 字。

候选随后发生证据绑定失败，Run 在事件 447 停止。不得用证据重绑掩盖正文结构错误。

## 4. 实施合同

### 4.1 对白结构门禁

`literary/revision_patch.py` 现在在补丁应用前后执行两层确定性校验：

1. 新稿不得增加中文直接引语的未闭合、错配或交叉错误；
2. 当原 `search` 和 `replacement` 含有同组完整对白时，允许正常改写和适度扩句，但拒绝短对白异常扩张到吞入长段叙述。

当前容错允许对白扩展到至少 96 字，或原对白长度的 4 倍；只有同时超过该范围且净增长超过 80 字才拒绝。该阈值用于识别结构性归属漂移，不是正文删减或文学字数硬门。

补丁 Prompt 同步声明：人物对白必须在台词处闭合，叙述动作、制度结算和时间跳转必须位于闭引号外。

### 4.2 候选拒绝

候选拒绝能力统一为 `reject_quality_candidate`：

- 同时接受 `pending_review` 和 `accepted` 候选；
- 必须绑定 base 正文、candidate 和冻结 Artifact 三重签名；
- 恢复 base 审校快照，不改正文；
- 不改变 Provider 预算、Wiki、Canon、Narrative World 或失败历史；
- 相同签名重复调用幂等；签名漂移时拒绝。

不保留 accepted-only 的旧方法名和兼容双轨。

## 5. Run B 零调用处置

新门禁已用 Run B 的冻结原稿和实际候选差异回放，得到：

```text
第 1 个 replacement 异常扩大对白范围，疑似把叙述包入引号
```

事件 448 完成签名绑定的候选拒绝：

- `candidate_status_before=pending_review`；
- 候选状态变为 `rejected`；
- `provider_calls=0`；
- 只新增一个状态修订和一个事件；
- 第 3 章正文、章节状态、预算、Wiki、Canon、Narrative World 和 failure history 全部不变；
- `formal_writeback=false`。

Run 仍保持 `failed / model_review_unavailable`。候选隔离不等于真实链路完成。

## 6. 本地验证

- 补丁、恢复、候选拒绝和场景重复恢复定向测试：`32 passed`；
- 后端全量：`1441 passed, 6 skipped, 1 warning`；
- Python `compileall`：通过；
- `git diff --check`：通过；
- 结构审计：无旧体量字段、无前端并行顶层目录；大文件清单仅作为责任审查信号，不做机械拆分。

本轮未启动前端服务，也未执行新的浏览器验收。Phase 24 的浏览器结果不能替代本阶段真实后端闭环。

## 7. 未闭合门禁

冻结 base 稿的模型审校仍明确缺少 5 项终章交付，包括人物职位后果、记忆复核制度、海边听潮、照片/纪念碑动作和个人代价。它们不是纯证据绑定误差，不能通过零调用重标为已完成。

Run B 因预算已耗尽，只允许以下两种产品决策：

1. 作者人工修改第 3 章并创建显式作者修订分支；
2. 从新的三章真实 Run 开始验证当前代码，重新观察 Detail 终章密度、补丁结构门禁、成本和文学质量。

禁止对 Run B 追加隐藏额度或再次复用已拒绝候选。

## 8. 下一轮验收顺序

1. 新 Run 在同一三章合同下重新生成，记录 Prompt 字符、模型、调用数和实际 Token；
2. 确认对白结构错误在候选持久化前被拒绝；
3. 检查 Detail 是否把过多结算责任压入终章，必要时从剧本密度和交接合同修正，而不是继续扩张正文 Prompt；
4. 三章全部完成后验证 Postprocess、Narrative State、Wiki、Canon、Volume Commit 和 Export；
5. 再做人工冷读，分别评价章内节奏、跨章承接、人物声音、伏笔回收和 AI 化表达；
6. 真实后端闭合后，才恢复前端全量、构建、CSS 和浏览器矩阵。

## 9. Definition of Done

- [x] 修复无歧义嵌套补丁，继续拒绝交叉补丁；
- [x] 一次性补丁协议恢复绑定 failure、正文和 Artifact 签名；
- [x] 增加有容错的对白闭合与归属扩张门禁；
- [x] `pending_review` 坏候选可零调用拒绝；
- [x] Run B 候选已隔离，冻结 base 和正式写回状态未变化；
- [x] 后端全量与静态门禁通过；
- [ ] 新真实 Run 完成三章正文、章后抽取和质量结算；
- [ ] Wiki、Canon、Narrative World、Volume Commit 与 Export 闭合；
- [ ] 人工文学审读达到投稿候选标准；
- [ ] 本阶段前端与浏览器验收完成。

## 10. Run C：修订计划编译缺口

Run：`phase25-real-deepseek-20260809-c`。

Info、Summary、Outline、Detail 均由真实 DeepSeek 调用完成，Detail 形成三章连续交接；正文第 1 章在质量结算停止。冻结证据如下：

- base 正文 2538 字，候选正文 2576 字；
- 第一次语义审稿确认约 78% 细纲覆盖，明确缺少“启动调查”和“决定联系苏敏，在局外继续还原声纹”；
- 因果审稿同时发现录音归档日期为 2047 年、删除时间为 2087 年的硬冲突；
- Voice Spec 的对白比例约 40%，正文实测约 5%，该项只属于诊断，不应单独消耗自动修订；
- 唯一一次修订只校正日期，没有补齐章末交接；候选复检后仍要求修订，最终以 `quality_budget_exhausted` 停止；
- `generation=2/2`、`revision=1/1`、`model_review=2/2`，直接恢复需要扩大既有额度，因此 Run C 不恢复、不改 JSON、不复用旧候选。

根因不在 Provider 是否执行指令，而在修订计划编译层：`combined_review_revision_instruction()` 遇到专项因果审稿后，会整段丢弃同轮语义审稿的结构化缺项。该旧行为还被单元测试固定，导致一次审稿发现多个必要问题时，系统仍只发出单目标 directive。

## 11. 单次多目标修订合同

修订计划现在遵守以下优先级和成本边界：

1. 优先收集已绑定正文证据的因果事实、终章结算或 POV 硬问题；
2. 再从模型审稿的结构化 `completion.coverage_items` 收集 `status=missing` 且带稳定 `contract_id` 的必要剧本动作与交接；
3. 专项与语义目标去重，总数最多 4 项，只发出一次局部补丁调用；
4. 明确的决定或交接缺项绑定当前章末唯一尾段，新增内容必须通过现有原句做插入锚点；
5. 对白比例、句长偏好、可选润色等诊断不进入该计划，也不增加 `automatic_revision_attempts`。

Run C 原始事件 153/155 已完成只读重放：

```text
hard_contracts=1
allowed=true
anchors=3
2047-03-14归档
2087年11月17日14时23分
“有些档案，删掉是有原因的。”
```

同一 directive 同时包含日期因果修复、启动调查与联系苏敏交接；实际 Provider 补丁仍须由全新 Run D 验证，离线重放不等于真实接受。

## 12. 本轮本地门禁

- 新增/更新修订计划与锚点定向合同：`41 passed`；
- 质量候选、章节审稿和模型复检相关回归：`46 passed`；
- 后端全量：`1443 passed, 6 skipped, 1 warning`；
- Python `compileall`：通过；
- `git diff --check`：通过；
- 结构审计：无旧体量字段、无前端并行顶层目录；大文件只作为责任审查信号。

该门禁随后由同一 DeepSeek 三章合同下的全新 Run D 执行；结果见第 13 节。Run D 从 Info 开始并在首次不可自动闭合的质量失败处停止，没有通过隐藏预算、重复恢复或手改运行状态追求绿色结果。

## 13. Run D：动态章节容量与真实失败

Run：`phase25-real-deepseek-20260809-d`。

Run D 的第 2 章由两个场景组成，冻结 base 正文为 3205 字。旧逻辑把节点固定上限 3000 当成逐章硬卡尺，导致第二场已经自然完成仍被要求压缩。当前合同改为：

- 单章允许最多 `min(硬上限的 10%, 300 字)` 的局部自然波动；
- 当前章仍受全书剩余容量约束；
- 必须为每个后续章节保留最低容量；
- 场景可以借用当前章剩余容量，但必须为后续场景保留最低篇幅；
- 全书验收按章节顺序动态结算，最终总量仍不得越过 `book_soft_max_chars`。

Run D 第 2 章的动态上限为：

```text
min(3000 + 300, 7200 - 2279 - 1300) = 3300
```

两个场景共 3205 字，处于 3300 字动态上限内，因此应直接接受，不再压缩、不再重写。隔离副本使用“任何 Provider 调用立即报错”的探针恢复成功：第二场 1529 字、场景可用上限 1624、`provider_calls=0`、Token 不变、原 Run 哈希不变。

真实恢复进入质量层后，Run D 第 2 章仍以 `quality_budget_exhausted` 停止。冻结状态如下：

- base 正文 3205 字，保持 `prose_ready`；
- 一次局部修订产生 3467 字候选；
- 候选补上日志过载报告和章末三份证据交接；
- 候选同时把“3 月 14 日上报一次，之后又重复三次”与“已上报三次”写入同一物证，新增四次/三次计数矛盾；
- 候选被拒绝，正式正文恢复 base；Wiki、Canon 和 Narrative World 未写回；
- 不增加第二次 revision，不修改 Run JSON，不用隐藏额度推进。

## 14. 候选复检证据保护

Run D 还暴露了另一个独立缺口：候选复检把三项在 base 已经绑定、且在候选中逐字保留的合同误降为 `missing`，使语义覆盖率从 80% 错降为 70%。

当前候选复检遵守以下 ratchet：

1. 同一 `contract_id` 在 base 已为 `direct` 或 `pov_observable_equivalent`；
2. base 的 `evidence_spans` 仍能在候选正文逐字绑定；
3. 则候选审稿不得将该合同降为 `missing`；
4. 保护后重新规范化 `complete`、`coverage_ratio` 和 `missing_elements`；
5. 该保护只继承正向证据，不能提升 base 原本缺失的合同，也不能覆盖专项审稿发现的新矛盾。

Run D 冻结候选零调用回放结果：

```text
coverage_before=0.7
coverage_after=1.0
protected_contracts=3
semantic_regressed=false
new_hard_contracts=1
specialty_regressed=true
decision=reject_candidate
provider_calls=0
```

新的专项门禁不盲信 Provider 返回的 `kind`。当同一权威不变量的两端证据可定位、修订目标可定位且置信度足够时，即使模型误标为普通 `editorial`，明确事实矛盾仍会进入硬门。若模型省略中间一句，只允许同一段落内、顺序一致、间隔受限的多段逐字证据，并回填真实连续原文；“四十七秒与对白长度是否匹配存疑”这类推测仍只作为诊断。

修订 Prompt 同步增加一条短约束：同一事实只在一个必要位置修订；数量、日期和编号先核对全文，不得在另一处重复补写或重新计数。该 Prompt 约束只是辅助，最终安全性仍由确定性证据门禁保证。

## 15. Run D 后本地门禁

- 候选证据、因果硬门、ratchet 与审稿持久化定向测试：`100 passed`；
- 动态字数、场景容量、章节质量与整书验收定向测试：`72 passed`；
- 后端全量：`1445 passed, 6 skipped, 1 warning`；
- Python `compileall`、`git diff --check`：通过；
- 结构审计：无非法前端目录；大文件只作为责任审查信号；
- 前端全量：`137` 个测试文件、`530 passed`；
- 前端生产构建、CSS split 和 CSS audit：通过，首屏 CSS `32.0 KiB gzip`；
- 浏览器烟测：规划页可达，未激活 Run 的 `/run/text` 正确回到规划页，控制台无 error/warning，`/api/health` 返回 `ok`；
- 3D 图谱 vendor 仍是约 1.37 MB 的独立懒加载 chunk，作为后续性能观察项，不与本轮后端合同混改。

Run D 仍是失败验收样本。此处原定的全新 Run E 已实际执行，后续又执行了 Run F 和 Run G；三次真实结果见第 17 节。Run B 至 Run G 均不得追加隐藏额度或人工修改运行数据。

## 16. Phase 25 收口：历史审稿快照恢复边界

隔离回放继续发现一个恢复层问题：恢复代码在读取历史 `chapter_review_coordination_started` 事件后，曾调用当前版本的 `build_review_input_snapshot()` 重新计算 `snapshot_id`。路由规则在后续版本增加了专项原因时，当前 ID 必然不同；这不是正文、上下文或审稿数据漂移，而是把算法版本演进误判成篡改。

本轮已改为历史快照原样承接：

- `snapshot_id`、路由原因、审稿焦点、角色顺序和章节版本直接来自历史协调事件；
- risk 与 candidate budget 必须从同一候选窗口内的缓存专项报告读取，并要求所有角色口径一致；
- packet/scenes 仍从当前冻结章节解析，但必须与协调事件的 `context_signature`、候选正文签名、cold-edit 签名和 Chapter Artifact 签名逐项匹配；
- 协调起点、语义审稿、全部专项结果、协调完成、Provider operation 启动/成功结算和事件顺序继续完整校验；
- 恢复成功只生成零 Provider 的候选接受事件，不能改变预算、Wiki、Canon、Narrative World 或正式写回状态。

专项硬事实识别也补上了一个保守边界：审稿句未写出“矛盾”二字时，只有“对照语句 + 两个不同的带单位数值”才会进入候选硬事实绑定；随后仍必须通过权威 claim class、同一谓词/主体、两端逐字证据、可定位修订目标和高置信度检查。Run D 的“已上报三次 / 前文记载为四次”因此正确进入硬门；“动机转变缺乏铺垫”以及带有“可能/存疑”的文学诊断仍保持编辑意见。

全量回归还纠正了两个同层问题：相邻场景职责越界必须先进入专用 `scene_role_boundary` 绑定，再决定普通事实分类，不能被普通冲突关键词提前过滤；历史 causal contract check 若无法与当前目录逐字同名，只能在命中日期/数量/身份/机制等硬领域、正文证据逐字存在，且明确形成两端冲突或缺失机制链时生成稳定 prose-fact 合同，不能恢复模糊目录匹配。

### 本轮证据

- 恢复与相邻生命周期定向测试：`77 passed`；场景职责与因果专项回归：`34 passed`；
- 后端全量：`1483 passed, 6 skipped, 1 warning`；唯一 warning 为 FastAPI TestClient 的 Starlette/httpx2 迁移提示；
- `compileall`、`git diff --check`：通过；
- Run D 临时副本回放：`provider_calls=0`、`budget_changed=false`，结果为 `rejected_quality_candidate_recovery_refused`，原因是新增可绑定硬专项合同；
- 冻结 Run D/Run G 哈希在隔离回放前后均未变化；Run G 仍为 `e1118e29a5beb8715774c3b7407d27e3d41b3e9b2b84ceeb83a9ab92fea10734`；
- 结构审计：无旧体量字段、无非法 Pipeline 顶层目录；`rejected_quality_candidate_recovery.py` 超过 500 行，当前仍是一个完整的拒绝候选恢复事务边界，后续只在能独立测试事件血缘/状态提交职责时拆分，不做机械切文件；
- 端口 `5173/8787/8000/8010` 均关闭，本轮未启动服务；
- 当前仍未完成 Run H 三章真实 Provider 生产、章后 Narrative/Wiki/Canon 正式写回、Volume Commit、Export 和人工冷读，不能宣称整书或投稿验收通过。

## 17. Run E / Run F / Run G：真实 Provider 结果

三次 Run 均使用冻结 Run JSON、事件流和预算账本记录结果。调用数以已提交到 Run 事件流的 `provider_attempt_succeeded` 为统计口径；Token 以 `budget_state.run_consumed_tokens` 为权威口径。不得把当前 scope 与归档 legacy scope 的 operation 直接相加，否则恢复产生的归档镜像会重复计数。

| Run | 已提交成功调用 | 预算账本 Token | 停止位置 | 冻结结论 |
| --- | ---: | ---: | --- | --- |
| Run E | 2（另有 1 次已结算成功停留在 deferred events） | 22,237 | Outline `artifact_validation` | Info、Summary 已形成；Outline 的人物推进项只给出 `related_to` 或 `relation` 单边字段，结构合同拒绝，未进入 Detail |
| Run F | 9 | 82,294 | 第 1 章 `revision_patch_invalid` | 第 1 章原稿保持 `prose_ready`；局部补丁篇幅变化超过安全边界，未形成完成章节 |
| Run G | 19 | 184,989 | 第 3 章 `artifact_validation` | 第 1、2 章已完成；第 3 章只保存第一场候选，尚无完整 Chapter Artifact |

Run G 的冻结文件哈希为 `e1118e29a5beb8715774c3b7407d27e3d41b3e9b2b84ceeb83a9ab92fea10734`。第 3 章第一场正文为 1,817 字，原始内容签名为 `c51ee6f74d81a6fae5f664a114576a04b5f7693eed9c510f10916c332c42b6e8`。该签名只证明已保存场景正文的身份，不是整章审稿使用的 `review_content_signature`。

Run E/F/G 证明当前失败已从早期的 Provider 连接与大对象截断，推进到结构验证、补丁安全和章节恢复边界；它们没有证明三章闭合。不能用 Run G 的前两章成功替代第三章、卷提交、导出和人工冷读。

## 18. `recovery_replay` 分支合同与 Run G 隔离回放

`fork_from_current_state()` 过去只表达 `committed_revision`。该分支语义用于从已提交状态开始作者修订，完整血缘成立时会跳过普通尾部恢复；直接拿它恢复失败 Run 会错误绕过 `reopen_low_quality_chapter_tail()` 和检查点恢复。

当前合同明确区分两种分支：

- `committed_revision`：保持默认兼容，用于已提交内容的显式作者修订；
- `recovery_replay`：用于失败 Run 的隔离恢复验证，保留冻结预算、恢复状态、审批状态和检查点，运行相位标记为 `recovery_replay_ready`；
- `committed_revision_branch()` 只识别具备完整父 Run、状态摘要和 `committed_revision` 类型的分支，必须对 `recovery_replay` 返回 false；
- 两种分支都必须使用新 Run ID，来源 Run 的状态、事件、预算和文件哈希保持不变。

Run G 的临时目录副本已按 `recovery_replay` 创建隔离分支。`prepare_acceptance_recovery()` 返回第 3 章 `scene_repair_pending`，随后运行相位进入 `checkpoint_recovery`，没有修改正式 Run G。

第一场零调用复用按当前动态容量重新结算：

```text
chapter_acceptance_maximum = 3428
scene_budget = 650 / 1000 / 1499
为第二场保留最低容量后的第一场可接受上限 = 2776
冻结第一场 = 1817
```

因此第一场可在恢复分支中直接复用，不应调用 Provider 重写或压缩。该结论只开放“继续生成第二场”的可能性，不开放以下操作：

- 第 3 章尚无完整 Chapter Artifact，不能执行整章 `finale_payoff_auditor`；
- 尚无 ReviewSnapshot 和 `verification_required`，不能伪造专项复检；
- 尚未形成 `revision_patch_invalid + prose_ready`，不能提前开放局部补丁；
- Narrative/Wiki/Canon、Volume Commit 与 Export 必须等待整章审稿和质量门完成。

分支相关定向测试为 `16 passed`；加入该合同后的后端全量为 `1483 passed, 6 skipped, 1 warning`，`compileall` 与 `git diff --check` 通过。下一次真实 Provider 实验必须使用全新 Run H：先完成本地恢复分支的零调用场景复用，再决定是否允许第二场调用；只有三章正式闭合后才进入写回、卷提交、导出和人工冷读。
