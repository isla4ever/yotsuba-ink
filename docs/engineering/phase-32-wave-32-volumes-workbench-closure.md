# Phase 32 Wave 32：Volumes 卷册架构专业工作台闭环

状态：**长篇 `VolumeArchitectureAggregate` 已完成正式 Artifact、source-bound 草稿、稳定
Volume 重排、定稿聚合、committed 只读、Monitor 与 Version 20 三视口验收；本轮没有调用
真实 Provider**

日期：2026-08-24

## 产品决定

Volumes 是长篇路线中承接 Book Architecture 与 Cast、向 Rolling Detail 交付有界卷合同的
聚合阶段：

```text
committed Book Architecture + committed Cast
  -> VolumeArchitectureAggregate candidate
  -> source-bound aggregate draft
  -> one decision receipt and aggregate commit
  -> immutable VolumeArchitectureAggregate
  -> Rolling Detail Window planning
```

作者可以编辑卷承诺、持续冲突、不可逆高潮、闭合状态和软篇幅，并重排现有 Volume。候选进入
决策后，`volume_ref`、Volume 集合、`part_ref` 与 `cast_subject_refs` 冻结；本页不提前编辑
章节、场景或 handoff，也不建立第二套 Volume/Part/Cast 权威。

## 后端引用与草稿边界

- `long_novel / volumes` 已开放与 Brief、Story Map、Book Architecture、Cast 相同的 current、
  source-bound draft、`draft_ref` materialization、decision receipt 与 committed Store 链路；
- Provider candidate 和作者草稿都必须引用同一 Run 已提交的 Book Architecture Part 与 Cast
  subject；未知 Part、未知人物、重复人物引用、Volume 身份增删替换在提交前确定性拒绝；
- 可编辑字段限定为 `promise / conflict / climax / closure / length_hint`，重排只重建连续
  `ordinal`，稳定 Volume ref 与上游引用不变；
- `VolumeContract.cast_subject_refs` 增加唯一性校验；
- Book Architecture 草稿同步收紧为不能凭空新增、删除或替换 Part ref；
- 跨 Artifact 校验从 Phase 32 driver 提取到独立 orchestration 责任边界，API route 继续只做
  HTTP 适配。

## Version 20 工作台

- 桌面卷册 rail 使用统一 `--stage-secondary-width: 272px`，按真实内容高度排列；
- Part 和人物显示上游 Artifact 的可读标签，同时保留冻结 ref 身份；
- 中央编辑区按“承诺 -> 对抗 -> 高潮 -> 闭合”呈现四段卷合同，软篇幅保持紧凑输入；
- Inspector 显示 Volume 数、计划字数、人物覆盖、Part 覆盖、编辑边界、下游交接与版本来源；
- `1180px` 以下 Inspector 下沉为底部检查区，`767px` 以下桌面 rail 转为 V01/V02 横向快捷
  导航；四段编辑区改单列，页面不出现横向溢出；
- 650ms 自动保存、刷新恢复、定向换稿弹窗、`Esc` 关闭、定稿、committed 只读和进入
  Rolling Detail 的导航都复用 Phase 32 正式链路；
- 页面与编辑器 CSS 按布局/字段职责拆分，并保持独立 lazy chunk。

## 新鲜 Fake Run 正式链路

隔离数据根中的新鲜 Run：

```text
project_id: p32-proj-4f8f73f05a87549cacd0
run_id: p32-run-090d8ecb5ce8b7a635e3
route: long_novel / r2
```

浏览器完成：

1. 通过正式 Project API 创建新作品，启动 Run 并接受 Brief、Book Architecture；同一 Graph
   自动提交 Cast，严格停在 Volumes 决策点；
2. 切换到第二卷，修改四个文学字段，将软篇幅从 `55,000` 调整为 `56,000`；
3. 将 `volume-2` 上移到第一位，连续 ordinal 重建为 `1 / 2`，`part-hearing / part-1` 与
   `maya` 引用保持不变；
4. 页面显示“草稿已保存”，服务端草稿 ref 为
   `p32-draft-8135cc19ef44077a812c678483aa7b948d24e3e5cfd2dbab5be3eab12ba8f8a0`；刷新后
   恢复相同顺序、字段和软篇幅；
5. 定向换稿弹窗显示 Volumes 专属边界与三条方向建议，`Esc` 关闭，未实际调用换稿；
6. 定稿生成
   `p32-volumes-committed-8562f4799928952fb42c260de6bf97b366ab584e57b9ea1f208edaed74b18163`；
   committed payload 保留作者修改与 `volume-2 / volume-1` 顺序；
7. 定稿后 4 个 textarea 与软篇幅 input 全部 `readOnly=true`，排序按钮全部禁用；
8. 同一 LangGraph 进入 `rolling_detail / awaiting_decision`，Volumes 为 completed，后续 Text、
   Cover、Export 仍 locked；
9. Run 为 `5/5` Fake Provider operations，合同拒绝、失败与 pending operation 均为 0。

该证据证明 Artifact、草稿、引用、决策、Graph、事件与 UI 投影闭环。Fake Provider 的 0 token、
未知价格和未知余额不代表真实成本，也没有用于证明文学质量。

## Monitor 与浏览器证据

Monitor 选择 Volumes 后显示：

- route-aware 8 阶段 rail，Volumes 已提交，Rolling Detail 为“待决策 · 当前”；
- committed `volume_architecture` ref、工作台合同与有界单元策略；
- Volumes 阶段开始、候选生成、等待决策、决策执行、Artifact 提交共 5 条事件；
- 全 Run 最近 `6/22` 条日志；
- `5/5` Provider operations、0 合同拒绝、0 失败/等待；
- checkpoint `1f19f0a3-fa7c-64a8-8004-ee28a59b4762`、definition digest 与 `r2 · 长篇小说`。

隔离环境为 API `127.0.0.1:8788`、Vite `127.0.0.1:5177`；用户自己的 `5176` 全程保持原
进程。`1440x920`、`1024x700`、`390x844` 的 candidate 与 committed 页面均满足
`documentElement.scrollWidth === clientWidth`；控制台 `0 error / 0 warning`。浏览器导航时被
AbortController 取消的旧读取随后由当前页面请求正常返回 `200`，没有 mock route 或真实外网请求。

截图：

- `output/playwright/wave32-32-volumes/volumes-candidate-1440x920.png`
- `output/playwright/wave32-32-volumes/volumes-candidate-1024x700.png`
- `output/playwright/wave32-32-volumes/volumes-candidate-390x844.png`
- `output/playwright/wave32-32-volumes/volumes-mobile-inspector-390x844.png`
- `output/playwright/wave32-32-volumes/volumes-committed-1440x920.png`
- `output/playwright/wave32-32-volumes/volumes-committed-1024x700.png`
- `output/playwright/wave32-32-volumes/volumes-committed-390x844.png`
- `output/playwright/wave32-32-volumes/monitor-volumes-1440x920.png`

## 测试与审计

- 后端全量：`1033 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`31 files / 84 tests passed`；
- TypeScript 与 Vite production build：通过；Volumes CSS/JS 为独立 lazy chunk；
- frontend structure audit：`138` 个 TypeScript source files，通过；
- CSS audit：`crossFileDuplicateSelectorCount=0`、`duplicateKeyframeNameCount=0`，通过；
- CSS build check：首屏 CSS `31.0 KiB gzip`，通过；
- 目标 `oxfmt --check`、Python `compileall`、`git diff --check` 与 production closure audit：通过。

第一次完整后端门暴露 `tests/test_phase26_boundaries.py` 的 orchestration 精确文件白名单未登记
新提取的 `phase32_stage_reference_validation.py`。生产逻辑测试均已通过；补齐边界清单后目标测试
和完整 `1033` 测试重新通过。

production build 仍报告既有主入口和 Character Graph 3D 大 chunk warning；Volumes 保持独立
`16.53 kB` JS / `13.63 kB` CSS chunk，本切片没有扩大既有大 chunk，也不据此宣称规模性能门完成。

## 闭环审计分类

- **已补行为**：Volumes 专业编辑、上游可读引用、草稿恢复、稳定 ref 重排、聚合提交、
  committed 只读、下游导航和 Monitor 内容；
- **已修合同缺口**：Volume 人物引用唯一性、Book Architecture Part 集合冻结、Provider 与作者
  草稿共用上游引用验证；
- **未证明行为**：真实 Provider 的卷册质量、真实成本、文学连续性、50 卷规模、自动 axe
  无障碍门与 post-commit amendment；
- **历史/旧路径**：Phase 32 Volumes 已走 Version 20 正式工作台；历史 Run 仍保持只读、零
  Provider。

## 未闭合边界

本切片只关闭长篇 Volumes 候选到 committed 工作台，不代表 Wave 32.6 或 Phase 32 整体完成：

1. Rolling Detail、Section Plan、Beat Board、Scene Deck、Text、Script、Cover 与 Export 仍未全部
   迁移为 Phase 32 专业工作台；
2. committed Volume amendment、dependency/impact 与三路线作者协作 source-bound patch 尚未接入；
3. 自动 axe 无障碍门、50 卷/大规模事件性能 fixture 尚未完成；
4. 本轮没有调用真实 Provider，不能证明卷册文学质量、真实成本、长链恢复或最终交付；
5. README、CHANGELOG、commit 和 push 继续等待三路线完整证据包。

下一切片应迁移长篇 `DetailPlanIndexArtifact` 的 Rolling Detail 专业工作台，先定义当前 Window、
Volume/Part 范围、章节施工图、handoff 和下一窗口入口状态，再接编辑、草稿、聚合提交与监控；
不能把旧全书 Detail 卡片页改名后继续作为 Phase 32 权威。
