# Phase 14：MiMo / DeepSeek 阶段路由与真实验证

> Phase 16 已把本阶段的双厂商路由扩展为模型级多厂商能力适配；后续实现与验收以 [Phase 16 厂商能力适配合同](./phase-16-provider-capability-adapters.md) 为准。

## 目标

让合规的 MiMo 按量 API 或 DeepSeek API 按阶段使用合适模型，同时保持公开版默认工作流不依赖厂商密钥。

## 路由决策

| 阶段 | MiMo 按量 API | DeepSeek API | 原因 |
| --- | --- | --- | --- |
| 小说信息推荐 | `mimo-v2.5-pro` | `deepseek-v4-pro` | 人物、阵营、关系边和约束遵循需要高推理能力 |
| 全书梗概 | `mimo-v2.5` | `deepseek-v4-flash` | 结构字段稳定，优先效率与成本 |
| 分卷大纲 | `mimo-v2.5-pro` | `deepseek-v4-pro` | 跨卷因果、节拍和伏笔分布需要全局保持 |
| 章节细纲 | `mimo-v2.5-pro` | `deepseek-v4-pro` | 场景序列和 handoff 必须逐字承接 |
| 正文生成 | `mimo-v2.5-pro` | `deepseek-v4-pro` | 承接、人物知识边界与文学执行优先 |
| AI 封面文案 | `mimo-v2.5` | `deepseek-v4-flash` | 只生成 brief/prompt，图片仍由独立 Provider 负责 |
| 导出 | 系统 | 系统 | 只整理 manifest、校验和下载包 |

## 接入合同

- MiMo 按量 API 使用 `https://api.xiaomimimo.com/v1` 与 `api-key` 请求头。小说文本只允许 `mimo-v2.5-pro`、`mimo-v2.5`，请求使用 `max_completion_tokens` 和 `thinking: {"type": "disabled"}`。
- MiMo Token Plan 的 `tp-...` 凭证仅限 AI 编程工具。应用后端的模型发现、Provider 测试、阶段探针和运行前 readiness 均返回 `provider_policy_blocked`，不发送外部请求。
- DeepSeek 使用 `https://api.deepseek.com`，当前模板使用 `deepseek-v4-pro`、`deepseek-v4-flash`；旧 `deepseek-chat` / `deepseek-reasoner` 不作为新配置默认值。
- API Key 始终由本机 Secret Store 或临时环境变量提供，不进入工作流 JSON、日志或 HTTP 响应。

## 本轮复核（2026-07-30）

- 阶段路由已抽到 `src/novel_workflow/workflows/stage_routing.py`。启用 MiMo 按量 API 时优先使用 MiMo；未配置时可使用 DeepSeek V4；默认工作流仍保持通用 Provider。
- readiness 返回物化后的实际阶段模型，并在模型目录与阶段配置不一致时阻断，避免运行到中途失败。
- MiMo Token Plan 历史探针返回 HTTP `401`；本轮不再重试暴露的 Token Plan 凭证，也不把它写入配置。该凭证应立即撤销并重置。
- 使用临时 DeepSeek 凭证完成 `GET /models`，返回 `deepseek-v4-flash`、`deepseek-v4-pro`；最小非思考文本请求 HTTP 200，返回 12 tokens。
- `deepseek-v4-pro` 信息推荐探针通过 `StoryBriefContract`（5 个标题、2 个人物、1 条关系）；`deepseek-v4-flash` 梗概探针通过 `SummaryContract`。凭证未写入仓库或持久配置，测试后应立即撤销并重置。
- `deepseek-v4-pro` 分卷大纲在 `3200` tokens 下通过 `OutlineContract`（低于生产预算 `4200`）；章节细纲在生产预算 `6000`、`120s` 阶段超时下通过 `DetailOutlineContract`（3 章）。探针现直接读取生产阶段预算与超时，避免低上限造成假失败。
- `deepseek-v4-pro` 正文通过 `ChapterProseContract`，`deepseek-v4-flash` 封面文案通过 `CoverContract`。
- 定向回归覆盖 MiMo `api-key` 请求头、`max_completion_tokens`、Token Plan 合规阻断、阶段模型目录不匹配和 DeepSeek 路由；全量后端 `327 passed, 1 skipped`，前端 `496 passed`，生产构建通过。

```bash
DEEPSEEK_API_KEY='在本机环境注入，不要写入仓库' \
  .venv/bin/python -m novel_workflow.providers.smoke \
  --provider-id deepseek-text --stage-id info --max-tokens 1200
```

## 质量边界

模型通过结构合同只代表可进入人工审阅和后续质量阀门，不代表正文可以跳过人工确认、连续性检查或正式写回。任何关系端点、场景交接、Wiki 事实和章节承接错误仍必须由后端合同阻断。
