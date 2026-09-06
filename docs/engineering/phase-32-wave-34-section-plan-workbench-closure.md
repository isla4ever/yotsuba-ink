# Phase 32 Wave 34：Section Plan 双态工作台闭环

状态：**短中篇 `SectionPlanArtifact` 已完成 source-bound 作者草稿、上游引用校验、阅读/编辑双态工作台与隔离浏览器验收；本轮没有调用真实 Provider，也没有改写历史 Run**

日期：2026-08-24

## 产品决定

`SectionPlanArtifact` 是正文开写前的施工排程，不是章节字段表单。页面围绕一个作者决定组织：当前单元是否具备清晰的戏剧任务、可执行的场景负载、有效 POV、Promise 推进和能驱动下一单元的 handoff。

1. 默认阅读态不渲染 `input`、`textarea` 或 `select`；
2. 编辑态只开放当前单元，其他单元保持稳定阅读与导航状态；
3. `scene_load` 按合同展示为整体场景负载说明，不伪造成第二套 Scene 数组；
4. 连续性使用“上一单元 handoff -> 当前戏剧任务 -> 下一单元入口”呈现；
5. 左侧单元栏使用统一 `--stage-secondary-width: 184px`，主区按“戏剧任务 / 场景负载 / 状态交接”三个 Tab 分区；
6. committed Artifact 保持只读，候选草稿只能通过 source-bound decision revision 保存和提交。

## 后端合同

- 开放 `short_novel/section_plan` 的 source-bound 作者草稿编辑；
- `unit_ref` 集合保持冻结，允许调整顺序、标题、POV、戏剧任务、场景负载、handoff 与软字数；
- 保存和提交时校验 POV 必须来自已确认 Cast，Promise 必须来自已确认 Story Map；
- 候选、草稿与 committed Artifact 继续使用同一 Artifact Store、Run repository 和 decision authority；
- 没有新增 route runtime selector、旧 schema fallback、第二套 Artifact Store 或 Provider 直写路径。

## 前端结果

- 新增 Section Plan 解析、排序、预算和 Promise 覆盖诊断纯函数；
- 新增上游 Story Map/Cast 引用读取 hook；
- 工作台由 184px 单元导航、连续施工纸面和阶段检查器组成；
- 阅读态采用定义列表、流程带和账本呈现，编辑态使用嵌入纸面的紧凑编辑槽；
- 检查器展示单元数、总软字数、POV 数、Promise 覆盖、当前引用来源和版本来源；
- 移动端隐藏普通二级栏，改用横向单元快捷导航；
- 共享阅读/编辑图标按钮补充 `aria-label` 与 tooltip，移动端图标化后仍有明确可访问名称。

## 浏览器证据

隔离环境：

- fixture API：`127.0.0.1:8790`；
- Vite：`127.0.0.1:5179`；
- 用户原有 `127.0.0.1:5176` 未停止、未修改；
- 所有数据只写入 `/tmp/yotsuba-wave34-section-plan`。

验收覆盖：

1. 候选阅读态控件数为 `0`，二级栏计算宽度为 `184px`；
2. 5 个单元、3 个 POV、20,000 软字数和 3 条 Promise 覆盖均来自真实 Artifact API；
3. 单元切换及“戏剧任务 / 场景负载 / 状态交接”Tab 均更新当前内容和检查器来源；
4. 编辑态只出现当前单元的标题、软字数、POV 和当前 Tab 文本共 4 个控件；
5. 修改第二单元标题后显示“草稿已保存”，刷新后恢复服务端草稿并回到默认阅读态；
6. committed 页面控件数为 `0`，“编辑模式”禁用，并提供“进入小说正文”入口；
7. `1440x1000`、`1024x700`、`390x844` 均无横向溢出；移动端普通侧栏隐藏、单元快捷导航显示；
8. 最终浏览器 Console 为 `0 error / 0 warning`。

截图证据位于：

- `output/playwright/wave34-section-plan-candidate-1440x1000.png`
- `output/playwright/wave34-section-plan-1024x700.png`
- `output/playwright/wave34-section-plan-390x844.png`
- `output/playwright/wave34-section-plan-edit-390x844.png`
- `output/playwright/wave34-section-plan-committed-1440x1000.png`

## 测试与审计

- 后端全量：`1049 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`39 files / 102 tests passed`；
- frontend structure audit：`150` 个 TypeScript source files，通过；
- CSS audit：`crossFileDuplicateSelectorCount=0`、`duplicateKeyframeNameCount=0`、`infiniteAnimationCount=9`、`reducedMotionGuardCount=22`，通过；
- production build 与 TypeScript：通过；
- Section Plan 独立产物：CSS `16.57 kB`，JS `19.71 kB`；
- 首屏 CSS：`31.7 KiB gzip`，通过预算检查；
- 目标 `oxfmt --check` 与 `git diff --check`：通过。

production build 仍报告既有主入口与 Character Graph 3D 大 chunk warning。本轮保持 3D 图谱动态导入，没有把它并入 Section Plan 或扩大首屏 CSS；该 warning 不在本轮功能范围内，也不据此宣称性能专项完成。

## 验收边界

1. 本轮证明的是 Section Plan 的离线合同、真实 API 草稿闭环和浏览器交互，不证明真实 Provider 文学质量、成本或长链恢复；
2. committed amendment、ImpactAnalysis 和下游 stale 重算仍未在该页面开放；
3. Text、Cover 与 Export 尚未全部迁移为 Phase 32 专业双态工作台；
4. 剧本路线的 `BeatBoardArtifact` 与 `SceneDeckArtifact` 仍是正文前优先缺口；
5. README、CHANGELOG、commit 与 GitHub push 继续等待三条路线完整证据包。

下一切片按已批准路线迁移剧本 `BeatBoardArtifact`，随后迁移 `SceneDeckArtifact`；不得复用旧脊柱因果链表单，也不得建立剧本专用 runtime。
