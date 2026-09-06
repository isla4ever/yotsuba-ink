# Phase 32 Wave 38：剧本专业交付工作台闭环

状态：**剧本样片 `ScriptDeliveryArtifact` 已完成确定性文件物化、不可变回执、列表/下载 API、Version 20 专业交付工作台和五视口浏览器验收；本轮没有调用真实 Provider，也没有改写历史 Run**

日期：2026-08-24

## 产品决定

剧本 Export 是已接受剧本版本的确定性交付，不是新的内容生成阶段。

1. Export commit 只读取冻结 `ScriptDeliveryArtifact` 与 ordered committed Scene 版本；
2. Fountain、PDF 和 Markdown 在提交时一次性物化，点击下载只读取不可变文件；
3. 文件名和作品库标题只来自 committed Brief 的正式 `title`，不从向导输入、route ID 或占位标题推导；
4. `artifact_ref / artifact_digest / scene_refs / scene_version_refs / size / sha256` 共同构成交付回执；
5. UI 是只读交付清单和下载控制台，不复用旧小说 Export 表单，也不提供输入框。

## 后端合同

- `ScreenplayBriefArtifact` 与 `NovelBriefArtifact` 新增必填正式标题，并拒绝“待定标题”“未命名作品”“screenplay_sample”等占位值；
- 三条官方路线升级到 `r3`；`screenplay_brief` Prompt revision 为 `v4`，`novel_brief` 为 `v3`；
- `ExportStore.materialize_script_delivery` 按 Artifact 中冻结格式顺序生成文件，重复执行返回相同回执；
- Fountain 和 Markdown 使用 UTF-8；PDF 使用 ReportLab、`STSong-Light` 中文字体与 invariant 模式，保证相同输入得到稳定内容哈希；
- 文件内容、大小或 SHA-256 与回执不一致时读取失败，不静默覆盖损坏文件；
- `GET /api/runs/{run_id}/exports` 返回 committed Export Artifact 绑定的文件回执；
- `GET /api/runs/{run_id}/exports/{export_id}` 返回冻结文件，并携带内容类型、UTF-8 文件名和 `X-Content-SHA256`；
- Export 不绑定 Provider，不产生新的文学 Artifact，也不改变已接受 Scene。

## 前端结果

- 新增剧本交付 Artifact/回执解析、绑定校验、Scene Manifest 与文件 SHA-256 校验；
- 工作台由 184px 交付文件轨道、主 Scene Manifest 和右侧不可变交付回执组成；
- 完整性摘要显示文件校验、Scene 覆盖、正文块数量和 committed 来源版本；
- 点击文件可切换回执，点击下载后状态从“就绪”切为“已下载”；请求或哈希失败会显示明确错误；
- 1024px 下完整性摘要改为 2x2，四项均完整显示；390px 下文件轨道转为顶部横向栏，回执隐藏，页面无横向溢出；
- 页面没有正文输入框，下载不会触发整页 loading 或 Provider 请求。

## 浏览器证据

隔离环境：

- Fake Provider/API：`127.0.0.1:8794`；
- Vite：`127.0.0.1:5183`；
- 用户原有 `127.0.0.1:5176` 未停止、未修改；
- 临时运行数据：`/tmp/yotsuba-wave38-delivery.w5OSoI`；
- Project：`p32-proj-f5eb80443e90fa3ac83c`；
- Run：`p32-run-3897f46487e939747ca1`；
- Gateway 只使用确定性本地 payload，不读取 API Key，不发起外部请求。

验收覆盖：

1. committed Brief、作品库、项目侧栏、交付标题和下载文件均显示《失序档案》；
2. 1728x1100、1440x1000、1280x920、1024x700、390x844 均无页面横向溢出；
3. 桌面交付轨道保持 184px；1024px 四项完整性摘要无截断；
4. 390px 交付文件为顶部横向栏，完整性摘要为 2x2，右侧回执按移动端合同隐藏；
5. 点击“下载 Fountain”得到 `失序档案.fountain`，接口返回 `200`，UI 文件轨道和回执均显示“已下载”；
6. 下载文件为 `116 B`，SHA-256 为 `99451a10fe68fe2b56fa60525913627ae82c056b1f0c34c1b644173aa98b0ebb`，与回执完全一致；
7. Browser Console 最终为 `0 error / 0 warning`，没有 Vite overlay。

截图证据位于：

- `output/playwright/wave32-38-script-delivery/delivery-1728x1100.png`
- `output/playwright/wave32-38-script-delivery/delivery-1440x1000.png`
- `output/playwright/wave32-38-script-delivery/delivery-1280x920.png`
- `output/playwright/wave32-38-script-delivery/delivery-1024x700-fixed.png`
- `output/playwright/wave32-38-script-delivery/delivery-390x844-fixed.png`
- `output/playwright/wave32-38-script-delivery/delivery-downloaded-1440x1000.png`

## 测试与审计

- 后端最终全量：`1065 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端最终全量：`50 files / 125 tests passed`；
- TypeScript/Vite production build：通过；剧本交付独立 CSS `13.52 kB`、JS `17.12 kB`；
- frontend structure audit：通过，共 `171` 个 TypeScript source files；
- CSS audit：通过，无跨文件重复 selector、无重复 keyframe、无新增 infinite animation；
- 首屏 CSS：`31.7 KiB gzip`，通过预算检查；
- Python `compileall`、目标 `oxfmt --check`、`git diff --check` 与 production closure audit：通过；
- production build 仍报告既有主入口和 Character Graph 3D 大 chunk warning，本轮保持交付工作台懒加载，没有扩大首屏 CSS。

## 验收边界

1. 本轮证明确定性交付合同、文件完整性、API 和浏览器下载，不证明真实 Provider 的剧本质量、连续性或成本；
2. 浏览器 fixture 为单 Scene 最小合法交付；多 Scene、三格式、顺序破坏和文件损坏由后端合同测试覆盖；
3. 短中篇与长篇的 Text、Cover、BookDelivery Export 尚未迁移到 Phase 32 专业工作台；
4. committed amendment、Adaptation Package、Phase 32 作者协作和 Story Bible 仍需后续 Wave；
5. README、CHANGELOG、commit 与 GitHub push 继续等待三条路线完整证据包。

下一切片优先迁移短中篇 `ShortProseUnitArtifact` 正文工作台：以冻结 Section Plan 单元顺序为权威，建立逐单元阅读/编辑、source-bound 草稿、顺序提交、连续性 handoff 和明确的下游 Cover/Export 边界；不得复用旧固定八阶段 Text mock。
