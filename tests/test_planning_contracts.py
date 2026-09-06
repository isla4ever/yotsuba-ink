from __future__ import annotations

import pytest

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterBibleArtifact,
    DetailArtifact,
    StoryBriefArtifact,
    StorySpineArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.output_contracts.prompt_materials import (
    DetailPreflightFeedback,
    DetailRecoverySource,
)
from novel_workflow.quality.planning_contracts import (
    build_mystery_promise_ledger,
    project_world_rules,
)
from novel_workflow.quality.narrative_contracts import (
    build_cast_identity_findings,
    dramatic_endpoints_for_text,
)
from novel_workflow.runtime.graph.detail_preflight import (
    DetailPreflightError,
    DetailPreflightReport,
    PlanningBlocker,
    build_detail_preflight,
    require_detail_preflight,
)
from novel_workflow.runtime.graph.detail_failure_recovery import (
    build_detail_recovery_source,
    merge_detail_recovery_patch,
    previous_detail_preflight_feedback,
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
    cast: CharacterBibleArtifact | None = None,
):
    return build_detail_preflight(
        brief=brief or _brief(),
        spine=spine or _spine(),
        cast=cast or _cast(),
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


def test_publication_of_all_evidence_before_the_climax_is_blocked() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["purpose"] = "林远公开所有证据并等待系统因矛盾崩溃。"

    report = _report(DetailArtifact.model_validate(payload))

    assert "premature_main_resolution" in {item.code for item in report.blockers}


def test_waiting_for_final_ruling_before_the_climax_is_not_terminal_resolution() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["handoff"] = "听证室外，林默等待最终裁决，尚未收到结果。"

    report = _report(DetailArtifact.model_validate(payload))

    assert "premature_main_resolution" not in {item.code for item in report.blockers}


def test_planning_to_publish_all_evidence_is_not_a_completed_resolution() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["handoff"] = (
        "发布会前夜，林远准备在次日听证会上公开所有证据。"
    )

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


def test_adjacent_same_turn_chapters_cannot_repeat_the_same_decision_endpoints() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["turn_refs"] = ["turn-1"]
    for chapter in payload["chapters"][:2]:
        chapter["purpose"] = "向部门提交旧案证据，遭上级拒绝后决定公开材料。"
        chapter["scenes"][0].update(
            {
                "objective": "向部门提交证据并申请重启调查",
                "conflict": "上级拒绝重启调查并威胁处分",
                "turn": "林远向部门提交旧案记录和录音证据",
                "result": "上级拒绝调查，林远决定公开证据",
            }
        )

    report = _report(DetailArtifact.model_validate(payload))

    assert any(
        item.code == "detail_duplicate_job"
        and item.chapter_refs == ["chapter-1", "chapter-2"]
        and "evidence_submission" in item.evidence
        for item in report.blockers
    )


def test_detail_preflight_does_not_block_low_similarity_jobs_for_generic_actions() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["purpose"] = "在媒体值班室发现气象记录缺页并通知维护组"
    payload["chapters"][0]["scenes"][0].update(
        {
            "place": "媒体值班室",
            "objective": "发现气象记录缺页",
            "conflict": "值班员不愿开放归档终端",
            "turn": "林远发现缺页并公开请求维护组保全终端",
            "result": "维护组封存终端，调查获得新的时间边界",
        }
    )
    payload["chapters"][2]["purpose"] = "在媒体中心发现撤离名单并公开承担家庭责任"
    payload["chapters"][2]["scenes"][0].update(
        {
            "place": "媒体中心",
            "objective": "发现撤离名单中的家庭签名",
            "conflict": "公开签名会破坏家人之间的信任",
            "turn": "林远发现签名后公开自己的亲属关系",
            "result": "家人开始质问当年的隐瞒，关系风险不可逆上升",
        }
    )

    report = _report(DetailArtifact.model_validate(payload))

    duplicate_pairs = {
        tuple(item.chapter_refs)
        for item in report.blockers
        if item.code == "detail_duplicate_job"
    }
    assert ("chapter-1", "chapter-3") not in duplicate_pairs


def test_detail_clues_keep_specific_report_labels_separate() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = (
        "林远从档案馆取得实验室报告并保管原件"
    )
    payload["chapters"][1]["scenes"][0]["result"] = (
        "林远向委员会提交漏洞报告，制度风险开始上升"
    )
    payload["chapters"][2]["scenes"][0]["result"] = (
        "林远核验实验室报告并公开证明旧案来源"
    )

    report = _report(DetailArtifact.model_validate(payload))
    clues = {item.label: item for item in report.narrative_contracts.clues}

    assert "实验室报告" in clues
    assert "漏洞报告" in clues
    assert clues["实验室报告"].central is True
    assert clues["漏洞报告"].mention_refs == ["chapter-2"]
    report_conflicts = [
        item.evidence
        for item in report.blockers
        if item.code == "evidence_provenance_conflict"
    ]
    assert not any("关键线索 报告 " in evidence for evidence in report_conflicts)


def test_detail_causal_subject_scan_does_not_read_a_room_as_a_person() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["handoff"] = (
        "傍晚，林远在调查室交出系统权限，但保留报警录音等待复核。"
    )

    report = _report(DetailArtifact.model_validate(payload))

    assert not any(
        item.code == "unregistered_causal_subject" and "查室" in item.evidence
        for item in report.blockers
    )


def test_detail_causal_subject_scan_does_not_read_modal_ability_as_a_person() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["conflict"] = (
        "苏婉受限于职责，不能直接提供证据，只能传递已经核验的信息。"
    )

    report = _report(DetailArtifact.model_validate(payload))

    assert not any(
        item.code == "unregistered_causal_subject" and "能直接" in item.evidence
        for item in report.blockers
    )


def test_refused_document_is_not_projected_as_an_existing_clue() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["purpose"] = (
        "林远找到退休官员，对方承认旧案选择，但拒绝提供书面证词。"
    )
    payload["chapters"][0]["scenes"][0]["result"] = (
        "林远要求官员提供书面证词，官员拒绝书面证词。"
    )

    report = _report(DetailArtifact.model_validate(payload))

    assert "书面证词" not in {
        item.label for item in report.narrative_contracts.clues
    }
    assert not any("书面证词" in item.evidence for item in report.blockers)


def test_possible_document_is_not_projected_as_an_existing_clue() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["purpose"] = "仓库里可能存有原始纸质记录。"

    report = _report(DetailArtifact.model_validate(payload))

    assert "原始纸质记录" not in {
        item.label for item in report.narrative_contracts.clues
    }


def test_system_generated_record_keeps_its_source() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = (
        "数字孪生系统自动生成电子记录，林远取得电子记录并保存。"
    )
    payload["chapters"][1]["scenes"][0]["result"] = "林远核验电子记录并确认来源。"
    payload["chapters"][2]["scenes"][0]["result"] = "林远公开电子记录并证明旧案责任。"

    report = _report(DetailArtifact.model_validate(payload))
    clue = next(
        item
        for item in report.narrative_contracts.clues
        if item.label == "电子记录"
    )

    assert "数字孪生系统" in clue.source_labels
    assert not any(
        item.code == "clue_source_missing" and "电子记录" in item.evidence
        for item in report.blockers
    )


def test_source_verb_is_not_part_of_the_clue_identity() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = (
        "林远从档案室取得并持有纸质撤离记录。"
    )

    report = _report(DetailArtifact.model_validate(payload))
    labels = {item.label for item in report.narrative_contracts.clues}

    assert "纸质撤离记录" in labels
    assert "持有纸质撤离记录" not in labels


def test_clue_identity_does_not_include_the_actor_and_grammar_particle() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = (
        "林远从档案室取得纸质撤离记录并登记来源。"
    )
    payload["chapters"][1]["scenes"][0]["result"] = (
        "林远将纸质撤离记录交给警方核验。"
    )
    payload["chapters"][2]["scenes"][0]["result"] = (
        "警方公开纸质撤离记录并证明旧案责任。"
    )

    report = _report(DetailArtifact.model_validate(payload))
    labels = {item.label for item in report.narrative_contracts.clues}

    assert "纸质撤离记录" in labels
    assert "林远将纸质撤离记录" not in labels


def test_generic_clue_alias_uses_the_unique_specific_label_in_its_chapter() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = (
        "林远从档案室取得纸质撤离记录并登记来源。"
    )
    payload["chapters"][1]["purpose"] = "核验纸质撤离记录中的签名。"
    payload["chapters"][1]["scenes"][0]["result"] = (
        "林远把纸质记录与签名比对，确认旧案责任。"
    )
    payload["chapters"][2]["scenes"][0]["result"] = (
        "林远公开纸质撤离记录并证明旧案责任。"
    )

    report = _report(DetailArtifact.model_validate(payload))
    clues = {item.label: item for item in report.narrative_contracts.clues}

    assert "纸质记录" not in clues
    assert clues["纸质撤离记录"].mention_refs == [
        "chapter-1",
        "chapter-2",
        "chapter-3",
    ]


def test_adjacent_chapters_cannot_repeat_the_same_turn_discovery() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["turn_refs"] = payload["chapters"][0]["turn_refs"]
    payload["chapters"][0]["purpose"] = "林远在拘留中获得父亲留下的信息并确认旧案坐标。"
    payload["chapters"][1]["purpose"] = "林远在拘留中分析父亲信息并确认旧案坐标。"
    payload["chapters"][0]["scenes"][-1]["result"] = "林远确认父亲留下旧案坐标。"
    payload["chapters"][1]["scenes"][-1]["result"] = "林远再次确认父亲留下的旧案坐标。"

    report = _report(DetailArtifact.model_validate(payload))

    assert any(
        item.code == "detail_duplicate_job"
        and item.chapter_refs == ["chapter-1", "chapter-2"]
        for item in report.blockers
    )


def test_detail_cannot_resolve_an_unresolved_historical_subject_as_dead() -> None:
    cast_payload = _cast().model_dump(mode="json")
    historical = dict(cast_payload["subjects"][0])
    historical.update(
        {
            "id": "subject-2",
            "name": "顾清岚",
            "kind": "historical_record",
            "function": "她的失踪记录持续改变林远对旧案责任的判断。",
            "background": "旧港档案员，故事开始前在事故夜后失踪。",
            "conflict_history": "事故后下落不明，现有记录无法确认她是否仍然生还。",
            "present_stakes": "她留下的记录若被误读，旧案责任会继续落在错误主体上。",
            "temperament": "档案文字总先列来源编号，再留下未完成的核验备注。",
            "speech_style": "仅在历史录音中使用短句复述编号，不作当下发言。",
            "drive": "通过历史记录保留事故真相的可追溯线索。",
            "change": "从被视为已失踪的记录主体转为可能仍待寻找的关键线索。",
            "debut": "chapter:1-3",
            "limits": ["档案与录音只能由现存人物解读，顾清岚不得亲自参与事故后的事件。"],
            "demand_refs": ["demand-historical-record"],
        }
    )
    cast_payload["subjects"].append(historical)
    detail_payload = _detail().model_dump(mode="json")
    detail_payload["chapters"][1]["purpose"] += "，并确认顾清岚已经死亡。"

    report = _report(
        DetailArtifact.model_validate(detail_payload),
        cast=CharacterBibleArtifact.model_validate(cast_payload),
    )

    assert any(
        item.code == "historical_status_overreach"
        and item.chapter_refs == ["chapter-2", "subject-2"]
        for item in report.blockers
    )


def test_modal_historical_opinion_does_not_resolve_an_unresolved_subject() -> None:
    cast_payload = _cast().model_dump(mode="json")
    historical = dict(cast_payload["subjects"][0])
    historical.update(
        {
            "id": "subject-2",
            "name": "顾清岚",
            "kind": "historical_record",
            "function": "她的失踪记录持续改变林远对旧案责任的判断。",
            "background": "旧港档案员，故事开始前在事故夜后失踪。",
            "conflict_history": "事故后下落不明，现有记录无法确认她是否仍然生还。",
            "present_stakes": "若记录被误读，旧案责任会继续落在错误主体上。",
            "temperament": "档案文字总先列来源编号，再留下未完成的核验备注。",
            "speech_style": "仅在历史录音中使用短句复述编号，不作当下发言。",
            "drive": "通过历史记录保留事故真相的可追溯线索。",
            "change": "从被视为已失踪的记录主体转为可能仍待寻找的关键线索。",
            "debut": "chapter:1-3",
            "limits": ["档案与录音只能由现存人物解读，顾清岚不得亲自参与事故后的事件。"],
            "demand_refs": ["demand-historical-record"],
        }
    )
    cast_payload["subjects"].append(historical)
    detail_payload = _detail().model_dump(mode="json")
    detail_payload["chapters"][1]["purpose"] += "，林远担心顾清岚可能已不在人世。"

    report = _report(
        DetailArtifact.model_validate(detail_payload),
        cast=CharacterBibleArtifact.model_validate(cast_payload),
    )

    assert not any(
        item.code == "historical_status_overreach" for item in report.blockers
    )


def test_detail_rejects_an_unexplained_return_to_custody_after_release() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = "林远被警方拘留，报警录音由律师保管"
    payload["chapters"][0]["handoff"] = "深夜，林远仍被拘留，等待律师探视"
    payload["chapters"][1]["scenes"][0].update(
        {
            "place": "拘留所探视室",
            "turn": "律师完成保释申请",
            "result": "林远获释并带着报警录音离开拘留所",
        }
    )
    payload["chapters"][1]["handoff"] = "次日清晨，林远获释后返回急救中心"
    payload["chapters"][2]["purpose"] = "林远在拘留中继续核验旧案证据"
    payload["chapters"][2]["scenes"][0].update(
        {
            "place": "拘留所探视室",
            "objective": "通过律师继续核验旧案证据",
            "turn": "律师向林远转交旧案目录",
            "result": "林远核验目录并决定公开报警录音",
        }
    )

    report = _report(DetailArtifact.model_validate(payload))

    assert any(
        item.code == "custody_handoff_conflict"
        and item.chapter_refs == ["chapter-2", "chapter-3"]
        for item in report.blockers
    )


def test_detail_accepts_an_explicit_surrender_before_returning_to_custody() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = "林远被警方拘留，报警录音由律师保管"
    payload["chapters"][0]["handoff"] = "深夜，林远仍被拘留，等待律师探视"
    payload["chapters"][1]["scenes"][0].update(
        {
            "place": "拘留所探视室",
            "turn": "律师完成保释申请",
            "result": "林远获释并带着报警录音离开拘留所",
        }
    )
    payload["chapters"][1]["handoff"] = "次日清晨，林远获释后返回急救中心"
    payload["chapters"][2]["purpose"] = "林远主动自首后在拘留中继续核验旧案证据"
    payload["chapters"][2]["scenes"] = [
        {
            "place": "急救中心门外",
            "objective": "承担违规调查的法律后果",
            "conflict": "继续逃避会让证据失去程序效力",
            "turn": "林远向警方主动自首并被带离急救中心",
            "result": "警方完成拘留手续，林远等待律师到场",
        },
        {
            "place": "拘留所探视室",
            "objective": "通过律师继续核验旧案证据",
            "conflict": "律师只能按程序传递材料",
            "turn": "律师向林远转交旧案目录",
            "result": "林远核验目录并保留尚未公开的结论",
        },
    ]
    payload["chapters"][2]["handoff"] = "深夜，林远在拘留所等待下一次程序审查"

    report = _report(DetailArtifact.model_validate(payload))

    assert not any(item.code == "custody_handoff_conflict" for item in report.blockers)


def test_custody_recovery_source_projects_the_adjacent_state_contract() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["scenes"][0]["result"] = "林远获释并返回急救中心"
    payload["chapters"][1]["handoff"] = "次日清晨，林远获释后返回急救中心"
    payload["chapters"][2]["purpose"] = "林远被拘留后通过律师核验旧案证据"
    payload["chapters"][2]["scenes"][0]["place"] = "拘留所探视室"
    detail = DetailArtifact.model_validate(payload)
    feedback = DetailPreflightFeedback.model_validate(
        {
            "source_candidate_ref": "detail-candidate-rejected",
            "source_attempt": 3,
            "unique_blocker_count": 1,
            "omitted_blocker_count": 0,
            "blockers": [
                {
                    "code": "custody_handoff_conflict",
                    "chapter_refs": ["chapter-2", "chapter-3"],
                    "evidence": "chapter-2 leaves the protagonist free",
                    "required_fix": "Execute a new arrest before the custody scene.",
                }
            ],
        }
    )
    source, local_feedback = build_detail_recovery_source(
        detail=detail,
        feedback=feedback,
        unit_id="volume-1.segment-1",
        provider_context={
            "material": {
                "scale_projection": {
                    "chapter_number_start": 1,
                    "chapter_target": 3,
                    "chapter_beats": [
                        {
                            "turn_refs": chapter.turn_refs,
                            "dramatic_job": chapter.purpose,
                        }
                        for chapter in detail.chapters
                    ],
                }
            }
        },
    )

    assert local_feedback is not None
    assert source.editable_chapter_refs == ["chapter-3"]
    assert source.custody_repair_contracts["chapter-3"].model_dump() == {
        "previous_chapter_ref": "chapter-2",
        "previous_state": "free",
        "target_state": "detained",
        "transition_timing": "on_page_before_custody",
        "allowed_institution": "警方",
        "preserved_dramatic_task": "林远通过律师核验旧案证据",
    }


def test_detail_may_repeat_a_terminal_historical_status_frozen_upstream() -> None:
    cast_payload = _cast().model_dump(mode="json")
    historical = dict(cast_payload["subjects"][0])
    historical.update(
        {
            "id": "subject-2",
            "name": "顾清岚",
            "kind": "historical_record",
            "function": "她的死亡记录促使林远追查旧案责任。",
            "background": "旧港档案员，故事开始前已在事故中确认死亡。",
            "conflict_history": "警务记录已确认她死于事故，争议只剩事故责任。",
            "present_stakes": "若记录被销毁，旧案责任将无法追溯。",
            "temperament": "档案文字总先列来源编号，再写核验结论。",
            "speech_style": "仅在历史录音中使用短句复述编号，不作当下发言。",
            "drive": "通过历史记录保留事故责任线索。",
            "change": "死亡事实不变，记录来源从被忽略转为公开核验。",
            "debut": "chapter:1-3",
            "limits": ["档案与录音只能由现存人物解读，顾清岚不得亲自参与事故后的事件。"],
            "demand_refs": ["demand-historical-record"],
        }
    )
    cast_payload["subjects"].append(historical)
    spine_payload = _spine().model_dump(mode="json")
    spine_payload["turns"][0]["cause"] += "，顾清岚的死亡档案出现来源缺口。"
    detail_payload = _detail().model_dump(mode="json")
    detail_payload["chapters"][0]["purpose"] += "，核验顾清岚已经死亡的档案来源。"

    report = _report(
        DetailArtifact.model_validate(detail_payload),
        spine=StorySpineArtifact.model_validate(spine_payload),
        cast=CharacterBibleArtifact.model_validate(cast_payload),
    )

    assert not any(
        item.code == "historical_status_overreach" for item in report.blockers
    )


def test_generic_clue_mentions_reuse_one_upstream_specific_label() -> None:
    spine_payload = _spine().model_dump(mode="json")
    spine_payload["turns"][0]["cause"] += "，档案馆保存旧港区居民名单"
    detail_payload = _detail().model_dump(mode="json")
    detail_payload["chapters"][0]["scenes"][0]["result"] = (
        "林远从档案馆取得旧港区居民名单并记录来源"
    )
    detail_payload["chapters"][1]["scenes"][0]["result"] = (
        "林远核验名单并确认父亲身份掩护"
    )
    detail_payload["chapters"][2]["scenes"][0]["result"] = (
        "林远公开名单并收到职业处分决定"
    )

    report = _report(
        DetailArtifact.model_validate(detail_payload),
        spine=StorySpineArtifact.model_validate(spine_payload),
    )
    clue = next(
        item
        for item in report.narrative_contracts.clues
        if item.label == "旧港区居民名单"
    )

    assert clue.mention_refs == ["chapter-1", "chapter-2", "chapter-3"]
    assert clue.source_labels == ["档案馆"]
    assert clue.verification_refs == ["chapter-1", "chapter-2"]
    assert clue.payoff_refs == ["chapter-2", "chapter-3"]
    assert not any(
        item.code in {"evidence_provenance_conflict", "clue_lifecycle_incomplete"}
        and "旧港区居民名单" in item.evidence
        for item in report.blockers
    )


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


def test_detail_preflight_feedback_reads_the_checkpoint_source_bound_candidate(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    run_id = "run-detail-preflight-feedback"
    refs = {
        "brief": stores.artifacts.commit(
            run_id, "brief", _brief(), source="decision:brief"
        ).artifact_id,
        "spine": stores.artifacts.commit(
            run_id, "spine", _spine(), source="decision:spine"
        ).artifact_id,
        "cast": stores.artifacts.commit(
            run_id, "cast", _cast(), source="decision:cast"
        ).artifact_id,
        "volumes": stores.artifacts.commit(
            run_id, "volumes", _volumes(), source="decision:volumes"
        ).artifact_id,
    }
    payload = _detail().model_dump(mode="json")
    first = payload["chapters"][0]
    payload["chapters"][1].update(
        {
            "title": first["title"],
            "purpose": first["purpose"],
            "turn_refs": first["turn_refs"],
            "scenes": first["scenes"],
            "handoff": first["handoff"],
        }
    )
    candidate = stores.artifacts.save_candidate(
        run_id,
        "detail",
        DetailArtifact.model_validate(payload),
        source=f"provider:{run_id}:detail:generate:1",
    )
    state = {
        "run_id": run_id,
        "artifact_refs": refs,
        "candidate_artifact_refs": {"detail": candidate.artifact_id},
        "stage_attempts": {"detail": 2},
        "stage_revision_directions": {},
    }

    feedback = previous_detail_preflight_feedback(stores.artifacts, state)  # type: ignore[arg-type]

    assert feedback is not None
    assert feedback.source_candidate_ref == candidate.artifact_id
    assert feedback.source_attempt == 1
    assert {item.code for item in feedback.blockers} >= {
        "detail_duplicate_job",
        "missing_state_delta",
    }

    interrupted_recovery_state = {
        **state,
        "stage_attempts": {"detail": 3},
    }
    interrupted_feedback = previous_detail_preflight_feedback(
        stores.artifacts,
        interrupted_recovery_state,  # type: ignore[arg-type]
    )
    assert interrupted_feedback is not None
    assert interrupted_feedback.source_candidate_ref == candidate.artifact_id
    assert interrupted_feedback.source_attempt == 1

    edited = stores.artifacts.save_candidate(
        run_id,
        "detail",
        DetailArtifact.model_validate(payload),
        source="author:edited-candidate",
    )
    edited_state = {
        **state,
        "candidate_artifact_refs": {"detail": edited.artifact_id},
    }
    assert (
        previous_detail_preflight_feedback(
            stores.artifacts,
            edited_state,  # type: ignore[arg-type]
        )
        is None
    )
    author_regeneration_state = {
        **state,
        "stage_revision_directions": {"detail": "让第二章改为关系决裂。"},
    }
    assert (
        previous_detail_preflight_feedback(
            stores.artifacts,
            author_regeneration_state,  # type: ignore[arg-type]
        )
        is None
    )


def test_detail_recovery_source_rejects_malformed_chapter_refs_before_number_parsing() -> None:
    chapter = _detail().chapters[0].model_dump(
        mode="json",
        exclude={"ref", "volume_ref", "target_characters", "turn_refs"},
    )

    with pytest.raises(ValueError, match="chapter-N format"):
        DetailRecoverySource.model_validate(
            {
                "source_candidate_ref": "detail-candidate-rejected",
                "source_attempt": 1,
                "segment_ref": "volume-1.segment-1",
                "chapter_refs": ["chapter-x"],
                "editable_chapter_refs": ["chapter-x"],
                "preserved_chapter_refs": [],
                "required_removed_endpoints": {},
                "source_segment": {"chapters": [chapter]},
            }
        )


def test_detail_recovery_rejects_a_noop_editable_segment() -> None:
    chapter = _detail().chapters[0].model_dump(
        mode="json",
        exclude={"ref", "volume_ref", "target_characters", "turn_refs"},
    )
    source = DetailRecoverySource.model_validate(
        {
            "source_candidate_ref": "detail-candidate-rejected",
            "source_attempt": 1,
            "segment_ref": "volume-1.segment-1",
            "chapter_refs": ["chapter-1"],
            "editable_chapter_refs": ["chapter-1"],
            "preserved_chapter_refs": [],
            "required_removed_endpoints": {},
            "source_segment": {"chapters": [chapter]},
        }
    )

    unchanged = {
        key: chapter[key]
        for key in ("purpose", "scenes", "handoff")
    }
    with pytest.raises(ValueError, match="without materially changing it"):
        merge_detail_recovery_patch(
            {"chapters": [unchanged]},
            source,
            selected_dossiers=[],
        )


def test_detail_recovery_requires_the_custody_transition_before_the_custody_scene() -> None:
    chapter = _detail().chapters[0].model_dump(
        mode="json",
        exclude={"ref", "volume_ref", "target_characters", "turn_refs"},
    )
    chapter.update(
        {
            "title": "拘留所来客",
            "purpose": "林远被拘留后通过律师获得旧案目录",
            "scenes": [
                {
                    "place": "拘留所探视室",
                    "objective": "通过律师取得旧案目录",
                    "conflict": "律师只能按程序传递材料",
                    "turn": "律师向林远转交旧案目录",
                    "result": "林远核验目录中的时间记录",
                }
            ],
            "handoff": "深夜，林远仍在拘留所等待下一次程序审查",
        }
    )
    source = DetailRecoverySource.model_validate(
        {
            "source_candidate_ref": "detail-candidate-rejected",
            "source_attempt": 3,
            "segment_ref": "volume-1.segment-1",
            "chapter_refs": ["chapter-3"],
            "editable_chapter_refs": ["chapter-3"],
            "preserved_chapter_refs": [],
            "required_removed_endpoints": {},
            "custody_repair_contracts": {
                "chapter-3": {
                    "previous_chapter_ref": "chapter-2",
                    "previous_state": "free",
                    "target_state": "detained",
                    "transition_timing": "on_page_before_custody",
                    "allowed_institution": "警方",
                    "preserved_dramatic_task": "林远通过律师获得旧案目录",
                }
            },
            "source_segment": {"chapters": [chapter]},
        }
    )
    no_transition = {
        "purpose": "林远在拘留中通过律师获得并核验旧案目录",
        "scenes": chapter["scenes"],
        "handoff": chapter["handoff"],
    }

    with pytest.raises(ValueError, match="free-to-custody transition on page"):
        merge_detail_recovery_patch(
            {"chapters": [no_transition]},
            source,
            selected_dossiers=[],
        )

    repaired = {
        "purpose": "林远在急救中心外重新被拘留，随后通过律师获得旧案目录",
        "scenes": [
            {
                "place": "急救中心门外",
                "objective": "依法回应警方传唤",
                "conflict": "台风临近而程序要求立即到案",
                "turn": "林远向警方自首并被带离急救中心",
                "result": "警方完成拘留手续，林远等待律师到场",
            },
            chapter["scenes"][0],
        ],
        "handoff": chapter["handoff"],
    }
    merged = merge_detail_recovery_patch(
        {"chapters": [repaired]},
        source,
        selected_dossiers=[],
    )

    assert merged["chapters"][0]["scenes"] == repaired["scenes"]


def test_detail_recovery_rejects_cosmetic_edits_that_keep_forbidden_endpoints() -> None:
    chapter = _detail().chapters[0].model_dump(
        mode="json",
        exclude={"ref", "volume_ref", "target_characters", "turn_refs"},
    )
    chapter["purpose"] = "提交证据后遭上级拒绝，决定公开材料"
    chapter["scenes"][0]["result"] = "上级拒绝调查，林远决定公开证据"
    source = DetailRecoverySource.model_validate(
        {
            "source_candidate_ref": "detail-candidate-rejected",
            "source_attempt": 1,
            "segment_ref": "volume-1.segment-1",
            "chapter_refs": ["chapter-1"],
            "editable_chapter_refs": ["chapter-1"],
            "preserved_chapter_refs": [],
            "required_removed_endpoints": {
                "chapter-1": ["authority_refusal", "public_decision"]
            },
            "source_segment": {"chapters": [chapter]},
        }
    )
    cosmetic = {
        "purpose": f"当日，{chapter['purpose']}",
        "scenes": chapter["scenes"],
        "handoff": chapter["handoff"],
    }

    with pytest.raises(ValueError, match="kept dramatic endpoints"):
        merge_detail_recovery_patch(
            {"chapters": [cosmetic]},
            source,
            selected_dossiers=[],
        )


def test_detail_recovery_patch_restores_preserved_chapters_from_source() -> None:
    chapters = [
        chapter.model_dump(
            mode="json",
            exclude={"ref", "volume_ref", "target_characters", "turn_refs"},
        )
        for chapter in _detail().chapters
    ]
    source = DetailRecoverySource.model_validate(
        {
            "source_candidate_ref": "detail-candidate-rejected",
            "source_attempt": 3,
            "segment_ref": "volume-1.segment-1",
            "chapter_refs": ["chapter-1", "chapter-2", "chapter-3"],
            "editable_chapter_refs": ["chapter-2"],
            "preserved_chapter_refs": ["chapter-1", "chapter-3"],
            "required_removed_endpoints": {},
            "source_segment": {"chapters": chapters},
        }
    )
    edited = {
        **chapters[1],
        "purpose": "核对旧案证据来源并保留尚未公开的结论",
        "handoff": "林远完成内部核验，公开与否仍留待下一章决定",
    }

    patch = {
        key: edited[key]
        for key in ("purpose", "scenes", "handoff")
    }
    merged = merge_detail_recovery_patch(
        {"chapters": [patch]},
        source,
        selected_dossiers=[],
    )

    assert merged["chapters"][0] == chapters[0]
    assert merged["chapters"][1] == edited
    assert merged["chapters"][2] == chapters[2]


def test_detail_recovery_patch_rejects_a_new_subject_outside_frozen_cast() -> None:
    chapter = _detail().chapters[0].model_dump(
        mode="json",
        exclude={"ref", "volume_ref", "target_characters", "turn_refs"},
    )
    source = DetailRecoverySource.model_validate(
        {
            "source_candidate_ref": "detail-candidate-rejected",
            "source_attempt": 3,
            "segment_ref": "volume-1.segment-1",
            "chapter_refs": ["chapter-1"],
            "editable_chapter_refs": ["chapter-1"],
            "preserved_chapter_refs": [],
            "required_removed_endpoints": {},
            "source_segment": {"chapters": [chapter]},
        }
    )
    patch = {
        "purpose": "林远请苏婉代替他核验未来报警",
        "scenes": chapter["scenes"],
        "handoff": chapter["handoff"],
    }

    with pytest.raises(ValueError, match="outside the frozen chapter cast"):
        merge_detail_recovery_patch(
            {"chapters": [patch]},
            source,
            selected_dossiers=[
                {"id": "subject-1", "name": "林远"},
                {"id": "subject-2", "name": "苏婉"},
            ],
        )


def test_submission_endpoint_distinguishes_intent_from_execution() -> None:
    assert "evidence_submission" not in dramatic_endpoints_for_text(
        "林远核对材料后决定次日提交证据。"
    )
    assert "evidence_submission" not in dramatic_endpoints_for_text(
        "林远整理证据，准备将材料提交给部门。"
    )
    assert "evidence_submission" in dramatic_endpoints_for_text(
        "林远当场将证据提交给部门，等待复核。"
    )


def test_duplicate_recovery_keeps_the_causal_endpoint_sequence_in_the_later_chapter() -> None:
    payload = _detail().model_dump(mode="json")
    for chapter in payload["chapters"][:2]:
        chapter["turn_refs"] = ["turn-1"]
        chapter["purpose"] = "向部门提交旧案证据，遭上级拒绝后决定公开材料"
        chapter["scenes"][0].update(
            {
                "objective": "向部门提交证据并申请重启调查",
                "conflict": "上级拒绝重启调查并威胁处分",
                "turn": "林远向部门提交旧案记录和录音证据",
                "result": "上级拒绝调查，林远决定公开证据",
            }
        )
    detail = DetailArtifact.model_validate(payload)
    feedback = DetailPreflightFeedback.model_validate(
        {
            "source_candidate_ref": "detail-candidate-rejected",
            "source_attempt": 1,
            "unique_blocker_count": 1,
            "omitted_blocker_count": 0,
            "blockers": [
                {
                    "code": "detail_duplicate_job",
                    "chapter_refs": ["chapter-1", "chapter-2"],
                    "evidence": "endpoints=['authority_refusal', 'evidence_submission', 'public_decision']",
                    "required_fix": "Each chapter must keep only its owned endpoint.",
                }
            ],
        }
    )

    first, first_feedback = build_detail_recovery_source(
        detail=detail,
        feedback=feedback,
        unit_id="volume-1.segment-1",
        provider_context={
            "material": {
                "scale_projection": {
                    "chapter_number_start": 1,
                    "chapter_target": 1,
                    "chapter_beats": [
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "核对证据后决定提交证据",
                        }
                    ],
                }
            }
        },
    )
    second, second_feedback = build_detail_recovery_source(
        detail=detail,
        feedback=feedback,
        unit_id="volume-1.segment-1",
        provider_context={
            "material": {
                "scale_projection": {
                    "chapter_number_start": 2,
                    "chapter_target": 1,
                    "chapter_beats": [
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "上级拒绝重启调查，林远决定公开证据",
                        }
                    ],
                }
            }
        },
    )

    assert first_feedback is not None
    assert second_feedback is None
    assert first.required_removed_endpoints == {
        "chapter-1": [
            "authority_refusal",
            "evidence_submission",
            "public_decision",
        ]
    }
    assert first.editable_chapter_refs == ["chapter-1"]
    assert second.required_removed_endpoints == {}


def test_evidence_source_change_requires_an_explicit_transfer() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][1]["scenes"][0]["result"] = (
        "警方提供报警录音，林远确认父亲身份掩护"
    )

    report = _report(DetailArtifact.model_validate(payload))

    assert "evidence_provenance_conflict" in {item.code for item in report.blockers}


def test_later_custody_does_not_create_a_second_clue_source() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0].update(
        {
            "place": "旧港观测站",
            "objective": "寻找纸质潮位记录",
            "turn": "林远在仪器台下发现纸质潮位记录",
            "result": "林远从旧港观测站取得纸质潮位记录并登记来源",
        }
    )
    payload["chapters"][1]["scenes"][0].update(
        {
            "place": "林远宿舍",
            "objective": "核验纸质潮位记录",
            "turn": "林远调取系统日志并比对纸质潮位记录",
            "result": "林远持有纸质潮位记录并确认潮位时间被修改",
        }
    )
    payload["chapters"][2]["scenes"][0]["result"] = (
        "林远公开纸质潮位记录并证明旧案责任。"
    )

    report = _report(DetailArtifact.model_validate(payload))
    clue = next(
        item
        for item in report.narrative_contracts.clues
        if item.label == "纸质潮位记录"
    )

    assert clue.source_labels == ["place:旧港观测站"]
    assert not any(
        item.code == "evidence_provenance_conflict"
        and "纸质潮位记录" in item.evidence
        for item in report.blockers
    )


def test_container_discovery_binds_the_clue_to_the_scene_place() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0].update(
        {
            "place": "旧港观测站",
            "objective": "寻找纸质潮位记录",
            "turn": "林远在仪器台下发现防水铁盒，内有几页纸质潮位记录",
            "result": "林远登记纸质潮位记录并带离现场",
        }
    )
    payload["chapters"][1]["scenes"][0]["result"] = "林远核验纸质潮位记录"
    payload["chapters"][2]["scenes"][0]["result"] = "林远公开纸质潮位记录"

    report = _report(DetailArtifact.model_validate(payload))
    clue = next(
        item
        for item in report.narrative_contracts.clues
        if item.label == "纸质潮位记录"
    )

    assert clue.source_labels == ["place:旧港观测站"]


def test_clue_label_drops_a_leading_object_particle() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["purpose"] = "找到纸质撤离记录"
    payload["chapters"][0]["scenes"][0]["turn"] = "林远找到纸质撤离记录"
    payload["chapters"][1]["handoff"] = "林远将纸质记录拍照存证"

    report = _report(DetailArtifact.model_validate(payload))
    labels = {item.label for item in report.narrative_contracts.clues}

    assert "将纸质记录" not in labels
    assert "纸质撤离记录" in labels


def test_cross_chapter_shorthand_inherits_the_nearest_specific_clue() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0].update(
        {
            "place": "市政档案室",
            "turn": "林远在档案柜中找到纸质撤离记录",
            "result": "林远取得纸质撤离记录并拍照存证",
        }
    )
    payload["chapters"][1]["scenes"][0]["result"] = "林远核验纸质记录中的签名"
    payload["chapters"][2]["scenes"][0]["result"] = "林远出示纸质记录获得证人确认"

    report = _report(DetailArtifact.model_validate(payload))
    labels = {item.label for item in report.narrative_contracts.clues}
    clue = next(
        item
        for item in report.narrative_contracts.clues
        if item.label == "纸质撤离记录"
    )

    assert "纸质记录" not in labels
    assert clue.source_labels == ["档案室"]
    assert "chapter-3" in clue.payoff_refs


def test_fact_inside_an_acquired_record_inherits_the_scene_source() -> None:
    spine_payload = _spine().model_dump(mode="json")
    spine_payload["turns"][0]["cause"] += "，父亲名字出现在原始名单中"
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0].update(
        {
            "place": "市政档案室",
            "turn": "林远在封存柜中找到纸质撤离记录",
            "result": "纸质记录显示父亲名字出现在原始名单中",
        }
    )
    payload["chapters"][1]["scenes"][0]["result"] = "林远核验原始名单中的签名"
    payload["chapters"][2]["scenes"][0]["result"] = "林远公开原始名单并证明旧案责任"

    report = _report(
        DetailArtifact.model_validate(payload),
        spine=StorySpineArtifact.model_validate(spine_payload),
    )
    clue = next(
        item
        for item in report.narrative_contracts.clues
        if item.label == "原始名单"
    )

    assert clue.source_labels == ["档案室"]
    assert not any(
        item.code == "clue_source_missing" and "原始名单" in item.evidence
        for item in report.blockers
    )


def test_generic_hidden_place_does_not_override_the_scene_source() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0].update(
        {
            "place": "旧港观测站",
            "turn": "林远在旧港观测站找到旧港日记",
            "result": "林远从隐蔽处取出旧港日记并保管",
        }
    )
    payload["chapters"][1]["scenes"][0]["result"] = "林远核验旧港日记中的签名"
    payload["chapters"][2]["scenes"][0]["result"] = "林远公开旧港日记并证明旧案责任"

    report = _report(DetailArtifact.model_validate(payload))
    clue = next(
        item
        for item in report.narrative_contracts.clues
        if item.label == "旧港日记"
    )

    assert clue.source_labels == ["place:旧港观测站"]
    assert "place:隐蔽" not in clue.source_labels


def test_playback_action_is_not_part_of_a_clue_label() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = "林远从档案室取得旧港日记并保管"
    payload["chapters"][1]["scenes"][0]["result"] = "林远用手机播放旧港日记录音并核验内容"
    payload["chapters"][2]["scenes"][0]["result"] = "林远公开旧港日记并证明旧案责任"

    report = _report(DetailArtifact.model_validate(payload))
    labels = {item.label for item in report.narrative_contracts.clues}

    assert "手机播放旧港日记" not in labels
    assert "手机播放旧港日记录音" not in labels
    assert "旧港日记" in labels
    assert "旧港日记录音" in labels


def test_using_a_key_to_open_its_lock_verifies_and_pays_off_the_key() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["result"] = "林远从档案室取得灯塔钥匙并保管"
    payload["chapters"][1]["scenes"][0]["result"] = "林远用灯塔钥匙打开旧港灯塔"
    payload["chapters"][2]["scenes"][0]["result"] = "林远公开灯塔内的报警录音并承担处分"

    report = _report(DetailArtifact.model_validate(payload))
    clue = next(
        item
        for item in report.narrative_contracts.clues
        if item.label == "灯塔钥匙"
    )

    assert "chapter-2" in clue.verification_refs
    assert "chapter-2" in clue.payoff_refs
    assert not any(
        item.code == "clue_lifecycle_incomplete" and "灯塔钥匙" in item.evidence
        for item in report.blockers
    )


def test_clue_identity_drops_an_inquiry_action_prefix() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0]["turn"] = "林远找到一本日记"
    payload["chapters"][1]["scenes"][0]["turn"] = "林远向旧案证人询问日记中的地址"
    payload["chapters"][2]["scenes"][0]["turn"] = "林远根据日记前往旧址"

    report = _report(DetailArtifact.model_validate(payload))
    labels = {item.label for item in report.narrative_contracts.clues}

    assert "旧案证人询问日记" not in labels
    assert "根据日记" not in labels
    assert "日记" in labels


def test_clue_identity_drops_custody_and_reading_action_prefixes() -> None:
    payload = _detail().model_dump(mode="json")
    first_scene = payload["chapters"][0]["scenes"][0]
    first_scene.update(
        {
            "place": "陈伯年家",
            "objective": "获取林远的日记",
            "conflict": "陈伯年只记得林远的日记藏在旧港灯塔里",
            "turn": "林远与陈伯年约定前往旧港灯塔",
            "result": "林远获得日记位置线索，但尚未取得日记",
        }
    )
    second_scene = payload["chapters"][1]["scenes"][0]
    second_scene.update(
        {
            "place": "废弃观测站",
            "turn": "林远从暗格中取出日记，对手抢夺日记，林远抢回并保住日记",
            "result": "林远在废弃观测站取得日记并核验内容",
        }
    )
    third_scene = payload["chapters"][2]["scenes"][0]
    third_scene.update(
        {
            "turn": "林远将日记转交给警方，随后在拘留中研读日记",
            "result": "警方归还日记后，林远公开日记并证明旧案责任",
        }
    )

    report = _report(DetailArtifact.model_validate(payload))
    clues = {item.label: item for item in report.narrative_contracts.clues}

    assert "抢夺日记" not in clues
    assert "保住日记" not in clues
    assert "拘留中研读日记" not in clues
    assert clues["林远日记"].source_labels == ["place:旧港灯塔", "place:废弃观测站"]
    blocker = next(
        item
        for item in report.blockers
        if item.code == "evidence_provenance_conflict" and "日记" in item.evidence
    )
    assert "后续转交" in blocker.evidence
    assert "不能解释独立来源地点" in blocker.evidence


def test_distinct_direct_acquisition_keeps_the_provenance_conflict() -> None:
    payload = _detail().model_dump(mode="json")
    payload["chapters"][0]["scenes"][0].update(
        {
            "place": "旧港观测站",
            "turn": "林远在仪器台下发现纸质潮位记录",
            "result": "林远从旧港观测站取得纸质潮位记录并登记来源",
        }
    )
    payload["chapters"][1]["scenes"][0].update(
        {
            "place": "市政档案室",
            "turn": "林远在封存柜中发现纸质潮位记录",
            "result": "林远从市政档案室取得纸质潮位记录并登记来源",
        }
    )

    report = _report(DetailArtifact.model_validate(payload))

    assert any(
        item.code == "evidence_provenance_conflict"
        and "纸质潮位记录" in item.evidence
        for item in report.blockers
    )


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
