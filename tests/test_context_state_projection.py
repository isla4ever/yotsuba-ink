from __future__ import annotations

import json

from novel_workflow.memory.resolved_story_state import (
    ResolvedStoryState,
    StoryStateEntry,
)
from novel_workflow.runtime.graph.context_compiler import (
    _context_story_state,
    _continuity_state_projection,
)


def _entry(
    fact_id: str,
    *,
    subject_id: str = "subject-1",
    property_key: str,
    value: str,
    chapter: int,
) -> StoryStateEntry:
    return StoryStateEntry(
        subject_id=subject_id,
        property_key=property_key,
        value=value,
        epistemic_status="fact",
        source_fact_id=fact_id,
        source_chapter=chapter,
        source_chain=[fact_id],
    )


def test_context_state_drops_unbound_and_ephemeral_claims() -> None:
    state = ResolvedStoryState(
        as_of_chapter=6,
        entries=[
            _entry("fact-claim", subject_id="story", property_key="claim:fact-claim", value="一次性叙事事实", chapter=1),
            _entry("fact-action", property_key="action", value="完成一次动作", chapter=6),
            _entry("fact-status", property_key="employment_status", value="suspended", chapter=2),
            _entry("fact-status-duplicate", property_key="employment_status", value="suspended", chapter=5),
        ],
    )

    projected = _context_story_state(state)

    assert [item["property_key"] for item in projected["entries"]] == [
        "employment_status"
    ]
    assert len(json.dumps(projected, ensure_ascii=False)) < 9_000


def test_context_state_compacts_large_durable_projection() -> None:
    state = ResolvedStoryState(
        as_of_chapter=80,
        entries=[
            _entry(
                f"fact-{index}",
                property_key=f"durable_state_{index}",
                value="长期事实 " + ("x" * 180),
                chapter=index,
            )
            for index in range(1, 81)
        ],
    )

    projected = _context_story_state(state)
    encoded = json.dumps(projected, ensure_ascii=False, separators=(",", ":"))

    assert len(encoded) <= 9_000
    assert projected["omitted_entry_count"] > 0
    assert projected["entries"]


def test_continuity_projection_groups_provenance_knowledge_objects_and_open_clues() -> None:
    state = ResolvedStoryState(
        as_of_chapter=4,
        entries=[
            _entry(
                "fact-source",
                subject_id="story",
                property_key="evidence.ledger.source",
                value="档案馆原件",
                chapter=1,
            ),
            _entry(
                "fact-knowledge",
                property_key="knowledge.ledger_owner",
                value="林默知道原件由警方保管",
                chapter=2,
            ),
            _entry(
                "fact-object",
                subject_id="story",
                property_key="object.blue_button.state",
                value="封存在证物袋",
                chapter=3,
            ),
            StoryStateEntry(
                subject_id="story",
                property_key="clue.page_seven.status",
                value="来源未核验",
                epistemic_status="belief",
                source_fact_id="fact-open-clue",
                source_chapter=4,
                source_chain=["fact-open-clue"],
            ),
        ],
    )

    projected = _continuity_state_projection(state)

    assert [item["source_fact_id"] for item in projected["evidence_provenance"]] == [
        "fact-source",
    ]
    assert projected["character_knowledge"][0]["source_fact_id"] == "fact-knowledge"
    assert projected["object_states"][0]["source_fact_id"] == "fact-object"
    assert projected["unresolved_clues"][0]["source_fact_id"] == "fact-open-clue"
