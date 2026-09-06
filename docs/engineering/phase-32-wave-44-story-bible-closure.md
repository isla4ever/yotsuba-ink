# Phase 32 Wave 44：三路线 Story Bible 只读投影闭环

状态：**Story Bible 已改为 Phase 32 Run read model、committed Artifact 与 accepted sequential prefix 的只读投影，并完成三路线语义、分页、来源跳转和 `1440x920 / 1024x700 / 390x844` 浏览器闭环；本轮只使用本地 `_FixtureGateway`，未调用真实 Provider**

日期：2026-08-25

## 产品决定

Story Bible 是作者查看正式创作依据与连续性线索的只读工作区，不是第二套 Canon、Wiki、Memory 或 Artifact Store：

1. 只投影 Run read model 已引用的 committed Artifact；candidate、draft 和 UI 本地状态不能进入；
2. 正文与剧本只读取 sequential stage 的 accepted prefix，遇到首个未提交单元立即停止；
3. “连续性”只展示 committed 规划中的 Promise、开放问题、闭合条件与 handoff，不从正文推断事实或兑现状态；
4. 每条记录携带直接来源、Artifact ref、payload digest、source path 与 committed 时间，并可返回正式来源阶段；
5. 正式事实、amendment 与 Canon/Wiki writeback 继续等待独立合同，页面明确显示 `pending_contract`，不伪造已写回数量。

## 权威链路

```text
GET /api/runs/{run_id}/story-bible?section=...&limit=...&cursor=...
  -> Phase32RunRepository.read(run_id)
  -> Run read model artifact_refs / sequential_stage_progress
  -> Phase32ArtifactStore committed records
  -> route-aware deterministic projection
  -> content-addressed projection revision + opaque cursor
  -> Version 20 read-only Story Bible page
```

- 剧本路线投影 Brief、Cast、Beat Board、Scene Deck 与 accepted Script scene；
- 短中篇投影 Brief、Cast、Story Map、Section Plan 与 accepted prose unit；
- 长篇投影 Brief、Cast、Book/Part Architecture、Volumes、Rolling Detail 与 accepted chapter；
- cursor 绑定 section 与 projection revision，过期或跨分类 cursor 明确拒绝，不把变化中的结果拼接到旧分页；
- API route 只做参数校验、依赖获取与错误映射，聚合和权威判断留在 storage projection 边界；
- 前端 IO、状态和展示分别位于 `services/`、`state/` 与 `running/story-bible/`，没有新增顶层 taxonomy。

## UI 与交互

- 五个分类为“核心设定 / 人物与关系 / 节拍与场景或路线结构 / 已接受内容 / 连续性”，标题按路线动态变化；
- Header 摘要只显示正式来源、人物、结构单元与已接受内容数量；
- “查看来源”回到 source-bound 阶段，不复制可编辑表单；
- 首次加载使用单一过渡遮罩，authority revision 刷新保留已显示内容；
- 分页追加按 `entry_ref` 去重，加载完成后按钮消失；
- 移动端分类栏横向滚动，冷刷新后当前激活分类自动进入可见区；
- 未提交 Brief 或结构时展示真实空状态，不使用 mock 内容填充视口。

## 浏览器验收

隔离环境：

- API：`http://127.0.0.1:8787`；
- Vite：`http://127.0.0.1:5176`；
- Provider：测试专用 `_FixtureGateway`，没有读取真实 Provider Key 或发出外部请求。

Run 证据：

1. 剧本样片 `wave44-story-bible-screenplay-empty-run` 停在 Brief 待决策；Story Bible 为零来源真实空状态，未提交候选没有泄露；
2. 短中篇 `wave44-story-bible-short-completed-run` 完整运行到 `completed / export`，Story Map、Section Plan 与 accepted 正文来自正式 Artifact；
3. 长篇 `wave44-story-bible-long-completed-run` 完整运行到 `completed / export`，五个分类均可读取；
4. 长篇人物夹具包含 56 个人物与 4 条关系，首页返回 `50 / 60`，点击“继续读取”后共显示 60 条且无重复，分页按钮正确消失；
5. 长篇 `Part 01` 的“查看来源”进入 `/run/book_architecture`，来源路由与 Artifact stage 一致；
6. 小说封面通过 source-bound draft 正式选择首个候选，没有绕过 Cover 决策完成 Export。

响应式与交互：

- `1440x920`：长篇五分类、来源跳转和真实分页通过；
- `1024x700`：短中篇 Story Map 与章节/段落计划通过；
- `390x844`：剧本空状态、长篇核心设定与连续性通过；
- 三个视口 `document/body scrollWidth == viewport width`；
- 浏览器最初复现 Hook dependency 长度变化错误，修复后以独立冷刷新会话复核：`Errors: 0 / Warnings: 0`；
- 390px 冷刷新“连续性”分类完整进入可见区，激活项未被横向裁切。

截图证据：

- `output/playwright/wave44-story-bible/long-overview-1440x920.png`
- `output/playwright/wave44-story-bible/long-cast-paginated-1440x920.png`
- `output/playwright/wave44-story-bible/long-continuity-1440x920.png`
- `output/playwright/wave44-story-bible/short-structure-1024x700.png`
- `output/playwright/wave44-story-bible/screenplay-empty-390x844.png`
- `output/playwright/wave44-story-bible/long-overview-390x844.png`
- `output/playwright/wave44-story-bible/long-continuity-390x844.png`

## 测试与审计

- 后端全量：`1093 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx TestClient 弃用提示；
- 前端全量：`65 files / 154 tests passed`；
- Python `compileall`、TypeScript/Vite production build、frontend structure audit、CSS audit 与 CSS build check：通过；
- structure audit：`193` 个生产 TypeScript 文件，无异常 pipeline 顶层目录；
- CSS audit：`435351 bytes / 3168 rules / 3575 selectors`，跨文件重复 selector `0`，无限动画 `8`；
- 首屏 CSS `29.4 KiB gzip`；Story Bible CSS `17.89 kB / 3.23 kB gzip`；Story Bible JS `19.07 kB / 6.65 kB gzip`；
- production build 仍有既存主入口与 `CharacterGraph3D` 大 chunk 提示，本轮没有扩大；
- production closure audit：无 legacy runtime marker、无异常 pipeline 顶层目录；
- 定向与最终 `git diff --check`：通过。

## 验收边界

1. 本轮证明 Story Bible 的本地确定性来源、三路线投影、分页与响应式交互，不证明真实 Provider 延迟、成本、稳定性或文学质量；
2. accepted 正文只作为不可变已接受单元展示，不据此自动建立正文事实、伏笔兑现或 Canon/Wiki writeback；
3. 正式 amendment/writeback、自动无障碍、规模/性能、三路线同版本真实 Provider 与文学冷读仍未完成；
4. README、CHANGELOG、版本修改、commit、push、Tag 与 Release 继续等待 Phase 32 发布门，不在本轮执行。

本轮关闭的是三路线 Story Bible 的只读投影与浏览器门，不是完整 `Wave 32.9` 发布门。
