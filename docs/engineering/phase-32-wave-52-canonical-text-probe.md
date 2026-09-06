# Wave 52：Canonical 文本 Provider 稳定性探针

- **日期**：2026-08-26
- **范围**：仅验证 DeepSeek 文本 Provider 的最低成本传输稳定性；不创建 Phase 32 Run、不写回 Artifact、不调用图片 Provider。
- **Provider**：`provider-deepseek-text`（OpenAI-compatible，地址仅记录为 `https://api.deepseek.com`，不记录密钥）
- **模型**：`deepseek-v4-flash`
- **任务**：`phase32.wave52.text_probe`
- **输入**：固定短提示，要求只返回“稳定性探针通过。”

## 结果

| Probe | Idempotency suffix | 响应字符数 | SHA-256 | Prompt / Completion / Total | Finish | 延迟 |
|---|---|---:|---|---:|---|---:|
| 1 | `canonical-20260826` | 8 | `19c39eef695d454530ad12079bea2fbb6c88bafc55e52e69ddf97faed670f4da` | 42 / 5 / 47 | `stop` | 1.240s |
| 2 | `canonical-20260826-2` | 8 | 同上 | 42 / 5 / 47 | `stop` | 1.202s |
| 3 | `canonical-20260826-3` | 8 | 同上 | 42 / 5 / 47 | `stop` | 1.724s |

三次 `reasoning_chars` 均为 0，返回 hash 完全一致；本轮没有产生 Run、Artifact、writeback 或图片 operation。

## 结论与边界

- **通过**：文本 Provider 的网络、认证、模型路由、基础响应和 usage 读取在固定低成本输入下稳定。
- **不能推断**：这不是三条路线的结构化 Artifact 合同验收，也不能证明长上下文连续性、文学质量、写回恢复或最终导出质量。
- **下一步**：使用新的 `run_id` 进行三条 canonical route 的受控 fresh smoke；Screenplay 到文本交付，Short/Long 到 CoverBrief 后保持 `image_deferred`，并保存完整 manifest / event / receipt / Artifact bundle。
