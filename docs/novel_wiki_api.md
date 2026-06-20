# 小说 Wiki 与人物关系拓扑对接方案

## 1. 总体原则

模型端不接数据库，只维护本地 Wiki 文件。后端负责鉴权、业务状态、阶段稿件、可选的人物关系拓扑持久化与回显。

本地存储目录按用户和小说隔离：

```text
data/novel_wiki/
  users/
    <user_id>/
      <novel_id>/
        sources/                 # 世界观、历史、势力、设定资料
        entities/characters/      # 人物卡，可由确认后的拓扑写入
        relations/                # 静态人物关系，可由确认后的拓扑写入
        ledgers/character_states/  # 每章人物状态账本
        ledgers/foreshadows/       # 每章伏笔账本
        ledgers/timeline/          # 每章时间线/因果账本
        plots/foreshadows/         # 伏笔状态机
        chapters/summaries/       # 章节回写摘要
        chapters/canon_events/    # 已发生事实
        reports/                   # 连续性体检报告
        reports/chapters/          # 章节后自动质检报告
        index.md
        bible.md
        log.md
```

兼容说明：旧目录 `data/novel_wiki/projects/<novel_id>/` 和 `data/novel_wiki/users/<user_id>/projects/<novel_id>/` 会在首次访问时无损复制到新目录。

## 2. 人物关系拓扑策略

人物关系网应在信息推荐阶段一次性高质量生成，后续梗概、分卷大纲、细纲、正文回写不自动迭代拓扑。

拓扑只表示静态关系：家族/血缘、师承、阵营、旧识、同乡、婚约、盟友、敌对、背景交集等。章节中的信任变化、立场变化、情绪变化、临时合作只写入章节记忆，不写入静态拓扑。

推荐链路：

1. 信息推荐阶段：模型返回 `novel_topology`。
2. 后端回显给前端拓扑图，用户确认或编辑。
3. 后端保存确认后的拓扑 JSON。
4. 梗概、大纲、细纲、正文每个阶段请求都携带确认后的拓扑，模型端会把它作为稳定设定约束注入 prompt。
5. 细纲阶段要求每章 `细纲内容` 内部包含：本章目标、承接信息、核心冲突、关键人物、伏笔推进、章末钩子。
6. 正文阶段不只依赖“上一章截取 + 当前章细纲”：后端传入上一章最后几个完整段落作为局部承接，模型端额外注入近期章节记忆、未回收伏笔、人物状态账本和时间线账本。
7. 即使用户没有上传世界观文件，只要正文生成后完成章节回写，模型端也会持续完善本地 Wiki，用于后续章节的连续性约束。
8. 每章正文回写后自动执行章节质检，并更新伏笔状态机；这些结果会进入前端常驻质量面板。

## 3. 信息推荐自动返回拓扑

`POST /v1/chat/completions`

```json
{
  "model": "ChiYong-MoE-Novel-18B-A6B",
  "task_name": "info_recommend",
  "user_id": "10001",
  "novel_id": "20001",
  "stream": false,
  "messages": [
    {"role": "user", "content": "小说标题：旧城风雨\n分类：悬疑, 都市\n请生成人物信息、故事背景、简介。"}
  ],
  "novel_rag": {
    "topology": true,
    "persist_topology": false
  }
}
```

非流式响应会附带：

```json
{
  "novel_topology": {
    "user_id": "10001",
    "novel_id": "20001",
    "source": "info_recommend",
    "stage_policy": "static_initial_topology",
    "nodes": [
      {"id": "林砚", "label": "林砚", "type": "character", "role": "protagonist", "summary": "..."}
    ],
    "edges": [
      {"source": "林砚", "target": "沈青禾", "relation_type": "background", "label": "背景交集", "evidence": "...", "confidence": 0.76}
    ],
    "quality": {
      "character_count": 4,
      "edge_count": 5,
      "static_edge_count": 4,
      "warnings": []
    }
  }
}
```

`quality.warnings` 不为空时，建议后端提示用户重新生成或手动补全关系后再进入下一阶段。

## 4. 后续阶段携带拓扑

后端每个阶段都建议携带确认后的拓扑，位置任选其一：

```json
{
  "user_id": "10001",
  "novel_id": "20001",
  "task_name": "summary",
  "novel_topology": {"nodes": [], "edges": []},
  "messages": [...]
}
```

或：

```json
{
  "user_id": "10001",
  "novel_id": "20001",
  "task_name": "outline",
  "novel_rag": {
    "topology_context": {"nodes": [], "edges": []}
  },
  "messages": [...]
}
```

模型端会把拓扑注入为系统上下文，并明确要求后续阶段不得改写静态关系。

## 5. 世界观资料上传

世界观、历史、势力、地点、规则等知识库资料可直接写入本地 Wiki，不需要数据库辅助。

`POST /v1/novel/wiki/projects/{novel_id}/documents`

```json
{
  "user_id": "10001",
  "title": "青岚盟与旧城陆家设定",
  "source_type": "worldbuilding",
  "tags": ["世界观", "阵营"],
  "content": "青岚盟位于旧城以北..."
}
```

默认只写入 `sources/`。不建议用资料上传去自动更新人物关系拓扑。

## 6. 从已有信息推荐文本生成拓扑

`POST /v1/novel/wiki/projects/{novel_id}/topology/from-info`

```json
{
  "user_id": "10001",
  "title": "旧城风雨",
  "info_recommend": "人物信息：\n- 林砚：...关系锚点：与沈青禾是旧识兼临时盟友。\n\n故事背景：...\n\n简介：...",
  "persist": false
}
```

`persist=false` 时只返回拓扑 JSON，适合后端保存。`persist=true` 时会把确认后的节点和关系写入本地 Wiki。

## 7. 读取本地 Wiki 状态

`GET /v1/novel/wiki/projects/{novel_id}/status?user_id=10001`

也可以用等价的文档列表接口读取同一份状态与文件列表：

`GET /v1/novel/wiki/projects/{novel_id}/documents?user_id=10001`

```json
{
  "user_id": "10001",
  "novel_id": "20001",
  "wiki_root": "data/novel_wiki/users/10001/20001",
  "counts": {
    "documents": 3,
    "words": 18520,
    "characters": 8,
    "relations": 12,
    "topology_nodes": 8,
    "topology_edges": 12,
    "chapter_summaries": 20,
    "chapter_events": 20,
    "character_state_ledgers": 20,
    "foreshadow_ledgers": 16,
    "timeline_ledgers": 20
  },
  "documents": [
    {
      "id": "a1b2c3d4e5f6a7b8",
      "model_document_id": "a1b2c3d4e5f6a7b8",
      "title": "青岚盟与旧城陆家设定",
      "source_type": "worldbuilding",
      "word_count": 6200,
      "preview": "青岚盟位于旧城以北，早年以护送商路起家...",
      "relative_path": "sources/qinglanmeng-a1b2c3.md",
      "model_path": "data/novel_wiki/users/10001/20001/sources/qinglanmeng-a1b2c3.md",
      "sync_status": 1,
      "sync_message": "已写入模型端本地 Wiki",
      "create_time": "2026-05-08T10:12:30Z",
      "update_time": "2026-05-08T10:12:30Z"
    }
  ],
  "latest_document": {
    "id": "a1b2c3d4e5f6a7b8",
    "title": "青岚盟与旧城陆家设定",
    "word_count": 6200,
    "preview": "青岚盟位于旧城以北，早年以护送商路起家..."
  },
  "latest_chapter": null,
  "latest_continuity_report": null,
  "updated_at": "2026-05-08T10:12:31Z"
}
```

读取单个知识库文件完整内容：

`GET /v1/novel/wiki/projects/{novel_id}/documents/{document_id}?user_id=10001`

```json
{
  "user_id": "10001",
  "novel_id": "20001",
  "document": {
    "id": "a1b2c3d4e5f6a7b8",
    "title": "青岚盟与旧城陆家设定",
    "source_type": "worldbuilding",
    "word_count": 6200,
    "content": "青岚盟位于旧城以北，早年以护送商路起家...",
    "raw_markdown": "---\ntitle: \"青岚盟与旧城陆家设定\"\n---\n# 青岚盟与旧城陆家设定\n...",
    "relative_path": "sources/qinglanmeng-a1b2c3.md",
    "sync_status": 1
  }
}
```

## 8. 小说连续性体检

`GET /v1/novel/wiki/projects/{novel_id}/continuity?user_id=10001&persist=true`

如果后端的人物拓扑只保存在数据库，建议使用 `POST` 并把确认版拓扑传入，避免模型端只看本地 Wiki 时误判缺少拓扑：

`POST /v1/novel/wiki/projects/{novel_id}/continuity`

```json
{
  "user_id": "10001",
  "persist": true,
  "topology_context": {"nodes": [], "edges": []}
}
```

用于检查当前 Wiki 是否足以支撑后续高质量生成，并把报告写入 `reports/_continuity_report.md`。后端可在进入下一阶段前调用，也可给前端做“质量面板”。

```json
{
  "user_id": "10001",
  "novel_id": "20001",
  "score": 84,
  "level": "watch",
  "counts": {
    "documents": 3,
    "words": 18520,
    "topology_nodes": 8,
    "topology_edges": 12,
    "chapter_summaries": 20,
    "foreshadow_ledgers": 16
  },
  "foreshadow_state_counts": {"open": 8, "strengthened": 4, "partially_resolved": 1, "resolved": 2},
  "latest_chapter_quality": {
    "title": "第 12 章质检报告",
    "relative_path": "reports/chapters/chapter-012-quality.md"
  },
  "findings": [
    {
      "severity": "warning",
      "code": "too_many_open_foreshadows",
      "message": "未回收伏笔候选较多（14 条）。",
      "suggestion": "进入后续分卷/正文前安排回收顺序，避免结尾集中补洞。"
    }
  ],
  "severity_counts": {"critical": 0, "warning": 1, "info": 0},
  "recommended_actions": ["进入后续分卷/正文前安排回收顺序，避免结尾集中补洞。"],
  "open_foreshadows": ["陆家旧约的真正签署人仍未揭开。"],
  "relative_path": "reports/_continuity_report.md",
  "checked_at": "2026-05-08T10:12:31Z"
}
```

当前体检重点：

- 人物拓扑是否缺节点、缺关系边、存在孤立人物。
- Wiki 内链是否断裂。
- 世界观资料是否太少。
- 章节摘要与已发生事实是否成对写入。
- 人物状态账本、伏笔账本、时间线账本是否持续沉淀。
- 未回收伏笔是否过多。
- 伏笔状态机中是否有长时间未触碰的开放伏笔。
- 最近章节质检是否持续产生报告。

## 9. 章节回写

`POST /v1/novel/wiki/projects/{novel_id}/chapters/writeback`

```json
{
  "user_id": "10001",
  "chapter_no": 12,
  "title": "第十二章",
  "content": "章节正文...",
  "refine": true,
  "metadata": {
    "detail_outline": "本章目标：...\n承接信息：...\n伏笔推进：...",
    "topology": {"nodes": [], "edges": []}
  }
}
```

章节回写只沉淀近期章节摘要、已发生事实、人物状态、地点、伏笔和互动/站位变化候选，不更新静态人物关系拓扑。

建议后端传 `refine=true`，让模型端先用本地模型精炼章节记忆，再回退到规则抽取。后端也应把本章细纲放入 `metadata.detail_outline`，把确认版人物关系放入 `metadata.topology`，这样章节后质检可以判断“正文是否跑偏、是否承接细纲、是否触碰长程伏笔”。

回写后模型端会自动：

- 写入 `chapters/summaries/` 与 `chapters/canon_events/`
- 写入人物状态、伏笔、时间线账本
- 更新 `plots/foreshadows/_state.json` 与 `_state.md`
- 生成 `reports/chapters/chapter-xxx-quality.md`

也可以单独调用章节质检：

`POST /v1/novel/wiki/projects/{novel_id}/chapters/quality`

```json
{
  "user_id": "10001",
  "chapter_no": 12,
  "title": "第十二章",
  "content": "章节正文...",
  "detail_outline": "本章目标：...",
  "topology_context": {"nodes": [], "edges": []},
  "persist": true
}
```

返回 `score`、`level`、`findings`、`recommended_actions`，用于后端或前端在正文生成后回显。

正文生成时，模型端会把以下上下文作为系统消息注入：

- 必须承接的长程记忆：未回收伏笔/待兑现承诺、较久未触碰线索
- 近期 3-5 章摘要、人物状态和伏笔候选
- 近期人物状态变化
- 近期时间线/因果事实
- 已确认的人物关系拓扑
- 用户上传的世界观/规则/设定资料

这样可以避免只看上一章尾巴造成的语义丢失，也能支持跨多章伏笔的推进和回收。

## 10. 后端可选 SQL 草案

模型端不需要这些表。当前后端代码保存拓扑回显时使用 `novel_wiki_topology`，知识库文档仍由模型端按本地 Wiki 文件存储，不需要建文档表。

```sql
CREATE TABLE IF NOT EXISTS `novel_wiki_topology` (
  `id` int NOT NULL AUTO_INCREMENT,
  `n_id` int NOT NULL COMMENT '小说ID',
  `u_id` int NOT NULL COMMENT '用户ID',
  `topology_json` mediumtext NOT NULL COMMENT '静态人物关系拓扑JSON',
  `source_text` mediumtext NULL COMMENT '生成拓扑时采用的信息推荐文本',
  `source_stage` varchar(40) NOT NULL DEFAULT 'info_recommend' COMMENT '来源阶段',
  `version` int NOT NULL DEFAULT 1 COMMENT '当前版本号',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_novel_wiki_topology_user_novel` (`u_id`, `n_id`),
  KEY `idx_novel_wiki_topology_novel` (`n_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='小说静态人物关系拓扑';
```

如果后端要做版本回滚，再追加版本表即可；模型端仍只接收当前确认版拓扑 JSON。

创作关键词不进入官方标签库，建议后端单独保存为作品私有语义补充，传给模型构造 prompt；用户申请进入官方标签库时另走审核表：

```sql
CREATE TABLE IF NOT EXISTS `novel_creative_keyword` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键',
  `n_id` int NOT NULL COMMENT '小说ID',
  `u_id` int NOT NULL COMMENT '用户ID',
  `keyword` varchar(32) NOT NULL COMMENT '作品私有创作关键词',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_novel_keyword` (`n_id`, `keyword`),
  KEY `idx_user_novel` (`u_id`, `n_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='小说私有创作关键词表';

CREATE TABLE IF NOT EXISTS `novel_tag_application` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键',
  `u_id` int NOT NULL COMMENT '申请用户ID',
  `keyword` varchar(32) NOT NULL COMMENT '申请标签词',
  `reason` varchar(200) DEFAULT NULL COMMENT '申请说明',
  `status` varchar(20) NOT NULL DEFAULT 'pending' COMMENT '状态：pending/approved/rejected',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_status_time` (`status`, `create_time`),
  KEY `idx_user_time` (`u_id`, `create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='官方标签申请表';
```
