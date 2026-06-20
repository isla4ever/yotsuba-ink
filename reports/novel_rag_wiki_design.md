# 小说创作场景 RAG + LLM Wiki 知识检索方案

## 1. 参考项目 wikiagent-main 的实现方式与逻辑

`C:\Users\wxwhs\Desktop\wikiagent-main` 的核心思想不是传统“把原始文档切块后每次临时检索”的 RAG，而是让 LLM 长期维护一个结构化 Markdown Wiki。它把“知识整理”前移到摄入阶段，使查询阶段面对的是已经归纳、交叉引用、可审计的知识库。

### 1.1 架构组成

- 主入口：`wikiagent/main.py` 读取配置、加载提示词/技能、创建主 Agent，并注册工具和子 Agent。
- LLM 客户端：`wikiagent/llm.py` 使用 OpenAI 兼容接口，支持流式输出和 function tool call 解析。
- Agent 循环：`wikiagent/agent.py` 将用户消息、系统提示、工具调用结果不断追加到 messages，直到模型不再调用工具。
- 工具系统：`wikiagent/tool.py` 与 `wikiagent/tools/` 提供 `read/write/edit/grep/glob/bash/web_fetch/task/todo` 等文件与检索工具。
- 子 Agent：`wikiagent/subagents/` 按职责拆分为 `wiki_ingest`、`wiki_query`、`wiki_lint`，分别负责摄入、只读查询和知识库体检。

### 1.2 核心工作流

1. `ingest`：读取 URL/文件/文本，生成 `wiki/sources/<slug>.md` 源摘要页，再更新相关实体页、概念页、主题页、索引与日志。
2. `query`：只读扫描 `wiki/index.md` 与相关 Markdown 页面，基于 Wiki 已知内容回答，并标明引用页面；缺失信息要明确说明。
3. `lint`：检查断链、孤立页、索引漂移、矛盾信息、缺页等问题，安全项自动修复，其他项写入报告。

### 1.3 可借鉴点

- 知识持久化：把 LLM 一次性理解沉淀成结构化页面，减少每次生成时重复理解长上下文。
- Obsidian 风格内链：`[[entities/foo]]`、`[[concepts/bar]]` 天然适合世界观和人物关系浏览。
- 子 Agent 职责隔离：写入、查询、体检分离，避免查询阶段误改知识库。
- 变更日志：`wiki/log.md` 记录每次摄入和修正，适合小说设定迭代审计。
- 矛盾不覆盖：新设定与旧设定冲突时进入 `Contradictions` 区域，而不是静默删除旧内容。

### 1.4 不足与需要增强处

- 当前参考项目主要靠 Markdown 文件和 grep/glob/read 检索，没有真正的向量数据库。
- 人物关系是隐含在链接和正文中的，缺少显式图谱查询能力，例如“谁背叛过谁”“某阵营所有敌对关系”。
- 缺少与当前 `nanochat` OpenAI 兼容推理服务的直接集成层。
- 对小说正文生成缺少“设定一致性守卫”和“情节连续性校验”的业务规则。

## 2. 当前 nanochat 模型端可集成位置

`C:\Users\wxwhs\Desktop\nanochat-dgxspark-rl-main` 已经具备小说任务和本地 OpenAI 兼容服务基础。

### 2.1 现有能力

- `deploy/openai_compat_server.py` 提供 `/v1/chat/completions`，支持 stream/non-stream，适合作为 Spring Boot 或其他前端统一调用入口。
- 服务内部已有任务识别：`info_recommend`、`summary`、`outline`、`detail_outline`、`text`、`text_first_chapter`、`text_non_first_chapter`。
- `scripts/` 下已有小说 SFT 数据构建、纠偏、联测、训练脚本，说明项目已有“信息推荐 → 全书梗概 → 分卷大纲 → 章节细纲 → 正文”的五阶段生成链路。
- `tools/search_tools.py` 和 `tasks/search_r1.py` 已具备搜索工具/多轮搜索训练思想，可复用“模型主动发起检索再生成”的范式。

### 2.2 推荐集成策略

不要把 RAG 直接写死在模型 generate 内部，而是在 `deploy/openai_compat_server.py` 前增加一个“小说 Wiki RAG 编排层”：

1. 请求进入 `/v1/chat/completions`。
2. 根据 `task_name` 或现有 `_resolve_task_name` 判断任务类型。
3. 对小说创作任务调用 `NovelWikiRetriever` 检索世界观、人物、关系、伏笔和章节记忆。
4. 将检索结果压缩成 `system` 或前置 `assistant` 上下文，拼接到模型 messages。
5. 模型生成后，按任务类型决定是否写回 Wiki：
   - 设定/人物推荐：可进入候选设定区，等待确认后入库。
   - 梗概/大纲/细纲：可自动写入 `plots/`、`arcs/`、`chapters/` 草稿页。
   - 正文：抽取新增事实、人物互动、伏笔变化，写入 `events/` 与 `chapters/`。

## 3. 面向小说创作的目标架构

建议采用三层知识结构：Markdown Wiki 是真相源，向量数据库负责语义召回，图谱索引负责人物关系拓扑。

```text
用户/后端请求
  ↓
OpenAI 兼容服务 deploy/openai_compat_server.py
  ↓
NovelRAGOrchestrator
  ├─ WikiStore：Markdown 设定库，负责可读、可审计、可编辑
  ├─ VectorStore：语义检索，负责相似设定/剧情片段召回
  ├─ GraphStore：人物、阵营、地点、事件关系拓扑
  ├─ MemoryStore：最近章节、最近对话、近期伏笔状态
  └─ ConsistencyGuard：设定冲突、人物口吻、时间线校验
  ↓
本地 Qwen/LoRA 模型生成
  ↓
后处理 + 可选写回 Wiki/向量库/图谱
```

## 4. 小说 Wiki 目录设计

建议在当前项目新增 `data/novel_wiki/`，避免与训练数据、报告混杂。

```text
data/novel_wiki/
  index.md                         # 全局索引
  log.md                           # 摄入/写回日志
  sources/                         # 原始设定、用户材料、外部资料摘要
  projects/<novel_id>/
    bible.md                       # 小说总设定圣经
    entities/
      characters/                  # 人物卡
      factions/                    # 阵营/组织
      locations/                   # 地点
      items/                       # 道具/功法/神器/技术
    concepts/                      # 世界规则、魔法体系、制度、文化
    relations/                     # 人物关系、阵营关系、动态关系变更
    timelines/                     # 年表、章节时间线
    plots/
      arcs/                        # 主线/支线/角色弧
      foreshadows/                 # 伏笔、回收状态
      conflicts/                   # 冲突与矛盾
    chapters/
      outlines/                    # 章节细纲
      summaries/                   # 章节摘要
      canon_events/                # 已发生事实
    style/
      voice.md                     # 叙事风格
      dialogue.md                  # 对话风格和人物口吻
```

## 5. 关键页面模板

### 5.1 人物卡 `entities/characters/<name>.md`

```markdown
---
type: character
name: 林砚
aliases: [林少主]
status: alive
faction: [[entities/factions/青岚盟]]
first_seen: [[chapters/summaries/chapter-001]]
updated: 2026-05-06
---

## 核心定位
- 表层身份：
- 隐藏身份：
- 欲望：
- 恐惧：
- 底线：

## 人物口吻
- 常用句式：
- 禁忌表达：
- 情绪外显方式：

## 关系
- [[entities/characters/沈青禾]]：盟友；信任值 65；最新变化见 [[relations/lin-yan__shen-qinghe]]

## 已知事实
- 第 3 章救下沈青禾，但隐瞒真实目的。来源：[[chapters/summaries/chapter-003]]

## 矛盾/待确认
- 
```

### 5.2 关系页 `relations/<a>__<b>.md`

```markdown
---
type: relation
source: 林砚
target: 沈青禾
relation_type: alliance|family|enemy|mentor|romance|debt|secret
polarity: 0.6
tension: 0.8
trust: 0.65
updated: 2026-05-06
---

## 当前关系
- 表面：
- 实际：
- 读者已知：
- 角色 A 已知：
- 角色 B 已知：

## 关系变化时间线
- 第 1 章：初遇，互不信任。
- 第 3 章：林砚救下沈青禾，信任上升但埋下隐瞒。

## 可用互动钩子
- 误会：
- 共同目标：
- 潜在爆点：
```

### 5.3 伏笔页 `plots/foreshadows/<slug>.md`

```markdown
---
type: foreshadow
status: planted|developing|paid_off|abandoned
planted_in: chapter-002
payoff_target: chapter-018
characters: [林砚, 沈青禾]
---

## 伏笔内容
- 

## 当前读者信息差
- 读者知道：
- 角色知道：
- 作者隐藏：

## 回收方案
- 弱回收：
- 强回收：
```

## 6. 向量数据库选型

### 6.1 推荐结论

当前项目是 Windows 本地模型端 + Python/FastAPI 服务，建议分阶段：

| 阶段 | 推荐 | 原因 |
|---|---|---|
| 原型期 | Chroma 或 Qdrant Local | 嵌入式、本地落盘、接入快 |
| 单机长期写作 | Qdrant Local/Server | payload filter 友好，后续可切服务模式 |
| 大规模多小说/多用户 | Milvus Lite → Milvus Standalone/Distributed | API 可迁移，适合更大规模向量集合 |

### 6.2 本项目首选

首选 `Qdrant`：

- 本地模式可不启动独立服务，后续也能切换为 Docker/服务端部署。
- payload 过滤适合小说场景，例如按 `novel_id`、`volume`、`chapter`、`entity_type`、`canon_status`、`updated_at` 检索。
- 对“同一查询先过滤当前小说，再语义召回人物/伏笔/章节记忆”的需求比较自然。

备选 `Chroma`：如果只想最快验证，可用 `PersistentClient` 本地落盘。

备选 `Milvus Lite`：如果预计后续数据量非常大，Milvus Lite 可作为单机原型，后续迁移到 Milvus 服务端。

官方资料要点：Chroma 支持 persistent client 本地落盘；Qdrant Python client 支持 local mode 与 on-disk storage；Milvus Lite 可作为 Python 应用内嵌向量库，并与 Standalone/Distributed 共享较一致的 API。

## 7. 向量集合设计

建议不是只建一个 collection，而是按召回语义分层。

### 7.1 Collection：`novel_wiki_chunks`

用于 Markdown 页面切块召回。

字段建议：

```json
{
  "id": "sha1(novel_id + path + heading + chunk_index)",
  "text": "切块正文",
  "path": "data/novel_wiki/projects/xxx/entities/characters/lin-yan.md",
  "novel_id": "xxx",
  "page_type": "character|relation|chapter|foreshadow|world_rule",
  "entity_names": ["林砚", "沈青禾"],
  "chapter_no": 3,
  "canon_status": "canon|draft|candidate|deprecated",
  "updated_at": "2026-05-06"
}
```

### 7.2 Collection：`novel_events`

用于检索已发生事实和时间线。

```json
{
  "event_id": "chapter-003-event-002",
  "summary": "林砚救下沈青禾但隐瞒真实目的",
  "characters": ["林砚", "沈青禾"],
  "location": "雾河渡口",
  "chapter_no": 3,
  "time_order": 3020,
  "emotional_delta": {"trust": 0.2, "tension": 0.4},
  "source_path": "chapters/canon_events/chapter-003.md"
}
```

### 7.3 Collection：`novel_dialogue_voice`

用于人物口吻召回。

```json
{
  "character": "林砚",
  "scene_type": "conflict|romance|battle|strategy",
  "sample": "人物代表性对白或旁白片段",
  "tone_tags": ["克制", "反讽", "压抑"]
}
```

## 8. 图谱索引设计

向量检索适合“语义相似”，但人物关系拓扑更适合图查询。建议先用轻量方案：`SQLite + NetworkX`，后续再换 Neo4j。

### 8.1 节点类型

- `Character`：人物
- `Faction`：阵营
- `Location`：地点
- `Item`：重要道具
- `Event`：事件
- `Foreshadow`：伏笔
- `Chapter`：章节

### 8.2 边类型

- `KNOWS`：认识
- `ALLY_OF`：盟友
- `ENEMY_OF`：敌对
- `LOVES`：情感线
- `OWES`：债务/恩情
- `HIDES_SECRET_FROM`：信息差
- `APPEARS_IN`：出场
- `CAUSES`：事件因果
- `PLANTED_IN` / `PAID_OFF_IN`：伏笔埋设/回收

### 8.3 图查询示例

- 生成第 10 章前：查询“本章出场人物两跳内的关键关系与未爆雷秘密”。
- 写人物互动前：查询“林砚与沈青禾共同经历过哪些事件，信任值变化如何”。
- 设计冲突前：查询“当前阵营之间是否已有未解决冲突”。

## 9. 检索策略

不同小说任务需要不同检索包。

| 任务 | 检索内容 | 作用 |
|---|---|---|
| `info_recommend` | 同类题材设定、标签、人物模板、世界规则候选 | 生成可落库的初始设定 |
| `summary` | 小说圣经、主角卡、核心冲突、世界规则 | 保证全书梗概不偏题 |
| `outline` | 梗概、角色弧、阵营冲突、伏笔计划 | 保证分卷递进和人物推进 |
| `detail_outline` | 当前卷摘要、章节目标、人物关系、未回收伏笔 | 保证章节细纲可写、冲突足够 |
| `text_first_chapter` | 风格、主角卡、开局地点、世界规则 | 保证开篇抓人且设定一致 |
| `text_non_first_chapter` | 上章摘要、近期事件、人物状态、关系变化、伏笔状态 | 保证续写连续、不吃设定 |

## 10. Prompt 注入格式

建议在模型 messages 前注入一个“检索上下文块”，不要散乱拼接。

```text
【小说 Wiki 检索上下文】
项目：<novel_id>
任务：<task_name>

## 不可违背的硬设定
- ... 来源：entities/characters/xxx.md

## 当前人物状态
- 林砚：...
- 沈青禾：...

## 人物关系拓扑摘要
- 林砚 -> 沈青禾：盟友但存在隐瞒，trust=0.65, tension=0.8

## 近期事件
- 第 8 章：...
- 第 9 章：...

## 待推进伏笔
- 玉坠裂纹：已埋设，目标第 18 章回收。

## 生成约束
- 不得改变人物既定身份、阵营和已发生事件。
- 如需新增设定，必须写成“候选设定”，不得直接覆盖硬设定。
```

## 11. 写回策略

RAG 系统要支持“读”和“写”，但写入必须分级。

### 11.1 自动写回

- 章节摘要：正文生成完成后摘要进 `chapters/summaries/`。
- 已发生事件：抽取客观事实进 `chapters/canon_events/`。
- 人物状态：只追加“最新状态”，不覆盖旧状态。
- 伏笔状态：从 `planted` → `developing` → `paid_off`。

### 11.2 需要用户确认

- 新主线设定
- 人物死亡/复活/背叛
- 阵营关系根本变化
- 世界规则改写
- 重要 CP 或亲属关系变更

### 11.3 禁止自动覆盖

- 人物核心身份
- 已确认时间线
- 章节已发生事实
- 用户手动标记为 `canon` 的设定

## 12. 与训练链路的结合

### 12.1 SFT 数据增强

可以从 Wiki 自动生成 SFT 样本：

- 输入：任务请求 + 检索上下文。
- 输出：符合格式的梗概/大纲/细纲/正文。
- 目标：训练模型学会使用结构化世界观上下文，而不是只靠泛化能力。

### 12.2 Search-R1 / GRPO 奖励

可将“搜索”替换或扩展为 `wiki_search`：

```text
<wiki_search>{"query":"林砚和沈青禾当前关系", "type":"relation"}</wiki_search>
<information>...</information>
```

奖励函数可加入：

- 设定一致性：是否违背人物卡/时间线。
- 检索利用率：生成是否正确引用检索到的信息。
- 情节推进度：是否推进当前章节目标或伏笔。
- 人物互动质量：是否体现关系张力和口吻差异。

## 13. 建议新增模块

```text
nanochat-dgxspark-rl-main/
  novelrag/
    __init__.py
    config.py                    # novel_id、路径、向量库配置
    wiki_store.py                # Markdown Wiki 读写、模板、索引
    chunker.py                   # Markdown heading-aware chunking
    embeddings.py                # 本地/远程 embedding 封装
    vector_store_qdrant.py       # Qdrant 实现
    graph_store.py               # SQLite + NetworkX 图谱
    retriever.py                 # 混合检索与 rerank
    orchestrator.py              # 面向任务组装上下文
    consistency.py               # 设定冲突检测
    writer.py                    # 生成后抽取事实并写回
  scripts/
    novel_wiki_ingest.py         # 摄入设定/已有章节
    novel_wiki_reindex.py        # 重建向量索引和图索引
    novel_wiki_lint.py           # 断链/矛盾/孤立伏笔检查
    novel_rag_query.py           # 命令行查询测试
```

## 14. 最小可行实现 MVP

### 阶段 1：只读 RAG

1. 建立 `data/novel_wiki/projects/<novel_id>/` 目录和页面模板。
2. 实现 Markdown chunker。
3. 接入 Qdrant Local 或 Chroma Persistent。
4. 在 `deploy/openai_compat_server.py` 请求进入后，根据 `task_name` 检索并注入上下文。
5. 先不自动写回，只记录 debug 检索包。

### 阶段 2：图谱与一致性

1. 从人物卡、关系页、事件页抽取节点和边。
2. 用 SQLite 保存边表，NetworkX 提供两跳关系、共同事件、未解决冲突查询。
3. 增加 `ConsistencyGuard`：检测人物状态、时间线、已死亡人物出场等硬错误。

### 阶段 3：生成后写回

1. 正文生成后抽取章节摘要、事件、人物状态变化。
2. 低风险内容自动写回草稿区。
3. 高风险设定生成 `pending_changes.md`，由用户确认。

### 阶段 4：训练闭环

1. 从 Wiki + 检索包构造 SFT 数据。
2. 扩展 Search-R1 为 `wiki_search` 多轮工具调用。
3. 用一致性、引用正确性、伏笔推进等指标做 GRPO 奖励。

## 15. 依赖建议

基础依赖：

```text
qdrant-client>=1.14.0
sentence-transformers>=3.0.0
networkx>=3.2.0
python-frontmatter>=1.1.0
markdown-it-py>=3.0.0
```

如果选择 Chroma：

```text
chromadb>=0.5.0
```

如果选择 Milvus Lite：

```text
pymilvus>=2.5.0
```

Embedding 模型建议：

- 中文/中英混合：`BAAI/bge-m3` 或 `BAAI/bge-large-zh-v1.5`。
- 轻量本地：`BAAI/bge-small-zh-v1.5`。
- 如果显存/速度紧张，可先用 CPU embedding 离线建库，推理时只做查询向量。

## 16. 关键风险

- 只做向量检索会丢失关系拓扑，所以必须保留图谱索引。
- 自动写回如果不分级，会污染世界观；必须区分 `canon`、`draft`、`candidate`、`deprecated`。
- 检索上下文过长会挤占正文生成空间；需要按任务压缩为 1,000~2,500 中文字。
- 小说设定经常存在“角色不知道但读者知道”的信息差，关系页必须区分“读者已知”和“角色已知”。
- 训练数据要包含检索上下文，否则在线 RAG 和离线 SFT 分布不一致。

## 17. 推荐落地顺序

1. 先实现 `novelrag` 只读检索，不动训练脚本。
2. 将检索上下文注入 `deploy/openai_compat_server.py` 的非流式和流式路径。
3. 用 1 部小说样例建立人物、关系、章节摘要，验证续写一致性。
4. 再实现图谱查询和一致性检查。
5. 最后做写回与训练闭环。

## 18. 外部资料

- Chroma Python Client 文档：Persistent client 支持本地落盘。
- Qdrant 文档：Python client 支持 Local Mode，也可使用 on-disk storage。
- Milvus 文档：Milvus Lite 可嵌入 Python 应用，且可以向 Standalone/Distributed 迁移。

