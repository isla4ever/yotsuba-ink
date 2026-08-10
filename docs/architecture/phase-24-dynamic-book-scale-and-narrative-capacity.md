# Phase 24：动态成书体量与叙事容量合同

> 状态：本地合同、全量门禁和浏览器验收已完成；等待恢复真实 Provider 三章验收。
>
> 日期：2026-08-08。

## 1. 产品决策

作者创建作品时只做一个体量决策：选择“总字数”或“总章数”，填写一个正整数目标值。卷数、另一项总量、各卷章节分布、单章软硬范围、全书闭合范围、人物规模和阶段输出预算全部由服务端派生。

这不是把旧字段藏进高级设置，而是删除多源配置：

- 不再单独配置卷数、每卷章数、细纲章数、正文章数或单章字数；
- 不再从 `stage_configs`、节点 `params`、生成预算或历史别名推断成书体量；
- 不接受客户端提交完整派生计划；
- 不保留旧字段转换器、读取回退、代理属性或双轨断言；
- 历史运行快照保留为审计证据，但不会成为新运行的输入兼容层。

## 2. 唯一数据流

```text
BookScaleTarget
  target_mode: total_chars | total_chapters
  target_value: positive integer
          |
          | POST /api/runs 或 /api/runs/stream
          v
server build_book_scale_plan()
          |
          v
BookScalePlan (frozen in run inputs)
  total_chars / total_chapters
  volume_count / chapters_per_volume / volumes[]
  chapter soft + hard budgets
  book soft closure
  stage_budgets / story_scope / capacity_policy
          |
          +--> Prompt Compiler
          +--> Outline 按卷生成、缓存、恢复与合并
          +--> Detail 按章生成、交接与合并
          +--> Text 逐章字符信封与全书预算闭合
          +--> Acceptance / Report / Recovery
```

`BookScaleTarget` 是一次性创建请求，不写入冻结运行。服务端派生成功后移除请求对象，只保存 `BookScalePlan`。前端可以用同算法即时预览，但预览不参与启动验真；Python 与 TypeScript 共同消费一份 JSON 案例夹具以发现显示漂移。

## 3. 派生算法

### 3.1 总量与章节

- 默认章节目标为 2000 个中文可见字符；统计标准固定为 `cjk-visible-chars-v1`。
- 用户指定总字数时，章数按 `total_chars / 2000` 四舍五入，并重新计算能闭合总量的单章目标。
- 用户指定总章数时，总字数按 `total_chapters * 2000` 派生。
- 总字数允许 3000-5,000,000；总章数允许 1-2500。布尔值、小数、字符串、零值和越界值在服务端拒绝。

### 3.2 分卷

- 16 章及以下使用单卷。
- 多卷以每卷约 12 章为中心，正常保持 8-16 章。
- 余数从前卷依次分配，例如 17 章派生为 `9 + 8`。
- `volumes[]` 明确保存连续的章起止、章数和字符目标；所有卷章数与字符数之和必须分别闭合全书。

### 3.3 软硬字数

- 单章软范围用于 Prompt 节奏引导，默认是目标的 80%-120%。
- 单章硬范围用于验收和失控保护，默认是目标的 65%-150%。
- 指定总字数时，全书软范围是目标的 95%-105%。
- 指定总章数时，全书软范围由每章软范围乘章数得到。
- 软下限不是补写触发器；轻微偏短不得为了命中字数重写完整章节。

### 3.4 叙事容量

- 每章默认承担一个主要叙事位移和一个主场景；必要时可使用第二场。
- 第三场只属于明确的结构例外，不是普通密度目标。
- 同章同时出现独立选择、重大揭示、关系反转或时空/视角转换时，优先拆成相邻章节。
- 未完成内容通过 Detail `continuity_handoff` 交给下一章，不在当前章强行结清。

## 4. 各阶段如何消费体量

| 阶段 | 体量职责 | 禁止行为 |
| --- | --- | --- |
| Info | 按成书规模派生人物与关系配额；生成 Story DNA | 不规划逐章剧情，不复制整本节拍 |
| Summary | 输出完整因果主干；预算只随卷级复杂度缓慢增长 | 不按章数线性展开长梗概 |
| Outline | 按 `volumes[]` 逐卷生成 Volume Program，并闭合每卷章区间 | 不由模型自行决定卷数和章区间 |
| Detail | 按计划章数逐章生成剧本；一章一个主要位移，使用稳定交接 | 不在一章堆完多个独立事件，不改变总章数 |
| Text | 使用单章软范围引导、硬范围保护，并在新章前做全书预算预测 | 只读取冻结计划，不为轻微偏差无脑重写 |
| Cover | 只消费稳定书名、主题、类型与视觉 brief | 不随正文章数线性增加 Prompt |
| Export | 校验 Manifest、章节完整性和总量报告 | 不自行修正文稿或伪造缺失章节 |

## 5. 删除和更名

本阶段直接删除：

- 阶段级旧体量字段，以及以卷、章或单章预算作为体量代理的配置路径；
- 从节点参数或阶段配置推断章节数的方法；
- `AcceptanceScope` 上代理 `BookScalePlan` 的属性和场景数方法；
- Acceptance 构建器和运行器的可空 `book_plan`、隐式默认计划与数字代理；
- 已被统一候选换稿链路取代的旧式简报重生成 API、请求模型和前端适配器。

验收报告使用明确的新字段：

- `total_volumes`；
- `total_chapters`；
- `contract_version`；
- `chapter_hard_chars`；
- `book_soft_chars`。

不提供旧报告字段别名。

## 6. 测试合同

### 6.1 派生与防伪

- 目标值必须是 JSON integer，不接受字符串、小数和布尔值；
- 上下界在服务端执行；
- 启动请求包含 `book_scale_plan` 时直接拒绝；
- 冻结后不存在 `book_scale_target`；
- 任意卷章分配的章数和字符数必须闭合；
- 阶段预算随职责增长，而不是随全书长度线性膨胀。

### 6.2 链路

- Outline 分批范围只来自 `BookScalePlan.volumes[]`；
- Detail 数量和恢复批次只来自 `total_chapters`；
- Prompt 快照显式包含“成书体量合同”；
- Acceptance、报告和审批直接读取 `scope.book_plan`；
- 前后端共同夹具至少覆盖最小字数、投稿字数、单章和余数分卷。

## 7. 验证顺序

1. 体量专项、Prompt 快照与 Acceptance 定向回归。
2. 后端全量、`compileall`、`git diff --check`。
3. 前端全量、TypeScript、Vite build、CSS 审计。
4. 浏览器验收总字数/总章数切换、边界值和小屏布局。
5. 以上全部通过后，才允许恢复 DeepSeek 三章真实链路。

## 8. Definition of Done

- [x] 用户只选择一种总量目标并填写一个值；
- [x] 服务端派生并冻结完整 `BookScalePlan`；
- [x] 启动接口拒绝客户端派生计划；
- [x] 旧阶段体量字段和 Acceptance 代理已删除；
- [x] 跨端共享派生案例已建立；
- [x] Prompt 快照已刷新为当前体量合同；
- [x] 后端全量、前端全量、构建和 CSS 门禁通过；
- [x] 桌面与小屏创建作品流程通过真实浏览器验收；
- [ ] 本地全绿后完成 DeepSeek 三章真实链路与人工文学审读。

## 9. 2026-08-08 本地验收记录

- 后端：`1415 passed, 6 skipped`；`compileall` 与 `git diff --check` 通过；
- 前端：`137` 个测试文件、`530` 个测试通过；TypeScript 与 Vite 生产构建通过；
- CSS：审计与拆分门禁通过，首屏 CSS `32.0 KiB gzip`；
- 浏览器：总章数输入 20 时即时派生 `4 万字 / 2 卷 / 20 章 / 10 + 10`；总字数输入 20,000 时即时派生 `2 万字 / 1 卷 / 10 章`；
- 小屏：390x844 视口无横向溢出，配置正文使用独立滚动容器，固定操作栏不覆盖滚动容器；
- Console：无应用错误或警告；
- 本轮未调用 DeepSeek 或其他真实文本 Provider，真实三章文学质量验收仍是下一门禁。
