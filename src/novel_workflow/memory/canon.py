from __future__ import annotations

import copy
import hashlib
import re
from datetime import datetime, timezone
from typing import Any


CONFLICT_RESOLUTIONS = {"keep_existing", "replace_existing"}


def preview_canon_writebacks(
    existing_facts: list[dict[str, Any]],
    writebacks: list[dict[str, Any]],
    *,
    chapter_id: str,
    chapter: str,
    chapter_version: int,
    artifact_signature: str,
) -> dict[str, Any]:
    active = [item for item in existing_facts if item.get("status", "active") == "active"]
    candidates: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for index, item in enumerate(writebacks, start=1):
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or item.get("title") or "").strip()
        fact = str(item.get("fact") or item.get("content") or "").strip()
        if not target or not fact:
            continue
        claim_key = claim_key_for(item, fact)
        source = {
            "stage": "chapter_text",
            "chapter_id": chapter_id,
            "chapter": chapter,
            "chapter_version": chapter_version,
            "artifact_signature": artifact_signature,
        }
        candidate_id = f"canon-candidate-{chapter_id}-v{chapter_version}-{index}"
        candidate = {
            "id": candidate_id,
            "target": target,
            "claim_key": claim_key,
            "fact": fact,
            "normalized_fact": normalize_fact(fact),
            "source": source,
            "writeback": {**copy.deepcopy(item), "claim_key": claim_key},
            "status": "proposed",
        }
        same_claim = [item for item in active if item.get("target") == target and item.get("claim_key") == claim_key]
        duplicate = next((item for item in same_claim if normalize_fact(str(item.get("fact") or "")) == candidate["normalized_fact"]), None)
        if duplicate:
            candidate.update({"status": "duplicate", "existing_fact_id": duplicate.get("id")})
        elif same_claim:
            existing = same_claim[-1]
            conflict_id = _conflict_id(target, claim_key, str(existing.get("id") or ""), candidate_id)
            candidate.update({"status": "conflict", "conflict_id": conflict_id})
            conflicts.append(
                {
                    "id": conflict_id,
                    "status": "pending",
                    "target": target,
                    "claim_key": claim_key,
                    "existing_fact_id": existing.get("id"),
                    "existing_fact": str(existing.get("fact") or ""),
                    "incoming_candidate_id": candidate_id,
                    "incoming_fact": fact,
                    "source": source,
                }
            )
        candidates.append(candidate)
    return {"candidates": candidates, "conflicts": conflicts}


def commit_canon_writebacks(
    existing_facts: list[dict[str, Any]],
    existing_conflicts: list[dict[str, Any]],
    chapter: dict[str, Any],
) -> dict[str, Any]:
    proposal = chapter.get("writeback_proposal")
    if isinstance(proposal, dict) and proposal.get("status") in {"rejected", "not_required"}:
        return {"facts": copy.deepcopy(existing_facts), "conflicts": copy.deepcopy(existing_conflicts), "effective_writebacks": [], "committed": [], "resolved": []}
    if isinstance(proposal, dict) and proposal.get("status") == "accepted":
        preview = proposal.get("canon") if isinstance(proposal.get("canon"), dict) else preview_canon_writebacks(
            existing_facts,
            _dict_list(proposal.get("wiki_writebacks")),
            chapter_id=str(chapter.get("id") or ""),
            chapter=str(chapter.get("title") or ""),
            chapter_version=int(chapter.get("version") or 0),
            artifact_signature=str(proposal.get("artifact_signature") or ""),
        )
        resolutions = proposal.get("conflict_resolutions") if isinstance(proposal.get("conflict_resolutions"), dict) else {}
    else:
        preview = preview_canon_writebacks(
            existing_facts,
            _dict_list(chapter.get("wiki_writebacks")),
            chapter_id=str(chapter.get("id") or ""),
            chapter=str(chapter.get("title") or ""),
            chapter_version=int(chapter.get("version") or 0),
            artifact_signature=str(chapter.get("commit_signature") or ""),
        )
        resolutions = {}
    facts = copy.deepcopy(existing_facts)
    conflicts = copy.deepcopy(existing_conflicts)
    effective: list[dict[str, Any]] = []
    committed: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    by_id = {str(item.get("id") or ""): item for item in facts}
    for candidate in preview.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        status = candidate.get("status")
        if status == "duplicate":
            existing = by_id.get(str(candidate.get("existing_fact_id") or ""))
            if existing is not None:
                source = candidate.get("source") or {}
                if source not in existing.setdefault("sources", []):
                    existing["sources"].append(source)
                existing["last_seen_at"] = _now()
            continue
        if status == "conflict":
            conflict_id = str(candidate.get("conflict_id") or "")
            resolution = resolutions.get(conflict_id)
            if resolution not in CONFLICT_RESOLUTIONS:
                conflict = next((item for item in preview.get("conflicts", []) if item.get("id") == conflict_id), None)
                if isinstance(conflict, dict) and not any(item.get("id") == conflict_id for item in conflicts):
                    conflicts.append(copy.deepcopy(conflict))
                continue
            conflict = next((item for item in preview.get("conflicts", []) if item.get("id") == conflict_id), None)
            existing = by_id.get(str(conflict.get("existing_fact_id") if isinstance(conflict, dict) else ""))
            if resolution == "keep_existing":
                resolved.append({"id": conflict_id, "resolution": resolution, "target": candidate.get("target")})
                conflicts.append({**copy.deepcopy(conflict or {}), "status": "resolved", "resolution": resolution, "resolved_at": _now()})
                continue
            if existing is not None:
                existing["status"] = "superseded"
                existing["superseded_at"] = _now()
            resolved.append({"id": conflict_id, "resolution": resolution, "target": candidate.get("target")})
            conflicts.append({**copy.deepcopy(conflict or {}), "status": "resolved", "resolution": resolution, "resolved_at": _now()})
        if status not in {"proposed", "conflict"} or (status == "conflict" and resolutions.get(str(candidate.get("conflict_id") or "")) != "replace_existing"):
            continue
        fact = _fact_from_candidate(candidate, proposal)
        facts.append(fact)
        by_id[str(fact["id"])] = fact
        effective.append(copy.deepcopy(candidate.get("writeback") or {}))
        committed.append({"id": fact["id"], "target": fact["target"], "claim_key": fact["claim_key"]})
    return {"facts": facts, "conflicts": conflicts, "effective_writebacks": effective, "committed": committed, "resolved": resolved}


def claim_key_for(item: dict[str, Any], fact: str) -> str:
    explicit = str(item.get("claim_key") or item.get("attribute") or item.get("key") or "").strip()
    return explicit or f"statement:{hashlib.sha1(normalize_fact(fact).encode('utf-8')).hexdigest()[:12]}"


def normalize_fact(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def effective_writebacks_for_proposal(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(proposal.get("canon"), dict):
        return _dict_list(proposal.get("wiki_writebacks"))
    resolutions = proposal.get("conflict_resolutions") if isinstance(proposal.get("conflict_resolutions"), dict) else {}
    result: list[dict[str, Any]] = []
    for candidate in proposal["canon"].get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("status") == "proposed" or (
            candidate.get("status") == "conflict"
            and resolutions.get(str(candidate.get("conflict_id") or "")) == "replace_existing"
        ):
            result.extend(_dict_list([candidate.get("writeback")]))
    return result


def _fact_from_candidate(candidate: dict[str, Any], proposal: dict[str, Any] | None) -> dict[str, Any]:
    source = copy.deepcopy(candidate.get("source") or {})
    fact_id = f"canon-fact-{hashlib.sha1(f'{candidate.get('id')}:{candidate.get('normalized_fact')}'.encode('utf-8')).hexdigest()[:16]}"
    return {
        "id": fact_id,
        "target": candidate.get("target"),
        "claim_key": candidate.get("claim_key"),
        "fact": candidate.get("fact"),
        "normalized_fact": candidate.get("normalized_fact"),
        "status": "active",
        "sources": [source],
        "created_at": _now(),
        "proposal_id": proposal.get("id") if isinstance(proposal, dict) else "",
    }


def _conflict_id(target: str, claim_key: str, existing_id: str, candidate_id: str) -> str:
    raw = f"{target}\0{claim_key}\0{existing_id}\0{candidate_id}"
    return f"canon-conflict-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
