from __future__ import annotations

import pytest

from novel_workflow.references.collaboration_field_policy import (
    collaboration_field_is_editable,
)


@pytest.mark.parametrize(
    ("stage_id", "field_path"),
    [
        ("spine", "turns.0.cause"),
        ("spine", "open_questions.2"),
        ("cast", "subjects.1.speech_style"),
        ("cast", "relations.0.pressure"),
        ("volumes", "volumes.3.closure"),
        ("detail", "chapters.2.purpose"),
        ("detail", "chapters.2.scenes.1.result"),
        ("text", "content"),
    ],
)
def test_collaboration_field_policy_accepts_literary_text_fields(
    stage_id: str,
    field_path: str,
) -> None:
    assert collaboration_field_is_editable(stage_id, field_path)


@pytest.mark.parametrize(
    ("stage_id", "field_path"),
    [
        ("spine", "turns.0.id"),
        ("spine", "turns.0.progress_type"),
        ("cast", "subjects.0.id"),
        ("cast", "subjects.0.kind"),
        ("cast", "relations.0.a"),
        ("volumes", "volumes.0.turn_refs.0"),
        ("detail", "chapters.0.title"),
        ("detail", "chapters.0.scenes.0.id"),
        ("text", "author_status"),
        ("brief", "promise"),
    ],
)
def test_collaboration_field_policy_rejects_identity_and_structure_fields(
    stage_id: str,
    field_path: str,
) -> None:
    assert not collaboration_field_is_editable(stage_id, field_path)
