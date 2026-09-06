# Phase 32 Wave 26：Project 创建权威与前端进入链路切换

状态：**Project 创建、作品库投影、进入首阶段与旧监控隔离切片通过；Phase 32 执行、SSE、Artifact 工作台和 Monitor 尚未完成生产切换**

日期：2026-08-23

## 产品决定

新建作品只有一个写入口：

```text
CreationIntent + WorkflowSelection
  -> POST /api/projects
  -> Phase32ProjectService
  -> Phase32CreationService
  -> Phase32 Project catalog + frozen Run definition/read model
  -> Version 20 Project Shell / Brief
```

向导不再先写 preparation、再由前端猜测 Project/Run；作品库、Header、阶段侧栏和刷新恢复都读取
同一份 Phase 32 Project 投影。路线在创建时冻结，阶段名称和顺序由 Phase 32 manifest 投影，旧
`fast / balanced / deep` 八阶段模板不能继续作为创建页的阶段语义。

## 正向生产路径

- `POST /api/projects` 接受 `idempotency_key + selection`，创建 `phase32-routes-v1` Project 和 Run；
- 项目投影返回 route revision、动态 stage manifest/status、active stage、target、usage、pending
  decisions、failure 和 progress；正式标题在 Brief 提交前保持“待定标题”；
- `GET /api/projects` 和 `PUT /api/projects/order` 分别成为作品库读取和拖拽排序权威；
- Version 20 新建向导按剧本样片、短中篇、长篇三条路线匹配模板，创建后进入 `/run/brief`；
- Header 与项目侧栏只从 Project manifest 渲染 6/7/8 个阶段，锁定阶段不可进入；
- Phase 32 Project 直达旧 `/monitor` 时只显示明确隔离页，不读取 Phase 27 监控数据。

## 同波拒绝与删除

- `POST /api/creation-wizard/prepare` 返回 `410 phase32_project_creation_required`；
- `POST /api/runs` 返回 `410 phase27_run_creation_retired`；
- Brief、Header、移动端入口和 Command Palette 不再为 Phase 32 Project 暴露旧监控入口；
- 删除 Creation Wizard 与 Runs route 中无用 imports，删除无消费者的前端
  `getProjectSummaries()`；
- Phase 27 Archive 仍只读，历史 Run 没有被恢复、改写或转换成新 Run 输入。

## 浏览器发现与最低责任修复

首次真实浏览器创建短中篇 Project 时，后端正确返回：

```text
brief -> story_map -> cast -> section_plan -> text -> cover -> export
```

但向导第一步把 Cast 放在 Story Map 前，第二步又把旧 Phase 27 八阶段 `workflow.nodes` 当成路线
阶段带，并显示“8 阶段生产合同”。最低责任层是前端 `creationWizard` 路线投影和
`WorkflowMatchStep`，不是后端 manifest。

修复后：

- 三条路线预览使用与后端 manifest 一致的 6/7/8 阶段名称和顺序；
- 官方模板显示为路线官方流水线，不再把极速/均衡/精细当成作品类型；
- 匹配卡只把旧模板作为模型、预算与审阅配置来源，不再把其八个节点冒充 Phase 32 路线；
- 作品库副标题覆盖剧本样片、短中篇和长篇，不再只写长篇小说。

新增合同测试证明同输入失败重试复用 idempotency key，改选流水线后轮换 key，并拒绝创建页
重新出现旧脊柱/八阶段投影。

## 验收证据

- 后端全量：`1016 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`10 files / 36 tests passed`；
- 前端 TypeScript/Vite production build：通过；既有 `CharacterGraph3D` 和主 chunk 大小 warning
  继续记录，不是本切片新增阻断；
- CSS audit、frontend structure audit：通过；
- 浏览器使用隔离临时后端和现有 `127.0.0.1:5176` Version 20 Vite，未调用 Provider；
- `1440x920`：创建短中篇 Project，确认 `POST /api/projects` payload、200 response、7 阶段
  manifest、锁定阶段、刷新恢复、返回书架和无双层 Loader；
- `1024x700`：Project Shell、Header 心电图、272px 项目侧栏和 Brief 内容区无重叠；
- `390x844`：桌面侧栏隐藏，左上移动端导航出现并可打开，底部状态栏与内容区无横向溢出；
- 创建第二个剧本样片 Project 后，拖拽真实触发 `PUT /api/projects/order`，随后
  `GET /api/projects` 读回相同顺序；
- 直达 `/monitor?project=...` 只显示 Phase 32 隔离提示；浏览器控制台为
  `0 error / 0 warning`。

## 未闭合边界

本切片不能宣称 Phase 32 完整生产切换：

1. `/api/phase32/runs` 尚未迁为正式 `/api/runs` 执行权威；
2. 旧 `/api/runs` 的 GET/start/decision 等 Phase 27 路由仍存在；
3. Phase 32 execution、SSE、Artifact、decision 和 Monitor 尚未接入 Version 20 active-run 合同；
4. 创建目录仍以旧 Phase 27 Workflow 记录作为模型/预算/审阅配置外壳；正式 Workflow 列表、
   详情编辑和复制仍需迁为 route-aware Phase 32 配置，才能删除 `official-deepseek-*` 与
   `quality_mode` 前端/后端读者；
5. 本轮没有调用真实 Provider，不证明后续阶段内容质量、连续性、成本或完整 Export。

下一切片应从正式 `/api/runs` 读写权威与 Version 20 active-run state 开始，垂直接通
start/resume -> SSE -> Artifact/decision -> Monitor，并在同一切片删除对应 Phase 27 reader；
不得通过 alias、converter、fallback 或双 SSE 维持两条生产链。
