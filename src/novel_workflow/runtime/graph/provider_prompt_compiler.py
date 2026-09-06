from __future__ import annotations

import json
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import ContextManifest
from novel_workflow.storage.narrative_run_repository import ProviderBinding


_STAGE_ARTIFACT_TASKS = frozenset(
    {"brief", "spine", "cast", "volumes", "detail", "cover"}
)


def render_structured_prompt(
    binding: ProviderBinding,
    task_name: str,
    context: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    # Stage templates describe the stage Artifact. Auxiliary proposal/review
    # calls have narrower contracts and must not be told to ignore a competing
    # stage-output task in the same prompt.
    template = (
        binding.prompt_template.strip()
        if task_name in _STAGE_ARTIFACT_TASKS
        and not _is_detail_preflight_recovery(task_name, context)
        else ""
    )
    prefix = f"{template}\n\n" if template else ""
    return (
        f"{prefix}You are the Yotsuba Ink {task_name} node.\n"
        "Return exactly one JSON object matching the supplied schema. Do not add commentary, defaults, or fields.\n"
        f"{_revision_contract(task_name, context)}"
        f"{_dynamic_task_contract(task_name, context)}"
        f"{_detail_preflight_recovery_contract(task_name, context)}"
        f"{_proposal_contract(task_name)}"
        f"{_review_contract(task_name)}"
        f"{_evidence_contract(task_name, context)}"
        f"{_output_budget_contract(context, schema)}"
        f"Schema:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n"
        f"Context:\n{json.dumps(context, ensure_ascii=False, sort_keys=True)}"
        f"{_revision_direction(task_name, context)}"
    )


def _is_detail_preflight_recovery(
    task_name: str,
    context: dict[str, Any],
) -> bool:
    if task_name != "detail":
        return False
    material = context.get("material")
    return isinstance(material, dict) and isinstance(
        material.get("preflight_feedback"),
        dict,
    ) and isinstance(material.get("recovery_source"), dict)


def _dynamic_task_contract(task_name: str, context: dict[str, Any]) -> str:
    material = context.get("material")
    if not isinstance(material, dict):
        return ""
    scale = material.get("scale_plan")
    if not isinstance(scale, dict):
        return ""
    if task_name == "spine":
        target = scale.get("turn_target")
        positions = scale.get("milestone_positions")
        if not isinstance(target, int) or not isinstance(positions, dict):
            raise ValueError("Spine prompt requires an exact turn target and milestone positions")
        required = (
            "inciting",
            "commitment",
            "midpoint_reversal",
            "crisis",
            "climax",
            "aftermath",
        )
        if any(
            not isinstance(positions.get(label), int)
            or not 1 <= int(positions[label]) <= target
            for label in required
        ):
            raise ValueError("Spine prompt milestone positions are invalid")
        anchors = ", ".join(
            f"turn {positions[label]} = {label}" for label in required
        )
        return (
            f"The runtime has frozen exactly {target} causal turns for this book. Return exactly {target}; "
            "the capacity range is diagnostic and is not permission to choose another count. "
            f"Write each anchored turn so its cause/change performs this exact structural function: {anchors}. "
            "Do not return milestone labels: the runtime binds those code-owned labels after validating the "
            "creative cause/change chain. A thin, repeated, waiting, or procedural turn is a failed plan, not a "
            "reason to change the count. Before emitting JSON, silently verify the exact count, every anchor, "
            "the cause-to-prior-change chain, and the progress rhythm. Every three-turn window must contain at "
            "least one relationship, external, or internal change; each relationship or external turn must name "
            "a recognizable chooser, consequence bearer, or pressure source for later Role Demand extraction. "
            "Repair the current response before emitting it; do not defer structural defects to revision.\n"
        )
    if task_name == "role_demand.proposal":
        recommended = scale.get("cast_recommended_range")
        hard_max = scale.get("cast_hard_max")
        if (
            not isinstance(recommended, list)
            or len(recommended) != 2
            or not all(isinstance(value, int) for value in recommended)
            or not isinstance(hard_max, int)
        ):
            raise ValueError("Role demand prompt requires the frozen cast capacity")
        return (
            f"This book scale requires at least {recommended[0]} distinct dramatic subjects and allows at most "
            f"{hard_max}; {recommended[1]} is the editorial center, not a quota. The lower bound includes the "
            "protagonist and any indispensable historical subject. Every slot must still be irreducible and "
            "supported by exact Spine turns; do not pad the roster with institutional representatives.\n"
        )
    return ""


def render_text_prompt(binding: ProviderBinding, context: dict[str, Any]) -> str:
    template = binding.prompt_template.strip()
    prefix = f"{template}\n\n" if template else ""
    material = context.get("material")
    if not isinstance(material, dict) or set(material) != {"chapter_context_manifest"}:
        raise ValueError("Text Provider input must contain only one Context Manifest")
    manifest = ContextManifest.model_validate(material["chapter_context_manifest"])
    if any(snippet.ref == "revision.local_segment" for snippet in manifest.snippets):
        return _render_local_scene_repair_prompt(prefix, manifest)
    scene_instruction = _text_scene_instruction(manifest)
    length_instruction = _text_length_instruction(manifest)
    revision_instruction = _text_revision_instruction(manifest)
    return (
        f"{prefix}You are the Yotsuba Ink text node.\n"
        "Write only the requested scene segment as plain prose. Do not return a chapter title, scene heading, JSON, Markdown fences, metadata, analysis, or commentary.\n"
        "If revision.request is present, its snippet is the controlling revision direction.\n"
        f"{scene_instruction}"
        f"{length_instruction}"
        f"{revision_instruction}"
        f"Context manifest:\n{json.dumps(manifest.model_dump(mode='json'), ensure_ascii=False, sort_keys=True)}"
    )


def _render_local_scene_repair_prompt(prefix: str, manifest: ContextManifest) -> str:
    required = {
        "detail.chapter",
        "cast.subjects",
        "volume.contract",
        "brief.world_rules",
        "scene.execution",
        "revision.local_segment",
    }
    refs = {snippet.ref for snippet in manifest.snippets}
    missing = sorted(required - refs)
    if missing:
        raise ValueError(f"Local scene fact repair is missing frozen refs: {missing}")
    if "revision.source_draft" in refs:
        raise ValueError("Local scene fact repair cannot include the full rejected scene")
    return (
        f"{prefix}You are the Yotsuba Ink bounded scene fact-repair node.\n"
        "Return only one replacement passage for revision.local_segment.masked_rejected_segment as plain prose. "
        "Do not return the whole scene, a continuation, heading, JSON, Markdown, analysis, or commentary. "
        "Preserve the local dramatic action and connect naturally to left_context and right_context, but do not "
        "repeat the placeholder or introduce any ordinal label, numeric value, date, count, rank, percentage, "
        "identifier, new subject, location, permission, record, procedure, history, or conclusion. The frozen "
        "Detail scene, subject dossiers, volume contract, world rules, and execution beats remain authoritative.\n"
        f"Context manifest:\n{json.dumps(manifest.model_dump(mode='json'), ensure_ascii=False, sort_keys=True)}"
    )


def _text_length_instruction(manifest: ContextManifest) -> str:
    snippet = next(
        (item for item in manifest.snippets if item.ref == "scale.scene_length"),
        None,
    )
    if snippet is None:
        return ""
    try:
        contract = json.loads(snippet.text)
    except json.JSONDecodeError as exc:
        raise ValueError("scale.scene_length snippet must contain JSON") from exc
    if not isinstance(contract, dict):
        raise ValueError("scale.scene_length snippet must be an object")
    target = contract.get("target_characters")
    minimum = contract.get("min_characters")
    maximum = contract.get("max_characters")
    accepted_prior = contract.get("accepted_prior_characters")
    remaining_scenes = contract.get("remaining_scene_count")
    chapter_target = contract.get("chapter_target_characters")
    chapter_minimum = contract.get("chapter_min_characters")
    chapter_maximum = contract.get("chapter_max_characters")
    values = (
        target,
        minimum,
        maximum,
        accepted_prior,
        remaining_scenes,
        chapter_target,
        chapter_minimum,
        chapter_maximum,
    )
    if not all(isinstance(value, int) for value in values):
        raise ValueError("scale.scene_length snippet is missing integer bounds")
    return (
        "This is a rolling scene envelope, not an equal-share chapter split. "
        f"The whole chapter must finish near {chapter_target} and inside {chapter_minimum}-{chapter_maximum} "
        f"non-whitespace characters; accepted earlier scenes currently total {accepted_prior}, with "
        f"{remaining_scenes} scene(s) still frozen after this one. "
        f"Draft toward {target} non-whitespace characters and finish only when this scene is at least "
        f"{minimum} and no more than {maximum} characters. Count Chinese characters and punctuation, "
        "not model tokens. Scene lengths may differ when their dramatic load differs. If short, deepen attempts and "
        "counteractions, spatial behavior, professional behavior already entailed by the script, dialogue or subtext "
        "among frozen present subjects, POV judgment, and immediate consequence inside the six beats. Do not add a "
        "new event, verifiable fact, character, discovery, procedure result, or ending.\n"
    )


def _text_revision_instruction(manifest: ContextManifest) -> str:
    refs = {snippet.ref for snippet in manifest.snippets}
    if "revision.request" not in refs:
        return ""
    if "revision.source_draft" not in refs:
        raise ValueError("A text revision requires the immutable source draft snippet")
    return (
        "Revision execution returns a full scene replacement, not a continuation, but it is not permission to "
        "resample an unrelated draft. Use revision.source_draft as the unaccepted scene to expand, compress, or "
        "correct according to the exact mode named in revision.request. For a net-expansion revision, preserve every "
        "compliant event, action chain, and substantive passage before adding safe dramatization; do not summarize, "
        "discard, or paraphrase the source into a shorter draft. For a fact correction, remove every sentence carrying "
        "an exact rejected token before rebuilding only that local passage. "
        "The Detail script, frozen subject dossiers, volume contract, continuity snippets, and revision.request "
        "override every conflicting invention in the source. Preserve useful prose only where it obeys those sources, "
        "and return one complete replacement scene rather than notes or an appended continuation.\n"
    )


def _text_scene_instruction(manifest: ContextManifest) -> str:
    refs = {snippet.ref for snippet in manifest.snippets}
    required = {"detail.chapter", "cast.subjects", "brief.world_rules", "scene.execution"}
    if not required.issubset(refs):
        missing = sorted(required - refs)
        raise ValueError(f"Scene generation context is missing frozen refs: {missing}")
    return (
        "This call executes one scene, not a whole chapter. Follow scene.execution's six beats in order and "
        "complete only detail.chapter.scene objective, conflict, turn, and result. Do not consume a later scene. "
        "brief.world_rules is the only world and professional rule source. Creative freedom applies to dramatization, "
        "not canon: use the frozen subjects' dossier traits to shape choices, embodied reactions, hesitation, subtext, "
        "and dialogue; use the existing place and already implied objects for spatial action; and elaborate ordinary "
        "professional behavior only where the scene objective already entails it. These details must not create a new "
        "verifiable proposition. Do not invent identifiers, ordinal labels, dates, numeric facts or percentages, "
        "including organizational labels such as 第一层, 第二层, 第3步, 第一条, 第二条, or 第三条; unless the frozen manifest contains the "
        "exact token, describe the action without numbering or layering it. For a list of logs, records, or objects, "
        "write 日志, 记录, or 一条记录 rather than inventing 第一条/第二条 labels. Do not invent "
        "institutions, locations, documents, permissions, prior discipline, operation history, evidence sources, "
        "procedure results, or investigation conclusions. Do not add any named or unnamed present actor or speaker "
        "outside cast.subjects. A historical_record may appear only through the recording or record explicitly "
        "required by the frozen scene and never gains present action. Quoted, transmitted, or recorded speech may "
        "dramatize only information directly stated in detail.chapter; it must not add a location, cause, accused actor, "
        "instruction, or evidence conclusion merely to make the scene richer. Do not turn a generic status, mark, tool, "
        "or action into a newly named workflow, permission, document, or durable professional rule to fill length. "
        "If current_chapter.previous_scene is present, treat its ending excerpt and result as the hard execution "
        "boundary for this scene: begin in that already-established state and write only what happens next. Do not "
        "restart the same approach, re-entry, travel, encounter, confrontation, explanation, or discovery that the "
        "previous scene has already completed, even when the current scene uses the same place or person. Do not "
        "write an alternate version of the previous scene before reaching this scene's own turn; continue directly "
        "from the final physical and knowledge state, then execute only the current scene's objective, conflict, turn, "
        "and result.\n"
    )


def _revision_contract(task_name: str, context: dict[str, Any]) -> str:
    material = context.get("material")
    revision = material.get("revision_request") if isinstance(material, dict) else None
    if not isinstance(revision, dict):
        return ""
    bounded_scope = _bounded_revision_scope(task_name)
    if bounded_scope:
        return (
            "The revision_request is stage-level editorial feedback, but this Provider operation owns only "
            f"{bounded_scope}. Apply only requirements that belong to this frozen unit. Requirements about "
            "sibling units are context constraints, not requests for additional output; never create, return, "
            "or rewrite a sibling unit. Return one complete replacement for the current unit inside its supplied "
            "schema and material boundary.\n"
        )
    return (
        "The revision_request is stage-level editorial feedback constrained by this call's supplied material and "
        "output schema. Return a complete replacement that executes the applicable direction without inventing "
        "additional output units or changing frozen story commitments.\n"
    )


def _output_budget_contract(
    context: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    budget = context.get("output_budget")
    if not isinstance(budget, dict):
        return ""
    item_cap = budget.get("item_cap")
    expected_items = budget.get("expected_items")
    field_char_cap = budget.get("field_char_cap")
    scene_cap = budget.get("scene_cap")
    if (
        not isinstance(expected_items, int)
        or not isinstance(item_cap, int)
        or not isinstance(field_char_cap, int)
    ):
        raise ValueError("Structured output budget is incomplete")
    scene_rule = (
        f" and no chapter may contain more than {scene_cap} scenes; the exact lower and upper bounds come from material.scale_projection"
        if isinstance(scene_cap, int)
        else ""
    )
    return (
        f"The output_budget is a hard response envelope sized for up to "
        f"{expected_items} items; return only semantically required items and never more than {item_cap}, "
        f"keep each item within about {field_char_cap} characters{scene_rule}. "
        "Array cardinality is governed by the JSON Schema below: every minItems and maxItems bound is mandatory "
        "and takes precedence over the generic instruction to return only semantically required items. "
        "Do not omit required keys to save space; prefer concise semantic text.\n"
    )


def _revision_direction(task_name: str, context: dict[str, Any]) -> str:
    material = context.get("material")
    revision = material.get("revision_request") if isinstance(material, dict) else None
    direction = revision.get("direction") if isinstance(revision, dict) else None
    if not isinstance(direction, str) or not direction.strip():
        return ""
    scope_note = (
        " Filter it through the current frozen unit boundary described above."
        if _bounded_revision_scope(task_name)
        else ""
    )
    return f"\nControlling stage revision direction.{scope_note}\n{direction.strip()}"


def _detail_preflight_recovery_contract(
    task_name: str,
    context: dict[str, Any],
) -> str:
    if task_name != "detail":
        return ""
    material = context.get("material")
    feedback = material.get("preflight_feedback") if isinstance(material, dict) else None
    source = material.get("recovery_source") if isinstance(material, dict) else None
    if not isinstance(feedback, dict) or not isinstance(source, dict):
        return ""
    blockers = feedback.get("blockers")
    codes = {
        str(item.get("code") or "")
        for item in blockers
        if isinstance(item, dict)
    } if isinstance(blockers, list) else set()
    repair_rules: list[str] = []
    if "detail_duplicate_job" in codes:
        repair_rules.append(
            "For detail_duplicate_job, use each editable chapter's exact chapter_beats.dramatic_job as its local "
            "ownership boundary. When adjacent chapters share a turn_ref, their whole contiguous sequence completes "
            "that turn once; remove submission, refusal, publication, verdict, or other endpoints from the chapter "
            "whose dramatic_job does not own them. recovery_source.required_removed_endpoints is the deterministic "
            "per-chapter removal contract: remove every named endpoint from that chapter instead of making a cosmetic "
            "wording change."
        )
    if "custody_handoff_conflict" in codes:
        repair_rules.append(
            "For custody_handoff_conflict, recovery_source.custody_repair_contracts is the deterministic state "
            "boundary. Continue from previous_state=free. If target_state=detained, an on-page scene must execute a "
            "re-arrest or surrender before any custody scene; if target_state=free_or_detained, keep the subject free "
            "unless an explicit on-page transition occurs. The established institution named allowed_institution may "
            "perform the transition without entering cast_ids, but never invent a named officer, new authority, or new "
            "procedure. preserved_dramatic_task is the custody-safe form of the frozen chapter job and is the sole "
            "creative task after the state transition; preserve its lawyer-mediated information transfer. Every source "
            "field or scene that assumed custody without that transition is intentionally "
            "withheld and must not be reconstructed. Never reset custody between chapter boundaries."
        )
    if {"clue_source_missing", "clue_lifecycle_incomplete"} & codes:
        repair_rules.append(
            "For clue_source_missing or clue_lifecycle_incomplete, do not invent a source, recording, document, or "
            "custodian merely to preserve an ungrounded label. Remove that invalid label or replace it with the exact "
            "already-established clue named in the source candidate, established_chapters, or frozen turns; only add "
            "source or verification actions already entailed by those materials."
        )
    code_specific_rules = " ".join(repair_rules)
    return (
        "material.preflight_feedback is deterministic feedback rebuilt from the immutable, immediately preceding "
        "Detail candidate that failed the whole-book preflight. material.recovery_source is a source-bound repair "
        "projection and the sole revision source. It exposes only editable_source_chapters; preserved chapter content "
        "and every source scene or field containing a required_removed_endpoint are intentionally withheld to prevent "
        "copying a known-invalid beat. Never reconstruct or paraphrase withheld content. Rebuild it only from the current "
        "chapter_beats.dramatic_job, the visible source_patch, frozen_cast_names, and preflight_feedback. Return only the "
        "chapters named by recovery_source.editable_chapter_refs, in that "
        "exact order; do not return any preserved_chapter_refs. The runtime deterministically restores every preserved "
        "chapter from the immutable candidate. Each returned patch must contain only purpose, scenes, and handoff; "
        "never return title, POV, cast_ids, chapter refs, slot order, or turn ownership because the runtime restores "
        "all of those frozen fields from the source. Repair only the listed defects instead of resampling unrelated "
        "story material. A returned editable chapter byte-for-byte identical to its source is a contract failure; every "
        "returned chapter must materially change. This recovery contract overrides any generic template wording that "
        "would make every chapter or segment independently complete a repeated turn's full cause/change. Adjacent "
        "chapters must perform different visible state changes rather than rediscover or reconfirm the same outcome. "
        "Keep every valid, source-grounded clue label stable, but do not preserve a label that the feedback explicitly "
        "identifies as lacking a frozen source. Never consume a later turn's climax, final publication, collapse, verdict, or "
        "resolution in the current turn. Never change a survival, death, custody, ownership, or knowledge state already "
        "frozen by upstream artifacts or by material.previous_segment_handoff.established_chapters, except for the one "
        "explicit custody transition required by recovery_source.custody_repair_contracts. A historical subject "
        "whose status remains unresolved must stay unresolved. The feedback is a diagnosis, not permission to invent a "
        "new actor, clue, authority, procedure, rule, or macro outcome. Before returning, compare each editable chapter "
        "against its source and silently verify that every required repair is present and every scene uses only the "
        "source chapter's frozen POV and cast_ids. material.selected_dossiers and present_actor_ids are exhaustive for "
        "this repair. A dossier marked reference_only may be mentioned only through the already-visible historical "
        "record and can never act, speak in the present, or enter cast_ids. "
        f"{code_specific_rules}\n"
    )


def _bounded_revision_scope(task_name: str) -> str:
    return {
        "cast": "the current subject_refs and matching role_demand_proposals dossier batch",
        "volumes": "the current volume_boundary and volume_spine_turns",
        "detail": "the current Detail segment and its scale_projection.chapter_beats",
    }.get(task_name, "")


def _proposal_contract(task_name: str) -> str:
    if task_name == "spine_review.proposal":
        return (
            "This call is an advisory semantic review of a structurally valid Spine candidate. Review only the "
            "frozen story_brief and proposed story_spine in material. Return pass only when every promised ending "
            "consequence is caused by explicit earlier choices or liabilities of the person who bears it; every major "
            "relationship or allegiance reversal has an earlier pressure, discovery, sacrifice, or decision that makes "
            "the reversal motivated; each relationship or external turn identifies the chooser, consequence bearer, "
            "or pressure source clearly enough for downstream Role Demand extraction. A stable functional label such as "
            "the supervisor or project lead is enough before Cast; never demand a personal name. An institution may remain "
            "the actor when it performs a policy, hearing, audit, or other genuinely institutional procedure that does not "
            "require one recurring person's independent choice. Evidence acquisition, institutional action, and verification "
            "must obey only the supplied world rules and plausible elapsed time; do not invent a legal or procedural rule "
            "that the Brief does not state. Private records may be voluntarily supplied when their provenance is plausible. "
            "world rules and plausible elapsed time; each cause materially consumes the preceding change; and repeated "
            "investigation steps do not merely collect interchangeable evidence. Professional, legal, or disciplinary "
            "Also report direct physical-state contradictions for the same subject across turns, such as being alive or "
            "present after an earlier death without an explicit timeline explanation. "
            "sanctions must arise from the sanctioned person's own action, omission, duty, or liability; another person's "
            "disclosure may expose that liability but does not transfer guilt. Collateral grief, illness, estrangement, or "
            "other harm to an innocent person may be caused by someone else's choice and does not require the injured person "
            "to have chosen or deserved it. Also reject an ending that introduces "
            "a result not established by the final turns. Enforce one exact final-three-turn contract. The pre-climax "
            "turn may assemble the final dilemma, maximum pressure, opposing positions, and evidence already available, "
            "but it must not complete the decisive proof, confirm the main truth, begin or finish the final ruling, revoke "
            "a qualification, exonerate a subject, or restart a project. In the code-owned climax turn, cause must pose the "
            "maximum confrontation that forces the protagonist to decide, while change must contain both the protagonist's "
            "irreversible choice and the resulting main answer, decisive institutional ruling, and promised professional "
            "or public consequences. Treat that ruling as part of the climax payoff, not as disqualifying administration. "
            "The aftermath may show only the resulting daily life, relationship state, and world order; it must not add a "
            "new determination, ruling, sanction, exoneration, construction decision, or repeated consequence. Do not report "
            "taste preferences, wording polish, internal monologue, missing scene "
            "detail, or optional complexity. An explicit choice made under already stated stakes is a sufficient motivation "
            "bridge at Spine resolution; do not demand scene beats. Return at most four highest-leverage root findings and "
            "group repeated symptoms under one finding instead of listing every instance. Every blocking finding must cite "
            "the smallest ordered turn_refs and prescribe "
            "a bounded causal repair suggestion that preserves the frozen Brief, exact turn count, milestone positions, "
            "and ending promise. Keep every claim and required_fix concise and within the schema's 800-character "
            "maximum; cite only the smallest contiguous turn window and never paste the whole Spine or repeat the same "
            "diagnosis across fields. Findings are evidence for a later human or deterministic decision; they do not by "
            "themselves block or trigger regeneration. Return verdict=pass with an empty findings list, or "
            "verdict=revise with concrete findings.\n"
        )
    if task_name == "role_demand_review.proposal":
        return (
            "This call is an advisory semantic review before role demands allocate named Cast slots. Review the "
            "frozen story_brief, story_spine, scale_plan, and proposed_role_demands in material. Return pass only when "
            "every demand is supported by its cited turns, cannot be merged into another returned subject, and owns a "
            "specific recurring choice, opposition, relationship consequence, or indispensable historical identity. "
            "Reject roster padding added only to satisfy the scale minimum, institution representatives created for a "
            "procedure, one-off helpers, arcs not established by the Spine, and historical subjects whose stable identity "
            "does not recur. Also reject any relationship turn without a non-protagonist demand that can actually make or "
            "bear its choice. When a professional, legal, or disciplinary consequence needs a recurring natural person, "
            "require the cited Spine turns to establish that same person's prior duty and own consequential choice, omission, "
            "or violation; never let Role Demand or Cast invent a late bribery, forgery, concealment, or duty merely to justify "
            "the promised sanction. Reject an allegiance reversal whose cited turns omit the pressure, loss, discovery, or "
            "decision that bridges the change. The scale range is dynamically derived from exact chapter capacity, but remains "
            "capacity rather than permission to invent duties; when the frozen minimum cannot "
            "be met by irreducible duties, require an upstream Spine repair rather than fabricated characters. Findings "
            "must cite the smallest ordered turn_refs. Choose the smallest contiguous evidence window that proves the "
            "finding and do not list every turn where only a symptom appears. A genuinely whole-arc issue may cite the "
            "complete supplied Spine instead of truncating its evidence. Cite demand_refs when an existing demand is "
            "responsible. Ignore "
            "names, prose style, optional complexity, and future scene detail. Return verdict=pass with no findings or "
            "verdict=revise with concrete evidence findings. Findings do not by themselves block or trigger "
            "regeneration.\n"
        )
    if task_name == "role_demand.proposal":
        return (
            "This call returns only the role demand proposal batch. Each demand is a casting slot for exactly one "
            "distinct named subject. Set narrative_role to protagonist, opposition, relationship, functional, or "
            "historical_record. Return exactly one protagonist role. The subject_mode/narrative_role pair is a "
            "closed decision table: protagonist, opposition, relationship, and functional always use actor; only "
            "narrative_role=historical_record may use subject_mode=historical_record. Never put a historical record "
            "into a present actor role, and never put a present actor into a historical_record role. In Chinese, "
            "历史主体只能写记录、证词、遗物、声音、遗产或缺席如何影响当代判断；不得写其在当下行动、说话、"
            "调查、选择、施压、互动或拥有 POV；不得把历史主体放进 present actor demand. Return exactly one protagonist role. Set subject_mode to actor for every present "
            "role, or historical_record only "
            "when one absent or past person's stable identity, voice, testimony, legacy, or remains recur across multiple "
            "spine turns and downstream stages must cite that same subject. For historical_record, required_change describes "
            "how the record or legacy changes meaning, credibility, ownership, or consequences across the story; never "
            "invent present action, present speech, or a POV for that subject. The "
            "runtime will create one subject per demand. Never split one character's duties, arc, or investigation "
            "into multiple demands: if two demands would be fulfilled by the same person, merge them into a single "
            "demand. material.scale_plan.cast_recommended_range is derived from this book's frozen length: its lower "
            "bound is the minimum viable ensemble and its upper bound is editorial guidance rather than a quota; "
            "material.scale_plan.cast_hard_max and output_budget.item_cap are hard ceilings. The actual returned count must "
            "equal the irreducible duties already present in story_spine: never aim for the midpoint, and never pad to the "
            "lower bound. If those duties cannot meet the lower bound required for this book scale, fail upstream rather "
            "than inventing a person. Derive only irreducible "
            "present agencies and indispensable historical subjects already required by story_spine. Every demand "
            "must cite the exact active_turn_refs that prove why one "
            "distinct actor must choose, obstruct, reveal, withhold, or change, or why one historical subject's identity, "
            "voice, testimony, legacy, or absence must remain stable. Do not create a clerk, lawyer, "
            "expert, colleague, resident representative, whistleblower, or anonymous helper merely to personify a "
            "procedure or alternate evidence path. An institution, department, court, committee, office, technical "
            "team, audit unit, association, hospital, police unit, or other service is not a character demand and "
            "must be omitted, even when it recurs across many turns. Never convert such an institution into a named "
            "leader, judge, engineer, officer, clerk, or representative. Include a person only when the spine already "
            "requires that same individual to make an independent irreversible choice that the institution cannot "
            "make. Every returned function must describe a human actor or an indispensable historical subject, never "
            "an organization. irreducibility must name the concrete choice, pressure, or consequence that cannot be "
            "merged into another returned subject; generic claims about richness, realism, or plot needs are invalid. "
            "Before returning, apply a removal test to every demand: name the exact cited turn whose choice, opposition, "
            "relationship consequence, or stable historical evidence would become impossible if this subject were "
            "removed. If the turn can still work through another returned subject or an institution, merge or omit the "
            "demand. Repeated appearances, shared employment, and participation in the same procedure do not by "
            "themselves prove a separate subject. "
            "The protagonist demand must cite both the first and final Spine turns so Text receives one continuous "
            "agency and consequence line. Every long-Spine relationship turn must be backed by at least one "
            "non-protagonist demand whose active_turn_refs includes that relationship turn; do not declare relationship "
            "progress without registering the other stable subject who chooses or bears its consequence. Do not invent "
            "any role, shortcut, or relationship absent from the frozen spine.\n"
        )
    if task_name == "cast_relation.proposal":
        return (
            "Return only direct relationship pressures already established by the supplied dossiers and their "
            "frozen dramatic duties. A relation exists only when both named subjects make choices that materially "
            "change the other subject's options, risk, trust, or responsibility. Omit speculative, procedural, "
            "one-way service, shared-evidence, and merely thematic associations. Never use words such as may, "
            "possibly, or potential to invent future pressure, and do not connect every subject to the protagonist "
            "or opposition by default. A historical_record relation is valid only when its established record or absence "
            "materially changes a present actor's choice; it never represents present interaction. Return only the "
            "smallest set of edges needed for the relationship carriers already required by the frozen Spine; do not "
            "optimize global graph connectivity, and leave unrelated subjects disconnected. Every type and pressure must describe an already "
            "established relationship and a concrete choice, trust shift, responsibility, or risk. Write pressure in "
            "the form '主体 A 已经做了具体动作 X，导致主体 B 已经失去/承担/暴露/改变 Y'. The action and result "
            "must be stated as completed facts grounded in the supplied dossiers, not a question, intention, forecast, "
            "or emotional possibility. Never use '能否', '是否', '会不会', '将会', '未来', '日后', '有望', or "
            "'推动公开' to turn an unresolved decision into a relation. If no such completed two-subject pressure "
            "is established, omit the edge; do not add a weak edge to keep the graph visually connected. The pressure text "
            "must contain both a visible agency signal (for example choose, refuse, reveal, withhold, threaten, "
            "protect, investigate, or continue) and a concrete consequence signal (loss, exposure, responsibility, "
            "trust change, risk, cost, or changed option). Phrases such as 'X作为某组，双方形成对抗', '关系复杂', "
            "'可能建立信任', or '双方存在联系' are not pressure and must be rewritten with the specific choice and "
            "what the other subject loses, risks, or must now do. vague, possible, potential, or merely thematic "
            "relationships are invalid. A one-sided investigation, intrusion, discovery, or evidence retrieval such "
            "as 'A 已深夜潜入取证' is not a relationship pressure by itself; delete it unless the same completed sentence "
            "states what B thereby loses, bears, is exposed to, or must now do. Before emitting JSON, inspect every edge and delete it when the pressure "
            "contains a question or unresolved decision such as '是否/能否/权衡是否继续', describes only one "
            "subject's reflection or one-way discovery such as '重新审视' or '调查发现某人的职位', or says an "
            "action 'will/may change' the other subject without stating the completed result. A completed coercion "
            "such as 'A 已经施压，迫使 B 转向媒体公开' is valid because it names both the choice and the changed "
            "option; a discovery without a choice or consequence is not. Do not call a future or merely possible harm "
            "an established consequence: phrases like '可能的报复', '可能失去', or '将面临' must be removed or replaced "
            "with a concrete harm that has already occurred. When material.contract_feedback is present, it is deterministic feedback "
            "from the immediately preceding failed relation-only attempt. Return a fresh complete batch, omit or rewrite every listed "
            "rejected edge, and include every missing required subject without repeating modal, one-way, or incomplete pressure. "
            "material.relationship_requirements is a deterministic hard contract: every required_subject_id must appear in at least one "
            "edge, and protagonist_subject_id must connect to at least one required subject. An empty relations array is valid only when "
            "required_subject_ids is empty; otherwise it will be rejected. "
            "never keep an edge merely to make the graph look connected. "
            "output_budget.item_cap is a ceiling, not a target.\n"
        )
    if task_name == "cast_review.proposal":
        return (
            "This call is an advisory semantic review before the current Cast dossier group enters the visible "
            "Character Bible. Review only story_brief, story_spine, role_demand_proposals, subject_refs, and "
            "proposed_dossiers in material. Return pass only when each dossier faithfully executes its frozen demand; "
            "background contains concrete identity, experience, and capability that already existed before the story; "
            "background must name a concrete pre-story person-level identity, workplace, prior duty, or lived event; "
            "abstract labels such as '腐败势力的代理人', '某方代表', '幕后人员', or '组织成员' are not a background "
            "and must be replaced with an established individual identity already supported by the Brief and Spine; "
            "conflict_history states a compatible prior responsibility, loss, or connection; present_stakes names a "
            "specific loss owned by that subject rather than punishment for someone else's act; drive and change have a "
            "visible motivation bridge in the cited Spine turns; and temperament plus speech_style provide distinct, "
            "repeatable behavior that Text can perform. Reject invented backstory needed only to justify a weak turn, "
            "contradictions with Brief or Spine, generic personality labels, duplicate dossier dimensions, and any present "
            "agency assigned to a historical_record. Do not request scene detail, prose polish, extra characters, new "
            "relationships, or changes to frozen demands. In particular, reject a conflict_history that invents bribery, "
            "forgery, concealment, violation, or a new duty absent from the frozen Brief and Spine just to rationalize a "
            "sanction or reversal; that is an upstream causal gap, not character depth. Every finding must cite subject_refs "
            "and demand_refs; cite only "
            "the smallest relevant ordered turn_refs when the issue depends on a turn. A genuinely whole-arc issue may "
            "cite the complete supplied Spine instead of truncating its evidence. Return verdict=pass with no findings "
            "or verdict=revise with concrete evidence findings. Findings do not by themselves block or trigger "
            "regeneration.\n"
        )
    if task_name == "cast":
        return (
            "Every dossier must be a distinct named character; no two subjects may share the same name, and one "
            "person must never occupy more than one subject slot. Give every subject a proper personal name (a "
            "real-sounding 人名), never a role descriptor such as 旧外套乘客 / 前值班员 / 机构代表 — put the role "
            "in function, not in name. material.reserved_names (when present) lists names already taken by other "
            "dossier groups of this same cast: never reuse or trivially vary them. Names such as someone's mother, "
            "former archivist, committee representative, protagonist, or anonymous witness are invalid role labels, "
            "not names. Every dossier must include concrete background, conflict_history, present_stakes, temperament, "
            "and speech_style that Text can perform without inventing history: background states prior identity and "
            "experience; conflict_history states the established relation to the central conflict; present_stakes names "
            "what can be concretely lost now; temperament states repeatable decisions under pressure; speech_style states "
            "sentence rhythm, vocabulary, silence, and expression habits. Never put runtime terms such as Prompt, "
            "Provider, Spine, Detail, model, upstream, or downstream inside character fields. Return exactly one dossier for "
            "every subject_ref supplied in this call. The runtime deterministically replaces each dossier's debut "
            "from its frozen role-demand turn position and the Run's exact code-owned chapter target; never expand the current "
            "batch in an attempt to coordinate debut windows for sibling subjects. Background must be a concrete "
            "person-level identity, workplace, position, prior duty, or lived event that existed before the story "
            "begins; abstract labels such as '腐败势力的代理人', '某方代表', '幕后人员', or '组织成员' are not "
            "backgrounds. Replace those labels with the individual's established identity and experience, and do not "
            "invent a personal identity that the frozen Brief and Spine do not support. A dossier is not ready when its "
            "background depends on events that happen only after the story begins, its conflict_history merely repeats "
            "function, its present_stakes says only that life or the future will be affected, or its temperament and "
            "speech_style are generic adjectives. For a historical_record, never write '不适用' or repeat the same "
            "placeholder in temperament and speech_style: describe instead how the record's wording, omissions, "
            "format, dialect, or recurring quoted phrasing can be performed and how it behaves under interpretation. "
            "Resolve those five dimensions in the first response. Never use the "
            "dossier to invent a past offense, duty, betrayal, or concealment that the frozen Brief and Spine did not "
            "establish merely to make a later consequence look motivated.\n"
        )
    if task_name == "detail":
        return (
            "material.world_rule_projection is the immutable structured projection of the Brief's world and "
            "professional rules. Preserve its future offsets, fixed times, recurrence, identity, and physical "
            "constraints; periodic or loop recurrence never authorizes repeating the same chapter result. "
            "material.volume_spine_turns is the exclusive macro story boundary for this segment. Across all contiguous "
            "chapter_beats that reference the same turn, collectively move from that turn's cause to its change exactly "
            "once. A repeated turn_ref means phased ownership such as attempt then counteraction or execution then "
            "consequence; it never requires each chapter or segment to replay the full cause/change. Each chapter must "
            "execute only its own dramatic_job without weakening or replacing the turn, and never enact an event, "
            "discovery, proof, decision, climax, or closure that belongs to any other turn. volume_contract is a "
            "runtime execution projection, not the full upstream artifact: closing_state is deliberately absent from "
            "non-final segments and, when present for the final segment, may only restate the result already executable "
            "from the supplied volume_spine_turns. previous_segment_handoff.completed_turn_refs and "
            "established_chapters are already "
            "planned canon for Detail: continue from them and never replay, rediscover, contradict, or rename those "
            "beats. established_chapters is cumulative across the whole book, not merely the immediately preceding "
            "segment. previous_segment_handoff.unresolved is the only open bridge into the first scene. Return exactly "
            "one chapter for each scale_projection.chapter_beats item in chapter_offset order. Each slot already "
            "contains the creative dramatic_job, length_hint, and causal turn_refs approved by the chapter-layout "
            "proposal; execute that job without returning or reassigning those metadata fields. Never fill a slot by "
            "replaying a completed turn, borrowing a later one, repeating a procedural submission, or inventing an "
            "unrelated investigation. Every item in "
            "selected_dossiers[].limits is a hard invariant. A historical_record may never act, speak, hold POV, or "
            "interact in the present. Keep institutions as institutions; do not invent a named official, covert "
            "helper, conspiracy, break-in, monitor tampering, hidden evidence, or other shortcut unless that exact "
            "action is required by the supplied turn. cast_ids contains only subjects physically present and acting "
            "in this chapter, not people merely mentioned in a record. The structured "
            "material.historical_record_ids list is a forbidden set: none of those IDs may appear in cast_ids. The "
            "structured material.present_actor_ids list is the only allowed source for present-day cast_ids; a "
            "historical record may be referenced only as a record, memory, or absence, never as an actor. Before "
            "returning, satisfy every structured material.debut_requirements item: the named subject must physically "
            "act or speak in cast_ids no later than latest_chapter. A debut window is two-sided: its first chapter is "
            "the earliest allowed appearance and its last chapter is the mandatory appearance deadline, not a loose "
            "suggestion. Keep every central document, recording, testimony, or object under the same specific label "
            "used by volume_spine_turns whenever it reappears; never collapse 实验室报告、漏洞报告、撤离记录 or other "
            "distinct clues into the generic words 报告、记录、证词. Before "
            "returning JSON, compare every cast_ids array against both structured lists, then compare every proposed "
            "title against reserved_titles and every established chapter title; reserved_titles are exact whole-stage "
            "exclusions, including titles attached to different events. Detail is a compact executable scene card "
            "whose scene count must obey scale_projection.scenes_per_chapter_min and "
            "scale_projection.scenes_per_chapter_max, "
            "not prose: keep each chapter roughly 300-700 Chinese characters, use 1-2 concise sentences for purpose, "
            "short actionable phrases for each scene field, and only the time, place, knowledge state, and pressure "
            "needed by the next chapter in handoff. Do not write dialogue, atmosphere, inner monologue, or literary "
            "filler. Any chapter target in scale_projection is the future prose budget, never a Detail word-count target.\n"
        )
    if task_name == "detail_layout.proposal":
        return (
            "This call returns one turn-window-scoped DetailLayoutProposalBatch for a single volume. The runtime has "
            "already partitioned the accepted volume into deterministic contiguous Spine windows; decide chapter "
            "boundaries only inside the supplied current window before scene-card expansion. material.story_spine.turns "
            "and volume_contracts[0].turn_refs are the exclusive causal range for this call. Never reference, replay, "
            "preview, or reassign a turn outside that range. "
            "material.world_rule_projection is the immutable Brief rule projection: recurring or loop rules may "
            "shape repeated forms, but every chapter slot must still create a distinct action, knowledge, relationship, "
            "or risk state. "
            "Preserve the exact specific label of every document, recording, testimony, or object named by the "
            "supplied turns when writing dramatic_job; do not replace distinct clues with generic 报告、记录、证词. "
            "When material.previous_window_layout exists, its completed_turn_refs and chapters are already frozen "
            "earlier layout. Continue after them without repeating their turn refs or dramatic jobs. For "
            "The previous_window_layout.completed_dramatic_jobs list is a hard exclusion set: do not return an "
            "exact repeat or a near-paraphrase of any listed job. A changed ending clause is still a repeat when it "
            "performs the same visible action, decision, discovery, loss, or consequence. Choose a different "
            "on-page change that advances the supplied turn instead of restating a completed endpoint. "
            "status=sufficient, return exactly one volume layout using the supplied volume_ref; never return an earlier "
            "or later volume. material.chapter_slots is the deterministic window chapter-count authority: return exactly one "
            "chapter proposal for every supplied slot, in slot order, without adding, dropping, or merging slots. The "
            "slots do not prescribe local events or the distribution among turns inside this window; you own those "
            "bounded creative choices. If the frozen window "
            "cannot support every slot without padding, return status=insufficient instead of shortening the array. "
            "Each chapter proposal contains only consecutive supplied turn_refs, one short dramatic_job describing a "
            "distinct on-page change, and length_hint compact/standard/expansive. Cover every turn in causal order; a "
            "turn may span adjacent chapters only when those chapters perform genuinely different dramatic jobs. Do "
            "not traverse the Spine slice more than once: repeated use of one turn must form one contiguous chapter "
            "run, and after any later turn appears no earlier turn may appear again. Before returning, scan the chapter "
            "array from left to right and verify that the first referenced turn position never decreases. Do "
            "not divide turns evenly, map one cause/change field to one chapter, or create chapters for filing, waiting, "
            "resubmitting, rechecking, receiving notice, or repeating a discovery unless that action creates a new "
            "irreversible choice, confrontation, loss, relationship shift, or external consequence. The runtime has already "
            "selected the current turn window's exact chapter-slot count inside scale_plan.chapter_range after reconciling "
            "scale_plan.book_chapter_range, Spine density, the accepted volume turn load, length_hint, allocated_chapters, "
            "and remaining_volume_range. The range is diagnostic context, not permission for the Provider to choose another "
            "count. Treat chapter_target and material.chapter_slots as the numeric authority. Provider output cannot move "
            "below or above it; use status=insufficient when the arc is genuinely underloaded. length_hint must describe each "
            "slot's actual load, never justify padding. "
            "scale_plan.minimum_chapter_surplus_over_turns is a deterministic capacity diagnostic. A positive surplus means a "
            "one-turn-per-chapter plan is invalid for status=sufficient: repeat suitable turn_refs across adjacent "
            "chapters and dramatize the causal bridge between that turn's supplied cause and change as distinct on-page "
            "phases such as attempt and counteraction, confrontation and local choice, verification and setback, or "
            "execution and consequence propagation. Detail owns these derived chapter-level actions: it may create the "
            "local attempt, obstacle, tactical choice, relationship reaction, or failed intermediate result needed to "
            "make the supplied cause produce the supplied change. Every phase must be causally necessary, perform a "
            "different visible change, and preserve the turn's frozen starting fact and final outcome. It must not add "
            "a new main clue, named actor, institution rule, authority, macro outcome, timeline fact, or subplot; local "
            "dramatic invention that only bridges the frozen endpoints is required craft work, not contract drift. "
            "If the supplied turns cannot "
            "support the minimum surplus this way, return status=insufficient instead of a numerically invalid "
            "sufficient layout. Choose the chapter plan in which every chapter owns an independent visible "
            "change; do not mechanically minimize, maximize, or evenly divide the count. Before returning "
            "status=sufficient, count "
            "the actual chapter arrays rather than describing counts in prose, and return diagnosis as an empty string. "
            "If the accepted Spine and Volumes "
            "cannot reach the minimum without padding or invented events, return status=insufficient, an empty volumes "
            "array, and a concrete diagnosis naming the underloaded arc; never fabricate capacity to satisfy a number.\n"
        )
    if task_name == "volume_boundary.proposal":
        return (
            "This call returns only the volume boundary proposal batch. A boundary is a whole volume arc, not a "
            "spine turn: group consecutive "
            "turns into complete arcs whose promise, escalation, climax, and local closure belong together. The runtime "
            "has already derived material.scale_plan.volume_target from the frozen chapter target and editorial volume "
            "capacity. Return exactly volume_target consecutive boundaries; you own where those boundaries fall, not "
            "how many exist. Balance the Spine turn load so every boundary can carry a complete local arc inside the "
            "code-owned volume_range and chapter_range. material.scale_plan.volume_candidate_cap is only the serialization "
            "ceiling. Never add, drop, or merge volumes to make the response easier.\n"
        )
    if task_name == "volumes":
        return (
            "Return exactly one volume contract for material.volume_boundary. Use only the events in "
            "material.volume_spine_turns; no adjacent-volume turn is available or may be invented. Never return "
            "the full turn_refs array or narrative-thread ids: the runtime owns boundary identity and ordering. Return "
            "one climax_turn_ref that exists in material.volume_spine_turns and lands in the final 40 percent of the "
            "volume. The climax text must dramatize that turn; closure may only summarize the final supplied turn and "
            "must not claim a fact that first appears in a later volume.\n"
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
        "it; findings may be an empty list. A blocking finding requires a direct conflict that prevents accepting "
        "this chapter; ambiguity, omitted explanation, or optional enrichment is at most a warning. Judge thematic "
        "and character-arc obligations through dramatized choices, consequences, and behavior; never require an "
        "explicit theme statement when the action already establishes the change. Each finding must cite an exact "
        "non-empty excerpt from chapter.content in evidence and list every relevant frozen subject id in subject_ids; "
        "use [] only when no subject is involved, which a character reviewer never does: every character finding "
        "must list at least one subject id taken from appearance_policy.roster, and a finding you cannot attribute to "
        "a roster subject must not be reported. For a character reviewer, a subject whose id is in "
        "appearance_policy.not_yet_eligible_subject_ids is compliant when absent. Report it only for an early "
        "appearance, with the exact excerpt that proves the early appearance. An appearance means the subject is on "
        "stage in a scene: acting, speaking, or physically present where the POV can perceive them. Being named in "
        "narration or dialogue, remembered, discussed, listed in a contact list, phoning or texting from off stage, "
        "or referred to without a name is not an appearance and is never an early_appearance finding. Resolve every "
        "name through appearance_policy.roster, which maps each frozen subject id to its name and to whether it may "
        "appear in this chapter; never guess an id from position, never report a person absent from the roster, and "
        "never override roster eligibility with a debut window inferred from anywhere else. A roster entry with "
        "eligible true may appear freely. Ensure every claim and evidence pair logically supports its severity. For "
        "a continuity reviewer, material.opening_chapter means this is the first chapter of the book: there is no "
        "earlier chapter, so never judge it against a predecessor and never treat its own plan or handoff as an "
        "earlier chapter. Otherwise compare the chapter opening against the end of previous_accepted_chapter.content. "
        "Also inspect recent_chapter_window as a bounded four-chapter structural history. Its dramatic_job, scene_results, "
        "handoff, accepted_ending, and state_changes are the authority for detecting non-adjacent re-discovery, evidence "
        "source drift, repeated dramatic work, and knowledge that appeared several chapters earlier. continuity_state "
        "groups evidence provenance, character knowledge, object state, unresolved clues, and explicit conflicts; do not "
        "invent facts outside those projections. Then check the current opening: "
        "a knowledge-state mismatch, a re-discovery of facts the POV already established, an invented past event "
        "that contradicts the previous chapter, or a time jump the prose contradicts is a blocking finding with the "
        "exact conflicting excerpt. A chapter break may move the story to a new time and place: opening in a different "
        "location, or after unstated hours, is normal craft and is a finding only when the prose presents the new "
        "scene as continuous with the previous ending, or when the elapsed time cannot accommodate what the chapter "
        "claims already happened. Also compare each internal scene boundary against current_detail_chapter.scenes "
        "in order: a later scene that replays an earlier scene's completed entry, encounter, confrontation, discovery, "
        "or location change, or jumps backward in place/time without a stated transition, is a blocking finding; cite "
        "the exact repeated or contradictory excerpt. Do not require a transitional passage for ordinary travel, but do "
        "require the prose to remain in the state produced by the preceding scene. Never require a transitional passage that narrates travel between two scenes. When "
        "story_state is supplied, treat each resolved entry as the current durable state for its subject and property: "
        "a passage that contradicts an entry (object state, prior event, character knowledge) is a blocking finding "
        "only when the entry has no supersession, reveal, or epistemic explanation. Treat current_detail_chapter, "
        "world_rule_projection, character_bible, previous_accepted_chapter (when present), and story_state (when present) as the "
        "complete durable-fact authority for this chapter. Report an invented_durable_fact blocking finding when the "
        "chapter establishes a reusable rule or procedure, permission or access right, institution or monitoring role, "
        "disciplinary or operation history, authoritative document or record, personal backstory, or evidence conclusion "
        "that is neither directly stated nor strictly entailed by those frozen sources. Cite the exact sentence that "
        "creates the new fact. This includes a newly specified repair process, an unregistered monitor and punishment, "
        "an onboarding note that invents career history, or a childhood relationship claim when the frozen sources do "
        "not establish it. Do not report sensory description, ordinary momentary action, a generic temporary object "
        "needed to perform the planned action, transient spatial choreography, dialogue subtext, or an immediate POV "
        "inference unless the prose presents it as a durable fact. For a prose reviewer, material.voice "
        "is the book-level narration contract: prose narrated in a different grammatical person than the voice "
        "promises (for example third person when the voice specifies first person) is a blocking finding; cite the "
        "chapter opening as evidence. Narration that already matches the promised person is not a finding at all.\n"
    )


def _evidence_contract(task_name: str, context: dict[str, Any]) -> str:
    if task_name != "text.evidence":
        return ""
    frozen_state = context.get("frozen_state")
    correction = (
        frozen_state.get("contract_correction")
        if isinstance(frozen_state, dict)
        else None
    )
    correction_instruction = (
        "This is the single bounded contract-correction attempt. Follow "
        "frozen_state.contract_correction exactly, but do not rewrite, continue, "
        "or reinterpret the accepted chapter. Return a complete replacement "
        "Evidence object rather than a patch.\n"
        if isinstance(correction, dict)
        else ""
    )
    return correction_instruction + (
        "Return at most eight durable claims supported only by the supplied evidence_candidates. For each claim, "
        "select one to three span_ids exactly as listed; span_ids has a hard maximum of three entries, so never "
        "return four or more. Do not copy quote text or return character offsets; deterministic runtime code owns "
        "the source spans. Exclude decorative detail, interpretation, and claims not directly supported by the "
        "selected spans. Every claim.kind must be exactly one of fact, character, relationship, foreshadow, or spine; "
        "assertion, story, and transition are state.type values and must never be used as claim.kind. Every claim must "
        "choose exactly one discriminated state object. Use state.type=story when "
        "the claim has no precise frozen subject/property state. Use state.type=assertion only with a subject_id "
        "listed in frozen_state.frozen_subjects (or the literal story for a book-level state) and an explicit "
        "property_key, value, and epistemic_status. Use stable property namespaces when applicable: "
        "evidence.<clue>.source, evidence.<clue>.owner, or evidence.<clue>.custody for provenance; "
        "knowledge.<fact> for what a subject knows; "
        "object.<object>.state for durable object state, and clue.<clue>.status for unresolved or paid-off clues. "
        "Reuse an existing property_key for the same durable subject property rather than creating a chapter-specific "
        "synonym. If that subject/property already exists, use state.type=transition with its source_fact_id instead "
        "of asserting it again. Use "
        "state.type=transition only with one source_fact_id exactly listed in frozen_state.story_state.entries, one "
        "action of supersedes or resolves, a new value, and epistemic_status. For a transition, deterministic runtime "
        "code derives the subject, property, lifecycle, and source links from source_fact_id; do not return those "
        "fields yourself. Never combine story, assertion, and transition fields in one state object.\n"
    )


__all__ = ["render_structured_prompt", "render_text_prompt"]
