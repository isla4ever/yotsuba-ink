# Phase 32 Wave 35：Beat Board 双态工作台闭环

状态：**剧本样片 `BeatBoardArtifact` 已完成 source-bound 作者草稿、冻结身份校验、阅读/编辑双态工作台与隔离浏览器验收；本轮没有调用真实 Provider，也没有改写历史 Run**

日期：2026-08-24

## 产品决定

`BeatBoardArtifact` 不是旧版“脊柱因果链”，也不是 AI 因果评分器。页面围绕一个作者决定组织：哪些角色决定和结果必须在屏幕上被看见，以及节拍是否兑现样片承诺。

1. 核心关系固定为“可见压力 -> 台面决定 -> 新局面”；
2. 默认阅读态不渲染 `input`、`textarea` 或 `select`；
3. 编辑态只开放当前 Beat，允许调整文学字段与顺序，不允许改变冻结身份；
4. `setup_or_payoff_refs` 作为稳定引用账本展示，覆盖可以确定性统计，文学效果只作为后续 warning；
5. Brief 只提供样片类型、观众承诺、可见冲突、结尾效果和软时长；Cast 只作为已确认人物名册来源，不伪造 Artifact 中不存在的人物引用字段；
6. 左侧 Beat 栏使用统一 `--stage-secondary-width: 184px`，移动端改为横向快捷导航；
7. committed Artifact 保持只读，候选草稿只能通过 source-bound decision revision 保存和提交。

## 后端合同

- 开放 `screenplay_sample/beat_board` 的 source-bound 作者草稿编辑；
- `beat_ref` 集合与 Beat 数量保持冻结，允许调整顺序、戏剧任务、可见压力、角色决定、结果、铺垫/回收引用与节奏提示；
- 替换、增加或删除冻结 `beat_ref` 返回 409；
- 合法草稿物化为新候选后通过同一 decision authority 提交，并推进 `scene_deck`；
- 没有新增剧本专用 runtime、旧 schema fallback、第二套 Artifact Store 或 Provider 直写路径；
- 决定可信度、冲击力度、节奏审美和可拍性没有被伪装成确定性 blocker。

## 前端结果

- 新增 Beat Board 解析、排序、引用归一化与覆盖诊断纯函数；
- 新增上游 Brief/Cast 读取 Hook；
- 工作台由 184px Beat 导航、屏幕决策纸面和阶段检查器组成；
- “决策链”Tab 展示当前 Beat 与前后 Beat 的连续入口；
- “任务与铺垫”Tab 展示戏剧任务、setup/payoff 稳定引用及 Brief 冲突/结尾对齐；
- 检查器展示 Beat 数、引用覆盖、无引用 Beat、样片承诺、已确认人物名册和 Artifact 版本；
- 阅读/编辑切换、自动保存、定向换稿、取消、确认和下游跳转均使用现有 Phase 32 决策服务；
- Beat Board 作为独立 lazy chunk 加载，没有并入主入口或 3D 人物图谱 chunk。

## 浏览器证据

隔离环境：

- fixture API：`127.0.0.1:8791`；
- Vite：`127.0.0.1:5180`；
- 用户原有 `127.0.0.1:5176` 未停止、未修改；
- 所有 fixture 数据只写入 `/tmp/yotsuba-wave35-beat-board`。

验收覆盖：

1. 候选阅读态控件数为 `0`，二级栏计算宽度为 `184px`；
2. 6 个 Beat、12 条 setup/payoff 引用和 4 个已确认人物均来自真实 Artifact API；
3. Beat 切换会更新当前压力、决定、结果与前后连续入口；
4. “决策链 / 任务与铺垫”Tab 切换会更新当前内容和引用区域；
5. 编辑态只出现当前 Beat 的节奏提示、当前 Tab 文本与稳定引用共 3 个控件；
6. 修改第三个 Beat 戏剧任务后显示“草稿已保存”，刷新后恢复服务端草稿并回到默认阅读态；
7. committed 页面控件数为 `0`，“编辑模式”禁用，并提供“进入场景牌组”入口；
8. `1280x920`、`1440x1000`、`1728x1100`、`1024x700`、`390x844` 均无横向溢出；移动端普通侧栏隐藏、Beat 快捷导航显示；
9. 最终浏览器 Console 为 `0 error / 0 warning`。

截图证据位于：

- `output/playwright/wave35-beat-board-candidate-1440x1000.png`
- `output/playwright/wave35-beat-board-candidate-1728x1100.png`
- `output/playwright/wave35-beat-board-1024x700.png`
- `output/playwright/wave35-beat-board-390x844.png`
- `output/playwright/wave35-beat-board-edit-390x844.png`
- `output/playwright/wave35-beat-board-committed-1440x1000.png`

## 测试与审计

- 后端定向：`44 passed, 1 warning`；
- 后端全量：`1051 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端定向：`3 files / 8 tests passed`；
- 前端全量：`42 files / 110 tests passed`；
- frontend structure audit：`155` 个 TypeScript source files，通过；
- CSS audit：`crossFileDuplicateSelectorCount=0`、`duplicateKeyframeNameCount=0`、`infiniteAnimationCount=9`、`reducedMotionGuardCount=24`，通过；
- production build、TypeScript 与首屏 CSS 预算：通过；
- Beat Board 独立产物：CSS `16.80 kB`，JS `19.81 kB`；
- 首屏 CSS：`31.7 KiB gzip`，通过预算检查；
- 目标 `oxfmt --check` 与 `git diff --check`：通过。

production build 仍报告既有主入口与 Character Graph 3D 大 chunk warning。本轮保持 3D 图谱动态导入，Beat Board 也使用独立懒加载，没有扩大首屏 CSS；该 warning 不在本轮功能范围内，也不据此宣称性能专项完成。

## 验收边界

1. 本轮证明的是 Beat Board 的离线合同、真实 API 草稿闭环和浏览器交互，不证明真实 Provider 文学质量、成本或长链恢复；
2. setup/payoff 覆盖可确定性统计，但节拍因果说服力、可拍性和节奏效果仍需文学审读；
3. committed amendment、ImpactAnalysis 和下游 stale 重算尚未在该页面开放；
4. 剧本路线的 `SceneDeckArtifact`、`ScreenplayDraftArtifact` 和交付工作台仍未完成专业双态迁移；
5. README、CHANGELOG、commit 与 GitHub push 继续等待三条路线完整证据包。

下一切片按已批准路线迁移剧本 `SceneDeckArtifact`；不得把 Scene Deck 做成普通卡片墙、小说式内心梗概或剧本专用 runtime。
