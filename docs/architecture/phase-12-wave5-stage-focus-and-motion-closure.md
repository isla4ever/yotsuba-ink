# Phase 12 Wave 5：阶段主体聚焦、模态闭环与动效收敛

日期：2026-07-29

状态：已完成实现与本地自动化/浏览器验收；真实付费文本 Provider 的文学质量验收仍待明确成本授权。

## 1. 本轮目标

Wave 5 不继续给页面叠加装饰。它解决六类会直接破坏创作效率的问题：

1. AI 封面候选卡重叠、hover 频闪，候选与正式封面决策不够清楚。
2. 章节细纲弹窗切章时整块内容闪动，弹窗遮罩不能稳定阻断外部交互。
3. 小说信息定稿的左右内容高度失衡，主体稿件面积不足。
4. 正文页 Header、上下文条和独立章节进度条重复占高。
5. 每个阶段重复铺开人物、世界观、伏笔和正典，挤压当前阶段产物。
6. 七阶段稿件栈没有可靠跟随真实运行阶段，双击导航和 3D 几何仍不稳定。

本轮产品原则：当前阶段 Artifact 是主角；跨阶段长期记忆只在与当前决策直接相关时显示紧凑摘要，其余通过明确入口进入 Story Bible 对应 Tab。

## 2. 截图问题与根因

| 证据 | 问题 | 当前根因 | 决策 |
| --- | --- | --- | --- |
| 图 1 | 封面候选像两张失控的斜卡，hover 频闪 | GSAP 3D 位姿、重叠按钮命中区和 CSS hover 同时作用；相交卡不断争夺 `:hover` | 采用稳定候选轨；只有被预览候选可交互置前，hover 仅做 4-8px 的局部抽出和边框变化，不改整体堆叠或命中区 |
| 图 2 | 细纲弹窗切章闪屏 | 切章直接替换整份表单；没有稳定高度的内容视口和 keyed crossfade | 侧栏不动，稿纸内容在固定容器内 120-180ms 交叉淡入；表单焦点和未保存保护保持原合同 |
| 图 3 | 左列下方空缺，左右未利用同一可用高度 | Info 主区按内容自然高度分行，支撑区与简介不共享稳定网格轨道 | 统一为 12 栏响应式工作台；简介是最大稿件面，标题/标签/世界观/人物只占必要轨道，桌面同底线 |
| 图 4 | 正文阶段章节进度独占一整行 | Context Bar 已显示 `第 x/y 章`，下方 `ChapterProgressStrip` 再次重复 | 把章节状态 cells 合并进张力/章节导航轨；移除重复标题和统计行，保留可访问标签 |
| 图 5 | 每阶段重复显示四个全局系统 | 侧栏和阶段侧面板同时承担系统导航与当前阶段观察 | 侧栏保留全局入口；阶段页只显示当前阶段必须的摘要和异常，点击后跳对应 Bible Tab 或打开全局详情 |
| 图 6 | 稿件栈未跟随当前运行阶段，3D 朝向/厚度不可信 | `selectedId` 同时承担配置选择和运行当前位置；3D 父链存在会 flatten 的视觉属性，命中层与展示层混用 | 运行后默认选中真实 current stage；展示层和命中层分离；统一右向透视、平齐基线、固定卡厚；双击仅在可导航策略允许时进入阶段页 |

## 3. 阶段 Artifact 与首屏信息合同

前端不得展示后端未返回或无法由正式 Artifact 推导的结构。

| 阶段 | 后端正式字段 | 首屏主体 | 紧凑辅助 | 全局入口 |
| --- | --- | --- | --- | --- |
| Info | `selected_title`、`title_candidates`、`synopsis`、`worldbuilding_detail`、`characters`、`relationships`、`tags`、`downstream_constraints`、`risk_notes` | 书名与简介稿、人物基线 | 世界观摘要、人物数量/关系数量 | 人物关系、世界观 |
| Summary | `one_liner`、`full_synopsis`、`act_structure`、`core_conflict`、`character_arcs`、`key_turns`、`ending_resolution`、`consistency_checks` | 完整梗概稿纸 | 结构节拍、关键转折、质量异常 | 人物关系、世界观、质量 |
| Outline | `volumes[].title/chapter_range/volume_goal/rhythm/opening/development/midpoint/climax/resolution` 及三类写回数组 | 分卷 beat board | 当前卷节奏、写回计数 | 人物关系、世界观、伏笔 |
| Detail | `chapters[].chapter/pov/scene/goal/entry_state/conflict/stakes/hook/continuity_notes` 及事实、伏笔、人物变化、Wiki 候选 | 章节施工表与蓝图稿纸 | 当前章连续性、事实/伏笔计数 | 人物关系、世界观、伏笔、正典/Wiki |
| Text | `chapters[].content/summary/context_packet/quality_report/revision_history/version_history/writeback_proposal` | 正文稿纸 | 当前章上下文、质量阻断、写回决策 | 人物关系、世界观、伏笔、正典/Wiki |
| Cover | `brief`、`visual_keywords`、`composition`、`copy_suggestions`、`prompt`、`candidates`、`selected_candidate_id` | 大幅封面预览 | 候选轨、简报、资产/导出就绪 | 不显示创作观察全家桶 |
| Export | `manifest`、`formats`、`chapters`、`metadata`、`validation`、`package_status` | 交付清单与格式 | 校验摘要、失败门禁 | 不显示创作观察全家桶 |

### 3.1 辅助系统显示规则

- Info：人物与世界观是当前定稿内容，可显示精简摘要。
- Summary：人物弧、世界观冲突和质量异常直接影响梗概，可显示精简摘要。
- Outline：只显示本卷新增或变化的写回计数，不重复完整全局图谱。
- Detail：只显示当前章的事实、伏笔、人物变化和连续性摘要。
- Text：只显示当前章质量、Wiki/Canon 提案和必要上下文。
- Cover/Export：不显示人物、世界观、伏笔或 Canon。
- Story Bible 侧栏入口始终负责完整浏览，不在阶段页复制完整模块。

## 4. 统一模态合同

### 4.1 真实模态

- 所有全局弹窗通过 `document.body` Portal 或 Radix Portal 渲染。
- 打开时锁定 body 滚动，并将应用主内容设为不可交互；遮罩必须覆盖完整 viewport。
- 外部指针事件只能命中遮罩，不得穿透到底层按钮。
- 非破坏性弹窗点击遮罩关闭；有未保存修改时进入统一未保存确认，不直接丢稿。
- Escape 只关闭最顶层弹窗；Tab 焦点限制在最顶层弹窗内。
- 嵌套确认弹窗打开时，父弹窗暂停焦点陷阱但仍不可操作。

### 4.2 动效生命周期

- 遮罩：`autoAlpha 0 -> 1`，120-160ms。
- 对话框：`autoAlpha 0 -> 1`、`y 8 -> 0`、`scale .985 -> 1`，160-220ms。
- 关闭先播放退出，再卸载 DOM；禁止状态先清空导致白闪。
- Reduced Motion 下立即切换，但仍保持焦点、遮罩和 inert 语义。
- 所有 GSAP timeline 必须可中断、`overwrite: auto`，组件卸载时 revert/kill。

### 4.3 Tab 与章节切换

- Tab 容器尺寸稳定，不动画 `height/width/top/left`。
- 旧内容 80-120ms 淡出，新内容 120-180ms 淡入；只有 `opacity` 与最多 4px `x/y`。
- 表单切章保持弹窗、标题区、章节 rail、footer 不卸载，只替换稿纸内容。
- 新内容完成首帧后再恢复交互，避免连续点击造成两份内容交叠。

## 5. AI 封面候选轨

- 候选使用一条可扫描的稳定轨道，不再把两张大卡在窄列内硬叠。
- 桌面：大预览占中间主体；左侧候选为 2:3 缩略卡，按固定间距错位，活动候选置前。
- 14 寸和窄屏：候选改为横向滚动条，预览保持 2:3 比例；Inspector 降为底部决策区。
- hover 只对被 hover 卡的内部视觉层做 `x: 6px`/边框变化；按钮命中盒保持不动。
- `backface-visibility: hidden` 与 `transform-style: preserve-3d` 只用于展示层；存在 `overflow/filter/opacity` 的父层不承担 3D context。
- 候选状态完全来自 `asset_status` 与 `image_url`；没有真实图片时显示等待/失败，不制造假封面。

## 6. 阶段主体与响应式密度

### 6.1 桌面基线

- 1728×1100：阶段内容区尽量在一个 viewport 内完成首屏，不出现页面级横向滚动。
- 1440×900 / 14 寸：Header 收到 56-64px；主体使用 `minmax(0, 1fr)`；辅助摘要压缩为 rail/小计数。
- 1280×920：允许局部稿纸或列表内部滚动，不允许右侧整页再产生独立大滚动条。

### 6.2 小屏

- 390×844：页面允许纵向滚动；禁止为了“一个视口”把文字压到不可读。
- 章节表可以整体横向滚动；正文稿纸、弹窗表单保持单列。
- hover 动作不作为唯一交互，触屏使用点击选中。

### 6.3 侧栏

- 桌面侧栏固定在 shell 轨道，内部 `overflow-y: auto`，不依赖内容区滚动。
- 折叠按钮与项目标题保持 sticky；阶段列表和全局入口在同一内部滚动容器。
- 当前阶段只使用模式主色；完成/失败仍有文本或图标，不靠颜色单独表达。

## 7. 七阶段稿件栈

### 7.1 状态来源

- 未启动：选中用户当前配置阶段。
- 已启动：默认选中 SSE/Run State 的真实当前运行阶段；用户临时浏览其他卡后可回到当前阶段。
- `done/attention/running` 必须继续由 `stageDeliveryStatus` 推导，Cover/Export 不得被错误算作完成。

### 7.2 交互

- 单击：只选择卡并更新下方 Artifact/决策/写回/依赖说明。
- 双击：仅在 `runHasStarted` 且路由策略允许阶段详情时导航；配置态双击不进入运行页。
- 键盘：Arrow/Home/End 选择，Enter/Space 等价单击；提供可访问的“打开阶段”命令，不依赖双击。

### 7.3 3D 几何

- 所有卡上、下基线对齐，不因选中而上浮或改变堆叠顺序。
- 全部卡统一向右侧展示厚度：`rotationY > 0`、右侧纸层、右下投影。
- 选中只改变模式色边框、材质与轻微前移，不改变 x/y 布局。
- 命中层保持二维稳定盒；展示层承担 3D transform，避免 hover 抢夺。
- 3D context 父链不使用会强制 flatten 的 `filter`、非 1 `opacity` 或不兼容 overflow。

## 8. 组件边界

本轮优先复用和拆分现有边界，不新建顶层 `components/` 或 `dialogs/`：

- `layout/ModalBackdrop.tsx`：统一非 Radix 模态遮罩与关闭命中语义。
- `layout/AnimatedPresence.tsx` 或现有 `motion.ts`：统一 Tab/内容交叉淡入参数。
- `running/CoverCandidateRail.tsx`：只负责候选选择与状态，不管理大预览解码。
- `running/ChapterBlueprintDialog.tsx`：Shell 与章节稿纸分离，切章只替换稿纸。
- `running/StageInsightLinks.tsx`：按阶段显示精简摘要和 Story Bible 跳转。
- `planning/ArtifactDeck.tsx`：交互与 GSAP 生命周期。
- `planning/artifactDeckLayout.ts`：纯几何；不读取 React/路由状态。
- `state/`：当前运行阶段和临时浏览阶段选择规则。

正常源文件控制在 250 行左右；现有超过 300 行的模块不得继续叠加职责。

## 9. 原型生成合同

原型只定义视觉层级，不定义新业务。生成图必须使用上述真实中文字段，禁止 KPI、负责人、日历、虚构自动化按钮和不存在的后端数据。

统一提示词方向：

> Yotsuba Ink high-density cinematic writing workstation, 16:10 desktop, black crystal and smoked silver materials, one dynamic mode accent only, calm premium typography, no decorative particles. Show four coherent product surfaces in one design system: a Cover workspace with one large 2:3 cover preview and a stable compact candidate rail; a Detail chapter blueprint modal with fixed chapter rail and large manuscript fields; a Text workspace with dominant manuscript editor and compressed chapter/tension rail; a Planning seven-stage right-facing 3D manuscript deck with aligned baselines and visible paper thickness. Chinese labels must match real artifacts: 小说信息、全书梗概、分卷大纲、章节细纲、正文生成、AI 封面、导出; 人物关系、世界观、伏笔账本、正典事实 are compact navigation links, not large repeated panels. No cards inside cards, no SaaS KPI tiles, no gradients as decoration, no purple-and-green mixed accents, no fake data features.

## 10. 验收矩阵

### 自动化

- Cover 候选选择不会因 hover 触发反复 state change。
- 弹窗遮罩点击关闭；点击弹窗内部不关闭；底层按钮不可点击。
- 切章存在未保存修改时继续触发保护；无修改时切章不重建整个 Dialog。
- 运行态稿件栈默认选中真实 current stage；双击导航遵守路由权限。
- 各阶段 UI 只读取合同字段，字段缺失时显示明确空状态。

### 浏览器

- 1280×920、1440×900、1728×1100、390×844。
- Cover：快速 hover 20 次无闪烁、无卡片跳位、控制台无警告。
- Detail：连续切换 1/2/3 章无白闪、外壳尺寸不跳、焦点不落到底层。
- Modal：遮罩期间底层任何按钮都不能触发；非破坏性弹窗遮罩关闭可用。
- Info：桌面左右轨道同底线，简介稿纸面积大于任一辅助摘要。
- Text：无独占重复章节进度行；正文稿纸获得更多垂直空间。
- Sidebar：自身滚动，内容区滚动不带动侧栏；当前项始终可见。
- Planning：七张卡无遮挡越界，统一右向厚度；运行阶段默认选中并可双击进入。
- 所有页面水平溢出为 0，控制台 0 error / 0 warning。

## 11. 实施顺序

1. 统一 Overlay/Presence 基础设施，先消除穿透和卸载白闪。
2. 修封面候选轨和细纲切章，它们是当前最高频的视觉故障。
3. 收缩 Header/正文重复进度，重排 Info 与阶段辅助系统。
4. 侧栏独立滚动与模式底色统一。
5. 稿件栈状态来源、双击导航与 3D 几何收口。
6. 前后端字段检查、全量回归与四视口验收。

## 12. 不在本轮伪造的结论

- 未经明确成本授权，不调用付费文本 Provider 验证文学质量。
- 可以验证 Prompt 结构、上下文连续性、确定性质量门禁与回归快照；不能把这些等同于真实模型已经产出高质量小说。
- 原型图不作为后端合同，只有本文件第 3 节和 canonical stage artifact contract 定义业务事实。

## 13. 完成记录

### 13.1 已实现

- Cover 候选区使用稳定命中盒和独立视觉层，快速 hover 不再改变卡片位置或触发状态频闪。
- Detail 章节蓝图保留固定 Dialog 外壳、章节 rail 与 footer，切章只在稳定稿纸视口内交叉淡入；遮罩覆盖完整视口、锁定 body 滚动并阻断底层交互。
- Info、Summary、Outline、Detail、Text、Cover、Export 均按正式 Artifact 字段组织主体和辅助信息；长期记忆系统不再在每个阶段重复铺满。
- Text 专注模式已改为单列、全高正文工作区；审校模式使用固定宽度审校区和质量/写回面板，切换不再触发布局抖动。
- Planning 七阶段稿件栈的交互层与 3D 展示层分离，运行态跟随真实 current stage，并保留键盘、Reduced Motion 与移动端 2D 降级。
- Story Bible 人物关系 3D 画布获得独立可用区域，档案栏不覆盖画布，移动端不产生页面级横向溢出。
- Export 在移动端改为单列交付流；Cover 与 Text 在 Detail 后并行，Export 等待正文与封面两路就绪。
- 两份无有效消费者的旧样式已退役：`stage-run-artifact-workbench-v4.css`、`stage-run-detail-writeback-dialog.css`。

### 13.2 自动化验收

- 前端测试：`125 files / 492 passed`。
- 后端测试：使用仓库虚拟环境执行 `.venv/bin/pytest -q`，结果为 `293 passed / 1 skipped`；仅保留一条 Starlette/httpx 第三方弃用警告。
- 前端生产构建：通过，`3687 modules transformed`。
- CSS 审计：通过；`838,594 bytes`、`5,020 rules`、`4,442 unique selectors`、`74 keyframes`、`86 animation declarations`。
- CSS 分包：通过；首屏 CSS `35,612 bytes gzip`（`34.8 KiB`），115 个惰性入口样式文件未进入首屏。
- `graph-3d-vendor` 仍是约 `345.32 KiB gzip` 的惰性 3D 图谱包，不进入 Planning 首屏；它是后续性能专项，而非本轮正确性阻断项。

### 13.3 浏览器验收

- `390x844` 下七阶段页面页面级横向溢出均为 0；小屏允许必要的纵向和局部内部滚动。
- `1280x920` Text 专注工作区约为 `1016x742`，编辑器约为 `1014x740`，正文可读区约为 `1014x658`；点击首帧即为单列。
- Text 审校区连续切换 6 次保持约 `320x667`，质量审校/事实写回面板保持约 `319x512`。
- Detail 蓝图连续切章 6 次，Dialog 保持 `1080x721`，稿纸视口保持 `874x607`；遮罩为 `1280x920`，点击遮罩关闭且路由不变。
- Cover 候选快速 hover 20 次无卡片位置/尺寸变化，无控制台错误或警告。
- Story Bible 人物关系画布桌面约 `755x481`，移动端约 `360x318`；档案栏独立且无重叠。
- Summary 活动结构面板恢复为约 `462x334`，结构节拍/关键转折切换不跳高。

### 13.4 仍需发布前完成

- 使用用户明确授权并配置的真实文本 Provider，跑一条至少跨卷、跨章的完整创作链，人工评估章节承接、视角转换、倒叙标记、人物声音漂移和伏笔回收。
- 使用真实图片 Provider 验证 Cover 资产生成、失败重试、候选确认和 Export 打包；当前本地合同与 Mock/失败路径通过不等于真实供应商已验收。
- 为 `graph-3d-vendor` 制定独立加载性能预算；不以删减人物关系交互能力换取首屏数字。
