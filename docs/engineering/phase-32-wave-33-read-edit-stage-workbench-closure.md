# Phase 32 Wave 33：阶段双态工作台与 Rolling Detail 闭环

状态：**Brief、Story Map、Book Architecture、Cast、Volumes、Rolling Detail 已统一为默认阅读态与聚焦编辑态；普通阶段二级栏统一为 184px；本轮没有调用真实 Provider**

日期：2026-08-24

## 产品决定

阶段页不再把核心文学 Artifact 直接摊成整页表单。六个已迁移规划阶段采用同一交互合同：

1. 默认进入阅读态，以文档、定义列表、施工账本、流程带和局部分区呈现已生成内容；
2. 只有候选稿可进入编辑态，committed 版本保持只读；
3. 编辑态只开放当前人物、Part、Volume、Window 或章节，不同时展示整个聚合的输入控件；
4. 复杂内容使用分区 Tab 和账本，不用纵向卡片或表单墙承载全部字段；
5. 阅读/编辑切换使用 180ms 状态淡入，Reduced Motion 下关闭动画；
6. 普通阶段二级导航统一使用 `--stage-secondary-width: 184px`，内容按真实高度排列，不拉伸铺满。

## 工作台结果

- Brief：作品核心、世界与收束使用阅读文档面；候选稿才允许编辑；
- Story Map：分为“开场与问题 / 当前故事锚点 / 收束与追问”，左栏只负责锚点选择；
- Book Architecture：分为“全书根契约 / 当前 Part”，Part 顺序和稳定引用继续由聚合根管理；
- Cast：人物名册保持 184px，人物档案分为“核心档案 / 行动边界 / 关系账本”，3D 关系投影仍是只读可重建投影；
- Volumes：阅读态以“承诺 -> 对抗 -> 高潮 -> 闭合”的卷册流程呈现，软篇幅和排序只在编辑态出现；
- Rolling Detail：使用 Window/章节二级导航、章节施工账本和“章节引擎 / 场景施工 / 状态交接”分区，正文阶段只读取当前有界章节上下文。

编辑控件采用嵌入文档面的自适应编辑槽：默认透明、只保留底线，聚焦时才增强背景与强调色；`field-sizing: content` 控制内容高度，取消 textarea 拖拽角标。人物核心档案使用两列账本，不再呈现六个大文本框。

面向作者的主路径文案同步去除 `Committed Artifact`、`Contract`、`scenes` 等实现术语；稳定 ref、版本来源和内部合同信息只在必要的检查器位置保留。

## 浏览器证据

隔离环境：

- Rolling Detail fixture API：`127.0.0.1:8788`；Vite：`127.0.0.1:5177`；
- Cast/Story Map fixture API：`127.0.0.1:8789`；Vite：`127.0.0.1:5178`；
- 用户原有 `127.0.0.1:5176` 未修改、未停止。

浏览器验证包括：

1. Rolling Detail 默认阅读态无输入控件；切换编辑后只开放当前 Window 与当前章节；
2. 修改章节标题后出现“草稿已保存”，刷新后回到阅读态并从服务端恢复同一草稿；
3. “章节引擎 / 场景施工 / 状态交接”分区可切换，阅读态控件数为 0；
4. 长篇 Brief、Book Architecture、Cast、Volumes committed 页面均为阅读态，主区无表单墙；
5. 短中篇 Story Map committed 页面分区、二级栏和检查器正常；
6. Cast 候选稿含 5 个人物、6 条关系，阅读态控件数为 0，编辑态只显示当前人物当前分区的 6 个编辑槽；
7. `1024x700` 与 `390x844` 下 `documentElement.scrollWidth === clientWidth`，移动端二级栏切换为横向快捷导航；
8. 最终浏览器控制台 `0 error / 0 warning`。

浏览器中的字段改动只写入 `/tmp` 隔离数据根，不进入历史 Run、用户项目或真实 Provider 数据。

## 测试与审计

- 前端定向双态测试：`6 files / 17 tests passed`；
- 前端全量：`35 files / 94 tests passed`；
- TypeScript 与 Vite production build：通过；
- frontend structure audit：`145` 个 TypeScript source files，通过；
- CSS audit：`crossFileDuplicateSelectorCount=0`、`duplicateKeyframeNameCount=0`，通过；
- CSS build check：首屏 CSS `31.7 KiB gzip`，通过；
- 后端全量：`1044 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- Python `compileall`、目标 `oxfmt --check` 与 `git diff --check`：通过。

CSS 审计基线已在浏览器和 production build 通过后更新，用于登记新增双态工作台样式；本轮没有新增跨文件重复 selector 或重复 keyframe。

production build 仍报告既有主入口与 Character Graph 3D 大 chunk warning；本轮保持 3D 图谱动态导入，没有把它并入首屏，也不据此宣称性能专项已完成。

## 验收边界

本轮只关闭六个已迁移规划阶段的双态信息架构和 Rolling Detail 浏览器链路，不代表 Phase 32 全部完成：

1. Beat Board、Scene Deck、Section Plan、Script、Text、Cover 与 Export 尚未全部迁移到相同双态工作台；
2. committed amendment、ImpactAnalysis 与跨阶段受影响范围重算尚未在这些页面开放；
3. 本轮没有调用真实 Provider，不能证明文学质量、真实成本或长链恢复；
4. 历史 Run 继续只读，不能用本轮 fixture 覆盖或改写；
5. README、CHANGELOG、commit 和 GitHub push 继续等待三条路线完整证据包。

下一切片应按路线优先迁移正文前仍缺失的专业工作台：短中篇 `SectionPlanArtifact`、剧本 `BeatBoardArtifact / SceneDeckArtifact`，再分别进入 Text 与 Script；不能为了页面完整度恢复旧八阶段表单或第二套 Artifact 权威。
