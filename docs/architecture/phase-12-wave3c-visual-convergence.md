# Phase 12 Wave 3C 黑晶工作台视觉收敛

> 状态：已完成（2026-07-27）
>
> 目标：修正 Wave 3 Artifact Deck 过度平铺的问题，并把同一套可实现的黑晶编辑工作台语言扩展到 Studio、阶段工作台、Story Bible 与全局对话框。视觉方向不改变阶段 Artifact、用户确认、正式写回或后端字段合同。

## 1. 问题定义

- 当前 Planning 七张稿件接近等宽横排，层叠、透视和选中稿件的主次关系不足。
- 中央区域的稿件占比偏小，纵向留白过多，和方向板中的编辑驾驶舱构图差距明显。
- Studio、运行阶段、Story Bible 已使用深色表面，但材质、边框、稿纸和选择态没有形成一个稳定的产品语言。
- 视觉优化必须使用真实状态与真实动作；不得用假版本、假字数、假百分比或任务管理字段填充画面。

## 2. 方向板

- 基准方向板：`output/visual-direction/novel-workflow-black-crystal-cockpit-v1.png`
- 多页面方向板：`output/visual-direction/novel-workflow-multisurface-styleboard-v2.png`
- 方向板只定义材质、层次、构图、密度和选中态，不定义新的产品功能。

## 3. 采用矩阵

| 生成样式 | 目标页面 | 真实产品含义 | 实现边界 | 验收证据 |
| --- | --- | --- | --- | --- |
| 斜向银灰稿件堆栈 | Planning | 七阶段 Artifact 与当前选择 | 状态来自 Workflow / SSE；右侧仍是配置面 | `planning-after-*.png` |
| 高亮主稿 + 退入景深的前后稿 | Planning | 当前阶段与相邻阶段 | 键盘顺序不变；移动端降级为二维横向轨 | 桌面三视口 + `390x844` |
| 书脊式作品层次 | Studio | 作品、最近阶段、最近活动 | 不制造封面、进度或运行数据 | `studio-after-*.png` |
| 低反射稿纸 + 窄检视轨 | Summary / Outline / Detail / Text | 当前结构化 Artifact 与支持信息 | “保存到当前稿”与“确认定稿/正式写回”继续分离 | 代表阶段桌面与移动截图 |
| 连续性档案墙 | Story Bible | 已正式写回的人物、世界、伏笔、正典事实 | 页面保持只读并显示来源 | `bible-after-*.png` |
| 银灰实体对话框 | 全局对话框 | 集中编辑、确认与失败恢复 | 不嵌套卡片；单一滚动所有者；保留危险语义色 | 对话框键盘与裁切检查 |

## 4. 视觉规则

1. 中性黑底、银灰玻璃、低反射稿纸三层足够；不增加装饰性第四层。
2. 每页只允许当前创作模式色作为主活动光，完成、警告和失败继续使用语义色。
3. 选中稿件通过尺寸、前移、边缘高光和内容密度建立主次，不使用持续辉光。
4. 透视只用于桌面视觉摘要；移动端为稳定二维横向轨，Reduced Motion 禁用位移动画。
5. 工作台使用 6-8px 圆角、细边和紧凑字号；不做营销 Hero、卡中卡、粒子、光球或无限动画。

## 5. 本轮顺序

1. 重建 Planning Artifact Deck 的空间构图并做截图对照。
2. 提取黑晶表面、稿纸、选择态和紧凑工具条规则，分别落到 Studio、运行阶段和 Story Bible。
3. 收敛对话框表面与遮罩，但不重写已经验证的编辑/写回流程。
4. 完成 `1280x920`、`1440x1000`、`1728x1100`、`390x844` 的截图、页面溢出、控制台、测试、构建和 CSS 审计。

## 6. 非目标

- 不实现 Phase 12 Wave 4 的 tour 引擎。
- 不重写后端、SSE、阶段 Artifact 或正式写回合同。
- 不用生成图片充当产品背景或最终交互界面。
- 不为了追求概念图相似度牺牲编辑密度、可访问性、移动端和 Reduced Motion。

## 7. 实现结果

- Planning 中央稿件栈已从固定横排改为七张独立薄稿组成的 CSS 3D 扇面。当前稿使用模式色玻璃前景、双层薄边与 Z 轴前移；前后稿沿阶段顺序分列两侧，按距离降低亮度、尺寸与景深。
- 稿件坐标由 `artifactDeckLayout.ts` 统一计算。选中阶段沿工作流轴移动，首阶段向右展开、中段双向展开、末阶段向左收拢；底部银灰托轨和模式色标记与当前阶段同步。
- 引入 `gsap` 与 `@gsap/react`，使用有作用域和自动清理的 `useGSAP` 时间线编排整组稿件重排及一次性镜面高光。动画只改变 transform / opacity，不改变业务状态或布局尺寸。
- `prefers-reduced-motion: reduce` 下时间线时长归零，CSS transition 为 `0s`，实测重排后页面动画数为 `0`；移动端继续使用二维横向稿件轨，不执行 3D 位移。
- 当前产物、用户决策、定稿后写回、下一阶段依赖仍来自 Artifact Deck 真实语义模型；没有增加假版本、假字数、KPI、负责人或日历字段。
- Studio、运行阶段、Story Bible、配置 Sheet 和对话框继续使用各自已有的黑晶所有权文件；本轮接纳 CSS audit 中 6 个已审查新增文件，没有把生成图作为页面背景。

## 8. 浏览器证据

- `1280x920`：`output/acceptance/wave4/planning-gsap-deck-final-1280x920.png`
- `1280x720` 短视口：`output/acceptance/wave4/planning-gsap-deck-short-1280x720.png`
- `1440x1000` 第二阶段：`output/acceptance/wave4/planning-gsap-deck-stage2-final-1440x1000.png`
- `1440x1000` 中段双向扇面：`output/acceptance/wave4/planning-gsap-deck-stage4-pass2-1440x1000.png`
- `1440x1000` 末阶段：`output/acceptance/wave4/planning-gsap-deck-stage7-pass2-1440x1000.png`
- `1728x1100`：`output/acceptance/wave4/planning-gsap-deck-final-1728x1100.png`
- `390x844`：`output/acceptance/wave4/planning-gsap-deck-pass2-390x844.png`
- 阶段配置 Sheet：`output/acceptance/wave4/planning-config-sheet-gsap-1440x1000.png`
- Reduced Motion：`output/acceptance/wave4/planning-gsap-deck-reduced-final-1440x1000.png`
- 真实正文数据：`output/acceptance/wave4/text-stage-gsap-wave4-1440x1000.png`、`output/acceptance/wave4/text-stage-real-wave4-390x844.png`
- 真实 Story Bible 写回数据：`output/acceptance/wave4/bible-characters-real-wave4-1440x1000.png`

桌面三个标准视口、`1280x720` 短视口与移动端页面级横向溢出均为 `0`；短视口主稿完整保留在 Deck 视口内。移动端 Deck 为 `364px` 可视宽度 / `1262px` 内部滚动宽度。真实正文状态包含 3 章、5036 字；真实 Story Bible 状态包含 5 人物 / 5 关系。独立浏览器控制台为 `0 error / 0 warning`。

常规动效验收记录到 GSAP 时间线的中间 transform 与最终 transform 均发生变化；Reduced Motion 环境中 `matchMedia` 命中、选择末阶段耗时 `38ms`、CSS transition 为 `0s`、页面动画数为 `0`。Arrow、Home、End 的 roving tabindex 路径保持可用。

## 9. 工程门禁

- 前端：`113` 个测试文件、`439` 项测试全部通过。
- 后端：`275 passed, 1 skipped`；唯一 warning 为 Starlette TestClient 的既有 httpx 弃用提示。
- 生产构建通过；`git diff --check` 通过。
- CSS audit 通过；CSS split 通过，首屏 CSS 为 `35,589 bytes / 34.8 KiB gzip`，低于 `40 KiB` 目标。
- Artifact Deck 主视觉文件为 `291` 行；壳层、说明栏和响应式规则按责任拆分，所有文件位于 `planning/` 所有权内。

## 10. 已知限制

- 当前 Studio 接口返回 `0` 部作品，因此本轮浏览器只能验收其真实空态，未为截图创建虚假作品；项目卡路径仍由既有 `ProjectCardWall` 测试覆盖。
- 3D 扇面只用于 Planning 的阶段摘要。移动端、正文编辑和 Story Bible 不复用该空间效果，以避免牺牲文本密度和交互稳定性。
