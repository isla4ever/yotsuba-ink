# Phase 32 Wave 46: amendment successor Run 与恢复闭环

状态：后端正式 successor Run 路径已完成本地离线、Fake Provider 与恢复门。Version 20 的 amendment / impact / branch 交互、正式 Canon/Wiki writeback、真实 Provider、文学冷读和发布门不在本轮完成范围。

## 根因与产品决定

Wave 45 在 committed 规划 Artifact apply 后会把原 Run 投影为 `needs_action`，但没有合法的继续路径。直接清空 stale 状态并复用原 checkpoint 会混淆修订前后的运行身份，且可能把旧 accepted Script/Text 与新规划串成同一条可执行历史。

本轮只保留一条正式处置路径：

```text
applied amendment + stale source Run
  -> immutable branch plan
  -> new GraphRunDefinition / Run / thread identity
  -> copy committed predecessors before stale frontier
  -> seed successor at earliest stale stage
  -> append Project lineage and bidirectional run.branched events
  -> durable branch receipt
  -> successor uses a fresh LangGraph checkpoint
```

具体决定：

1. 原 Run、旧 committed Artifact、accepted Script/Text prefix 和事件永久保留；原 Run 继续为 `needs_action` 只读对照，不恢复执行。
2. successor 继承最早 stale stage 之前的 committed 规划 Artifact，从 stale frontier 开始执行；历史正文/剧本 prefix 不复制为新 Run 的初始执行状态。
3. successor 冻结与 source 相同的 route、Workflow、Scale、Inputs、Provider bindings 和 Export profile，但使用新的 Run/thread/definition/checkpoint 身份。
4. target Run id 由服务端的内容寻址 command 生成；客户端不能指定 target，也不能切换 route 或临时覆盖 Provider binding。
5. 一个 amendment 永久只允许一个 branch plan。idempotency key 只能恢复同一命令，不能产生第二个 successor。
6. Project lineage 必须包含相邻 `source -> successor` 边。receipt 中断后即使 Project 已继续追加后续 Run，只要该边仍存在就可以恢复；receipt 已完成后 lineage 或 provenance 漂移则明确阻断。
7. branch provenance 使用 `run.branched`。没有真实 checkpoint 写入时禁止借用 `checkpoint.saved`，避免监控台报告不存在的检查点。
8. 不提供原 Run 就地 repair。未来若需要其他类型的作者分支，必须建立与其 Artifact/accepted-history 语义匹配的新合同，不能复活通用 checkpoint branch。

## 权威与恢复顺序

| 概念 | 唯一权威 | 恢复要求 |
| --- | --- | --- |
| branch plan / amendment-plan pointer | `Phase32AmendmentBranchStore` | plan 先于任何 target 写入；同 amendment 的第二 plan 拒绝 |
| successor definition/state/read model | `Phase32RunRepository` | 已存在时必须与 immutable plan 完全一致 |
| inherited planning Artifact | `Phase32ArtifactStore` | 跨 Run 复制后仍保持同一内容寻址 committed ref |
| Project lineage | `Phase32ProjectCatalogStore` | 只追加相邻 source/target；已存在的合法边幂等复用 |
| branch provenance | source/target Run event journal | 两端各一个 `run.branched`，event id 幂等 |
| completion receipt | branch store | 只在 target、Artifact、lineage 和事件均完成后写入 |

允许的中断点包括 plan、Artifact copy、target create、target event、Project append、source event 和 receipt 之间。恢复重放不得生成第二 target、重复事件或重复 Project id。receipt 快速重放仍会核验不可变 target definition、复制 Artifact、lineage 相邻边与双向 provenance；它不绑定 successor 的“当前”Artifact 投影，因为 successor 后续可以合法产生自己的 amendment。

## HTTP 与 Graph

新增正式接口：

```text
GET  /api/runs/{run_id}/planning/amendments/{amendment_id}/branch
POST /api/runs/{run_id}/planning/amendments/{amendment_id}/branch
```

POST 只接受 apply receipt、source domain revision 和 idempotency key。生产 OpenAPI 对该路径只注册 `GET / POST` 各一次。

共享 `route_graph` 的 START 入口读取冻结 `state.active_stage_id`。普通新 Run 仍从 Brief 开始；successor 从 stale frontier 开始。Graph 不读取 source checkpoint，也不为继承阶段再次调用 Provider。

## 同波删除与拒绝

- 删除未接生产的 `orchestration/phase32_branch_contract.py` 及其旧 branch fixture。该模块允许客户端 target id、旧 checkpoint frontier 和未来 Provider binding override，与正式 amendment successor 合同冲突。
- 保留独立 `Phase32RunPreflight` 测试和三路线共享 Graph fixture；删除的只是第二套 branch 权威，不是运行前校验或动态路线执行能力。
- branch 事件删除对 `checkpoint.saved` 的语义借用，统一改为 `run.branched`；监控投影同步显示“修订分支已创建”。
- source 非 Project 最新 Run、错误 apply receipt/domain revision、pending decision、第二 plan、target/lineage/provenance 漂移和客户端自造 target 均拒绝。

## 验证证据

- 三条路线均从 completed/Export source apply Brief amendment，successor 首个 Provider 请求从各路线最早 stale stage 开始；Brief 不重跑，最终均完成 Export。
- source Run 保持 `needs_action`；旧 accepted Script/Text prefix 不变，successor 初始状态不复制历史正文/剧本。
- 模拟 receipt 前中断后可恢复；Project 在合法 successor 后继续前移仍可补齐 receipt；换 idempotency key 不能创建第二 plan；receipt 后 lineage 漂移被拒绝。
- `run.branched` 在 source 与 target 各写一次，重放不重复；复制 Artifact、target definition 和 receipt 均内容寻址校验。
- branch/amendment/Artifact/Project/Graph/SSE/边界定向回归通过；最终后端全量为 `1103 passed, 1 warning`，warning 为既有 Starlette/httpx TestClient 弃用提示。
- 前端全量：`65 files / 155 tests passed`；TypeScript/Vite production build、structure audit、CSS audit、CSS build check 和目标 `oxfmt --check` 通过。
- structure audit：`193` 个生产 TypeScript 文件，无异常 pipeline 顶层目录。
- CSS audit：`435351 bytes / 3168 rules / 3575 selectors`，跨文件重复 selector `0`；首屏 CSS `29.4 KiB gzip`。
- Python `compileall`、production closure audit 与 `git diff --check` 通过。closure audit 未发现旧模式字段或前端目录漂移；既有超大文件继续作为技术债，不属于本轮新增第二责任。
- production build 仍有既存主入口与 `CharacterGraph3D` 大 chunk 提示；本轮没有新增 UI chunk 或 CSS。
- 本轮未启动 API/Vite；最终检查确认 `5176` 与 `8787` 均无监听。

## 验收边界

本轮证明 amendment apply 后可以通过一个新的、可恢复的 successor Run 继续三条路线，并保持 source 历史不可变。它不证明 Version 20 已能创建或查看 amendment branch，也不证明正式 Canon/Wiki writeback、浏览器交互、规模/性能、真实 Provider 成本/稳定性、文学质量、README、commit、push、Tag 或 Release 已完成。
