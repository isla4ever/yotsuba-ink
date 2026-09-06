# Phase 32 Wave 53：三路线文本闭环与质量收口

## 范围

本记录是 Wave 53 的三路线现场证据补充。验收只覆盖文本 Provider、结构化 Artifact、
阶段决策、写回、进程恢复、SSE/read-model 和文本侧交付；图片生成仍明确排除，Short/Long
在 CoverBrief 后停留 `image_deferred`，不创建图片 operation。

## 实施切片

1. 写回恢复在发现同源 `pending` operation 时读取 immutable Provider input snapshot，复用原
   operation key、prompt 和 schema，不因 recovery counter 变化留下孤立 pending receipt。
2. Story Map anchor 和 Section Plan unit 的 Promise 引用进入新候选硬合同；历史 Artifact 仍可
   读取，但新候选不能用空数组绕过承诺追踪。
3. Cast/Short prose/Long chapter prompt 冻结已登记 display name；新增窄范围命名门禁，只检查
   `姓名：X`、`名字是X`、`叫作X`、`输入“X”` 等高置信身份标记，不做泛化中文 NER。未登记显式
   姓名在候选接受前以 `provider_contract_failed` 阻断，并保留名称诊断。
4. LangGraph 恢复按持久 interrupt id 定向投递，避免 sequential text 完成后误恢复到另一个
   mandatory decision。

## 真实 DeepSeek 证据

| 路线 / Run | 终态与交付 | Provider / 恢复 | 冷读结论 |
|---|---|---|---|
| Screenplay `release-smoke-canonical-screenplay-20260827-r3` | `completed`；Brief/Cast/Beat Board/Scene Deck/Script/Export 完成；Fountain 可读 | 11/11 receipts `succeeded`、0 pending；首次 writeback binding error 后通过持久 read-model 决策恢复；47 条 SSE，seq 连续，末事件 `export.ready`；Export 200 | 3 场 speaker 均来自 Cast（`林深`、`未来林深`）；重复 storm/rain 意象和结尾回声保留为文学 warning，不阻断传输闭环 |
| Short `release-smoke-canonical-short_novel-20260827-r7` | `image_deferred`；文本阶段完成；Export 明确锁定 | 12 receipts：11 最终成功、1 首轮 writeback contract reject 后纠正；0 pending；46 条 SSE；图片 operation 0；Export 409 `image_deferred` | Promise 完整覆盖；Cast `林默`、`陈屿`；正文未观察到未登记姓名；成本约 `$0.07936368`，tokens 43,882 |
| Short `release-smoke-canonical-short_novel-20260827-r8` | `image_deferred`；3 个文本单元完成；Export 明确锁定 | 11/11 receipts `succeeded`；首轮 `span_ids` reject 0；空 claims 纠正 0；0 pending；46 条 SSE seq 连续；图片 operation 0；Export 409；成本约 `$0.07033356`，tokens 39,031 | Cast 仅 `林默`；正文未观察到 `林晚`、`林晓` 或元话语标记；Promise/命名边界通过 |
| Long `release-smoke-canonical-long_novel-20260827-r7` | `image_deferred`；Book Architecture/Cast/Volumes/Rolling Detail/Text/Cover 完成；Export 锁定 | Volumes 首次真实网络失败，重启后同 Run 恢复；12 receipts 全部成功、0 pending；52 条 SSE seq 连续，包含可解释 `stage.failed`/`writeback.failed` 后续恢复；图片 operation 0；成本约 `$0.08790408`，tokens 50,704 | 结构 handoff 可读，但两章正文引入 Cast 未登记的 `林晚`；当前 smoke 仅 2 章（约 2,128 / 2,611 字符，非 100k 长篇质量证明）。该 Run 发生在命名硬门禁之前，不能计为长篇文学质量通过 |
| Long `release-smoke-canonical-long_novel-20260827-r8` | `image_deferred`；同一 2 章 bounded smoke 完成；Export 锁定 | 11 receipts：10 succeeded、1 首轮 writeback contract reject（`span_ids` 超过 3）后纠正；0 pending；45 条 SSE seq 连续；冷启动 API 200；Export API 409 `image_deferred`；图片 operation 0；成本约 `$0.08797932`，tokens 48,675 | 新命名硬门禁通过；Cast 为 `林墨`、`档案馆长`、`失踪者`，两章正文未出现 `林晚` 或元话语。仍只是 2 章技术样本，不能替代标准多章/100k 文学验收 |
| Long `release-smoke-canonical-long_novel-20260827-r9` | `image_deferred`；同一 2 章 bounded smoke 完成；Export 锁定 | 10/10 receipts `succeeded`；首轮 `span_ids` reject 0；空 claims 纠正 0；0 pending；45 条 SSE seq 连续；冷启动 API 200；Export API 409 `image_deferred`；图片 operation 0；成本约 `$0.06923928`，tokens 37,674 | Cast `林墨`、`林晓`、`匿名委托人`；两章正文未出现 `林晚` 或元话语。新写回硬门通过；仍只是 2 章技术样本，不能替代标准多章/100k 文学验收 |

## 当前判定

- **传输闭环**：三条路线均有真实 DeepSeek 文本调用；Screenplay 到文本侧 Export，Short/Long
  到 `image_deferred`；重启、SSE 顺序、写回和 pending 统计均有证据。
- **业务闭环**：图片边界没有被伪造为完成；Short/Long 的 Export 409 与图片 operation 为 0
  与状态语义一致。
- **质量闭环**：Short 的 Promise/命名样本通过；Screenplay 仍有非阻断文学 warning；Long r8/r9
  已通过显式命名门禁，Short r8/Long r9 也通过写回首轮 `span_ids` 门，但 bounded smoke 与正式长篇
  规模之间存在差距，因此 Wave 53/54 仍**不整体标记为文学质量通过**。

## Wave 54 写回首轮证据

DeepSeek 文本模板实际使用 `json_object`，嵌套 `span_ids.maxLength=3` 由本地 Pydantic 最终校验。Wave 54
在冻结上下文末尾重复 cardinality gate，并把纠正提示改为局部修复。新鲜 Short r8（11 operations）和
Long r9（10 operations）均为首轮 contract reject 0、空 claims 纠正 0、pending 0；r7/r8 Long 历史拒绝
仍保留为回归基线，不以新样本覆盖历史证据。

## Wave 55 文本 Export 证据

成功 Export 列表现在显式返回 `artifact_type`、`source_artifact_refs`、`dependency_status=ready` 和
`deferred_reason`；无真实 delivery receipt 时返回 `409 delivery_not_materialized`，不返回空成功。
Short r8/Long r9 冷启动读取均返回 `409 image_deferred`，带 `dependency_status=deferred`、固定 deferred
原因和已知 source refs；Screenplay r3 返回 200，带 1 个真实 Fountain item、4 个 source refs，下载仍
通过 immutable receipt 的 `ETag/X-Content-SHA256` 校验。详情见 [Wave 55 文本交付记录](phase-32-wave-55-export-delivery.md)。

对已落盘的 Long r7 committed chapters 进行新门禁回放时，chapter 01/02 均稳定返回
`Prose introduces an unregistered explicit character name: 林晚`。这证明门禁能在冷读/复核阶段
复现问题，但不修改历史 Run；下一次新 Run 才能验证模型是否会改用已注册职能标签。

## 离线验证

- 后端全量：`uv run pytest -q` → `1160 passed, 1 warning`；唯一 warning 是既有
  Starlette/httpx TestClient 弃用提示。
- `compileall -q src/novel_workflow` 通过；`git diff --check` 和新增文档/源码 trailing-whitespace
  检查通过。
- 前端本轮未改动，沿用 Wave 53 已验证的 68 个 Vitest 文件 / 172 tests、TypeScript、Vite build
  和结构审计结果。

## 下一轮退出条件

1. 保留 Long r8 的命名通过证据，并继续监测更长文本/跨窗口是否出现未注册别名；若再次出现，
   候选阶段必须稳定失败并给出具体名称诊断，当前终态合同失败应通过新 Run/显式修订分支恢复，
   不得把失败降级为成功。
2. 为三路线各保留一次人工冷读记录，把结构合同、承诺覆盖、人物命名、meta 话语、handoff
   和文学 warning 分开计分。
3. 继续观察 writeback 首轮 contract reject 率；恢复成功不能抹掉首轮错误，目标是连续样本中
   降低并解释每一次 reject。
4. Long 的 2 章 release-smoke 仅作为技术恢复样本；进入正式长篇验收前，增加标准多章/跨窗口
   accepted-prefix 样本。图片 Provider、CoverAsset 和完整 BookDelivery 留到后续波次。
