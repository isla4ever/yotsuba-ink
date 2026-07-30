# Phase 9.5C-1：Summary / Outline 运行期表单系统

> 状态：已完成并通过全量门禁验收
>
> 日期：2026-07-25
>
> 范围：仅 Summary 与 Outline 的当前稿编辑、结构化承接、换稿方向、草稿保护和响应式验收。Detail、Text、Cover、Export 继续留在后续 Phase 9.5C 批次。

## 1. 本批目标

Phase 9.5B 已收口 Settings、Provider 与阶段配置表单，本批开始处理运行期表单。目标不是把配置页样式机械复制到工作台，而是让每一个编辑动作都严格对应阶段 Artifact：

1. Summary 以完整梗概为主稿，结构节拍、关键转折、人物弧和叙事承诺分别进入有明确语义的编辑器。
2. Outline 以分卷 Beat Board 为主面，卷内五段节拍与人物、世界观、伏笔三类下游承接分开编辑。
3. 所有专用编辑器都明确“当前稿保存”与“正式定稿写回”的区别。
4. 必填、引用、唯一性与保存前 trim 在 UI 和后端合同中形成双层约束。
5. 未保存修改在关闭、Escape、切换对象与路由离开时得到保护，并恢复到发起操作的焦点。
6. 换稿方向只允许“一个预设方向”或“一个自定义方向”，不能同时提交两种语义。
7. 390px 窄屏不产生页面级横向滚动，节拍板的横向浏览留在工作台内部。

## 2. 产品决策

### 2.1 Artifact-first，而不是通用表单堆叠

Summary 和 Outline 没有共用一张万能大表单。每个编辑器围绕一个业务对象组织：

- Summary 主稿：`full_synopsis`。
- Summary 结构节拍：`act_structure[]`。
- Summary 关键转折：`key_turns[]`。
- Summary 人物深化：`character_arcs[]`，并引用 Info 已确认人物与关系。
- Summary 叙事承诺：`core_conflict`、`ending_resolution`、`consistency_checks[]`。
- Outline 卷内节拍：当前卷基础字段与 `opening / development / midpoint / climax / resolution`。
- Outline 人物承接：`character_progression[]`。
- Outline 世界观承接：`world_reveal[]`。
- Outline 伏笔账本：`foreshadow_plan[]`。

人物、世界观和伏笔不会混进卷纲节拍编辑器。三类数据的来源、验证和最终写回目标不同，合并只会让用户误判保存结果。

### 2.2 当前稿保存不等于正式写回

编辑器中的“保存到当前稿”只更新当前 Stage Artifact 草稿，并在工作台与右侧面板显示“定稿后写回”预览。它不会立即改写 Memory、Story Bible、人物图谱、世界观或伏笔账本。

只有阶段进入正式确定路径后才执行后端写回：

- Deep：用户确认定稿后写回。
- Fast / Balanced：阶段自动确定后走同一正式写回。
- 刷新、SSE 重连或服务恢复只补齐尚未提交的正式写回；Artifact 签名相同则幂等跳过。

### 2.3 密度与布局

- Summary 主稿占据主要高度，结构与人物深化是支持面，不与主稿争夺视觉优先级。
- Outline 使用卷导航、节奏曲线、五段节拍板和三条下游承接带，不用通用 Card 瀑布。
- 桌面保留高密度工作台；移动端只把必要区域改为单列或内部横向浏览。
- 动画只用于弹窗进入、离开和状态反馈，不加入持续背景动效。

## 3. Summary Artifact 合同

| 字段 | 用户语义 | 前端完整性 | 保存处理 | 下游用途 |
| --- | --- | --- | --- | --- |
| `one_liner` | 一句话故事核心 | trim 后非空 | 当前稿直接更新 | 阶段定位摘要 |
| `full_synopsis` | 覆盖完整推进与结局的全书梗概 | trim 后非空 | 主稿编辑器更新 | Outline 主上下文 |
| `act_structure[]` | 结构节点 | 至少 1 项；`title/goal/turn` 必填 | 三字段 trim | 节拍与分卷规划 |
| `core_conflict` | 主线冲突与阻力系统 | 必填 | trim | 大纲冲突约束 |
| `character_arcs[]` | 人物弧、关系压力与后续影响 | 至少 1 项；字段完整；人物来自 Info | 字段 trim | 人物图谱与 Outline 初值 |
| `key_turns[]` | 关键转折 | 至少 1 项；`label/detail` 必填 | 字段 trim | Outline 转折约束 |
| `ending_resolution` | 结局承诺 | 必填 | trim | 后续阶段结局边界 |
| `consistency_checks[]` | 与人物、世界观和物证的对齐结果 | 至少 1 条有效内容 | 按行 trim、去空行 | 质量与连续性检查 |

### 3.1 Summary 编辑器边界

- `SummaryManuscriptPane` 负责阅读态、流式生成态与主稿编辑态，不重复渲染两份完整梗概。
- `SummaryMiniEditDialog` 分别编辑单个结构节拍或单个关键转折，并在原数组位置替换。
- `CharacterArcDeepeningDialog` 先展示 Info 人物与关系基线，再编辑人物弧、压力和后续影响。
- `SummaryCommitmentDialog` 只编辑冲突、结局和一致性检查，不承担结构或人物字段。
- `summaryReadiness` 汇总 8 个合同区，不完整时 Deep 定稿不可放行。

## 4. Outline Artifact 合同

### 4.1 卷基础与节拍

每卷必须提供：

- `title`
- `chapter_range`
- `volume_goal`
- `rhythm`
- `opening`
- `development`
- `midpoint`
- `climax`
- `resolution`

卷内编辑器只维护这些结构字段。兼容字段 `mid_twist` 和 `volume_cliffhanger` 仍由保存映射维护，但界面不把兼容字段作为第二套用户语义。

### 4.2 人物承接

固定结构：

```ts
type OutlineCharacterProgression = {
  character: string;
  related_to: string;
  relation: string;
  pressure: string;
  change: string;
  impact: string;
};
```

规则：

- `character` 与 `related_to` 必须来自 Info 已确认人物。
- 两个人物不得相同。
- 同一卷内，同一无向关系只能存在一条。
- `relation / pressure / change / impact` 全部必填并在保存前 trim。
- 已存在关系按原数组位置替换；只有新关系才追加。
- 关系 key 对两端名称 trim 后排序，避免“甲/乙”和“乙/甲”被当成两条关系。

### 4.3 世界观承接

固定结构：

```ts
type OutlineWorldReveal = {
  anchor: string;
  reveal: string;
  rule: string;
  impact: string;
};
```

规则：

- `anchor` 必须是 Info `worldbuilding_detail` 中可以精确引用的原文锚点。
- `reveal / rule / impact` 全部必填并在保存前 trim。
- 已存在锚点按原数组位置替换；只有新锚点才追加。
- 前端只展示已确认锚点；后端仍再次验证锚点属于 Info 世界观。

### 4.4 伏笔账本

固定结构：

```ts
type OutlineForeshadow = {
  name: string;
  status: '投放' | '推进' | '回收' | '延后';
  chapter_range: string;
  note: string;
};
```

规则：

- 每卷至少一条伏笔。
- 四个字段全部必填。
- `status` 只能使用四个受控值。
- 同卷 `name.trim()` 不得重复。
- 保存时 `name / chapter_range / note` 统一 trim，空行或只含空格的值不能通过。

### 4.5 Outline 完整度

每卷聚合为 5 个可理解检查区：

1. 基础信息。
2. 五段节拍。
3. 人物承接。
4. 世界观揭示。
5. 伏笔账本。

前端 `outlineReadiness` 负责即时反馈；后端 `OutlineContract` 和 `outline_reference_errors` 再次执行结构、引用与唯一性验证。前端完成度不是绕过后端审批的凭证。

## 5. 原位替换与顺序稳定

本批修复了人物承接和世界观承接编辑后的顺序漂移。

原规则通过“过滤旧项再追加新项”保存，编辑数组中间条目时会把它移动到末尾，导致工作台预览与用户心智顺序变化。现规则由 `outlineDependencyDrafts.ts` 统一处理：

- 找到匹配项时用 `map` 在原 index 替换。
- 找不到匹配项时才在数组末尾追加。
- 人物关系按无向关系 key 匹配。
- 世界观按精确 `anchor` 匹配。

对应测试覆盖：人物原位替换、世界观原位替换、真正新增时追加。

## 6. 未保存草稿保护

Summary 与 Outline 专用弹窗统一使用 `useUnsavedDraftGuard`：

- `dirty` 由初始结构与当前结构的深比较产生。
- 只读预览不触发放弃确认。
- 关闭按钮、Backdrop、Escape、对象切换和路由离开都进入同一保护路径。
- 对象切换时确认文案显示目标对象，避免用户不知道即将切换到哪里。
- “继续编辑”关闭确认层并把焦点恢复到原字段。
- “放弃修改”执行原关闭或切换动作，并把焦点恢复到原入口。
- dirty 期间注册 `beforeunload`，防止浏览器刷新静默丢稿。

确认层使用独立 `alertdialog`，原编辑弹窗在其打开期间暂停 Escape 处理，避免一次按键关闭两层。

## 7. 换稿方向互斥

`DraftRegenerationDialog` 始终展示 3 个阶段相关预设方向和 1 个自定义方向输入，但提交时只有一个来源：

- 选择预设方向：清空自定义内容。
- 输入或聚焦自定义方向：取消全部预设 Radio。
- 自定义内容只含空格时不可提交。
- 每次重新打开弹窗时恢复第一条预设并清空旧自定义草稿。
- 点击“按方向重生成”才调用候选生成；打开、选择或输入本身不触发请求。

该交互保持“换一稿”和平衡模式“版本对比”两条合同分离。

## 8. 正式写回时机与目标

Outline 正式确定后，后端按 Artifact 签名执行一次写回：

| 数据 | 正式目标 | 行为 |
| --- | --- | --- |
| 完整 Outline Artifact | Memory / Wiki refs | 按节点 memory policy 写入 |
| 卷与结构结果 | Story Bible | 更新分卷信息 |
| `character_progression[]` | 人物图谱、人物档案、关系边 | 更新压力状态、卷内 progression，必要时新增关系边 |
| `world_reveal[]` | Worldbuilding、Story Bible 世界规则 | 写入卷揭示并合并硬规则 |
| `foreshadow_plan[]` | Story Bible 伏笔账本、运行伏笔账本 | 用 Outline 来源替换旧条目并限制账本长度 |
| 最终状态 | Wiki state、continuity state | 重算正式运行状态 |

相同 Artifact 签名已存在 `committed` 标记时不重复执行，避免刷新或 SSE 重连重复写 Memory。

## 9. 响应式与交互验收

### 9.1 Mobile 390 x 844

- 页面级横向溢出：`0`。
- 分卷节奏条和五段 Beat Board 的横向滚动限制在各自内部。
- 水平滚轮作用于 Beat Board 时，节拍板 `scrollLeft` 从 `0` 前进到 `480`，页面 `scrollX` 仍为 `0`。
- 卷纲弹窗：`x=12`、`right=378`、`bottom=723.09`，完整位于视口内。
- 人物承接弹窗：`x=28`、`right=362`、`bottom=827.14`，完整位于视口内。
- 世界观承接弹窗：`x=28`、`right=362`、`bottom=826.87`，完整位于视口内。
- 伏笔账本弹窗：`x=28`、`right=362`、`bottom=698.22`，完整位于视口内。
- 四类弹窗均完成 Escape、未保存确认、继续编辑焦点恢复、放弃修改入口焦点恢复。
- 输入控件可以有自身文本滚动，但没有第二个抢夺页面操作的弹窗级纵向滚动区。

### 9.2 Desktop 1440 x 1000

- 页面与 Body 横向溢出均为 `0`。
- 主稿区、五段节拍板和右侧人物 / 世界观 / 质量面板没有重叠或裁切。
- 最终截图：`output/playwright/phase95c1/outline-1440x1000.png`。
- Summary 截图：`output/playwright/phase95c1/summary-1440x1000.png`、`summary-390x844.png`。
- Outline 移动截图：`output/playwright/phase95c1/outline-390x844.png`。
- 换稿方向截图：`output/playwright/phase95c1/summary-regeneration-390x844.png`。

### 9.3 Console 与请求

- Browser Console：0 Error、0 Warning。
- 历史加载、Run 恢复、Workflow、Knowledge 与 Provider Readiness 请求均返回 200。
- 验收导航期间一条历史列表请求被后续同路径请求主动取消，随后同请求返回 200；不属于 Provider、审批或写回失败。

## 10. Header 临时镜像边界

历史恢复的临时验收镜像可能同时展示“已完成 / 继续创作”和工作台内“等待人工定稿”。本批把它记录为临时运行镜像的展示矛盾，不扩大为 Header、SSE 或运行状态机重构，原因如下：

- 当前任务只验证 Summary / Outline 运行期表单与 Artifact 写回边界。
- 弹窗、草稿、当前稿和正式写回逻辑不依赖该 Header 文案。
- 在临时镜像上修改 SSE 或状态机，会让验收夹具问题污染正式运行合同。

后续应使用真实新 Run 单独复现，只有事实源确实不一致时才进入运行状态专项。

## 11. 不变合同与延期项

- 未修改 Provider 模板、Provider 生命周期或计费行为。
- 未修改 SSE 事件类型、Artifact 字段协议或 Run 状态机。
- 未把当前稿保存改成正式 Canon / Memory 写回。
- 未新增 UI 或动效依赖。
- 未新增 `components/`、`dialogs/`、`screens/` 等平行目录。
- 保留 Mock / Demo 路径，在真实 Provider 不可用时仍可完成产品演示与回归。
- Detail、Text、Cover、Export 的运行期表单不在本批宣称完成。

## 12. 最终门禁

本批已执行：

```bash
cd apps/web
npm test -- --run
npm run build
npm run audit:css -- --update-baseline
npm run audit:css
cd ../..
git diff --check
```

最终结果：

- 前端全量测试：66 个测试文件、223 项测试全部通过。
- Outline 顺序回归：3 项聚焦测试通过，覆盖人物原位替换、世界观原位替换和新增追加。
- TypeScript 与 Vite 生产构建通过，共转换 3520 个模块。
- CSS 审计基线在视觉复核后更新，随后审计通过。
- `git diff --check` 通过。
- Browser Console：0 Error、0 Warning。
- 1440 x 1000 与 390 x 844 实机浏览器验收通过。
- 临时 Summary / Outline 验收 Run 镜像与错误尺寸截图已删除。
