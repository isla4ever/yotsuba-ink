# Phase 32 Wave 24：创作语言冻结权威与全阶段 Prompt 合同

状态：**新鲜 Run 在 Brief 语言偏离后严格停止；最低责任层已离线修复，新的真实 Provider 验收尚未执行**

日期：2026-08-23

## 真实停止证据

Wave 32.23 修复 Beat v3 后创建了一个全新 `screenplay_sample r2` Run，原计划重新验证
Brief、Cast 与 Beat：

```text
project_id:        p32-screenplay-r2-beat-v3-project-20260823-121830
run_id:            p32-screenplay-r2-beat-v3-live-20260823-121830
definition digest: 0324249d063af7889bb239ba5acc047999fc63e1492668268b060f2f31d25b7b
Provider/model:    provider-deepseek-text / deepseek-v4-flash
```

只执行 Brief，一次 transport attempt 返回合法、Schema 匹配的 JSON：

```text
prompt tokens:     867
completion tokens: 508
total tokens:      1375
estimated cost:    $0.00026362
response sha256:   2304f378ebffffae2b839586e9fb8b669ab73303a438cc0af7766d3fef974011
```

但 `sample_type / premise / audience_promise / visible_conflict / ending_effect / tone` 的自然
语言全部是英文。Run 因产品语言失败保持 `awaiting_decision / brief / domain_revision 0`；Brief
未接受，Cast/Beat 未调用，真实调用总数固定为 `1`。原 definition、candidate、input snapshot、
operation receipt、state 和 read model 均不修改。

## 最低责任层

真实 Provider input 证明问题不是 DeepSeek 额度、transport、JSON parser 或 Artifact Schema：

```text
CreationIntent
  -> frozen Run inputs（没有 creation_language）
  -> Phase 32 Prompt snapshot（只写“专业中文创作节点”）
  -> Provider output（可合法选择英文）
```

Wave 32.23 只在 Beat 指令中要求中文，无法约束 Brief、Cast 与其余路线阶段。继续重试只会在同一
不完整输入上消耗 token，因此本轮停止在 Run 前语言权威和共享 Prompt 合同，不对 DeepSeek、
重试次数或质量阀门加补丁。

## 产品与合同决策

- `inputs.creation_language` 是 Run 前冻结的唯一输出语言权威；
- 当前产品只接受 `zh-CN`；
- 面向作者的所有自然语言字段使用简体中文；
- JSON key、枚举值、稳定 ref 与 code-owned metadata 保持合同规定的 ASCII；
- 语言偏离是可见 warning 与人工验收问题，不使用字符比例或关键词扫描伪装确定性 blocker；
- 旧冻结 Run 保持只读，不补字段、不改 digest、不恢复执行。

## 离线修复

1. `CreationIntent` 新增唯一允许值 `creation_language="zh-CN"`，creation-prepare 将其冻结进
   `inputs.<route>.v2 / r2`。
2. 三条路线的 14 个 Provider task 共享语言合同；所有 Prompt revision 显式升级：
   `screenplay_brief v3`、`character_bible v3`、`beat_board v4`，其余 task 为 `v2`。
3. 删除 `_TASK_PROMPT_REVISIONS.get(..., 1)` 的隐式新阶段回退；新增 task 未登记 revision 时
   立即失败，不能静默复用 v1。
4. Preflight 只在冻结 Prompt 含新语言合同标记时要求 `inputs v2/r2 + zh-CN`。历史 Prompt
   没有该标记，仍可按原 definition 解析；新 Prompt 缺语言则不能进入执行。
5. Fake Provider fixture 同步冻结语言；Provider request 回归证明 `context.inputs` 实际携带
   `creation_language`。
6. 英文 Brief 被压缩为只读证据 fixture，不成为生产判断器，也不触发自动重试。

## 验证边界

- 创建向导、creation-prepare、Prompt、Preflight、Run fixture、Provider request 与图执行扩展
  定向门：`100 passed`；
- 全量后端：`1027 passed`，另有 1 个既有 Starlette/httpx 弃用 warning；
- `compileall`、`git diff --check` 和 production closure audit：通过；
- closure audit 无 legacy runtime marker、无异常 frontend pipeline 顶层目录；
- 排除凭据数据库后扫描 19,346 个仓库文件，DeepSeek 密钥原值命中 `0`；
- 本轮真实 Provider 新增调用：`0`；
- 当前真实 Run 的调用总数：`1`；

## 未关闭的门

本轮离线绿灯不能证明 DeepSeek 将遵守新语言合同。完成全量离线门后，仍需另建全新 Run，冻结
`creation_language=zh-CN` 和新的全阶段 Prompt revisions，再从 Brief 开始做有界真实验收。
不得 resume 当前英文 Brief Run，也不得用修改历史输入或重复请求替代新鲜验收。
