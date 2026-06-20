from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from novel_workflow.references.schemas import ReferenceDocument, ReferenceUploadRequest
from novel_workflow.storage.json_store import JsonStore


class ReferenceStore:
    def __init__(self, root: Path) -> None:
        self.store = JsonStore(root)

    def create(self, request: ReferenceUploadRequest) -> ReferenceDocument:
        reference_id = f"ref-{uuid4().hex[:12]}"
        content = request.content.strip()
        document = ReferenceDocument(
            reference_id=reference_id,
            title=request.title.strip(),
            content=content,
            preview=_preview(content),
            char_count=len(content),
            source_type=request.source_type,
        )
        self.store.write(reference_id, document.model_dump())
        return document

    def read(self, reference_id: str) -> ReferenceDocument:
        return ReferenceDocument.model_validate(self.store.read(reference_id))


def _preview(content: str, limit: int = 180) -> str:
    compact = " ".join(content.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."
