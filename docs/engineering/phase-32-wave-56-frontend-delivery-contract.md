# Phase 32 Wave 56：前端交付依赖契约与图片暂缓可解释性

Wave 56 将 Wave 55 的交付信封元数据接入前端，并为 Short/Long 的 `image_deferred` 建立明确的不可导出状态。图片生成与图片验收仍不在本波验收范围内。

## 交付内容

- `script_delivery` / `book_delivery` 成功信封强制校验 `artifact_type=...`、`dependency_status=ready`、空 `deferred_reason` 与 `source_artifact_refs`。
- HTTP 结构化错误保留 `code`、`dependency_status`、`deferred_reason` 与 source refs，状态 Hook 向页面暴露这些字段。
- 成书交付页在依赖暂缓时显示“正文已完成，成书交付暂缓”和 `DEPENDENCY DEFERRED · IMAGE ACCEPTANCE`，按钮返回正式封面，不提供误导性的空文件下载入口。

## 验证

- 受影响前端测试：8 个文件 / 17 tests passed（包含 script/book 409 结构化错误、envelope provenance、Hook deferred 状态保留与空态视图）。
- 全量前端测试：72 files / 184 tests passed。
- 后端全量 `uv run pytest -q`：1160 passed、1 个既有 Starlette/httpx deprecation warning；`compileall` 通过。
- `npm run build`：TypeScript 与 Vite 构建通过；保留既有大 chunk warning（入口约 935 kB、CharacterGraph3D 约 1.4 MB），列入后续性能波次。
- `npm run audit:structure` 与 `npm run audit:css`：通过；deferred 空态样式已同步 CSS 基线（450647 bytes / 15520 source lines）。`git diff --check` 通过。

### 真实浏览器 smoke（2026-08-27）

使用隔离 API/Vite（Vite `5176`、API `8788`）加载三条 canonical Run，并采集 DOM、截图、network 与 console：

| 路线 / Run | 关键结果 | 网络与控制台 | 截图 |
|---|---|---|---|
| Screenplay `release-smoke-canonical-project-screenplay-20260827-r3` | `剧本交付已冻结`；3 scenes、1 file；Fountain 可下载；integrity 全部通过 | project/run/events/export 均 200；无意外 JS error/warning | `output/playwright/wave56/screenplay-export-1440x920.png` |
| Short `release-smoke-canonical-short_novel-20260827-r8` | `正文已完成，成书交付暂缓`；显示 `DEPENDENCY DEFERRED · IMAGE ACCEPTANCE`；仅返回封面阶段 | `/exports` 返回预期 409 `image_deferred`；无意外 JS error/warning | `output/playwright/wave56/short-image-deferred-1440x920.png` |
| Long `release-smoke-canonical-long_novel-20260827-r9` | 同上；正文完成上下文、原因和下一步均可见 | `/exports` 返回预期 409 `image_deferred`；无意外 JS error/warning | `output/playwright/wave56/long-image-deferred-1440x920.png` |

Long 路线在 390×844 移动视口下同样可读，`document.scrollWidth` 与 viewport 一致，无横向溢出（`output/playwright/wave56/long-image-deferred-390x844.png`）。浏览器控制台中出现的 409 是 Wave 55 定义的业务阻断响应，不是未捕获异常；本轮门禁按“无意外错误/警告 + 业务 409 被正确呈现”判定。

### 本轮回归修复

首次 smoke 暴露一个真实竞态：Hook 用 `Promise.all` 同时请求 current export artifact 与 delivery envelope 时，`image_deferred` Run 的 artifact 404 可能先 reject，覆盖随后到达的结构化 409，页面因此错误显示“成书交付尚未就绪”。现已改为先读取 delivery envelope，再读取 current artifact；Short/Long 在图片暂缓时稳定保留 `code`、`dependency_status`、`deferred_reason` 与 source refs，并有 Hook 回归测试覆盖。该修复不改变后端 409 契约，也不触发图片调用。

图片生成、图片质量与 CoverAsset 下载仍明确不在本波验收范围；Wave 57 只在文本链路持续稳定后启动。
