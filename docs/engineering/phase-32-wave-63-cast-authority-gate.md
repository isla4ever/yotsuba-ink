# Phase 32 Wave 63：Cast 主体权威人工门

- **状态**：真实 Run 已在 Volumes 候选前主动止损；三条官方路线的 Cast 人工门与 v5 提示合同已完成本地修复
- **日期**：2026-09-05
- **证据 Run**：`continuity-acceptance-run-b49b9d28c1bc05cfe57d`
- **图片状态**：图片调用 0；本波不进入封面图片验收

## 1. 用户授权与监制边界

用户授权由当前执行者全程承担内容确认。该授权用于逐阶段审读、提交有边界的人工草稿和接受合格候选，不等于忽略确定性错误、扩大预算或盲目自动通过。

继续沿用冻结上限：

```text
max_cost_usd: 5.00
max_operations: 48
max_total_tokens: 2,000,000
max_transport_attempts_per_operation: 3
text_only: true
```

## 2. Brief 与 Book Architecture 监制结果

Brief 原候选存在“修复后不可逆但又可销毁未来来源”的规则冲突，以及拒绝修复为何触发时间重置的因果缺口。监制通过正式 Stage Draft API 保存编辑稿，再以 `draft_ref` 接受；原候选保持不可变。

```text
brief draft:
  p32-draft-509628369f98104a7821d9478a3f893b5c1337c63966254ef25ebc53ec21f9c8
brief committed:
  p32-brief-committed-a300baf397e1708a3760a55824c2dae3c41c963911de6ec16c84abc6c4f6806c
```

修订后固定：完成归档才使失踪不可逆；归档前可销毁正在显影的来函；冻结墨每次只夺走一段与某人有关的真实记忆；第十二封归档或销毁后通道永久关闭。结局不再依赖未声明的时间线重置。

Book Architecture 首稿又把“使用冻结墨才失忆”放大成“每归档一封就失忆”，并留下全部为空的跨 Part obligation。监制保持四个 Part 和所有稳定引用不变，只修订记忆代价、跨 Part 义务与终局条件：

```text
book architecture candidate:
  p32-book_architecture-candidate-f613f54e37fa473a9c943714a2ccdb42-43caf4c6
book architecture draft:
  p32-draft-ee524b373ed0b191326053e9ccfa654fafcfc47e341230220069473311581b70
book architecture committed:
  p32-book_architecture-committed-c75247f8aa76e82babedc684ca9e3194f8bc8df18455d6e5e5315c41e2286de0
```

## 3. 真实 Cast 暴露的业务断点

接受 Book Architecture 后，冻结的 `review.long_novel.default/r1` 没有把 Cast 列为 mandatory stage。Graph 因而在同一次恢复中生成并自动提交 Cast，然后直接生成 Volumes 候选。

Cast 结果只有三个主体：

```text
protagonist_archivist -> 档案修复师
missing_person        -> 失踪者
anonymous_sender      -> 匿名委托人
relationships         -> []
```

这不是普通文风 warning，而是正文质量的权威断点：

1. Cast 是正文前唯一主体注册表；
2. Cast 提交后，Stage Draft 合同禁止新增、删除或替换 `subject_ref`；
3. Chapter v5 合同禁止正文给未登记主体创造姓名；
4. 因此后续十二章只能把十一名独立失踪者反复写成同一个“失踪者”，无法形成独立证据链、对白、关系或人物弧；
5. 当前 Run 已无法用普通编辑修复，只能通过正式 amendment/successor Run 重算，不能原地覆盖。

同时，Volumes 候选把四部分配为 `12,500 / 37,500 / 37,500 / 62,500` 字；只处理第十二封的最终 Part 占全书 41.7%，而各处理五封的中间 Part 各占 25%。该候选尚未接受。

## 4. 根因

根因是两个合同叠加，不是 Provider 单点随机失误：

1. 三条官方 ReviewPolicy 均未一致地把 Cast 作为主体冻结前的人工门；
2. Cast v4 提示把认识论保护写成了绝对禁止：上游只有“失踪者”等职能标签时必须原样保留且不得命名；
3. 该规则没有区分“一个身份必须保持未知的持续角色”和“多个将独立行动的主体集合”；
4. 一旦 Provider 合并主体，自动提交和不可变编辑合同共同消除了人工修复窗口。

## 5. 产品决定

三条官方路线统一遵守以下规则：

- Cast 是主体引用成为不可变权威前的 mandatory decision stage；
- Cast 允许一次有方向的 Provider redraft；
- 单一且必须匿名的持续角色保留职能标签；
- 职能标签若代表多个独立出场、承担不同证据链、对白或人物弧的个体，Cast 必须拆成不同 `subject_ref`，并赋予可区分的作者工作名；
- 工作名只是已接受人物规划，不得借命名把未知身份、隐秘动机、罪责、关系或结局提升为既成事实；
- 已冻结 Run 不因新代码被静默迁移或覆写。

## 6. 实现

`src/novel_workflow/workflows/review_policy.py`：

- 三条官方 ReviewPolicy 从 `r1` 升为 `r2`；
- 三条路线均把 `cast` 加入 `mandatory_decision_stages`；
- 三条路线均冻结 `directed_redraft_limit_by_stage.cast = 1`；
- 剧本路线移除 `cast` 的 auto-continue。

`src/novel_workflow/workflows/phase32_prompt_contract.py`：

- `character_bible` 提示从 v4 升为 v5；
- 保留 epistemic custody；
- 新增单一匿名角色与多个独立主体的拆分规则；
- 明确工作名不能夹带未经证实的叙事事实。

合同测试同步证明：

- 三条官方路线都在 Cast 停止；
- Cast 决策包含 `regenerate`，上限为 1；
- 接受 Cast 后才可进入下游；
- 既有 downstream contract rejection 仍投影到正确 checkpoint frontier；
- 旧 Run 的冻结定义和 Artifact 不被改写。

## 7. 真实调用与成本

当前 Run 在主动停止时：

| 指标 | 结果 |
|---|---:|
| Provider operations | 4 |
| succeeded | 4 |
| contract rejected / failed / pending | 0 / 0 / 0 |
| prompt tokens | 10,256 |
| completion tokens | 2,993 |
| total tokens | 13,249 |
| conservative estimated cost | `$0.02539020` |
| image operations | 0 |

新增真实 receipts：

```text
book_architecture:
  p32-provider-operation-43caf4c63cbb9f7966170b952c094d44f46dba14a6657e5584e9c7d532869647
cast:
  p32-provider-operation-9624a0e2dab897ba4cc7ea891ff6c01bd3c118aacf7a71accddab3d476a8a5ac
volumes:
  p32-provider-operation-75c2f854be1e9ed997f7d673c7e6934501103d37a311792c751eca10dd26e067
```

Run 当前仍为：

```text
status: awaiting_decision
active_stage_id: volumes
pending_decisions: 1
accepted stages: brief, book_architecture, cast
unaccepted candidate: volumes
```

## 8. 验证

阶段合同与执行专项：

```text
151 passed, 1 warning
```

完整后端第一次运行正确暴露 2 个仍假设“官方 Cast 自动通过”的旧测试；更新为显式 Cast 决策后，两个回归用例单独通过。最终门禁：

```text
backend full suite: 1334 passed, 1 warning
compileall: passed
git diff --check: passed
closure audit: no legacy runtime markers; no unexpected pipeline directories
```

唯一 warning 为既有 Starlette `TestClient` / `httpx` 弃用提示。审计仍列出历史大文件清单，它是责任边界复核信号，不是本波新增回归。

## 9. 下一门

当前旧 Run 适合作为“自动 Cast 导致主体权威过早冻结”的真实失败证据，不适合继续冒充文学验收。后续顺序：

1. 完整后端与静态门全绿；
2. 用新 `r2 + Cast v5` 冻结一个全新 exact-12 Run；
3. 新 Run 的 Provider 预算必须重新形成明确授权，不能把旧 Run 剩余额度静默复制给另一个 Run；
4. 新 Cast 必须在人工门审查：主体数量、命名、关系、认识论状态与十一名失踪者的独立证据职责；
5. 只有 Cast 通过后才审查 Volumes/rolling detail，并继续十二章正文；
6. CoverBrief 可生成，但图片调用仍保持 0，最终停在 `image_deferred`。
