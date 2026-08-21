from __future__ import annotations

import pytest

from novel_workflow.memory.canon_store import CanonFact, CanonStore
from novel_workflow.output_contracts.provider_tasks import ChapterEvidenceResult
from novel_workflow.runtime.graph.chapter_evidence_contract import (
    project_evidence_state_bindings,
)


def _fact(
    fact_id: str,
    *,
    chapter: int,
    subject_id: str = "subject-1",
    property_key: str = "life_status",
    value: str,
    epistemic_status: str = "fact",
    lifecycle: str = "active",
    supersedes_fact_ids: list[str] | None = None,
) -> CanonFact:
    return CanonFact(
        fact_id=fact_id,
        claim=value,
        evidence_refs=[f"evidence-{fact_id}"],
        chapter_version_id=f"chapter-{chapter}-v1-accepted",
        subject_id=subject_id,
        property_key=property_key,
        value=value,
        epistemic_status=epistemic_status,
        lifecycle=lifecycle,
        effective_from_chapter=chapter,
        supersedes_fact_ids=supersedes_fact_ids or [],
    )


def test_false_death_is_resolved_by_explicit_reveal_without_conflict(tmp_path) -> None:
    store = CanonStore(tmp_path / "canon")
    rumour = _fact(
        "fact-rumour",
        chapter=1,
        value="死亡",
        epistemic_status="rumour",
    )
    reveal = _fact(
        "fact-reveal",
        chapter=5,
        value="存活并使用新身份",
        epistemic_status="reveal",
        lifecycle="supersedes",
        supersedes_fact_ids=[rumour.fact_id],
    )
    store.commit("run-1", "tx-1", [rumour])
    store.commit("run-1", "tx-2", [reveal])

    before_reveal = store.resolved_state("run-1", as_of_chapter=4)
    after_reveal = store.resolved_state("run-1", as_of_chapter=5)

    assert [(item.value, item.epistemic_status) for item in before_reveal.entries] == [
        ("死亡", "rumour")
    ]
    assert [(item.value, item.epistemic_status) for item in after_reveal.entries] == [
        ("存活并使用新身份", "reveal")
    ]
    assert after_reveal.conflicts == []


def test_unresolved_same_property_values_remain_visible_as_conflict(tmp_path) -> None:
    store = CanonStore(tmp_path / "canon")
    store.commit(
        "run-1",
        "tx-1",
        [
            _fact("fact-a", chapter=1, value="在岗"),
            _fact("fact-b", chapter=2, value="已离职"),
        ],
    )

    state = store.resolved_state("run-1", as_of_chapter=2)

    assert len(state.conflicts) == 1
    assert state.conflicts[0].fact_ids == ["fact-a", "fact-b"]
    assert {item.value for item in state.entries} == {"在岗", "已离职"}


def test_hidden_identity_keeps_the_complete_explicit_source_chain(tmp_path) -> None:
    store = CanonStore(tmp_path / "canon")
    rumour = _fact(
        "fact-rumour",
        chapter=1,
        property_key="identity",
        value="身份不明的死者",
        epistemic_status="rumour",
    )
    hidden = _fact(
        "fact-hidden",
        chapter=3,
        property_key="identity",
        value="使用周岚身份",
        epistemic_status="reveal",
        lifecycle="supersedes",
        supersedes_fact_ids=[rumour.fact_id],
    )
    restored = _fact(
        "fact-restored",
        chapter=7,
        property_key="identity",
        value="真实身份为顾行舟",
        epistemic_status="reveal",
        lifecycle="supersedes",
        supersedes_fact_ids=[hidden.fact_id],
    )
    store.commit("run-1", "tx-1", [rumour, hidden, restored])

    state = store.resolved_state("run-1", as_of_chapter=7)

    assert [(item.value, item.source_chain) for item in state.entries] == [
        (
            "真实身份为顾行舟",
            ["fact-rumour", "fact-hidden", "fact-restored"],
        )
    ]
    assert state.conflicts == []


def test_same_name_different_subjects_do_not_share_state(tmp_path) -> None:
    store = CanonStore(tmp_path / "canon")
    store.commit(
        "run-1",
        "tx-1",
        [
            _fact("fact-a", chapter=1, subject_id="subject-a", value="在调度中心"),
            _fact("fact-b", chapter=1, subject_id="subject-b", value="在医院"),
        ],
    )

    state = store.resolved_state("run-1", as_of_chapter=1)

    assert state.conflicts == []
    assert {item.subject_id for item in state.entries} == {"subject-a", "subject-b"}


def test_rumour_and_belief_are_not_physical_state_conflicts(tmp_path) -> None:
    store = CanonStore(tmp_path / "canon")
    store.commit(
        "run-1",
        "tx-1",
        [
            _fact(
                "fact-rumour",
                chapter=1,
                value="已经离开城市",
                epistemic_status="rumour",
            ),
            _fact(
                "fact-belief",
                chapter=1,
                value="仍藏在旧城区",
                epistemic_status="belief",
            ),
        ],
    )

    state = store.resolved_state("run-1", as_of_chapter=1)

    assert len(state.entries) == 2
    assert state.conflicts == []


def test_resolver_keeps_old_state_beyond_the_former_recent_claim_window(tmp_path) -> None:
    store = CanonStore(tmp_path / "canon")
    facts = [
        _fact(
            f"fact-{chapter}",
            chapter=chapter,
            property_key=f"state_{chapter}",
            value=f"长期事实 {chapter}",
        )
        for chapter in range(1, 61)
    ]
    store.commit("run-1", "tx-1", facts)

    state = store.resolved_state("run-1", as_of_chapter=60, subject_ids={"subject-1"})

    assert len(state.entries) == 60
    assert state.entries[0].value == "长期事实 1"
    assert state.entries[-1].value == "长期事实 60"


def test_evidence_state_binding_rejects_unknown_subject_or_source_fact() -> None:
    context = {
        "frozen_subjects": [{"id": "subject-1", "name": "林默", "kind": "major"}],
        "story_state": {
            "entries": [
                {
                    "subject_id": "subject-1",
                    "property_key": "life_status",
                    "source_fact_id": "fact-rumour",
                }
            ]
        },
    }
    unknown_subject = ChapterEvidenceResult.model_validate(
        {
            "claims": [
                {
                    "kind": "fact",
                    "claim": "陌生主体改变状态",
                    "span_ids": ["span-0001"],
                    "state": {
                        "type": "assertion",
                        "subject_id": "subject-unknown",
                        "property_key": "life_status",
                        "value": "存活",
                        "epistemic_status": "fact",
                    },
                }
            ]
        }
    )
    unknown_source = ChapterEvidenceResult.model_validate(
        {
            "claims": [
                {
                    "kind": "fact",
                    "claim": "林默仍然活着",
                    "span_ids": ["span-0001"],
                    "state": {
                        "type": "transition",
                        "source_fact_id": "fact-missing",
                        "action": "supersedes",
                        "value": "存活",
                        "epistemic_status": "reveal",
                    },
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="unfrozen subject"):
        project_evidence_state_bindings(unknown_subject, context)
    with pytest.raises(ValueError, match="unknown source facts"):
        project_evidence_state_bindings(unknown_source, context)


def test_evidence_transition_derives_frozen_subject_property_and_lifecycle() -> None:
    context = {
        "frozen_subjects": [{"id": "subject-1", "name": "林默", "kind": "major"}],
        "story_state": {
            "entries": [
                {
                    "subject_id": "subject-1",
                    "property_key": "life_status",
                    "source_fact_id": "fact-rumour",
                }
            ]
        },
    }
    result = ChapterEvidenceResult.model_validate(
        {
            "claims": [
                {
                    "kind": "fact",
                    "claim": "林默仍然活着",
                    "span_ids": ["span-0001"],
                    "state": {
                        "type": "transition",
                        "source_fact_id": "fact-rumour",
                        "action": "supersedes",
                        "value": "存活",
                        "epistemic_status": "reveal",
                    },
                }
            ]
        }
    )

    binding = project_evidence_state_bindings(result, context)[0]

    assert binding.subject_id == "subject-1"
    assert binding.property_key == "life_status"
    assert binding.lifecycle == "supersedes"
    assert binding.supersedes_fact_ids == ("fact-rumour",)
    with pytest.raises(ValueError, match="state"):
        ChapterEvidenceResult.model_validate(
            {
                "claims": [
                    {
                        "kind": "fact",
                        "claim": "旧式可选字段不再是 Provider 合同",
                        "span_ids": ["span-0001"],
                        "subject_id": "subject-1",
                        "property_key": "life_status",
                        "value": "存活",
                    }
                ]
            }
        )


@pytest.mark.parametrize(
    "property_key",
    [
        "evidence.ledger.holder",
        "evidence.ledger_owner",
        "document.ledger.owner",
        "object.blue_button.status",
        "clue.page_seven.state",
        "character.ledger.knows",
    ],
)
def test_evidence_assertion_rejects_noncanonical_reserved_property_namespaces(
    property_key: str,
) -> None:
    result = ChapterEvidenceResult.model_validate(
        {
            "claims": [
                {
                    "kind": "fact",
                    "claim": "林默掌握账本状态",
                    "span_ids": ["span-0001"],
                    "state": {
                        "type": "assertion",
                        "subject_id": "subject-1",
                        "property_key": property_key,
                        "value": "已确认",
                        "epistemic_status": "fact",
                    },
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="namespace|properties"):
        project_evidence_state_bindings(
            result,
            {"frozen_subjects": [{"id": "subject-1"}], "story_state": {"entries": []}},
        )


def test_evidence_assertion_requires_transition_for_an_existing_subject_property() -> None:
    result = ChapterEvidenceResult.model_validate(
        {
            "claims": [
                {
                    "kind": "fact",
                    "claim": "账本仍由林默保管",
                    "span_ids": ["span-0001"],
                    "state": {
                        "type": "assertion",
                        "subject_id": "subject-1",
                        "property_key": "evidence.ledger.owner",
                        "value": "林默",
                        "epistemic_status": "fact",
                    },
                }
            ]
        }
    )
    context = {
        "frozen_subjects": [{"id": "subject-1"}],
        "story_state": {
            "entries": [
                {
                    "source_fact_id": "fact-ledger-owner",
                    "subject_id": "subject-1",
                    "property_key": "evidence.ledger.owner",
                }
            ]
        },
    }

    with pytest.raises(ValueError, match="transition"):
        project_evidence_state_bindings(result, context)
