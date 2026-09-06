# Phase 32 Wave 32.0 Dirty Worktree Inventory

状态：2026-08-22 基线盘点；生产代码尚未因 Phase 32 修改

## 1. 基线结论

- 当前分支已有用户未提交的 Phase 28/29 可靠性改动，必须原位吸收，禁止 reset、checkout、clean 或覆盖。
- Phase 32 开始前后端全量为 `777 passed, 1 warning`；warning 是既有 Starlette/httpx 弃用提示。
- closure audit 未发现 legacy/shadow/dual runtime marker 或异常 `apps/web/src/features/pipeline` 顶层目录。
- 现有改动主要解决 5 万字 Run 的 Detail source-bound recovery、no-op 拒绝、人物关系恢复、状态/线索连续性、Provider operation 持久化和显式 failure decision。
- 这些确定性能力应迁入新 unit/runtime 合同；旧三档模板、flat Spine Prompt 和固定八阶段投影将在替代路径通过时退出。

分类：

- `keep`：责任和语义可直接保留。
- `adapt`：能力保留，但需改为 route/stage/unit 动态合同。
- `supersede`：先保留当前唯一正确行为；新路径通过同 Wave 退出门后删除旧生产入口。
- `archive`：只保留历史证据，不进入新运行时。

## 2. 文档与运行时镜像

| 当前文件 | 归属 | Phase 32 处理 |
| --- | --- | --- |
| `docs/architecture/phase-28-v1.1-literary-reliability-and-author-control.md` | archive | 冻结为 5 万字失败/修复证据；后续结论写 Phase 32，不继续把旧 Fast Run 当新验收 |
| `docs/architecture/phase-32-three-creation-routes-reconstruction.md` | keep | 已批准的实施 RFC |
| `runtime/novel_workflow/prompts/prompt-brief.json` | supersede | 新 Brief Prompt 按 Screenplay/Novel artifact kind 建立后删除旧单一镜像 |
| `runtime/novel_workflow/prompts/prompt-spine.json` | supersede | Beat Board/Story Map/Book Architecture Prompt 通过后删除 |
| `runtime/novel_workflow/prompts/prompt-cast.json` | adapt | 保留 Cast 质量约束，改读 route-specific planning context |
| `runtime/novel_workflow/prompts/prompt-volumes.json` | adapt | 只保留 long route，并改读 Part/Book aggregate |
| `runtime/novel_workflow/prompts/prompt-detail.json` | adapt | 抽取 source-bound unit recovery，分别适配 Scene Deck/Section Plan/Rolling Detail |
| `runtime/novel_workflow/prompts/prompt-text.json` | adapt | 拆分 Script/ShortProse/LongChapter 任务，保留量化事实和局部恢复纪律 |
| `runtime/novel_workflow/workflows/official-deepseek-fast.json` | supersede | 三条新官方 Route workflow 完成后删除 |
| `runtime/novel_workflow/workflows/official-deepseek-balanced.json` | supersede | 三条新官方 Route workflow 完成后删除 |
| `runtime/novel_workflow/workflows/official-deepseek-deep.json` | supersede | 三条新官方 Route workflow 完成后删除 |

## 3. 后端生产文件

| 当前文件 | 归属 | Phase 32 处理 |
| --- | --- | --- |
| `src/novel_workflow/api/routes/runs.py` | adapt | 保留薄路由与 project-owned input 冻结调用；请求改为 route-aware RunDefinition |
| `src/novel_workflow/workflows/run_inputs.py` | adapt | 保留 project idea 唯一权威；从固定 Brief node 改为 compiled manifest 的 Brief capability |
| `src/novel_workflow/workflows/prompt_templates.py` | supersede | 新 route prompt registry 完成后删除旧固定七 Prompt 列表 |
| `src/novel_workflow/output_contracts/artifacts_vnext.py` | adapt | 保留已验证字段/校验，按 route artifact responsibility 拆分；删除 StorySpine/flat Detail 新 Run authority |
| `src/novel_workflow/output_contracts/prompt_materials.py` | adapt | 保留 source-bound recovery materials，改用通用 PlanningUnit/ProseUnit refs |
| `src/novel_workflow/output_contracts/provider_tasks.py` | adapt | 保留严格 Provider task/semantic receipt，按 artifact kind 注册 |
| `src/novel_workflow/quality/custody_contracts.py` | keep | 作为确定性状态 transition 规则保留；从中文 marker 实现逐步迁到 resolved-state contract |
| `src/novel_workflow/quality/narrative_contracts.py` | adapt | 保留确定性状态/线索/人物边界；拆出通用与 route-specific validators，文学判断降级 warning |
| `src/novel_workflow/runtime/graph/chapter_evidence.py` | adapt | 保留 accepted prose -> Evidence 责任，支持 Script/ShortProse/LongChapter source kinds |
| `src/novel_workflow/runtime/graph/chapter_scene_facts.py` | adapt | 保留 source/owner/custody 投影，改为通用 prose unit evidence helper |
| `src/novel_workflow/runtime/graph/context_compiler.py` | adapt | 改为 route/stage/unit policy；保留污染隔离和 source-bound snapshot |
| `src/novel_workflow/runtime/graph/detail_preflight.py` | supersede | 抽取通用 deterministic planning-unit validators；flat Detail 入口在替代后删除 |
| `src/novel_workflow/runtime/graph/failure.py` | keep | 保留最低责任层、Provider result reuse 和明确 stop gate |
| `src/novel_workflow/runtime/graph/narrative_graph.py` | supersede | RouteGraphCompiler 通过后由动态图替换固定八阶段 graph |
| `src/novel_workflow/runtime/graph/output_budget.py` | adapt | 改为 route scale envelope；删除旧 mode tolerance 和精确 turn 配额 |
| `src/novel_workflow/runtime/graph/provider_contract_compiler.py` | adapt | 以 artifact kind/workbench task 注册 Schema，不读固定 StageId |
| `src/novel_workflow/runtime/graph/provider_gateway.py` | keep | 保留冻结 Provider binding、receipt 和无 fallback 语义 |
| `src/novel_workflow/runtime/graph/provider_input_compiler.py` | adapt | 保留冻结输入、source-bound recovery 和禁止字段；按 route context policy 拆分 |
| `src/novel_workflow/runtime/graph/provider_prompt_compiler.py` | adapt | 保留严格渲染与镜像一致性；按 route artifact task 选择 Prompt |
| `src/novel_workflow/runtime/graph/runtime.py` | adapt | 保留单 LangGraph/checkpointer、interrupt/resume、projection；stage mapping 动态化 |
| `src/novel_workflow/runtime/graph/stage_executor.py` | adapt | 逐责任拆出 planning unit、prose unit、delivery executor；不机械拆行数 |
| `src/novel_workflow/runtime/graph/stage_graph.py` | adapt | ReviewPolicy 取代 `quality_mode == fast`；保留 candidate/decision/commit/checkpoint lifecycle |
| `src/novel_workflow/runtime/graph/state.py` | adapt | 固定 StageId mapping 改为 compiled manifest 校验的动态 refs |
| `src/novel_workflow/runtime/graph/cast_relation_recovery.py` | adapt | 保留冻结 dossier reuse 和一次显式关系恢复；去除 old mode/stage attempt 假设 |
| `src/novel_workflow/runtime/graph/detail_failure_recovery.py` | adapt | 保留 source-bound segment reuse、preserved units 和 no-op stop；推广到 route planning units |
| `src/novel_workflow/runtime/graph/planning_proposal_graph.py` | keep | 作为共享 bounded proposal 子图保留，StageId 改 RouteStageId 后复用 |

## 4. 测试与 fixture

| 当前文件 | 归属 | Phase 32 处理 |
| --- | --- | --- |
| `tests/fakes.py` | adapt | Fake Provider 增加三 route artifact/task，保留失败注入能力 |
| `tests/fixtures/prompt-material-contract.json` | adapt | 更新为 route/unit Context receipt，不保留旧 Spine/Detail 执行输入 |
| `tests/test_artifacts_vnext.py` | supersede | 新 artifact contract 测试覆盖后删除固定 STAGE_ORDER/StorySpine 断言 |
| `tests/test_author_collaboration.py` | adapt | 保留线程、Context receipt、Patch Candidate 和权限边界，扩展 stage capability |
| `tests/test_chapter_scene_generation.py` | adapt | 参数化 ShortProse/LongChapter/Script 单元；保留持久事实和长度 warning |
| `tests/test_detail_stage_contract.py` | adapt | 迁为 Scene/Section/RollingDetail planning-unit 合同 |
| `tests/test_dynamic_provider_schema.py` | keep | 保留动态 Schema、editable-only recovery 和禁止字段测试，加入 artifact kind registry |
| `tests/test_evidence_recovery.py` | adapt | 参数化 prose source kind；保留 accepted version 和 exactly-once 写回 |
| `tests/test_langgraph_narrative_runtime.py` | adapt | 拆出 route graph 场景，保留重启/重放/no-op/显式 decision 证据 |
| `tests/test_output_budget.py` | adapt | 改测 route scale envelope、最低可用门和无机械凑数 |
| `tests/test_planning_contracts.py` | adapt | 保留状态/线索/人物/恢复正反例，迁到新 Artifact refs |
| `tests/test_project_api.py` | adapt | 保留项目 idea 唯一权威；增加 route/revision/旧字段拒绝 |
| `tests/test_provider_prompt_compiler.py` | adapt | 增加三 route Prompt/Context/forbidden fields 镜像门 |
| `tests/test_provider_task_contracts.py` | adapt | 增加 Beat/StoryMap/Book/Scene/Section/Window/Script task 合同 |

## 5. Wave 32.0 退出条件

- [x] 用户批准 Phase 32 三路线 RFC。
- [x] `stage-artifact-contract.md` 改为 Phase 32 canonical。
- [x] 当前 dirty 文件有明确 `keep/adapt/supersede/archive` 归属。
- [x] 当前全量后端基线通过：`777 passed, 1 warning`。
- [x] closure audit 无第二 runtime 与异常前端目录。
- [x] Phase 32 文档与 inventory 完成格式检查并写回执行证据。

格式证据：三份文档代码围栏计数分别为 `34 / 8 / 0`，均为偶数；目标文档 `git diff --check` 通过。

Wave 32.0 已关闭并进入 Wave 32.1。该结果不证明 Route Kernel、三条 Graph、前端或真实 Provider 已完成。
