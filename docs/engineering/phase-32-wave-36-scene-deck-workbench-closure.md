# Phase 32 Wave 36：Scene Deck 双态工作台闭环

状态：**剧本样片 `SceneDeckArtifact` 已完成 source-bound 作者草稿、Cast 引用校验、阅读/编辑双态工作台与隔离浏览器验收；本轮没有调用真实 Provider，也没有改写历史 Run**

日期：2026-08-24

## 产品决定

`SceneDeckArtifact` 负责把已确认 Beat Board 转换为可执行的场景调度，不负责写对白正文，也不重新发明一条逐场因果链。

1. 核心决策固定为场景顺序、标准场景标题、地点时间、出场人物、可见目标、台面对抗、场景结果与软页数；
2. 默认阅读态不渲染 `input`、`textarea` 或 `select`，编辑态只开放当前 Scene；
3. `scene_ref`、Scene 集合和已确认 Cast 身份保持冻结，作者只能调整顺序与文学字段；
4. Beat Board 作为可见决定与结果的上游依据展示，但当前 Artifact 没有 `beat_ref`，前端不伪造逐场映射；
5. “上一场结果 -> 当前场目标 -> 下一场入口”只投影现有字段，帮助检查交接，不作为文学因果硬门；
6. 左侧 Scene 栏使用统一 `--stage-secondary-width: 184px`，移动端改为横向 S01-S06 快捷导航；
7. committed Artifact 保持只读，并从同一 Run read model 跳转到下一阶段 Script。

## 后端合同

- 开放 `screenplay_sample/scene_deck` 的 source-bound 作者草稿编辑；
- `scene_ref` 集合与 Scene 数量保持冻结，允许调整顺序、场景标题、地点时间、Cast 组合、可见目标、对抗、结果与软页数；
- 替换、增加或删除冻结 `scene_ref` 返回冲突；
- 重复 Cast 引用、未知 Cast 引用和空 Cast 组合均被确定性拒绝；
- 已确认人物来源于 committed `CharacterBibleAggregate`，Scene Deck 不能创建新人物身份；
- 合法草稿物化为新候选后通过同一 decision authority 提交，并推进 `script`；
- 没有新增剧本专用 runtime、旧 schema fallback、第二套 Artifact Store 或 Provider 直写路径。

## 前端结果

- 新增 Scene Deck 解析、排序、容量与人物覆盖诊断纯函数；
- 新增已确认 Beat Board 与 Cast 上游读取 Hook；
- 工作台由 184px Scene 导航、场景调度纸面和右侧检查器组成；
- “场景调度”Tab 展示可见目标、台面对抗、场景结果和前后场交接；
- “制作信息”Tab 展示标准场景标题、地点时间与已确认人物组合；
- 检查器展示场次、总页数、均场页数、人物覆盖、Beat 上游和 Artifact 版本；
- 阅读/编辑切换、650ms 自动保存、刷新恢复、顺序调整、定向换稿、取消、确认和下游跳转均复用 Phase 32 正式服务；
- Scene Deck 以独立 lazy chunk 加载，没有并入主入口或 3D 人物图谱 chunk。

## 浏览器证据

隔离环境：

- fixture API：`127.0.0.1:8792`；
- Vite：`127.0.0.1:5181`；
- 用户原有 `127.0.0.1:5176` 与既有验收服务未停止、未修改；
- 所有 fixture 数据只写入 `/tmp/yotsuba-wave36-scene-deck`；
- 候选 Project：`project-scene-deck-candidate`；
- committed Project：`project-scene-deck-committed`。

验收覆盖：

1. 候选阅读态工作台没有表单控件，二级栏计算宽度为 `184px`；
2. 6 个真实 Scene、12 页软目标、4 个 committed Cast 和 6 个 committed Beat 均来自正式 Artifact API；
3. Scene 切换会更新当前场景、调度内容、连续入口与制作信息；
4. “场景调度 / 制作信息”Tab 在桌面和移动端都可切换；
5. 编辑态只出现当前 Scene 的页数、顺序、当前 Tab 文本或 Cast 控件；
6. 第三个 Scene 的地点时间已自动保存为“闭馆前八分钟，应急灯开始闪烁”，刷新后恢复服务端草稿并回到阅读态；
7. committed 页面工作台表单控件数为 `0`，“编辑模式”禁用，并提供“进入剧本正文”入口；
8. 下游入口正确跳转到 `/run/script`，并投影 Script 的 `awaiting_decision` 状态；
9. `1728x1100`、`1440x1000`、`1280x920`、`1024x700`、`390x844` 均无横向溢出；
10. 移动端能切换 Scene、阅读/编辑与两个 Tab，滚到最底时 Artifact 版本区不被固定底栏遮挡；
11. 最终浏览器 Console 为 `0 error / 0 warning`。

截图证据位于：

- `output/playwright/wave36-scene-deck-candidate-1728x1100.png`
- `output/playwright/wave36-scene-deck-candidate-1440x1000-final.png`
- `output/playwright/wave36-scene-deck-candidate-1280x920.png`
- `output/playwright/wave36-scene-deck-candidate-1024x700.png`
- `output/playwright/wave36-scene-deck-candidate-mobile-read-390x844.png`
- `output/playwright/wave36-scene-deck-candidate-mobile-edit-390x844.png`
- `output/playwright/wave36-scene-deck-candidate-mobile-bottom-390x844.png`
- `output/playwright/wave36-scene-deck-committed-1440x1000.png`

## 测试与审计

- 后端定向：`47 passed, 1 warning`；
- 后端全量：`1054 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端定向：`3 files / 6 tests passed`；
- 前端全量：`45 files / 116 tests passed`；
- frontend structure audit：`160` 个 TypeScript source files，通过；
- CSS audit：`crossFileDuplicateSelectorCount=0`、`duplicateKeyframeNameCount=0`、`infiniteAnimationCount=9`、`reducedMotionGuardCount=25`，通过；
- production build、TypeScript、Python `compileall` 与首屏 CSS 预算：通过；
- Scene Deck 独立产物：CSS `18.42 kB`，JS `20.94 kB`；
- 首屏 CSS：`31.7 KiB gzip`，通过预算检查；
- 目标 `oxfmt --check`、`git diff --check` 与 production closure audit：通过。

production build 仍报告既有主入口与 Character Graph 3D 大 chunk warning。本轮保持 3D 图谱动态导入，Scene Deck 也使用独立懒加载，没有扩大首屏 CSS；该 warning 不在本轮功能范围内，也不据此宣称性能专项完成。

## 验收边界

1. 本轮证明的是 Scene Deck 的离线合同、正式 API 草稿闭环和浏览器交互，不证明真实 Provider 的场景质量、成本或长链恢复；
2. 场景顺序、引用和字段完整性可以确定性校验，但可拍性、冲突力度与场景交接效果仍需文学审读；
3. committed amendment、Scene 拆分/合并和下游 stale 重算尚未在该页面开放；
4. 剧本路线的 `ScreenplayDraftArtifact` 与交付工作台仍未完成专业双态迁移；
5. 短中篇 Text、长篇 Text、Cover、Export、作者协作和 Story Bible 的 Phase 32 专业投影仍未全部完成；
6. README、CHANGELOG、commit 与 GitHub push 继续等待三条路线完整证据包。

下一切片按已批准路线迁移剧本 `ScreenplayDraftArtifact`；必须以 Scene 为顺序单元、显示规范剧本正文与版本决策，不能回退到通用大文本框或旧 Text 工作台。
