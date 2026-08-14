from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterDossierBatch,
    CharacterRelationBatch,
    ContextManifest,
    CoverBrief,
    DetailSegmentArtifact,
    RoleDemandProposalBatch,
    StageId,
    StorySpineDraftArtifact,
    VolumeArchitectureDraftArtifact,
    VolumeBoundaryProposalBatch,
)
from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider
from novel_workflow.providers.frozen_contract import schema_digest
from novel_workflow.providers.model_capabilities import resolve_request_policy
from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
from novel_workflow.providers.openai_image import OpenAICompatibleImageProvider
from novel_workflow.providers.structured_schema import structured_format_decision
from novel_workflow.providers.structured_tasks import contract_for_task
from novel_workflow.providers.usage import provider_usage_snapshot
from novel_workflow.runtime.graph.evidence_candidates import (
    build_chapter_evidence_candidates,
)
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding
from novel_workflow.output_contracts.provider_tasks import (
    ChapterEvidenceResult,
    ChapterReviewResult,
    EvidenceClaimProposal,
    ReviewFinding,
)

class ProviderOperationError(RuntimeError):
    """A frozen Provider operation failed and must not silently reroute."""

    def __init__(
        self,
        message: str,
        *,
        operation_key: str = "",
        usage: dict[str, int] | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.operation_key = operation_key
        self.usage = usage or {}
        self.diagnostic = diagnostic or {}

    @classmethod
    def for_operation(
        cls,
        operation_key: str,
        error: Exception | str,
    ) -> "ProviderOperationError":
        return cls(
            str(error),
            operation_key=operation_key,
            usage=getattr(error, "usage", {}),
            diagnostic=getattr(error, "diagnostic", {}),
        )


class StructuredProviderResult(BaseModel):
    """One strict Provider response plus its non-Artifact receipt metadata."""

    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
    usage: dict[str, int] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)


class PlainTextProviderResult(BaseModel):
    """One complete prose response; chapter generation never parses JSON."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    usage: dict[str, int] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)


class StageGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    stage_id: StageId
    attempt: int = Field(ge=1)
    binding: ProviderBinding
    context: dict[str, Any]


class ProposalGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    proposal_type: Literal["role_demand", "cast_relation", "volume_boundary"]
    binding: ProviderBinding
    context: dict[str, Any]


class ChapterGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    chapter_id: str
    chapter_number: int = Field(ge=1)
    binding: ProviderBinding
    context: dict[str, Any]


class ChapterReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    chapter_id: str
    chapter_version_id: str
    role: str
    required: bool
    binding: ProviderBinding
    context: dict[str, Any]


class ChapterEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    chapter_id: str
    chapter_version_id: str
    content: str = Field(min_length=1)
    binding: ProviderBinding


class CoverImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    candidate_index: int = Field(ge=1, le=4)
    generation_attempt: int = Field(ge=1)
    binding: CoverAssetBinding
    prompt: str = Field(min_length=1, max_length=6000)


class NarrativeProviderGateway(Protocol):
    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult: ...

    async def generate_chapter(self, request: ChapterGenerationRequest) -> PlainTextProviderResult: ...

    async def generate_proposal(self, request: ProposalGenerationRequest) -> StructuredProviderResult: ...

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage: ...

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult: ...

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult: ...


class FrozenNarrativeProviderGateway:
    """Strict vNext adapter built only from a Run's executable Provider snapshots.

    LangGraph owns control flow. This adapter owns one network call and has no
    retry, alias, schema conversion, or alternate Provider behavior.
    """

    def __init__(
        self,
        secret_resolver: Callable[[str], str | None],
        *,
        text_provider_factory: Callable[[ProviderBinding, str], TextProvider] | None = None,
        image_provider_factory: Callable[[CoverAssetBinding, str], ImageProvider] | None = None,
    ) -> None:
        self.secret_resolver = secret_resolver
        self.text_provider_factory = text_provider_factory or _build_text_provider
        self.image_provider_factory = image_provider_factory or _build_image_provider

    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        schema = _schema_for_stage(request.stage_id)
        response = await self._structured(
            request.binding,
            request.operation_key,
            request.stage_id,
            request.context,
            schema,
        )
        try:
            _validate_stage_payload(request.stage_id, response.payload)
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=response.usage,
                diagnostic=response.diagnostic,
            ) from exc
        return response

    async def generate_chapter(self, request: ChapterGenerationRequest) -> PlainTextProviderResult:
        provider = self._text_provider(request.binding)
        prompt = _render_text_prompt(request.binding, request.context)
        try:
            content = await provider.generate_text(
                prompt,
                task_name="text",
                context={"idempotency_key": request.operation_key},
            )
            result = PlainTextProviderResult(
                content=content,
                usage=provider_usage_snapshot(provider),
                diagnostic=_provider_diagnostic(provider),
            )
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=provider_usage_snapshot(provider),
                diagnostic=_provider_diagnostic(provider),
            ) from exc
        if not result.content.strip():
            raise ProviderOperationError(
                "Chapter Provider returned empty prose",
                operation_key=request.operation_key,
                usage=result.usage,
                diagnostic=result.diagnostic,
            )
        return result

    async def generate_proposal(self, request: ProposalGenerationRequest) -> StructuredProviderResult:
        schema, model = _schema_for_proposal(request.proposal_type)
        response = await self._structured(
            request.binding,
            request.operation_key,
            f"{request.proposal_type}.proposal",
            request.context,
            schema,
        )
        try:
            model.model_validate(response.payload)
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=response.usage,
                diagnostic=response.diagnostic,
            ) from exc
        return response

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage:
        provider = self._image_provider(request.binding)
        return await provider.generate_cover(
            request.prompt,
            context={
                "idempotency_key": request.operation_key,
                "model": request.binding.model,
                "size": request.binding.size,
                "quality": request.binding.quality,
                "timeout_seconds": request.binding.timeout_seconds,
            },
        )

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        response = await self._structured(
            request.binding,
            request.operation_key,
            "text.review",
            request.context,
            _schema_for_review_role(request.role),
            frozen_task_name=f"text.review.{request.role}",
        )
        try:
            result = ChapterReviewResult.model_validate(response.payload)
            validate_review_result_contract(request, result)
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=response.usage,
                diagnostic=response.diagnostic,
            ) from exc
        return response

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult:
        candidates = build_chapter_evidence_candidates(request.content)
        response = await self._structured(
            request.binding,
            request.operation_key,
            "text.evidence",
            {
                "chapter_id": request.chapter_id,
                "chapter_version_id": request.chapter_version_id,
                "evidence_candidates": [
                    candidate.prompt_payload() for candidate in candidates
                ],
            },
            contract_for_task("text.evidence").schema,
        )
        ChapterEvidenceResult.model_validate(response.payload)
        return response

    async def _structured(
        self,
        binding: ProviderBinding,
        operation_key: str,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any],
        *,
        frozen_task_name: str = "",
    ) -> StructuredProviderResult:
        frozen_task_name = frozen_task_name or task_name
        _validate_frozen_structured_task(
            binding,
            frozen_task_name=frozen_task_name,
            provider_task_name=task_name,
            schema=schema,
        )
        provider = self._text_provider(binding)
        prompt = _render_prompt(binding, task_name, context, schema)
        try:
            result = await provider.generate_strict_structured(
                prompt,
                task_name=task_name,
                context={"idempotency_key": operation_key},
                schema=schema,
            )
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=operation_key,
                usage=provider_usage_snapshot(provider),
                diagnostic=_provider_diagnostic(provider),
            ) from exc
        if not isinstance(result, dict):
            raise ProviderOperationError(
                "Provider structured result must be a JSON object",
                operation_key=operation_key,
                usage=provider_usage_snapshot(provider),
                diagnostic=_provider_diagnostic(provider),
            )
        return StructuredProviderResult(
            payload=result,
            usage=provider_usage_snapshot(provider),
            diagnostic=_provider_diagnostic(provider),
        )

    def _text_provider(self, binding: ProviderBinding) -> TextProvider:
        secret = self._secret(binding.provider_config.secret_ref)
        return self.text_provider_factory(binding, secret)

    def _image_provider(self, binding: CoverAssetBinding) -> ImageProvider:
        secret = self._secret(binding.provider_config.secret_ref)
        return self.image_provider_factory(binding, secret)

    def _secret(self, secret_ref: str) -> str:
        value = self.secret_resolver(secret_ref)
        if not isinstance(value, str) or not value.strip():
            raise ProviderOperationError(
                "Frozen Provider secret is unavailable",
                diagnostic={"code": "secret_unavailable"},
            )
        return value.strip()


def _build_text_provider(binding: ProviderBinding, secret: str) -> TextProvider:
    config = binding.provider_config
    return OpenAICompatibleTextProvider(
        base_url=config.base_url,
        api_key=secret,
        model=binding.model,
        temperature=binding.temperature,
        max_tokens=binding.max_tokens,
        top_p=binding.top_p,
        timeout_seconds=binding.timeout_seconds,
        template_id=binding.template_id,
        template=binding.provider_template,
    )


def _build_image_provider(binding: CoverAssetBinding, secret: str) -> ImageProvider:
    config = binding.provider_config
    return OpenAICompatibleImageProvider(
        base_url=config.base_url,
        api_key=secret,
        model=binding.model,
        timeout_seconds=binding.timeout_seconds,
        template_id=binding.template_id,
        template=binding.provider_template,
    )


def _validate_frozen_structured_task(
    binding: ProviderBinding,
    *,
    frozen_task_name: str,
    provider_task_name: str,
    schema: dict[str, Any],
) -> None:
    frozen = binding.structured_tasks.get(frozen_task_name)
    if frozen is None:
        raise ProviderOperationError(
            f"Frozen structured task is missing: {frozen_task_name}",
            diagnostic={"code": "structured_task_missing"},
        )
    if frozen.schema_digest != schema_digest(schema):
        raise ProviderOperationError(
            f"Structured schema changed after Run creation: {frozen_task_name}",
            diagnostic={"code": "schema_digest_mismatch"},
        )
    policy = resolve_request_policy(
        binding.provider_template,
        model=binding.model,
        task_name=provider_task_name,
    )
    decision = (
        structured_format_decision(
            policy,
            task_name=provider_task_name,
            schema=schema,
        )
        if binding.provider_template.supports_response_format
        else None
    )
    effective_mode = decision.effective_mode if decision is not None else "prompt_only"
    if effective_mode != frozen.effective_mode:
        raise ProviderOperationError(
            f"Structured output mode changed after Run creation: {frozen_task_name}",
            diagnostic={"code": "structured_mode_mismatch"},
        )


def _provider_diagnostic(provider: Any) -> dict[str, Any]:
    value = getattr(provider, "last_response_diagnostic", None)
    return dict(value) if isinstance(value, dict) else {}


def _schema_for_stage(stage_id: str) -> dict[str, Any]:
    return contract_for_task(stage_id).schema


def _schema_for_proposal(
    proposal_type: Literal["role_demand", "cast_relation", "volume_boundary"],
) -> tuple[dict[str, Any], type[BaseModel]]:
    if proposal_type == "role_demand":
        return contract_for_task("role_demand.proposal").schema, RoleDemandProposalBatch
    if proposal_type == "cast_relation":
        return contract_for_task("cast_relation.proposal").schema, CharacterRelationBatch
    return contract_for_task("volume_boundary.proposal").schema, VolumeBoundaryProposalBatch


def _schema_for_review_role(role: str) -> dict[str, Any]:
    return contract_for_task(f"text.review.{role}").schema


def _validate_stage_payload(stage_id: str, payload: dict[str, Any]) -> None:
    from novel_workflow.output_contracts.artifacts_vnext import ARTIFACT_MODELS

    if stage_id == "cover":
        CoverBrief.model_validate(payload)
        return
    if stage_id == "cast":
        CharacterDossierBatch.model_validate(payload)
        return
    if stage_id == "spine":
        StorySpineDraftArtifact.model_validate(payload)
        return
    if stage_id == "volumes":
        VolumeArchitectureDraftArtifact.model_validate(payload)
        return
    if stage_id == "detail":
        DetailSegmentArtifact.model_validate(payload)
        return
    ARTIFACT_MODELS[stage_id].model_validate(payload)


def _render_prompt(
    binding: ProviderBinding,
    task_name: str,
    context: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    template = binding.prompt_template.strip()
    prefix = f"{template}\n\n" if template else ""
    revision_contract = _revision_contract(context)
    proposal_contract = _proposal_contract(task_name)
    review_contract = _review_contract(task_name)
    evidence_contract = _evidence_contract(task_name)
    output_budget_contract = _output_budget_contract(context)
    revision_direction = _revision_direction(context)
    return (
        f"{prefix}You are the Yotsuba Ink {task_name} node.\n"
        "Return exactly one JSON object matching the supplied schema. Do not add commentary, defaults, or fields.\n"
        f"{revision_contract}"
        f"{proposal_contract}"
        f"{review_contract}"
        f"{evidence_contract}"
        f"{output_budget_contract}"
        f"Schema:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n"
        f"Context:\n{json.dumps(context, ensure_ascii=False, sort_keys=True)}"
        f"{revision_direction}"
    )


def _render_text_prompt(binding: ProviderBinding, context: dict[str, Any]) -> str:
    template = binding.prompt_template.strip()
    prefix = f"{template}\n\n" if template else ""
    material = context.get("material")
    if not isinstance(material, dict) or set(material) != {"chapter_context_manifest"}:
        raise ValueError("Text Provider input must contain only one Context Manifest")
    manifest = ContextManifest.model_validate(material["chapter_context_manifest"])
    return (
        f"{prefix}You are the Yotsuba Ink text node.\n"
        "Write the requested chapter as plain prose only. Do not return JSON, Markdown fences, metadata, analysis, or commentary.\n"
        "If revision.request is present, its snippet is the controlling revision direction.\n"
        f"Context manifest:\n{json.dumps(manifest.model_dump(mode='json'), ensure_ascii=False, sort_keys=True)}"
    )


def _revision_contract(context: dict[str, Any]) -> str:
    material = context.get("material")
    revision = material.get("revision_request") if isinstance(material, dict) else None
    if not isinstance(revision, dict):
        return ""
    return (
        "The revision_request is the controlling instruction for this call. "
        "Treat source_chapter or source_artifact only as the immutable draft to replace, not as accepted truth. "
        "Return a complete replacement that executes direction; rewrite or remove every source passage that "
        "conflicts with direction, and preserve only unaffected frozen story commitments.\n"
    )


def _output_budget_contract(context: dict[str, Any]) -> str:
    budget = context.get("output_budget")
    if not isinstance(budget, dict):
        return ""
    item_cap = budget.get("item_cap")
    field_char_cap = budget.get("field_char_cap")
    scene_cap = budget.get("scene_cap")
    if not isinstance(item_cap, int) or not isinstance(field_char_cap, int):
        raise ValueError("Structured output budget is incomplete")
    scene_rule = (
        f" and no chapter may contain more than {scene_cap} scenes"
        if isinstance(scene_cap, int)
        else ""
    )
    return (
        f"The output_budget is a hard response envelope: return at most {item_cap} top-level items, "
        f"keep each item within about {field_char_cap} characters{scene_rule}. "
        "Do not omit required keys to save space; prefer concise semantic text.\n"
    )


def _revision_direction(context: dict[str, Any]) -> str:
    material = context.get("material")
    revision = material.get("revision_request") if isinstance(material, dict) else None
    direction = revision.get("direction") if isinstance(revision, dict) else None
    if not isinstance(direction, str) or not direction.strip():
        return ""
    return f"\nControlling revision direction (apply every requirement):\n{direction.strip()}"


def _proposal_contract(task_name: str) -> str:
    if task_name == "role_demand.proposal":
        return (
            "This call returns only the role demand proposal batch; ignore stage-output "
            "instructions above that describe another artifact. Each demand is a casting "
            "slot for exactly one distinct character, and the runtime will create one "
            "subject per demand. Never split one character's duties, arc, or investigation "
            "into multiple demands: if two demands would be fulfilled by the same person, "
            "merge them into a single demand. The protagonist owns at most one demand. "
            "material.scale_plan gives the demand count guidance: aim for role_demand_target "
            "demands and stay inside role_demand_range (when user_locked is true the target "
            "is a user decision and must be matched exactly). Besides protagonist and "
            "opposition slots, include at least one named supporting character who "
            "personifies the story's emotional or communal stakes on the page — never leave "
            "the cost of the premise to anonymous walk-ons.\n"
        )
    if task_name == "cast":
        return (
            "Every dossier must be a distinct named character; no two subjects may share "
            "the same name, and one person must never occupy more than one subject slot. "
            "Give every subject a proper personal name (a real-sounding 人名), never a role "
            "descriptor such as 旧外套乘客 / 前值班员 / 机构代表 — put the role in function, "
            "not in name. material.reserved_names (when present) lists names already taken "
            "by other dossier groups of this same cast: never reuse or trivially vary them. "
            "Return exactly one dossier for every subject_ref supplied in this call.\n"
        )
    if task_name == "volume_boundary.proposal":
        return (
            "This call returns only the volume boundary proposal batch; ignore stage-output "
            "instructions above that describe another artifact. A boundary is a whole volume "
            "arc, not a spine turn: group consecutive turns into complete arcs. "
            "material.scale_plan gives the boundary count guidance: aim for volume_target "
            "boundaries and stay inside volume_range (when user_locked is true the count is "
            "a user decision and must be matched exactly). Never map one turn to one "
            "boundary mechanically.\n"
        )
    if task_name == "volumes":
        return (
            "Return exactly one volume contract for every boundary listed in "
            "material.volume_boundaries.proposals, in the same order. Never merge, split, "
            "add, or drop boundaries in this call.\n"
        )
    return ""


def _review_contract(task_name: str) -> str:
    if task_name != "text.review":
        return ""
    return (
        "Report only violations directly evidenced in the chapter. Do not emit findings for satisfied constraints, "
        "items not required in this chapter, or future appearance windows. Every finding is a violation report: "
        "never write a claim stating that the chapter satisfies, matches, complies with, or conforms to a "
        "constraint, and never restate a rule the chapter follows. When a constraint holds, return no finding for "
        "it; findings may be an empty list. A blocking finding requires a direct "
        "conflict that prevents accepting this chapter; ambiguity, omitted explanation, or optional enrichment is "
        "at most a warning. Judge thematic and character-arc obligations through dramatized choices, consequences, "
        "and behavior; never require an explicit theme statement when the action already establishes the change. "
        "Each finding must cite an exact non-empty excerpt from chapter.content in evidence and list every relevant "
        "frozen subject id in subject_ids; use [] only when no subject is involved, which a character reviewer "
        "never does: every character finding must list at least one subject id taken from "
        "appearance_policy.roster, and a finding you cannot attribute to a roster subject must not be reported. "
        "For a character reviewer, a subject "
        "whose id is in appearance_policy.not_yet_eligible_subject_ids is compliant when absent. Report it only for "
        "an early appearance, with the exact excerpt that proves the early appearance. "
        "An appearance means the subject is on stage in a scene: acting, speaking, or physically present where the "
        "POV can perceive them. Being named in narration or dialogue, remembered, discussed, listed in a contact "
        "list, phoning or texting from off stage, or referred to without a name is not an appearance and is never "
        "an early_appearance finding. Resolve every name through appearance_policy.roster, which maps each frozen "
        "subject id to its name and to whether it may appear in this chapter; never guess an id from position, "
        "never report a person absent from the roster, and never override roster eligibility with a debut window "
        "inferred from anywhere else. A roster entry with eligible true may appear freely. "
        "Ensure every claim and "
        "evidence pair logically supports its severity. For a continuity reviewer, material.opening_chapter means this "
        "is the first chapter of the book: there is no earlier chapter, so never judge it against a predecessor "
        "and never treat its own plan or handoff as an earlier chapter. Otherwise compare the chapter opening "
        "against the end of previous_accepted_chapter.content: a knowledge-state mismatch, a re-discovery of facts "
        "the POV already established, an invented past event that contradicts the previous chapter, or a time jump "
        "the prose contradicts is a blocking finding with the exact conflicting excerpt. A chapter break may move "
        "the story to a new time and place: opening in a different location, or after unstated hours, is normal "
        "craft and is a finding only when the prose presents the new scene as continuous with the previous ending, "
        "or when the elapsed time cannot accommodate what the chapter claims already happened. Never require a "
        "transitional passage that narrates travel between two scenes. When "
        "canon_facts is supplied, treat each claim as established truth: a passage that contradicts a canon claim "
        "(object state, prior event, character knowledge) is a blocking finding. For a prose reviewer, "
        "material.voice is the book-level narration contract: prose narrated in a different grammatical person "
        "than the voice promises (for example third person when the voice specifies first person) is a blocking "
        "finding; cite the chapter opening as evidence. Narration that already matches the promised person is not "
        "a finding at all.\n"
    )


def validate_review_result_contract(
    request: ChapterReviewRequest,
    result: ChapterReviewResult,
) -> None:
    """Reject a reviewer result that cannot be grounded in its frozen chapter context."""

    if result.role != request.role:
        raise ValueError("Reviewer result role does not match its frozen lane")
    if not result.findings:
        return
    material = request.context.get("material")
    if not isinstance(material, dict):
        raise ValueError("Reviewer context must contain its immutable material")
    chapter = material.get("chapter")
    content = chapter.get("content") if isinstance(chapter, dict) else None
    if not isinstance(content, str) or not content:
        raise ValueError("Reviewer context must contain the immutable chapter content")
    for finding in result.findings:
        if finding.evidence not in content:
            raise ValueError("Reviewer evidence must be an exact excerpt from the chapter")
    if request.role != "character":
        return
    policy = material.get("appearance_policy")
    if not isinstance(policy, dict):
        raise ValueError("Character reviewer context must contain an appearance policy")
    future_ids = {
        str(value)
        for value in policy.get("not_yet_eligible_subject_ids") or []
    }
    known_ids = {
        *(
            str(value)
            for value in policy.get("eligible_subject_ids") or []
        ),
        *future_ids,
    }
    for finding in result.findings:
        subject_ids = set(finding.subject_ids)
        if not subject_ids:
            raise ValueError("Character review findings must identify their frozen subjects")
        unknown = subject_ids - known_ids
        if unknown:
            raise ValueError(
                f"Character review references unknown frozen subjects: {sorted(unknown)}"
            )


def _evidence_contract(task_name: str) -> str:
    if task_name != "text.evidence":
        return ""
    return (
        "Return at most eight durable claims supported only by the supplied evidence_candidates. "
        "For each claim, select one to three span_ids exactly as listed; span_ids has a hard maximum of "
        "three entries, so never return four or more. Do not copy quote text or return "
        "character offsets; deterministic runtime code owns the source spans. Exclude decorative detail, "
        "interpretation, and claims not directly supported by the selected spans.\n"
    )


__all__ = [
    "ChapterGenerationRequest",
    "ChapterEvidenceRequest",
    "ChapterEvidenceResult",
    "ChapterReviewRequest",
    "ChapterReviewResult",
    "CoverImageRequest",
    "NarrativeProviderGateway",
    "PlainTextProviderResult",
    "ProposalGenerationRequest",
    "ProviderOperationError",
    "FrozenNarrativeProviderGateway",
    "ReviewFinding",
    "StageGenerationRequest",
    "StructuredProviderResult",
    "validate_review_result_contract",
]
