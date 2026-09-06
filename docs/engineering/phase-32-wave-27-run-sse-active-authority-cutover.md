# Phase 32 Wave 27：Run、SSE 与 Active Run 正式权威切换

状态：**正式 Run API、执行命令、SSE、Version 20 active-run、运行监控和创作历史切换通过；Artifact payload 工作台、作者协作、Story Bible 与 Cover assets 尚未迁移**

日期：2026-08-23

## 产品决定

Project 创建后，运行状态只有一条正式读取与执行链路：

```text
Phase 32 Project.latest_run_id
  -> GET /api/runs/{run_id}
  -> Phase32RunRepository + Phase32HistoryProjection
  -> Version 20 useActiveRun
  -> Header / Shell / Stage status / Monitor / History

GET /api/runs/{run_id}/events?after={sequence}
  -> Phase32EventProjection
  -> api/sse.py
  -> cursor-aware frontend stream
```

`/api/runs` 不再同时代表 Phase 27 历史运行和 Phase 32 正式运行。历史 Phase 27 Run 只允许从
独立 archive reader 查看，不能恢复、写入或转换成 Phase 32 可执行输入。

## 正向生产路径

- `GET /api/runs` 从 `Phase32HistoryProjection` 返回动态路线、阶段 manifest、active unit、
  pending decision、checkpoint、Provider operation 与 Token 用量；
- `GET /api/runs/{run_id}` 返回冻结 definition、权威 read model 和同源 summary；
- `GET /api/runs/{run_id}/events` 通过唯一 `api/sse.py` 消费
  `Phase32EventProjection`，按 sequence cursor 续传并在 terminal projection 后关闭；
- `POST /api/runs/{run_id}/start` 和 `POST /api/runs/{run_id}/decisions` 分别调用
  `Phase32RunExecutionService.start()` 与 `.resume()`，保留 operation、decision receipt、
  checkpoint 和幂等恢复边界；
- Version 20 `useActiveRun` 先读取 Run envelope，再从同一事件流批量刷新；断线从最后 sequence
  续传，不使用计时器伪造进度；
- Header 心电图、阶段状态、项目侧栏、移动端监控入口和创作历史都读取动态 manifest/read
  model，不再读取旧固定八阶段或 `quality_mode`；
- 新监控台使用 `272px` 动态阶段栏、阶段内容/事件主区和 Inspector，显示 Artifact 引用、
  pending decision、Provider usage/cost、checkpoint、连接与恢复状态；
- Phase 32 未迁移阶段不再回落旧 Cast/Volumes/Text/Cover/Export 工作台，而是显示显式迁移状态。

## 同波拒绝与删除

- `POST /api/runs` 返回 `410 phase27_run_creation_retired`，Project 创建仍只有
  `POST /api/projects` 一个权威；
- `POST /api/runs/{run_id}/resume` 返回 `410 phase32_resume_alias_retired`，决策只允许发送到
  `/decisions`；
- `/api/phase32/runs` 及其所有子路径返回 `410 phase32_run_alias_retired`，不保留第二套正式
  URL；
- 删除旧 `api/routes/run_history.py`、旧 `archive/legacy_run_viewer.py` 和独立 Phase 32 SSE/
  route 适配文件；Phase 32 SSE 合并到唯一 `api/sse.py`；
- Version 20 Phase 32 路由不再把 legacy GraphRunEnvelope、legacy run events 或旧阶段工作台
  作为兜底；
- 监控台在正式 Artifact payload reader 开放前不显示“接受候选”操作，避免作者在看不到内容时
  盲目提交决定。

## 浏览器发现与最低责任修复

首次空 manifest 渲染时，Header 心电图在首帧计算出非数值宽度，浏览器报告 SVG
`width="NaN%"`。最低责任层是 `StageProgressTrace` 的空 manifest 投影，不是 CSS 或后端事件。

修复后：

- 无 Project/Run manifest 时进度为稳定空态，不向 SVG 写入非数值属性；
- 新增 Shell 回归测试覆盖空 manifest 首帧；
- 监控页在桌面、短桌面和移动端保持满高，不出现横向溢出或旧侧栏竞争；
- 历史页打开记录时先读取正式 Project，再进入该 Project 的 `/run/brief`。

## 验收证据

- 后端全量：`1018 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 后端 Run/SSE 目标集：`34 passed, 1 warning`；
- Python `compileall`：通过；
- 前端全量：`15 files / 44 tests passed`；
- TypeScript/Vite production build：通过；主 chunk 与 `CharacterGraph3D` 大小 warning 继续作为
  性能债，不是本切片新增阻断；
- CSS audit：`151129 bytes` 基线、无跨文件重复 selector、无重复 keyframe；
- frontend structure audit：通过，共 `117` 个 TypeScript 源文件；
- CSS build check：首屏 CSS gzip `29.5 KiB`；
- 浏览器视口 `1440x920`、`1024x700`、`390x844` 通过，控制台
  `0 error / 0 warning`，移动端 `scrollWidth === innerWidth === 390`；
- 浏览器正式网络路径为 `/api/runs/{id}`、`/events?after=0` 和
  `/api/runs?limit=50`；
- 截图：`output/playwright/wave32-27-monitor-1440x920.png`、
  `wave32-27-monitor-1024x700.png`、`wave32-27-monitor-390x844.png`、
  `wave32-27-history-1440x920.png`；
- 浏览器未点击“启动流水线”，本轮未调用 Provider、未恢复或推进历史 Run。

## 未闭合边界

本切片不能宣称 Phase 32 工作台或完整产品切换已经完成：

1. 正式 Artifact payload、候选读取、draft、decision 编辑与 committed content reader 尚未开放，
   监控台当前只能安全显示引用和运行状态；
2. Cast、Volumes、Text、Cover、Export 等 Phase 32 专业工作台仍待按路线 Artifact 合同迁移；
3. `author_collaboration.py`、`story_bible.py`、`cover_assets.py` 和 `api/bootstrap.py` 仍消费旧
   `narrative_stores`，属于后续 Wave 32.8/32.9 的垂直迁移与删除范围；
4. Phase 32 作者协作入口因此没有回接旧 Dock；它必须先迁移 source-bound patch、amendment、
   Evidence/Outbox 和权限边界；
5. Workflow 正式配置仍有旧模板外壳，`official-deepseek-*` 与旧 `quality_mode` 的所有生产读者
   尚未完成静态删除；
6. 本轮没有新的真实 Provider Run，不证明后续 Artifact 内容质量、连续性、完整 Export 或文学
   验收。

下一切片应先建立正式 Artifact payload/read/write/decision 垂直闭环，再迁移一个共用阶段工作台；
不得让 Version 20 页面回读 legacy `narrative_stores`，也不得在内容不可见时开放接受决定。
