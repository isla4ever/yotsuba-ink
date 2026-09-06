# Wave 67：v0.1.0 发布候选与下一轮质量优化

日期：2026-09-06
版本：`0.1.0`
分支：`codex/v2-phase32-routes`
状态：发布候选已通过本地提交与全新检出复验；等待用户明确下达推送指令

## 1. 发布结论

本轮的目标不是继续堆叠功能，而是把已完成的 Phase 32 三路线迭代收敛为可推送 GitHub 的单一发布候选。发布判断拆为两个互不替代的结论：

1. **工程与业务链路**：三条官方路线的 catalog、Project、Run、Artifact、作者决定、Provider operation、恢复、写回、质量投影和文本交付形成同一权威路径；标准长篇 exact-12 已完成真实 DeepSeek 运行和冷态证据复验。
2. **内容质量**：结构与连续性可以继续，但本次长篇样本尚未达到文学成品标准。篇幅、重复感和因果可信度需要下一轮定向改进。

封面图片生成经用户确认不进入本次验收。短中篇与长篇到 `CoverBrief` 后只能进入 `image_deferred`；图片 operation 必须为 0，不能用占位图或历史资产冒充通过。

## 2. 唯一公开产品路径

| 路线 | 官方 workflow id | 冻结阶段链 | 文本侧终态 |
| --- | --- | --- | --- |
| 剧本样片 | `official.screenplay_sample` | brief → cast → beat_board → scene_deck → script → export | `completed`，真实 Fountain receipt |
| 短中篇小说 | `official.short_novel` | brief → story_map → cast → section_plan → text → cover → export | `image_deferred`，真实 CoverBrief，不创建图片 operation |
| 长篇小说 | `official.long_novel` | brief → book_architecture → cast → volumes → rolling_detail → text → cover → export | `image_deferred`，真实 CoverBrief，不创建图片 operation |

公开创建向导、路线目录、Project Shell、命令面板、设置、监控和健康检查均使用上述身份。旧 `official-deepseek-*` 记录只可作为历史数据读取线索，不能写入新的 canonical Run。

## 3. 真实 DeepSeek exact-12 冻结证据

### 3.1 身份

- Project：`continuity-acceptance-proj-a95ab75164232e84fbb1`
- Run：`continuity-acceptance-run-a2c4903f135af471afbc`
- Route：`official.long_novel`
- 架构：`phase32-routes-v1`
- Profile：私有 `continuity_acceptance`，单卷、单 window、恰好 12 章
- 预算：`$5 / 48 logical operations / 2,000,000 tokens / max 3 transports per operation`
- 图片与作者协作：均冻结为 0 operation

### 3.2 完成与恢复

| 指标 | 结果 | 判断 |
| --- | ---: | --- |
| 已接受章节 | 12/12 | accepted prefix 完整且单调 |
| 已提交写回 | 12/12 | chapter 与 source-bound writeback 一一对应 |
| 逻辑 operation | 45 | 全部形成可用终态 |
| transport attempt | 48 | 3 次网络失败均在同一 operation 第 2 次尝试恢复 |
| pending decision / operation | 0 / 0 | 没有悬空工作 |
| 终态 | `image_deferred` | 与当前图片验收边界一致 |
| 图片 / 协作 operation | 0 / 0 | 没有越界调用 |

Provider ledger 中 42 个 operation 直接成功，3 个出现首轮合同拒绝；这 3 个拒绝均保留原回执，并由同一 stage 后续的成功候选与 committed artifact 形成可验证恢复链。Release verifier 只允许这种有完整失败事件、后续成功候选和提交证据的恢复；其他非成功状态仍然阻断。

### 3.3 用量与成本

| 口径 | Prompt tokens | Completion tokens | Total tokens | 成本 |
| --- | ---: | ---: | ---: | ---: |
| Provider 实际回执 | 222,190 | 64,003 | 286,193 | `$0.54674268` |
| Release bundle 保守占用 | — | — | 371,318 | `$0.70662768` |

保守口径包含失败 attempt 的未释放预留，用于保证预算证据宁可高估而不低估。两种口径必须分别展示，禁止把估算当成实际账单。

### 3.4 冷态证据

- Bundle ref：`p32-continuity-evidence-9ae276d6b7e706ca978fd9456bcdb384c9d6363d7e58d236fc38e8394324adbc`
- Quality report ref：`p32-quality-report-1389801dc8e928e6db8516b51e7afcce4a71eea26c7c64a05ff43f5a055dff89`
- Bundle verdict：`ready`
- Issues：`[]`
- 复验方式：从全新进程读取持久 authority，重建 run、attempt、artifact、writeback、quality 与终态后校验；不依赖原进程内存。

## 4. 文学质量诚实结论

12 章非空白字符数依次为：

`2187, 1995, 2071, 1299, 2149, 1942, 1850, 2909, 3028, 1888, 2103, 2327`

总计 `25,748 / 37,500`，达成率 `68.7%`。12 章中 9 章经过一次定向换稿，共形成 17 个正文 draft version；12/12 最终接受稿均绑定人工 source digest。

| 质量面 | 结果 | 发布含义 |
| --- | --- | --- |
| 结构 blocker | 0 | 工程链可继续 |
| 冷读意愿 | `continue_reading` | 故事具备继续阅读基础，不等于成品通过 |
| 篇幅 | 高风险 warning | 当前 Prompt/预算没有稳定兑现冻结章长 |
| 流程性重复 | 中风险 warning | 调查、核验、交接动作有同构感 |
| 因果可信度 | 高风险 warning | 部分关键转折的证据与行动代价不足 |
| production acceptance | `not_evaluated` | 禁止宣称文学成品验收完成 |

因此，本版本可以声明“文本运行、连续性、恢复和证据闭环通过”，不能声明“长篇文学质量通过”或“可直接出版”。

## 5. 本轮发布工程收口

- Python、Web、API 与锁文件版本统一为 `0.1.0`。
- 公开 creation catalog 和新建 Project 只接受三条 canonical workflow id。
- `mode=new`、自定义模板种子和旧 workflow catalog reader 已从公开创建合同移除；未交付的第四条写路径不能再绕过官方目录。
- 前端目录、创建向导、路线详情、Project Shell、命令面板和设置使用 route-native manifest，不再展示旧质量模式。
- 健康检查只返回三条 canonical 路线。
- CORS 默认只允许 `127.0.0.1:5176` 与 `localhost:5176`；额外来源必须由 `YOTSUBA_CORS_ORIGINS` 显式列出，通配来源 fail closed。
- 本地运行数据库、稿件、Provider receipt 和 46MB exact-12 runtime 目录由 `.gitignore` 排除；冻结的脱敏证据摘要进入本文，不提交用户内容或 secret。
- README、英文 README 和 CHANGELOG 从真实三路线产品边界重新编写，不再继承旧模式、旧阶段或历史版本宣传。
- 真实浏览器收口额外修复三项测试盲区：异常历史 Brief 不再拖垮整个书架、路线快捷入口在创作意图为空时必须回到第一步、未启动 Run 的首阶段不再误标为“运行中”。
- Vite 升级到无已知漏洞的 `8.2.2`，作者协作与角色 3D 图保持按需 chunk；首屏 JS 不携带 3D 图实现。

## 6. 下一轮优化计划

### P0：稳定兑现冻结篇幅

目标：标准 exact-12 总篇幅达成率从 68.7% 提高到至少 90%，且单章不以机械填充达标。

1. 将章节目标拆成场景预算，而不是只在 Prompt 中重复总字数。
2. Provider 返回后先计算各 scene 的证据、冲突、转折与结果覆盖，再判断是否允许定向扩写。
3. 定向换稿只补缺失 scene function 或薄弱证据，不重写已经有效的章节。
4. 把 `target / minimum / actual / revision delta` 写入质量报告和监控面板。
5. 用至少两次新的 exact-12 样本验证均值、P10/P90 和成本变化，避免单样本调参。

退出门：两个新样本均达到总篇幅 90%，无单章低于冻结 minimum，重复率不因扩写恶化，预算仍在授权范围内。

### P0：提高因果可信度

目标：关键转折必须能回答“证据从哪里来、角色为何现在行动、行动付出什么代价”。

1. 在 Rolling Detail 中为关键转折增加 `evidence_source / decision_trigger / irreversible_cost` 可验证字段。
2. Chapter Prompt 只携带当前章相关的因果链，不把整本规划原样重复注入。
3. 质量门区分“缺字段”的确定性 blocker 与“说服力不足”的文学 warning。
4. 冷读抽样优先检查重大转折前后两章，而不是孤立评分单章。

退出门：所有关键转折引用有效上游 source；人工冷读不再出现高风险因果缺口。

### P1：降低流程性重复

目标：连续章节不再反复使用同一种调查、核验、汇报和收尾节奏。

1. 在 accepted prefix 中投影最近三章的 scene function、动作类型、收尾方式和核心意象。
2. Prompt 将这些信息作为“避免复用”约束，但不把风格相似本身升级为硬阻断。
3. 质量 sidecar 输出重复证据、跨度和可替换位置，交由一次定向换稿处理。
4. 统计跨章 scene function n-gram 与结尾动作分布，人工冷读复核自动信号。

退出门：新 exact-12 样本不再产生中风险流程重复 warning，且没有为追求差异而破坏人物动机。

### P1：前端加载性能

目标：角色 3D 图与非当前阶段工作台不进入初始主包。

1. 验证 route stage 页面全部通过动态 import 按需加载。
2. 把 Three.js/force-graph 维持在 Story Bible 独立 chunk，进入页面前不请求。
3. 为生产构建记录主包 gzip、首次交互 chunk 和移动端网络 waterfall。
4. 以真实浏览器而非仅 bundle warning 决定是否继续拆分共享依赖。

退出门：首屏不加载 3D chunk，主路径无 long task，移动视口可在不打开 Story Bible 时完成创建与阶段导航。

### Future：图片独立验收

图片能力继续作为独立波次，必须重新完成 Provider 定价、预算、二进制格式、尺寸、hash、持久化、幂等恢复、人工质量与 CoverBrief → CoverAsset → BookDelivery 依赖验收。通过前不得改变 `image_deferred` 语义。

## 7. 发布门禁记录

| 门禁 | 目标 | 最终结果 |
| --- | --- | --- |
| 后端全量 | pytest 全通过 | 1,339 passed；仅 1 条 Starlette TestClient 未来迁移 warning |
| 前端全量 | Vitest、TypeScript、Vite 全通过 | 74 files / 193 tests；TypeScript 与 Vite 8.2.2 production build 通过 |
| 静态门 | compileall、CSS、目录、格式、diff check | compileall、260 个前端文件格式、182 个 TS 目录结构、CSS、29.8 KiB 首屏 CSS 与 diff check 均通过；Python wheel/sdist 构建成功 |
| 安全门 | CORS、secret、依赖审计 | CORS fail-closed；npm/pip 已知漏洞均为 0；secret 扫描仅命中文档占位符和测试假 key；runtime 与本地日志均被忽略 |
| 浏览器 | 1440、1024、390；console/network/a11y names | 三档均从 UI 创建到 Brief；完成态/暂缓态、响应式、DOM 标签和请求回执通过；console 0 error/warn |
| Evidence | 冷进程验证 immutable bundle | `ready`，issues 0 |
| 干净检出 | 从发布提交重新安装、构建与 smoke | `uv sync --frozen` 与 `pnpm install --frozen-lockfile` 成功；1,339 后端、193 前端、production build、CSS/结构/格式全部复验通过；空数据目录中三条官方 Project 均创建成功 |
| Git | 单一发布提交，工作树干净，未推送 | 单一 `feat!` 发布提交；本地工作树干净；远端未改动 |

## 8. GitHub 推送边界

本轮允许在本地创建发布提交并验证干净检出；不自动删除远端 tag、release 或历史。只有用户明确下达推送指令后，才执行 push、tag 和 GitHub Release 操作。推送前再次核对当前分支、commit SHA、远端目标和工作树状态。
