# Phase 32 Wave 43：三路线运行监控闭环

状态：**Phase 32 监控台已改为同一 Run read model 与 Artifact Store 的只读投影，并在剧本完成、短篇失败、长篇逐章待审三种状态及 `1440x920 / 1024x700 / 390x844` 视口完成浏览器闭环；本轮只使用本地 `_FixtureGateway`，未调用真实 Provider**

日期：2026-08-25

## 产品决定

运行监控不是第二个创作工作台，也不建立第二套进度或内容状态：

1. 左侧路线、阶段、单元与状态只读取正式 Run read model；
2. 中间内容只读取 `/api/runs/{run_id}/stages/{stage_id}/artifacts/current`，不显示 mock 正文或 raw JSON；
3. 右侧检查器只读投影 failure、pending decision、Provider usage、checkpoint、Evidence、writeback 与最近 200 条正式事件；
4. SSE 刷新保留用户选中的阶段、单元与旧内容，直到新 Artifact 返回，不闪空、不重置导航；
5. 接受、换稿、编辑与写回仍回到阶段工作台，监控页不成为新的 Artifact 写入口。

## 权威链路

```text
Project.latest_run_id
  -> GET /api/runs/{run_id}
  -> Run read model + route stage manifest + sequential progress
  -> GET /api/runs/{run_id}/events
  -> GET /api/runs/{run_id}/stages/{stage_id}/artifacts/current?unit_ref=...
  -> route-aware read-only preview / status inspector / formal event log
```

- `phase32RunMonitor.ts` 只承担 Run/Artifact 到展示模型的纯投影；
- `usePhase32MonitorArtifact.ts` 是唯一 Artifact IO 状态边界，刷新时保留上次已解析内容；
- `Phase32RunArtifactPreview.tsx` 按 Brief、规划、人物、剧本、小说正文、封面和交付物展示真实字段；
- `Phase32RunMonitorInspector.tsx` 不推断质量，只呈现正式 failure、usage、checkpoint 和事件分类；
- 页面在 `App.tsx` 中按需加载，专用 CSS 不进入 Phase 32 首屏主样式。

## 浏览器验收

隔离环境：

- API：`http://127.0.0.1:8787`；
- Vite：`http://127.0.0.1:5176`；
- 临时数据根：`/tmp/yotsuba-wave43-monitor.l4RKnq`；
- Provider：测试专用 `_FixtureGateway`，没有读取 API Key 或发出外部请求。

Run 证据：

1. 剧本样片 `p32-run-471e7934d15a9410beed`：`completed / export`，可在交付物与
   `script / scene-1` 之间切换，正式场景块、Scene version 与交付 Manifest 均来自 Artifact API；
2. 短中篇 `p32-run-4db3807b3ffb17e24f9a`：测试 Gateway 在 Cover 返回错误合同，Run 正确冻结为
   `provider_contract_failed / cover`；检查器显示错误码、最低责任阶段、合同拒绝和 `5/6` 用量，仍可回看
   已提交的 `text / unit-1`；
3. 长篇 `p32-run-wave43-long-monitor`：停在 `text / chapter-2` 等待审阅，`chapter-1` 为 committed、
   `chapter-2` 为 candidate；左栏切换后中间内容、状态标识与 Artifact ref 同步变化，Rolling Detail 显示
   同一 Window 下两章的施工图；
4. 最初的 100,000 字长篇临时 Run 因测试 Gateway 固定返回 150,000 字 Brief 而被合同拒绝。未在失败 Run
   上重试，改用匹配冻结 ScaleProfile 的全新 150,000 字临时 Run；这是浏览器 harness 输入不匹配，不是
   生产 Provider 或监控投影故障。

响应式与交互：

- `1440x920`：`184px` 阶段/单元栏、内容区和固定检查器三栏完整，无横向溢出；
- `1024x700`：检查器改为 Header 触发的右侧抽屉，关闭后完全退出视口；
- `390x844`：阶段栏变为横向带，当前阶段自动进入可见区；检查器为右侧抽屉并避开底部导航；
- 浏览器复现并修复了抽屉焦点缺陷：关闭按钮或宽屏日志 Tab 保持焦点时进入窄断点，会让浏览器为
  离屏焦点横向平移。现在关闭与断点切换都用 `preventScroll` 把焦点归还到 Header 触发按钮；
- 窄屏关闭态在退场动画结束后切换为 `visibility: hidden`，隐藏检查器不再进入键盘焦点顺序；
- 三个视口 `document/body scrollWidth == viewport width`，浏览器控制台均为 `0 error / 0 warning`。

截图证据：

- `output/playwright/wave43-monitor-long-1440x920.png`
- `output/playwright/wave43-monitor-long-1024x700.png`
- `output/playwright/wave43-monitor-long-390x844.png`
- `output/playwright/wave43-monitor-short-failed-1440x920.png`
- `output/playwright/wave43-monitor-screenplay-completed-1440x920.png`

## 测试与审计

- 监控投影、事件分类、单元状态、静默刷新与检查器焦点测试：通过；
- 后端全量：`1087 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx TestClient 弃用提示；
- 前端全量：`62 files / 148 tests passed`；
- Python `compileall`、TypeScript/Vite production build、frontend structure audit、CSS audit 与 CSS build
  check：通过；
- CSS audit：跨文件重复 selector `0`；首屏 CSS `31.6 KiB gzip`；监控专用 CSS `3.55 KiB gzip`；
- 监控懒加载 chunk：JS `10.54 KiB gzip`；production build 仍保留既有主入口与 `CharacterGraph3D`
  大 chunk 提示，本轮没有扩大该问题；
- production closure audit：无 legacy runtime marker、无异常 pipeline 顶层目录。`phase32RunMonitor.ts`
  为 573 行，已做职责审查：它只含同一 Run 监控域的纯投影与无副作用辅助函数，不混合 IO、React
  状态或组件；当前不为行数机械拆分。

## 验收边界

1. 本轮证明本地确定性 Run/Artifact/event/usage/failure 的 UI 投影，不证明真实 Provider 延迟、成本、
   稳定性或文学质量；
2. 测试 Run 中 Evidence、writeback 与 checkpoint 类事件可能为零；分类与非零投影由合同测试覆盖，
   真实 Provider/Evidence/Outbox 证据仍需进入发布验收包；
3. Story Bible、正式 amendment/writeback、自动无障碍、规模/性能、三路线同版本真实 Provider 与文学
   冷读仍未完成；
4. README、CHANGELOG、版本修改、commit、push、Tag 与 Release 继续等待 Phase 32 发布门，不在本轮执行。

本轮关闭的是三路线 route-aware 监控的本地确定性与浏览器门，不是完整 `Wave 32.9` 发布门。
