from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _slug(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "-", value.strip().lower()).strip("-")
    return cleaned[:80] or hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


class WikiStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        path = self.root / _slug(project_id)
        path.mkdir(parents=True, exist_ok=True)
        (path / "sources").mkdir(exist_ok=True)
        (path / "index.md").touch(exist_ok=True)
        return path

    def write(self, project_id: str, title: str, content: str, source_type: str) -> dict[str, Any]:
        project = self.project_dir(project_id)
        document_id = hashlib.sha1(f"{title}\n{content}".encode("utf-8")).hexdigest()[:16]
        path = project / "sources" / f"{_slug(title)}-{document_id[:8]}.md"
        frontmatter = {
            "id": document_id,
            "title": title,
            "source_type": source_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(
            "---\n"
            + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in frontmatter.items())
            + "\n---\n\n"
            + f"# {title}\n\n{content.strip()}\n",
            encoding="utf-8",
        )
        index = project / "index.md"
        index_line = f"- [{title}](sources/{path.name})\n"
        if index_line not in index.read_text(encoding="utf-8"):
            with index.open("a", encoding="utf-8") as handle:
                handle.write(index_line)
        return {"id": document_id, "title": title, "path": str(path)}

    def load_context(
        self,
        project_id: str,
        *,
        node_id: str,
        node_type: str,
        query: str,
        kinds: list[str],
        limit: int = 6,
    ) -> dict[str, Any]:
        result = self.search(project_id, query=query, limit=limit)
        context = {
            "node_id": node_id,
            "node_type": node_type,
            "kinds": kinds,
            "query": query,
            "hits": result["results"],
            "hit_count": len(result["results"]),
        }
        return context

    def write_artifact(
        self,
        project_id: str,
        *,
        node_id: str,
        node_type: str,
        output_key: str,
        content: str,
        kinds: list[str],
    ) -> dict[str, Any]:
        title = f"{node_type}:{output_key}"
        ref = self.write(project_id, title=title, content=content, source_type="memory_writeback")
        return {**ref, "node_id": node_id, "node_type": node_type, "output_key": output_key, "kinds": kinds}

    def search(self, project_id: str, query: str, limit: int = 6) -> dict[str, Any]:
        project = self.project_dir(project_id)
        terms = [term for term in re.split(r"\s+", query.strip()) if term]
        results = []
        for path in sorted((project / "sources").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            score = sum(text.count(term) for term in terms) if terms else 1
            if score <= 0:
                continue
            results.append({"title": path.stem, "path": str(path), "score": score, "preview": text[:240]})
        results.sort(key=lambda item: item["score"], reverse=True)
        return {"query": query, "results": results[:limit]}

    def status(self, project_id: str) -> dict[str, Any]:
        project = self.project_dir(project_id)
        docs = list((project / "sources").glob("*.md"))
        return {"project_id": project_id, "documents": len(docs), "wiki_root": str(project)}
