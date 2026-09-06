# Phase 32 Wave 25：三阶段中文、认识论保管与嵌套决策真实门

状态：**Brief、Cast、Beat Board 三阶段真实小门通过；Run 按计划停在 Beat Board 人工决策点，未接受 Beat、未进入 Scene Deck**

日期：2026-08-23

## 范围与停止条件

本轮使用一个全新的 `screenplay_sample r2` Run，执行：

```text
Brief -> 人工审读 -> accept -> Cast auto-continue -> Beat Board -> stop
```

Provider/model 冻结为 `provider-deepseek-text / deepseek-v4-flash`。每个 operation 的
transport attempt 上限为 `1`，真实调用总上限为 `3`。任一语言、Artifact、认识论、状态或
明显文学失败都必须立即停止；不自动换稿、不切换模型、不隐藏重试，也不恢复 Wave 32.23
或 Wave 32.24 的历史 Run。

## 调用前发现并关闭的价格权威漂移

调用前重新核对 DeepSeek 官方价格页：

`https://api-docs.deepseek.com/quick_start/pricing/`

`deepseek-v4-flash` 的峰时 cache-miss 输入和输出价格分别为 `$0.44 / 1M tokens` 与
`$1.32 / 1M tokens`。代码拥有的 Provider profile 当时仍冻结 `$0.14 / $0.28`，却把自身标记为
`conservative_upper_bound`，会让未来 receipt 的成本证据失真。

该问题在任何新 Provider 请求前关闭：

- `default_provider_profiles()` 改为 `$0.44 / $1.32`；
- creation-prepare 回归直接断言冻结价格，避免只验证 `source/profile` 标签；
- 正常 `seed_defaults` 刷新运行时 Provider profile；
- 新 Run 冻结新的内容寻址价格快照；
- 历史 definition、receipt 和估算值保持不可变。

## 新鲜 Run 与冻结合同

```text
project_id:        p32-screenplay-r2-language-project-20260823-125111
run_id:            p32-screenplay-r2-language-live-20260823-125111
workflow_id:       official-deepseek-fast
route revision:    r2
definition digest: e39fda716b21979e3183481c8c01f9a0e77f75e6dcd043aaa5a67fc99f9b6dfa
definition sha256: c9460f16badd2e35552815726cdb58d932d874366c6d28135b3f7f89f0bade68
pricing snapshot:  p32-provider-pricing-4024910c51457ff2bf8a696fb6ff2dc188351fa03c27becac4aa9301e45ba0f2
```

调用前已确定性证明：

- inputs 为 `inputs.screenplay_sample.v2 / r2`；
- `inputs.creation_language = zh-CN`；
- Prompt 分别为 `brief.v3 / cast.v3 / beat_board.v4`；
- 三阶段均冻结 `deepseek-v4-flash` 和同一可追溯价格快照；
- 密钥只验证存在性，没有输出原值；
- Provider input 和 operation receipt 数均为 `0`。

三个实际 Provider input snapshot 都携带 `creation_language=zh-CN` 和共享语言合同标记；Cast
snapshot 额外携带 `epistemic_custody`，其合同 digest 为
`864a2104b0c4e9a736fd173bae7837071c7027957b950f4e9ba8b283d01994fa`。

## 真实调用与成本

| Stage | receipt | attempts | prompt | completion | total | estimated cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Brief | `succeeded` | 1 | 947 | 443 | 1,390 | $0.00100144 |
| Cast | `succeeded` | 1 | 2,944 | 728 | 3,672 | $0.00225632 |
| Beat Board | `succeeded` | 1 | 2,201 | 976 | 3,177 | $0.00225676 |
| 合计 | 3 operations | 3 | 6,092 | 2,147 | 8,239 | $0.00551452 |

三次返回均为单一完整 JSON object，`schema_match_count=1`，没有 repair、合同纠正、隐藏重试
或模型切换。Provider response SHA-256：

```text
Brief:     d63d08bf075a3bae92717f541b67318dd089eb9c1b4e26d7f2096316ec6d5ded
Cast:      85752d400ca3eecf4dff62f65bcc771c7939c9aaf58b0b64d37073d260190331
Beat Board:14f1692dbb17d99f97c4a5e28a5333def097caaa6fd56b68180a5bc2a14db919
```

## 人工内容审读

### Brief v3

Brief 全字段使用简体中文。12 分钟、控制室/维护通道、主管阻挠、区间断电、违规开锁和职业
代价均具体可拍；结尾把更深证据或阴谋保持为暗示，而不是已证实 Canon。Brief 中出现的姓名
仍是 accepted planning prose，不是 Cast 前稳定 subject ref。

### Cast v3

Cast 提交 `lin_lan / zhou_qiming / chen_mo` 三个稳定主体。认识论保管通过：

- 林岚的事故责任、失职与职位后果都保持为条件；
- 周启明只被定义为规程阻力，没有被升级成掩盖阴谋、绑架或灭口的既成罪责；
- 陈默的危险保持为未知危险，关于证据的信息仍是其计划目标和不完整认知；
- 未来停职、救援和关系变化保持在 stakes/arc/change 范围，没有伪装成当前 Canon。

这证明 `cast.v3 + context.screenplay.cast.v2` 在本次真实模型返回中继续守住 Wave 32.22 的
未决性边界。Cast 仍是 accepted planning，不会因此获得 Canon 权限。

### Beat Board v4

Beat Board 返回 5 拍，时间提示连续覆盖 `0-12` 分钟。所有面向作者的自然语言字段使用简体
中文；5 个 `character_decision` 均为可见行动，没有“无决定 / No decision”占位。10 次
setup/payoff 引用全部是稳定 ASCII ref，未出现中文标签或冒号说明。

保留两个非阻断文学 warning：

- 第 4 拍的“尝试争辩”虽是台面行动，但相对前后拍的决策增量偏弱；
- `payoff_chen_mo_arrival` 与 `payoff_zhou_qiming_block` 在多拍重复，引用合法但 setup/payoff
  语义还可进一步收紧。

这些属于创作质量建议，不是 Schema blocker，也不授权自动换稿。本轮不接受 Beat。

## 状态、事件与停止点

最终权威状态为：

```text
status:             awaiting_decision
active_stage_id:    beat_board
domain_revision:    2
brief:              completed
cast:               completed
beat_board:         awaiting_decision
scene_deck/script:  locked
provider operations: 3 succeeded / 0 pending / 0 failed
events:             12
```

事件严格为 Brief started/candidate/decision、Brief accept/commit、Cast
started/candidate/auto-continue/commit、Beat started/candidate/decision。repository state、read
model、pending decision 和 durable checkpoint 均停在 Beat Board，证明 Wave 32.23 的父图/子图
interrupt 投影错误没有复发。Brief decision receipt 已完成，并指向新的 Beat decision。

历史 Run 保持只读：Wave 32.24 Run 仍为 1 次调用和原 definition digest；Wave 32.23 Run 仍为
3 次调用和原 definition digest。没有 resume、重投影或补写历史语言字段。

## 验证边界

- creation-prepare 定向回归：`9 passed, 1 warning`；价格 sidecar 与 creation-prepare 扩展回归：
  `21 passed, 1 warning`；
- 全量后端：`1027 passed, 1 warning`；唯一 warning 仍是既有 Starlette/httpx 弃用提示；
- `compileall`、全工作树 `git diff --check` 和 production closure audit：通过；audit 无 legacy
  runtime marker、无异常 frontend pipeline 顶层目录；
- 密钥扫描覆盖 19,364 个项目文件，DeepSeek 密钥原值命中 `0`；
- Wave 32.23 与 Wave 32.24 历史 Run 的 definition digest 和 operation 数不变断言：通过；
- 本轮真实 Provider 调用严格为 `3`，到达停止点后新增调用为 `0`；
- 本门只证明剧本路线前三个规划阶段的真实合同与内容可用性，不证明 Scene Deck、Script、Export、
  完整剧本、三路线全图、前端浏览器或发布门已通过。

## 下一道门

保持当前 Beat decision 未处理。下一次工作应决定是推进 Screenplay 的 Scene Deck 小门，还是
先补齐 Phase 32 当前更高优先级的生产切换/UI 工作。
不得把本 Run 当成下一次 Provider 测试的可恢复样本，也不得用本次三阶段通过替代完整路线验收。
