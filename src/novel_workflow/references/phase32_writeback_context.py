"""Deterministic source projection and proposal binding for Phase 32 writeback."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from novel_workflow.memory.phase32_canon_store import Phase32CanonStore
from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ChapterArtifact,
    ScreenplayDraftArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.output_contracts.phase32_writeback import (
    Phase32CanonFact,
    Phase32EvidenceProposalBundle,
    Phase32EvidenceRecord,
    Phase32EvidenceSpan,
    Phase32StateAssertionProposal,
    Phase32StateTransitionProposal,
)
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.storage.phase32_evidence_store import phase32_now
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


_SENTENCE_ENDINGS = frozenset("。！？!?")
_TRAILING_CLOSERS = frozenset("”’」』】）)")
_PROPERTY_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*){1,3}$")
_PROPERTY_ROOTS = frozenset(
    {"character", "relationship", "world", "location", "object", "clue", "knowledge", "promise"}
)


@dataclass(frozen=True, slots=True)
class Phase32EvidenceCandidate:
    span_id: str
    start: int
    end: int
    quote: str

    def prompt_payload(self) -> dict[str, object]:
        return {"span_id": self.span_id, "quote": self.quote}


@dataclass(frozen=True, slots=True)
class Phase32BoundWriteback:
    evidence: tuple[Phase32EvidenceRecord, ...]
    facts: tuple[Phase32CanonFact, ...]


def accepted_source_text(record: Phase32ArtifactRecord) -> str:
    if record.stage_id == "script":
        artifact = ScreenplayDraftArtifact.model_validate(record.payload)
        return "\n".join(block.text for block in artifact.blocks).strip()
    if record.creation_route_id == "short_novel":
        return ShortProseUnitArtifact.model_validate(record.payload).content.strip()
    if record.creation_route_id == "long_novel":
        return ChapterArtifact.model_validate(record.payload).content.strip()
    raise ValueError("Only accepted Script/Text Artifacts can produce Evidence")


def accepted_unit_ref(record: Phase32ArtifactRecord) -> str:
    if record.stage_id == "script":
        return ScreenplayDraftArtifact.model_validate(record.payload).scene_ref
    if record.creation_route_id == "short_novel":
        return ShortProseUnitArtifact.model_validate(record.payload).unit_ref
    if record.creation_route_id == "long_novel":
        return ChapterArtifact.model_validate(record.payload).chapter_ref
    raise ValueError("Unsupported Phase 32 writeback source")


def build_evidence_candidates(content: str) -> tuple[Phase32EvidenceCandidate, ...]:
    candidates: list[Phase32EvidenceCandidate] = []
    start: int | None = None
    index = 0
    while index < len(content):
        char = content[index]
        if start is None:
            if char.isspace():
                index += 1
                continue
            start = index
        if char in _SENTENCE_ENDINGS:
            end = index + 1
            while end < len(content) and (
                content[end] in _SENTENCE_ENDINGS or content[end] in _TRAILING_CLOSERS
            ):
                end += 1
            _append_candidate(candidates, content, start, end)
            start = None
            index = end
            continue
        if char == "\n":
            _append_candidate(candidates, content, start, index)
            start = None
        index += 1
    if start is not None:
        _append_candidate(candidates, content, start, len(content))
    if not candidates:
        raise ValueError("Accepted Artifact has no Evidence source spans")
    return tuple(candidates)


def compile_writeback_context(
    *,
    definition: GraphRunDefinition,
    artifact_store: Phase32ArtifactStore,
    canon: Phase32CanonStore,
    record: Phase32ArtifactRecord,
    content: str,
    candidates: tuple[Phase32EvidenceCandidate, ...],
    effective_ordinal: int,
) -> dict[str, Any]:
    subject_refs = _frozen_subject_refs(definition, artifact_store)
    existing_facts = canon.facts(definition.run_id)
    return {
        "source": {
            "source_artifact_ref": record.artifact_ref,
            "source_payload_digest": record.payload_digest,
            "source_text_digest": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "stage_id": record.stage_id,
            "unit_ref": accepted_unit_ref(record),
            "effective_ordinal": effective_ordinal,
        },
        "frozen_subject_refs": sorted(subject_refs),
        "existing_facts": [
            {
                "fact_ref": fact.fact_ref,
                "claim": fact.claim,
                "subject_ref": fact.subject_ref,
                "property_key": fact.property_key,
                "value": fact.value,
                "epistemic_status": fact.epistemic_status,
                "effective_ordinal": fact.effective_ordinal,
            }
            for fact in existing_facts[-64:]
        ],
        "source_spans": [candidate.prompt_payload() for candidate in candidates],
    }


def render_writeback_prompt(context: dict[str, Any], *, correction: str = "") -> str:
    subject_refs = [
        str(item).strip()
        for item in context.get("frozen_subject_refs", [])
        if str(item).strip()
    ]
    subject_example = subject_refs[0] if subject_refs else "frozen_subject_ref"
    instruction = (
        "你是四叶墨的事实提案器。只从已接受内容的 source_spans 中提取对后续创作有持续约束的事实。"
        "通常返回 0-3 条、绝不超过 8 条 claim；不要逐句罗列临时动作、外观、场景调度或普通对白。"
        "每条 claim 必须只引用 1-3 个给定 span_id（绝不能超过 3 个），优先选择最小的连续证据窗口；"
        "span_ids 是证据 ID 的 JSON 数组，不是 source_spans 的完整复制；即使一条 claim 可由 4 个片段支持，也只能选最相关的 1-3 个，4 个或更多必定合同失败；"
        "不得把计划、比喻、未证实猜测或写作建议升级为事实。"
        "每个 assertion.subject_ref 必须逐字等于 frozen_subject_refs 中的一个值；"
        "不得发明 clue、story、地点名、物件名或其他 subject_ref。无法绑定到冻结人物的持续事实必须使用 story state；"
        "已有同一属性必须用 transition 和 source_fact_ref。"
        "state 必须是对象，不能是字符串；state 必须是 JSON 对象，只允许以下三种形状："
        "story 为 {\"type\":\"story\",\"epistemic_status\":\"fact\"}；"
        f"assertion 为 {{\"type\":\"assertion\",\"subject_ref\":\"{subject_example}\",\"property_key\":\"clue.status\",\"value\":\"已发现拼接痕迹\",\"epistemic_status\":\"fact\"}}；"
        "assertion 的 property_key 必须使用受控的小写命名空间，首段只能是 "
        "character、relationship、world、location、object、clue、knowledge 或 promise；"
        "property_key 必须至少包含一个点并采用 namespace.name 形状，不能只返回 knowledge、clue 等根名；"
        "不得使用 evidence、accusation、response 等未注册命名空间，也不要把普通事件类型当作属性根；"
        "transition 的唯一合法形状是 {\"type\":\"transition\",\"source_fact_ref\":\"existing_facts 中的真实 fact_ref\","
        "\"action\":\"supersedes 或 resolves\",\"value\":\"新的状态\",\"epistemic_status\":\"fact\"}；"
        "不得包含 subject_ref、property_key、fact_ref、transition 等额外字段；"
        "只能逐字复制 existing_facts 中真实存在的 fact_ref，绝不能输出 p32-fact-... 等占位符。"
        "state.type 必须是 story、assertion 或 transition 之一；epistemic_status 只能使用 fact、rumour、belief、reveal、refutation，绝对不要使用 confirmed。"
        "没有足够依据时返回 {\"claims\": []}，不要为了填满结果而发明事实。"
        "你只返回符合 JSON Schema 的对象，不返回解释。"
    )
    existing_properties = [
        {
            "subject_ref": item.get("subject_ref"),
            "property_key": item.get("property_key"),
            "fact_ref": item.get("fact_ref"),
        }
        for item in context.get("existing_facts", [])
        if isinstance(item, dict)
        and item.get("subject_ref")
        and item.get("property_key")
        and item.get("fact_ref")
    ]
    if existing_properties:
        instruction += (
            " 当前上下文已有属性清单如下："
            + json.dumps(existing_properties, ensure_ascii=False, separators=(",", ":"))
            + "。如果 claim 的 subject_ref 与清单中的 subject_ref/property_key 组合相同，"
            "必须引用对应的精确 fact_ref 并使用 state.type=transition；"
            "禁止再次使用 state.type=assertion，也禁止改用另一个 property_key 绕过该规则。"
        )
    else:
        instruction += (
            " 当前 existing_facts 中没有可转换的绑定属性，因此禁止使用 transition；"
            "只能使用 story、绑定到 frozen_subject_refs 的 assertion，或返回空 claims。"
        )
    if correction:
        instruction += f" 上一次返回违反合同：{correction[:800]}。请完整重新返回，不要复述错误内容。"
    frozen_context = json.dumps(
        context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    # Keep a short format gate after the potentially very large context. Long
    # chapter spans can otherwise bury the discriminated-union constraints and
    # lead the model to emit a JSON-encoded state string or a partial claim.
    # Repeat the span cardinality rule here as well: DeepSeek's JSON-object mode
    # validates syntax but does not enforce nested maxLength from the schema.
    output_gate = (
        "输出前硬检查：claims 为空，或每条 claim 都必须含 state 对象；"
        "state 绝不能加引号、绝不能是字符串；state.type 只能是 story、assertion、transition；"
        "每个 span_ids 必须是长度为 1、2 或 3 的 JSON 数组，不能出现 4 项，不能复制全部 source_spans。"
    )
    if correction:
        output_gate += (
            " 合同纠正（最高优先级）："
            f"{correction[:800]}。保留未违规 claim，只修复指出的字段；"
            "不要因为单条 span_ids 超限而清空全部 claims，除非确实没有可绑定证据。"
        )
    return (
        instruction
        + "\n\n冻结上下文：\n"
        + frozen_context
        + "\n\n"
        + output_gate
        + "只返回一个 JSON 对象。"
    )


def bind_writeback_proposals(
    *,
    definition: GraphRunDefinition,
    record: Phase32ArtifactRecord,
    content: str,
    candidates: tuple[Phase32EvidenceCandidate, ...],
    bundle: Phase32EvidenceProposalBundle,
    existing_facts: tuple[Phase32CanonFact, ...],
    frozen_subject_refs: set[str],
    effective_ordinal: int,
) -> Phase32BoundWriteback:
    by_span = {candidate.span_id: candidate for candidate in candidates}
    by_fact = {fact.fact_ref: fact for fact in existing_facts}
    existing_properties = {
        (fact.subject_ref, fact.property_key)
        for fact in existing_facts
        if fact.subject_ref and fact.property_key
    }
    evidence_records: list[Phase32EvidenceRecord] = []
    facts: list[Phase32CanonFact] = []
    source_text_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    for proposal in bundle.claims:
        spans = tuple(_bind_span(by_span, span_id, content) for span_id in proposal.span_ids)
        state = proposal.state
        subject_ref = ""
        property_key = ""
        value = ""
        lifecycle = "active"
        source_fact_refs: tuple[str, ...] = ()
        epistemic_status = state.epistemic_status
        if isinstance(state, Phase32StateAssertionProposal):
            if state.subject_ref not in frozen_subject_refs:
                raise ValueError(f"Evidence references an unfrozen subject: {state.subject_ref}")
            _validate_property_key(state.property_key)
            if (state.subject_ref, state.property_key) in existing_properties:
                raise ValueError("Existing subject property requires a source-bound transition")
            subject_ref = state.subject_ref
            property_key = state.property_key
            value = state.value
        elif isinstance(state, Phase32StateTransitionProposal):
            source = by_fact.get(state.source_fact_ref)
            if source is None:
                raise ValueError(f"Evidence references an unknown source fact: {state.source_fact_ref}")
            if not source.subject_ref or not source.property_key:
                raise ValueError("Only a bound state fact can be transitioned")
            subject_ref = source.subject_ref
            property_key = source.property_key
            value = state.value
            lifecycle = state.action
            source_fact_refs = (source.fact_ref,)
        evidence_seed = {
            "run_id": definition.run_id,
            "source_artifact_ref": record.artifact_ref,
            "claim": proposal.claim,
            "spans": [span.model_dump(mode="json") for span in spans],
            "state": state.model_dump(mode="json"),
        }
        evidence_ref = f"p32-evidence-{canonical_digest(evidence_seed)}"
        evidence = Phase32EvidenceRecord(
            evidence_ref=evidence_ref,
            run_id=definition.run_id,
            creation_route_id=definition.creation_route_id,
            stage_id=record.stage_id,
            unit_ref=accepted_unit_ref(record),
            source_artifact_ref=record.artifact_ref,
            source_payload_digest=record.payload_digest,
            source_text_digest=source_text_digest,
            kind=proposal.kind,
            claim=proposal.claim,
            spans=spans,
            subject_ref=subject_ref,
            property_key=property_key,
            value=value,
            epistemic_status=epistemic_status,
            lifecycle=lifecycle,
            source_fact_refs=source_fact_refs,
            effective_ordinal=effective_ordinal,
            created_at=phase32_now(),
        )
        fact_seed = {
            "evidence_ref": evidence_ref,
            "source_artifact_ref": record.artifact_ref,
            "claim": proposal.claim,
            "state": state.model_dump(mode="json"),
        }
        fact = Phase32CanonFact(
            fact_ref=f"p32-fact-{canonical_digest(fact_seed)}",
            claim=proposal.claim,
            evidence_refs=(evidence_ref,),
            source_artifact_ref=record.artifact_ref,
            stage_id=record.stage_id,
            unit_ref=accepted_unit_ref(record),
            subject_ref=subject_ref,
            property_key=property_key,
            value=value,
            epistemic_status=epistemic_status,
            lifecycle=lifecycle,
            source_fact_refs=source_fact_refs,
            effective_ordinal=effective_ordinal,
        )
        evidence_records.append(evidence)
        facts.append(fact)
    return Phase32BoundWriteback(tuple(evidence_records), tuple(facts))


def _frozen_subject_refs(
    definition: GraphRunDefinition,
    artifacts: Phase32ArtifactStore,
) -> set[str]:
    committed = artifacts.list(definition.run_id, stage_id="cast", status="committed")
    if not committed:
        raise ValueError("Writeback requires a committed Cast Artifact")
    payload = committed[-1].payload
    refs = {
        str(item.get("subject_ref") or "").strip()
        for item in payload.get("characters", [])
        if isinstance(item, dict)
    }
    refs.discard("")
    if not refs:
        raise ValueError("Committed Cast has no frozen subjects")
    return refs


def frozen_subject_refs(
    definition: GraphRunDefinition,
    artifacts: Phase32ArtifactStore,
) -> set[str]:
    return _frozen_subject_refs(definition, artifacts)


def _bind_span(
    candidates: dict[str, Phase32EvidenceCandidate],
    span_id: str,
    content: str,
) -> Phase32EvidenceSpan:
    candidate = candidates.get(span_id)
    if candidate is None:
        raise ValueError(f"Evidence references an unknown source span: {span_id}")
    if content[candidate.start : candidate.end] != candidate.quote:
        raise ValueError("Evidence source span drifted from the accepted Artifact")
    return Phase32EvidenceSpan(
        start=candidate.start,
        end=candidate.end,
        quote=candidate.quote,
    )


def _append_candidate(
    candidates: list[Phase32EvidenceCandidate],
    content: str,
    start: int,
    end: int,
) -> None:
    while end > start and content[end - 1].isspace():
        end -= 1
    if end <= start:
        return
    candidates.append(
        Phase32EvidenceCandidate(
            span_id=f"span-{len(candidates) + 1:04d}",
            start=start,
            end=end,
            quote=content[start:end],
        )
    )


def _validate_property_key(property_key: str) -> None:
    if not _PROPERTY_KEY.fullmatch(property_key):
        raise ValueError("Evidence property key must use a stable lowercase namespace")
    if property_key.split(".", 1)[0] not in _PROPERTY_ROOTS:
        raise ValueError("Evidence property namespace is not supported")


__all__ = [
    "Phase32BoundWriteback",
    "Phase32EvidenceCandidate",
    "accepted_source_text",
    "accepted_unit_ref",
    "bind_writeback_proposals",
    "build_evidence_candidates",
    "compile_writeback_context",
    "frozen_subject_refs",
    "render_writeback_prompt",
]
