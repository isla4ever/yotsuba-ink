from __future__ import annotations

import hashlib
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


RELATION_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "family": ("父亲", "母亲", "父子", "父女", "母子", "母女", "兄", "弟", "姐", "妹", "姐姐", "妹妹", "哥哥", "弟弟", "叔侄", "叔父", "伯父", "义父", "义母", "家族", "血缘", "亲族", "宗族"),
    "romance": ("恋人", "爱人", "未婚", "婚约", "夫妻", "夫妇", "喜欢", "暗恋", "旧情", "青梅竹马"),
    "mentor": ("师父", "师傅", "师徒", "老师", "导师", "门生", "弟子", "传授"),
    "ally": ("盟友", "同伴", "队友", "合作", "伙伴", "搭档", "同盟", "并肩", "共同"),
    "enemy": ("仇人", "敌人", "敌对", "宿敌", "仇敌", "旧敌", "死敌", "追杀", "陷害", "对立"),
    "faction": ("同事", "同僚", "同门", "同族", "同宗", "阵营", "组织", "公会", "门派", "家臣", "下属", "上司", "上下级", "利益共同体"),
    "background": ("旧识", "故人", "旧案", "档案牵连", "契约债务", "情报交易", "资源合作", "同乡", "同窗", "儿时", "过去", "背景", "交集", "相识"),
}


@dataclass(frozen=True)
class WikiDocument:
    document_id: str
    user_id: str
    novel_id: str
    title: str
    source_type: str
    path: str
    tags: Tuple[str, ...]
    created_at: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(value: str, fallback: str = "item") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\\/:*?\"<>|]+", "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-._ ")
    if not text:
        digest = hashlib.sha1(fallback.encode("utf-8")).hexdigest()[:10]
        return f"{fallback}-{digest}"
    return text[:80]


def _safe_rel_path(root: Path, *parts: str) -> Path:
    target = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    if root_resolved != target and root_resolved not in target.parents:
        raise ValueError(f"Path escapes wiki root: {target}")
    return target


def _frontmatter(data: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            serialized = "[" + ", ".join(json.dumps(str(item), ensure_ascii=False) for item in value) + "]"
        else:
            serialized = json.dumps(value, ensure_ascii=False)
        lines.append(f"{key}: {serialized}")
    lines.append("---")
    return "\n".join(lines)


def _split_names(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = re.split(r"[,，、;；/\n]+", value)
    elif isinstance(value, Iterable):
        raw = [str(item) for item in value]
    else:
        raw = [str(value)]
    names: List[str] = []
    seen: set[str] = set()
    for item in raw:
        name = str(item or "").strip().strip("'\"")
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _infer_relation_type(description: str, explicit: str = "") -> str:
    text = f"{explicit} {description}"
    for relation_type, keywords in RELATION_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return relation_type
    return "connection"


class NovelWikiStore:
    """Local Markdown + JSON index store for novel worldbuilding materials."""

    def __init__(self, root: str | Path = "data/novel_wiki") -> None:
        self.root = Path(root).resolve()
        self._search_cache: Dict[str, Tuple[int, int, str]] = {}

    def ensure_project(self, novel_id: str, user_id: str = "default") -> Path:
        safe_user_id = _slugify(user_id or "default", "user")
        safe_novel_id = _slugify(novel_id, "novel")
        project = _safe_rel_path(self.root, "users", safe_user_id, safe_novel_id)
        if not project.exists():
            legacy_user_project = _safe_rel_path(self.root, "users", safe_user_id, "projects", safe_novel_id)
            legacy_global_project = _safe_rel_path(self.root, "projects", safe_novel_id)
            legacy_project = None
            if self._has_project_content(legacy_user_project):
                legacy_project = legacy_user_project
            elif safe_user_id == "default" and self._has_project_content(legacy_global_project):
                legacy_project = legacy_global_project
            if legacy_project is not None:
                shutil.copytree(legacy_project, project, dirs_exist_ok=True)
        directories = [
            project,
            project / "sources",
            project / "entities" / "characters",
            project / "entities" / "factions",
            project / "entities" / "locations",
            project / "relations",
            project / "canon",
            project / "candidates",
            project / "ledgers" / "character_states",
            project / "ledgers" / "foreshadows",
            project / "ledgers" / "timeline",
            project / "plots" / "foreshadows",
            project / "chapters" / "summaries",
            project / "chapters" / "canon_events",
            project / "indexes",
            project / "reports",
            project / "reports" / "chapters",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        for filename, title in (("index.md", "小说 Wiki 索引"), ("log.md", "小说 Wiki 日志"), ("bible.md", "小说设定圣经")):
            path = project / filename
            if not path.exists():
                path.write_text(f"# {title}\n\n", encoding="utf-8")
        return project

    def _has_project_content(self, project: Path) -> bool:
        if not project.exists() or not project.is_dir():
            return False
        content_dirs = ("sources", "entities", "relations", "chapters")
        if any((project / name).exists() for name in content_dirs):
            return True
        return any((project / name).exists() for name in ("index.md", "bible.md", "log.md"))

    def ingest_document(
        self,
        novel_id: str,
        title: str,
        content: str,
        source_type: str = "text",
        tags: Optional[Sequence[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "default",
    ) -> WikiDocument:
        project = self.ensure_project(novel_id, user_id=user_id)
        clean_title = title.strip() or "未命名资料"
        document_id = hashlib.sha1(f"{user_id}\n{novel_id}\n{clean_title}\n{content}".encode("utf-8")).hexdigest()[:16]
        slug = _slugify(clean_title, document_id)
        path = project / "sources" / f"{slug}.md"
        if path.exists():
            path = project / "sources" / f"{slug}-{document_id[:6]}.md"
        created_at = _utc_now()
        tag_values = tuple(_split_names(tags or []))
        front = _frontmatter(
            {
                "type": "source",
                "document_id": document_id,
                "title": clean_title,
                "source_type": source_type,
                "tags": tag_values,
                "created_at": created_at,
                **(metadata or {}),
            }
        )
        body = f"{front}\n\n# {clean_title}\n\n## 原始内容\n\n{content.strip()}\n"
        path.write_text(body, encoding="utf-8")
        self._append_log(project, f"ingest | {clean_title}", [f"Source: {path.relative_to(project).as_posix()}"])
        self._append_index(project, f"- [[sources/{path.stem}]]：{clean_title}（{source_type}）")
        return WikiDocument(document_id, user_id, novel_id, clean_title, source_type, str(path), tag_values, created_at)

    def upsert_character(
        self,
        novel_id: str,
        name: str,
        user_id: str = "default",
        profile: str = "",
        aliases: Optional[Sequence[str]] = None,
        faction: str = "",
        background: str = "",
    ) -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("character name is required")
        path = project / "entities" / "characters" / f"{_slugify(clean_name, clean_name)}.md"
        created = not path.exists()
        front = _frontmatter(
            {
                "type": "character",
                "name": clean_name,
                "aliases": tuple(_split_names(aliases or [])),
                "faction": faction,
                "updated_at": _utc_now(),
            }
        )
        body = (
            f"{front}\n\n# {clean_name}\n\n"
            f"## 核心定位\n{profile.strip() or '- 待补充。'}\n\n"
            f"## 家族/背景\n{background.strip() or '- 待补充。'}\n\n"
            "## 关系\n- 待补充。\n\n"
            "## 已知事实\n- 待补充。\n"
        )
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            addition = []
            if profile.strip():
                addition.append(f"\n## 补充定位 {_utc_now()}\n{profile.strip()}\n")
            if background.strip():
                addition.append(f"\n## 补充背景 {_utc_now()}\n{background.strip()}\n")
            if addition:
                path.write_text(existing.rstrip() + "\n" + "".join(addition), encoding="utf-8")
        else:
            path.write_text(body, encoding="utf-8")
            self._append_index(project, f"- [[entities/characters/{path.stem}]]：人物 {clean_name}")
        self._append_log(project, f"character | {clean_name}", ["Created" if created else "Updated", f"Path: {path.relative_to(project).as_posix()}"])
        return {"name": clean_name, "path": str(path), "created": created}

    def upsert_relation(
        self,
        novel_id: str,
        source: str,
        target: str,
        user_id: str = "default",
        relation_type: str = "",
        description: str = "",
        evidence: str = "",
    ) -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        source_name = source.strip()
        target_name = target.strip()
        if not source_name or not target_name:
            raise ValueError("source and target are required")
        inferred_type = _infer_relation_type(description, relation_type)
        slug = f"{_slugify(source_name, source_name)}__{_slugify(target_name, target_name)}"
        path = project / "relations" / f"{slug}.md"
        created = not path.exists()
        front = _frontmatter(
            {
                "type": "relation",
                "source": source_name,
                "target": target_name,
                "relation_type": inferred_type,
                "updated_at": _utc_now(),
            }
        )
        body = (
            f"{front}\n\n# {source_name} ↔ {target_name}\n\n"
            f"## 关系类型\n- {inferred_type}\n\n"
            f"## 关系说明\n{description.strip() or '- 待补充。'}\n\n"
            f"## 证据/来源\n{evidence.strip() or '- 待补充。'}\n"
        )
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            addition = f"\n## 补充 {_utc_now()}\n- 类型：{inferred_type}\n- 说明：{description.strip() or '待补充。'}\n"
            if evidence.strip():
                addition += f"- 证据：{evidence.strip()}\n"
            path.write_text(existing.rstrip() + "\n" + addition, encoding="utf-8")
        else:
            path.write_text(body, encoding="utf-8")
            self._append_index(project, f"- [[relations/{path.stem}]]：{source_name} 与 {target_name} 的 {inferred_type} 关系")
        self._append_log(project, f"relation | {source_name} - {target_name}", ["Created" if created else "Updated", f"Path: {path.relative_to(project).as_posix()}"])
        return {"source": source_name, "target": target_name, "relation_type": inferred_type, "path": str(path), "created": created}

    def extract_relations(self, novel_id: str, text: str, characters: Optional[Sequence[str]] = None, user_id: str = "default") -> Dict[str, Any]:
        names = _split_names(characters or [])
        relations: List[Dict[str, str]] = []
        sentences = [part.strip() for part in re.split(r"[。！？!?\n]+", text) if part.strip()]
        for sentence in sentences:
            present = [name for name in names if name and name in sentence]
            if len(present) < 2:
                continue
            relation_type = _infer_relation_type(sentence)
            for idx, source in enumerate(present):
                for target in present[idx + 1 :]:
                    relations.append({"source": source, "target": target, "relation_type": relation_type, "description": sentence})
        unique: Dict[Tuple[str, str, str], Dict[str, str]] = {}
        for relation in relations:
            key = (relation["source"], relation["target"], relation["relation_type"])
            unique.setdefault(key, relation)
        return {"user_id": user_id, "novel_id": novel_id, "characters": names, "relations": list(unique.values())}

    def build_topology(self, novel_id: str, user_id: str = "default") -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        static_path = project / "canon" / "static_topology.json"
        if static_path.exists():
            try:
                parsed = json.loads(static_path.read_text(encoding="utf-8"))
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                parsed["user_id"] = user_id
                parsed["novel_id"] = novel_id
                parsed.setdefault("nodes", [])
                parsed.setdefault("edges", [])
                return parsed
        nodes: Dict[str, Dict[str, str]] = {}
        edges: List[Dict[str, str]] = []
        for char_path in (project / "entities" / "characters").glob("*.md"):
            name = self._read_frontmatter_value(char_path, "name") or char_path.stem
            nodes[name] = {"id": name, "label": name, "type": "character", "path": str(char_path)}
        for relation_path in (project / "relations").glob("*.md"):
            source = self._read_frontmatter_value(relation_path, "source")
            target = self._read_frontmatter_value(relation_path, "target")
            relation_type = self._read_frontmatter_value(relation_path, "relation_type") or "connection"
            if not source or not target:
                continue
            nodes.setdefault(source, {"id": source, "label": source, "type": "character", "path": ""})
            nodes.setdefault(target, {"id": target, "label": target, "type": "character", "path": ""})
            edges.append({"source": source, "target": target, "relation_type": relation_type, "label": relation_type, "path": str(relation_path)})
        return {"user_id": user_id, "novel_id": novel_id, "nodes": list(nodes.values()), "edges": edges}

    def project_status(self, novel_id: str, user_id: str = "default") -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        topology = self.build_topology(novel_id, user_id=user_id)
        source_paths = sorted((project / "sources").glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        summary_paths = sorted((project / "chapters" / "summaries").glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        event_paths = sorted((project / "chapters" / "canon_events").glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        character_paths = list((project / "entities" / "characters").glob("*.md"))
        relation_paths = list((project / "relations").glob("*.md"))
        ledger_state_paths = list((project / "ledgers" / "character_states").glob("*.md"))
        ledger_foreshadow_paths = list((project / "ledgers" / "foreshadows").glob("*.md"))
        ledger_timeline_paths = list((project / "ledgers" / "timeline").glob("*.md"))
        report_path = project / "reports" / "_continuity_report.md"
        quality_paths = sorted((project / "reports" / "chapters").glob("*-quality.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        foreshadow_states = self._load_foreshadow_states(project)
        documents = [self._source_document_summary(project, path) for path in source_paths]
        total_words = sum(int(item.get("word_count", 0) or 0) for item in documents)
        return {
            "user_id": user_id,
            "novel_id": novel_id,
            "wiki_root": str(project),
            "counts": {
                "documents": len(source_paths),
                "words": total_words,
                "characters": len(character_paths),
                "relations": len(relation_paths),
                "topology_nodes": len(topology.get("nodes", [])),
                "topology_edges": len(topology.get("edges", [])),
                "chapter_summaries": len(summary_paths),
                "chapter_events": len(event_paths),
                "character_state_ledgers": len(ledger_state_paths),
                "foreshadow_ledgers": len(ledger_foreshadow_paths),
                "foreshadow_states": len(foreshadow_states),
                "timeline_ledgers": len(ledger_timeline_paths),
                "chapter_quality_reports": len(quality_paths),
            },
            "documents": documents,
            "latest_document": documents[0] if documents else None,
            "latest_chapter": self._latest_page_summary(project, summary_paths[0]) if summary_paths else None,
            "latest_continuity_report": self._latest_page_summary(project, report_path) if report_path.exists() else None,
            "latest_chapter_quality": self._latest_page_summary(project, quality_paths[0]) if quality_paths else None,
            "foreshadow_state_counts": self._foreshadow_state_counts(foreshadow_states),
            "updated_at": _utc_now(),
        }

    def get_document(self, novel_id: str, document_id: str, user_id: str = "default") -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        lookup = str(document_id or "").strip()
        if not lookup:
            raise ValueError("document_id is required")
        for path in sorted((project / "sources").glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
            summary = self._source_document_summary(project, path)
            aliases = {
                str(summary.get("id") or ""),
                str(summary.get("model_document_id") or ""),
                str(summary.get("relative_path") or ""),
                path.name,
                path.stem,
            }
            if lookup not in aliases:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            body = self._source_document_body(text)
            detail = dict(summary)
            detail.update(
                {
                    "content": body,
                    "raw_markdown": text,
                    "content_word_count": len(re.sub(r"\s+", "", body)),
                }
            )
            return {"user_id": user_id, "novel_id": novel_id, "document": detail}
        raise FileNotFoundError(f"Document not found: {lookup}")

    def build_topology_from_info_recommend(
        self,
        novel_id: str,
        info_text: str,
        user_id: str = "default",
        title: str = "",
        persist: bool = False,
    ) -> Dict[str, Any]:
        """Build a frontend-friendly character topology from info_recommend text.

        This intentionally focuses on stable background relations such as family,
        faction, mentor, old acquaintance, ally/enemy, not plot behavior trends.
        """
        characters = self._parse_info_characters(info_text)
        background = self._extract_section(info_text, "故事背景", ("简介",))
        intro = self._extract_section(info_text, "简介", ())
        context = f"{background}\n{intro}\n{info_text}"
        nodes: Dict[str, Dict[str, Any]] = {}
        for item in characters:
            nodes[item["name"]] = {
                "id": item["name"],
                "label": item["name"],
                "type": "character",
                "role": item.get("role", ""),
                "summary": item.get("description", ""),
            }

        edges: List[Dict[str, Any]] = []
        seen_edges: set[Tuple[str, str, str]] = set()

        def add_edge(source: str, target: str, relation_type: str, label: str, evidence: str, confidence: float = 0.65) -> None:
            if not source or not target or source == target:
                return
            source_name = source.strip()
            target_name = target.strip()
            if source_name not in nodes or target_name not in nodes:
                return
            ordered = tuple(sorted((source_name, target_name)))
            key = (ordered[0], ordered[1], relation_type)
            if key in seen_edges:
                return
            seen_edges.add(key)
            edges.append(
                {
                    "source": source_name,
                    "target": target_name,
                    "relation_type": relation_type,
                    "label": label,
                    "evidence": evidence[:180],
                    "confidence": confidence,
                }
            )

        names = [item["name"] for item in characters]
        sentences = [_clean_text_for_relation(part) for part in re.split(r"[。！？!?\n]+", context) if part.strip()]
        for sentence in sentences:
            present = [name for name in names if name in sentence]
            if len(present) < 2:
                continue
            subject = self._line_subject(sentence, names)
            if not subject and any(marker in sentence for marker in ("关系锚点", "关系：", "关系:")):
                continue
            if subject:
                explicit_edges = self._extract_explicit_relation_edges(sentence, subject, names)
                for edge in explicit_edges:
                    add_edge(
                        subject,
                        edge["target"],
                        edge["relation_type"],
                        edge["label"],
                        edge["evidence"],
                        0.88,
                    )
                if not explicit_edges:
                    for target in present:
                        if target == subject:
                            continue
                        relation_type = self._infer_pair_relation(sentence, subject, target)
                        if relation_type == "connection":
                            continue
                        add_edge(subject, target, relation_type, self._relation_label(relation_type, sentence), sentence, 0.66)
                continue
            if not self._is_static_relation_sentence(sentence):
                continue
            relation_type = _infer_relation_type(sentence)
            if relation_type == "connection":
                continue
            label = self._relation_label(relation_type, sentence)
            for idx, source in enumerate(present):
                for target in present[idx + 1 :]:
                    add_edge(source, target, relation_type, label, sentence, 0.62)

        for item in characters:
            name = item["name"]
            description = item.get("description", "")
            explicit_edges = self._extract_explicit_relation_edges(description, name, names)
            for edge in explicit_edges:
                add_edge(name, edge["target"], edge["relation_type"], edge["label"], edge["evidence"], 0.9)
            if explicit_edges:
                continue
            for other in names:
                if other == name or other not in description:
                    continue
                relation_type = self._infer_pair_relation(description, name, other)
                add_edge(name, other, relation_type, self._relation_label(relation_type, description), description, 0.68)

        static_edges = [edge for edge in edges if edge.get("relation_type") != "connection"]
        relation_types = {str(edge.get("relation_type") or "") for edge in static_edges}
        connected_names = {str(edge.get("source") or "") for edge in edges} | {str(edge.get("target") or "") for edge in edges}
        quality_warnings: List[str] = []
        if names and len(static_edges) < max(1, min(3, len(names) - 1)):
            quality_warnings.append("静态关系边偏少，建议重新生成或要求信息推荐补足家族、师承、阵营、旧识、盟友、敌对等关系锚点。")
        isolated = [name for name in names if not any(edge.get("source") == name or edge.get("target") == name for edge in edges)]
        if isolated:
            quality_warnings.append("存在未连接人物：" + "、".join(isolated[:8]))
        if len(names) < 4:
            quality_warnings.append("核心人物数量偏少，建议至少包含主角、对手、盟友、灰度角色和剧情支点。")
        if len(names) > 0 and len(static_edges) < max(2, len(names) - 1):
            quality_warnings.append("静态关系密度偏低，后续梗概和大纲可能缺少人物牵引。")
        if len(relation_types) < 3 and len(static_edges) >= 3:
            quality_warnings.append("关系类型不够丰富，建议增加家族、敌对、阵营、师承、旧识等差异化关系。")
        if any(edge.get("relation_type") == "connection" for edge in edges):
            quality_warnings.append("存在泛化主线交集边，建议改为更明确的静态关系。")

        coverage_ratio = (len(connected_names & set(names)) / len(names)) if names else 0.0
        edge_target = max(1, len(names))
        edge_ratio = min(1.0, len(static_edges) / edge_target)
        diversity_ratio = min(1.0, len(relation_types) / 4)
        score = round(35 + coverage_ratio * 25 + edge_ratio * 25 + diversity_ratio * 15 - len(quality_warnings) * 6)
        score = max(0, min(100, score))
        level = "good" if score >= 85 else "watch" if score >= 68 else "risk"

        topology = {
            "user_id": user_id,
            "novel_id": novel_id,
            "title": title,
            "nodes": list(nodes.values()),
            "edges": edges,
            "source": "info_recommend",
            "stage_policy": "static_initial_topology",
            "quality": {
                "character_count": len(names),
                "edge_count": len(edges),
                "static_edge_count": len(static_edges),
                "relation_type_count": len(relation_types),
                "coverage_ratio": round(coverage_ratio, 3),
                "score": score,
                "level": level,
                "warnings": quality_warnings,
            },
            "note": "人物关系网应在信息推荐阶段高质量定稿。关系边偏向家族、背景、阵营、旧识、师承、敌友等静态关系，不随梗概、大纲、细纲或正文回写自动迭代。",
        }
        if persist:
            topology = self.persist_topology(novel_id, topology, user_id=user_id, title=title, source_text=info_text)
        return topology

    def persist_topology(
        self,
        novel_id: str,
        topology: Dict[str, Any],
        user_id: str = "default",
        title: str = "",
        source_text: str = "",
    ) -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        normalized = dict(topology or {})
        normalized["user_id"] = user_id
        normalized["novel_id"] = novel_id
        if title and not normalized.get("title"):
            normalized["title"] = title
        normalized.setdefault("source", "info_recommend")
        normalized.setdefault("stage_policy", "static_initial_topology")
        nodes = normalized.get("nodes") if isinstance(normalized.get("nodes"), list) else []
        edges = normalized.get("edges") if isinstance(normalized.get("edges"), list) else []
        created_characters = 0
        created_relations = 0
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("label") or node.get("id") or "").strip()
            if not name:
                continue
            path = project / "entities" / "characters" / f"{_slugify(name, name)}.md"
            if path.exists():
                continue
            self.upsert_character(
                novel_id,
                name,
                user_id=user_id,
                profile=str(node.get("summary") or node.get("description") or ""),
                background="由信息推荐阶段的人物关系拓扑同步。",
            )
            created_characters += 1
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source") or "").strip()
            target = str(edge.get("target") or "").strip()
            if not source or not target or source == target:
                continue
            slug = f"{_slugify(source, source)}__{_slugify(target, target)}"
            path = project / "relations" / f"{slug}.md"
            if path.exists():
                continue
            self.upsert_relation(
                novel_id=novel_id,
                user_id=user_id,
                source=source,
                target=target,
                relation_type=str(edge.get("relation_type") or ""),
                description=str(edge.get("evidence") or edge.get("label") or ""),
                evidence="info_recommend_topology",
            )
            created_relations += 1
        payload_path = project / "canon" / "static_topology.json"
        payload_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        md_lines = [
            _frontmatter({"type": "static_topology", "title": normalized.get("title") or title, "updated_at": _utc_now()}),
            "",
            "# 静态人物关系拓扑",
            "",
            "## 人物",
        ]
        for node in nodes:
            if isinstance(node, dict):
                md_lines.append(f"- {node.get('label') or node.get('id')}：{node.get('summary') or ''}")
        md_lines.extend(["", "## 关系"])
        for edge in edges:
            if isinstance(edge, dict):
                md_lines.append(f"- {edge.get('source')} -> {edge.get('target')}：{edge.get('label') or edge.get('relation_type')}；{edge.get('evidence') or ''}")
        if source_text:
            md_lines.extend(["", "## 来源信息推荐", source_text[:4000]])
        md_path = payload_path.with_suffix(".md")
        md_path.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")
        self._append_index(project, "- [[canon/static_topology]]：静态人物关系拓扑")
        self._append_log(
            project,
            "topology-sync | info_recommend",
            [f"Characters created: {created_characters}", f"Relations created: {created_relations}", f"Path: {payload_path.relative_to(project).as_posix()}"],
        )
        normalized["wiki_status"] = self.project_status(novel_id, user_id=user_id)
        return normalized

    def search(self, novel_id: str, query: str, limit: int = 8, user_id: str = "default", task_name: str = "") -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        query_terms = self._search_terms(query)
        pages = self._candidate_search_pages(project, task_name=task_name)
        scored: List[Tuple[int, Path, str]] = []
        for page in pages:
            text = self._cached_page_text(page)
            if not text:
                continue
            score = sum(text.count(term) * 3 + page.name.count(term) * 5 for term in query_terms)
            if query and query in text:
                score += 10
            if score <= 0:
                continue
            snippet = self._make_snippet(text, query_terms or [query])
            scored.append((score, page, snippet))
        scored.sort(key=lambda item: item[0], reverse=True)
        return {
            "user_id": user_id,
            "novel_id": novel_id,
            "query": query,
            "results": [
                {"score": score, "path": str(path), "relative_path": path.relative_to(project).as_posix(), "snippet": snippet}
                for score, path, snippet in scored[: max(1, min(limit, 50))]
            ],
        }

    def build_rag_context(self, novel_id: str, query: str, task_name: str = "", limit: int = 6, user_id: str = "default", topology: Optional[Dict[str, Any]] = None, current_volume: Optional[int] = None) -> str:
        project = self.ensure_project(novel_id, user_id=user_id)
        topology = topology if isinstance(topology, dict) else self.build_topology(novel_id, user_id=user_id)
        recent_limit = 5 if task_name in {"text", "text_first_chapter", "text_non_first_chapter"} else 3

        with ThreadPoolExecutor(max_workers=3) as executor:
            search_future = executor.submit(self.search, novel_id, query, limit, user_id, task_name)
            recent_future = executor.submit(self._recent_chapter_memory, project, task_name, recent_limit, current_volume)
            long_future = executor.submit(self._long_range_memory, project, task_name)
            search_result = search_future.result()
            recent_memory = recent_future.result()
            long_range_memory = long_future.result()
        worldbuilding_terms = self._worldbuilding_term_memory(project)

        lines: List[str] = [
            "【小说 Wiki 检索上下文】",
            f"用户：{user_id}",
            f"项目：{novel_id}",
            f"任务：{task_name or 'unknown'}",
            "",
        ]
        if worldbuilding_terms:
            lines.append("## 世界观硬设定")
            lines.append("说明：以下来自用户上传的世界观/设定资料，优先级仅次于明确的章节细纲。正文不得泛化替换这些术语；涉及异常、调查、地点或规则时，应优先使用原始规则名并按规则推进。")
            lines.extend(worldbuilding_terms)
            lines.append("")
        if long_range_memory:
            lines.append("## 必须承接的长程记忆")
            lines.append("说明：这部分优先级最高，正文和细纲不得无视。")
            lines.extend(long_range_memory)
            lines.append("")
        if recent_memory:
            lines.append("## 近期章节记忆")
            lines.extend(recent_memory)
            lines.append("")
        if topology.get("nodes") or topology.get("edges"):
            lines.append("## 人物关系拓扑")
            lines.append("说明：这是信息推荐阶段形成的静态人物关系网。后续阶段必须保持家族、师承、阵营、旧识、敌友等关系一致，只能推进事件、立场、信任与情绪状态，不能改写静态关系。")
            node_summaries = []
            for node in topology.get("nodes", [])[:12]:
                name = node.get("label") or node.get("id")
                summary = node.get("summary") or node.get("role") or ""
                if name:
                    node_summaries.append(f"- {name}：{str(summary)[:120] if summary else '人物节点'}")
            if node_summaries:
                lines.append("人物节点：")
                lines.extend(node_summaries)
            if topology.get("edges"):
                lines.append("关系边：")
            for edge in topology.get("edges", [])[:12]:
                source = edge.get("source", "")
                target = edge.get("target", "")
                label = edge.get("label") or edge.get("relation_type") or "人物关系"
                evidence = str(edge.get("evidence") or "").strip()
                if source and target:
                    suffix = f"；依据：{evidence[:90]}" if evidence else ""
                    lines.append(f"- {source} -> {target}：{label}{suffix}")
            lines.append("")
        results = search_result.get("results", [])
        if results:
            lines.append("## 相关设定/资料")
            for item in results[:limit]:
                relative_path = item.get("relative_path", item.get("path", ""))
                snippet = item.get("snippet", "")
                lines.append(f"- 来源：{relative_path}\n  摘要：{snippet}")
            lines.append("")
        lines.extend(
            [
                "## 使用约束",
                "- 优先遵守上述 Wiki 中的既定世界观、人物关系、阵营与已上传资料。",
                "- 若本章涉及异常现象、调查线索、专有地点、禁忌或能力规则，正文必须自然使用 Wiki 的原始术语和规则名，不要只写成泛泛的旧港、磁带、频率。",
                "- 不得随意改写家族、师承、阵营、旧识、敌友等静态关系。",
                "- 人物关系拓扑只作为稳定设定约束；章节中可以出现信任变化、情绪变化、阶段站位变化，但不得把它们当作新的静态拓扑。",
                "- 正文生成必须照顾近期章节记忆与长程连续性记忆：人物状态、未回收伏笔、已发生事实、时间线不能断裂。",
                "- 对未回收伏笔可以推进、强化、阶段回收或暂时保留，但不能无视已经铺设的线索。",
                "- 如需新增设定，请作为候选补充，不要覆盖已确认设定。",
            ]
        )
        text = "\n".join(lines).strip()
        return text[:3600]

    def _chapter_slug(self, chapter_no: int, volume_no: Optional[int] = None) -> str:
        safe_chapter_no = max(1, int(chapter_no or 1))
        try:
            safe_volume_no = int(volume_no or 0)
        except Exception:
            safe_volume_no = 0
        if safe_volume_no > 0:
            return f"volume-{safe_volume_no:02d}-chapter-{safe_chapter_no:03d}"
        return f"chapter-{safe_chapter_no:03d}"

    def _chapter_label(self, chapter_no: int, volume_no: Optional[int] = None) -> str:
        try:
            safe_volume_no = int(volume_no or 0)
        except Exception:
            safe_volume_no = 0
        if safe_volume_no > 0:
            return f"第 {safe_volume_no} 卷第 {chapter_no} 章"
        return f"第 {chapter_no} 章"

    def writeback_chapter(
        self,
        novel_id: str,
        chapter_no: int,
        title: str,
        content: str,
        user_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        refined_memory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        safe_chapter_no = max(1, int(chapter_no or 1))
        try:
            volume_no = int((metadata or {}).get("volume") or (metadata or {}).get("volume_no") or 0) or None
        except Exception:
            volume_no = None
        chapter_slug = self._chapter_slug(safe_chapter_no, volume_no)
        chapter_label = self._chapter_label(safe_chapter_no, volume_no)
        clean_title = title.strip() or f"{chapter_label}"
        clean_content = _clean_text_for_relation(content)
        summary = self._chapter_summary(clean_content)
        characters = self._characters_mentioned(project, clean_content)
        relations = self.extract_relations(novel_id, clean_content, characters=characters, user_id=user_id).get("relations", [])
        character_states = self._extract_character_state_candidates(clean_content, characters)
        locations = self._extract_location_candidates(clean_content)
        foreshadows = self._extract_foreshadow_candidates(clean_content)
        events = self._extract_event_candidates(clean_content)
        timeline_events = self._extract_timeline_candidates(clean_content)
        if isinstance(refined_memory, dict):
            summary = self._pick_refined_text(refined_memory.get("chapter_summary"), summary, max_chars=520)
            character_states = self._merge_refined_items(refined_memory.get("character_states"), character_states, limit=12)
            locations = self._merge_refined_items(refined_memory.get("locations"), locations, limit=10)
            foreshadows = self._merge_refined_items(refined_memory.get("foreshadows"), foreshadows, limit=10)
            events = self._merge_refined_items(refined_memory.get("events"), events, limit=10)
            timeline_events = self._merge_refined_items(refined_memory.get("timeline"), timeline_events, limit=8)
        foreshadows = self._filter_foreshadow_items(foreshadows, limit=7)
        summary_path = project / "chapters" / "summaries" / f"{chapter_slug}.md"
        event_path = project / "chapters" / "canon_events" / f"{chapter_slug}.md"
        if volume_no:
            legacy_slug = self._chapter_slug(safe_chapter_no, None)
            if legacy_slug != chapter_slug:
                for legacy_path in (
                    project / "chapters" / "summaries" / f"{legacy_slug}.md",
                    project / "chapters" / "canon_events" / f"{legacy_slug}.md",
                ):
                    try:
                        if legacy_path.exists() and legacy_path.is_file():
                            legacy_path.unlink()
                    except Exception:
                        pass
        front = _frontmatter(
            {
                "type": "chapter_summary",
                "volume": volume_no,
                "chapter_no": safe_chapter_no,
                "chapter_key": chapter_slug,
                "title": clean_title,
                "characters": characters,
                "updated_at": _utc_now(),
                **(metadata or {}),
            }
        )
        summary_body = (
            f"{front}\n\n# {clean_title}\n\n"
            f"## 章节摘要\n{summary}\n\n"
            "## 出场人物\n"
            + ("\n".join(f"- [[entities/characters/{_slugify(name, name)}|{name}]]" for name in characters) or "- 暂无自动识别。")
            + "\n\n## 人物状态候选\n"
            + ("\n".join(f"- {item}" for item in character_states) or "- 暂无自动识别。")
            + "\n\n## 互动/站位变化候选（不更新静态人物关系拓扑）\n"
            + ("\n".join(f"- {item.get('source')} -> {item.get('target')}：{item.get('relation_type')}；{item.get('description')}" for item in relations[:12]) or "- 暂无自动识别。")
            + "\n\n## 地点/场景候选\n"
            + ("\n".join(f"- {item}" for item in locations) or "- 暂无自动识别。")
            + "\n\n## 伏笔候选\n"
            + ("\n".join(f"- {item}" for item in foreshadows) or "- 暂无自动识别。")
            + "\n"
        )
        event_body = (
            f"{_frontmatter({'type': 'chapter_events', 'volume': volume_no, 'chapter_no': safe_chapter_no, 'chapter_key': chapter_slug, 'title': clean_title, 'updated_at': _utc_now()})}\n\n"
            f"# {clean_title} 已发生事实\n\n"
            "## 客观事实候选\n"
            + "\n".join(f"- {item}" for item in events)
            + "\n\n## 时间线/因果候选\n"
            + ("\n".join(f"- {item}" for item in timeline_events) or "- 暂无自动识别。")
            + "\n"
        )
        summary_path.write_text(summary_body, encoding="utf-8")
        event_path.write_text(event_body, encoding="utf-8")
        self._append_character_state_updates(project, safe_chapter_no, clean_title, character_states, volume_no)
        self._append_ledgers(project, safe_chapter_no, clean_title, character_states, foreshadows, timeline_events, volume_no)
        foreshadow_state = self._update_foreshadow_state_machine(project, safe_chapter_no, clean_title, foreshadows, clean_content, volume_no)
        quality = self.quality_check_chapter(
            novel_id,
            chapter_no=safe_chapter_no,
            title=clean_title,
            content=clean_content,
            user_id=user_id,
            detail_outline=str((metadata or {}).get("detail_outline") or ""),
            topology=(metadata or {}).get("topology") if isinstance((metadata or {}).get("topology"), dict) else None,
            persist=True,
            volume_no=volume_no,
        )
        self._append_index(project, f"- [[chapters/summaries/{chapter_slug}]]：{clean_title} 摘要")
        self._append_index(project, f"- [[chapters/canon_events/{chapter_slug}]]：{clean_title} 已发生事实")
        self._append_log(
            project,
            f"chapter-writeback | {clean_title}",
            [
                f"Summary: {summary_path.relative_to(project).as_posix()}",
                f"Events: {event_path.relative_to(project).as_posix()}",
                f"Characters: {', '.join(characters) if characters else 'none'}",
            ],
        )
        return {
            "novel_id": novel_id,
            "volume": volume_no,
            "chapter_no": safe_chapter_no,
            "chapter_key": chapter_slug,
            "summary_path": str(summary_path),
            "event_path": str(event_path),
            "characters": characters,
            "relations": relations,
            "relationship_events": relations,
            "relationship_policy": "chapter writeback records dynamic interaction candidates only; it does not update the static character topology.",
            "character_states": character_states,
            "locations": locations,
            "foreshadows": foreshadows,
            "foreshadow_state": foreshadow_state,
            "events": events,
            "quality": quality,
            "refined": bool(refined_memory),
        }

    def quality_check_chapter(
        self,
        novel_id: str,
        chapter_no: int,
        title: str,
        content: str,
        user_id: str = "default",
        detail_outline: str = "",
        topology: Optional[Dict[str, Any]] = None,
        persist: bool = True,
        volume_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        clean_content = _clean_text_for_relation(content)
        clean_outline = _clean_text_for_relation(detail_outline)
        topology = topology if isinstance(topology, dict) else self.build_topology(novel_id, user_id=user_id)
        findings: List[Dict[str, Any]] = []

        def add(severity: str, code: str, message: str, suggestion: str = "") -> None:
            findings.append({"severity": severity, "code": code, "message": message, "suggestion": suggestion})

        compact_len = len(re.sub(r"\s+", "", clean_content))
        leakage_markers = (
            "主要人物和他们的行为",
            "故事情节",
            "直接输出小说正文",
            "请根据以上信息",
            "输出要求",
            "章节标题",
            "章節標題",
            "细纲内容",
            "細綱內容",
            "静态关系铁律",
            "静态关系不变",
            "角色职能定位",
            "剧情推进逻辑",
            "关系恒定",
            "核心冲突",
            "节奏把控",
            "家族/血缘",
            "不可更改",
            "将抽象",
            "落地为具体",
            "看见第一反应",
            "看见1.",
            "看见2.",
            "':{",
            '":{',
            "全链路质量测试",
            "质量测试体系",
            "全链路的质量",
        )
        if any(marker in clean_content for marker in leakage_markers) or re.search(
            r"(^|\n|\s)\d+\s*[.、:：]\s*(静态关系|关系恒定|角色职能|剧情推进|核心冲突|节奏把控)",
            clean_content,
        ):
            add(
                "critical",
                "structural_leakage",
                "正文混入了提示词、结构化字段或细纲内部说明。",
                "重新生成正文；生成前先清洗细纲，正文输出阶段禁止出现 JSON、字段名、编号说明和提示词原文。",
            )
        if re.search(r"['\"“”‘’]\s*(?:章节标题|章節標題|细纲内容|細綱內容)\s*['\"“”‘’]?\s*[:：]", clean_content):
            add(
                "critical",
                "raw_field_leakage",
                "正文残留了结构化字段名或键值片段。",
                "重新生成正文；进入正文前应先修复细纲解析结果，禁止把字段名写入小说正文。",
            )
        traditional_markers = ("章節", "標題", "細綱", "檔案", "觀瀾", "許", "蘇", "與", "舊案", "視線", "贺今遙")
        traditional_hits = [marker for marker in traditional_markers if marker in clean_content]
        if traditional_hits:
            add(
                "warning",
                "mixed_simplified_traditional",
                "正文出现明显繁简混用。",
                "统一为简体中文；优先检查细纲归一化和模型输出后处理。",
            )
        awkward_patterns = (
            "围绕而是",
            "的气息还压在",
            "关于“并在此过程中”",
            "防风夹克拉克",
            "因为而是",
            "围绕这让",
            "把这一章真正",
        )
        if any(pattern in clean_content for pattern in awkward_patterns):
            add(
                "warning",
                "awkward_source_splice",
                "正文存在提示源片段拼接导致的病句。",
                "清洗细纲中的抽象说明，正文生成应改用具体场景、动作和对话承接。",
            )
        fallback_template_markers = (
            "这一章真正落下来的，不是答案，而是更明确的行动代价",
            "没有急着把上一轮判断盖棺定论",
            "如果前一章只是让裂缝露出边缘",
            "等新的证据被重新放到灯下",
            "先比暗处的人更快一步",
        )
        fallback_hits = [marker for marker in fallback_template_markers if marker in clean_content]
        if len(fallback_hits) >= 2:
            add(
                "warning",
                "fallback_template_generation",
                "正文疑似命中规则兜底模板，章节之间容易同构。",
                "优先保留模型原始正文并只做轻量补全；若必须兜底，应结合本章场景、上一章余波和伏笔状态重新生成。",
            )
        if re.search(r"(的|了|而|但|并|和|与|把|将|让|向|对|在|被|却)$", clean_content[-80:].strip()):
            add(
                "critical",
                "dangling_tail",
                "正文尾句疑似截断或未完成。",
                "补全章末段落，确保以完整句号、问号、感叹号或引号结束。",
            )
        if compact_len < 1200:
            add("warning", "short_chapter", f"本章字数偏少（约 {compact_len} 字）。", "扩写场景动作、对话交锋、人物心理和章末推进，避免只完成情节摘要。")
        if clean_outline:
            outline_terms = self._important_terms(clean_outline, limit=12)
            matched_terms = [term for term in outline_terms if term in clean_content]
            if len(outline_terms) >= 5 and len(matched_terms) < max(3, len(outline_terms) // 3):
                add("warning", "outline_low_coverage", "正文对本章细纲关键点覆盖不足。", "回到正文生成前先补细纲，或重生成正文时明确要求承接本章目标、冲突、伏笔推进和章末钩子。")
        else:
            add("info", "missing_detail_outline", "章节质检没有收到本章细纲。", "后端应把本章细纲一并传给模型端，便于检查正文是否跑偏。")

        node_names = [str(node.get("label") or node.get("id") or "").strip() for node in topology.get("nodes", []) if isinstance(node, dict)]
        mentioned_names = [name for name in node_names if name and name in clean_content]
        if node_names and not mentioned_names:
            add("warning", "no_topology_character_used", "正文没有明显使用人物关系网中的人物。", "检查本章是否跑偏，或在细纲中明确本章出场人物与互动目标。")

        if "“" not in clean_content and "\"" not in clean_content and compact_len >= 1500:
            add("info", "little_dialogue", "本章几乎没有可识别对话。", "如果不是刻意的独白章，建议增加人物交锋来强化信息释放和情绪张力。")

        tail = clean_content[-220:]
        hook_keywords = ("忽然", "突然", "却", "只见", "没想到", "消息", "线索", "真相", "门外", "身后", "下一刻", "？", "?")
        if compact_len >= 1200 and not any(keyword in tail for keyword in hook_keywords):
            add("info", "weak_chapter_hook", "章末牵引偏弱。", "增加一个新线索、新代价、新决定或关系压力，把读者自然推向下一章。")

        open_foreshadows = self._collect_unresolved_foreshadows(project)
        is_later_story_stage = int(chapter_no or 1) >= 3 or int(volume_no or 0) > 1
        if is_later_story_stage and open_foreshadows:
            touched = [item for item in open_foreshadows[:12] if self._foreshadow_text_touched(item, clean_content)]
            if not touched:
                add("info", "no_long_range_foreshadow_touch", "本章没有明显触碰已记录的开放伏笔。", "不要求每章都回收伏笔，但正文生成前应确认本章是推进、强化、搁置还是回收。")

        critical = sum(1 for item in findings if item["severity"] == "critical")
        warning = sum(1 for item in findings if item["severity"] == "warning")
        info = sum(1 for item in findings if item["severity"] == "info")
        score = max(0, 100 - critical * 30 - warning * 12 - info * 4)
        report = {
            "user_id": user_id,
            "novel_id": novel_id,
            "volume": volume_no,
            "chapter_no": chapter_no,
            "title": title,
            "score": score,
            "level": "good" if score >= 85 else "watch" if score >= 68 else "risk",
            "word_count": compact_len,
            "findings": findings,
            "recommended_actions": [str(item.get("suggestion") or "").strip() for item in findings if str(item.get("suggestion") or "").strip()][:6],
            "checked_at": _utc_now(),
        }
        if persist:
            path = self._write_chapter_quality_report(project, report)
            report["report_path"] = str(path)
            report["relative_path"] = path.relative_to(project).as_posix()
        return report

    def continuity_report(
        self,
        novel_id: str,
        user_id: str = "default",
        persist: bool = True,
        topology: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        project = self.ensure_project(novel_id, user_id=user_id)
        status = self.project_status(novel_id, user_id=user_id)
        counts = dict(status.get("counts", {}) if isinstance(status.get("counts"), dict) else {})
        topology = topology if isinstance(topology, dict) else self.build_topology(novel_id, user_id=user_id)
        counts["topology_nodes"] = len(topology.get("nodes", []))
        counts["topology_edges"] = len(topology.get("edges", []))
        findings: List[Dict[str, Any]] = []

        def add(severity: str, code: str, message: str, suggestion: str = "", path: str = "") -> None:
            findings.append(
                {
                    "severity": severity,
                    "code": code,
                    "message": message,
                    "suggestion": suggestion,
                    "path": path,
                }
            )

        if int(counts.get("documents", 0) or 0) == 0:
            add("warning", "no_worldbuilding_sources", "当前小说还没有上传世界观/设定资料。", "至少上传世界观、阵营、地点、规则、术语表等稳定设定。")
        if int(counts.get("words", 0) or 0) < 1000:
            add("info", "thin_worldbuilding_sources", "知识库资料总字数偏少，后续长篇生成时可用约束有限。", "补充核心舞台、势力结构、能力规则、禁忌、历史事件。")
        if not topology.get("nodes"):
            add("critical", "missing_topology_nodes", "缺少静态人物关系拓扑节点。", "在信息推荐阶段重新生成并确认人物关系网。")
        if topology.get("nodes") and not topology.get("edges"):
            add("critical", "missing_topology_edges", "人物关系拓扑只有人物节点，没有稳定关系边。", "补全家族、师承、阵营、旧识、敌对、盟友等静态关系。")

        node_names = {str(node.get("label") or node.get("id") or "").strip() for node in topology.get("nodes", []) if isinstance(node, dict)}
        degree: Dict[str, int] = {name: 0 for name in node_names if name}
        for edge in topology.get("edges", []):
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source") or "").strip()
            target = str(edge.get("target") or "").strip()
            if source in degree:
                degree[source] += 1
            if target in degree:
                degree[target] += 1
        isolated = sorted(name for name, value in degree.items() if value == 0)
        if isolated:
            add("warning", "isolated_topology_nodes", f"人物关系拓扑存在孤立人物：{'、'.join(isolated[:8])}。", "为孤立人物补充静态关系，否则后续容易变成一次性工具人。")

        broken_links = self._find_broken_wiki_links(project)
        for item in broken_links[:20]:
            add("warning", "broken_wiki_link", f"Wiki 内链不存在：{item['target']}。", "修复链接或补建对应页面。", item["source"])
        if len(broken_links) > 20:
            add("info", "broken_wiki_link_overflow", f"另有 {len(broken_links) - 20} 个断链未展开。")

        summary_paths = sorted((project / "chapters" / "summaries").glob("*.md"))
        event_paths = sorted((project / "chapters" / "canon_events").glob("*.md"))
        if summary_paths and len(event_paths) < len(summary_paths):
            add("warning", "chapter_event_gap", "章节摘要数量多于已发生事实记录数量。", "确认章节回写是否完整写入 summaries 与 canon_events。")
        if len(summary_paths) >= 5 and int(counts.get("foreshadow_ledgers", 0) or 0) == 0:
            add("warning", "no_foreshadow_ledger", "已经有多章记忆，但伏笔账本为空。", "正文回写应持续沉淀伏笔、悬念、待回收承诺。")
        if len(summary_paths) >= 5 and int(counts.get("character_state_ledgers", 0) or 0) == 0:
            add("warning", "no_character_state_ledger", "已经有多章记忆，但人物状态账本为空。", "沉淀人物伤势、秘密暴露、信任变化、阶段立场，避免人物行为跳变。")

        foreshadow_states = self._load_foreshadow_states(project)
        counts["foreshadow_states"] = len(foreshadow_states)
        counts["foreshadow_open"] = self._foreshadow_state_counts(foreshadow_states).get("open", 0)
        counts["foreshadow_strengthened"] = self._foreshadow_state_counts(foreshadow_states).get("strengthened", 0)
        counts["foreshadow_resolved"] = self._foreshadow_state_counts(foreshadow_states).get("resolved", 0)
        unresolved_foreshadows = self._collect_unresolved_foreshadows(project)
        active_unresolved_count = sum(
            1 for item in foreshadow_states if item.get("status") in {"open", "strengthened"}
        )
        if active_unresolved_count >= 12:
            add("warning", "too_many_open_foreshadows", f"未回收伏笔候选较多（{active_unresolved_count} 条）。", "进入后续分卷/正文前安排回收顺序，避免结尾集中补洞。")
        stale = [
            item for item in foreshadow_states
            if item.get("status") in {"open", "strengthened"}
            and int(item.get("last_chapter") or item.get("first_chapter") or 0) + 6 <= int(max([self._chapter_no_from_path(path) for path in summary_paths] or [0]))
        ]
        if stale:
            add("warning", "stale_foreshadows", f"存在较久未触碰伏笔（{len(stale)} 条）。", "在后续细纲中安排强化、阶段回收或明确延后，避免长线线索断层。")

        critical = sum(1 for item in findings if item["severity"] == "critical")
        warning = sum(1 for item in findings if item["severity"] == "warning")
        info = sum(1 for item in findings if item["severity"] == "info")
        score = max(0, 100 - critical * 28 - warning * 8 - max(0, len(findings) - critical - warning) * 3)
        recommended_actions = [
            str(item.get("suggestion") or "").strip()
            for item in findings
            if str(item.get("suggestion") or "").strip()
        ][:6]
        report = {
            "user_id": user_id,
            "novel_id": novel_id,
            "score": score,
            "level": "good" if score >= 85 else "watch" if score >= 65 else "risk",
            "counts": counts,
            "severity_counts": {"critical": critical, "warning": warning, "info": info},
            "findings": findings,
            "recommended_actions": recommended_actions,
            "open_foreshadows": unresolved_foreshadows[:20],
            "foreshadow_states": foreshadow_states[:30],
            "foreshadow_state_counts": self._foreshadow_state_counts(foreshadow_states),
            "latest_chapter_quality": status.get("latest_chapter_quality"),
            "checked_at": _utc_now(),
        }
        if persist:
            path = self._write_continuity_report(project, report)
            report["report_path"] = str(path)
            report["relative_path"] = path.relative_to(project).as_posix()
        return report

    def _append_ledgers(
        self,
        project: Path,
        chapter_no: int,
        title: str,
        character_states: Sequence[str],
        foreshadows: Sequence[str],
        timeline_events: Sequence[str],
        volume_no: Optional[int] = None,
    ) -> None:
        chapter_slug = self._chapter_slug(chapter_no, volume_no)
        chapter_label = self._chapter_label(chapter_no, volume_no)
        updates = (
            (
                project / "ledgers" / "character_states" / f"{chapter_slug}.md",
                "人物状态账本",
                character_states,
            ),
            (
                project / "ledgers" / "foreshadows" / f"{chapter_slug}.md",
                "伏笔账本",
                foreshadows,
            ),
            (
                project / "ledgers" / "timeline" / f"{chapter_slug}.md",
                "时间线账本",
                timeline_events,
            ),
        )
        for path, ledger_title, items in updates:
            if not items:
                continue
            front = _frontmatter({"type": "ledger", "volume": volume_no, "chapter_no": chapter_no, "chapter_key": chapter_slug, "title": title, "updated_at": _utc_now()})
            body = f"{front}\n\n# {chapter_label}《{title}》{ledger_title}\n\n" + "\n".join(f"- {item}" for item in items) + "\n"
            path.write_text(body, encoding="utf-8")
            self._append_index(project, f"- [[{path.relative_to(project).with_suffix('').as_posix()}]]：{chapter_label}{ledger_title}")

    def _find_broken_wiki_links(self, project: Path) -> List[Dict[str, str]]:
        findings: List[Dict[str, str]] = []
        for path in project.rglob("*.md"):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", text):
                target = match.group(1).strip().strip("/")
                if not target or target.startswith(("http://", "https://")):
                    continue
                target_path = _safe_rel_path(project, f"{target}.md")
                if not target_path.exists():
                    findings.append({"source": path.relative_to(project).as_posix(), "target": target})
        return findings

    def _candidate_search_pages(self, project: Path, task_name: str = "", max_pages: int = 180) -> List[Path]:
        """Return a bounded search set so prompt enrichment does not slow down long novels."""
        task = str(task_name or "")
        groups: List[Path] = [
            project / "sources",
            project / "canon",
            project / "entities",
        ]
        if task in {"summary", "outline", "detail_outline"}:
            groups.extend([project / "relations", project / "reports"])
        if task in {"text", "text_first_chapter", "text_non_first_chapter"}:
            groups.extend([project / "chapters" / "canon_events"])

        pages: List[Path] = []
        seen: set[str] = set()
        for direct in (project / "bible.md", project / "index.md"):
            if direct.exists():
                pages.append(direct)
                seen.add(str(direct))
        for group in groups:
            if not group.exists():
                continue
            for path in sorted(group.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
                key = str(path)
                if key in seen:
                    continue
                seen.add(key)
                pages.append(path)
                if len(pages) >= max_pages:
                    return pages
        if pages:
            return pages
        return sorted(project.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:max_pages]

    def _cached_page_text(self, path: Path) -> str:
        try:
            stat = path.stat()
            key = str(path)
            cached = self._search_cache.get(key)
            signature = (int(stat.st_mtime_ns), int(stat.st_size))
            if cached and cached[0] == signature[0] and cached[1] == signature[1]:
                return cached[2]
            text = path.read_text(encoding="utf-8", errors="ignore")
            if len(text) > 80000:
                text = text[:60000] + "\n" + text[-12000:]
            self._search_cache[key] = (signature[0], signature[1], text)
            if len(self._search_cache) > 420:
                for old_key in list(self._search_cache.keys())[:80]:
                    self._search_cache.pop(old_key, None)
            return text
        except Exception:
            return ""

    def _search_terms(self, query: str, limit: int = 44) -> List[str]:
        source = re.sub(r"\s+", " ", str(query or "")).strip()
        if not source:
            return []
        counts: Dict[str, int] = {}
        stop = {
            "小说", "章节", "正文", "细纲", "故事", "人物", "生成", "输出", "要求", "当前", "根据", "信息", "内容",
            "关系", "世界观", "主线", "情绪", "场景", "事件", "对话", "一个", "需要", "不能", "必须",
        }

        def add(term: str, weight: int = 1) -> None:
            token = term.strip()
            if len(token) < 2 or token in stop or token.isdigit():
                return
            counts[token] = counts.get(token, 0) + weight

        for quoted in re.findall(r"[《「“\"]([^》」”\"]{2,24})[》」”\"]", source):
            add(quoted, 5)
        for token in re.findall(r"[A-Za-z0-9_]{2,32}", source):
            add(token, 2)
        for seq in re.findall(r"[一-鿿]{2,80}", source):
            if 2 <= len(seq) <= 6:
                add(seq, 2)
            upper = min(5, len(seq))
            for size in range(2, upper + 1):
                for index in range(0, max(0, len(seq) - size + 1)):
                    add(seq[index : index + size])
        return [term for term, _ in sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))[:limit]]

    def _foreshadow_state_path(self, project: Path) -> Path:
        return project / "plots" / "foreshadows" / "_state.json"

    def _load_foreshadow_states(self, project: Path) -> List[Dict[str, Any]]:
        path = self._foreshadow_state_path(project)
        if not path.exists():
            return []
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(parsed, dict):
            parsed = parsed.get("items")
        if not isinstance(parsed, list):
            return []
        return [
            item
            for item in parsed
            if isinstance(item, dict) and self._is_valid_foreshadow_candidate(str(item.get("text") or ""))
        ]

    def _save_foreshadow_states(self, project: Path, states: Sequence[Dict[str, Any]]) -> Path:
        path = self._foreshadow_state_path(project)
        payload = {"updated_at": _utc_now(), "items": list(states)}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path = path.with_suffix(".md")
        lines = [
            _frontmatter({"type": "foreshadow_state", "updated_at": payload["updated_at"]}),
            "",
            "# 伏笔状态机",
            "",
        ]
        for item in states:
            first_label = self._chapter_label(int(item.get("first_chapter") or 0), item.get("first_volume")) if item.get("first_chapter") else "未知章节"
            last_label = self._chapter_label(int(item.get("last_chapter") or item.get("first_chapter") or 0), item.get("last_volume") or item.get("first_volume")) if (item.get("last_chapter") or item.get("first_chapter")) else "未知章节"
            lines.append(f"- [{item.get('status') or 'open'}] {first_label} -> {last_label}：{item.get('text')}")
        md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        self._append_index(project, "- [[plots/foreshadows/_state]]：伏笔状态机")
        return path

    def _foreshadow_state_counts(self, states: Sequence[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {"open": 0, "strengthened": 0, "partially_resolved": 0, "resolved": 0}
        for item in states:
            status = str(item.get("status") or "open")
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _foreshadow_similarity(self, left: str, right: str) -> float:
        left_set = set(re.findall(r"[一-鿿A-Za-z0-9]{1}", left or ""))
        right_set = set(re.findall(r"[一-鿿A-Za-z0-9]{1}", right or ""))
        if not left_set or not right_set:
            return 0.0
        return len(left_set & right_set) / max(1, min(len(left_set), len(right_set)))

    def _foreshadow_has_resolution_signal(self, text: str) -> bool:
        return any(
            keyword in text
            for keyword in (
                "真相大白", "揭开", "揭露", "证实", "解释", "交代清楚", "答案", "暴露", "坦白", "承认",
                "破解", "解开", "回收", "兑现", "原来", "终于明白", "终于知道",
            )
        )

    def _foreshadow_text_touched(self, item: str, content: str) -> bool:
        item_terms = [term for term in self._important_terms(item, limit=6) if len(term) >= 2]
        if item_terms and any(term in content for term in item_terms[:4]):
            return True
        return self._foreshadow_similarity(item[:80], content[-1200:]) >= 0.55

    def _update_foreshadow_state_machine(
        self,
        project: Path,
        chapter_no: int,
        title: str,
        foreshadows: Sequence[str],
        content: str,
        volume_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        states = self._load_foreshadow_states(project)
        now = _utc_now()
        touched_ids: List[str] = []
        for raw in foreshadows:
            text = re.sub(r"\s+", " ", str(raw or "")).strip()
            if not self._is_valid_foreshadow_candidate(text):
                continue
            matched: Optional[Dict[str, Any]] = None
            for item in states:
                if self._foreshadow_similarity(text, str(item.get("text") or "")) >= 0.62:
                    matched = item
                    break
            if matched is None:
                foreshadow_id = hashlib.sha1(f"{volume_no or 0}:{chapter_no}:{text}".encode("utf-8")).hexdigest()[:12]
                matched = {
                    "id": foreshadow_id,
                    "text": text[:220],
                    "status": "open",
                    "first_volume": volume_no,
                    "first_chapter": chapter_no,
                    "first_title": title,
                    "mentions": 0,
                    "history": [],
                    "created_at": now,
                }
                states.append(matched)
            matched["last_volume"] = volume_no
            matched["last_chapter"] = chapter_no
            matched["last_title"] = title
            matched["mentions"] = int(matched.get("mentions") or 0) + 1
            if self._foreshadow_has_resolution_signal(text):
                matched["status"] = "partially_resolved" if matched.get("status") != "resolved" else "resolved"
            elif matched.get("status") == "open" and int(matched.get("mentions") or 0) >= 2:
                matched["status"] = "strengthened"
            matched["updated_at"] = now
            history = matched.get("history") if isinstance(matched.get("history"), list) else []
            history.append({"volume": volume_no, "chapter_no": chapter_no, "title": title, "event": "touch", "text": text[:160], "updated_at": now})
            matched["history"] = history[-8:]
            touched_ids.append(str(matched.get("id")))

        for item in states:
            if str(item.get("id")) in touched_ids:
                continue
            if item.get("status") in {"open", "strengthened", "partially_resolved"} and self._foreshadow_text_touched(str(item.get("text") or ""), content):
                item["last_volume"] = volume_no
                item["last_chapter"] = chapter_no
                item["last_title"] = title
                item["mentions"] = int(item.get("mentions") or 0) + 1
                item["status"] = "partially_resolved" if self._foreshadow_has_resolution_signal(content[-1400:]) else item.get("status", "strengthened")
                item["updated_at"] = now
                touched_ids.append(str(item.get("id")))

        states.sort(key=lambda item: (str(item.get("status") or ""), int(item.get("first_chapter") or 0), str(item.get("id") or "")))
        path = self._save_foreshadow_states(project, states)
        self._append_log(project, f"foreshadow-state | {self._chapter_label(chapter_no, volume_no)}", [f"Touched: {len(touched_ids)}", f"State: {path.relative_to(project).as_posix()}"])
        return {
            "state_path": str(path),
            "relative_path": path.relative_to(project).as_posix(),
            "touched_ids": touched_ids,
            "counts": self._foreshadow_state_counts(states),
        }

    def _collect_unresolved_foreshadows(self, project: Path) -> List[str]:
        state_items = self._load_foreshadow_states(project)
        if state_items:
            result = []
            for item in state_items:
                if item.get("status") in {"open", "strengthened", "partially_resolved"}:
                    prefix = self._chapter_label(int(item.get("first_chapter") or 0), item.get("first_volume")) if item.get("first_chapter") else "未知章节"
                    status = str(item.get("status") or "open")
                    result.append(f"{prefix} [{status}] {item.get('text')}")
            return result
        items: List[str] = []
        seen: set[str] = set()
        for path in sorted((project / "ledgers" / "foreshadows").glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for raw in re.findall(r"^\s*-\s+(.+)$", text, flags=re.MULTILINE):
                item = re.sub(r"\s+", " ", raw).strip()
                if not item or item in seen:
                    continue
                if any(token in item for token in ("已回收", "已兑现", "已解释", "解决")):
                    continue
                if not self._is_valid_foreshadow_candidate(item):
                    continue
                seen.add(item)
                items.append(item)
        return items

    def _chapter_no_from_path(self, path: Path) -> int:
        match = re.search(r"chapter-(\d+)", path.name)
        return int(match.group(1)) if match else 0

    def _important_terms(self, text: str, limit: int = 12) -> List[str]:
        stop = {
            "本章", "当前", "一个", "他们", "她们", "人物", "故事", "情绪", "场景", "事件", "对话", "冲突", "目标",
            "章节", "推进", "关系", "伏笔", "主角", "需要", "开始", "之后", "因为", "因此", "但是", "可以",
        }
        counts: Dict[str, int] = {}
        for token in re.findall(r"[一-鿿A-Za-z0-9]{2,8}", text or ""):
            if token in stop or token.isdigit():
                continue
            counts[token] = counts.get(token, 0) + 1
        return [token for token, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]

    def _write_chapter_quality_report(self, project: Path, report: Dict[str, Any]) -> Path:
        chapter_no = int(report.get("chapter_no") or 1)
        volume_no = report.get("volume")
        chapter_slug = self._chapter_slug(chapter_no, volume_no)
        chapter_label = self._chapter_label(chapter_no, volume_no)
        path = project / "reports" / "chapters" / f"{chapter_slug}-quality.md"
        findings = report.get("findings", []) if isinstance(report.get("findings"), list) else []
        lines = [
            _frontmatter({"type": "chapter_quality_report", "volume": volume_no, "chapter_no": chapter_no, "chapter_key": chapter_slug, "score": report.get("score"), "level": report.get("level"), "checked_at": report.get("checked_at")}),
            "",
            f"# {chapter_label}质检报告",
            "",
            f"- 章节：{report.get('title') or ''}",
            f"- 分数：{report.get('score')}",
            f"- 等级：{report.get('level')}",
            f"- 字数：{report.get('word_count')}",
            "",
            "## 问题清单",
        ]
        if findings:
            for item in findings:
                suggestion = f" 建议：{item.get('suggestion')}" if item.get("suggestion") else ""
                lines.append(f"- [{item.get('severity')}] {item.get('message')}{suggestion}")
        else:
            lines.append("- 暂无明显章节质量风险。")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._append_index(project, f"- [[{path.relative_to(project).with_suffix('').as_posix()}]]：{chapter_label}质检报告")
        return path

    def _write_continuity_report(self, project: Path, report: Dict[str, Any]) -> Path:
        path = project / "reports" / "_continuity_report.md"
        findings = report.get("findings", []) if isinstance(report.get("findings"), list) else []
        lines = [
            _frontmatter({"type": "continuity_report", "score": report.get("score"), "level": report.get("level"), "checked_at": report.get("checked_at")}),
            "",
            "# 小说连续性体检报告",
            "",
            f"- 分数：{report.get('score')}",
            f"- 等级：{report.get('level')}",
            f"- 检查时间：{report.get('checked_at')}",
            "",
            "## 问题清单",
        ]
        if findings:
            for item in findings:
                path_text = f"（{item.get('path')}）" if item.get("path") else ""
                suggestion = f" 建议：{item.get('suggestion')}" if item.get("suggestion") else ""
                lines.append(f"- [{item.get('severity')}] {item.get('message')}{path_text}{suggestion}")
        else:
            lines.append("- 暂无明显连续性风险。")
        lines.append("")
        lines.append("## 未回收伏笔候选")
        open_foreshadows = report.get("open_foreshadows", []) if isinstance(report.get("open_foreshadows"), list) else []
        if open_foreshadows:
            lines.extend(f"- {item}" for item in open_foreshadows)
        else:
            lines.append("- 暂无。")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._append_index(project, "- [[reports/_continuity_report]]：小说连续性体检报告")
        self._append_log(project, f"continuity-check | score {report.get('score')}", [f"Report: {path.relative_to(project).as_posix()}", f"Findings: {len(findings)}"])
        return path

    def _append_log(self, project: Path, title: str, lines: Sequence[str]) -> None:
        log_path = project / "log.md"
        block = [f"\n## [{_utc_now()}] {title}"]
        block.extend(f"- {line}" for line in lines)
        log_path.write_text(log_path.read_text(encoding="utf-8") + "\n".join(block) + "\n", encoding="utf-8")

    def _append_index(self, project: Path, line: str) -> None:
        index_path = project / "index.md"
        text = index_path.read_text(encoding="utf-8")
        if line not in text:
            index_path.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8")

    def _latest_page_summary(self, project: Path, path: Path) -> Dict[str, Any]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = self._read_frontmatter_value(path, "title")
        if not title:
            match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
            title = match.group(1).strip() if match else path.stem
        snippet = self._chapter_summary(re.sub(r"---[\s\S]*?---", "", text, count=1), max_chars=160)
        return {
            "title": title,
            "relative_path": path.relative_to(project).as_posix(),
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snippet": snippet,
        }

    def _source_document_summary(self, project: Path, path: Path) -> Dict[str, Any]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = self._read_frontmatter_value(path, "title") or path.stem
        document_id = self._read_frontmatter_value(path, "document_id") or hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]
        source_type = self._read_frontmatter_value(path, "source_type") or "worldbuilding"
        body = self._source_document_body(text)
        compact = re.sub(r"\s+", "", body)
        return {
            "id": document_id,
            "model_document_id": document_id,
            "title": title,
            "source_type": source_type,
            "word_count": len(compact),
            "preview": self._chapter_summary(body, max_chars=320),
            "relative_path": path.relative_to(project).as_posix(),
            "model_path": str(path),
            "sync_status": 1,
            "sync_message": "已写入模型端本地 Wiki",
            "create_time": datetime.fromtimestamp(path.stat().st_ctime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "update_time": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _source_document_body(self, text: str) -> str:
        body = re.sub(r"^---[\s\S]*?---\s*", "", str(text or ""), count=1).strip()
        body = re.sub(r"^#\s+.+\n+", "", body).strip()
        body = re.sub(r"^##\s+原始内容\s*", "", body).strip()
        return body

    def _extract_candidate_names(self, text: str) -> List[str]:
        names: List[str] = []
        seen: set[str] = set()
        patterns = [
            r"([一-鿿]{2,4})(?:是|为|乃|与|和|同|跟)",
            r"(?:人物|角色|主角|配角|父亲|母亲|兄长|妹妹|师父|弟子)[:：]?([一-鿿]{2,4})",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1).strip()
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
        return names[:30]

    def _read_frontmatter_value(self, path: Path, key: str) -> str:
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
        if not match:
            return ""
        value = match.group(1).strip().strip("'\"")
        try:
            loaded = json.loads(value)
            if isinstance(loaded, str):
                return loaded
        except Exception:
            pass
        return value

    def _make_snippet(self, text: str, terms: Sequence[str], radius: int = 90) -> str:
        clean = re.sub(r"\s+", " ", text).strip()
        first_index = -1
        for term in terms:
            if not term:
                continue
            idx = clean.find(term)
            if idx >= 0 and (first_index < 0 or idx < first_index):
                first_index = idx
        if first_index < 0:
            return clean[: radius * 2]
        start = max(0, first_index - radius)
        end = min(len(clean), first_index + radius)
        return clean[start:end]

    def _chapter_summary(self, content: str, max_chars: int = 420) -> str:
        clauses = _extract_clean_clauses(content, min_len=12)
        selected: List[str] = []
        for clause in clauses:
            if len("".join(selected)) >= max_chars:
                break
            selected.append(_ensure_sentence_end(clause))
        summary = "".join(selected).strip()
        return summary[:max_chars] or content[:max_chars] or "暂无摘要。"

    def _characters_mentioned(self, project: Path, content: str) -> List[str]:
        names: List[str] = []
        for char_path in (project / "entities" / "characters").glob("*.md"):
            name = self._read_frontmatter_value(char_path, "name") or char_path.stem
            if name and name in content and name not in names:
                names.append(name)
        if names:
            return names[:20]
        return []

    def _extract_event_candidates(self, content: str, limit: int = 8) -> List[str]:
        clauses = _extract_clean_clauses(content, min_len=18)
        events: List[str] = []
        keywords = ("发现", "决定", "进入", "离开", "交代", "揭开", "确认", "拒绝", "答应", "冲突", "争执", "追查", "救下", "背叛", "死亡", "受伤")
        for clause in clauses:
            if any(keyword in clause for keyword in keywords):
                events.append(_ensure_sentence_end(clause))
            if len(events) >= limit:
                break
        if not events:
            events = [_ensure_sentence_end(item) for item in clauses[: min(limit, 5)]]
        return events or ["暂无自动识别事实。"]

    def _extract_character_state_candidates(self, content: str, characters: Sequence[str], limit: int = 12) -> List[str]:
        clauses = _extract_clean_clauses(content, min_len=12)
        state_keywords = (
            "受伤", "昏迷", "醒来", "失踪", "暴露", "隐瞒", "怀疑", "确认", "决定", "答应", "拒绝", "害怕", "愤怒", "动摇",
            "信任", "不信任", "误会", "和解", "加入", "离开", "背叛", "获知", "发现", "记起", "失去", "得到", "突破", "晋升",
        )
        candidates: List[str] = []
        seen: set[str] = set()
        known_characters = [name for name in characters if name]
        for clause in clauses:
            if not any(keyword in clause for keyword in state_keywords):
                continue
            matched = [name for name in known_characters if name in clause]
            if not matched and not known_characters:
                matched = self._extract_candidate_names(clause)[:2]
            for name in matched[:3]:
                item = f"{name}：{_ensure_sentence_end(clause)}"
                if item in seen:
                    continue
                seen.add(item)
                candidates.append(item)
                if len(candidates) >= limit:
                    return candidates
        return candidates

    def _extract_location_candidates(self, content: str, limit: int = 10) -> List[str]:
        clauses = _extract_clean_clauses(content, min_len=10)
        location_suffixes = "城|镇|村|府|宫|殿|楼|阁|院|寺|庙|山|谷|林|河|湖|海|岛|港|街|巷|关|营|寨|矿|塔|桥|站|馆|店"
        location_pattern = rf"([一-鿿]{{1,8}}?(?:{location_suffixes}))"
        scene_keywords = ("抵达", "进入", "离开", "返回", "赶往", "经过", "藏身", "相见", "埋伏", "追逐", "战斗", "谈判")
        candidates: List[str] = []
        seen: set[str] = set()
        for clause in clauses:
            names: List[str] = []
            for match in re.finditer(location_pattern, clause):
                name = match.group(1).strip("，。；：、 ")
                name = re.sub(r"^.*(?:在|到|抵达|进入|离开|返回|赶往|经过)", "", name)
                if 2 <= len(name) <= 8 and name not in names:
                    names.append(name)
            if not names and not any(keyword in clause for keyword in scene_keywords):
                continue
            prefix = "、".join(names[:3]) if names else "未命名场景"
            item = f"{prefix}：{_ensure_sentence_end(clause)}"
            if item in seen:
                continue
            seen.add(item)
            candidates.append(item)
            if len(candidates) >= limit:
                break
        return candidates

    def _is_valid_foreshadow_candidate(self, text: str) -> bool:
        value = re.sub(r"\s+", " ", str(text or "")).strip(" -；;，,。")
        if len(value) < 10:
            return False
        strong_keywords = (
            "伏笔", "暗示", "未解释", "未说清", "没有解释", "秘密", "线索", "证据", "录音", "档案", "名单", "钥匙",
            "密信", "残页", "信物", "令牌", "账本", "记号", "暗号", "编号", "密码", "坐标", "异常", "不对劲",
            "真相", "幕后", "身份", "计划", "代价", "消失", "死亡", "警报", "备用", "把柄", "藏有", "删改",
            "来源不明", "无法解释", "没有说完", "欲言又止", "被隐瞒", "被调包", "缺失",
        )
        weak_keywords = ("似乎", "仿佛", "隐约", "传闻", "梦见", "古怪", "可疑")
        has_strong = any(keyword in value for keyword in strong_keywords)
        has_weak = any(keyword in value for keyword in weak_keywords)
        if not (has_strong or has_weak):
            return False
        # 伏笔状态机只沉淀可追踪的线索，不收纳整段氛围描写；长段落会让看板误判为大量未回收风险。
        if len(value) > 180:
            return False
        if any(token in value for token in ("本章", "这一章", "读者会", "故事会", "创作", "生成", "细纲", "大纲")):
            return False
        atmosphere_terms = ("雨", "风", "钟声", "潮声", "雾", "夜色", "空气", "灯光", "泥水", "街灯", "霓虹", "走廊", "码头")
        atmosphere_hits = sum(1 for term in atmosphere_terms if term in value)
        if atmosphere_hits >= 3 and not has_strong:
            return False
        if re.fullmatch(r".{0,20}(似乎|仿佛|隐约).{0,80}", value) and not has_strong:
            return False
        return True

    def _filter_foreshadow_items(self, items: Sequence[str], limit: int = 7) -> List[str]:
        candidates: List[str] = []
        seen: set[str] = set()
        for raw in items:
            item = _ensure_sentence_end(re.sub(r"\s+", " ", str(raw or "")).strip(" -；;，,。"))
            if not self._is_valid_foreshadow_candidate(item):
                continue
            key = item[:120]
            if key in seen:
                continue
            seen.add(key)
            candidates.append(item[:220])
            if len(candidates) >= limit:
                break
        return candidates

    def _extract_foreshadow_candidates(self, content: str, limit: int = 7) -> List[str]:
        clauses = _extract_clean_clauses(content, min_len=14)
        keywords = (
            "没有说完", "欲言又止", "秘密", "线索", "证据", "录音", "档案", "名单", "钥匙", "信物", "残页", "密信",
            "真相", "幕后", "不对劲", "异常", "记号", "暗号", "编号", "密码", "代价", "警报", "备用", "把柄",
            "来源不明", "无法解释", "删改", "缺失", "被隐瞒", "被调包",
        )
        candidates: List[str] = []
        seen: set[str] = set()
        for clause in clauses:
            if not any(keyword in clause for keyword in keywords):
                continue
            item = _ensure_sentence_end(clause)
            if not self._is_valid_foreshadow_candidate(item):
                continue
            if item in seen:
                continue
            seen.add(item)
            candidates.append(item)
            if len(candidates) >= limit:
                break
        return candidates

    def _extract_timeline_candidates(self, content: str, limit: int = 8) -> List[str]:
        clauses = _extract_clean_clauses(content, min_len=16)
        keywords = ("因为", "因此", "于是", "随后", "之后", "此前", "同时", "直到", "终于", "导致", "使得", "从而")
        candidates: List[str] = []
        seen: set[str] = set()
        for clause in clauses:
            if not any(keyword in clause for keyword in keywords):
                continue
            item = _ensure_sentence_end(clause)
            if item in seen:
                continue
            seen.add(item)
            candidates.append(item)
            if len(candidates) >= limit:
                break
        return candidates

    def _pick_refined_text(self, value: Any, fallback: str, max_chars: int = 520) -> str:
        text = str(value or "").strip()
        if len(text) < 12:
            return fallback
        return _ensure_sentence_end(text[:max_chars])

    def _merge_refined_items(self, refined: Any, fallback: Sequence[str], limit: int = 10) -> List[str]:
        items: List[str] = []
        seen: set[str] = set()

        def push(value: Any) -> None:
            if isinstance(value, dict):
                if "character" in value and "state" in value:
                    text = f"{value.get('character')}：{value.get('state')}"
                elif "name" in value and "description" in value:
                    text = f"{value.get('name')}：{value.get('description')}"
                else:
                    text = "；".join(str(v) for v in value.values() if v)
            else:
                text = str(value or "")
            text = re.sub(r"\s+", " ", text).strip(" -；;，,。")
            if len(text) < 4:
                return
            text = _ensure_sentence_end(text[:220])
            if text in seen:
                return
            seen.add(text)
            items.append(text)

        if isinstance(refined, list):
            for item in refined:
                push(item)
                if len(items) >= limit:
                    return items
        elif refined:
            push(refined)
        for item in fallback:
            push(item)
            if len(items) >= limit:
                break
        return items

    def _append_character_state_updates(
        self,
        project: Path,
        chapter_no: int,
        title: str,
        character_states: Sequence[str],
        volume_no: Optional[int] = None,
    ) -> None:
        if not character_states:
            return
        characters_root = project / "entities" / "characters"
        existing_pages: Dict[str, Path] = {}
        for char_path in characters_root.glob("*.md"):
            name = self._read_frontmatter_value(char_path, "name") or char_path.stem
            existing_pages[name] = char_path
        grouped: Dict[str, List[str]] = {}
        for item in character_states:
            name, _, state = item.partition("：")
            if not name or name not in existing_pages or not state:
                continue
            grouped.setdefault(name, []).append(state)
        for name, states in grouped.items():
            path = existing_pages[name]
            text = path.read_text(encoding="utf-8", errors="ignore").rstrip()
            marker = f"## {self._chapter_label(chapter_no, volume_no)}状态更新"
            if marker in text:
                continue
            block = ["", marker, f"来源：{self._chapter_label(chapter_no, volume_no)}《{title}》"]
            block.extend(f"- {state}" for state in states[:5])
            path.write_text(text + "\n" + "\n".join(block) + "\n", encoding="utf-8")

    def _recent_chapter_memory(self, project: Path, task_name: str = "", limit: int = 3, current_volume: Optional[int] = None) -> List[str]:
        if task_name not in {"text", "text_first_chapter", "text_non_first_chapter", "detail_outline", "outline", "summary"}:
            return []
        all_paths = sorted((project / "chapters" / "summaries").glob("*.md"))
        chapter_paths = all_paths[-limit:]
        if task_name == "detail_outline" and current_volume:
            try:
                previous_volume = int(current_volume) - 1
            except Exception:
                previous_volume = 0
            if previous_volume > 0:
                previous_paths = [
                    path
                    for path in all_paths
                    if self._read_frontmatter_value(path, "volume") == str(previous_volume)
                ]
                if previous_paths:
                    chapter_paths = previous_paths[-max(limit, 5):]
        lines: List[str] = []
        for path in chapter_paths:
            text = path.read_text(encoding="utf-8", errors="ignore")
            title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
            title = title_match.group(1).strip() if title_match else path.stem
            summary = self._extract_markdown_section(text, "章节摘要", max_chars=180)
            states = self._extract_markdown_section(text, "人物状态候选", max_chars=180)
            foreshadows = self._extract_markdown_section(text, "伏笔候选", max_chars=140)
            compact = "；".join(item for item in (summary, states, foreshadows) if item)
            if compact:
                lines.append(f"- {title}：{compact[:360]}")
        return lines

    def _worldbuilding_term_memory(self, project: Path, limit: int = 10) -> List[str]:
        source_paths = sorted((project / "sources").glob("*.md"))
        if not source_paths:
            return []
        lines: List[str] = []
        seen: set[str] = set()
        for path in source_paths:
            source_type = self._read_frontmatter_value(path, "source_type")
            tags = self._read_frontmatter_value(path, "tags")
            if "world" not in source_type.lower() and "世界" not in tags and "设定" not in tags:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE):
                term = re.sub(r"\s+", "", match.group(1)).strip(" #：:")
                if not term or term in {"原始内容"} or term in seen:
                    continue
                start = match.end()
                next_match = re.search(r"^##\s+", text[start:], flags=re.MULTILINE)
                end = start + next_match.start() if next_match else min(len(text), start + 360)
                desc = re.sub(r"\s+", " ", text[start:end]).strip()
                if not desc:
                    continue
                seen.add(term)
                lines.append(f"- {term}：{desc[:220]}")
                if len(lines) >= limit:
                    return lines
        return lines

    def _long_range_memory(self, project: Path, task_name: str = "", limit: int = 10) -> List[str]:
        if task_name not in {"text", "text_first_chapter", "text_non_first_chapter", "detail_outline", "outline", "summary"}:
            return []
        lines: List[str] = []
        open_foreshadows = self._collect_unresolved_foreshadows(project)
        if open_foreshadows:
            lines.append("未回收伏笔/待兑现承诺：")
            lines.extend(f"- {item[:180]}" for item in open_foreshadows[: min(limit, 8)])

        state_paths = sorted((project / "ledgers" / "character_states").glob("*.md"))[-4:]
        state_lines: List[str] = []
        for path in state_paths:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for raw in text.splitlines():
                item = raw.strip()
                if item.startswith("- "):
                    item = item[2:].strip()
                    if item and item not in state_lines:
                        state_lines.append(item)
                if len(state_lines) >= 8:
                    break
            if len(state_lines) >= 8:
                break
        if state_lines:
            lines.append("近期人物状态变化：")
            lines.extend(f"- {item[:180]}" for item in state_lines[:8])

        timeline_paths = sorted((project / "ledgers" / "timeline").glob("*.md"))[-3:]
        timeline_lines: List[str] = []
        for path in timeline_paths:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for raw in text.splitlines():
                item = raw.strip()
                if item.startswith("- "):
                    item = item[2:].strip()
                    if item and item not in timeline_lines:
                        timeline_lines.append(item)
                if len(timeline_lines) >= 6:
                    break
            if len(timeline_lines) >= 6:
                break
        if timeline_lines:
            lines.append("近期时间线/因果事实：")
            lines.extend(f"- {item[:180]}" for item in timeline_lines[:6])
        return lines[: max(1, limit + 8)]

    def _extract_markdown_section(self, text: str, heading: str, max_chars: int = 220) -> str:
        pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
        match = re.search(pattern, text, flags=re.MULTILINE)
        if not match:
            return ""
        section = re.sub(r"\s+", " ", match.group(1)).strip(" -\n\t")
        return section[:max_chars]

    def _parse_info_characters(self, info_text: str) -> List[Dict[str, str]]:
        person_section = self._extract_section(info_text, "人物信息", ("故事背景", "简介")) or info_text
        characters: List[Dict[str, str]] = []
        seen: set[str] = set()
        for raw_line in person_section.splitlines():
            line = raw_line.strip().lstrip("-• ").strip()
            if not line:
                continue
            match = re.match(r"^([一-鿿A-Za-z0-9_]{2,12})\s*[:：]\s*(.+)$", line)
            if not match:
                continue
            name = match.group(1).strip()
            description = _clean_text_for_relation(match.group(2))
            if not name or name in seen:
                continue
            seen.add(name)
            role = self._infer_character_role(description)
            characters.append({"name": name, "description": description, "role": role})
        return characters[:12]

    def _extract_section(self, text: str, label: str, stop_labels: Sequence[str]) -> str:
        source = str(text or "")
        start_pattern = rf"(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*[:：]"
        start_match = re.search(start_pattern, source)
        if not start_match:
            return ""
        tail = source[start_match.end() :]
        end_pos = len(tail)
        for stop_label in stop_labels:
            stop_pattern = rf"\n\s*(?:\*\*)?{re.escape(stop_label)}(?:\*\*)?\s*[:：]"
            stop_match = re.search(stop_pattern, tail)
            if stop_match and stop_match.start() < end_pos:
                end_pos = stop_match.start()
        return tail[:end_pos].strip()

    def _infer_character_role(self, description: str) -> str:
        if any(token in description for token in ("主角", "叙事中心", "主人公", "核心")):
            return "protagonist"
        if any(token in description for token in ("反派", "敌对", "仇敌", "幕后")):
            return "antagonist"
        if any(token in description for token in ("盟友", "同伴", "伙伴", "协助")):
            return "ally"
        if any(token in description for token in ("父", "母", "兄", "弟", "姐", "妹", "家族")):
            return "family"
        return "character"

    def _relation_label(self, relation_type: str, evidence: str) -> str:
        labels = {
            "family": "家族/血缘",
            "romance": "情感关系",
            "mentor": "师承关系",
            "ally": "盟友/同伴",
            "enemy": "敌对关系",
            "faction": "阵营关系",
            "background": "背景交集",
            "connection": "主线交集",
        }
        if relation_type == "family":
            if "妹妹" in evidence or "兄妹" in evidence:
                return "兄妹/姐弟"
            if "父" in evidence:
                return "父辈关系"
            if "母" in evidence:
                return "母系关系"
        return labels.get(relation_type, "人物关系")

    def _line_subject(self, sentence: str, names: Sequence[str]) -> str:
        match = re.match(r"^-?\s*([一-鿿A-Za-z0-9_]{2,12})\s*[:：]", sentence.strip())
        if not match:
            return ""
        candidate = match.group(1).strip()
        return candidate if candidate in names else ""

    def _is_static_relation_sentence(self, sentence: str) -> bool:
        text = _clean_text_for_relation(sentence)
        if any(marker in text for marker in ("关系锚点", "人物关系", "血缘关系", "师承关系", "阵营关系")):
            return True
        relation_words = (
            "父子", "父女", "母子", "母女", "兄妹", "姐弟", "姐妹", "兄弟", "叔侄",
            "师徒", "同门", "旧识", "故人", "同乡", "同窗", "盟友", "同盟",
            "敌对", "仇敌", "旧敌", "宿敌", "同事", "同僚", "同阵营", "同组织",
            "契约债务", "情报交易", "资源合作", "家族", "血缘",
        )
        if re.search(r"(?:与|和|同为|同是|同属|同在).{1,24}(?:为|是|系|有|存在|保持|共享|同属|隶属)", text):
            return True
        if any(word in text for word in relation_words) and re.search(
            r"(?:与|和|同为|同是|同属|同在|同门|同乡|同窗|同盟|同阵营|同组织)",
            text,
        ):
            return True
        return False

    def _extract_explicit_relation_edges(self, sentence: str, subject: str, names: Sequence[str]) -> List[Dict[str, str]]:
        text = _clean_text_for_relation(sentence)
        results: List[Dict[str, str]] = []
        seen: set[Tuple[str, str]] = set()
        for target in names:
            if not target or target == subject or target not in text:
                continue
            relation_type = ""
            relation_label = ""
            patterns = [
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系)(兄弟|兄妹|姐弟|姐妹|父子|父女|母子|母女|同族|血亲|亲族)", "family"),
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系)(师徒|师兄弟|同门|师承)", "mentor"),
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系)(盟友|同盟|伙伴|同伴|搭档|合作方)", "ally"),
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系)(敌对|仇敌|宿敌|旧敌|死敌|对手)", "enemy"),
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系).{0,16}(猎人|猎物|死对头|对手|宿敌|敌人|仇敌)", "enemy"),
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系)(旧识|故人|同乡|同窗|青梅竹马)", "background"),
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系)(昔日战友|旧日战友|战友|旧部|旧友)", "background"),
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系)(叔侄|叔父|伯侄|舅甥|同族|血亲|亲族)", "family"),
                (rf"(?:与|和|同){re.escape(target)}(?:为|是|系)(同事|同僚|上下级|利益共同体|同阵营|同组织|同门派|同家族)", "faction"),
                (rf"(?:与|和|同){re.escape(target)}(?:有|存在|保持)(背景交集|旧案交集|旧案牵连|档案牵连|旧识关系|资源合作关系|情报交易关系)", ""),
                (rf"(?:与|和|同){re.escape(target)}有背景交集但互相防备", "background"),
                (rf"(?:与|和|同){re.escape(target)}在立场上摇摆合作", "ally"),
                (rf"(?:与|和|同){re.escape(target)}(?:共享|共用|掌握)(灰色渠道|共同旧案|旧案线索|关键线索|家族秘密)", "background"),
                (rf"(?:与|和|同){re.escape(target)}(?:互相防备|彼此防备|立场摇摆合作|若即若离合作)", "ally"),
                (rf"{re.escape(target)}(?:为|是|系){re.escape(subject)}(?:的)?(兄弟|兄妹|姐弟|姐妹|父亲|母亲|子女|同族|血亲|亲族)", "family"),
                (rf"{re.escape(target)}(?:为|是|系){re.escape(subject)}(?:的)?(师父|师傅|导师|弟子|同门)", "mentor"),
                (rf"{re.escape(target)}(?:为|是|系){re.escape(subject)}(?:的)?(盟友|同盟|伙伴|敌人|仇敌|旧识|故人)", ""),
            ]
            for pattern, explicit_type in patterns:
                match = re.search(pattern, text)
                if not match:
                    continue
                phrase = match.group(1) if match.groups() else match.group(0)
                relation_type = explicit_type or _infer_relation_type(str(phrase))
                relation_label = str(phrase)
                break
            if not relation_type:
                continue
            key = (target, relation_type)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "target": target,
                    "relation_type": relation_type,
                    "label": relation_label or self._relation_label(relation_type, text),
                    "evidence": text[:180],
                }
            )
        return results

    def _infer_pair_relation(self, sentence: str, subject: str, target: str) -> str:
        text = sentence.replace(" ", "")
        if any(pattern in text for pattern in (f"{target}生父", f"{target}生母", f"{target}父亲", f"{target}母亲")):
            return "family"
        if any(pattern in text for pattern in (f"{target}的妹妹", f"{target}的兄长", f"{target}的哥哥", f"{target}的弟弟", f"{target}的姐姐", f"{target}的父亲", f"{target}的母亲")):
            return "family"
        if any(pattern in text for pattern in (f"{target}的盟友", f"与{target}合作", f"和{target}合作", f"同{target}并肩", f"{target}的同伴")):
            return "ally"
        if any(pattern in text for pattern in (f"与{target}在立场上摇摆合作", f"和{target}在立场上摇摆合作", f"与{target}互相防备", f"和{target}互相防备", f"与{target}彼此防备", f"和{target}彼此防备")):
            return "ally"
        if any(pattern in text for pattern in (f"{target}的敌人", f"与{target}敌对", f"和{target}敌对", f"被{target}追杀", f"追杀{target}", f"被{target}囚禁", f"{target}囚禁", f"与{target}是猎人与猎物")):
            return "enemy"
        if any(pattern in text for pattern in (f"{target}的旧识", f"与{target}旧识", f"和{target}旧识", f"重逢{target}", f"与{target}是昔日战友", f"和{target}是昔日战友", f"与{target}是战友", f"和{target}是战友")):
            return "background"
        if any(pattern in text for pattern in (f"{target}的师父", f"{target}的师兄", f"{target}的弟子", f"与{target}同门", f"和{target}同门")):
            return "mentor"
        if not any(pattern in text for pattern in (f"与{target}", f"和{target}", f"{target}的", f"{target}是", f"{target}为", f"{target}系")):
            return "connection"
        return _infer_relation_type(sentence)


def _clean_text_for_relation(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("**", "")).strip()


def _extract_clean_clauses(text: str, min_len: int = 6) -> List[str]:
    clauses: List[str] = []
    for part in re.split(r"[。！？!?；;\n]+", str(text or "")):
        value = re.sub(r"\s+", " ", part).strip(" ，,、\t")
        if len(value) >= min_len:
            clauses.append(value)
    return clauses


def _ensure_sentence_end(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if value[-1] in "。！？!?；;":
        return value
    return value + "。"

