# Phase 32 Wave 48: Canon/Wiki Writeback Closure

日期：2026-08-26

状态：已关闭（2026-08-26）。本文只记录正式 Phase 32 写回合同与本 Wave 证据；不授权真实 Provider、历史 Run 恢复、Git 提交或推送。

## 1. 当前权威图与最低责任问题

| 概念 | 当前 writer | 当前 reader | 持久化 owner | 恢复 owner | 竞争来源 / 缺口 |
| --- | --- | --- | --- | --- | --- |
| accepted Script/Text | `Phase32RouteDriver.commit_stage()` | 下一单元 Context、Delivery、Story Bible | `Phase32ArtifactStore` + `SequentialStageProgress` | Phase 32 checkpointer + Run repository | 当前在 Artifact commit 后立即推进 accepted prefix，没有等待正式写回 |
| Evidence | 退役 Phase 28 `chapter_evidence.py` | Phase 28 Context/Story Bible | 旧 `EvidenceStore` | 旧 chapter graph interrupt | Phase 32 没有 source-bound Evidence identity，也没有 Script/Short/Long 共用合同 |
| Canon | 退役 Phase 28 `chapter_writeback.py` | 旧 Context resolver | 旧 `CanonStore` | 旧 `DomainOutbox` | Phase 32 不读取也不写入；旧 writer 不能接到新 Run |
| Wiki | 旧 `DomainOutbox.flush()` | 旧 Story Bible | 旧 `WikiProjectionStore` | 旧 Outbox 重放 | Phase 32 Story Bible 仍硬编码 `pending_contract` |
| writeback event | 无 Phase 32 writer | SSE、监控已有事件标签 | Phase 32 event journal | Phase 32 event replay | `writeback.committed/failed` 只存在于事件枚举，没有正向生产发射器 |
| process recovery | 无 Phase 32 writeback recovery | 无 | 无 | 无 | Canon 已提交、Wiki 未投影时没有 Phase 32 reconciliation owner |

根因是 Phase 32 的 accepted Artifact 生命周期在 `artifact.committed` 处提前结束，而 Evidence、Outbox、Canon/Wiki 仍停留在退役 graph 的 chapter-only 身份中。把旧 `chapter_writeback` 直接挂到新 driver 会重新引入第二套 State、事件、恢复和 `chapter_version_id` 语义，因此拒绝该方案。

## 2. 产品决定

正式路径固定为：

```text
accepted Screenplay scene / Short prose unit / Long chapter
  -> immutable source text + bounded source spans
  -> provider fact proposal under the frozen writing-stage execution binding
  -> deterministic subject/span/source validation
  -> Phase 32 Evidence records
  -> durable Phase 32 Outbox intent
  -> Canon commit
  -> Wiki projection
  -> immutable writeback receipt
  -> writeback event + Story Bible read-only projection
  -> next sequential unit
```

产品边界：

1. accepted Script/Text Artifact 永远不可原地覆盖；Evidence recovery 不能生成新正文版本。
2. Provider 只能提出 facts，并只能引用代码提供的 span id、冻结 subject ref 和现有 fact ref；source Artifact、Evidence id、transaction id、lifecycle 和提交状态由代码拥有。
3. 允许一次自动合同纠正；传输重试继续服从已有 operation lease，文学判断不触发隐藏重试。
4. 没有可支持的 durable fact 时允许返回空 proposal，系统仍保存可审计的零事实写回回执，不强迫模型发明事实。
5. Canon 是不可变事实账本；Wiki 是由 Canon transaction 重建的只读投影；Story Bible 只读消费二者，不获得编辑权。
6. Outbox 分别记录 `queued -> canon_committed -> committed`，进程在任一步退出后只重放未完成的确定性提交，不重复 Provider 调用。
7. 写回未完成时不推进 accepted prefix。页面只提供“重试写回”和“取消 Run”，不把 Evidence 失败伪装成正文质量失败。

## 3. 正向生产路径

- `output_contracts/phase32_writeback.py`：Provider proposal、Evidence、Canon fact 与 receipt 的类型合同。
- `storage/phase32_evidence_store.py`：source-bound Evidence 与 proposal attempt。
- `memory/phase32_canon_store.py`：Phase 32 Canon transaction 唯一 writer。
- `memory/phase32_wiki_projection.py`：按 Canon transaction 幂等重建 Wiki。
- `storage/phase32_writeback_outbox.py`：分阶段 Outbox 与进程恢复状态。
- `orchestration/phase32_writeback.py`：Provider proposal、确定性校验、Evidence、Outbox 与 reconciliation 编排。
- `route_graph.py`：Artifact commit 后执行写回；只有 receipt committed 才接受当前 unit。
- `phase32_story_bible_projection.py`：读取正式 Canon/Wiki 回执和事实，不再显示 `pending_contract`。

API routes 保持薄适配，不承载 proposal、校验、Outbox 或 reconciliation 规则。

## 4. 同 Wave 删除与拒绝项

- 删除 Phase 32 Story Bible 的 `formal_writeback_status=pending_contract` 占位合同与“正式修订合同完成后接入”文案。
- Phase 32 模块禁止导入退役 `chapter_evidence.py`、`chapter_writeback.py`、旧 `DomainOutbox`、旧 `CanonStore` 或旧 `WikiProjectionStore`。
- 不增加空 Evidence 静默成功、直接写 Canon、Provider 写 ID、旧 Run converter、runtime selector、fallback 或第二套 UI 本地进度。
- 旧 Phase 28 文件只保留为历史实现和回归证据；`/api/runs`、Phase 32 driver、Story Bible 与监控不得调用它们。

## 5. 退出门

必须同时证明：

1. 正向：三条路线各一个 accepted unit 产生 source-bound Evidence、Canon、Wiki 和 committed receipt。
2. 拒绝：candidate、错误 source ref、未知 span/subject、accepted identity 漂移均不能写 Canon/Wiki。
3. 幂等：重复 accept/resume 不重复 Provider、Evidence、Canon、Wiki 或事件。
4. 中断恢复：分别模拟 Provider return 后、Outbox queued 后、Canon commit 后退出；新进程只补齐剩余步骤。
5. 投影：SSE/监控与 Story Bible 使用正式 receipt，页面不显示 raw JSON，写回恢复动作可用。
6. 静态：Phase 32 生产路径无旧 writer import，closure audit 无 legacy marker 或异常前端目录。
7. 全量：后端、前端、production build、CSS/结构门通过后，才启动 Fake Provider 浏览器矩阵；本 Wave 不调用真实 Provider。

## 6. Wave 48 验收证据

### 6.1 后端合同与恢复

- Phase 32 execution-service 回归测试：`22 passed`。
- 普通阶段决策绑定 `candidate_artifact_refs`；`writeback_recovery` 使用已经接受的 committed Artifact，并校验 stage、active unit、receipt、原候选前缀和决策类型。
- Canon 已提交、Wiki 首次投影失败时，Run 进入 `writeback_recovery`；`retry_writeback` 只重放确定性写回，不重新生成正文。恢复成功后才推进下一个顺序单元。
- 四条隔离路线均由 `_FixtureGateway` 提供脱敏固定响应；未读取真实 API Key，未调用外部 Provider。

### 6.2 三路线浏览器矩阵

| Run | 路线结果 | 写回重试 Provider 请求 | 浏览器状态 |
| --- | --- | ---: | --- |
| `wave48-screenplay-recovery-run` | `script -> export` 完成 | 1 | `1440x920` 无横向溢出，单 Loader |
| `wave48-short-recovery-run` | `text -> cover` 待封面决策 | 1 | `1024x700` 无横向溢出，单 Loader |
| `wave48-long-recovery-run` | 写回后进入 `chapter-2` 待决策 | 1 | `390x844` + Reduced Motion；取消确认 Escape 可关闭 |
| `wave48-long-bible-recovery-run` | 保持 `writeback_recovery` | 0 | Story Bible 连续性页显示恢复提示，未越权补写 |

短篇与长篇恢复 Run 的事件日志各包含恰好 1 条 `retry_writeback`；Provider operation store 各只有 1 个写回 operation，证明重试没有重复生成正文或无界增加调用。

### 6.3 Story Bible 投影证据

- 恢复态截图：`output/playwright/wave48-writeback/story-bible-recovery-continuity-1440x920.png`。
- 已提交态截图：`output/playwright/wave48-writeback/story-bible-committed-continuity-long-1440x920.png`；页面显示“已核验 1 条正式事实”，并标注 Canon/Wiki 已完成只读投影。
- 其他路线截图：`screenplay-recovery-1440x920.png`、`short-recovery-1024x700.png`、`long-recovery-390x844-reduced.png`。
- 浏览器控制台仅观察到隔离环境无法访问 Google Fonts CDN（`ERR_CONNECTION_CLOSED`）；没有 React、应用 JavaScript 或 API 错误。该网络资源问题不影响本地字体回退和交互验收。

本 Wave 的 Fake Provider、写回恢复、三路线投影、浏览器证据、后端/前端全量、生产构建与 CSS/结构审计均已完成，详见第 7 节全量门结果。

## 7. 全量门结果

- 后端：`.venv/bin/pytest -q` 为 `1123 passed, 1 warning`；`.venv/bin/python -m compileall -q src tests` 通过。
- 前端：`68` 个 Vitest 文件、`170` 个测试通过；`tsc --noEmit` 与 `pnpm build` 通过。
- 前端静态门：`pnpm audit:css`、`pnpm audit:structure`、`pnpm check:css-build` 与 `pnpm exec oxfmt --check src` 全部通过；首屏 CSS gzip `31.6 KiB`，跨文件重复 selector 为 `0`，重复 keyframe 为 `0`，结构审计识别 `201` 个 TypeScript 源文件。
- 生产构建保留既有主入口和 `CharacterGraph3D` 大 chunk 提示；本 Wave 未扩大首屏或新增持续动画循环，不将该提示误报为本 Wave 性能通过。
- `closure_audit.py`：无 runtime legacy marker、无异常 `features/pipeline` 顶层目录；超过 500 行的历史/实现重模块已列入输出，未因行数机械拆分。
- `git diff --check` 通过。隔离 API、Vite 和 Playwright 已停止，`5176/8787` 端口均已关闭；本 Wave 临时运行数据已清理。

Wave 48 因此满足本 Wave 的正向合同、拒绝/幂等回归、进程恢复、只读投影、Fake Provider 浏览器与全量离线门；真实 Provider、自动无障碍、规模/性能、文学冷读和 `0.1.0` 发布门仍按 Phase 32 总计划单独执行。
