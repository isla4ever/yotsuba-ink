from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.phase32_route_artifacts import (
    CharacterBibleArtifact,
    CharacterRecord,
    ScreenplayBriefArtifact,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderRequest,
    Phase32ProviderResponse,
)
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.phase32_epistemic_context import (
    Phase32EpistemicContext,
    compile_phase32_cast_epistemic_context,
)
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE
from tests.test_phase32_route_graph import _definition


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures/phase32_wave22_cast_claim_custody.json"
)


class RecordingGateway:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests: list[Phase32ProviderRequest] = []

    async def generate(self, request, *, binding) -> Phase32ProviderResponse:
        self.requests.append(request)
        return Phase32ProviderResponse(payload=self.payload)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_wave21_claims_compile_to_traceable_non_canon_custody() -> None:
    fixture = _fixture()
    inputs = fixture["inputs"]
    brief = fixture["brief"]
    brief_digest = canonical_digest(brief)
    context = compile_phase32_cast_epistemic_context(
        creation_route_id="screenplay_sample",
        context_policy_ref="context.screenplay.cast.v2",
        inputs=inputs,
        inputs_digest=canonical_digest(inputs),
        upstream_artifacts={
            "brief": {
                "artifact_ref": f"p32-brief-committed-{brief_digest}",
                "artifact_kind": "screenplay_brief",
                "payload": brief,
                "payload_digest": brief_digest,
            }
        },
    )

    assert context is not None
    by_path = {entry.source_path: entry for entry in context.sources}
    assert {
        path: by_path[path].status
        for path in fixture["expected_status_by_path"]
    } == fixture["expected_status_by_path"]
    assert all(not entry.canon_authority for entry in context.sources)
    assert by_path["upstream_artifacts.brief.payload.visible_conflict"].value_digest == (
        canonical_digest(brief["visible_conflict"])
    )
    assert "legal liability" in by_path[
        "upstream_artifacts.brief.payload.visible_conflict"
    ].prohibited_promotion
    assert "embedded open questions" in by_path[
        "upstream_artifacts.brief.payload.ending_effect"
    ].prohibited_promotion

    payload = context.model_dump(mode="json")
    payload["sources"][0]["status"] = "open_question"
    with pytest.raises(ValidationError, match="digest"):
        Phase32EpistemicContext.model_validate(payload)


def test_cast_v1_frozen_context_remains_unchanged() -> None:
    assert compile_phase32_cast_epistemic_context(
        creation_route_id="screenplay_sample",
        context_policy_ref="context.screenplay.cast.v1",
        inputs={"creative_intent": "旧 Run 冻结输入"},
        inputs_digest=canonical_digest({"creative_intent": "旧 Run 冻结输入"}),
        upstream_artifacts={},
    ) is None


@pytest.mark.parametrize(
    ("route_id", "context_policy_ref", "upstream_artifacts", "path", "status"),
    (
        (
            "short_novel",
            "context.short_novel.cast.v2",
            {
                "story_map": {
                    "artifact_ref": "p32-story-map-committed-fixture",
                    "artifact_kind": "story_map",
                    "payload": {
                        "opening_state": "记者只相信公开档案。",
                        "story_question": "谁在修改城市记忆？",
                        "anchors": [{"anchor_ref": "anchor_1"}],
                        "ending_state": "证据公开但责任仍待追查。",
                        "open_questions": ["主管是否参与篡改？"],
                    },
                }
            },
            "upstream_artifacts.story_map.payload.open_questions",
            "open_question",
        ),
        (
            "long_novel",
            "context.long_novel.cast.v2",
            {
                "book_architecture": {
                    "artifact_ref": "p32-book-architecture-committed-fixture",
                    "artifact_kind": "book_architecture",
                    "payload": {
                        "book_promise": "追查城市档案背后的长期权力关系。",
                        "ending_conditions": ["篡改链被公开。"],
                        "parts": [
                            {
                                "part_ref": "part_1",
                                "dramatic_question": "谁控制签名链？",
                                "unresolved_obligations": ["主管责任仍未证实。"],
                            }
                        ],
                    },
                }
            },
            "upstream_artifacts.book_architecture.payload.parts",
            "accepted_plan",
        ),
    ),
)
def test_all_route_cast_contexts_preserve_explicit_unknowns(
    route_id,
    context_policy_ref,
    upstream_artifacts,
    path,
    status,
) -> None:
    inputs = {"creative_intent": "保留未决问题，不提前确定罪责。"}
    context = compile_phase32_cast_epistemic_context(
        creation_route_id=route_id,
        context_policy_ref=context_policy_ref,
        inputs=inputs,
        inputs_digest=canonical_digest(inputs),
        upstream_artifacts=upstream_artifacts,
    )

    assert context is not None
    entry = next(source for source in context.sources if source.source_path == path)
    assert entry.status == status
    assert "unresolved" in entry.prohibited_promotion.lower()


@pytest.mark.asyncio
async def test_route_driver_injects_cast_custody_without_real_provider(tmp_path: Path) -> None:
    fixture = _fixture()
    current_brief = {"title": "封锁线之前", **fixture["brief"]}
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "artifacts")
    brief = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="screenplay_sample",
        stage_id="brief",
        artifact=ScreenplayBriefArtifact.model_validate(current_brief),
    )
    state = initial_route_run_state(definition).model_copy(
        update={"artifact_refs": {"brief": brief.artifact_ref}}
    )
    cast = CharacterBibleArtifact(
        characters=(
            CharacterRecord(
                subject_ref="lin_wan",
                display_name="林晚",
                role="在封锁规程与救援选择之间作决定的信号员",
                desire="在倒计时内确认求救来源并作出可见选择",
                stakes="证人可能受伤，她也可能失去职位",
                constraints=("操作会留下不可撤销的系统日志",),
                voice="短句、克制，先报告可见事实",
                arc_scope="从服从规程转向承担一次可见违规选择",
            ),
        )
    )
    gateway = RecordingGateway(cast.model_dump(mode="json"))
    driver = Phase32RouteDriver(store, gateway)

    await driver.generate_stage(
        definition=definition,
        state=state,
        stage=definition.stage("cast"),
    )

    assert len(gateway.requests) == 1
    request = gateway.requests[0]
    custody = request.context["epistemic_custody"]
    assert custody["context_policy_ref"] == "context.screenplay.cast.v2"
    assert custody["contract_digest"]
    assert "epistemic_custody" in request.rendered_prompt
    assert "开放问题、怀疑、未来结果和风险不得写成人物事实" in request.rendered_prompt
