from __future__ import annotations

import hashlib
import json

import pytest

from novel_workflow.memory.canon_store import CanonFact, CanonStore
from novel_workflow.memory.wiki_projection import WikiProjectionStore
from novel_workflow.api.sse import sse_payload
from novel_workflow.output_contracts.artifacts_vnext import ContextManifest
from novel_workflow.storage.context_manifest_store import ContextManifestStore
from novel_workflow.storage.domain_outbox import DomainOutbox
from novel_workflow.storage.event_projection import EventProjection
from novel_workflow.storage.narrative_run_repository import ExportPreferences, NarrativeRunRepository, ProviderBinding, RunReadModel
from novel_workflow.storage.operation_store import OperationStore
from novel_workflow.storage.provider_input_store import (
    ProviderInputPayload,
    ProviderOutputContract,
)
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from tests.phase27_bindings import cover_asset_binding, provider_binding


def bindings() -> dict[str, ProviderBinding]:
    return {stage: provider_binding(stage) for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")}


def test_run_repository_separates_definition_from_graph_projection(tmp_path) -> None:
    store = NarrativeRunRepository(tmp_path / "runs")
    definition = store.create(run_id="run-1", project_id="project-1", workflow_id="workflow-1", workflow_revision="phase27-vnext", workflow_digest="a" * 64, quality_mode="balanced", inputs={"genre": "悬疑"}, scale_profile=NarrativeScaleProfile(word_target_soft=4_000), provider_bindings=bindings(), cover_asset_binding=cover_asset_binding(), export_preferences=ExportPreferences(format="zip"))
    projected = store.project("run-1", RunReadModel(run_id="run-1", project_id="project-1", thread_id="run-1", status="running", active_stage_id="brief", stage_status={"brief": "running", "spine": "locked", "cast": "locked", "volumes": "locked", "detail": "locked", "text": "locked", "cover": "locked", "export": "locked"}, updated_at="ignored"))
    assert definition.scale_profile.word_target_soft == 4_000
    assert projected.status == "running"
    assert "status" not in store.definition("run-1").model_dump()


def test_event_projection_is_idempotent(tmp_path) -> None:
    events = EventProjection(tmp_path / "events")
    first = events.append("run-1", event_id="run-1:start", type="run.started", stage_id="brief")
    duplicate = events.append("run-1", event_id="run-1:start", type="run.started", stage_id="brief")
    second = events.append("run-1", event_id="run-1:brief", type="node.started", stage_id="brief")
    assert first == duplicate
    assert second.sequence == 2
    assert [item.sequence for item in events.read("run-1", after=first.sequence)] == [2]
    assert sse_payload(second.model_dump(mode="json")).startswith("id: 2\n")


def test_operation_receipt_does_not_repeat_completed_result(tmp_path) -> None:
    store = OperationStore(tmp_path / "operations")
    provider_input = _provider_input()
    pending = store.begin_provider(run_id="run-1", operation_key="run-1:brief:generate", kind="generation", provider_profile_id="fake", model="fake", provider_input=provider_input)
    assert store.begin_provider(run_id="run-1", operation_key="run-1:brief:generate", kind="generation", provider_profile_id="fake", model="fake", provider_input=provider_input) == pending
    completed = store.succeed("run-1", "run-1:brief:generate", {"title": "雾港"}, usage={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3})
    assert store.succeed("run-1", "run-1:brief:generate", {"title": "不同"}) == completed


def test_provider_regeneration_preserves_prior_input_and_receipt(tmp_path) -> None:
    store = OperationStore(tmp_path / "operations")
    first_input = _provider_input(revision="初稿")
    first = store.begin_provider(
        run_id="run-1",
        operation_key="run-1:chapter-1:generate:1",
        kind="chapter_generation",
        provider_profile_id="fake",
        model="fake",
        provider_input=first_input,
    )
    succeeded = store.succeed(
        "run-1",
        first.operation_key,
        {"chapter_version_id": "chapter-1-v1", "content": "旧候选正文"},
    )

    revised_input = _provider_input(revision="增强人物冲突", attempt=2)
    second = store.begin_provider(
        run_id="run-1",
        operation_key="run-1:chapter-1:generate:2",
        kind="chapter_generation",
        provider_profile_id="fake",
        model="fake",
        provider_input=revised_input,
    )
    failed = store.fail(
        "run-1",
        second.operation_key,
        {"type": "ProviderOperationError", "message": "timeout"},
    )

    assert first.request_signature != second.request_signature
    assert first.provider_input_ref != second.provider_input_ref
    assert store.read("run-1", first.operation_key) == succeeded
    assert store.read("run-1", second.operation_key) == failed
    assert store.provider_inputs.read("run-1", first.provider_input_ref).input == first_input
    assert store.provider_inputs.read("run-1", second.provider_input_ref).input == revised_input
    assert succeeded.status == "succeeded"
    assert failed.status == "failed"


def test_provider_operation_key_rejects_changed_input_and_snapshots_are_content_addressed(tmp_path) -> None:
    store = OperationStore(tmp_path / "operations")
    first_input = _provider_input(revision="初稿")
    receipt = store.begin_provider(
        run_id="run-1",
        operation_key="run-1:chapter-1:generate:1",
        kind="chapter_generation",
        provider_profile_id="fake",
        model="fake",
        provider_input=first_input,
    )
    snapshot = store.provider_inputs.read("run-1", receipt.provider_input_ref)

    with pytest.raises(ValueError, match="different request"):
        store.begin_provider(
            run_id="run-1",
            operation_key=receipt.operation_key,
            kind="chapter_generation",
            provider_profile_id="fake",
            model="fake",
            provider_input=_provider_input(revision="改写", attempt=1),
        )

    assert store.provider_inputs.write(
        run_id="run-1",
        operation_key=receipt.operation_key,
        input=first_input,
    ) == snapshot
    assert len(store.provider_inputs.list("run-1")) == 1


@pytest.mark.parametrize(
    "binding",
    [
        {"provider_profile_id": "fake", "api_key": "secret"},
        {"provider_template": {"auth_header": "authorization"}},
        {"provider_template": {"prompt_cache_key_header": ""}},
        {"provider_template": {"custom_headers": {}}},
    ],
)
def test_provider_input_rejects_secret_or_header_configuration(
    binding: dict,
) -> None:
    with pytest.raises(ValueError, match="forbidden secret or header field"):
        _provider_input(binding=binding)


def _provider_input(
    *,
    revision: str = "",
    attempt: int = 1,
    binding: dict | None = None,
) -> ProviderInputPayload:
    context = {"chapter": "chapter-1", "revision": revision}
    return ProviderInputPayload(
        stage_id="text",
        task_name="text",
        attempt=attempt,
        chapter_id="chapter-1",
        provider_binding=binding or {"provider_profile_id": "fake", "model": "fake"},
        prompt_template_id="prompt-text",
        prompt_digest="a" * 64,
        rendered_prompt=f"正文输入：{context}",
        structured_context=context,
        output_contract=ProviderOutputContract(
            kind="plain_text",
            plain_text_contract="完整纯文本章节",
        ),
    )


def test_outbox_commits_canon_and_wiki_once(tmp_path) -> None:
    canon = CanonStore(tmp_path / "canon")
    wiki = WikiProjectionStore(tmp_path / "wiki")
    outbox = DomainOutbox(tmp_path / "outbox", canon=canon, wiki=wiki)
    fact = CanonFact(fact_id="fact-1", claim="林默找到母带", evidence_refs=["evidence-1"], chapter_version_id="chapter-1-v1")
    outbox.enqueue("run-1", "outbox-1", "canon-1", [fact])
    assert outbox.flush("run-1", "outbox-1") == outbox.flush("run-1", "outbox-1")
    assert canon.facts("run-1") == [fact]
    assert len(wiki.list("run-1")) == 1


def test_outbox_recovers_a_crash_before_canon(tmp_path, monkeypatch) -> None:
    canon_root = tmp_path / "canon"
    wiki_root = tmp_path / "wiki"
    outbox_root = tmp_path / "outbox"
    canon = CanonStore(canon_root)
    wiki = WikiProjectionStore(wiki_root)
    outbox = DomainOutbox(outbox_root, canon=canon, wiki=wiki)
    fact = _canon_fact("before-canon")
    outbox.enqueue("run-crash", "outbox-before-canon", "canon-before-canon", [fact])

    def crash_before_canon(*args, **kwargs):
        raise RuntimeError("process stopped before Canon commit")

    monkeypatch.setattr(canon, "commit", crash_before_canon)
    with pytest.raises(RuntimeError, match="before Canon"):
        outbox.flush("run-crash", "outbox-before-canon")

    assert outbox.read("run-crash", "outbox-before-canon").status == "failed"
    assert canon.facts("run-crash") == []
    assert wiki.list("run-crash") == []

    recovered = DomainOutbox(
        outbox_root,
        canon=CanonStore(canon_root),
        wiki=WikiProjectionStore(wiki_root),
    )
    assert recovered.flush("run-crash", "outbox-before-canon").status == "committed"
    assert recovered.canon.facts("run-crash") == [fact]
    assert len(recovered.wiki.list("run-crash")) == 1


def test_outbox_recovers_a_crash_after_canon(tmp_path, monkeypatch) -> None:
    canon_root = tmp_path / "canon"
    wiki_root = tmp_path / "wiki"
    outbox_root = tmp_path / "outbox"
    canon = CanonStore(canon_root)
    wiki = WikiProjectionStore(wiki_root)
    outbox = DomainOutbox(outbox_root, canon=canon, wiki=wiki)
    fact = _canon_fact("after-canon")
    outbox.enqueue("run-crash", "outbox-after-canon", "canon-after-canon", [fact])

    def crash_before_wiki(*args, **kwargs):
        raise RuntimeError("process stopped before Wiki projection")

    monkeypatch.setattr(wiki, "project", crash_before_wiki)
    with pytest.raises(RuntimeError, match="before Wiki"):
        outbox.flush("run-crash", "outbox-after-canon")

    assert outbox.read("run-crash", "outbox-after-canon").status == "failed"
    assert canon.facts("run-crash") == [fact]
    assert wiki.list("run-crash") == []

    recovered = DomainOutbox(
        outbox_root,
        canon=CanonStore(canon_root),
        wiki=WikiProjectionStore(wiki_root),
    )
    assert recovered.flush("run-crash", "outbox-after-canon").status == "committed"
    assert recovered.canon.facts("run-crash") == [fact]
    assert len(recovered.wiki.list("run-crash")) == 1


def test_outbox_recovers_after_canon_and_wiki_before_receipt(tmp_path, monkeypatch) -> None:
    import novel_workflow.storage.domain_outbox as outbox_module

    canon_root = tmp_path / "canon"
    wiki_root = tmp_path / "wiki"
    outbox_root = tmp_path / "outbox"
    canon = CanonStore(canon_root)
    wiki = WikiProjectionStore(wiki_root)
    outbox = DomainOutbox(outbox_root, canon=canon, wiki=wiki)
    fact = _canon_fact("before-receipt")
    outbox.enqueue("run-crash", "outbox-before-receipt", "canon-before-receipt", [fact])
    original_write = outbox_module.atomic_write_json

    def crash_before_receipt(path, value):
        if value.get("status") == "committed":
            raise RuntimeError("process stopped before Outbox receipt")
        return original_write(path, value)

    monkeypatch.setattr(outbox_module, "atomic_write_json", crash_before_receipt)
    with pytest.raises(RuntimeError, match="before Outbox receipt"):
        outbox.flush("run-crash", "outbox-before-receipt")

    assert outbox.read("run-crash", "outbox-before-receipt").status == "queued"
    assert canon.facts("run-crash") == [fact]
    assert len(wiki.list("run-crash")) == 1

    monkeypatch.setattr(outbox_module, "atomic_write_json", original_write)
    recovered = DomainOutbox(
        outbox_root,
        canon=CanonStore(canon_root),
        wiki=WikiProjectionStore(wiki_root),
    )
    assert recovered.flush("run-crash", "outbox-before-receipt").status == "committed"
    assert recovered.canon.facts("run-crash") == [fact]
    assert len(recovered.wiki.list("run-crash")) == 1


def _canon_fact(suffix: str) -> CanonFact:
    return CanonFact(
        fact_id=f"fact-{suffix}",
        claim=f"可恢复事实 {suffix}",
        evidence_refs=[f"evidence-{suffix}"],
        chapter_version_id="chapter-1-v1-accepted",
    )


def test_context_manifest_store_is_immutable_and_run_scoped(tmp_path) -> None:
    store = ContextManifestStore(tmp_path / "context_manifests")
    manifest = _context_manifest()

    first = store.write("run-1", attempt=1, manifest=manifest)
    replay = store.write("run-1", attempt=1, manifest=manifest)

    assert replay == first
    with pytest.raises(FileNotFoundError):
        store.read("run-2", first.manifest_id)

    path = tmp_path / "context_manifests" / "run-1" / f"{first.manifest_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["manifest"]["snippets"][0]["text"] = "tampered"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        store.read("run-1", first.manifest_id)


def test_context_manifest_branch_copy_preserves_only_explicit_record(tmp_path) -> None:
    store = ContextManifestStore(tmp_path / "context_manifests")
    first = store.write("source", attempt=1, manifest=_context_manifest("chapter-1"))
    store.write("source", attempt=1, manifest=_context_manifest("chapter-2"))

    copied = store.copy(
        source_run_id="source",
        target_run_id="target",
        manifest_id=first.manifest_id,
    )

    assert copied.manifest_id == first.manifest_id
    assert [item.chapter_id for item in store.list("target")] == ["chapter-1"]


def _context_manifest(chapter_id: str = "chapter-1") -> ContextManifest:
    text = f"script for {chapter_id}"
    payload = {
        "task": chapter_id,
        "required": ["detail.chapter"],
        "optional": [],
        "forbidden": ["full_canon"],
        "snippets": [{
            "ref": "detail.chapter",
            "purpose": "chapter_script",
            "text": text,
            "source_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }],
        "budget": {"input_chars": len(text), "output_tokens": 100},
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["manifest_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return ContextManifest.model_validate(payload)
