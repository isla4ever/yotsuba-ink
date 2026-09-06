# Phase 32 Wave 40：封面与小说成书交付闭环

状态：**短中篇 `CoverArtifact` 与 `BookDeliveryArtifact` 已完成真实图片资产、source-bound 选择草稿、正式封面定稿、确定性 DOCX 物化、不可变回执、下载校验、Version 20 专业工作台与四视口浏览器验收；本轮没有调用真实 Provider，也没有改写失败或历史 Run**

日期：2026-08-24

## 产品决定

Cover 是作者对真实候选图片资产的定稿阶段，Export 是对已接受正文版本和正式封面的确定性交付阶段。两者都不是 mock 预览，也不能在下载时重新生成内容。

1. Cover candidate 保存视觉 Brief、图片 Prompt、候选资产 ref 与作者当前选择；候选图片由独立 AssetStore 持久化；
2. 作者切换候选只写 source-bound stage draft，确认后才把选择提交为 committed Cover Artifact；
3. Export 只接受 ordered committed 正文版本、正式封面、格式与交付元数据；不回读未接受候选；
4. 文件在 Export commit 时一次性物化，列表和下载只读取不可变文件与回执；
5. 封面、正文版本、Artifact digest、文件大小和 SHA-256 任一不一致都必须显式失败，不能静默重建或继续下载。

## 后端合同

- `CoverArtifact` 使用稳定 `candidate_asset_refs` 与 `selected_asset_ref`；服务端拒绝不在候选集合中的选择；
- 三张浏览器夹具候选均为持久化 PNG，尺寸为 `256 x 384`，不是 CSS 色块或远程占位图；
- Run 创建时冻结图片 Provider binding。首个隔离 Run 因 `image_execution=null` 正确停在 Cover，并记录 `provider_contract_failed`；该失败 Run 未被重试或改写；
- 第二个隔离 Run 在创建前绑定本地 Fake image gateway，生成三张候选后停在 Cover 决策点；gateway 不读取真实密钥、不发外部请求；
- committed Export Artifact 冻结正文单元、正文版本、封面资产、格式和元数据；
- `ExportStore.materialize_book_delivery` 从同一权威一次性物化文件，并按 Artifact digest 幂等返回相同回执；
- `GET /api/runs/{run_id}/exports` 只返回 committed Artifact 绑定的文件；下载接口返回冻结内容与 `X-Content-SHA256`；
- 下载前后均校验文件 SHA-256；DOCX 内嵌封面 PNG 的 SHA-256 也必须与正式封面回执一致。

## 前端结果

- Cover 使用统一 `184px` 候选资产栏、主封面预览和视觉/资产回执 Inspector；选择态、alt、大图、尺寸、文件大小和哈希同步切换；
- 当前选择通过统一 stage draft 自动保存，刷新后从服务端恢复；确认正式封面后自动进入 `/run/export`；
- Book Delivery 使用统一 `184px` 文件栏、正文版本 Manifest、正式封面、完整性摘要与右侧不可变交付回执；页面无输入框；
- 多格式文件按钮会切换当前文件、主下载命令和右侧回执；各格式下载状态独立保存；
- 下载成功后文件栏和回执同步显示“已下载”，不会触发整页 loading、正文重算或 Provider 调用；
- Cover 与 Book Delivery 各自按 shell/assets-or-manifest/inspector-or-receipt 三个职责拆分 CSS，并由对应 lazy StageView 唯一导入；
- `900px` 以下工作台改为纵向自然流，移动端候选/文件栏为横向导航，主内容与回执顺序堆叠，不再继承桌面 `flex: 1` 造成覆盖。

## 浏览器证据

隔离环境：

- Fake Provider/API：`127.0.0.1:8796`；
- Vite：`127.0.0.1:5185`；
- 用户原有 `127.0.0.1:5176` 未停止、未修改；
- Project：`p32-proj-fb9efa748daa5b1a79e3`；
- 成功 Run：`p32-run-89736db89dd61f6dccde`；
- Provider 合同失败证据 Run：`p32-run-3d272f36e733cd34aa74`；
- 临时运行目录在验收结束后已删除，`8796/5185` 已关闭。

验收覆盖：

1. 点击 Cover 候选 2 后，大图、alt、尺寸与 SHA-256 同步为该资产；`PUT stage-drafts` 返回 `200`，刷新后仍恢复候选 2；
2. 点击“确认正式封面”后 URL 自动进入 `/run/export`，Run 终态为“已完成”；
3. Export 显示 `1` 个 committed 正文单元、`23` 个正文字符、正式封面和唯一 DOCX 回执；
4. 下载得到 `失序档案.docx`，大小 `7,245 B`，SHA-256 为 `ca42b2bbd022ee8f3c73a499967b19e72d3f835cacf67aa0d2764cfada239a96`，与页面和 API 回执完全一致；
5. DOCX ZIP 结构完整，内含 `word/media/cover.png`；内嵌封面 SHA-256 为 `791fde698fe2679c6a958f81f4cda8e76ecc65373b1edb9e8dcfdbd1a44bbf48`，与 committed Cover 完全一致；
6. 下载后文件栏显示“已下载”，右侧回执显示“已下载并核验”；
7. `1440x920`、`1280x920`、`1024x700`、`390x844` 均无页面横向溢出，未命名按钮为 `0`；
8. Browser Console 最终为 `0 error / 0 warning`，只有 React DevTools 开发环境 info。

截图证据位于：

- `output/playwright/wave32-40-cover-book-delivery/cover-selected-1440x920.png`
- `output/playwright/wave32-40-cover-book-delivery/cover-selected-1280x920.png`
- `output/playwright/wave32-40-cover-book-delivery/cover-selected-1024x700.png`
- `output/playwright/wave32-40-cover-book-delivery/cover-selected-390x844-final.png`
- `output/playwright/wave32-40-cover-book-delivery/cover-selected-mobile-bottom-390x844.png`
- `output/playwright/wave32-40-cover-book-delivery/book-delivery-1440x920.png`
- `output/playwright/wave32-40-cover-book-delivery/book-delivery-1280x920.png`
- `output/playwright/wave32-40-cover-book-delivery/book-delivery-1024x700.png`
- `output/playwright/wave32-40-cover-book-delivery/book-delivery-390x844.png`

## 测试与审计

- Cover/Book Delivery 前端目标集：`4 files / 6 tests passed`；
- 后端 Cover/Book Delivery/API 目标集：`56 passed, 1 warning`；
- 前端全量：`56 files / 133 tests passed`；
- 后端全量：`1073 passed, 1 warning`；唯一 warning 为既有 Starlette/httpx 弃用提示；
- TypeScript/Vite production build：通过；Cover CSS `11.29 kB`、Book Delivery CSS `14.08 kB`；
- frontend structure audit：通过，共 `185` 个 TypeScript source files；
- CSS audit：跨文件重复 selector `0`、重复 keyframe `0`、infinite animation `9`、Reduced Motion guard `31`；
- 首屏 CSS `31.7 KiB gzip`，CSS build check 通过；
- Python `compileall`、目标 `oxfmt --check`、`git diff --check` 与 production closure audit：通过；
- production build 仍报告既有主入口和 `CharacterGraph3D` 大 chunk warning，本轮 StageView 保持懒加载，没有把 Cover/Book Delivery CSS 并回首屏。

## 验收边界

1. 本轮证明 Fake Provider 下的真实资产、正式决策、确定性交付、文件完整性和浏览器交互，不证明真实图片 Provider 的稳定性、成本或审美质量；
2. 浏览器夹具为单单元、单 DOCX 最小合法交付；多单元、长篇卷级 Manifest、EPUB/Markdown 顺序、损坏文件和多格式物化由后端合同测试覆盖，多格式 UI 切换由前端回归测试覆盖；
3. 长篇 Text 尚未迁移，因此长篇路线仍不能端到端进入 Cover/Book Delivery；
4. Phase 32 作者协作、Story Bible、规模/性能、分级真实 Provider 与文学冷读门仍未闭合；
5. README、CHANGELOG、commit 与 GitHub push 继续等待三条路线完整证据包。

下一切片优先迁移长篇逐章 Text：必须消费当前 Rolling Detail Window、冻结 Book/Part/Volume/Cast 引用、上一章 handoff 与有界正文尾部，保留 accepted prefix，并在全部冻结章节完成后接入本轮已经建立的 Cover/Book Delivery 合同。
