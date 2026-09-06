# Phase 32 Wave 21：三阶段真实合同 Stop Gate 与 checkpoint 前沿修复

状态：**Brief/Cast 真实调用成功，Beat Board 合同拒绝；失败证据已冻结，最低责任层已离线修复；三阶段真实门仍未通过**

日期：2026-08-23

## 范围与停止条件

本轮获准创建一个全新 `screenplay_sample` Run，执行：

```text
Brief -> 人工审读 -> Cast -> 人工审读 -> Beat Board
```

每个 operation 的 transport attempt 上限为 `1`，最多三次真实调用。Brief 经人工接受后，冻结 ReviewPolicy 将 Cast 配置为 `auto_continue`，因此 Graph 自动提交 Cast 并进入 mandatory Beat Board；本轮没有人为跳过 Cast，也没有在失败后继续调用 Provider。

## 新鲜 Run 与真实用量

```text
project_id: p32-screenplay-project-20260823-105907
run_id: p32-screenplay-brief-cast-beat-live-20260823-105907
workflow_id: official-deepseek-fast
model_id: deepseek-v4-flash
definition_digest: 35e9a5f9351555024378c7b2de515fc8d6ae0e216ebe1923401f8486f1be2c27
```

| Stage | receipt | prompt | completion | total | estimated cost |
| --- | --- | ---: | ---: | ---: | ---: |
| Brief | `succeeded` | 867 | 544 | 1,411 | $0.0002737 |
| Cast | `succeeded` | 1,422 | 904 | 2,326 | $0.0004522 |
| Beat Board | `contract_rejected` | 2,258 | 1,026 | 3,284 | $0.0006034 |
| 合计 | 3 operations | 4,547 | 2,474 | 7,021 | $0.0013293 |

三次返回均为单一完整 JSON object，结构化传输解析没有修复或隐藏 retry。内容寻址哈希：

```text
Brief payload:     85b683469ab5d87e0bf8278fc528d8003133093e55ef68205e2ab24f2164287f
Brief response:    0160de39aef0cc2ee03685682c420b3ad1940c589360dd2189622d6c9ac1c561
Cast payload:      2b8f100f575356fddba4887f47243d672a059cb7be3ce0a6cecd9c7f9e5de155
Cast response:     73bb1c63ec636785d6fd999d75a9bd7d26641b5e571cf275045cf31316d35b86
Beat payload:      8d21c4fb94e1317f82b07a76500472b144e0428c516e54a037ead88be9eb5339
Beat response:     178b8bccaaaac6d39775af7b57039c013ec91d430a727ab70ca202883c426a57
```

## Beat Board 合同失败

Beat Board 返回了 6 个完整节拍，但 13 个 `setup_or_payoff_refs` 使用了作者标签：

```text
setup: 异常信号
payoff: 陈默出现
```

核心 Artifact 要求稳定 ref 匹配 `^[a-z][a-z0-9_-]{1,63}$`。旧 Prompt 只在共用尾注中泛称“稳定引用使用小写英文”，字段 JSON Schema 也没有解释 setup/payoff ref 的具体格式，模型因此把说明文字当作引用。最低责任层是 Beat Prompt/字段 Schema，不是 transport、JSON 提取器或重试次数。

修复：

- Beat Prompt 升为 `prompt.phase32.screenplay_sample.beat_board.v2`；
- 明确只允许 `setup_abnormal_signal`、`payoff_chen_mo_arrival` 这类稳定 ASCII ref；
- JSON Schema 字段 description 同步禁止冒号标签、中文说明和解释文本；
- 原始失败 payload 固化为 `tests/fixtures/phase32_wave21_beat_board_contract_rejected.json`，所有验证均离线完成。

不增加解析修复、字符串归一化或隐藏合同重试。新 Prompt 只会进入未来新 Run 的冻结 definition，不修改本 Run。

## 失败后的权威漂移

Graph 实际事件顺序为：

```text
1  stage.started       brief
2  candidate.created   brief
3  decision.required   brief
4  decision.required   brief
5  decision.resolved   brief / accept
6  artifact.committed  brief
7  stage.started       cast
8  candidate.created   cast
9  decision.resolved   cast / auto_continue
10 artifact.committed  cast
11 stage.started       beat_board
12 stage.failed        brief / phase32_execution_failed  # 错误投影
```

SQLite 为该 thread 保存 23 条 checkpoints、197 条 writes。失败后的 root checkpoint 已包含 Brief/Cast committed refs，失败 task 的子图 checkpoint 进一步显示：

```text
active_stage_id: beat_board
brief: completed
cast: completed
beat_board: running
domain_revision: 2
failed node: beat_board.generate
```

旧失败处理却使用 resume 前的 repository record，并把异常链一直下钻到 Pydantic `ValidationError`，最终把 read model 写成 Brief awaiting、无 Artifact refs、错误 failure code/stage。接受 Brief 的 decision receipt 也因下游异常永远停在 `pending`。

修复后的单一规则：

- `Phase32GraphExecutionService` 在 Graph 抛错后只读 `aget_state(..., subgraphs=True)`，选择最深失败 task 的 durable state，不从 ArtifactStore 猜测前沿；
- Provider contract/transport 异常携带稳定 `code / stage_id / retryable`，不再由最底层 Pydantic 文案猜阶段；
- 非重试合同失败投影为 Run `failed`、Beat Board `failed`，保留 Brief/Cast refs、domain revision、最新 root checkpoint 和用量；
- 已经推进 domain revision 且不再 pending 的 decision command 完成 receipt，并记录 downstream failure；
- 同 payload 的连续 `decision.required` 在事件 sink 幂等，未来 resume 不再重复监控提示；
- failed Run 的普通 `start` 在进入 Graph 前拒绝，离线测试证明 Provider 请求数保持 3。

历史 Run 仍保持原始错误投影、pending decision receipt 和 immutable receipts，作为失败证据，不做修史式修正、恢复、取消或重放。

## 内容审读

Cast 已生成并提交 `lin_wan / zhou_tao / chen_mo` 三个稳定主体，结构、关系端点和引用合同合法。

文学 warning：Cast 把 Brief 中尚待证明的“周涛掩盖旧事故”“断电必死”“刑事诉讼”进一步固化成事实和动机。这不是 Schema blocker，但证明上游未决声明会沿自动 Cast 传播。下一次真实门前应为 Context/Prompt 增加“未决主张不得升级为事实”的可追溯语义；在没有 warning/evidence sidecar 前，不用临时关键词过滤冒充解决。

## 安全与离线门

- 本 Run definition、input snapshot、operation receipt、decision receipt 的实际密钥值扫描：0 个匹配；`auth_header=authorization` 仅是无密钥模板元数据；
- 历史 Run 未恢复、取消、接受 Beat 或再次调用 Provider；
- 真实 Provider 调用总数固定为 3；
- Prompt/Artifact/Driver/Graph/decision/failure/recovery 定向回归：42 passed；
- 职责拆分后的核心执行回归：28 passed；
- 全量后端：1017 passed，另有 1 个既有 Starlette/httpx 弃用 warning；
- `compileall`、`git diff --check` 和 production closure audit 通过；
- closure audit 无 legacy runtime marker 和异常 frontend pipeline 顶层目录。

## 下一道门

本轮只能关闭离线根因门，不能称为 Brief/Cast/Beat Board 三阶段通过。下一次真实 Provider 验收必须由用户再次明确授权并创建全新 Run；先验证 Beat v2 生成稳定 refs，再人工审读是否仍放大 Brief 未决主张。旧 Run 不得恢复，失败 fixture 不得触发真实 gateway。
