# Phase 32 Wave 30：Book Architecture 专业工作台闭环

状态：**长篇 Book Architecture 的正式 Artifact、作者草稿、Part 重排、定稿聚合、committed
只读、Monitor 与 Version 20 三视口验收通过；浏览器发现的聚合游标错误已在新鲜 Run 中关闭**

日期：2026-08-23

## 产品决定

本切片只迁移长篇路线的 `BookArchitectureArtifact`。Book Architecture 是一个聚合根：

```text
Book root
  -> stable Part refs[]
  -> Part entry/question/turning points/exit/obligations
  -> one source-bound draft
  -> one aggregate commit
```

作者可以编辑 Book/Part 文学内容并重排现有 Part，但不能在没有服务端稳定 ref 分配合同的
情况下新增或删除 Part。Promise 与 Turning Point refs 继续只读；Inspector 只观察当前
Artifact 内的引用分布，不宣称已经通过尚不存在的 Promise registry 核验。

## Version 20 工作台

- 桌面使用统一 `--stage-secondary-width: 272px` Part rail，按真实内容高度排列；
- 主区先显示 Book Promise 与 Ending Conditions，再显示当前 Part 的 entry state、dramatic
  question、exit state、Promise refs、turning point refs 与 unresolved obligations；
- 点击 Part rail 会同步选中内容，现有 Part 可上下移动；重排只重建连续 ordinal，稳定
  `part_ref` 与引用身份保持不变；
- 文学字段和列表复用 650ms source-bound 自动保存，刷新后从服务端恢复同一 draft；
- ReviewPolicy 允许时提供定向换稿，弹窗有三条 Book Architecture 专属建议并支持 `Esc`；
- committed Artifact 保持相同信息架构，但全部 textarea 只读、排序按钮禁用，并提供进入
  Volumes 当前决策点的正式导航；
- `1180px` 以下 Inspector 转为底部检查区，`767px` 以下隐藏桌面 rail，使用 Part 快捷导航；
  Reduced Motion 下取消不必要位移。

## 浏览器发现与底层修复

第一次浏览器定稿使用 Run：

```text
project_id: p32-proj-2447750e17d847df9d0f
run_id: p32-run-8589b3378efcaac37bbb
```

作者把 `part-hearing` 移到 `part-archive` 之前并保存草稿后，提交被确定性拒绝：

```text
Candidate unit ref does not match its Artifact
```

最低责任层不是前端、草稿 Store 或 Provider。运行时曾把 `bounded_units` 聚合中数组第一项的
ref 当成 `active_unit_ref`。pending decision 因此冻结了原首项 `part-archive`，而合法重排后的
物化候选首项是 `part-hearing`，导致同一聚合根被错误判断为运行单元身份漂移。

修复后，`active_unit_ref` 只用于真正按顺序执行的 `sequential_units`。Book Architecture、
Cast、Volumes、Rolling Detail、Section Plan 与 Scene Deck 等 `bounded_units` 阶段仍由各自
聚合根一次提交，子项顺序不再冒充 Graph cursor。回归测试使用两个 Part 反转首项后定稿，
直接覆盖本次失败条件。

失败 Run 保持不可变，没有 reset、删除、恢复或伪造为成功；正式验收改用新鲜 Run。

## 新鲜正式链路证据

隔离 Fake Provider Run：

```text
project_id: p32-proj-622c2daadaaed328bd36
run_id: p32-run-480f95448c90612db874
route: long_novel / r2
```

浏览器完成：

1. 原始候选包含 `part-archive / part-hearing` 两个稳定 Part；
2. 重排为 `part-hearing / part-archive`，ordinal 自动恢复为 `1 / 2`；
3. 修改 Part 01 戏剧问题与进入状态，页面显示“草稿已保存”；
4. 刷新后恢复相同文本、稳定 ref 与 Part 顺序；
5. 定向换稿弹窗显示三条专属建议，`Esc` 关闭，未真正换稿；
6. 草稿定稿为：

```text
p32-book_architecture-committed-8af4f2a7333c07bc434321f6d41689c55c3b2b9f51beb78d7b5e47c0564ce288
```

7. committed payload 保留作者修改和 `part-hearing / part-archive` 顺序；6 个 textarea 全部
   `readOnly=true`，Part 排序按钮全部禁用；
8. 同一 LangGraph 按冻结 ReviewPolicy 自动提交 Cast，并停在 Volumes 人工决策点；Rolling
   Detail 及后续阶段保持 locked；
9. Run read model 为 `awaiting_decision / volumes`，failure 为空，4 次 Fake Provider operation
   全部 returned/succeeded，合同拒绝、失败与 pending 均为 0。

该数据只证明 Artifact、草稿、决策、Graph、事件和 UI 投影闭环。Fake Provider 的 `0 token`、
未知价格和未知余额不代表真实成本，也没有用于文学质量判断。

## Monitor 与浏览器证据

Monitor 选择 Book Architecture 后显示：

- committed Artifact ref 与 `book_architecture` 工作台合同；
- 阶段开始、候选生成、等待决策、决策执行、Artifact 提交共 5 条阶段事件；
- 全 Run 最近 6/17 条日志；
- `4/4` Provider operations、0 合同拒绝、0 失败/等待；
- checkpoint、definition digest、`r2 · 长篇小说` 与当前 Volumes 决策。

隔离环境：API `127.0.0.1:8788`，Vite `127.0.0.1:5177`；用户自己的 `5176` 全程保持原
进程。`1440x920`、`1024x700`、`390x844` 的 candidate 与 committed 页面均满足
`documentElement.scrollWidth === clientWidth`；Monitor `1440x920` 同样无横向溢出。控制台
`0 error / 0 warning`。

截图：

- `output/playwright/wave32-30-book-architecture/book-architecture-candidate-1440x920.png`
- `output/playwright/wave32-30-book-architecture/book-architecture-candidate-1024x700.png`
- `output/playwright/wave32-30-book-architecture/book-architecture-candidate-390x844.png`
- `output/playwright/wave32-30-book-architecture/book-architecture-committed-1440x920.png`
- `output/playwright/wave32-30-book-architecture/book-architecture-committed-1024x700.png`
- `output/playwright/wave32-30-book-architecture/book-architecture-committed-390x844.png`
- `output/playwright/wave32-30-book-architecture/monitor-book-architecture-1440x920.png`

## 测试与审计

- Part 重排提交、Phase 32 driver 与 route graph 目标后端：`23 passed, 1 warning`；
- Book Architecture parser、editor 与 stage view：`3 files / 8 tests passed`；
- 后端全量：`1023 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`24 files / 68 tests passed`；
- TypeScript 与 Vite production build：通过；Book Architecture CSS/JS 保持独立懒加载；
- frontend structure audit：`129` 个 TypeScript source files，通过；
- CSS audit：`crossFileDuplicateSelectorCount=0`、`duplicateKeyframeNameCount=0`，通过；
- CSS build check：首屏 CSS `30.4 KiB gzip`，通过；
- Python `compileall`、`git diff --check` 与 production closure audit：通过。

production build 仍报告既有主入口和 Character Graph 3D 大 chunk warning；本切片没有把
Book Architecture 合并进这些 chunk，也不能据此宣称性能规模门完成。

## 闭环审计分类

- **已补行为**：Book/Part 专业编辑、服务端草稿恢复、稳定 ref 重排、聚合提交、committed
  只读、下一阶段导航和 Monitor 内容；
- **已修错误**：bounded aggregate 的第一子项不再污染 Graph `active_unit_ref`；
- **未证明行为**：真实 Provider 的 Book Architecture 输出质量、成本、余额、文学连续性和
  自动 axe 无障碍门；
- **仍缺行为**：Part 新增/删除稳定 ref 分配、正式 Promise registry、post-commit amendment/
  impact、作者协作 source-bound patch；
- **历史/旧路径**：失败 Run 留作只读证据；closure audit 未发现目标 legacy markers 或异常
  pipeline 顶层目录。

## 未闭合边界

本切片只关闭长篇 Book Architecture 的候选到 committed 工作台，不代表 Wave 32.6 或
Phase 32 整体完成：

1. Cast、Volumes、Rolling Detail、Section Plan、Beat Board、Scene Deck、Text、Script、Cover
   与 Export 仍未全部迁移为 Phase 32 专业工作台；
2. Book Architecture 的 committed amendment、dependency/impact 与作者协作仍未接入；
3. 自动无障碍门尚未引入 `@axe-core/playwright`；
4. 本轮没有调用真实 Provider，不能证明文学质量、真实成本、长链恢复或最终交付；
5. README、CHANGELOG、commit 和 push 继续等待三路线完整证据包。

下一切片应迁移三路线共享 `CharacterBibleAggregate` 的 Cast 专业工作台，先定义 route-aware
人物职责、关系、scope 与 source-bound aggregate commit，再复用现有 3D/2D 图谱作为可重建
投影；不能让图谱坐标或旧 Story Bible Store 成为 Character Artifact 权威。
