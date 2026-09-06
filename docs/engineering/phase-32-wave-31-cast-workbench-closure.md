# Phase 32 Wave 31：Cast 人物圣经专业工作台闭环

状态：**三条 Phase 32 路线共用的 `CharacterBibleAggregate` 已完成正式 Artifact 读取、
source-bound 草稿、关系编辑、定稿物化、committed 只读、3D 确定性投影、Monitor 与 Version 20
三视口验收；本轮没有调用真实 Provider**

日期：2026-08-23

## 产品决定

Cast 继续是正文或剧本前唯一具名主体注册表。本切片只允许作者修改人物文学字段、行动限制与
已登记人物之间的有向关系：

```text
pending CharacterBibleAggregate candidate
  -> schema-specific Cast workbench
  -> source-bound aggregate draft
  -> draft_ref
  -> LangGraph decision resume
  -> immutable committed CharacterBibleAggregate
  -> route-specific downstream stages
```

人物集合和 `subject_ref` 在候选进入作者决策时冻结。草稿不能新增、删除或替换人物身份；新增
关系的两个端点必须引用同一聚合中已登记的 `subject_ref`。3D 节点坐标、相机、缩放和拖拽状态
均为可重建 UI 投影，不进入 Character Artifact，也不获得 Canon/Wiki 写权限。

## 后端身份与草稿边界

- 剧本样片、短中篇和长篇路线均开放 Cast source-bound draft；
- 保存前校验 Run、decision、domain revision、source Artifact、Schema 与路线身份；
- 允许修改人物文学字段、行动限制和关系文学字段；
- 允许增删关系，但关系端点只能来自冻结人物集合；
- 拒绝增删人物、替换 `subject_ref`、重复身份或悬空关系端点；
- `accept + draft_ref` 继续走同一 Artifact materialization、decision receipt、LangGraph resume 和
  committed Store，不建立 Cast 专用第二提交路径。

## Version 20 工作台

- 桌面人物二级侧栏固定 `272px`，人物行按真实内容高度排列，不拉伸铺满；
- 主区使用紧凑人物档案，不暴露 JSON：人物身份、路线化职责、欲望、失败代价/台面利害、
  行动限制、声音和弧线范围直接编辑；
- 关系编辑显示方向、稳定 ref、当前压力和未来变化触发；关系 composer 只列出尚未连接的已登记
  人物；
- Inspector 显示冻结人物数、全聚合有向关系数、当前人物连接数、身份冻结、投影边界、下游
  使用与孤立人物检查；
- 三条路线使用同一个 Aggregate 和编辑器，但文案分别对应 `Beat Board`、`Section Plan`、
  `Volumes / Rolling Detail`，没有把旧 mode 或固定八阶段重新塞回 UI；
- 650ms 自动保存、刷新恢复、ReviewPolicy 允许时的定向换稿、`Esc` 关闭、定稿和 committed
  只读均复用 Phase 32 正式链路；
- 3D 图谱使用确定性人物/关系投影，提供缩放、适配、节点选择、邻域高亮与 WebGL 不可用降级。

## 浏览器发现与底层修复

首次移动端 3D 验收没有页面级 `documentElement` 溢出，但画布只显示桌面图谱左半部分；点击右侧
相机控件后，Cast 内部工作区横向滚动到 `260px`。

最低责任层不是相机公式，而是 `CharacterGraph3D` 首帧把画布初始化为 `720px`。这个宽度反向
撑开移动工作区，`ResizeObserver` 又读取被画布撑大的 `720px`，形成无法收缩的测量循环。修复
包括：

1. 首帧画布使用不超过窄视口的 `300px` 安全宽度，再由容器测量接管真实尺寸；
2. 3D graph 与 canvas 容器明确拥有 overflow 边界；
3. 移动 Cast 页面只允许纵向滚动，横向人物名册仍在自己的 rail 内独立滚动。

修复后 `390x844` 的真实 canvas 为 `385x458`，五个人物全部进入视口；缩放后 Cast 页面保持
`clientWidth=385 / scrollWidth=385 / scrollLeft=0`。移动图谱截图裁剪区包含 `4,489` 种颜色，
非背景像素比例 `6.28%`；桌面图谱裁剪区包含 `8,389` 种颜色，非背景像素比例 `3.31%`，两处
WebGL 画布均非空。

## Fake Run 正式链路证据

隔离数据根中的三条新鲜 Run：

```text
p32-cast-browser-screenplay_sample
p32-cast-browser-short_novel
p32-cast-browser-long_novel
```

对应 Project：

```text
p32-cast-project-screenplay_sample
p32-cast-project-short_novel
p32-cast-project-long_novel
```

短中篇浏览器完成：

1. 读取 5 位冻结人物与 6 条有向关系，修改“玛雅”的可观察欲望；
2. 页面显示“草稿已保存”，刷新后恢复同一服务端草稿；
3. 定向换稿弹窗展示三条 Cast 专属建议，`Esc` 关闭，未真正换稿；
4. 3D 图谱非空，缩放/适配按钮可用，桌面点击“玛雅”后出现选中人物标签；
5. 新增 `maya -> chen-ke`，填写关系压力与变化触发；刷新后关系数保持 7、当前人物连接数保持 4；
6. 定稿后 Artifact 标记为 `Committed Artifact`，所有 textarea 为 `readOnly`，关系新增/删除入口
   消失，作者修改与新增关系保留；
7. 冻结 ReviewPolicy 随后自动继续到 Export，浏览器使用后端返回的 `/run/export`，没有由 Cast
   组件猜测下一阶段。该行为只证明导航和自动继续，不代表中间未迁移工作台已经完成专业验收。

剧本样片保持 Cast 人工决策并正确显示 `SCREENPLAY SAMPLE` 与 `Beat Board` 下游语义；长篇保持
Cast 人工决策并正确显示 `LONG NOVEL`、Book/Part scope 与 `Volumes / Rolling Detail` 下游语义。

## Monitor 与浏览器证据

长篇 Cast Monitor 显示：

- route-aware 8 阶段 rail，Cast 为 `待决策 · 当前`，后续阶段锁定；
- 当前创作内容、candidate ref、Cast 三条阶段事件和全 Run 最近 `6/14` 条日志；
- `3/3` Fake Provider operations、0 合同拒绝、0 失败/等待；
- checkpoint、definition digest、`r2 · 长篇小说` 与 fixture Provider/model；
- Project 主侧栏隐藏，保留 Monitor 专注布局。

隔离环境：API `127.0.0.1:8788`，Vite `127.0.0.1:5177`；用户自己的 `5176` 全程保持原进程。
`1440x920`、`1024x700`、`390x844` 均满足
`documentElement.scrollWidth === clientWidth`；移动 3D 内部工作区同样无横向滚动。控制台
`0 error / 0 warning`。

截图：

- `output/playwright/wave32-31-cast/cast-short-1440x920-committed.png`
- `output/playwright/wave32-31-cast/cast-short-3d-1440x920-final.png`
- `output/playwright/wave32-31-cast/cast-long-1024x700-final.png`
- `output/playwright/wave32-31-cast/cast-screenplay-390x844.png`
- `output/playwright/wave32-31-cast/cast-screenplay-3d-390x844-root-fixed.png`
- `output/playwright/wave32-31-cast/monitor-long-cast-1440x920.png`

## 测试与审计

- 后端全量：`1027 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`28 files / 76 tests passed`；
- TypeScript 与 Vite production build：通过；3D graph 保持独立动态 chunk；
- frontend structure audit：`133` 个 TypeScript source files，通过；
- CSS audit：`crossFileDuplicateSelectorCount=0`、`duplicateKeyframeNameCount=0`，通过；
- CSS build check：首屏 CSS `31.0 KiB gzip`，通过；
- Python `compileall`、目标 `oxfmt --check`、`git diff --check` 与 production closure audit：通过；
- closure audit 未发现 runtime legacy marker 或异常 pipeline 顶层目录。

production build 仍报告主入口和独立 Character Graph 3D 大 chunk warning。3D chunk 只有打开图谱
才动态加载，本切片没有把它并入首屏；该证据不等于 120 人或低端设备性能规模门完成。

## 闭环审计分类

- **已补行为**：三路线 Cast 专业编辑、服务端草稿恢复、关系增删改、定稿/只读、路线文案、
  3D 确定性投影和 Monitor 内容；
- **已修错误**：移动 3D 首帧 `720px` 画布不再反向撑宽容器和触发内部横向滚动；
- **未证明行为**：真实 Provider 的人物质量、关系可信度、真实成本、文学连续性、120 人性能和
  自动 axe 无障碍门；
- **仍缺行为**：post-commit Character amendment/impact、主体新增/归档的稳定 ref 分配、作者协作
  source-bound patch；
- **历史/旧路径**：旧 Cast UI/CSS 已由新正向路径替代；历史 Run 仍保持只读、零 Provider。

## 未闭合边界

本切片只关闭 Cast 候选到 committed 工作台，不代表 Wave 32.6 或 Phase 32 整体完成：

1. Volumes、Rolling Detail、Section Plan、Beat Board、Scene Deck、Text、Script、Cover 与 Export
   仍未全部迁移为 Phase 32 专业工作台；
2. committed Character amendment、dependency/impact 与三路线作者协作仍未接入；
3. 自动无障碍门和 120 人图谱性能 fixture 尚未完成；
4. 本轮没有调用真实 Provider，不能证明人物文学质量、真实成本、长链恢复或最终交付；
5. README、CHANGELOG、commit 和 push 继续等待三路线完整证据包。

下一切片应迁移长篇 `VolumeArchitectureAggregate` 专业工作台，保持卷聚合一次提交、稳定 Volume
refs、Book/Part 引用与人物 scope 边界；不能把旧 Volumes 卡片页改名后继续作为 Phase 32 权威。
