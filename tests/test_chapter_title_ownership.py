from __future__ import annotations

import pytest

from novel_workflow.runtime.graph.chapter_decision import save_edited_chapter_candidate
from novel_workflow.storage.chapter_store import ChapterStore
from novel_workflow.storage.event_projection import EventProjection


def test_prose_edit_preserves_the_detail_owned_chapter_title(tmp_path) -> None:
    chapters = ChapterStore(tmp_path / "chapters")
    events = EventProjection(tmp_path / "events")
    source = {
        "chapter_id": "chapter-1",
        "version_id": "chapter-1-v1",
        "title": "档案余烬",
        "content": "原始正文",
        "author_status": "candidate",
    }
    chapters.write("run-1", source)

    edited = save_edited_chapter_candidate(
        chapters,
        events,
        run_id="run-1",
        chapter_id="chapter-1",
        source_version_id="chapter-1-v1",
        payload={**source, "content": "作者修改后的正文"},
    )

    assert edited.artifact.title == "档案余烬"
    with pytest.raises(ValueError, match="owned by the frozen Detail"):
        save_edited_chapter_candidate(
            chapters,
            events,
            run_id="run-1",
            chapter_id="chapter-1",
            source_version_id="chapter-1-v1",
            payload={**source, "title": "正文另起章名", "content": "作者修改后的正文"},
        )
