# Phase 9.5C-2：Detail 运行期表单系统

> 状态：已完成并通过全量门禁验收
>
> 日期：2026-07-25
>
> 范围：仅章节细纲的章节施工表、章节蓝图、人物变化、事实 / Wiki、伏笔账本、当前稿保护和正式写回合同。Text、Cover、Export 继续留在后续批次。

## 1. 本批目标

Phase 9.5C-1 已完成 Summary / Outline 运行期表单。本批沿用 Artifact-first 原则，但不把上一批表单机械复制到 Detail，而是围绕“逐章施工”完成闭环：

1. 章节表承担全书细纲扫描与选章，不把每章扩张为大 Card。
2. 章节蓝图只回答“本章怎么写”，不混入人物、事实、Wiki 和伏笔的正式写回语义。
3. 人物变化、事实 / Wiki、伏笔使用三个独立编辑器，分别对应不同来源、校验和系统目标。
4. 四类编辑器在保存前统一 trim，并执行必填、唯一性、受控值与引用合法性检查。
5. 前端即时校验与后端最终合同形成双层防御，不能依赖前端完成度绕过正式审批。
6. 未保存修改在关闭、Backdrop、Escape、章节切换和路由离开时得到保护；“继续编辑”回到原字段且确认层不会竞态重开。
7. 当前稿与生成 / 候选来源绑定，来源变化后旧稿和右侧写回预览一起失效。
8. 390px 窄屏保持页面零横向溢出，章节表只在内部横向滚动，弹窗只保留一个纵向滚动区。

## 2. 阶段产品合同

| 合同问题 | Detail 决策 |
| --- | --- |
| Artifact | `chapters[]`，每章包含九项蓝图字段、`character_shift`、`fact_reveals[]`、`wiki_candidates[]`、`foreshadow[]` |
| 用户决策 | 每章是否具备可执行场景、明确冲突与正文交接；人物、事实和线索变化是否准确 |
| 当前稿目标 | 更新与当前来源绑定的完整 Detail Stage Artifact，并刷新章节表、上下文账本和侧栏预览 |
| 正式写回目标 | Memory、Story Bible、人物图谱、世界观、Wiki 候选、伏笔账本与连续性状态 |
| 下一阶段依赖 | Text 的 `ChapterContextPacket.chapter_outline` 按章节索引读取结构化蓝图、事实、人物变化、伏笔与连续性备注 |

本阶段不是运行日志页，也不是通用 Memory 编辑器。SSE 只补充当前章节状态和短预览，不能把生成过程写进最终 Artifact。

## 3. 信息架构与组件边界

### 3.1 主工作台

- `DetailContextBar`：当前章节、正文交接、事实 / Wiki 数量、伏笔数量和合同完整度。
- `DetailConstructionTable`：高密度章节施工表；桌面完整展示，移动端整表内部横向滚动。
- `DetailChapterLedger`：当前章节的正文交接与三类写回入口；入口明确显示“定稿后写回”。
- `DetailStageView`：只负责选章、打开专用编辑器、更新完整当前稿和显示轻量保存反馈。

### 3.2 四类编辑器

- `ChapterBlueprintDialog`：九项章节施工字段。
- `DetailCharacterShiftDialog`：一章的人物状态与可选关系变化。
- `DetailWorldWikiDialog`：事实揭示和 Wiki 候选两组结构记录。
- `DetailForeshadowDialog`：一章的伏笔动作 ledger。
- `DetailWritebackDialogShell`：三类写回弹窗共享的全局遮罩、章节 Rail、单一滚动体和稳定 Footer。
- `DetailWritebackFields`：共享字段、行操作和错误呈现原语，不承载业务保存或正式写回。

不存在统一的 `DetailWritebackHubDialog`。人物、事实 / Wiki、伏笔不能合并成一个 Tab Hub，因为它们的引用源、错误恢复和最终目标不同。

## 4. 四类字段与校验矩阵

### 4.1 章节蓝图

| 字段 | 用户语义 | 前端规则 | 下游 |
| --- | --- | --- | --- |
| `chapter` | 章节名称 | trim 后必填；全书唯一 | 章节索引与正文导航 |
| `pov` | 视角人物 | 必须选择 Info 已确认人物 | Text 视角与人物上下文 |
| `scene` | 主要场景 | trim 后必填 | 场景定位 |
| `entry_state` | 场景进入状态 | trim 后必填 | 开章状态 |
| `goal` | 章节行动目标 | trim 后必填 | 正文推进目标 |
| `conflict` | 核心冲突 | trim 后必填 | 戏剧引擎 |
| `stakes` | 失败代价 | trim 后必填 | 风险与质量检查 |
| `hook` | 章末钩子 | trim 后必填 | 章节收束与下一章衔接 |
| `continuity_notes` | 正文交接与连续性 | trim 后必填 | Text Context Packet |

蓝图弹窗按场景设置、戏剧推进和正文交接组织，不显示内部字段名或原始 JSON。保存时仍映射回稳定字段对象。

### 4.2 人物变化

```ts
type DetailCharacterShift = {
  character: string;
  related_to: string;
  relation: string;
  pressure: string;
  motivation: string;
  change: string;
  impact: string;
};
```

规则：

- `character` 必须引用 Info 已确认人物。
- `related_to` 与 `relation` 必须同时填写或同时留空。
- 关系对象存在时必须引用已确认人物，且不能与 `character` 相同。
- `pressure / motivation / change / impact` 全部必填。
- 所有文本在保存前 trim；只含空格不能通过。
- 当前稿预览可以投影到人物图谱，但只有阶段正式确定后才更新正式人物档案和关系边。

### 4.3 事实揭示与 Wiki 候选

```ts
type DetailFactReveal = {
  anchor: string;
  fact: string;
  impact: string;
};

type DetailWikiCandidate = {
  title: string;
  fact: string;
  source_anchor: string;
};
```

规则：

- 每章至少一条事实揭示和一条 Wiki 候选。
- `anchor` 与 `source_anchor` 必须来自 Info 世界观原文或已确认 Outline `world_reveal[].anchor`。
- 事实行的 `fact / impact` 必填；Wiki 行的 `title / fact` 必填。
- 同章事实文本不得重复；同章 Wiki 标题不得重复。
- 添加、删除和编辑都保留结构数组，不允许退化为多行自由文本。
- 当前稿只显示世界观 / Wiki 写回预览，不立即创建正式 Wiki 或 Canon 事实。

### 4.4 伏笔账本

```ts
type DetailForeshadow = {
  name: string;
  status: '投放' | '推进' | '回收' | '延后';
  note: string;
};
```

规则：

- 每章至少一条伏笔动作。
- `name / note` trim 后必填。
- `status` 只允许四个受控值。
- 同章 `name.trim()` 不得重复。
- 可以承接 Outline 伏笔，也允许 Detail 创建新线索；正式写回时通过 `source_kind` 区分来源。

## 5. 错误呈现与首错聚焦

四类编辑器共享以下错误合同：

1. 保存时先生成 trim 后的候选值，不把脏空格写回当前稿。
2. 错误写入稳定字段 key，例如 `fact_reveals.0.fact`。
3. 控件设置 `aria-invalid` 和与字段对应的 `aria-describedby`。
4. 弹窗顶部或 Footer 显示错误数量，但不以汇总信息替代字段级错误。
5. 保存失败后按 DOM 顺序聚焦第一个 `[data-detail-field]` 错误控件。
6. 用户修正后再次保存，完整 trim 后对象一次性更新当前稿。

已覆盖的真实浏览器错误包括：蓝图空字段、重复章节名、人物关系配对、重复事实、重复 Wiki 标题和重复伏笔名称。

## 6. 当前稿、来源签名与正式写回

### 6.1 来源绑定

`StageRunWorkbench` 为每个阶段保存：

```ts
type StageArtifactDraft = {
  source: string;
  value: string;
};
```

只有 `draft.source === currentSource` 时才使用本地当前稿。重新生成、选择候选或事件恢复产生新来源后，旧稿不能覆盖新稿，旧的章节表、人物投影和写回摘要也不再参与页面派生。

### 6.2 当前稿保存

“保存到当前稿”只执行：

- 更新当前章节对应结构字段。
- 把完整 Detail Artifact 回传给阶段草稿状态。
- 刷新章节施工表、上下文账本和右侧“定稿后写回”预览。
- 显示短暂、可读的保存反馈。

它不执行 Memory、Story Bible、人物图谱、世界观、Wiki、Canon 或伏笔账本的正式写回。

### 6.3 正式确定与幂等提交

- Deep：用户确认定稿后提交完整当前稿。
- Fast / Balanced：阶段自动确定后调用同一最终提交函数。
- pending、confirmed、completed 与恢复路径统一补齐 Detail 最终写回。
- 后端在写回前再次执行结构合同和引用校验。
- 最终 Artifact 计算稳定签名；`detail_confirmed_writeback` 已记录相同签名时幂等跳过。

正式写回结果：

| 数据 | 正式目标 | 行为 |
| --- | --- | --- |
| 完整 Detail Artifact | Memory / Wiki refs | 按节点 memory policy 写入一次 |
| 章节、场景、目标、钩子、连续性 | Story Bible timeline | 按 Detail 来源替换章节时间线 |
| `character_shift` | 人物档案与人物图谱 | 更新状态、Detail shifts 和可选关系边 |
| `fact_reveals` | Worldbuilding | 写入章节事实 |
| `wiki_candidates` | Wiki 候选展示层 | 保存章节、来源和候选事实 |
| `foreshadow` | Story Bible / 运行伏笔账本 | 按章节稳定 ID 写入，并标记 Outline 或 Detail 来源 |
| 最终状态 | Wiki state / continuity state | 在写回完成后重算 |

## 7. 前后端双层合同

### 7.1 前端即时层

- `detailDraftValidation.ts`：四类编辑器保存校验、trim、唯一性和引用检查。
- `detailArtifactModel.ts`：全阶段 5 项 / 章完整度；3 章夹具总计 `15/15`。
- `detailValidationFocus.ts`：字段错误 ID 与首错聚焦。
- `detailWritebackRows.ts`：结构行的稳定新增、删除和更新。

### 7.2 后端最终层

- `DetailOutlineContract`：至少一章；九项蓝图必填；人物、事实、Wiki、伏笔对象结构固定；三个数组至少一项。
- Pydantic 合同统一 strip 文本，拒绝重复章节、重复事实、重复 Wiki 标题和重复伏笔名称。
- `detail_reference_errors` 再次验证 Info 人物、世界观锚点、关系配对、人物自引用和同章唯一性。
- `commit_detail_writebacks` 在任何正式持久化前调用引用校验，错误时不写 Memory、人物图谱、世界观或伏笔账本。

前端完成度只负责即时可用性，不是后端审批凭证。

## 8. 未保存草稿保护与焦点恢复

四类编辑器统一使用 `useUnsavedDraftGuard`：

- 初始结构与当前结构深比较产生 `dirty`。
- 只读快照不触发放弃确认。
- 关闭按钮、Backdrop、Escape、章节切换和 React Router 路由离开进入同一保护逻辑。
- dirty 期间注册 `beforeunload`，防止刷新静默丢稿。
- `alertdialog` 打开时暂停原弹窗 Escape，避免一次按键关闭两层。
- “放弃修改”执行原关闭、切章或导航动作。
- “继续编辑”取消原动作，并通过字段元素、`data-detail-field`、id、name 或 aria-label 恢复原编辑焦点。

本批最终烟测发现并修复了路由阻断竞态：`blocker.reset()` 与 `intent=null` 同周期时，旧 blocked 状态曾重新创建确认层。现由一次性 dismissal 标记抑制旧状态，等 blocker 回到 `unblocked` 后再解除。浏览器复测确认：确认层数量为 `0`，焦点恢复到 `data-detail-field="scene"`，编辑值未丢失。

## 9. 响应式与浏览器验收

### 9.1 Mobile 390 x 844

- 页面级横向溢出：`0`。
- 章节施工表：可视宽 `364px`，内部滚动宽 `860px`；页面本身不横向移动。
- 章节蓝图：`x=12, y=12, width=366, height=820`，完整位于视口内。
- 蓝图唯一纵向滚动体：`clientHeight=669`、`scrollHeight=1344`。
- 蓝图章节 Rail：横向滚动、纵向隐藏；稿纸本身不创建第二纵向滚动区。
- 人物变化弹窗：`x=12, y=12, width=366, height=820`；内容 `668/868px`。
- 事实 / Wiki 弹窗：`x=12, y=12, width=366, height=820`；内容 `668/891px`。
- 伏笔弹窗：`x=12, y=119, width=366, height=606`；内容 `454/454px`，内容不足一屏时不制造无意义滚动。
- 四类弹窗 Footer 稳定可见，保存按钮、错误状态和关闭入口没有重叠。

### 9.2 Desktop 1440 x 1000

- 页面级横向溢出：`0`。
- 章节表可视宽与滚动宽均为 `1042px`，无需桌面横向滚动。
- 主工作台、章节账本和右侧运行洞察没有重叠或裁切。

### 9.3 截图与控制台

- `output/playwright/phase95c2/detail-1440x1000.png`
- `output/playwright/phase95c2/detail-390x844.png`
- `output/playwright/phase95c2/detail-blueprint-390x844.png`
- `output/playwright/phase95c2/detail-blueprint-validation-390x844.png`
- `output/playwright/phase95c2/detail-world-wiki-390x844.png`
- 全新页面 Console：`0 Error / 0 Warning`。

## 10. 样式所有权与视觉决策

- 章节蓝图样式归 `stage-run-detail-blueprint.css`，不由写回弹窗文件跨域覆盖。
- 三类写回弹窗共享布局样式，但业务内容仍由三个独立组件负责。
- 工作台使用表格、稿纸、章节 Rail 和 ledger，不用通用 Card 瀑布。
- Hover、Focus、Error 和模式主色服务于状态辨识；不引入持续 Glow、粒子或大面积装饰动画。
- 弹窗使用短 Fade / Scale 过渡并遵守 Reduced Motion，不新增 GSAP 或其他运行依赖。
- CSS 审计在样式归位后，跨文件重复选择器由 `546` 降至 `538`，当前重复出现次数为 `1639`。

## 11. 不变合同与延期项

- 未修改 Provider 模板、Provider 生命周期、模型调用或计费行为。
- 未修改 SSE 事件、Run 状态机或 Header 事实源。
- 未把当前稿保存改成正式 Memory / Wiki / Canon 写回。
- 未新增 UI 或动效依赖。
- 未新增 `components/`、`dialogs/`、`screens/` 等平行目录。
- 保留 Mock / Demo 路径，真实 Provider 不可用时仍可完成结构化演示和回归。
- Text、Cover、Export 运行期表单未在本批宣称完成。

## 12. 最终门禁

本批执行：

```bash
cd apps/web
npm test
npm run build
npm run audit:css
cd ../..
.venv/bin/python -m pytest -q
git diff --check
```

最终结果：

- 前端全量测试：67 个测试文件、229 项测试全部通过。
- 后端全量测试：207 项通过、1 项跳过。
- TypeScript 与 Vite 生产构建通过，共转换 3522 个模块。
- CSS 审计通过；重复选择器基线没有回退。
- `git diff --check` 通过。
- 1440 x 1000 与 390 x 844 真实浏览器验收通过。
- 全新页面 Console：0 Error、0 Warning。
- 临时 Detail 验收 Run 与 `/tmp/phase95c2-run.json` 已删除；验收截图保留。

## 13. 下一阶段入口

下一批应进入 Text 运行期表单 / 编辑闭环，优先审查正文稿纸、章节导航、局部修订、版本恢复、摘要同步、质量复检和写回提案。该工作必须继续遵守 Text Artifact、UTF-16 选区、双签名并发保护和正式 Canon 冲突决策合同，不在本批顺带实施。
