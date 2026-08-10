# Yotsuba Ink 人工偏好校准协议

> 适用范围：Wave 17.4 冷编辑与盲化偏好评审的发布前校准。
> 这是内部验收门，不是第八个创作阶段，也不进入普通创作者的正文工作台。

## 1. 验收合同

| 项目 | 定义 |
| --- | --- |
| 校准产物 | 绑定 Run 快照和候选正文签名的盲样本包、封存键、人工答卷和机器可读报告 |
| 用户决策 | 在不知道模型、厂商、生成顺序和系统胜出稿的前提下，对每组选择 `A`、`B` 或 `tie` |
| 写回目标 | 只写入 Run 目录下的本地 `acceptance/preference-calibration/`；不写入 Chapter、Memory、Wiki、Canon 或 Story Bible |
| 下一阶段依赖 | 答卷完整且一致率/顺序稳定性的点估计与 95% Wilson 区间同时达标，才能进入 Wave 17.5 Run II |

## 2. 文件边界

| 文件 | 用途 | 人工选择前是否可读 |
| --- | --- | --- |
| `blind-samples.json` | 包含当章承接、场景约束与 A/B 正文 | 是 |
| `review-responses.json` | 填写审稿人、`author_choice` 和必要备注 | 是 |
| `calibration-key.json` | 封存系统结论、顺序翻转和同源情况 | 否 |
| `calibration-report.json` | 完整性、分层统计、Wilson 区间与退出结论 | 选择完成后 |
| `calibration-report.md` | 人工可读摘要 | 选择完成后 |

盲样本不显示 Provider、Model、候选原始 ID、系统建议或评审证据。封存键只保留统计必需元数据，不复制候选正文。每个样本绑定 SHA-256，修改正文或上下文后报告必须拒绝计算。

## 3. 执行方式

仅对包含多候选和 `preference_review_state` 的完整 Run 快照执行：

```bash
.venv/bin/novel-workflow-preference-calibration prepare \
  --run-file runtime/novel_workflow/real_gate_runs/<run-id>/run.json
```

审稿人只打开 `blind-samples.json` 和 `review-responses.json`，并填写 `reviewer`、
`completed_at` 以及每组 `author_choice`。完成后计算报告：

```bash
.venv/bin/novel-workflow-preference-calibration report \
  --bundle-dir runtime/novel_workflow/real_gate_runs/<run-id>/acceptance/preference-calibration
```

`prepare` 重复执行时会保留同一样本包的已有答卷；如果目录已属于另一个样本包，必须换目录，不会覆盖人工结果。

## 4. 统计规则

- 稳定胜出稿映射为 `A` 或 `B`；正反顺序结论不一致时映射为 `tie`。
- Provider 不可用不等于文学平局：`unavailable` 在一致率中记为未命中，且不进入顺序翻转分母。
- 同模型家族和跨模型家族必须分层报告，避免总体一致率隐藏同源偏差。
- 退出要求同时满足：全部样本已审且审核身份/时间完整；一致率点估计与 95% Wilson 下界均 `>=75%`；顺序翻转率点估计与 95% Wilson 上界均 `<=5%`。
- 在零翻转的理想情况下，至少需要 73 个可用顺序复评样本，95% Wilson 上界才会降到 5%；因此一本九章小样本的表面 100% 不能被描述为已校准。

## 5. Prompt 迭代规则

校准未达标时，先根据错配样本修正评审身份、证据协议和决策顺序，不允许调低阈值或删除失败样本。

1. 先分类错配：承接违约、视角/知情越界、因果断层、解释压过行动、语声漂移、位置偏差或证据不可定位。
2. 保留“与生成者隔离的盲化文学评审员”身份，但用正向的阅读任务、阶段约束和证据格式引导判断，不把文学风格压成固定模板。
3. 在调整集上修改 Prompt，用未见保留集重跑正反顺序评审；不能在同一批人工选择上反复拟合后报告提升。
4. 同时报告自动结论可用率和同源/跨源分层；高弃权率不能用来美化一致率。

## 6. 当前状态

工程机制已具备盲样本导出、三候选成对关系、签名防篡改、答卷保护、同源分层和 Wilson 退出门。当前仓库尚无达到样本量的真实人工答卷，因此 Wave 17.4 保持未完成，不得启动或宣称 Run II 文学校准已通过。

Run B `phase17-preference-pilot-20260802-b` 已形成 9 章、27 个候选和 27 组盲样本，候选与
正式 Chapter/Memory/Wiki/Canon 隔离检查通过；但复检发现 27 份候选全部超过已存
`1600-2400` 字符合同，实际范围为 `2556-4900`，均值 `3780.3`，其中 24 份还被编排层
重新注入章节标题。独立 GLM Judge 的 27 组结果也全部为 `unavailable`。因此 Run B 的
候选语料本身无资格进入 Judge 恢复或人工校准；`review-responses.json` 保持 27 项全空，
不能由模型补填。

Run B 固定保留为不可变失败证据，旧的“原 Run 只恢复 Judge”方案作废。下一轮顺序固定为：

1. 先由正文信封规范化和逐场长度双边修复保证新候选满足合同；
2. 使用新的 Run ID 创建 Run C，不复制、改写或重新签名 Run B 的 27 份候选；
3. Pilot 在 Provider/Judge 恢复前检查 `candidate_length_contract` 与
   `candidate_prose_envelope_clean`，任一失败立即阻断；
4. 新候选合同通过后，再完成独立 Judge 的 forward/reversed 评审；
5. 只有候选合同、`all_pairwise_reviews_available`、隔离和预算检查全部通过后，才允许真实审稿人开始盲评。

### 6.1 叙事角色与 Judge 可用性边界

普通创作可以在 Info 配置中单选六种只读叙事角色，并在选择前查阅完整策略段落。角色是
Prompt 的观察/取舍层，不是新的 Artifact，也不允许覆盖阶段身份、SceneContract、Canon、
人物知识边界、用户要求或硬一致性门。旧 Run 没有选择时不注入角色段落，以保持文学 Prompt
基线兼容；新 Run 只有一个贯穿全书的角色选择，不支持自由编辑和混合角色。

偏好校准的 Judge 必须与 Writer 使用不同 Provider，并先通过一次性低 token 的
`judge-smoke`：同一匿名强/弱候选按 forward/reversed 各调用一次，检查结构化 JSON、顺序
归一化、稳定胜者和 Writer/Judge 隔离。命令示例：

```bash
.venv/bin/novel-workflow-preference-calibration judge-smoke \
  --runtime-root runtime/novel_workflow \
  --writer-provider-id deepseek-live-acceptance \
  --judge-provider-id <independent-judge> \
  --max-tokens 900
```

烟测失败必须保留公开错误码并停止，不得触碰旧 Run、重签候选或把不可用 Judge 当作平局。
GLM 当前记录为 `insufficient_balance`；MiMo Coding Plan 不满足文学 Judge 用途；DeepSeek
作为 Writer 时不能同时担任独立 Judge。只有烟测通过，才可创建新的 Run C 并从 Info 开始。

### Run C 启动就绪矩阵（2026-08-03）

| 条件 | 状态 | 证据或限制 |
| --- | --- | --- |
| 正文标题与内容分层 | 通过 | 共享正文信封规范化已接入候选组装与逐场生成 |
| 过短/过长双边修复 | 通过 | 修复后仍越界会拒绝候选，不截断落盘 |
| 每章 Judge 前候选预检 | 通过 | 内部校准固定检查 3 份候选、长度与正文信封；失败时 Judge 零调用 |
| 已完成旧 Run 预检 | 通过 | Provider 就绪检查前拒绝无效旧候选，Run 快照不变 |
| Pilot 创建前 Judge 烟测 | 通过 | Pilot 函数强制先完成双顺序烟测；失败时 Writer 零调用且不创建 Run |
| Writer | 已配置 | `deepseek-live-acceptance` 有本地密钥记录；本表不把密钥记录当作实时可用证明 |
| 独立 Judge | 未通过 | 2026-08-03 GLM 重试仍在首次推理前返回 `insufficient_balance`；MiMo Coding Plan 不满足文学 Judge 用途 |
| 新 Run ID | 未创建 | 独立 Judge 未通过前不创建 Run C，不产生模型费用 |

因此当前正确动作不是启动 Run C，而是先取得一个与 Writer 不同、可完成低 Token 正反顺序评审烟测的 Judge。烟测必须使用一次性新测试作用域，不得触碰 Run B；通过后再创建新的 Run ID，从 Info 开始生成候选。

### 6.2 运行恢复与角色输入一致性

普通创作选择的叙事角色属于 Run 输入的一部分，不是只存在于当前浏览器表单的临时偏好。
服务端创建 Run 时会保存 `inputs` 与当时的 `workflow`；恢复时优先使用服务端快照，不能用
当前工作流默认值替换已创建运行。浏览器本地恢复点和“重置后撤销”同样保存结构校验后的
`RunInputs`，仅在服务端暂时不可达时提供离线展示与继续入口。旧 Run 没有该字段时保持兼容，
不注入新角色段落，也不得因此获得文学验收资格。

智谱标准按量入口与 Coding Plan 入口不是同一额度通道。Coding Plan 的 OpenAI 兼容地址以
[智谱接入工具文档](https://docs.bigmodel.cn/cn/coding-plan/tool/others) 为准；429 业务码必须按
[智谱错误码文档](https://docs.bigmodel.cn/cn/api/api-code) 区分余额、套餐权限、速率和平台拥塞，
不得统一解释为并发过高。
