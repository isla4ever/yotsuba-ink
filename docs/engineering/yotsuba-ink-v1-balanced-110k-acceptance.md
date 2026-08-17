# Yotsuba Ink v1.0 平衡模式长篇验收

日期：2026-08-17
验收 Run：`balanced-110k-v1-demo-20260817-040033`
Project：`proj-e1007717ad`
书名：`明日来电`
工作流：`official-deepseek-balanced`（项目运行时冻结工作流：`wf-proj-e1007717ad`）

## 结论

本 Run 完成 `brief -> spine -> cast -> volumes -> detail -> text -> cover -> export` 全链路。正文达到产品硬门 10 万字，44 章均有已接受版本，章节标题、分卷标题和导出 ZIP 均可用。封面生图按本次配置跳过，但 Cover Artifact、封面 Brief 和导出元数据完整，页面明确显示“仅保留元数据”。

终态作品从作品库打开时采用服务端 read model 静态投影，直接进入 `/run/export`；不会从事件 0 重放历史 SSE，也不会在历史章节之间抢占路由。

这是一份工程与可交付性验收，不替代完整人工冷读。Reviewer 记录的文学、节奏、AI 味和连续性提示保存在技术债文档中，未因低置信或未独立复核的 finding 无限换稿。

## 硬门

| 门 | 结果 | 证据 |
| --- | --- | --- |
| 流程可完成、可恢复 | PASS | 8/8 read-model stages completed；3 次 Provider 失败均有恢复回执 |
| 结构化输出可解析 | PASS | Brief、Spine、Cast、Volumes、Detail、Text、Cover、Export Artifact 均已 committed |
| 关键 Artifact 与正文非空 | PASS | 7 个阶段 Artifact ref；44 个 accepted chapter versions；正文 107,613 字符 |
| 章节/分卷标题 | PASS | 44/44 章节标题、3/3 分卷标题存在 |
| 上游硬约束 | PASS（终态） | 最终 read model 无 failure；历史失败仅为中间候选/旧精确目标，未覆盖终态 Artifact |
| 10 万字目标 | PASS | 107,613 个非空白字符 |
| 导出可用 | PASS | ZIP 导出回执、SHA-256、文件大小均可在 Export 工作台读取并下载 |

## 规模与章节分布

- 总正文：`107,613` 个非空白字符。
- 章节数：`44`；标题完整率：`44/44 = 100%`。
- 单章非空白字符：最小 `1,710`，最大 `3,692`，平均 `2,445.75`，P90 `2,962`。
- 章节范围没有出现 1,000 与 6,000 字的极端离散；自然差异保留。
- 分卷：`来电初现` 14 章 / 35,795 字符，`破碎回声` 14 章 / 34,126 字符，`永夜回声` 16 章 / 37,692 字符；卷标题完整率 `3/3 = 100%`。
- Detail Artifact 章节数为 44，Export Artifact 选择的章节版本数为 44。

## 连续性抽检

抽检了开篇三章、中段 `chapter-22 -> chapter-23` 和终稿 `chapter-44` 的标题、开头、结尾与章节状态。抽检结果未发现同一抽检对中明确的物理位置或人物状态不可能转移；第 22 章结尾等待来电，第 23 章开头来电发生，属于直接承接。此项是定向抽检，不等同于人工逐章冷读。

“死亡后复活、隐藏身份、延迟揭示”等叙事转折不按表面文本直接判定为冲突；只有同一主体在同一时空、同一事实状态上出现明确且有证据的不可解释矛盾，才进入硬门。

## Provider 与恢复

- Provider operations：`314`。
- 成功：`311`；失败：`3`；最终 pending：`0`。
- 总 tokens：`1,760,252`（prompt `1,627,787`，completion `132,465`）。
- 失败回执：Volumes 候选的 climax 位置合同、Text 终检的冻结 `110,000` 精确目标、Cover 候选的 `negative_constraints` 数量合同。
- 以上失败均没有破坏最终产品硬门：Volumes/Cover 形成有效 committed Artifact；Text 的最终正文高于产品 100,000 字硬门，随后恢复并完成 Cover/Export。

## 导出回执

- 文件名：`明日来电.zip`；格式：`application/zip`；大小：`329,105` bytes。
- SHA-256：`62132a9dd82cf18691189af27a727628cc1c8c6327f29c1da52224f42a33df55`。
- 本地交付文件：`runtime/novel_workflow/native_runtime/exports/balanced-110k-v1-demo-20260817-040033/files/export-bddc2be828bc5fa7be566ddd.bin`；文件签名与回执一致，`unzip -t` 无错误。

## UI 与浏览器证据

- 作品库书架：单行 `nowrap` 横向轨道，`overflow-x: auto`，左右 44px 控件，支持触控板/触摸横向滚动。
- 已完成作品打开：最终 URL `/run/export`；请求只读取当前 Run、7 个阶段 Artifact、accepted chapters 和 Export 回执，没有 `/events` 请求。
- 桌面截图：`output/playwright/v1-closure/browser/bookshelf-desktop-1440x1000.png`、`completed-export-desktop-1440x1000.png`。
- 移动截图：`output/playwright/v1-closure/browser/bookshelf-mobile-390x844.png`。
- 浏览器断言：`8/8` 阶段、`314 次调用`、`1,760,252 tokens`、`44 章`；控制台 0 error / 0 warning；移动端文档宽度 `390px`，无页面级横向溢出。

## 验证命令

```bash
cd apps/web
pnpm exec tsc --noEmit
pnpm exec vitest run src/features/pipeline/services/runApi.test.ts \
  src/features/pipeline/state/runState.test.ts \
  src/features/pipeline/state/stageDeliveryStatus.test.ts \
  src/features/pipeline/state/useProjectSession.test.ts \
  src/features/pipeline/state/useRunRecovery.test.tsx \
  src/features/pipeline/layout/studio/ProjectBookshelf.test.tsx \
  src/features/pipeline/running/artifactSemanticReadiness.test.ts \
  src/features/pipeline/running/CoverStageViewVnext.test.tsx
```

本次聚焦测试结果：8 个文件、41 个测试全部通过。完整仓库测试、生产构建和 CSS 门禁需在提交前再次运行并以终端输出为准。

提交前复核结果：前端完整 Vitest `112` 个文件、`421` 个测试通过；TypeScript、生产构建、CSS 审计和 CSS 分包检查通过；后端 `.venv/bin/pytest -q` 为 `527 passed`，仅有既有 Starlette/httpx 弃用警告；`.venv/bin/python -m compileall -q src tests` 与 `git diff --check` 通过。
