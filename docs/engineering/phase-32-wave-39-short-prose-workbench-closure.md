# Phase 32 Wave 39：短中篇逐单元正文工作台闭环

状态：**短中篇 `ShortProseUnitArtifact` 已完成冻结单元顺序、窄上下文生成、source-bound 草稿、逐单元提交、SQLite 恢复、Version 20 正文工作台与五视口浏览器验收；本轮没有调用真实 Provider，也没有改写历史 Run**

日期：2026-08-24

## 产品决定

短中篇 Text 是按已确认 Section Plan 连续写作的正文版本链，不是一次性生成整本书，也不是把全部历史正文重新塞回模型。

1. 单元顺序、类型、标题与 POV 由 committed `SectionPlanArtifact.units` 冻结；
2. 每次只生成当前单元，读取当前计划、相关 Story Map 锚点、POV 与一跳关系人物、上一单元 handoff 和最多 1,200 字尾部；
3. accepted 单元不可覆盖，可从单元栏回看但保持只读；
4. 候选正文默认以稿纸阅读态呈现，只有当前候选进入编辑态后才出现正文编辑器；
5. 全部冻结单元提交后才允许进入 Cover，不用字数硬配额触发隐藏扩写或换稿。

## 后端合同

- `Phase32RouteDriver.sequential_unit_refs` 只从 committed Section Plan 投影 ordered unit refs；
- `ShortProseUnitArtifact.unit_ref / unit_kind / title / pov_subject_ref` 为冻结身份，作者草稿只允许修改 `content`；
- Context compiler 不注入完整历史正文，只携带上一 accepted 单元的有界尾部和 handoff；
- 当前单元的 Story Map Promise、相关 Cast 与 Section Plan 计划被裁剪为最小上下文；
- Provider 返回的标题、类型、POV 或单元引用漂移会成为合同拒绝，不写入候选；
- 每个单元拥有独立 candidate、decision、draft 和 committed ref；全部完成后清空 unit cursor 并进入 Cover；
- SQLite checkpointer、Run repository、ArtifactStore 与 Provider receipt 重开后共同恢复到下一未提交单元。

## 前端结果

- 新增短中篇正文 Artifact 解析、冻结身份校验与字符统计；
- 工作台由统一 184px 单元导航、主稿纸和右侧计划/交接 Inspector 组成；
- 当前候选支持阅读/编辑双态、650ms 自动保存、刷新恢复、定向换稿、取消与确认；
- 历史 accepted 单元可切换回看，但编辑入口与正文输入均禁用；
- 390px 下普通二级栏转为顶部横向 U01/U02 导航，主稿纸保持单列阅读；
- 修复移动端全局命令按钮缺少可访问名称，浏览器未命名交互控件从 1 降为 0。

## 浏览器证据

隔离环境：

- Fake Provider/API：`127.0.0.1:8795`；
- Vite：`127.0.0.1:5184`；
- 临时运行数据：`/tmp/yotsuba-wave39-short-prose.JaveIg`；
- 用户原有 `127.0.0.1:5176` 未停止、未修改；
- Gateway 只使用确定性本地 payload，不读取 API Key，不发起外部请求。

验收覆盖：

1. U01 committed、U02 candidate，历史 U01 可浏览且不可编辑；
2. U02 的计划/交接 Tab 均显示当前真实上下文；
3. 编辑两段正文后显示“草稿已保存”，刷新后从服务端恢复草稿并回到阅读态；
4. `PUT stage-drafts` 与 `POST decisions` 均返回 `200`；
5. U02 提交后 URL 进入 `/run/cover`，返回正文可看到 U01/U02 均为 accepted；
6. `1728x1100`、`1440x1000`、`1280x920`、`1024x700`、`390x844` 均无横向溢出；
7. 桌面单元栏稳定为 `184px`，Browser Console 为 `0 error / 0 warning`。

截图证据位于：

- `output/playwright/wave32-39-short-prose/short-prose-candidate-1728x1100.png`
- `output/playwright/wave32-39-short-prose/short-prose-candidate-1440x1000.png`
- `output/playwright/wave32-39-short-prose/short-prose-candidate-1280x920.png`
- `output/playwright/wave32-39-short-prose/short-prose-candidate-1024x700.png`
- `output/playwright/wave32-39-short-prose/short-prose-candidate-390x844.png`
- `output/playwright/wave32-39-short-prose/short-prose-edit-1440x1000.png`
- `output/playwright/wave32-39-short-prose/short-prose-edit-390x844.png`
- `output/playwright/wave32-39-short-prose/short-prose-to-cover-1440x1000.png`
- `output/playwright/wave32-39-short-prose/short-prose-committed-1440x1000.png`

## 测试与审计

- 后端全量：`1069 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- 前端全量：`52 files / 127 tests passed`；
- TypeScript/Vite production build：通过；短中篇正文独立 CSS `13.31 kB`、JS `17.50 kB`；
- frontend structure audit：`175` 个 TypeScript source files，通过；
- CSS audit：跨文件重复 selector `0`、重复 keyframe `0`、infinite animation `9`、Reduced Motion guard `29`；
- 首屏 CSS `31.7 KiB gzip`、Python `compileall`、目标 `oxfmt --check` 与 `git diff --check` 均通过；
- production build 仍只有既有主入口与 `CharacterGraph3D` 大 chunk warning。

## 验收边界

1. 本轮证明逐单元离线合同、跨进程恢复、正式 API 草稿闭环和浏览器交互，不证明真实 Provider 的文学质量、成本或长链稳定性；
2. 动机、连续性、声音与结尾兑现仍属于后续真实 Provider 和通篇冷读门；
3. committed amendment、Section 拆分/合并与下游 stale 重算尚未开放；
4. 短中篇 Cover 与 BookDelivery、长篇 Text/Cover/BookDelivery、Phase 32 作者协作和 Story Bible 仍未闭合；
5. README、CHANGELOG、commit 与 GitHub push 继续等待三条路线完整证据包。

下一切片迁移短中篇 `CoverArtifact` 与 `BookDeliveryArtifact`：封面候选必须绑定真实不可变资产，Export 必须消费 ordered committed 正文版本与正式封面并确定性物化文件；不得复用旧 `selected_asset_id / chapter_version_ids` mock 合同。
