from __future__ import annotations

import pytest

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterBibleArtifact,
    DetailArtifact,
    StoryBriefArtifact,
    StorySpineArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.quality.planning_contracts import (
    build_mystery_promise_ledger,
    project_world_rules,
)
from novel_workflow.quality.narrative_contracts import build_cast_identity_findings
from novel_workflow.runtime.graph.detail_preflight import (
    DetailPreflightError,
    DetailPreflightReport,
    PlanningBlocker,
    build_detail_preflight,
    require_detail_preflight,
)
from novel_workflow.runtime.graph.runtime import filesystem_stores
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.planning_authority import HierarchicalPlanningAuthority
from tests.fakes import FakeNarrativeProvider


def _brief(*, world_rules: list[str] | None = None) -> StoryBriefArtifact:
    return StoryBriefArtifact.model_validate(
        {
            "title": "明日来电",
            "premise": "急救调度员追查一通牵连家庭旧案的未来报警电话。",
            "promise": "每次干预都会改变他对父亲死亡传闻和旧案真相的理解。",
            "world_rules": world_rules
            or ["每晚固定时间会接到来自24小时后的报警电话。"],
            "theme": "亲情责任与职业伦理如何共存",
            "ending_promise": "旧案真相被揭示，主角承担干预未来的职业代价。",
            "voice": "现实克制的第三人称有限视角",
            "length_envelope": {"word_target_soft": 10_000},
        }
    )


def _spine(*, information_progress: bool = True) -> StorySpineArtifact:
    progress_types = (
        ["information", "relationship", "external"]
        if information_progress
        else ["external", "relationship", "internal"]
    )
    return StorySpineArtifact.model_validate(
        {
            "turns": [
                {
                    "id": "turn-1",
                    "cause": "未来报警点名旧案证人",
                    "change": "主角确认电话包含尚未公开的事故细节",
                    "progress_type": progress_types[0],
                    "milestones": ["inciting", "commitment"],
                },
                {
                    "id": "turn-2",
                    "cause": "证人承认死亡消息来自一次身份掩护",
                    "change": "父亲以新身份留下的证据链被揭示",
                    "progress_type": progress_types[1],
                    "milestones": ["midpoint_reversal", "crisis", "climax"],
                },
                {
                    "id": "turn-3",
                    "cause": "揭示迫使家人面对当年的选择",
                    "change": "旧案得到处理且主角承担职业处分",
                    "progress_type": progress_types[2],
                    "milestones": ["aftermath"],
                },
            ],
            "ending": "家人接受父亲当年假死隐匿的真相，主角承担处分。",
            "open_questions": ["未来电话的来源是否会在故事外延续？"],
            "progress_types": list(dict.fromkeys(progress_types)),
        }
    )


def _cast() -> CharacterBibleArtifact:
    return CharacterBibleArtifact.model_validate(
        {
            "subjects": [
                {
                    "id": "subject-1",
                    "name": "林远",
                    "kind": "protagonist",
                    "function": "在急救调度职责与家庭旧案之间作出选择。",
                    "background": "市急救中心调度员，故事开始前已值守多年并熟悉派车流程。",
                    "conflict_history": "父亲多年前被传在事故中死亡，家庭因此长期回避旧案。",
                    "present_stakes": "若违规干预失败，他会失去调度资格与家人的信任。",
                    "temperament": "受压时先核对时间与地址，再决定是否承担越规风险。",
                    "speech_style": "短句确认关键信息，犹豫时会重复对方最后一个名词。",
                    "drive": "阻止伤亡并查清家庭旧案。",
                    "change": "从独自干预转向公开承担职业与亲情后果。",
                    "debut": "chapter:1",
                    "limits": ["不得伪造急救记录或越过派车权限。"],
                    "demand_refs": ["demand-protagonist"],
                }
            ],
            "relations": [],
        }
    )


def _volumes() -> VolumeArchitectureArtifact:
    return VolumeArchitectureArtifact.model_validate(
        {
            "volumes": [
                {
                    "id": "volume-1",
                    "title": "明日旧案",
                    "promise": "核验报警录音并揭示旧案身份掩护。",
                    "conflict": "职业程序限制林远取得和公开录音证据。",
                    "climax": "林远公开已核验的报警录音并承担处分。",
                    "climax_turn_ref": "turn-2",
                    "closure": "录音来源和旧案真相落地，家庭开始承担后果。",
                    "turn_refs": ["turn-1", "turn-2", "turn-3"],
                    "cast_ids": ["subject-1"],
                    "length_hint": "short",
                }
            ]
        }
    )


def _chapter(
    number: int,
    turn_ref: str,
    *,
    title: str,
    purpose: str,
    result: str,
    handoff: str,
    cast_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ref": f"chapter-{number}",
        "volume_ref": "volume-1",
        "title": title,
        "target_characters": 2500,
        "turn_refs": [turn_ref],
        "purpose": purpose,
        "pov": (cast_ids or ["subject-1"])[0],
        "cast_ids": cast_ids or ["subject-1"],
        "scenes": [
            {
                "place": "急救调度大厅",
                "objective": f"推进{purpose}",
                "conflict": "职业程序与家庭压力同时收紧",
                "turn": f"林远采取第{number}次可见行动",
                "result": result,
            }
        ],
        "handoff": handoff,
    }


def _detail() -> DetailArtifact:
    payload = {
        "chapters": [
                _chapter(
                    1,
                    "turn-1",
                    title="明日号码",
                    purpose="核验未来报警中的事故细节",
                    result="林远确认电话描述的事故尚未发生",
                    handoff="深夜，林远留在调度大厅，准备核对旧案证人",
                ),
                _chapter(
                    2,
                    "turn-2",
                    title="旧名回声",
                    purpose="揭示父亲死亡传闻背后的身份掩护",
                    result="林远确认父亲当年未死并以新身份留下证据",
                    handoff="次日清晨，林远掌握证据链，决定向家人说明真相",
                ),
                _chapter(
                    3,
                    "turn-3",
                    title="处分之后",
                    purpose="让家庭选择与职业代价同时落地",
                    result="家人接受真相，林远收到职业处分决定",
                    handoff="一周后，旧案处理完成，林远与家人开始修复关系",
                ),
            ]
        }
    payload["chapters"][0]["scenes"][0]["result"] = "林远在调度大厅取得报警录音并记录来源"
    payload["chapters"][1]["scenes"][0]["result"] = "林远核对报警录音，确认父亲身份掩护"
    payload["chapters"][2]["scenes"][0]["result"] = "林远公开报警录音并收到职业处分决定"
    return DetailArtifact.model_validate(payload)


def _report(
    detail: DetailArtifact | None = None,
    *,
    brief: StoryBriefArtifact | None = None,
    spine: StorySpineArtifact | None = None,
):
    return build_detail_preflight(
        brief=brief or _brief(),
        spine=spine or _spine(),
        cast=_cast(),
        volumes=_volumes(),
        detail=detail or _detail(),
    )


def test_world_rule_projection_captures_temporal_professional_and_recurrence() -> None:
    projection = project_world_rules(
        _brief(
            world_rules=[
                "急救调度员每晚固定时间会接到来自二十四小时后的报警电话。"
            ]
        )
    )

    rule = projection.rules[0]
    assert rule.categories == ["temporal", "professional"]
    assert rule.future_offset_hours == 24
    assert rule.fixed_time is True
    assert rule.recurrence == "periodic"
    assert rule.authorizes_repetition is True
    assert len(rule.source_hash) == 64


def test_mystery_ledger_accepts_structural_evidence_without_information_progress_type() -> None:
    report = _report(spine=_spine(information_progress=False))

    assert not any(item.code == "central_mystery_missing" for item in report.blockers)


def test_mystery_ledger_still_requires_frozen_milestones() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["turn_refs"] = ["turn-1"]
    report = _report(detail=DetailArtifact.model_validate(payload))

    blocker = next(item for item in report.blockers if item.code == "central_mystery_missing")
    assert "detail_reveal" in blocker.evidence


def test_detail_preflight_rejects_an_unfrozen_subject() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["pov"] = "subject-unknown"
    payload["chapters"][0]["cast_ids"] = ["subject-unknown"]

    report = _report(DetailArtifact.model_validate(payload))

    assert "unknown_detail_subject" in {item.code for item in report.blockers}


def test_adjacent_chapters_without_a_state_delta_are_blocked() -> None:
    payload = _detail().model_dump(mode="json")
    first = payload["chapters"][0]
    second = payload["chapters"][1]
    second.update(
        {
            "title": first["title"],
            "purpose": first["purpose"],
            "turn_refs": first["turn_refs"],
            "scenes": first["scenes"],
            "handoff": first["handoff"],
        }
    )

    report = _report(
        DetailArtifact.model_validate(payload),
        brief=_brief(world_rules=["报警电话来自24小时后的事件，只能提前一天干预。"]),
    )

    assert {"missing_state_delta", "unauthorized_repetition"} <= {
        item.code for item in report.blockers
    }


def test_periodic_story_form_passes_when_each_return_changes_state() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["title"] = payload["chapters"][0]["title"]
    payload["chapters"][1]["purpose"] = payload["chapters"][0]["purpose"]
    detail = DetailArtifact.model_validate(payload)

    report = _report(detail)

    assert report.blockers == []
    assert report.chapters[1].authorized_repetition_refs == ["world-rule-1"]


def test_explicit_resolution_before_the_climax_is_blocked() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["purpose"] = "案件正式结案后整理旧案证据"

    report = _report(DetailArtifact.model_validate(payload))

    assert "premature_main_resolution" in {item.code for item in report.blockers}


def test_waiting_for_final_ruling_before_the_climax_is_not_terminal_resolution() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["handoff"] = "听证室外，林默等待最终裁决，尚未收到结果。"

    report = _report(DetailArtifact.model_validate(payload))

    assert "premature_main_resolution" not in {item.code for item in report.blockers}


def test_false_death_and_hidden_identity_reveal_are_not_conflicts() -> None:
    report = _report(
        brief=_brief(
            world_rules=[
                "每晚固定时间会接到来自24小时后的报警电话。",
                "已确认的死亡传闻可以被后续证据反驳，隐藏身份必须留下来源与后果。",
            ]
        )
    )

    require_detail_preflight(report)


def test_short_spine_milestone_overlap_keeps_ledger_refs_stable() -> None:
    spine = StorySpineArtifact.model_validate(
        {
            "turns": [
                {
                    "id": "turn-1",
                    "cause": "电话出现",
                    "change": "主角确认电话指向未来事故",
                    "progress_type": "information",
                    "milestones": [
                        "inciting",
                        "commitment",
                        "midpoint_reversal",
                        "crisis",
                        "climax",
                    ],
                },
                {
                    "id": "turn-2",
                    "cause": "主角公开电话记录",
                    "change": "家人共同承担后果",
                    "progress_type": "relationship",
                    "milestones": ["aftermath"],
                },
            ],
            "ending": "真相与代价同时落地",
            "open_questions": [],
            "progress_types": ["information", "relationship"],
        }
    )

    ledger = build_mystery_promise_ledger(_brief(), spine)

    mystery = next(item for item in ledger.entries if item.kind == "central_mystery")
    assert mystery.setup_refs == ["turn-1"]
    assert mystery.misdirection_refs == ["turn-1"]
    assert mystery.reveal_ref == "turn-1"
    assert mystery.consequence_ref == "turn-2"


def test_stage_executor_validates_detail_preflight_before_decision(tmp_path) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    run_id = "run-detail-preflight"
    brief = stores.artifacts.commit(
        run_id, "brief", _brief().model_dump(mode="json"), source="test:brief"
    )
    spine = stores.artifacts.commit(
        run_id, "spine", _spine().model_dump(mode="json"), source="test:spine"
    )
    cast = stores.artifacts.commit(
        run_id, "cast", _cast().model_dump(mode="json"), source="test:cast"
    )
    volumes = stores.artifacts.commit(
        run_id,
        "volumes",
        _volumes().model_dump(mode="json"),
        source="test:volumes",
    )
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1].update(
        {
            "turn_refs": payload["chapters"][0]["turn_refs"],
            "scenes": payload["chapters"][0]["scenes"],
            "handoff": payload["chapters"][0]["handoff"],
        }
    )
    candidate = stores.artifacts.save_candidate(
        run_id,
        "detail",
        payload,
        source="test:detail",
        subject_ids={"subject-1"},
        volume_cast_ids={"volume-1": {"subject-1"}},
    )
    executor = StageExecutor(
        runs=stores.runs,
        artifacts=stores.artifacts,
        planning=HierarchicalPlanningAuthority(
            runs=stores.runs,
            store=stores.planning_aggregates,
        ),
        chapters=stores.chapters,
        operations=stores.operations,
        events=stores.events,
        evidence=stores.evidence,
        exports=stores.exports,
        cover_assets=stores.cover_assets,
        context_manifests=stores.context_manifests,
        outbox=stores.outbox,
        provider=FakeNarrativeProvider(),
    )
    state = {
        "run_id": run_id,
        "artifact_refs": {
            "brief": brief.artifact_id,
            "spine": spine.artifact_id,
                "cast": cast.artifact_id,
                "volumes": volumes.artifact_id,
            },
        "candidate_artifact_refs": {"detail": candidate.artifact_id},
    }

    with pytest.raises(DetailPreflightError, match="missing_state_delta"):
        executor.validate_candidate(state, "detail")  # type: ignore[arg-type]


def test_cross_artifact_identity_binding_rejects_competing_employers() -> None:
    cast_payload = _cast().model_dump(mode="json")
    cast_payload["subjects"][0]["background"] = (
        "林远是王建国的助理，故事开始前负责整理旧案材料并核对公开记录。"
    )
    detail_payload = _detail().model_dump(mode="json")
    detail_payload["chapters"][0]["purpose"] = (
        "林远以周启明的助理身份取得报警录音并记录来源"
    )

    report = build_detail_preflight(
        brief=_brief(),
        spine=_spine(),
        cast=CharacterBibleArtifact.model_validate(cast_payload),
        volumes=_volumes(),
        detail=DetailArtifact.model_validate(detail_payload),
    )

    codes = {item.code for item in report.blockers}
    assert "subject_identity_conflict" in codes
    assert "unbound_identity_target" in codes


def test_cast_identity_preflight_runs_before_detail_generation() -> None:
    cast_payload = _cast().model_dump(mode="json")
    cast_payload["subjects"][0]["background"] = (
        "林远是王建国的助理，故事开始前负责整理旧案材料并核对公开记录。"
    )

    findings = build_cast_identity_findings(
        spine=_spine(),
        cast=CharacterBibleArtifact.model_validate(cast_payload),
    )

    assert {item.code for item in findings} == {"unbound_identity_target"}


def test_detail_preflight_rejects_nonadjacent_duplicate_dramatic_jobs() -> None:
    payload = _detail().model_dump(mode="json")
    for index in (0, 2):
        chapter = payload["chapters"][index]
        chapter["purpose"] = "在市政厅发布会公开交易证据并面对媒体否认"
        chapter["scenes"][0].update(
            {
                "place": "市政厅发布会",
                "objective": "向警方提交并公开交易证据",
                "conflict": "律师当众否认证据并威胁诉讼",
                "turn": "林远向媒体展示交易证据",
                "result": "警方介入，媒体公开报道",
            }
        )
        chapter["handoff"] = "发布会后林远面临诉讼，警方继续核验材料"

    report = _report(DetailArtifact.model_validate(payload))

    duplicate = next(item for item in report.blockers if item.code == "detail_duplicate_job")
    assert duplicate.chapter_refs == ["chapter-1", "chapter-3"]


def test_detail_preflight_preserves_more_than_sixty_four_actionable_blockers() -> None:
    report = _report(_detail())
    blockers = [
        PlanningBlocker(
            code="detail_duplicate_job",
            chapter_refs=["chapter-1", "chapter-3"],
            evidence=f"重复任务证据 {index}",
            required_fix="让后章产生不同的行动、知识、关系或风险结果。",
        )
        for index in range(65)
    ]

    expanded = DetailPreflightReport.model_validate(
        {**report.model_dump(mode="json"), "blockers": blockers}
    )

    assert len(expanded.blockers) == 65
    with pytest.raises(DetailPreflightError, match="detail_duplicate_job"):
        require_detail_preflight(expanded)


def test_evidence_source_change_requires_an_explicit_transfer() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["scenes"][0]["result"] = (
        "警方提供报警录音，林远确认父亲身份掩护"
    )

    report = _report(DetailArtifact.model_validate(payload))

    assert "evidence_provenance_conflict" in {item.code for item in report.blockers}


def test_named_clue_requires_verification_and_payoff() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["scenes"][0]["result"] = "林远确认父亲身份掩护"
    payload["chapters"][2]["scenes"][0]["result"] = "林远收到职业处分决定"

    report = _report(DetailArtifact.model_validate(payload))

    blocker = next(item for item in report.blockers if item.code == "clue_lifecycle_incomplete")
    assert "录音" in blocker.evidence


def test_climax_cannot_introduce_an_unbound_functional_victim() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["scenes"][0]["result"] += "，并从仓库救出年轻人质"

    report = _report(DetailArtifact.model_validate(payload))

    assert "unbound_climax_victim" in {item.code for item in report.blockers}


def test_cast_debut_window_must_be_executed_by_detail() -> None:
    cast_payload = _cast().model_dump(mode="json")
    second = dict(cast_payload["subjects"][0])
    second.update(
        {
            "id": "subject-2",
            "name": "苏婉",
            "kind": "major",
            "function": "在公开旧案与保护家人之间作出独立选择。",
            "background": "地方档案馆研究员，故事开始前已整理事故目录多年。",
            "conflict_history": "曾因旧案目录缺页与林远发生争执并保留一份索引。",
            "present_stakes": "若证言失效，她会失去职业信誉和家人的信任。",
            "temperament": "受压时先封存原件，再要求对方说明公开责任。",
            "speech_style": "措辞准确，先报来源编号，再陈述自己的判断。",
            "drive": "保护证据来源并迫使旧案进入正式程序。",
            "change": "从私下保管材料转向实名承担公开后果。",
            "debut": "chapter:1-2",
            "limits": ["不得代替林远完成最终职业选择。"],
            "demand_refs": ["demand-witness"],
        }
    )
    cast_payload["subjects"].append(second)

    report = build_detail_preflight(
        brief=_brief(),
        spine=_spine(),
        cast=CharacterBibleArtifact.model_validate(cast_payload),
        volumes=_volumes(),
        detail=_detail(),
    )

    assert "subject_debut_unfulfilled" in {item.code for item in report.blockers}
