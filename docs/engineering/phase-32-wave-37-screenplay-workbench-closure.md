# Phase 32 Wave 37：逐 Scene 剧本正文工作台闭环

状态：**剧本样片 `ScreenplayDraftArtifact` 已完成逐 Scene 生成、source-bound 作者草稿、冻结引用校验、历史 Scene 回看、阅读/编辑双态工作台、顺序提交与隔离浏览器验收；本轮没有调用真实 Provider，也没有改写历史 Run**

日期：2026-08-24

## 产品决定

`script` 不是单一长文本 Artifact，而是以冻结 `SceneDeckArtifact.scenes` 为顺序权威的逐 Scene 正文集合。

1. 当前 Scene 才允许编辑、定向换稿、取消或确认；已接受 Scene 绑定不可变 committed Artifact，只读回看；
2. 页面默认阅读态，按场景标题、动作、对白、括注与转场渲染规范剧本页；编辑态才淡入块类型、人物、正文与排序控件；
3. Scene 标题必须与冻结 Scene Deck 完全一致，对白人物必须同时属于已确认 Cast 和当前 Scene 的冻结人物范围；
4. 当前 Scene 只能继承已接受前缀，不能跳过冻结游标生成或提交后续 Scene；
5. 左侧 Scene 栏保持统一 `--stage-secondary-width: 184px`，移动端替换为横向 S01-S03 快捷导航；
6. “调度依据”只展示上一场结果、本场目标、台面对抗与必须落地的结果，不把文学因果伪装成确定性评分；
7. Export 只在所有冻结 Scene 都拥有 committed Artifact 后开放，并按冻结 Scene 顺序绑定不可变版本。

## 后端合同

- `ScreenplayDraftArtifact` 以一个 `scene_ref` 和有序正文块为最小生成、编辑、确认与恢复单元；
- `SequentialStageProgress.ordered_unit_refs` 冻结 Scene 顺序，`committed_artifact_refs` 只允许按前缀增长；
- Provider 返回当前游标以外 Scene 时立即拒绝，不把错误输出保存为候选；
- source-bound 作者草稿必须保留 Scene 身份、冻结标题与人物引用边界；
- 全局 Cast 中存在、但不属于当前 Scene 的人物对白同样返回合同冲突；
- SQLite checkpoint 重开后从下一个未提交 Scene 恢复，不重生成已接受 Scene；
- Export 由三个 committed Scene 版本组装，不重新聚合成第二个单体 `script` Artifact；
- API route 继续只承担适配，顺序、引用、草稿与决定权威均保留在 Phase 32 domain/storage/runtime 边界。

## 前端结果

- 新增剧本 Artifact 解析、冻结引用诊断和短 Scene 标识纯函数；
- 新增 Scene Deck 与 Cast 上游上下文 Hook；
- 工作台由 184px Scene 导航、剧本纸面和右侧检查器组成；
- 点击已接受 Scene 会持续停留在所选历史版本，不再被 active Scene effect 自动拉回；
- 阅读态没有正文表单，编辑态按块展示类型、人物、文本、排序、删除与新增操作；
- 无效标题、未知人物或越过本场人物范围的草稿会在前端提前禁用确认，后端保留最终权威校验；
- 650ms 自动保存、刷新恢复、阅读/编辑切换、定向换稿、取消和逐 Scene 确认复用正式 Phase 32 服务；
- 第三场确认后由同一 Run read model 自动进入 `/run/export`，没有前端假进度或重复本地游标；
- `phase32-screenplay.css` 已作为独立懒加载样式登记 CSS 审计基线。

## 浏览器证据

隔离环境：

- Fake Provider/API：`127.0.0.1:8793`；
- Vite：`127.0.0.1:5182`；
- 用户原有 `127.0.0.1:5176` 未停止、未修改；
- 临时运行数据只写入 `/tmp/yotsuba-wave37-screenplay.*`；
- 候选 Project：`p32-screenplay-project-candidate`，启动时前两场已接受、第三场待决策；
- 完成态 Project：`p32-screenplay-project-committed`，三个 Scene 均已接受；
- Gateway 只返回确定性本地 payload，不读取 API Key，不发起外部请求。

验收覆盖：

1. 候选页面显示 3 个冻结 Scene、2 个 committed 版本和第三场候选，初始正文块数为 5；
2. 点击 S01、S02 后分别持续显示对应历史版本，`aria-current="step"` 保持正确，编辑禁用且确认按钮不出现；
3. 返回 S03 后，“剧本页 / 调度依据”Tab 正确切换并展示冻结目标、对抗与结果；
4. 编辑态只开放当前 Scene，冻结场景标题不可编辑，对白人物下拉只包含本场人物；
5. 第三场对白修改为“把时间、页码、水印和取证路径都写进公开记录。”后显示“草稿已保存”，刷新后恢复服务端草稿并回到阅读态；
6. S03 确认后页面进入 `/run/export`，Run 状态为 `completed`，三个 committed Artifact ref 按 `scene-1`、`scene-2`、`scene-3` 顺序写入；
7. 完成态页面表单控件数为 `0`，编辑禁用，显示 `3/3` 并提供“进入剧本交付”入口；
8. `1728x1100`、`1440x1000`、`1280x920`、`1024x700`、`390x844` 均无横向溢出；实测 `1728x1100`、`1280x920`、`1024x700` 的 Scene 栏计算宽度均为 `184px`；
9. 移动端桌面 Scene 栏与检查器隐藏，S01-S03 快捷导航可用；阅读、编辑、调度 Tab 和长表单底部均未被固定状态栏遮挡；
10. 候选、确认后 Export 与完成态页面最终 Browser Console 均为 `0 error / 0 warning`，没有 Vite overlay。

截图证据位于：

- `output/playwright/wave32-37-screenplay/screenplay-candidate-1728x1100.png`
- `output/playwright/wave32-37-screenplay/screenplay-candidate-1440x1000.png`
- `output/playwright/wave32-37-screenplay/screenplay-candidate-1280x920.png`
- `output/playwright/wave32-37-screenplay/screenplay-candidate-1024x700.png`
- `output/playwright/wave32-37-screenplay/screenplay-schedule-1440x1000.png`
- `output/playwright/wave32-37-screenplay/screenplay-edit-1440x1000.png`
- `output/playwright/wave32-37-screenplay/screenplay-mobile-read-390x844.png`
- `output/playwright/wave32-37-screenplay/screenplay-mobile-edit-390x844.png`
- `output/playwright/wave32-37-screenplay/screenplay-mobile-bottom-390x844.png`
- `output/playwright/wave32-37-screenplay/screenplay-committed-1440x1000.png`

## 测试与审计

- 后端 Wave 37 定向：`92 passed, 1 warning`；
- 后端全量：`1058 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`48 files / 122 tests passed`；
- frontend structure audit：通过；
- CSS audit：通过，`phase32-screenplay.css` 已独立登记；
- production build、TypeScript、Python `compileall`、首屏 CSS 预算与 `git diff --check`：通过；
- production build 仍报告既有主入口与 `CharacterGraph3D` 大 chunk warning；剧本工作台保持独立懒加载，没有扩大该既有问题。

## 验收边界

1. 本轮证明的是逐 Scene 离线合同、正式 API 草稿闭环与真实浏览器交互，不证明真实 Provider 的剧本质量、成本、连续性或长链恢复；
2. Scene 顺序、标题和人物范围可以确定性校验，可拍性、对白潜台词、动作密度与场间节奏仍需文学审读；
3. committed amendment、Scene 拆分/合并与下游 stale 重算尚未在该页面开放；
4. 剧本 Export 当前只证明权威入口与 ordered committed refs，专业剧本交付清单、格式预览、校验与下载工作台仍是下一切片；
5. 短中篇 Text、长篇 Text、Cover、Export、作者协作和 Story Bible 的 Phase 32 专业投影仍未全部完成；
6. README、CHANGELOG、commit 与 GitHub push 继续等待三条路线完整证据包。

下一切片迁移剧本 `ExportArtifact` 专业交付工作台：直接消费三个 ordered committed Scene 版本，展示交付清单、格式校验、元数据、版本来源与下载状态；不得重新生成正文、回退到旧 Export mock 或引入第二套交付持久化路径。
