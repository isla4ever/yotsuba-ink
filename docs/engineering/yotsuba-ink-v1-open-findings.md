# Yotsuba Ink v1.0 历史问题与后续迭代

本文只记录 `balanced-110k-v1-demo-20260817-040033` 的证据，不把历史问题伪装成新的验收，也不在 v1.0 收口阶段逐条改写正文。

## 已恢复的工程问题

1. 终态 Run 原先从 `after=0` 重放约 2,210 条历史事件，导致作品打开时依次经过历史章节路由。现在终态改为 Run/read-model/Artifact/chapter 快照，`reconnect: false`；运行中或待决策 Run 仍保留 SSE 重连。
2. 事件历史中的 `text.finish_chapters` 失败事件曾覆盖后续人工恢复后的 Text 完成状态。终态投影以 `read_model.stage_status` 为当前事实，并合成确定性的阶段完成事件；历史失败仍作为诊断证据保留。
3. Cover 生图关闭时，缺少 `selected_asset_id` 曾被误投影为“待完善”。现在以冻结的 `include_cover_image=false` 显示“封面生图已跳过 / 仅保留元数据”，Cover 仍可交付。
4. 作品库原先允许书脊换行。现在固定单行横向轨道，支持按钮、触控板和触摸横向滚动。
5. 同一 Project 重新打开时，不能只用 Run ID 判断本地状态已经同步。现在以 `project.latest_run_id` 校验 canonical latest Run；同一 Run 的终态也会重新做服务端快照。

## 运行中记录

- Provider 失败 3 次，均完成同一链路内恢复，没有新增长期兼容路径。
- 29 条 `quality.warning`：17 条 scene length soft band、11 条 chapter length soft band、1 条 detail title reused。它们不阻断 10 万字产品硬门。
- Reviewer 有 16 个带 finding 的 receipt，共 25 条 finding（23 条标为 blocking、2 条 warning）。这些 finding 来自模型审稿证据，部分指向场景重放、知识状态、提前出场或时间衔接；本次没有对每条 finding 自动换稿，也没有把“表面死亡/身份隐藏/延迟揭示”直接当作冲突。后续应由人工冷读或更强的证据绑定复核后，才决定是否进入定向修订。
- AI 味、节奏、句式重复和章节钩子属于软质量记录，不因单次模型审稿低置信判断阻断已完成 Demo。

## 后续建议

- 先用人工冷读确定真正影响读者理解的连续性问题，再设计最小的章节级定向修订入口；不要恢复全书无限换稿。
- 为 reviewer finding 增加“证据是否直接命名主体、是否同一时空、是否同一物理状态”的人工确认层。
- 将终态静态快照的事件构造抽成可复用只读投影，并继续保持它与运行 SSE 的 authority 边界分离。
- 为完整 Run 增加可选的脱敏验收摘要，避免浏览器验收依赖手工从 2,210 条事件中筛选数据。
