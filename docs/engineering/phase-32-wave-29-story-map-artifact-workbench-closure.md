# Phase 32 Wave 29：Story Map Artifact 专业工作台闭环

状态：**短中篇 Story Map 的正式 Artifact 读取、作者草稿、锚点重排、定稿物化、committed 只读、监控同步与 Version 20 三视口验收通过；后续专业工作台仍未迁移**

日期：2026-08-23

## 产品决定

本切片只迁移短中篇路线的 `StoryMapArtifact`。它继续复用 Wave 32.28 建立的唯一正式链路：

```text
pending decision candidate
  -> current Artifact API
  -> schema-specific Story Map workbench
  -> source-bound draft autosave
  -> draft_ref
  -> LangGraph decision resume
  -> committed immutable StoryMapArtifact
  -> Run read model / SSE / monitor
```

Story Map 是有限锚点的单体故事规划，不恢复旧 Spine 的 `cause/change` 链、精确 turn 配额或
隐藏语义重试。确定性边界只负责 Artifact Schema、稳定 ref、顺序、Promise 引用分布、草稿来源
与提交身份；动机、因果说服力和高潮力度仍是作者判断或文学 warning。

当前没有正式 Promise registry，因此 Inspector 只统计 `promise_refs` 的覆盖分布，不宣称上游
承诺已经被系统核验。服务端也尚未提供新增或删除 anchor 时的稳定 ref 分配合同，本切片只允许
在保留原 ref 的前提下编辑和重排现有 anchor。

## Version 20 工作台

- 桌面二级侧栏使用统一 `--stage-secondary-width: 272px`，按 Artifact 中的真实 anchor 高度排列；
- 主区按连续故事地图呈现开场状态、故事问题、每个 anchor 的戏剧任务、压力、选择或揭示、
  后果、Promise refs、结尾状态和开放问题，不使用通用 JSON 表单或卡片墙；
- 点击侧栏 anchor 会选中并滚动到对应内容，选中态与主区保持一致；
- 上下移动会重排 Artifact 数组，但 `anchor_ref`、Promise refs 和内容身份保持不变；
- 开放问题支持增删改；Promise refs 保持只读，避免 UI 无权创建上游承诺；
- 所有字段复用 650ms source-bound 自动保存，刷新后从服务端恢复同一 draft；确认前再次 flush；
- ReviewPolicy 允许时显示定向换稿，弹窗提供 3 条 Story Map 专属建议并支持 `Esc` 关闭；
- committed Artifact 全部只读，隐藏开放问题 composer，禁用排序按钮，并提供进入当前活动阶段的
  正式导航；
- `1180px` 以下 Inspector 转为底部检查区，`767px` 以下隐藏桌面 anchor rail，改用横向快捷导航；
  Reduced Motion 下取消平滑滚动和不必要位移。

## 运行监控修复

浏览器验收确认中央“当前创作内容”和阶段事件已经来自正式 Run read model/SSE，但右侧 Inspector
缺少用户此前明确要求的运行日志。修复后：

- 中央区域继续保留所选阶段的完整事件历史；
- 右侧新增“最近运行日志”，只显示全 Run 最新 6 条，保持健康、Provider、成本和恢复信息的层级；
- 中央与右侧共用同一个事件 label/detail/time helper，没有复制事件状态源；
- failure/recovery 日志使用风险色，其余日志保持克制；移动端仍使用专注布局，不强行塞入右栏。

## 正式链路证据

隔离 Fake Provider Run：

```text
project_id: p32-proj-f193bf4f91ac52ad0954
run_id: p32-run-bec169d9c2f3209bcbeb
route: short_novel / r2
```

浏览器完成：

1. 接受 Brief 后不刷新即可读取 3 个稳定 Story Map anchors；
2. 把 `anchor-1 / anchor-2 / anchor-3` 重排为
   `anchor-2 / anchor-1 / anchor-3`；
3. 修改故事问题并新增第 3 条开放问题，页面显示“草稿已保存”；
4. 刷新后恢复相同文本、开放问题和 anchor 顺序；
5. 打开定向换稿弹窗，验证 3 条专属建议和 `Esc` 关闭，但没有执行换稿；
6. 确认 Story Map 后，草稿物化为：

```text
p32-story_map-committed-681eb17d93b2687bd9e3f52b4db961ce2268b8b1ce54d9674bf52bb0e80b624b
```

7. committed 页面恢复相同顺序和作者修改，全部 textarea 只读、排序按钮禁用；
8. 同一 Graph 按冻结 ReviewPolicy 继续提交 Cast 与 Section Plan，并停在 `text / unit-1`
   决策点；没有进入 Cover 或 Export；
9. 监控选择 Story Map 后显示 committed ref、5 条该阶段事件、Run 最新日志、`5/5` Fake
   Provider operations、checkpoint 和 Text 当前决策。

该数据只证明 Artifact、决策、草稿、事件和 UI 投影闭环。Fake Provider 的 `0 token`、未知价格
和未知余额不代表真实成本，也没有用于文学质量判断。

## 浏览器与视觉证据

隔离环境：

- API：`127.0.0.1:8788`；
- Vite：`127.0.0.1:5177`；
- 用户自己的 `127.0.0.1:5176` 全程保持原进程，未重启或修改。

视口：

- `1440x920`：272px anchor rail、连续主区和右侧 Inspector 同屏；
- `1024x700`：Inspector 转为底部检查区，主区保留内部滚动；
- `390x844`：桌面 rail 隐藏，3 个 anchor 使用横向快捷导航，底部全局状态栏不遮挡内容。

三种视口均满足 `documentElement.scrollWidth === clientWidth`，没有页面级横向溢出；控制台
`0 error / 0 warning`。截图：

- `output/playwright/wave32-29-story-map/story-map-committed-1440x920.png`
- `output/playwright/wave32-29-story-map/story-map-committed-1024x700.png`
- `output/playwright/wave32-29-story-map/story-map-committed-390x844.png`
- `output/playwright/wave32-29-story-map/monitor-story-map-1440x920.png`

## 测试与审计

目标门：

- Story Map parser、draft hook、editor、stage view 与 monitor Inspector：
  `5 files / 12 tests passed`；
- 正式 Phase 32 execution API：`7 passed, 1 warning`。

最终回归：

- 后端全量：`1022 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`21 files / 60 tests passed`；
- TypeScript 与 Vite production build：通过；Story Map CSS 保持独立按需 chunk；
- frontend structure audit：`125` 个 TypeScript source files，通过；
- CSS audit：`crossFileDuplicateSelectorCount=0`、`duplicateKeyframeNameCount=0`，通过；
- CSS build check：首屏 CSS `30.4 KiB gzip`，通过；
- Python `compileall`、`git diff --check` 与 production closure audit：通过。

production build 仍报告既有大 JS chunk warning，主要是 Character Graph 3D chunk 和主入口；
本切片没有扩大该问题，也不能据此宣称性能规模门完成。

## 闭环审计分类

- **已补行为**：Story Map 专业编辑、服务端草稿恢复、稳定 ref 重排、定稿/只读、阶段导航、
  监控内容与右侧最近日志；
- **未证明行为**：真实 Provider 的 Story Map 输出质量、计价、余额、文学连续性和自动 axe
  无障碍门；
- **仍缺行为**：anchor 新增/删除的服务端 ref 分配、正式 Promise registry、post-commit
  amendment/impact、作者协作 source-bound patch；
- **历史/旧路径**：closure audit 未发现目标 legacy markers 或异常 pipeline 顶层目录；既有
  `SpineStageView`、旧大文件和后续未迁移工作台仍需在对应替代路径通过后同波退休，不能在本
  切片提前删除。

## 未闭合边界

本切片只关闭短中篇 Story Map 的候选到 committed 工作台，不代表 Wave 32.6 或 Phase 32
整体完成：

1. Book Architecture、Cast、Volumes、Rolling Detail、Section Plan、Beat Board、Scene Deck、
   Text、Script、Cover 与 Export 仍未全部迁移为 Phase 32 专业工作台；
2. Story Map 的 committed amendment、dependency/impact 与作者协作仍未接入；
3. 自动无障碍门尚未引入 `@axe-core/playwright`，本轮只完成语义 DOM、键盘弹窗和三视口检查；
4. 本轮没有调用真实 Provider，不能证明文学质量、真实成本、长链恢复或最终交付；
5. README、CHANGELOG、commit 和 push 继续等待三路线完整证据包。

下一切片应迁移长篇 `BookArchitectureArtifact` 专业工作台，复用相同 current/draft/decision/
receipt/SSE 链路，并保持 Book root、Part contracts、Promise lifecycle 与聚合提交边界；不能把
Story Map 或旧 Spine UI 改名后复用。
