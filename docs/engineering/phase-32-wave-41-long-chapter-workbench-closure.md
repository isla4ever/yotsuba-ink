# Phase 32 Wave 41：长篇逐章正文与成书交付闭环

状态：**长篇 `ChapterArtifact` 已完成冻结章节顺序、窄上下文、逐章提交、accepted prefix 保护、source-bound 当前章草稿、Version 20 专业工作台，并复用 Wave 40 的真实封面资产与确定性 `BookDeliveryArtifact` 完成两章 Fake Provider 浏览器闭环；本轮没有调用真实 Provider，也没有改写失败或历史 Run**

日期：2026-08-25

## 产品决定

长篇正文不是一次生成整本书，也不是把完整历史正文持续塞回模型。正文执行边界由已提交 Rolling Detail 冻结，并按章节串行推进：

1. 当前章只读取所属 Book/Part/Volume、Detail chapter、相关 Cast、上一章 handoff 与最多 `1,200` 字正文尾部；
2. Chapter N+1 只能在 Chapter N 已接受后开始，accepted prefix 不可覆盖、重排或静默重写；
3. 作者只能编辑当前候选章的文学正文，`chapter_ref / volume_ref / title / pov_subject_ref` 继续由冻结规划拥有；
4. 全部章节提交后进入 Cover，正式封面定稿后由 Export 聚合 ordered committed chapter versions；
5. Export 不调用 Provider，不回读候选稿，也不在下载时重生正文、封面或文件。

## 后端合同

- `text` 的 `sequential_units` 从 committed `DetailPlanIndexArtifact` 冻结章节顺序、章节身份与所属卷；
- 长篇 Provider input 只携带当前层级合同、当前 Detail chapter、相关人物、上一章 handoff/版本摘要和有界尾部，不随已接受章节总长度线性增长；
- 当前章 candidate 可物化为 source-bound draft candidate；服务端允许正文修改，同时拒绝章节、卷、标题和 POV 身份漂移；
- 当前章提交后写入不可变 `ChapterArtifact` version，历史 accepted 章节保持只读，下一章 cursor 单调推进；
- `BookDeliveryArtifact` 冻结 `chapter_refs`、`chapter_version_refs`、`volume_refs`、正式封面与格式；浏览器编辑后的第二章版本进入唯一 Export Manifest；
- Provider usage 从 operation receipt store 重建。混合“文本成本未知 + Fake 图片成本已知为 `0.0`”时，全局成本必须保持 `None / unknown`，不能把部分已知的零成本误投影成整次 Run 的已知总价；
- Provider 子项仍分别保留图片 `0.0 / known` 与文本 `unknown`，Run read model 与 receipt store 的 operation 数必须一致。

## 前端结果

- 新增长篇专用 `LongChapterStageView`、`LongChapterWorkbench`、纯投影 helper 与 Context hook，没有回落旧 `TextStageView`；
- 桌面使用统一 `184px` Part/Volume/Chapter 树、正文阅读区与计划/交接/来源 Inspector；移动端转为横向章节导航；
- 默认是阅读态，只有当前候选章可进入编辑态；历史 accepted 章节只读，当前章自动保存、刷新恢复和确认都走正式 API；
- 主内容占满剩余视口，章节导航、阅读/编辑、Inspector 与完成态均不依赖 mock、timer 或本地假进度；
- 全部章节接受后自动进入 `/run/cover`；正式封面提交后自动进入 `/run/export`，继续复用 Wave 40 的 Cover/Book Delivery 工作台。

## 根因修复

浏览器 Run 已产生 `11` 条成功 receipt，但重启后的 read model 一度仍显示旧的 `7` 次 operation。最低责任层不是 SSE、前端缓存或 Provider 重试，而是 usage 聚合校验：

1. 文本 Provider 没有冻结计价表，operation 成本为未知；
2. 本地 Fake 图片 Provider 明确返回固定成本 `0.0`，状态为已知；
3. 旧聚合把部分已知的 `0.0` 当作全局估算总价，同时又把全局状态标成 `unknown`；
4. 该自相矛盾的投影触发 Pydantic 校验失败，driver 因而保留旧 read model 统计。

修复后只有全部 operation 成本已知时才生成全局总价。混合已知/未知时全局保持 `estimated_cost_usd=null / cost_status=unknown`，Provider 子项不丢失各自精度；driver 测试同时锁定最终 read model 必须等于 receipt store 重建汇总。

## 浏览器证据

隔离环境：

- Fake Provider/API：`127.0.0.1:8797`；
- Vite：`127.0.0.1:5186`；
- Project：`wave41-long-chapter-project`；
- Run：`wave41-long-chapter-run`；
- 验收结束后测试页、API 与 Vite 均已关闭。

验收覆盖：

1. `1728x1100`、`1440x1000`、`1280x920`、`1024x700`、`390x844` 的长篇正文页均无横向溢出，桌面二级栏为 `184px`；
2. 第一章 accepted 版本只读；第二章可编辑，自动保存后刷新仍恢复同一草稿，确认后生成新的 committed version；
3. 第二章正式正文为“听证厅的门合上时，玛雅把两份签名并排放在投影灯下。/审批时间彼此冲突，旁听席第一次安静下来。”，共 `45` 个字符；
4. 两章确认后自动进入 Cover，三张本地 Fake PNG 候选真实持久化；选择候选 1、等待草稿保存并确认后自动进入 Export；
5. Export Manifest 顺序为 `chapter-1 / chapter-2`，版本 refs 与 committed Chapter Artifact 一致，第二章是浏览器编辑后的版本；
6. 正式封面 SHA-256 为 `438c39240643ca425158458501d4f40ceeb65831c8fbf9af35cec91084d8654a`；
7. `失序档案.docx` 为 `7,777 B`，SHA-256 为 `e2234234c6b58c8c85aa2f2ce0e2fe7c73b397e9ac37de8e73bd3b3343454c7d`；DOCX 内能检出两章标题及浏览器编辑后的第二章正文；
8. Run 终态为 `completed/export`，`11/11` operation 成功：文本 `8` 次成本未知，图片 `3` 次成本 `0.0 / known`，全局成本 `null / unknown`；
9. Export 在 `1728x1100` 与 `390x844` 均无横向溢出，移动端未命名按钮为 `0`，Browser Console 为 `0 error / 0 warning`。

截图证据位于：

- `output/playwright/wave32-41-long-chapter/long-chapter-1728x1100.png`
- `output/playwright/wave32-41-long-chapter/long-chapter-1440x1000.png`
- `output/playwright/wave32-41-long-chapter/long-chapter-1280x920.png`
- `output/playwright/wave32-41-long-chapter/long-chapter-1024x700.png`
- `output/playwright/wave32-41-long-chapter/long-chapter-390x844.png`
- `output/playwright/wave32-41-long-chapter/long-chapter-390x844-inspector.png`
- `output/playwright/wave32-41-long-chapter/long-chapter-both-accepted-1728x1100.png`
- `output/playwright/wave32-41-long-chapter/long-chapter-to-cover-1728x1100.png`
- `output/playwright/wave32-41-long-chapter/long-export-1728x1100.png`
- `output/playwright/wave32-41-long-chapter/long-export-390x844.png`

## 测试与审计

- 长篇章节、Provider cost sidecar 与 driver 定向回归：通过；
- 后端全量：`1080 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`58 files / 135 tests passed`；
- TypeScript/Vite production build、CSS audit、CSS build check 与 frontend structure audit：通过；
- Python `compileall`、`git diff --check` 与 production closure audit：通过；
- production closure audit 无 legacy runtime marker、无异常 pipeline 顶层目录；既有大文件继续列入责任审查，本轮不为行数机械拆分。
- production build 仍报告既有主入口与 `CharacterGraph3D` 大 chunk 提示；长篇 StageView 保持独立懒加载，没有并回首屏执行路径。

## 验收边界

1. 本轮证明长篇两章 Fake Provider 的逐章状态、作者草稿、正式封面、确定性交付和浏览器链路，不证明真实文本/图片 Provider 的稳定性、成本或审美质量；
2. 两章仅是 `release_smoke` 容量级合同样本，不证明 10-20 万字长篇的上下文规模、长期连续性或文学质量；
3. DOCX 是当前已配置格式；Phase 32 发布门要求的 EPUB/Markdown、500 章/50 卷/120+ 人物性能、自动无障碍与恢复矩阵仍需独立闭合；
4. Phase 32 作者协作、Story Bible、三路线同一 runtime digest 的新鲜真实 Provider Run 与文学观察仍未完成；
5. README、CHANGELOG、版本修改、commit、push、Tag 与 Release 继续等待第 17-18 节完整发布证据包。

长篇 `Text -> Cover -> Export` 的 Fake Provider 正向路径至此闭合。下一切片应回到共用生产缺口，优先完成 Phase 32 作者协作/Story Bible 权威迁移、自动无障碍与规模/恢复门；这些低层门关闭后，才进入三路线同版本真实 Provider 稳定性验收。
