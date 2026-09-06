# Phase 32 Wave 49：真实 Provider 稳定性与质量探针

日期：2026-08-26

状态：**文本链路已完成一次真实 DeepSeek 稳定性验收；三路线发布门仍未关闭。**

本记录承接 Wave 48 的离线、恢复和 Fake Provider 证据。真实调用只使用冻结的
`provider-deepseek-text` 文本绑定；不恢复历史 Run，不把图片 Provider 的缺失价格伪装成可执行，
也不把结构化通过误报成文学定稿。

## 1. 本轮改动

真实运行暴露了四个最低责任层问题，均先用冻结输入重现后修复：

1. `screenplay_draft` 的结构化示例曾让模型生成非合同字段或空的 `speaker_ref`。现在 Schema 示例只
   展示必填键，Prompt 明确每个 block 只允许 `kind + text`，对白/括号才可绑定冻结 Cast，且对白文本
   统一写入 `text`。
2. 写回提案曾把 `subject_ref / property_key / fact_ref / transition` 混写到 transition 中。现在
   Context 与 correction 固定为 source-bound 规则和唯一 transition 形状，并禁止虚构 subject、占位
   fact ref、无点号 property key 和无现有 fact 的 transition。
3. LangGraph 在写回恢复的 interrupt resume 上会重放整个 commit 节点；旧实现用推进后的 durable
   Outbox 数量重新计算 decision id，导致恢复重放时 id 不一致。现在先重放历史 decision，再生成当前
   decision，Provider/Outbox/Canon/Wiki 副作用保持 exactly-once。
4. 写回重试会把上一次可见的语义绑定错误带入下一次 proposal prompt，使模型能针对实际错误修正，而
   不是得到一个无上下文的通用重试提示。
5. 长篇 `release_smoke` 的 5,000 字默认值与正式 `NovelBriefArtifact` 的 100,000 字路线下限冲突。
   现在长篇 smoke 保持正式 100,000 字下限，只缩小为 1 Part / 1 Volume / 1 Window / 2 章，避免用
   特殊绕过削弱生产 Artifact 合同。

## 2. 真实稳定性证据

### 2.1 剧本样片全链路

Run：`release-smoke-screenplay-20260826-r7`；Workflow：`official-deepseek-fast`；文本模型：
`deepseek-v4-flash`。

| 指标 | 结果 |
| --- | ---: |
| Provider operations | 10 / 10 succeeded |
| transport attempts | 10 次均为 1 |
| 结构化解析 | 10 / 10 `exact_object`，无 repair |
| finish reason | 10 / 10 `stop` |
| accepted Script scenes | 3 |
| committed writeback | 3（前两场各 3 条事实，第三场允许 0 条事实） |
| Run 终态 | `completed`，active stage `export`，无 pending operation |
| 估算文本成本 | `$0.01479104`（本地冻结价格上界，不是账单） |

Fountain 交付文件已落盘，5118 bytes，SHA-256：
`9cf4a39069094c538665778c31c42e72c23656114817e615754208f46d1b6ece`。
对同一组 committed Script 进行纯确定性渲染的 QA 哈希为：

- Fountain：`9cf4a39069094c538665778c31c42e72c23656114817e615754208f46d1b6ece`
- PDF：`144cd7455529506e1f231dbd3f07ce868a049eaa8f058e6ca330b721b1d21965`
- Markdown：`1f8b2434af7e706cb305abbcfb9a415ca8e14777f88c065e401251bda3f011c3`

当前 Run 冻结的 `export_profile=fountain`，因此只有 Fountain 被 Run 的 ExportStore 持久化；PDF 和
Markdown 是同一 committed Artifact 的确定性渲染证据，不应描述为已从该 Run 下载的三个文件。

### 2.2 短中篇真实链路与 fail-closed

Run：`release-smoke-short-20260826-r3`；Workflow：`official-deepseek-balanced`；文本模型：
`deepseek-v4-pro`。

- 首次 Brief 请求遇到真实网络连接错误；同一 operation 在重启 Run 后以
  `transport_attempts=2` 成功，没有生成重复 operation identity。
- 三个 Text unit 均接受，三个写回均 committed；其中一个写回使用 `recovery_count=1` 后成功。
- CoverBrief 已完成，但 Cover 图片 preflight 因 `pricing_unavailable`、固定输出价和来源验证缺失
  显式阻断；没有调用或伪造图片字节，Run 保持可恢复的 `running/cover` 状态。
- 文本侧 12 个已返回 operation 均为 `exact_object` / `stop`；图片 operation 仍 pending，成本状态
  保持 unknown，不做估价填充。

### 2.3 长篇真实文本链路与 fail-closed

Run：`release-smoke-long-20260826-r4`；Workflow：`official-deepseek-deep`；文本模型：
`deepseek-v4-pro`；固定目标为正式长篇下限 100,000 字，容量限制为 1 Part / 1 Volume / 1 Detail
Window / 2 章。

- Brief、Book Architecture、Cast、Volumes、Rolling Detail 和 2 个 Chapter 均通过严格 Artifact 合同；
  10 个文本 operation 均返回 `exact_object`，没有 contract rejection 或 transport retry。
- 两章正文均接受，2 个 writeback receipt 均 committed，事实数分别为 1 和 3；accepted prefix 按
  `chapter_01 -> chapter_02` 单调推进。
- Cover preflight 因图片定价资料缺失 fail-closed，Run 保持 `running/cover`，图片 operation pending，
  没有生成或伪造图片字节。
- 本 Run 文本侧累计 38,387 tokens，按当前冻结 DeepSeek Pro 上界估算 `$0.0697818`；该值不是 Provider
  账单，图片 operation 保持 unknown。

### 2.4 低成本重复探针

在同一冻结文本绑定下连续 3 次发送“只回复稳定性探针”请求，均精确返回 8 个字符，三次响应 SHA-256
一致：`19c39eef695d454530ad12079bea2fbb6c88bafc55e52e69ddf97faed670f4da`。

| 次数 | 延迟 | tokens | finish |
| ---: | ---: | ---: | --- |
| 1 | 2.494s | 27 / 5 / 32 | stop |
| 2 | 0.842s | 27 / 5 / 32 | stop |
| 3 | 0.796s | 27 / 5 / 32 | stop |

其中 tokens 依次为 prompt / completion / total；三次均无 reasoning 字符。

## 3. 离线与静态门

- 后端：`.venv/bin/pytest -q`：`1144 passed, 1 warning`。
- 编译与工作树：`compileall`、`git diff --check` 通过。
- 前端：68 个 Vitest 文件、170 个测试通过；`tsc --noEmit`、Vite production build 通过。
- 前端静态门：structure、CSS、CSS build 全部通过；closure audit 无 runtime legacy marker、无异常
  `features/pipeline` 顶层目录。

## 4. 质量结论与未闭合门

本轮可以确认：DeepSeek 文本 Provider 的请求、严格 JSON 解析、Artifact 合同、写回恢复和确定性交付
在小规模真实 Run 上已经形成可复现链路；网络失败也能在既有 operation 上安全恢复。剧本样片的结构、
引用和交付可做工程稳定性样本。

本轮不能确认：

1. 图片 Provider 的真实调用、封面质量和图片成本；必须先补齐固定输出价、来源 URL、验证时间、估算
   basis 和价格快照，再创建全新短篇/长篇 Run。
2. 三路线全部到 `completed/export`。当前只有剧本样片完成，短篇停在 Cover 价格门，长篇尚未执行真实
   Provider。
3. PDF/Markdown 在同一次 Run 中作为可下载持久化文件存在；当前仅 Fountain profile 已持久化，其余
   两种格式有纯函数渲染哈希。
4. 通篇文学冷读、人物动机、节奏、声音区分和 AI 味；本轮质量证据是结构与链路质量，不是模型自评或
   投稿级文学验收。自动无障碍、规模/性能门也仍未闭合。

长篇 smoke 的尺度、Book Architecture 和 Rolling Detail 合同修复分别发生在 `screenplay r7`、
`short r3` 与长篇 `r1-r3` 之后，因此按照同一 runtime source digest 规则，这些修复前 Run 只能作为
诊断证据，不能与修复后的新 Run 混成最终三路线发布证据。当前长篇 `r4` 是修复后有效的真实文本
证据，但仍停在图片 Cover 门；发布门需要在最终代码冻结后重新创建并完成全部路线。

### 4.1 非阻断文学观察

剧本样片的三场顺序能够读出“档案异常 → 废弃建筑追踪 → 地下室身份揭示”的基本升级，主角林默从
被动发现转为主动追查，第三场也留下了后续悬念。这足以作为小规模可读样本。

同时可见两个需要人工冷读的风险：第三场对白承担了较多设定解释（“我是你……被抹去的那个证人”），
动作段落反复使用暴雨、昏灯、潮湿等氛围词，部分对白的“低声”标注也趋于重复。它们不是本轮的
确定性失败，不触发自动换稿；下一轮应由作者或外部读者判断是否需要压缩解释、增加动机台阶和区分
对白声音。

## 5. 下一步顺序

1. 为 `openai-compatible-image / gpt-image-2` 配置可核验的 pricing snapshot，并在确认成本上限后新建
   短篇 Run，完成 Cover 与三种 Export profile 的明确验收。
2. 以同一图片价格门新建长篇最小 Run，验证 Part/Volume/Window、首章写回、Cover 和 Book Delivery。
3. 对两条新鲜 Run 记录 provider receipt、usage、failure/recovery、Artifact/Evidence/Outbox/Canon/Wiki
   与导出哈希，再做人工文学冷读和浏览器/无障碍/性能门。
4. 只有三路线稳定性证据完整后，才进入 README/版本元数据和 `0.1.0` 发布流程。
