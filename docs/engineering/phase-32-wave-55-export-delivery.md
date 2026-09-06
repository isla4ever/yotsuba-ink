# Phase 32 Wave 55：文本侧导出与交付状态

## 目标与边界

本波收口文本交付 API 的事实表达：成功必须对应真实持久化文件和可校验回执；Short/Long 尚未进入图片
验收时必须显式返回 `image_deferred`，不能返回空 `items` 或伪造成书完成。图片 Provider、CoverAsset
二进制和完整 BookDelivery 仍不在本波验收。

## 实施

`src/novel_workflow/api/routes/runs.py` 的 Run Export adapter 现在统一投影：

- 成功列表增加 `artifact_type`（`script_delivery` / `book_delivery`）、`source_artifact_refs`、
  `dependency_status=ready` 和空 `deferred_reason`；原有 `artifact_ref`、`artifact_digest`、文件
  `sha256`、`size_bytes`、`created_at` 和格式列表保持兼容。
- Source refs 从不可变 Script/Book delivery receipt 的 artifact/version refs 确定性汇总，不从 UI
  本地状态或事件顺序猜测。
- Short/Long 的 `image_deferred` 409 detail 增加 `artifact_type=book_delivery`、
  `dependency_status=deferred`、`deferred_reason=image_acceptance_not_in_current_wave`、已知
  `source_artifact_refs` 和空 items，明确只完成 CoverBrief。
- 已结束但没有真实 delivery receipt 时返回 `409 delivery_not_materialized`，不再以 200 空列表伪装成功。
- 下载路由继续校验 immutable receipt 的 bytes/hash；图片延后时同样返回结构化 409，不创建图片 operation。

## 验证

- `uv run pytest -q tests/test_phase32_script_delivery.py tests/test_phase32_book_delivery.py tests/test_phase32_execution_api.py`：44 passed，1 warning。
- `uv run pytest -q`：1160 passed，1 warning（既有 Starlette/httpx TestClient 弃用提示）。
- `python -m compileall -q src/novel_workflow`、`git diff --check` 通过。

## 真实 Run 冷启动投影

| Run | 读取 | Export 响应 | 关键字段 |
|---|---:|---:|---|
| Screenplay `release-smoke-canonical-screenplay-20260827-r3` | 200，`completed` | 200 | `artifact_type=script_delivery`、`dependency_status=ready`、1 个真实 Fountain item、4 个 source refs |
| Short `release-smoke-canonical-short_novel-20260827-r8` | 200，`image_deferred` | 409 | `artifact_type=book_delivery`、`dependency_status=deferred`、deferred reason 固定、5 个已知 source refs、0 items |
| Long `release-smoke-canonical-long_novel-20260827-r9` | 200，`image_deferred` | 409 | `artifact_type=book_delivery`、`dependency_status=deferred`、deferred reason 固定、6 个已知 source refs、0 items |

三条路线的真实 Run 均保持图片 operation 为 0；Screenplay 的成功文件仍可用 `ETag/X-Content-SHA256`
反查，Short/Long 的成书下载被同一依赖判断阻断。

## 退出与下一步

Wave 55 的文本 Export 事实投影和“无空成功”门已通过本地合同与三条真实 Run 冷读。剩余未关闭项是：

1. 长篇标准多章/accepted-prefix 与三路线人工文学冷读；
2. Wave 56 浏览器路径验证新增字段和 `image_deferred` 操作提示；
3. Wave 57 才重新引入图片 Provider、CoverAsset 和完整 BookDelivery。
