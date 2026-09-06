# Phase 32 Wave 42：三路线作者协作迁移闭环

状态：**Phase 32 作者协作已从旧质量档门槛迁为 RouteStage capability，并在剧本样片、短中篇与长篇三个全新隔离 Run 中完成线程、Context Receipt、选区改稿候选、拒绝保护、历史切换和响应式浏览器闭环；本轮使用本地确定性协作 Gateway，没有调用真实 Provider，也没有开放 Patch 直接写回正式 Artifact**

日期：2026-08-25

## 产品决定

作者协作是阶段 Artifact 的受控讨论与提案 sidecar，不是第四条创作路线，也不是新的写回权威：

1. 入口只由服务端冻结的 `stage_manifest[].collaboration_enabled` 决定，不再由旧
   `fast / balanced / deep` 身份决定；
2. 每个线程绑定一个 `run_id / stage_id / source_ref`，切换路线、阶段或 Run 时关闭当前 Dock；
3. 首次发送前必须确认完整 Context Receipt，后续轮次只显示采用范围与预算轻提示；
4. 讨论、方案与改稿共享同一线程合同；改稿必须先建立字段级 SelectionAnchor；
5. 模型只返回 source-bound Patch Candidate。当前生产 UI 只允许保留原文，不能直接应用、
   提交或写入 Canon/Wiki；正式写回继续等待 amendment/branch 版本合同。

## 权威链路

本轮验证的单一路径为：

```text
RouteStage capability
  -> 当前 Run / Stage / Unit Artifact 快照
  -> Context preview 与首次回执
  -> 冻结 thread + turn request
  -> collaboration Gateway
  -> assistant message / Patch Candidate
  -> 显式拒绝状态
```

- 前端 Dock 不维护第二份 Artifact，也不从页面标签猜测 source；
- Context 只聚合当前 Artifact、manifest 声明的已提交上游、作者本轮要求与显式选择的知识库；
- 未选择 Source Pack 时知识库在回执中明确标为排除；
- Patch 拒绝只更新候选状态，原字段草稿和正式 Artifact 均保持不变；
- 线程历史、消息、Patch 与 SSE 仍由后端 Store/API 投影，页面不使用 mock 消息或本地假进度。

## 三路线浏览器证据

隔离环境：

- API：`127.0.0.1:8787`；
- Vite：`127.0.0.1:5176`；
- 临时数据根：`/tmp/yotsuba-wave42-author-collaboration.SV6bbz`；
- 协作 Gateway：测试专用 `_ApiCollaborationGateway`，只返回本地确定性 payload；
- 三条 Run 均为本轮新建，未读取 API Key、未发出外部 Provider 请求。

验收覆盖：

1. 剧本样片 `cast / maya`：打开 Dock 后产品主侧栏隐藏，人物二级导航保持 `184px`；
   首轮回执采用当前人物 Artifact、Brief 上游和作者要求，知识库明确排除；第二轮不再弹完整回执；
2. 同一人物阶段可新建第二线程，历史从 `1` 增至 `2`，切回原线程后两轮消息完整恢复；
3. 人物编辑态选择“找出被删去的真相”后生成 `8 字 · characters.0.desire` Selection chip，
   改稿模式才被启用；候选建议为“在公开听证前找到可独立核验的原始签名链。”；
4. Patch Candidate 只显示“保留原文”，没有应用、提交或写回入口；拒绝后状态变为
   “已保留原文”，原字段仍为“找出被删去的真相”；
5. 短中篇 `story_map / anchor-1`：方案模式首次回执采用当前 Story Map 单元、Brief 上游和本轮要求，
   返回结构化方案，source/unit 与 Run manifest 一致；
6. 长篇 `book_architecture / part-1`：作者协作保留 `184px` Part 导航，source/unit 与当前 Part 一致；
7. 从剧本 Run 切换到短中篇、再切到长篇时 Dock 自动关闭，没有跨 Run 复用线程或选区；
8. `1440x920`、`1024x700`、`390x844` 均无横向溢出。`1024px` 下保留二级导航，
   `390px` 下 Dock 为全宽主界面、阶段二级导航隐藏、按钮无越界或重叠；
9. Browser Console 为 `0 error / 0 warning`；API 日志中的项目、Artifact、thread、context-preview、
   turn、stream 与 patch reject 请求均为 `2xx`，无 `4xx/5xx`。

截图证据位于：

- `output/playwright/wave32-42-author-collaboration/screenplay-cast-dock-1440x920.png`
- `output/playwright/wave32-42-author-collaboration/screenplay-first-context-receipt-1440x920.png`
- `output/playwright/wave32-42-author-collaboration/long-book-architecture-dock-1024x700.png`
- `output/playwright/wave32-42-author-collaboration/long-book-architecture-dock-mobile-390x844.png`

## 测试与审计

- 作者协作后端定向回归：`23 passed, 1 warning`；
- 作者协作、选区捕获与 Shell 前端定向回归：`6 files / 23 tests passed`；
- 后端全量：`1087 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 测试客户端弃用提示；
- 前端全量：`60 files / 142 tests passed`；
- TypeScript/Vite production build、CSS audit、CSS build check、frontend structure audit 与 Python
  `compileall`：通过；
- production closure audit：无 legacy runtime marker、无异常 pipeline 顶层目录；既有大文件继续列入
  责任审查，本轮不为行数机械拆分；
- production build 仍报告既有主入口与 `CharacterGraph3D` 大 chunk 提示；三路线 StageView 保持懒加载，
  本轮没有把 3D 图谱并入作者协作 Dock。

## 验收边界

1. 本轮证明三路线作者协作的本地确定性 API、状态、权限和浏览器投影，不证明 DeepSeek 或其他
   真实模型的延迟、成本、稳定性与建议质量；
2. Patch Candidate 仍不能直接写回正式 Artifact；committed amendment、impact analysis、rebase/fork
   与 Evidence/Outbox 写回必须在独立 Wave 中闭合；
3. Story Bible、监控全状态、自动无障碍、规模/性能、分级真实 Provider 和文学冷读仍未完成；
4. README、CHANGELOG、版本修改、commit、push、Tag 与 Release 继续等待三路线同版本真实全链路门。

本轮关闭的是 Phase 32 作者协作迁移，不是完整 `Wave 32.8`。下一切片应继续验证并补齐三路线
监控的 route-aware 内容、日志、Evidence、checkpoint、usage、writeback 与静默 SSE replay。
