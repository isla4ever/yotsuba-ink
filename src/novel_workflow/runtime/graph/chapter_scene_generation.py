from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from novel_workflow.output_contracts.artifacts_vnext import (
    ContextManifest,
    DetailChapter,
)
from novel_workflow.runtime.graph.chapter_scene_facts import (
    introduced_quantified_fact_tokens,
)
from novel_workflow.runtime.graph.chapter_scene_length import (
    SceneLengthContract,
    next_scene_length_contract,
)
from novel_workflow.runtime.graph.context_compiler import (
    _context_snippet,
    _manifest_hash,
)
from novel_workflow.runtime.graph.provider_gateway import compile_provider_input
from novel_workflow.runtime.graph.provider_requests import (
    ChapterSceneGenerationRequest,
    ProviderOperationError,
)
from novel_workflow.runtime.graph.stage_executor import _is_transient_network_error
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from novel_workflow.workflows.narrative_scale import (
    ChapterLengthContract,
    chapter_length_contract,
    count_prose_characters,
)

if TYPE_CHECKING:
    from novel_workflow.runtime.graph.output_budget import OutputBudgetPlan
    from novel_workflow.runtime.graph.stage_executor import StageExecutor
    from novel_workflow.runtime.graph.state import NarrativeRunState


_MAX_SCENE_ATTEMPTS = 3
_SCENE_NETWORK_ATTEMPTS = 3
_SCENE_OUTPUT_TOKEN_CAP = 2_400
# Keep the prior scene bounded while preserving enough of its final physical
# and knowledge state for the next scene to continue without replaying it.
_PREVIOUS_SCENE_EXCERPT_CHARS = 900


@dataclass(frozen=True, slots=True)
class ChapterSceneGenerationResult:
    content: str
    operation_keys: tuple[str, ...]


class SceneProseContractError(ValueError):
    def __init__(self, message: str, *, operation_key: str) -> None:
        super().__init__(message)
        self.operation_key = operation_key


async def generate_chapter_scenes(
    executor: StageExecutor,
    state: NarrativeRunState,
    *,
    base_manifest: ContextManifest,
    detail_chapter: DetailChapter,
    binding: ProviderBinding,
    budget: OutputBudgetPlan,
) -> ChapterSceneGenerationResult:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    chapter_number = int(state["active_chapter_number"])
    chapter_attempt = int((state.get("chapter_attempts") or {}).get(chapter_id) or 1)
    chapter_contract = chapter_length_contract(
        detail_chapter.target_characters,
        executor.runs.definition(run_id).quality_mode,
        scene_count=len(detail_chapter.scenes),
    )
    if chapter_contract is None:
        raise ValueError("Chapter scene generation requires a frozen character target")

    scene_binding = _scene_binding(budget.bind(binding), chapter_contract)
    chapter_revision = _snippet_text(base_manifest, "revision.request")
    generated: list[str] = []
    accepted_character_counts: list[int] = []
    operation_keys: list[str] = []

    for _scene in detail_chapter.scenes:
        contract = next_scene_length_contract(
            chapter_contract,
            accepted_character_counts=accepted_character_counts,
        )
        source, source_fact_drift = _previous_attempt_scene(
            executor,
            run_id=run_id,
            chapter_id=chapter_id,
            chapter_attempt=chapter_attempt,
            scene_index=contract.scene_index,
        )
        accepted_scene = ""
        final_fact_drift: tuple[str, ...] = ()
        for scene_attempt in range(1, _MAX_SCENE_ATTEMPTS + 1):
            operation_key = scene_operation_key(
                run_id,
                chapter_id,
                chapter_attempt=chapter_attempt,
                scene_index=contract.scene_index,
                scene_attempt=scene_attempt,
            )
            revision = _scene_revision_direction(
                contract,
                source,
                chapter_revision=chapter_revision,
                rejected_fact_tokens=source_fact_drift,
            )
            manifest = build_scene_manifest(
                base_manifest,
                detail_chapter=detail_chapter,
                scene_index=contract.scene_index,
                contract=contract,
                output_tokens=scene_binding.max_tokens,
                previous_scene=generated[-1] if generated else "",
                source_scene=source,
                revision_direction=revision,
            )
            request = ChapterSceneGenerationRequest(
                operation_key=operation_key,
                run_id=run_id,
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                chapter_attempt=chapter_attempt,
                scene_index=contract.scene_index,
                scene_attempt=scene_attempt,
                binding=scene_binding,
                context={
                    "target": "text.scene",
                    "sources": {},
                    "material": {
                        "chapter_context_manifest": manifest.model_dump(mode="json")
                    },
                    "output_budget": {"max_tokens": scene_binding.max_tokens},
                },
            )
            receipt = executor.operations.begin_provider(
                run_id=run_id,
                operation_key=operation_key,
                kind="chapter_scene_generation",
                provider_profile_id=binding.provider_profile_id,
                model=scene_binding.model,
                provider_input=compile_provider_input(request),
            )
            operation_keys.append(operation_key)
            if receipt.status == "failed":
                raise ProviderOperationError.for_operation(
                    operation_key,
                    f"Provider operation already failed: {operation_key}",
                )
            if receipt.status == "succeeded":
                content = _read_scene_receipt(receipt.result)
            else:
                response = None
                try:
                    response = await _generate_scene_with_network_retry(executor, request)
                    content = response.content.strip()
                    if not content:
                        raise ValueError("Chapter scene Provider returned empty prose")
                except Exception as exc:
                    executor.operations.fail(
                        run_id,
                        operation_key,
                        {"type": type(exc).__name__, "message": str(exc)},
                        usage=(response.usage if response is not None else getattr(exc, "usage", {})),
                        diagnostic=(
                            response.diagnostic
                            if response is not None
                            else getattr(exc, "diagnostic", {})
                        ),
                    )
                    raise ProviderOperationError.for_operation(operation_key, exc) from exc
                measured = count_prose_characters(content)
                fact_drift = introduced_quantified_fact_tokens(content, manifest)
                executor.operations.succeed(
                    run_id,
                    operation_key,
                    {"content": content},
                    usage=response.usage,
                    diagnostic={
                        **response.diagnostic,
                        "measured_non_whitespace_characters": measured,
                        "scene_length_bounds": [
                            contract.min_characters,
                            contract.max_characters,
                        ],
                        "introduced_quantified_facts": list(fact_drift),
                    },
                )

            actual = count_prose_characters(content)
            final_fact_drift = introduced_quantified_fact_tokens(content, manifest)
            if not final_fact_drift:
                accepted_scene = content.strip()
                warning = scene_length_warning_payload(contract, actual)
                if warning is not None:
                    executor.events.append(
                        run_id,
                        event_id=f"{operation_key}:length-warning",
                        type="quality.warning",
                        stage_id="text",
                        node_id="text.generate_prose",
                        chapter_id=chapter_id,
                        status="warning",
                        payload=warning,
                        payload_ref=operation_key,
                    )
                break
            source = content.strip()
            source_fact_drift = final_fact_drift

        if not accepted_scene:
            raise SceneProseContractError(
                "introduced quantified facts absent from frozen context: "
                + ", ".join(final_fact_drift)
                + f" after {_MAX_SCENE_ATTEMPTS} attempts",
                operation_key=operation_keys[-1],
            )
        generated.append(accepted_scene)
        accepted_character_counts.append(count_prose_characters(accepted_scene))

    return ChapterSceneGenerationResult(
        content="\n\n".join(generated),
        operation_keys=tuple(operation_keys),
    )


def scene_length_warning_payload(
    contract: SceneLengthContract,
    actual: int,
) -> dict[str, Any] | None:
    if contract.min_characters <= actual <= contract.max_characters:
        return None
    return {
        "code": "scene_length_soft_band",
        "actual_characters": actual,
        "target_characters": contract.target_characters,
        "soft_bounds": [contract.min_characters, contract.max_characters],
    }


def build_scene_manifest(
    base: ContextManifest,
    *,
    detail_chapter: DetailChapter,
    scene_index: int,
    contract: SceneLengthContract,
    output_tokens: int,
    previous_scene: str = "",
    source_scene: str = "",
    revision_direction: str = "",
) -> ContextManifest:
    by_ref = {snippet.ref: snippet.model_dump(mode="json") for snippet in base.snippets}
    required_base = ("cast.subjects", "volume.contract", "brief.world_rules")
    missing = [ref for ref in required_base if ref not in by_ref]
    if missing:
        raise ValueError(f"Scene context is missing frozen inputs: {missing}")
    scene = detail_chapter.scenes[scene_index - 1]
    snippets = [
        _context_snippet(
            "detail.chapter",
            "current_scene_script",
            {
                "ref": detail_chapter.ref,
                "title": detail_chapter.title,
                "purpose": detail_chapter.purpose,
                "pov": detail_chapter.pov,
                "scene_index": scene_index,
                "scene_count": len(detail_chapter.scenes),
                "scene": scene.model_dump(mode="json"),
                "chapter_handoff": (
                    detail_chapter.handoff
                    if scene_index == len(detail_chapter.scenes)
                    else ""
                ),
            },
        ),
        by_ref["cast.subjects"],
        by_ref["volume.contract"],
        by_ref["brief.world_rules"],
        _context_snippet(
            "scene.execution",
            "deterministic_dramatic_scaffold",
            _scene_execution_scaffold(scene_index, scene),
        ),
        _context_snippet(
            "scale.scene_length",
            "rolling_scene_length_contract",
            {
                "counting_rule": "non_whitespace_characters",
                "scene_index": scene_index,
                "scene_count": contract.scene_count,
                "target_characters": contract.target_characters,
                "min_characters": contract.min_characters,
                "max_characters": contract.max_characters,
                "accepted_prior_characters": contract.accepted_prior_characters,
                "remaining_scene_count": contract.remaining_scene_count,
                "chapter_target_characters": contract.chapter_target_characters,
                "chapter_min_characters": contract.chapter_min_characters,
                "chapter_max_characters": contract.chapter_max_characters,
            },
        ),
    ]
    required = [
        "detail.chapter",
        "cast.subjects",
        "volume.contract",
        "brief.world_rules",
        "scene.execution",
        "scale.scene_length",
    ]
    optional: list[str] = []
    if "brief.voice" in by_ref:
        optional.append("brief.voice")
        snippets.append(by_ref["brief.voice"])
    for ref in (
        "previous.handoff",
        "previous.ending_excerpt",
        "previous.staged_beats",
        "canon.established_facts",
    ):
        if ref in by_ref:
            optional.append(ref)
            snippets.append(by_ref[ref])
    if previous_scene:
        optional.append("current_chapter.previous_scene")
        snippets.append(
            _context_snippet(
                "current_chapter.previous_scene",
                "already_written_continue_without_repeating",
                {
                    "result": detail_chapter.scenes[scene_index - 2].result,
                    "ending_excerpt": previous_scene[-_PREVIOUS_SCENE_EXCERPT_CHARS:],
                },
            )
        )
    if source_scene:
        if not revision_direction.strip():
            raise ValueError("A scene source draft requires a revision direction")
        optional.extend(["revision.source_draft", "revision.request"])
        snippets.extend(
            [
                _context_snippet(
                    "revision.source_draft",
                    "unaccepted_scene_to_replace",
                    {
                        "scope": "scene",
                        "measured_non_whitespace_characters": count_prose_characters(
                            source_scene
                        ),
                        "content": source_scene,
                    },
                ),
                _context_snippet(
                    "revision.request",
                    "controlling_scene_revision",
                    revision_direction,
                ),
            ]
        )
    manifest_body: dict[str, Any] = {
        "task": detail_chapter.ref,
        "required": required,
        "optional": optional,
        "forbidden": [
            "full_canon",
            "full_wiki",
            "unrelated_subjects",
            "full_previous_chapter",
        ],
        "snippets": snippets,
        "budget": {
            "input_chars": sum(len(item["text"]) for item in snippets),
            "output_tokens": output_tokens,
        },
    }
    manifest_body["manifest_hash"] = _manifest_hash(manifest_body)
    return ContextManifest.model_validate(manifest_body)


def scene_operation_key(
    run_id: str,
    chapter_id: str,
    *,
    chapter_attempt: int,
    scene_index: int,
    scene_attempt: int,
) -> str:
    return (
        f"{run_id}:{chapter_id}:scene-{scene_index}:"
        f"generate:{chapter_attempt}.{scene_attempt}"
    )


def _scene_execution_scaffold(scene_index: int, scene: Any) -> dict[str, Any]:
    return {
        "scene_index": scene_index,
        "beats": [
            {
                "order": 1,
                "job": f"从{scene.place}中 POV 正在执行的动作落地，不新增时间、编号或人物",
            },
            {"order": 2, "job": f"把目标写成连续可见动作：{scene.objective}"},
            {"order": 3, "job": f"让既定阻力在台面上发生：{scene.conflict}"},
            {
                "order": 4,
                "job": "写 POV 基于既有规则的选择与应对，可展开空间动作、职业行为和心理张力，但不新增可验证事实",
            },
            {"order": 5, "job": f"完整执行既定转折：{scene.turn}"},
            {"order": 6, "job": f"停在既定结果形成的可见状态：{scene.result}"},
        ],
    }


def _scene_revision_direction(
    contract: SceneLengthContract,
    source: str,
    *,
    chapter_revision: str,
    rejected_fact_tokens: tuple[str, ...] = (),
) -> str:
    if not source:
        return ""
    actual = count_prose_characters(source)
    if actual < contract.min_characters:
        minimum_growth = contract.min_characters - actual
        target_growth = max(0, contract.target_characters - actual)
        length_direction = (
            f"这是保留合规内容的净扩写修订，不是重新取样、缩写或摘要。新稿相对旧稿至少净增 "
            f"{minimum_growth} 字，并尽量净增 {target_growth} 字；保留旧稿中符合冻结输入的事件顺序、"
            "动作链和有效段落，不得删减或概括后再用更短文字替换。只把既有尝试与受阻、空间动作、"
            "POV 选择、身体反应、潜台词和即时后果写得更充分，不得用新增程序、权限、记录或前史填充。"
        )
    elif actual > contract.max_characters:
        length_direction = (
            "这是压缩修订。保留施工图要求的目标、冲突、转折和结果，删除重复心理复述、解释性总结"
            "和无效过场，不得删掉因果动作或改变场景结果。"
        )
    else:
        length_direction = (
            "当前篇幅已经合格；只修复事实合同，不得借修复改变事件顺序、重写场景结果或明显缩短正文。"
        )
    direction = (
        f"返回当前场景的完整替换稿。旧稿为 {actual} 字，必须改到 "
        f"{contract.min_characters}-{contract.max_characters} 字并靠近 "
        f"{contract.target_characters} 字。{length_direction}"
        "删除冻结输入未出现的编号、日期、地点、人物、权限、记录、历史和调查结论；"
        "不得新增场景结果之外的事件或可验证事实。"
    )
    if rejected_fact_tokens:
        exact_tokens = "、".join(rejected_fact_tokens)
        direction += (
            f"上次输出被确定性事实门拒绝，精确违规 token 为：{exact_tokens}。"
            "逐一删除包含这些 token 的句子，不得改写、替换或再次输出这些量化身份；"
            "改用不产生新编号或数量事实的动作表达。"
        )
    return f"{chapter_revision.strip()}\n{direction}".strip()


def _previous_attempt_scene(
    executor: StageExecutor,
    *,
    run_id: str,
    chapter_id: str,
    chapter_attempt: int,
    scene_index: int,
) -> tuple[str, tuple[str, ...]]:
    if chapter_attempt <= 1:
        return "", ()
    for scene_attempt in range(_MAX_SCENE_ATTEMPTS, 0, -1):
        operation_key = scene_operation_key(
            run_id,
            chapter_id,
            chapter_attempt=chapter_attempt - 1,
            scene_index=scene_index,
            scene_attempt=scene_attempt,
        )
        receipt = executor.operations.find(run_id, operation_key)
        if receipt is not None and receipt.status == "succeeded":
            rejected = receipt.diagnostic.get("introduced_quantified_facts") or []
            return _read_scene_receipt(receipt.result), tuple(
                dict.fromkeys(
                    str(token).strip()
                    for token in rejected
                    if str(token).strip()
                )
            )
    raise ValueError("A repeated chapter generation requires its immutable source scenes")


def _scene_binding(
    binding: ProviderBinding,
    chapter: ChapterLengthContract,
) -> ProviderBinding:
    max_tokens = min(
        binding.max_tokens,
        _SCENE_OUTPUT_TOKEN_CAP,
        max(1_800, round(chapter.max_characters * 1.5)),
    )
    return binding.model_copy(update={"max_tokens": max_tokens})


async def _generate_scene_with_network_retry(
    executor: StageExecutor,
    request: ChapterSceneGenerationRequest,
) -> Any:
    for round_index in range(_SCENE_NETWORK_ATTEMPTS):
        try:
            return await executor.provider.generate_chapter_scene(request)
        except Exception as exc:
            if (
                round_index >= _SCENE_NETWORK_ATTEMPTS - 1
                or not _is_transient_network_error(exc)
            ):
                raise
            await asyncio.sleep(2 * (round_index + 1))
    raise RuntimeError("unreachable")


def _read_scene_receipt(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ValueError("Chapter scene receipt must be an object")
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Chapter scene receipt must contain non-empty text")
    return content.strip()


def _snippet_text(manifest: ContextManifest, ref: str) -> str:
    snippet = next((item for item in manifest.snippets if item.ref == ref), None)
    return snippet.text if snippet is not None else ""


__all__ = [
    "ChapterSceneGenerationResult",
    "SceneProseContractError",
    "build_scene_manifest",
    "generate_chapter_scenes",
    "scene_operation_key",
]
