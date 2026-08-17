from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    ChapterSceneGenerationRequest,
    ChapterReviewRequest,
    ChapterReviewResult,
    CoverImageRequest,
    PlainTextProviderResult,
    ProposalGenerationRequest,
    ProviderOperationError,
    FrozenNarrativeProviderGateway,
    StageGenerationRequest,
    StructuredProviderResult,
    compile_provider_input,
)
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from tests.phase27_bindings import cover_asset_binding, provider_binding


def brief() -> dict[str, Any]:
    return {
        "title": "雾港旧声", "premise": "修复师追查母带", "promise": "真相伴随代价", "world_rules": ["广播覆盖记忆"],
        "theme": "真相的代价", "ending_promise": "真相公开", "voice": "克制", "length_envelope": {"word_target_soft": 10000},
    }


class CapturingTextProvider(TextProvider):
    name = "capturing"

    def __init__(self, *, structured: dict[str, Any] | None = None) -> None:
        self.structured = structured or brief()
        self.calls: list[tuple[str, str]] = []

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        self.calls.append((task_name, prompt))
        return "第一章正文。"

    async def generate_strict_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((task_name, prompt))
        return self.structured


class CapturingImageProvider(ImageProvider):
    name = "image"

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> GeneratedImage:
        return GeneratedImage(content=b"image", mime_type="image/png", provider_asset_id="asset-1")


def binding(stage_id: str = "brief") -> ProviderBinding:
    return provider_binding(
        stage_id,
        provider_profile_id="provider-primary",
        model="model-frozen",
        max_tokens=1000,
    )


def chapter_context_manifest() -> dict[str, Any]:
    values = {
        "detail.chapter": "chapter script",
        "cast.subjects": "cast",
        "volume.contract": "volume",
        "brief.world_rules": "rules",
        "scene.execution": "beats",
    }
    snippets = [
        {
            "ref": ref,
            "purpose": ref,
            "text": text,
            "source_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
        for ref, text in values.items()
    ]
    payload: dict[str, Any] = {
        "task": "chapter-1",
        "required": list(values),
        "optional": [],
        "forbidden": ["full_canon"],
        "snippets": snippets,
        "budget": {
            "input_chars": sum(len(text) for text in values.values()),
            "output_tokens": 100,
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    payload["manifest_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return payload


def gateway(
    text: TextProvider,
    *,
    image: ImageProvider | None = None,
) -> FrozenNarrativeProviderGateway:
    return FrozenNarrativeProviderGateway(
        lambda secret_ref: f"saved-secret-for-{secret_ref}",
        text_provider_factory=lambda frozen, secret: text,
        image_provider_factory=lambda frozen, secret: image or CapturingImageProvider(),
    )


@pytest.mark.asyncio
async def test_stage_gateway_uses_exact_frozen_binding_and_current_contract() -> None:
    provider = CapturingTextProvider()
    result = await gateway(provider).generate_stage(StageGenerationRequest(operation_key="run:brief:1", run_id="run", stage_id="brief", attempt=1, binding=binding(), context={"target": "brief", "material": {"project_brief": {}, "length_envelope": {}}}))
    assert result.payload["title"] == "雾港旧声"
    assert provider.calls[0][0] == "brief"


@pytest.mark.asyncio
async def test_stage_gateway_rejects_invalid_json_shape_without_repair() -> None:
    provider = CapturingTextProvider(structured={"title": "missing"})
    with pytest.raises(ProviderOperationError):
        await gateway(provider).generate_stage(StageGenerationRequest(operation_key="run:brief:1", run_id="run", stage_id="brief", attempt=1, binding=binding(), context={"target": "brief", "material": {"project_brief": {}, "length_envelope": {}}}))


@pytest.mark.asyncio
async def test_schema_digest_drift_stops_before_secret_or_provider_resolution() -> None:
    frozen = binding()
    structured_tasks = dict(frozen.structured_tasks)
    structured_tasks["brief"] = structured_tasks["brief"].model_copy(
        update={"schema_digest": "0" * 64}
    )
    drifted = frozen.model_copy(update={"structured_tasks": structured_tasks})
    secret_calls: list[str] = []
    factory_calls: list[tuple[ProviderBinding, str]] = []

    def secret_resolver(secret_ref: str) -> str:
        secret_calls.append(secret_ref)
        return "offline-secret"

    def provider_factory(
        provider_binding: ProviderBinding,
        secret: str,
    ) -> TextProvider:
        factory_calls.append((provider_binding, secret))
        return CapturingTextProvider()

    frozen_gateway = FrozenNarrativeProviderGateway(
        secret_resolver,
        text_provider_factory=provider_factory,
    )

    with pytest.raises(ProviderOperationError) as captured:
        await frozen_gateway.generate_stage(
            StageGenerationRequest(
                operation_key="run:brief:drift",
                run_id="run",
                stage_id="brief",
                attempt=1,
                binding=drifted,
                context={
                    "target": "brief",
                    "material": {"project_brief": {}, "length_envelope": {}},
                },
            )
        )

    assert captured.value.diagnostic["code"] == "schema_digest_mismatch"
    assert secret_calls == []
    assert factory_calls == []


@pytest.mark.asyncio
async def test_chapter_gateway_is_plain_text_and_never_parses_json() -> None:
    provider = CapturingTextProvider()
    result = await gateway(provider).generate_chapter_scene(ChapterSceneGenerationRequest(operation_key="run:chapter-1:scene-1:1", run_id="run", chapter_id="chapter-1", chapter_number=1, chapter_attempt=1, scene_index=1, scene_attempt=1, binding=binding("text"), context={"target": "text.scene", "material": {"chapter_context_manifest": chapter_context_manifest()}}))
    assert isinstance(result, PlainTextProviderResult)
    assert result.content == "第一章正文。"
    assert provider.calls[0][0] == "text"


@pytest.mark.asyncio
async def test_review_gateway_locks_role_to_the_requested_lane() -> None:
    provider = CapturingTextProvider(structured=ChapterReviewResult(role="continuity").model_dump(mode="json"))
    request = ChapterReviewRequest(operation_key="run:review", run_id="run", chapter_id="chapter-1", chapter_version_id="chapter-1-v1", role="continuity", required=True, attempt=1, binding=binding("text"), context={"target": "text.review", "material": {"chapter": {"content": "正文"}}})
    result = await gateway(provider).review_chapter(request)
    assert result.payload["role"] == "continuity"


@pytest.mark.asyncio
async def test_character_review_finding_without_a_frozen_subject_is_rejected() -> None:
    provider = CapturingTextProvider(
        structured={
            "role": "character",
            "available": True,
            "findings": [
                {"code": "early_appearance", "severity": "blocking", "claim": "提前出场", "evidence": "王建国走进值班室", "subject_ids": []}
            ],
        }
    )
    request = ChapterReviewRequest(
        operation_key="run:review",
        run_id="run",
        chapter_id="chapter-1",
        chapter_version_id="chapter-1-v1",
        role="character",
        required=True,
        attempt=1,
        binding=binding("text"),
        context={
            "target": "text.review",
            "material": {
                "chapter": {"content": "王建国走进值班室"},
                "appearance_policy": {"eligible_subject_ids": ["subject-1"], "not_yet_eligible_subject_ids": ["subject-2"]},
            },
        },
    )
    with pytest.raises(ProviderOperationError):
        await gateway(provider).review_chapter(request)


@pytest.mark.asyncio
async def test_proposal_gateway_validates_narrow_json_contract() -> None:
    provider = CapturingTextProvider(structured={"proposals": [{"demand_key": "demand-a", "subject_mode": "actor", "narrative_role": "protagonist", "function": "取证", "required_change": "作证", "irreducibility": "必须由主角承担公开证言的不可逆后果。", "active_turn_refs": ["turn-1"]}]})
    result = await gateway(provider).generate_proposal(ProposalGenerationRequest(operation_key="run:proposal", run_id="run", stage_id="cast", proposal_type="role_demand", attempt=1, binding=binding("cast"), context={"target": "cast", "material": {"scale_plan": {"cast_recommended_range": [1, 11], "cast_hard_max": 11}}}))
    assert result.payload["proposals"][0]["demand_key"] == "demand-a"


@pytest.mark.asyncio
async def test_detail_layout_gateway_uses_its_frozen_strict_contract() -> None:
    provider = CapturingTextProvider(
        structured={
            "status": "sufficient",
            "diagnosis": "",
            "volumes": [
                {
                    "volume_ref": "volume-1",
                    "chapters": [
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "让证据公开造成不可逆后果",
                            "length_hint": "standard",
                        }
                    ],
                }
            ],
        }
    )
    result = await gateway(provider).generate_proposal(
        ProposalGenerationRequest(
            operation_key="run:detail_layout:proposal:1",
            run_id="run",
            stage_id="detail",
            proposal_type="detail_layout",
            attempt=1,
            binding=binding("detail"),
            context={"target": "detail", "material": {"chapter_slots": [{"slot_index": 1}]}},
        )
    )

    assert result.payload["volumes"][0]["chapters"][0]["dramatic_job"]
    assert provider.calls[0][0] == "detail_layout.proposal"


@pytest.mark.asyncio
async def test_image_gateway_keeps_explicit_profile_and_binding() -> None:
    provider = CapturingImageProvider()
    request = CoverImageRequest(operation_key="run:cover:image:1", run_id="run", candidate_index=1, generation_attempt=1, binding=cover_asset_binding(provider_profile_id="image-primary", model="image-model"), prompt="封面")
    image = await gateway(CapturingTextProvider(), image=provider).generate_cover_image(request)
    assert image.provider_asset_id == "asset-1"


def test_provider_input_compiler_covers_every_provider_operation_without_secrets() -> None:
    text = binding("text")
    requests = [
        StageGenerationRequest(operation_key="run:brief:1", run_id="run", stage_id="brief", attempt=1, binding=binding("brief"), context={"target": "brief", "material": {}}),
        StageGenerationRequest(operation_key="run:cover:1", run_id="run", stage_id="cover", attempt=1, binding=binding("cover"), context={"target": "cover", "material": {}}),
        ProposalGenerationRequest(operation_key="run:proposal:1", run_id="run", stage_id="cast", proposal_type="role_demand", attempt=1, binding=binding("cast"), context={"target": "cast", "material": {"scale_plan": {"cast_recommended_range": [1, 11], "cast_hard_max": 11}}}),
        ProposalGenerationRequest(operation_key="run:detail_layout:proposal:1", run_id="run", stage_id="detail", proposal_type="detail_layout", attempt=1, binding=binding("detail"), context={"target": "detail", "material": {"chapter_slots": [{"slot_index": 1}]}}),
        ChapterSceneGenerationRequest(
            operation_key="run:chapter-1:scene-1:generate:2.1",
            run_id="run",
            chapter_id="chapter-1",
            chapter_number=1,
            chapter_attempt=2,
            scene_index=1,
            scene_attempt=1,
            binding=text,
            context={"target": "text.scene", "material": {"chapter_context_manifest": chapter_context_manifest()}},
        ),
        ChapterReviewRequest(
            operation_key="run:chapter-1:review:v2:continuity",
            run_id="run",
            chapter_id="chapter-1",
            chapter_version_id="chapter-1-v2",
            role="continuity",
            required=True,
            attempt=2,
            binding=text,
            context={"target": "text.review", "material": {"chapter": {"content": "正文"}}},
        ),
        ChapterEvidenceRequest(
            operation_key="run:chapter-1:evidence:v2",
            run_id="run",
            chapter_id="chapter-1",
            chapter_version_id="chapter-1-v2",
            attempt=2,
            content="第一段证据。第二段证据。",
            binding=text,
        ),
        CoverImageRequest(
            operation_key="run:cover:image:1",
            run_id="run",
            candidate_index=1,
            generation_attempt=1,
            binding=cover_asset_binding(provider_profile_id="image-primary", model="image-model"),
            prompt="封面图像提示",
        ),
    ]

    snapshots = [compile_provider_input(request) for request in requests]
    assert {snapshot.task_name for snapshot in snapshots} == {
        "brief",
        "cover",
        "role_demand.proposal",
        "detail_layout.proposal",
        "text.scene",
        "text.review",
        "text.evidence",
        "cover.image",
    }
    assert snapshots[4].attempt == 1
    assert snapshots[5].chapter_version_id == "chapter-1-v2"
    assert snapshots[6].structured_context["evidence_candidates"]
    encoded = json.dumps(
        [snapshot.model_dump(mode="json") for snapshot in snapshots],
        ensure_ascii=False,
        sort_keys=True,
    )
    assert "secret_ref" not in encoded
    assert "authorization" not in encoded.lower()
    assert not [
        path
        for snapshot in snapshots
        for path in _forbidden_header_paths(snapshot.provider_binding)
    ]


def _forbidden_header_paths(
    value: object,
    path: tuple[str, ...] = (),
) -> list[str]:
    if isinstance(value, dict):
        matches: list[str] = []
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            current_path = (*path, key)
            if (
                normalized in {"header", "headers"}
                or normalized.endswith("_header")
                or normalized.endswith("_headers")
            ):
                matches.append(".".join(current_path))
            matches.extend(_forbidden_header_paths(item, current_path))
        return matches
    if isinstance(value, list):
        return [
            match
            for index, item in enumerate(value)
            for match in _forbidden_header_paths(item, (*path, str(index)))
        ]
    return []
