# Phase 16：厂商能力适配与模型级请求合同

> 状态：模板、请求预检、模型级参数、生产准入、目录协议、图片协议保护与 GLM-5.2 真实小流量探针已完成；Run E 仍为 `recovery_required`，后续整书验收必须从新的稳定分支 Run 开始
>
> 日期：2026-08-01
>
> 前置合同：[阶段产物合同](./stage-artifact-contract.md)、[Phase 14 模型路由](./phase-14-mimo-stage-routing-and-live-validation.md)、[Phase 15 整书验收](./phase-15-full-book-live-acceptance.md)

## 1. 目标与边界

Yotsuba Ink 不再把“OpenAI-compatible”视为能力相同。Provider 模板必须同时回答：

1. 当前模型是否支持 `json_schema`、`json_object` 或只能依赖 Prompt。
2. 厂商扩展参数应直接传给 SDK，还是放入 `extra_body`。
3. `max_tokens`、`max_completion_tokens`、采样参数和思考参数如何组合。
4. 同一厂商不同模型支持哪些推理档位。
5. Schema 不兼容时能否在请求前降级，避免一次已计费 400 后再偷偷重试。
6. 图片接口是同步生成、专用图片端点还是提交/查询异步任务，能否由当前适配器安全执行。
7. 模板是“生产可用”“仅评估”还是“外部工具专用”，连接测试成功能否进入阶段探针与自动路由。

上游只保证返回格式；业务正确性仍由本地 Pydantic 阶段合同、质量阀门和正式写回门禁负责。任何 JSON 成功都不能绕过 Artifact 校验。

本轮静态覆盖为 31 个 Provider 模板：22 个文本模板与 9 个图片模板。`custom` 模板只声明协议边界，不冒充厂商能力；`gateway` 模板只声明网关自身公开保证，不继承被路由原厂的私有参数；带具体厂商和模型的模板才允许保存模型级请求覆盖。所有模板都关闭 SDK 隐式重试，避免一次用户动作产生不可见的二次计费。设置页同时展示生产准入状态：生产模板可进入 readiness、Registry、阶段探针和自动路由；评估模板只允许显式连接测试；外部工具模板连应用后端连接测试也被阻断。

## 2. 核心官方厂商矩阵

| 模板 | 当前模型 | 结构化输出 | 思考/采样合同 | 默认边界 | 官方资料 |
| --- | --- | --- | --- | --- | --- |
| OpenAI | `gpt-5.6-sol/terra/luna` | strict JSON Schema；请求前转官方子集 | `reasoning_effort`；不发送 temperature/top_p | Schema 不兼容时请求前降为 JSON Object | [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)、[Models](https://developers.openai.com/api/docs/models) |
| DeepSeek | `deepseek-v4-pro/flash` | JSON Object；Prompt 必须含 JSON 与示例 | `thinking` 进入 `extra_body`；思考强度官方只保证 high/max（low/medium 映射 high） | 未列举任务显式关闭思考；空 content 显式报错；Prefix 仅显式纯文本 Beta | [JSON Output](https://api-docs.deepseek.com/zh-cn/guides/json_mode)、[Prefix Completion](https://api-docs.deepseek.com/zh-cn/guides/chat_prefix_completion)、[Thinking](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode)、[模型与价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) |
| MiMo API | `mimo-v2.5-pro/2.5` | JSON Object；Prompt 含字段示例 | `max_completion_tokens`；思考节点不发采样参数，正文关闭思考并只发 `temperature` | Token Plan 禁止应用后端执行，只允许按量 API | [OpenAI API](https://mimo.mi.com/docs/zh-CN/api/chat/openai-api)、[Structured Output](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/structured-output)、[模型选型](https://mimo.mi.com/docs/quick-start/summary/model) |
| DashScope/Qwen | `qwen3.7-max`、`qwen3.7-plus`、`qwen3.7-flash`、`qwen3.6-flash` | 当前结构化输出专题明确列出四个系列，统一使用 JSON Object + 本地校验 | JSON Mode 不发 `max_tokens`；复杂阶段流式思考，正文关闭思考 | 结构阶段优先 Plus，轻量结构阶段可用 3.7/3.6 Flash；Max 可用于质量优先正文和显式结构探针 | [结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output)、[深度思考](https://help.aliyun.com/zh/model-studio/deep-thinking)、[模型清单](https://help.aliyun.com/zh/model-studio/text-generation-model) |
| Kimi/Moonshot | `kimi-k3`、`kimi-k2.6` | K3 使用 strict JSON Schema；K2.6 使用非 strict Schema；两者仍过本地校验 | K3 始终思考，使用顶层 `reasoning_effort=low/high/max`；K2.6 使用 `thinking`；统一使用 `max_completion_tokens` | K3 作为官方当前默认；K2.6 作为关闭思考的轻量回退；Partial 仅限显式纯文本且不得与 `response_format` 混用 | [Kimi Chat API](https://platform.kimi.com/docs/api/chat)、[Structured Output](https://platform.kimi.com/docs/guide/response_format)、[模型参数](https://platform.kimi.com/docs/api/models-overview)、[Partial Mode](https://platform.kimi.com/docs/api/partial)、[模型列表](https://platform.kimi.com/docs/models) |
| 智谱 GLM | `glm-5.2/5.1/4.7` | JSON Object；Prompt 必须给字段结构示例 | `thinking` 进入 `extra_body`；仅 5.2 发送 `reasoning_effort`；大型 Detail 流式累积 | 未列举任务显式关闭思考；5.1/4.7 不接收 5.2 专属推理档位 | [结构化输出](https://docs.bigmodel.cn/cn/guide/capabilities/struct-output)、[GLM-5.2](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2)、[深度思考](https://docs.bigmodel.cn/cn/guide/capabilities/thinking) |
| Google Gemini | `gemini-3.6-flash`、`gemini-3.5-flash-lite` | OpenAI 兼容 JSON Schema | `reasoning_effort`；不与原生 thinking config 混用 | 复杂 Schema 先本地预检，仍需本地合同校验 | [OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai) |
| Anthropic Claude | `claude-sonnet-5/opus-5` | OpenAI 兼容层忽略 response_format | 兼容层也忽略 reasoning_effort | 连接测试可用，但 readiness、Registry、阶段探针和自动路由全部阻断；生产结构化输出待原生 Claude Adapter | [OpenAI SDK compatibility](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk)、[Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) |

Kimi 官方 Chat API 当前把 K3 列为默认模型，并明确 K3 始终推理、使用顶层 `reasoning_effort`；K2.6 仍保留 `thinking` 开关。模板因此把 K3 放入默认候选，K2.6 作为成本与正文回退；Partial 仍只在明确的纯文本实验任务中启用，不能和结构化输出混用。TokenHub 的实时目录仍需单独探针，网关可用不等于 Moonshot 直连接口合同相同。

### 2.1 官方证据到模板的转换规则

每个模板至少核对模型目录、Chat/Responses 请求字段、结构化输出、思考参数、流式响应和实验能力六类资料。资料冲突时采用以下优先级：

1. 具体模型详情页高于厂商通用能力专题页；同级官方资料冲突时取保守交集。2026-07-31 再核验时，Qwen 结构化输出专题已明确列出 Qwen3.7 Max 系列，因此 Max 恢复 JSON Object；文本模型总表若仍出现同步滞后，不再覆盖该专题的具体请求合同，所有结果仍执行本地 Pydantic 校验与最小探针。
2. 原厂模型合同高于聚合平台的宣传页；聚合网关仍需以它自己的 `/models` 与参数支持为准，不能直接复制原厂 `thinking` 或 Schema 保证。
3. 当前账号目录高于静态候选名。静态模板只提供推荐候选，readiness 与最小探针决定能否执行。
4. Beta、Partial、Prefix、Predicted Outputs 等能力必须显式启用，且不得与结构化输出、恢复预算或正式写回门禁冲突。
5. 所有远端格式保证之后仍执行本地 JSON 解析、Pydantic Artifact、领域引用、连续性与写回校验。

模板通过 `capability_docs` 保存官方证据入口；存在模型级差异时，通过 `ModelCapabilityProfile` 保存模型匹配、请求覆盖、`verified/conservative/experimental` 证据状态和冲突说明。能力元数据由服务端模板与服务端目录同步拥有，前端提交的伪造值不会覆盖已发现结果；切换厂商模板时会清空旧目录能力，避免把上一家厂商的结论带到新模板。

## 3. 兼容层与网关矩阵

| 模板 | 当前策略 | 不能静态承诺的部分 | 官方资料 |
| --- | --- | --- | --- |
| SiliconFlow | JSON Object + JSON 示例 + 本地校验 | 模型支持清单会变化，不宣称 Schema 保证 | [JSON mode](https://docs.siliconflow.cn/en/userguide/guides/json-mode) |
| OpenRouter | JSON Schema + `provider.require_parameters=true` + `allow_fallbacks=false` | 无兼容上游时显式失败；网关不得在本地预算与审计之外偷偷切换上游 | [Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)、[Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection) |
| Groq | GPT-OSS 走 strict JSON Schema；使用 `max_completion_tokens`；按阶段发送 low/medium/high 推理强度 | strict 支持按模型变化，必须模型级匹配 | [API Reference](https://console.groq.com/docs/api-reference)、[Structured Outputs](https://console.groq.com/docs/structured-outputs) |
| Together | JSON Schema + Prompt 内 Schema 示例；GPT-OSS 按阶段发送 low/medium/high 推理强度 | 实际支持范围依实时 Serverless/Dedicated 目录 | [Structured outputs](https://docs.together.ai/docs/inference/chat/structured-outputs)、[Reasoning](https://docs.together.ai/docs/inference/chat/reasoning) |
| xAI | Grok 4.5 的当前 Chat Adapter 走 strict JSON Schema、low/medium/high 推理档位；缓存键通过 `x-grok-conv-id` 请求头发送 | xAI 已把 Responses API 作为推荐路径、Chat Completions 标为 deprecated；Responses 的 `prompt_cache_key` 与事件外形需独立 Adapter | [Structured Outputs](https://docs.x.ai/developers/model-capabilities/text/structured-outputs)、[Prompt Caching](https://docs.x.ai/developers/advanced-api-usage/prompt-caching/maximizing-cache-hits)、[Responses 对比](https://docs.x.ai/developers/model-capabilities/text/comparison) |
| Mistral | JSON Schema；JSON Object 只作降级 | 原生 SDK 和 OpenAI 请求结构的细节差异 | [Chat API](https://docs.mistral.ai/api)、[Structured Outputs](https://docs.mistral.ai/studio-api/conversations/structured-output) |
| Fireworks | JSON Schema + Prompt 示例 | 开启 response_format 会关闭 reasoning 输出 | [Structured Outputs](https://docs.fireworks.ai/structured-responses/structured-response-formatting) |
| Cerebras | GPT-OSS 120B 走 strict JSON Schema；Schema 超过 5000 字符时请求前降级 | 其他模型 reasoning_effort 值不同 | [Structured Outputs](https://inference-docs.cerebras.ai/capabilities/structured-outputs) |
| 火山方舟 | Prompt-only JSON + 本地校验 | 模型使用部署 Endpoint ID，能力取决于具体部署，暂不静态发送 response_format | [方舟文档](https://www.volcengine.com/docs/82379) |
| TokenHub | 公共 Chat 接口支持 JSON Schema；DeepSeek/MiniMax 按模型专页降为 JSON Object 或 Prompt-only；Kimi/GLM 使用网关专属参数 | 不把直连厂商参数原样复制给网关；Responses 仍需独立 Adapter | [语言模型调用概览](https://cloud.tencent.com/document/product/1823/130079)、[DeepSeek](https://cloud.tencent.com/document/product/1823/132248)、[GLM](https://cloud.tencent.com/document/product/1823/132061)、[Kimi](https://cloud.tencent.com/document/product/1823/132232)、[MiniMax](https://cloud.tencent.com/document/product/1823/132246) |
| LiteLLM | Prompt-only JSON + 本地校验 | Proxy 可转换 `response_format`，但支持范围需按模型查询 `get_supported_openai_params` / `supports_response_schema`；普通 `/models` 不提供足够静态保证 | [LiteLLM Proxy](https://docs.litellm.ai/docs/simple_proxy)、[Structured Outputs](https://docs.litellm.ai/docs/completion/json_mode) |
| Portkey | Prompt-only JSON + 本地校验；`/v1/models` 使用工作区模型目录 | Chat、Responses 与 Messages 均可转换，但具体上游能力仍由模型和路由配置决定；当前 Chat Adapter 不冒充 Open Responses Adapter | [Models](https://portkey.ai/docs/api-reference/inference-api/models/models)、[Universal API](https://portkey.ai/docs/product/ai-gateway/universal-api)、[Open Responses](https://portkey.ai/docs/product/ai-gateway/responses-api) |

### 3.1 模型目录协议

- 通用目录默认请求模板的 `models_endpoint_path`，目录鉴权与生成鉴权可以分开声明。Portkey 的 `/v1/models` 使用官方 `x-portkey-api-key`；MiMo API 使用 `api-key`；其他 OpenAI 兼容目录默认使用 Bearer。
- Portkey 正式目录允许 `@provider/model` 形式。模型 ID 清洗只放行有限字符和长度，不再错误删除合法的前导 `@`。
- SiliconFlow 图片目录显式发送 `type=image`，避免把文本、音频或视频模型混入封面模型候选。
- OpenRouter 文本目录的 `supported_parameters` 是字符串数组；专用图片目录是参数描述对象。两种形态都只提取经过白名单清洗的参数名，不持久化枚举值、价格或任意嵌套对象。
- 只有 OpenRouter 模板把目录参数用于请求前能力阻断。LiteLLM、Portkey 和普通厂商目录只更新当前账号可见模型，不会反向改写静态结构化输出合同。

### 3.2 图片 Provider 协议矩阵

| 模板 | 当前模型/端点 | 请求与响应合同 | 执行策略 | 官方资料 |
| --- | --- | --- | --- | --- |
| OpenAI | `gpt-image-2`，`/v1/images/generations` | `size`、`quality`、`n`；官方模板读取 `data[]` 图片结果 | 默认可执行；兼容网关模板显式请求 Base64 | [GPT Image 2](https://developers.openai.com/api/docs/models/gpt-image-2) |
| 智谱 | `glm-image`，兼容 `cogview-4-250304` | `size`；同步返回 `data[0].url` | 默认可执行，URL 仍经过公网 HTTPS 与大小校验 | [GLM-Image](https://docs.bigmodel.cn/cn/guide/models/image-generation/glm-image)、[图像 API](https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E5%9B%BE%E5%83%8F%E7%94%9F%E6%88%90) |
| SiliconFlow | `Kwai-Kolors/Kolors` | `image_size`；读取 `images[]`；目录使用 `type=image` | 默认可执行，模型目录需实时确认 | [Images API](https://docs.siliconflow.cn/cn/api-reference/images/images-generations)、[Models API](https://docs.siliconflow.cn/en/api-reference/models/get-model-list) |
| OpenRouter | 专用 `/api/v1/images` 与 `/images/models` | 像素尺寸使用 `size`；读取 Base64 `data[]`；保存清洗后的参数描述键 | 默认可执行，具体模型参数以 endpoint capability 为准 | [Image Generation](https://openrouter.ai/docs/guides/overview/multimodal/image-generation) |
| xAI | `grok-imagine-image-quality` | 封面尺寸转 `aspect_ratio`，分辨率用 `resolution=1k` | 默认可执行 | [Imagine](https://docs.x.ai/developers/model-capabilities/imagine)、[Model](https://docs.x.ai/developers/models/grok-imagine-image-quality) |
| Together | Imagen/FLUX/Qwen Image | 默认 `width`、`height`、`response_format=base64`、`output_format=png`；Kontext 模型级覆盖为 `aspect_ratio` | 默认可执行；Schnell 按 API Schema、参数表和官方示例使用宽高，Kontext 覆盖保持 conservative，解除保守状态前需真实最小探针 | [Images API](https://docs.together.ai/reference/post-images-generations)、[模型参数](https://docs.together.ai/docs/inference/images/parameters) |
| 腾讯 TokenHub | `hy-image-v3.0`，`/v1/api/image/submit` + `/v1/api/image/query` | 首次提交返回 job id，随后轮询到 completed 再读取 `data[]` | 当前明确阻断；不能冒充同步 `/images/generations` | [TokenHub 图像生成](https://cloud.tencent.com/document/product/1823/130080) |

## 4. 请求构造合同

### 4.1 Schema 预处理

`json_schema` 请求使用原始 Pydantic Schema 作为本地真相，另生成一份只供上游约束解码的 Schema：

- 移除 `default`、长度、范围、正则和数组数量等上游不稳定约束。
- 每层 object 补 `additionalProperties: false`。
- strict 模式把所有 properties 写入 required；本地原始 Pydantic 仍负责默认值与完整约束。
- 对厂商额外限制（例如 Cerebras 的 500 个枚举值）在请求前降级，不把一次 400 计费错误变成隐式重试。
- 在请求前检查根对象、关键字、属性数、嵌套深度和序列化大小。
- 不兼容时直接使用 `json_object`，并记录降级原因；不得先付费失败后重试。

DeepSeek、MiMo、Qwen、GLM 与 SiliconFlow 等 JSON Object 模式会从 Schema 生成紧凑 JSON 实例，而不是把 JSON Schema 本身冒充“返回样例”。Together 与 Fireworks 的官方合同要求 Schema 同时出现在 Prompt 与 `response_format`，仅这类模板额外注入完整 Schema。

### 4.2 参数位置

- OpenAI SDK 已声明字段，例如 `reasoning_effort`、`max_completion_tokens`，直接作为调用参数。
- DeepSeek、MiMo、GLM 的 `thinking`，Qwen 的 `enable_thinking`，OpenRouter 的 provider 路由要求，统一放入 `extra_body`。
- OpenRouter 显式设置 `provider.require_parameters=true` 与 `allow_fallbacks=false`：前者保证上游不能静默丢弃 Schema，后者保证一次 Yotsuba Ink Provider 尝试只对应一个可审计的网关选择；跨 Provider 回退只能由本地 fallback、预算和事件链触发。
- DeepSeek 上下文硬盘缓存默认开启，不发送虚构的缓存参数；稳定命中依赖 system 和公共约束位于请求前缀，返回中的 `prompt_cache_hit_tokens/prompt_cache_miss_tokens` 只用于用量观测。
- 模板参数先合并，随后按具体模型覆盖，最后应用阶段参数；模型级规则优先级最高。
- DeepSeek 启用思考时不再发送 `temperature`/`top_p`；官方明确说明这些采样参数在思考模式下无效。关闭思考的正文节点仍可保留温度以控制语言随机性。
- GLM-5.2 的 Detail 使用官方流式响应持续接收 `delta.content`，在本地拼成完整 JSON 后再解析。真实 Run E 证明“流式”只能避免长连接空等，不能解决单次产物过大的截断问题。
- Run E 的 Detail 在 `16000` 与 `32000` 单请求、以及“每卷 3 章 × 14000”首次分批中均以 `finish_reason=length` 截断。稳定策略改为每章 1 批、每批 `12000` tokens、共 9 批，并将 GLM-5.2 Detail 从 `max` 调整为官方支持的 `high` 推理档位；最终合并后统一执行 9 章、18 场、引用与连续性校验。
- 第二章起显式注入上一章末尾 `hook`、`continuity_notes` 与最后一场 `handoff_out`，并附带此前成功章节的紧凑 ledger；Prefix/Partial 不参与结构化 Detail。批次来源签名变化时不得复用旧草稿。
- Moonshot 官方直连默认 K3：结构化节点使用 JSON Schema、Prompt 字段示例和本地 Pydantic 三重校验；K3 按阶段发送 `reasoning_effort`，K2.6 关闭思考用于轻量节点；两者统一发送 Chat API 推荐的 `max_completion_tokens`，不主动发送已弃用的 `max_tokens`。
- Moonshot Chat API 和 Mistral Chat API 均公开支持 `prompt_cache_key`。编排层按 `Run + 阶段节点` 生成稳定键，Provider 在发送前做 SHA-256，不把作品名、Prompt、密钥或其他敏感内容放入缓存键；DeepSeek 等未声明该字段的模板不会误发。
- xAI Chat Completions 不接收请求体 `prompt_cache_key`；同一散列键必须通过 `x-grok-conv-id` 请求头发送。只有未来独立 Responses Adapter 才能把 `prompt_cache_key` 放入请求体。
- MiMo 2.5 Pro 在 Info、大纲、细纲和模型评审启用思考，在 Summary、正文和后处理关闭；思考开启时不发送采样参数，关闭时只发送 `temperature`，让正文保留可控的语言随机性。`mimo-v2.5` 继续承担轻量节点。
- Qwen 3.7 Max/Plus/Flash 的 Info、Outline、Detail 与模型评审使用 `stream=true`、`enable_thinking=true` 和分阶段 `thinking_budget`；适配器只累积最终 `delta.content`，完整内容到齐后再解析。Summary、正文和章后抽取关闭思考，避免推理预算挤占文本与结构预算。远端格式约束按具体模型独立决定，不能由同一厂商模板一刀切。
- 自动结构路由只使用当前官方资料交集：Info/Outline/Detail 优先 3.7 Plus，Summary/Cover 优先 3.6 Flash；Text 可优先 3.7 Max。四个当前系列都可发送官方 JSON Object；正文纯文本任务不发送 `response_format`，结构任务仍需 Prompt 中的 JSON 关键词、格式示例和本地 Pydantic 校验。
- Groq 所有 Chat 模型统一使用当前 API 推荐的 `max_completion_tokens`，GPT-OSS 才发送 low/medium/high `reasoning_effort`；Together 的 GPT-OSS 使用同一阶段强度分配，且 Schema 必须同时进入 Prompt 和 `response_format`。两者的其他模型不能继承 GPT-OSS 专属推理参数。
- Groq 的 `qwen/qwen3.6-27b` 只使用官方列出的 `reasoning_effort=default/none`：Info、Outline、Detail 与模型评审使用 `default`，并设置 `reasoning_format=hidden` 让 JSON content 不混入思考文本；Summary、正文与章后处理使用 `none`，且不再发送 `reasoning_format`。
- Qwen 3.8 Max Preview 当前仅标注为 Token Plan 能力，不进入应用后端按量模板；Kimi K2.7 Code 系列只面向编程任务，也不进入小说阶段的推荐路由。两类模型即使出现在实时目录，也只能由用户显式选择并通过阶段探针后使用。
- TokenHub 2026-07-28 的公共 Chat 文档列出 `json_schema`，但模型专页同时给出更窄合同：DeepSeek 只示例 `json_object` 且不建议和思考混用；MiniMax M3 同样应关闭 adaptive thinking 后再用 JSON Object，M2.x 无法关闭思考，因此只做 Prompt + `reasoning_split` + 本地校验；Kimi K3 使用 `max_completion_tokens`、固定采样参数和网关当前唯一的 `reasoning_effort=max`；GLM-5.2 的 `reasoning_effort` 放入 `extra_body`。这些规则已拆为独立 TokenHub 模型能力模块，不能继承直连模板。
- xAI Grok 4.5 在当前 Chat Adapter 中使用顶层 `reasoning_effort`：Summary/正文/后处理为 `low`，Info/Outline 为 `medium`，Detail/模型评审为 `high`；推理不能完全关闭。Chat Completions 虽仍可调用但已被官方标为 deprecated，因此该模板不得吸收 Responses 专属的 `reasoning.effort`、`prompt_cache_key` 或响应事件字段。
- Gemini 3.6 Flash 继续按复杂度使用 low/medium/high；Gemini 3.5 Flash-Lite 仅在 Summary 与章后轻量处理使用其官方支持的 `minimal`。该模型级覆盖只属于 `gemini-text`，不能泄漏到 OpenAI 模板。
- Assistant Prefix/Partial 仅允许显式纯文本 `chapter_text` 任务；用于其他任务时在本地抛出 `unsupported_assistant_prefill`。它与结构化输出冲突时抛出 `provider_feature_conflict`，两种情况都不发送请求。
- Kimi Partial 对当前官方文档明确支持的 K3/K2.6 开放，但只接受显式纯文本 `chapter_text`；响应不包含 leading text，因此适配器逐字拼回原前缀，空白和尾换行不得被清理。K3 的结构化主链仍不会自动启用 Partial。
- Mistral Prefix 复用最后一条 assistant 消息的 `prefix=true`，只对显式纯文本正文实验开放；Mistral 返回内容已包含前缀语义，不做二次拼接。
- 自定义兼容地址、火山 Endpoint、LiteLLM 与 Portkey 默认不发送 `response_format`。只有选择具备官方静态合同的厂商模板，或未来实时能力元数据明确支持时，才启用远端格式约束。
- OpenAI 当前建议新项目优先使用 Responses API，其中结构化输出位于 `text.format`、推理强度位于 `reasoning.effort`；Portkey Open Responses 使用同一外形并负责上游转换。两者都需要独立 Responses 请求与事件适配器，不能把字段塞进当前 Chat Completions Adapter。
- Anthropic OpenAI 兼容层明确忽略 `response_format` 和 `reasoning_effort`，因此模板只用于评估。连接测试仍用于鉴权和基本可达性确认，但 readiness 返回 `provider_workflow_blocked`，Registry、阶段探针和自动路由均拒绝该模板。生产级 Claude Structured Outputs 需要原生 Messages Adapter，使用 `output_config.format` 与原生 effort/thinking 合同。

### 4.3 阶段输出模式与正文上下文

- Info、Summary、Outline、Detail、Cover brief、章后抽取和模型评审继续使用 JSON Object/JSON Schema；这些节点的核心产物是可编辑、可写回的结构对象。
- `chapter_text` 正文生成、短场完整性修复、整章质量修订和正文换稿使用纯文本调用。Provider 返回后由编排层包装为 `{chapter_title, content}`，再执行 `ChapterProseContract`；不得为了复用结构化适配器要求模型把长篇正文塞入 JSON 字符串。
- 章后摘要、Wiki、人物变化、伏笔与跨章携带状态由独立 `chapter_postprocess` 结构化调用从最终正文抽取。正文调用不得同时生成这些字段，避免模型把文学执行降格为结构摘要。
- 正文 Prompt 上限为 16000 字符。系统只注入当前章细纲、当前 SceneContract、章节上下文包、上一章尾文、必要人物状态、Voice Spec、硬规则和相关伏笔；完整 `detail_outline`、重复 Story Brief、无关人物与参考层不得进入单场调用。
- 请求审计只记录模板、协议、模型、输出模式、Prompt/输出字符数、思考状态、流式状态、Token 字段和 finish reason；不得记录 Prompt 全文、作品正文、API Key 或其他秘密。
- DeepSeek Prefix、Kimi Partial 和 Mistral Prefix 只有显式 `_assistant_prefill` 实验开关才启用。默认正文连续性靠 `previous_chapter_tail + transition_directive + SceneContract`，不自动把上一章尾文作为 assistant 前缀，避免 Kimi Partial 结果拼接造成正文重复。通用 `StageRegistry.execute(chapter_text)` 与场景化正文入口现在统一把纯文本包装为 `{chapter_title, content}` 后再交给本地正文合同。

### 4.4 错误与重试

- DeepSeek 文档所述结构化空响应返回 `structured_empty_content`，不隐藏重试。
- 明确的 `finish_reason=length` 返回 `output_truncated`，Provider 内不做隐藏重试。只有用户从检查点显式恢复后，Usage Gate 才能重新授权下一次调用。
- OpenAI SDK 的自动重试默认关闭。不同兼容厂商未统一承诺 Idempotency-Key 语义，429/5xx/连接失败不得在预算和审计事件之外隐式再次调用。
- Schema 400、能力不支持、鉴权、余额、策略阻断不得被改写成“换个参数再试”的隐式计费请求。

## 5. 阶段模型路由

| 阶段 | 旗舰/平衡模型 | 经济模型职责 |
| --- | --- | --- |
| Info | Sol/Terra、V4 Pro、MiMo Pro、Qwen Plus、K3、GLM 5.2、Gemini Flash | 不默认降级，先建立人物与硬规则 |
| Summary | Luna、V4 Flash、MiMo 2.5、Qwen Flash、K2.6、GLM 5.1、Gemini Flash-Lite | 稳定结构抽取与成本控制 |
| Outline | Terra/Pro/Plus/K3/GLM 5.2/Gemini Flash | 维持跨卷因果与伏笔分布 |
| Detail | Sol、V4 Pro、MiMo Pro、Qwen Plus、K3、GLM 5.2、Gemini Flash | 复杂场景序列、handoff 与写回候选 |
| Text | Terra、V4 Pro、MiMo Pro、Qwen Plus、K3、GLM 5.2、Gemini Flash | 文学执行优先，不使用轻量模型自动替代 |
| Cover brief | Luna、V4 Flash、MiMo 2.5、Qwen Flash、K2.6、GLM 5.1、Flash-Lite | 只生成 brief/prompt，图片由独立 Provider 负责 |
| Export | 系统本地 | 不调用文本模型 |

路由只选择 Provider 已发现目录中的候选模型。候选缺失时回退该 Provider 的默认模型，而不是制造 `model_not_discovered`；用户手动选择目录外模型时 readiness 仍必须阻断。

## 6. 稳定能力与实验能力

默认稳定能力：

- 模型目录发现、阶段模型匹配、JSON Schema/JSON Object、Prompt 示例、本地 Pydantic 校验。
- 模型级思考参数、Token 字段、采样字段和 `extra_body` 映射。
- 请求前 Schema 降级、显式空响应、截断和能力冲突错误。

实验能力：

- DeepSeek Prefix Completion 只允许纯文本 `chapter_text` 显式传入 `_assistant_prefill`，使用 Beta Base URL；当前纯文本正文主链默认仍不启用，只作为可单独验收的实验能力。
- Kimi Partial Mode 只允许 K3/K2.6 的显式纯文本任务；结构化任务永远拒绝混用，返回时逐字补回服务端省略的 leading text。
- Mistral Prefix 只允许显式纯文本任务；它与 DeepSeek Prefix、Kimi Partial 一样不进入结构化正文主链。
- Claude 原生 Structured Outputs 尚未实现，兼容模板不能冒充生产适配器。
- 火山方舟、LiteLLM、Portkey 的具体模型格式能力必须在后续模型级元数据或最小探针中确认。三者已支持模型目录同步，但目录可见不等于格式能力可用。TokenHub Chat Completions 已按模型族选择 JSON Schema、JSON Object 或 Prompt-only；Responses API 的 `text.format=json_schema`、`reasoning.effort` 与事件结构仍需要独立 Responses Adapter，不能冒充现有 Chat Completions 实现。
- 腾讯 HY-Image-V3.0 必须等原生 submit/query 适配器、轮询超时和幂等测试完成后才能解除执行阻断。
- Together 图片参数页对 FLUX Schnell 的概述文字与 API Schema、模型参数表和可执行示例存在冲突；当前取保守交集使用 `width/height`。Kontext 的 `aspect_ratio` 保留为模型级 conservative 合同，必须经过真实请求快照后才可标记 verified。

### 6.1 静态稳定合同与实时目录

- 模板保存官方文档可长期验证的参数语义、协议形态和安全边界，是可测试的静态合同。
- 模型目录只刷新当前账号可见的模型 ID，不得反向改写 `supports_json_schema`、Token 字段或思考参数。OpenRouter 的参数元数据仅用于请求前阻断已知不支持的模型。
- 阶段路由只从“静态候选与实时目录的交集”选模型；交集为空时使用用户已保存的默认模型并由 readiness 显式提示。
- 新模型先经过目录发现、最小格式探针、阶段合同探针和小流量成本验证，再加入稳定候选；不得仅凭营销页名称进入生产路由。
- 本轮官方文档核验日期为 2026-08-01。网页能力可能变化，后续升级必须保留来源日期与请求快照测试。
- `agent-reach` 的 Exa 官方域名检索先返回 LiteLLM、Portkey 与 OpenAI 官方资料，随后触发免费额度 429；证据收集按技能降级为官方域名定向检索和官方页面直读，未使用博客、论坛答复或聚合文章决定请求参数。

## 7. 验收顺序

1. Provider 请求快照、模型级参数和阶段路由测试全绿。
2. 前端模板类型、Provider 设置测试与生产构建全绿。
3. 本轮 Provider 能力适配后的全量后端回归全绿：`502 passed, 1 skipped`；前端基线为 `126` 个测试文件、`497` 条用例和生产构建全绿。
4. 只对已保存且未暴露的新密钥执行 `/models`，不产生文本费用。
5. 对当前真实主 Provider 执行一个最小 JSON Object 探针和一个阶段 Pydantic 探针。
6. 探针成功后从检查点恢复 Phase 15 Run E；旧 Detail 单请求范围归档为 legacy，用显式策略升级事件开启新批次预算，不隐藏任何二次计费请求。

任何曾在对话、截图、日志或命令中暴露的密钥都必须撤销重置，不进入文档、SQLite、Run State、验收报告或 Git。

## 8. 真实探针记录

2026-07-31 使用本地 Secret Store 中未输出过内容的 `openai-compatible / zhipu-text` 凭据完成以下验证，命令和报告均未打印密钥：

1. `GET /models` 返回 8 个模型：`glm-4.5`、`glm-4.5-air`、`glm-4.6`、`glm-4.7`、`glm-5`、`glm-5-turbo`、`glm-5.1`、`glm-5.2`。
2. `glm-5.2` 最小 JSON Object 探针使用 256-token 上限、关闭思考、无 SDK 自动重试，返回并解析为 `{"ok": true, "provider": "glm-5.2"}`。
3. Info 正式阶段探针使用生产预算 4600 tokens 和节点 120 秒超时，通过 `StoryBriefContract`：5 个标题候选、7 个人物、12 条关系，且包含 `voice_spec`、`downstream_constraints` 与 `risk_notes`。

探针只证明当前凭据、模型目录、请求参数、JSON 解析和 Info 阶段合同可用，不代表正文文学质量已经通过；后者继续由 Phase 15 整书验收、逐章质量阀门与人工冷编辑判定。
