from __future__ import annotations

import pytest
import asyncio
import threading
import time
from types import SimpleNamespace

from novel_workflow.memory.wiki import WikiStore
from tests.fakes import FakeImageProvider, FakeTextProvider
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.schemas import ProviderProfile
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.templates import default_workflow, materialize_workflow_for_execution
from tests.workflow_runner_harness import detail_outline_fixture


FAKE_FALLBACK = FakeTextProvider()


def fake_registry(provider: FakeTextProvider | None = None) -> ProviderRegistry:
    text = provider or FakeTextProvider()
    return ProviderRegistry(
        text_provider=text,
        image_provider=FakeImageProvider(),
        text_providers={"openai-compatible": text},
        image_providers={"openai-compatible-image": FakeImageProvider()},
    )


@pytest.mark.asyncio
async def test_default_workflow_runs_with_test_fake_provider(tmp_path):
    workflow = default_workflow()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()
    run_id = "test-run"
    store.create(run_id, workflow, {"project_id": "p1", "title": "雾港测试"})

    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, {"project_id": "p1", "title": "雾港测试"})

    assert events[0]["type"] == "run_started"
    assert events[-1]["type"] == "run_completed"
    assert any(event["type"] == "memory_context_loaded" for event in events)
    assert any(event["type"] == "memory_writeback_completed" for event in events)
    assert any(event["type"] == "quality_check_completed" for event in events)
    assert any(event["type"] == "chapter_progress_updated" for event in events)
    assert any(event["type"] == "phase_changed" and event.get("phase") == "writing" for event in events)
    assert any(event["type"] == "chapter_started" for event in events)
    assert any(event["type"] == "chapter_delta" for event in events)
    assert any(event["type"] == "chapter_completed" for event in events)
    assert not any(event["type"] == "variant_generated" for event in events)
    assert not any(event["type"] == "variant_judged" for event in events)
    assert not any(event["type"] == "best_variant_selected" for event in events)
    assert any(event["type"] == "worldbuilding_updated" for event in events)
    assert any(event["type"] == "wiki_state_updated" for event in events)
    assert any(event["type"] == "character_graph_updated" for event in events)
    assert any(event["type"] == "approval_required" for event in events)
    assert any(event["type"] == "artifact_approved" for event in events)
    saved = store.read(run_id)
    assert "chapters" in saved["state"]["artifacts"]
    assert saved["state"]["quality_events"]
    assert saved["state"]["quality_reports"]
    assert saved["state"]["chapter_progress"]
    assert saved["state"]["chapter_drafts"]
    assert not saved["state"]["selected_variants"]
    assert saved["state"]["token_estimates"]
    assert saved["state"]["worldbuilding_state"]
    assert saved["state"]["wiki_state"]
    assert saved["state"]["character_graph"]["nodes"]
    assert saved["state"]["wiki_refs"]
    assert saved["state"]["memory_contexts"]
    assert saved["state"]["story_bible"]["world_rules"]
    assert saved["state"]["chapter_context_packets"]
    assert saved["state"]["foreshadow_ledger"]
    assert saved["state"]["continuity_state"]["chapter_summaries"] >= 1
    assert any(event["type"] == "chapter_context_built" for event in events)
    assert any(event["type"] == "story_bible_updated" for event in events)
    assert any(event["type"] == "quality_check_started" for event in events)


def test_default_workflow_is_acyclic():
    from novel_workflow.workflows.compiler import NovelWorkflowCompiler

    order = NovelWorkflowCompiler().compile_order(default_workflow())
    assert [node.id for node in order][0] == "info"


def test_default_workflow_does_not_expose_wiki_as_node():
    workflow = default_workflow()
    node_types = {node.type for node in workflow.nodes}
    assert "wiki_writeback" not in node_types
    assert "wiki_query" not in node_types
    assert all("wiki" not in node.id.lower() for node in workflow.nodes)


def test_default_workflow_does_not_expose_quality_gate_as_node():
    workflow = default_workflow()
    node_types = {node.type for node in workflow.nodes}
    node_ids = {node.id for node in workflow.nodes}
    assert "quality_gate" not in node_types
    assert "quality" not in node_ids
    assert all(edge.source != "quality" and edge.target != "quality" for edge in workflow.edges)


def test_default_workflow_has_stage_configuration():
    workflow = default_workflow()
    assert workflow.global_inputs
    assert workflow.provider_profiles
    assert workflow.prompt_templates
    for node in workflow.nodes:
        assert node.input_schema
        if node.type != "export_artifact":
            assert node.provider_profile_id
            assert node.model_settings.model


def test_info_recommend_brief_schema_and_quality_policy():
    workflow = default_workflow()
    info = next(node for node in workflow.nodes if node.id == "info")
    fields = {field.key: field for field in info.input_schema}
    required_keys = {
        "genre",
        "target_length",
        "target_words_range",
        "audience",
        "core_concept",
        "keywords",
        "taboos",
        "reference_mode",
    }
    reference_keys = {"reference_keywords", "reference_query_intent", "reference_urls", "knowledge_base_doc_ids", "enable_web_search", "reference_summary"}
    assert workflow.version == "1.0.5-parallel-delivery"
    assert required_keys <= set(fields)
    assert all(fields[key].required for key in required_keys)
    assert reference_keys <= set(fields)
    assert fields["reference_mode"].default == "smart_search"
    # Phase 12 A3: optional hint/placeholder guidance on the narrative brief fields.
    assert fields["core_concept"].placeholder == "一句话说清冲突：谁+想要什么+被什么阻止"
    assert fields["core_concept"].hint
    assert fields["taboos"].hint and fields["keywords"].hint and fields["audience"].hint
    assert fields["target_words_range"].hint
    assert info.quality_policy.min_score == 0.82
    assert "模板味风险" in info.quality_policy.checks


def test_default_workflow_has_canvas_layout_without_crosscutting_execution_nodes():
    workflow = default_workflow()
    assert workflow.canvas_layout.crosscutting_visible is True
    assert "wiki-layer" in workflow.canvas_layout.nodes
    assert "quality-layer" in workflow.canvas_layout.nodes
    stage_y = workflow.canvas_layout.nodes["info"].y
    assert workflow.canvas_layout.nodes["summary"].y == stage_y
    assert workflow.canvas_layout.nodes["wiki-layer"].y < stage_y - 180
    assert workflow.canvas_layout.nodes["quality-layer"].y > stage_y + 180
    assert all(node.id not in {"wiki-layer", "quality-layer"} for node in workflow.nodes)
    assert all(edge.source not in {"wiki-layer", "quality-layer"} for edge in workflow.edges)


def test_default_workflow_branches_cover_after_detail_and_joins_at_export():
    from novel_workflow.workflows.compiler import NovelWorkflowCompiler

    workflow = default_workflow()
    order = [node.id for node in NovelWorkflowCompiler().compile_order(workflow)]
    assert order == ["info", "summary", "outline", "detail", "text", "cover", "export"]
    assert all(edge.source != "summary" or edge.target != "cover" for edge in workflow.edges)
    assert all(edge.source != "text" or edge.target != "cover" for edge in workflow.edges)
    assert any(edge.source == "detail" and edge.target == "text" for edge in workflow.edges)
    assert any(edge.source == "detail" and edge.target == "cover" for edge in workflow.edges)
    assert any(edge.source == "text" and edge.target == "export" for edge in workflow.edges)
    assert any(edge.source == "cover" and edge.target == "export" for edge in workflow.edges)
    cover = next(node for node in workflow.nodes if node.id == "cover")
    assert "detail_outline" in cover.input_refs
    assert "chapters" not in cover.input_refs


def test_default_workflow_has_quality_mode_and_variant_policy():
    workflow = default_workflow()
    text = next(node for node in workflow.nodes if node.id == "text")
    info = next(node for node in workflow.nodes if node.id == "info")
    assert workflow.quality_mode == "balanced"
    assert text.variant_policy.enabled is False
    assert text.variant_policy.candidate_count == 1
    assert next(field for field in text.input_schema if field.key == "enable_version_compare").default is False
    assert info.variant_policy.enabled is False


def test_default_workflow_uses_real_global_provider():
    workflow = default_workflow()
    live = materialize_workflow_for_execution(workflow)

    assert {profile.kind for profile in live.provider_profiles} == {"openai-compatible", "openai-compatible-image"}
    assert all(node.provider_profile_id == "openai-compatible" for node in live.nodes)
    assert all(node.model_settings.model == "gpt-4.1-mini" for node in live.nodes if node.type != "export_artifact")


@pytest.mark.asyncio
async def test_deep_mode_does_not_auto_generate_variants(tmp_path):
    workflow = default_workflow()
    workflow.quality_mode = "deep"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()
    run_id = "deep-run"
    store.create(run_id, workflow, {"project_id": "p-deep", "title": "深度测试"})
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, {"project_id": "p-deep", "title": "深度测试"})
    info_variants = [event for event in events if event["type"] == "variant_generated" and event.get("node_id") == "info"]
    summary_variants = [event for event in events if event["type"] == "variant_generated" and event.get("node_id") == "summary"]
    text_variants = [event for event in events if event["type"] == "variant_generated" and event.get("node_id") == "text"]
    assert not info_variants
    assert not summary_variants
    assert not text_variants
    assert not any(event["type"] == "best_variant_selected" and event.get("node_id") == "info" for event in events)


def test_mode_variant_policy_matches_product_rules():
    from novel_workflow.orchestration.helpers import effective_variant_policy

    workflow = default_workflow()
    text = next(node for node in workflow.nodes if node.id == "text")

    workflow.quality_mode = "fast"
    fast = effective_variant_policy(text, workflow)
    assert fast.enabled is False
    assert fast.candidate_count == 1

    workflow.quality_mode = "balanced"
    text.variant_policy.enabled = True
    text.variant_policy.candidate_count = 8
    balanced = effective_variant_policy(text, workflow)
    assert balanced.enabled is False
    assert balanced.candidate_count == 1

    workflow.quality_mode = "deep"
    text.variant_policy.candidate_count = 3
    deep = effective_variant_policy(text, workflow)
    assert deep.enabled is False
    assert deep.candidate_count == 1


@pytest.mark.asyncio
async def test_deep_mode_export_waits_for_manual_return(tmp_path):
    workflow = default_workflow()
    workflow.quality_mode = "deep"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()
    run_id = "deep-export-wait"
    inputs = {"project_id": "p-deep-export", "title": "导出留页测试", "quality_mode": "deep"}
    store.create(run_id, workflow, inputs)
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, inputs)
    assert events[-1]["type"] == "run_export_ready"
    saved = store.read(run_id)["state"]
    assert saved["pending_export_return"] is True
    assert saved["runtime_phase"] == "stage_ready_to_continue"


@pytest.mark.asyncio
async def test_incomplete_detail_outline_blocks_writing(tmp_path, monkeypatch):
    workflow = default_workflow()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()

    async def short_detail(prompt, *, task_name, context, schema=None):
        del prompt, context, schema
        if task_name == "detail_outline":
            return {"chapters": [{"chapter": "第1章", "pov": "林澈", "scene": "旧港档案馆", "goal": "只有一章。"}]}
        return await FAKE_FALLBACK.generate_structured("", task_name=task_name, context={})

    monkeypatch.setattr(providers.text_provider, "generate_structured", short_detail)
    run_id = "blocked-writing"
    store.create(run_id, workflow, {"project_id": "p-block", "title": "阻断测试"})
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, {"project_id": "p-block", "title": "阻断测试"})
    assert any(event["type"] == "artifact_validation_failed" and event.get("node_id") == "detail" for event in events)
    assert any(event["type"] == "node_failed" and event.get("node_id") == "detail" for event in events)
    assert not any(event["type"] == "phase_changed" and event.get("phase") == "writing" for event in events)


@pytest.mark.asyncio
async def test_balanced_mode_creates_revision_directive_for_chapter_handoff(tmp_path, monkeypatch):
    workflow = default_workflow()
    workflow.quality_mode = "balanced"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()

    async def no_handoff_text(prompt, *, task_name, context, schema=None):
        del prompt, context, schema
        if task_name == "chapter_text":
            return {
                "chapter_title": "测试章节",
                "content": "人物 冲突 伏笔 世界观 正文 " * 40,
                "summary": "测试正文缺少上一章承接。",
                "wiki_writebacks": [],
                "character_shift": "人物状态推进。",
                "foreshadow_updates": [],
            }
        if task_name == "detail_outline":
            return detail_outline_fixture()
        return await FAKE_FALLBACK.generate_structured("", task_name=task_name, context={})

    monkeypatch.setattr(providers.text_provider, "generate_structured", no_handoff_text)
    run_id = "revision-run"
    inputs = {"project_id": "p-rev", "title": "修订测试", "stage_configs": {"detail": {"chapter_count": 3}, "text": {"chapter_count": 3}}}
    store.create(run_id, workflow, inputs)
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, inputs)
    assert any(event["type"] == "revision_directive_created" and event.get("chapter") == "第2章" for event in events)
    assert any(event["type"] == "revision_applied" for event in events)
    saved = store.read(run_id)["state"]
    assert saved["revision_directives"]
    assert "[候选版本" not in saved["artifacts"]["chapters"]["chapters"][1]["content"]
    assert "[质量修订]" not in saved["artifacts"]["chapters"]["chapters"][1]["content"]


@pytest.mark.asyncio
async def test_fast_mode_skips_revision_directives(tmp_path, monkeypatch):
    workflow = default_workflow()
    workflow.quality_mode = "fast"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()

    async def no_handoff_text(prompt, *, task_name, context):
        if task_name == "chapter_text":
            return "人物 冲突 伏笔 世界观 正文 " * 40
        if task_name == "detail_outline":
            return "第1章：伏笔。\n第2章：推进。\n第3章：回收。"
        return "人物 冲突 伏笔 世界观 结局 角色弧 第1卷：旧案开启 " * 20

    monkeypatch.setattr(providers.text_provider, "generate_text", no_handoff_text)
    run_id = "fast-revision-run"
    inputs = {"project_id": "p-fast", "title": "极速测试", "stage_configs": {"detail": {"chapter_count": 3}, "text": {"chapter_count": 3}}}
    store.create(run_id, workflow, inputs)
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, inputs)
    assert not any(event["type"] == "revision_directive_created" for event in events)


@pytest.mark.asyncio
async def test_fast_mode_records_warnings_without_stopping(tmp_path, monkeypatch):
    """§2.1 mode contract: fast records warnings (no revision) and keeps producing."""
    workflow = default_workflow()
    workflow.quality_mode = "fast"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()

    async def warning_heavy_text(prompt, *, task_name, context, schema=None):
        del prompt, context, schema
        if task_name == "chapter_text":
            # No handoff signal, no foreshadow token, repetitive wording:
            # multiple warnings push the score below min_score in every chapter.
            return {
                "chapter_title": "警告章节",
                "content": "夜色 深沉 灯下 沉默 " * 40,
                "summary": "极速档警告不应停机。",
                "wiki_writebacks": [],
                "character_shift": "",
                "foreshadow_updates": [],
            }
        if task_name == "detail_outline":
            return detail_outline_fixture()
        return await FAKE_FALLBACK.generate_structured("", task_name=task_name, context={})

    monkeypatch.setattr(providers.text_provider, "generate_structured", warning_heavy_text)
    run_id = "fast-warning-run"
    inputs = {"project_id": "p-fast-warn", "title": "极速警告测试", "stage_configs": {"detail": {"chapter_count": 3}, "text": {"chapter_count": 3}}}
    store.create(run_id, workflow, inputs)
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, inputs)

    assert events[-1]["type"] == "run_completed"
    assert not any(event["type"] == "node_failed" and event.get("node_id") == "text" for event in events)
    assert not any(event["type"] == "revision_directive_created" for event in events)
    saved = store.read(run_id)["state"]
    chapters = saved["artifacts"]["chapters"]["chapters"]
    assert len(chapters) == 3
    assert all(item["status"] == "completed" for item in chapters)
    text_reports = [item for item in saved["quality_reports"] if item.get("node_id") == "text" and item.get("findings")]
    assert text_reports  # warnings are recorded, not swallowed


@pytest.mark.asyncio
async def test_fast_mode_still_stops_on_hard_blocking_conflict(tmp_path, monkeypatch):
    """§2.1 mode contract: the hard-blocking line is shared by all modes, fast included."""
    workflow = default_workflow()
    workflow.quality_mode = "fast"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()

    async def conflicting_text(prompt, *, task_name, context, schema=None):
        del prompt, context, schema
        if task_name == "chapter_text":
            return {
                "chapter_title": "冲突章节",
                "content": "他宣布从此推翻世界观硬设定，伏笔与承接照旧，其余一切继续运转。" * 4,
                "summary": "刻意触发世界观硬规则冲突。",
                "wiki_writebacks": [],
                "character_shift": "",
                "foreshadow_updates": [],
            }
        if task_name == "detail_outline":
            return detail_outline_fixture()
        return await FAKE_FALLBACK.generate_structured("", task_name=task_name, context={})

    monkeypatch.setattr(providers.text_provider, "generate_structured", conflicting_text)
    run_id = "fast-hard-block-run"
    inputs = {"project_id": "p-fast-block", "title": "极速硬阻断测试"}
    store.create(run_id, workflow, inputs)
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, inputs)

    assert any(event["type"] == "continuity_conflict_found" for event in events)
    assert any(event["type"] == "manual_intervention_required" for event in events)
    assert any(event["type"] == "node_failed" and event.get("node_id") == "text" for event in events)
    assert events[-1]["type"] == "run_failed"


@pytest.mark.asyncio
async def test_worldbuilding_hard_conflict_blocks_pipeline(tmp_path, monkeypatch):
    workflow = default_workflow()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = fake_registry()

    async def conflict_text(prompt, *, task_name, context, schema=None):
        del prompt, context, schema
        if task_name == "summary":
            return {
                "one_liner": "冲突测试",
                "full_synopsis": "本阶段会推翻世界观硬设定，人物 冲突 伏笔 结局。",
                "act_structure": [{"title": "冲突", "goal": "测试硬设定冲突", "turn": "推翻世界观硬设定"}],
                "core_conflict": "推翻世界观硬设定",
                "character_arcs": [{
                    "name": "林澈",
                    "arc": "从回避旧案到公开证据",
                    "pressure": "公开真相会触发利益链反扑",
                    "next": "继续核验父亲签章与证据边界",
                }],
                "key_turns": [{"label": "冲突", "detail": "推翻世界观硬设定"}],
                "ending_resolution": "结局",
                "consistency_checks": ["该测试刻意触发世界观硬设定冲突"],
            }
        return await FAKE_FALLBACK.generate_structured("", task_name=task_name, context={})

    monkeypatch.setattr(providers.text_provider, "generate_structured", conflict_text)
    run_id = "conflict-run"
    store.create(run_id, workflow, {"project_id": "p-conflict", "title": "冲突测试"})
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, {"project_id": "p-conflict", "title": "冲突测试"})
    assert any(event["type"] == "continuity_conflict_found" for event in events)
    assert any(event["type"] == "manual_intervention_required" for event in events)
    assert events[-1]["type"] == "run_failed"


async def _run_with_brief_approval(
    runner: NovelWorkflowRunner,
    workflow,
    store: RunStore,
    run_id: str,
    inputs: dict,
) -> list[dict]:
    events: list[dict] = []

    async def approve_when_needed() -> None:
        confirmed: set[str] = set()
        for _ in range(240):
            await asyncio.sleep(0.05)
            approval = store.read(run_id).get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id not in confirmed:
                artifact = _approved_test_artifact(approval.get("artifact"))
                store.approve_artifact(run_id, node_id=node_id, output_key=str(approval.get("output_key") or node_id), artifact=artifact)
                confirmed.add(node_id)
            stored = store.read(run_id)
            state = stored.get("state") or {}
            if state.get("runtime_phase") in {"completed", "failed"}:
                return

    approver = asyncio.create_task(approve_when_needed())
    try:
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            events.append(event)
    finally:
        await approver
    return events


def _approved_test_artifact(artifact):
    if isinstance(artifact, dict):
        approved = dict(artifact)
        approved.setdefault("downstream_constraints", [])
        if isinstance(approved.get("downstream_constraints"), list):
            approved["downstream_constraints"] = [*approved["downstream_constraints"], "人工定稿测试确认"]
        return approved
    return f"{artifact or ''}\n\n[人工定稿] 保留核心卖点、人物边界和世界观硬约束。"


def _configure_test_client_provider(client) -> None:
    provider = next(item for item in client.get("/api/providers").json() if item["id"] == "openai-compatible")
    provider["base_url"] = "https://example.test"
    provider["default_model"] = "deepseek-v4-pro-202606"
    provider["enabled"] = True
    client.post("/api/providers", json=provider)
    client.post("/api/providers/openai-compatible/secret", json={"api_key": "unit-test-secret"})
    image_provider = next(item for item in client.get("/api/providers").json() if item["id"] == "openai-compatible-image")
    image_provider["base_url"] = "https://example.test"
    image_provider["default_model"] = "gpt-image-1"
    image_provider["enabled"] = True
    client.post("/api/providers", json=image_provider)
    client.post("/api/providers/openai-compatible-image/secret", json={"api_key": "unit-test-image-secret"})
    client.app.state.providers = fake_registry()


def test_provider_and_prompt_api_seed_defaults():
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    client = TestClient(create_app())
    providers = client.get("/api/providers").json()
    prompts = client.get("/api/prompts").json()
    workflows = client.get("/api/workflows").json()
    assert any(item["id"] == "openai-compatible" for item in providers)
    assert any(item["id"] == "prompt-info" for item in prompts)
    assert workflows[0]["global_inputs"]


def test_provider_secret_api_does_not_expose_key(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NOVEL_LLM_API_KEY", "env-unit-secret")
    client = TestClient(create_app())
    response = client.post("/api/providers/openai-compatible/secret", json={"api_key": "unit-test-secret"})
    assert response.status_code == 200
    assert response.json()["has_saved_secret"] is True
    providers = client.get("/api/providers").json()
    openai_profile = next(item for item in providers if item["id"] == "openai-compatible")
    assert openai_profile["has_saved_secret"] is True
    assert openai_profile["has_env_secret"] is True
    assert "unit-test-secret" not in str(providers)
    assert "env-unit-secret" not in str(providers)
    assert (tmp_path / "runtime" / "novel_workflow" / "provider_profiles.sqlite3").exists()
    assert (tmp_path / "runtime" / "novel_workflow" / "provider_secrets.sqlite3").exists()


def test_provider_registry_uses_sqlite_secret(tmp_path):
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
    from novel_workflow.storage.provider_secret_store import ProviderSecretStore
    from novel_workflow.workflows.schemas import ProviderProfile

    secret_store = ProviderSecretStore(tmp_path / "provider_secrets.sqlite3")
    secret_store.set_api_key("openai-compatible", "unit-test-secret")
    registry = ProviderRegistry.from_profiles(
        [
            ProviderProfile(
                id="openai-compatible",
                name="OpenAI Compatible",
                kind="openai-compatible",
                base_url="https://example.test",
                default_model="deepseek-v4-pro-202606",
                enabled=True,
            )
        ],
        secret_resolver=secret_store.get_api_key,
    )
    assert isinstance(registry.text_provider, OpenAICompatibleTextProvider)
    assert registry.text_provider.model == "deepseek-v4-pro-202606"


def test_provider_stage_probe_api_uses_saved_secret_without_exposing_key(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app
    from novel_workflow.providers.stage_probe import StageProbeResult
    import novel_workflow.api.routes.providers as provider_routes

    calls = []

    async def fake_probe(profile, *, api_key, stage_id="info", inputs=None, max_tokens=None):
        calls.append({"profile": profile, "api_key": api_key, "stage_id": stage_id, "inputs": inputs, "max_tokens": max_tokens})
        return StageProbeResult(ok=True, provider_id=profile.id, stage_id=stage_id, stage_type="info_recommend", schema_name="StoryBriefContract", message="ok")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(provider_routes, "probe_structured_stage", fake_probe)
    client = TestClient(create_app())
    provider = next(item for item in client.get("/api/providers").json() if item["id"] == "openai-compatible")
    provider["base_url"] = "https://example.test"
    provider["default_model"] = "deepseek-v4-pro-202606"
    client.post("/api/providers", json=provider)
    client.post("/api/providers/openai-compatible/secret", json={"api_key": "unit-test-secret"})

    response = client.post("/api/providers/stage-probe", json={"provider_id": "openai-compatible", "stage_id": "info", "max_tokens": 512})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert calls[0]["api_key"] == "unit-test-secret"
    assert calls[0]["max_tokens"] == 512
    assert "unit-test-secret" not in str(payload)


@pytest.mark.asyncio
async def test_provider_smoke_uses_saved_secret_without_exposing_key(tmp_path, monkeypatch):
    from novel_workflow.providers.smoke import run_provider_smoke
    from novel_workflow.providers.stage_probe import StageProbeResult
    import novel_workflow.providers.smoke as smoke
    from novel_workflow.storage.provider_profile_store import ProviderProfileStore
    from novel_workflow.storage.provider_secret_store import ProviderSecretStore
    from novel_workflow.workflows.schemas import ProviderProfile

    runtime_root = tmp_path / "runtime" / "novel_workflow"
    ProviderProfileStore(runtime_root / "provider_profiles.sqlite3").write(
        "openai-compatible",
        ProviderProfile(
            id="openai-compatible",
            name="OpenAI Compatible",
            kind="openai-compatible",
            base_url="https://example.test",
            default_model="unit-model",
        ).model_dump(),
    )
    ProviderSecretStore(runtime_root / "provider_secrets.sqlite3").set_api_key("openai-compatible", "unit-test-secret")
    calls = []

    async def fake_probe(profile, *, api_key, stage_id="info", inputs=None, max_tokens=None):
        calls.append({"profile": profile, "api_key": api_key, "stage_id": stage_id, "max_tokens": max_tokens})
        return StageProbeResult(ok=True, provider_id=profile.id, stage_id=stage_id, stage_type="info_recommend", schema_name="StoryBriefContract", message="ok")

    monkeypatch.setattr(smoke, "probe_structured_stage", fake_probe)
    result = await run_provider_smoke(runtime_root=runtime_root, provider_id="openai-compatible", stage_id="info", max_tokens=768)

    assert result["ok"] is True
    assert result["api_key_source"] == "sqlite"
    assert result["schema_name"] == "StoryBriefContract"
    assert calls[0]["api_key"] == "unit-test-secret"
    assert calls[0]["max_tokens"] == 768
    assert "unit-test-secret" not in str(result)


@pytest.mark.asyncio
async def test_provider_smoke_reports_missing_secret(tmp_path):
    from novel_workflow.providers.smoke import run_provider_smoke
    from novel_workflow.storage.provider_profile_store import ProviderProfileStore
    from novel_workflow.workflows.schemas import ProviderProfile

    runtime_root = tmp_path / "runtime" / "novel_workflow"
    ProviderProfileStore(runtime_root / "provider_profiles.sqlite3").write(
        "openai-compatible",
        ProviderProfile(
            id="openai-compatible",
            name="OpenAI Compatible",
            kind="openai-compatible",
            base_url="https://example.test",
            default_model="unit-model",
        ).model_dump(),
    )
    result = await run_provider_smoke(runtime_root=runtime_root, provider_id="openai-compatible", stage_id="info", max_tokens=768)

    assert result["ok"] is False
    assert result["error_code"] == "secret_missing"


@pytest.mark.asyncio
async def test_stage_probe_seeds_planning_upstream_context(monkeypatch):
    from novel_workflow.providers.stage_probe import probe_structured_stage
    from novel_workflow.workflows.schemas import ProviderProfile

    calls = []

    class FakeProvider:
        async def generate_structured(self, prompt, *, task_name, context, schema=None):
            calls.append({"prompt": prompt, "task_name": task_name, "context": context, "schema": schema})
            return {
                "chapters": [
                    {
                        "chapter": "第1章",
                        "pov": "林澈",
                        "scene": "旧港档案馆",
                        "goal": "修复 7A-13 磁带",
                        "entry_state": "林澈只想完成普通委托",
                        "conflict": "磁带底噪出现他的名字",
                        "stakes": "私人记忆被卷入旧案",
                        "fact_reveals": [{"anchor": "雾钟", "fact": "7A-13 母带存在", "impact": "旧案获得物证入口"}],
                        "foreshadow": [{"name": "父亲签章", "status": "投放", "note": "求救声暗示签章来源"}],
                        "character_shift": {"character": "林澈", "related_to": "许望舒", "relation": "调查同盟", "pressure": "母带可能被封存", "motivation": "确认求救声来源", "change": "开始怀疑自己的记忆", "impact": "主动保留并追查证据"},
                        "hook": "求救声来自十年前",
                        "continuity_notes": "承接 info 中声纹档案设定",
                        "wiki_candidates": [{"title": "7A-13 母带", "fact": "保存十年前声纹证词", "source_anchor": "雾钟"}],
                    }
                ]
            }

    def fake_from_profile(**kwargs):
        return FakeProvider()

    monkeypatch.setattr("novel_workflow.providers.stage_probe.OpenAICompatibleTextProvider.from_profile", fake_from_profile)
    result = await probe_structured_stage(
        ProviderProfile(id="openai-compatible", name="OpenAI Compatible", kind="openai-compatible", base_url="https://example.test", default_model="unit-model"),
        api_key="unit-test-secret",
        stage_id="detail",
    )

    assert result.ok is True
    assert calls[0]["task_name"] == "detail_outline"
    assert "approved_story_brief" in calls[0]["prompt"]
    assert "### outline" in calls[0]["prompt"]
    assert "7A-13 母带" in calls[0]["prompt"]


@pytest.mark.asyncio
async def test_stage_probe_text_uses_chapter_generation_contract(monkeypatch):
    from novel_workflow.providers.stage_probe import probe_structured_stage
    from novel_workflow.workflows.schemas import ProviderProfile

    calls = []

    class FakeProvider:
        async def generate_structured(self, prompt, *, task_name, context, schema=None):
            calls.append({"prompt": prompt, "task_name": task_name, "context": context, "schema": schema})
            return {
                "chapter_title": "雾钟未眠",
                "content": "第一章 雾钟未眠\n\n林澈把 7A-13 母带放进修复机时，旧港的雾正贴着窗缝往里钻。底噪第三次回放时，一个年轻声音喊出他的名字。",
                "summary": "林澈修复 7A-13 母带时听见十年前的求救声，旧案入口被打开。",
                "wiki_writebacks": [{"target": "7A-13 母带", "fact": "底噪里包含十年前的求救声", "source_chapter": "第1章"}],
                "character_shift": "林澈开始怀疑自己的记忆。",
                "foreshadow_updates": [{"name": "父亲签章", "status": "投放"}],
            }

    def fake_from_profile(**kwargs):
        return FakeProvider()

    monkeypatch.setattr("novel_workflow.providers.stage_probe.OpenAICompatibleTextProvider.from_profile", fake_from_profile)
    result = await probe_structured_stage(
        ProviderProfile(id="openai-compatible", name="OpenAI Compatible", kind="openai-compatible", base_url="https://example.test", default_model="unit-model"),
        api_key="unit-test-secret",
        stage_id="text",
    )

    assert result.ok is True
    assert result.schema_name == "ChapterGenerationContract"
    assert result.summary["content_chars"] > 40
    assert calls[0]["task_name"] == "chapter_text"
    assert calls[0]["schema"] is None
    assert "当前调用只生成一个章节" in calls[0]["prompt"]
    assert "章节上下文包" in calls[0]["prompt"]
    assert "7A-13 母带" in calls[0]["prompt"]


def test_reference_search_returns_disabled_without_tavily_key(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    client = TestClient(create_app())
    response = client.post("/api/references/search", json={"query": "长篇悬疑 小说"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["results"] == []
    assert "TAVILY_API_KEY" in payload["message"]


def test_reference_search_normalizes_tavily_results(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app
    import novel_workflow.references.search as search_module

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "answer": "参考摘要",
                "results": [{"title": "资料 A", "url": "https://example.com/a", "content": "内容摘要", "score": 0.91}],
            }

    calls = []

    def fake_post(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return FakeResponse()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(search_module.requests, "post", fake_post)
    client = TestClient(create_app())
    response = client.post("/api/references/search", json={"query": "长篇悬疑 小说", "max_results": 3, "search_depth": "basic"})
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["message"] == "参考摘要"
    assert payload["results"][0]["title"] == "资料 A"
    assert calls[0]["kwargs"]["json"]["max_results"] == 3
    assert calls[0]["kwargs"]["headers"]["Authorization"] == "Bearer test-key"


def test_reference_upload_and_get(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    upload = client.post("/api/references/upload", json={"title": "风格片段", "content": "冷调悬疑，人物关系以旧案为牵引。"}).json()
    assert upload["reference_id"].startswith("ref-")
    assert upload["char_count"] > 0
    stored = client.get(f"/api/references/{upload['reference_id']}").json()
    assert stored["title"] == "风格片段"
    assert "旧案" in stored["content"]


def test_knowledge_upload_and_search(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    upload = client.post(
        "/api/knowledge/documents/upload",
        json={
            "title": "旧港设定",
            "filename": "world.md",
            "content_type": "text/markdown",
            "content": "# 旧港\n记忆实验、档案馆和港务集团共同牵引旧案。人物关系围绕伏笔推进。",
        },
    )
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["document"]["doc_id"].startswith("kb-")
    assert payload["document"]["chunk_count"] >= 1
    docs = client.get("/api/knowledge/documents").json()
    assert docs[0]["title"] == "旧港设定"
    search = client.post("/api/knowledge/search", json={"query": "记忆实验 伏笔", "intent": "检索旧港设定，不要返回无关桥段", "top_k": 3}).json()
    assert search["query_rewrite"]
    assert search["results"]
    assert "旧港" in search["results"][0]["title"]


def test_knowledge_delete_returns_index_status_and_removes_chunks(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    upload = client.post(
        "/api/knowledge/documents/upload",
        json={"title": "待删除资料", "filename": "delete.md", "content": "旧港 记忆实验 伏笔 " * 80},
    ).json()
    doc_id = upload["document"]["doc_id"]
    deleted = client.delete(f"/api/knowledge/documents/{doc_id}").json()
    assert deleted["ok"] is True
    assert deleted["deleted_chunks"] >= 1
    assert "backend_synced" in deleted
    docs = client.get("/api/knowledge/documents").json()
    assert all(item["doc_id"] != doc_id for item in docs)
    search = client.post("/api/knowledge/search", json={"query": "旧港 记忆实验", "top_k": 3}).json()
    assert not search["results"]


def test_redis_backend_setting_falls_back_when_unavailable(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KNOWLEDGE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    client = TestClient(create_app())
    client.post(
        "/api/knowledge/documents/upload",
        json={"title": "资料", "filename": "a.txt", "content": "记忆实验 伏笔 旧港"},
    )
    search = client.post("/api/knowledge/search", json={"query": "记忆实验", "top_k": 2}).json()
    assert search["backend"] == "redis-hybrid"
    assert search["backend_available"] is False
    assert search["results"]


def test_prompt_plan_includes_reference_summary():
    from novel_workflow.stages.prompt_plan import PromptPlanBuilder
    from novel_workflow.workflows.schemas import NovelRunState

    workflow = default_workflow()
    info = next(node for node in workflow.nodes if node.id == "info")
    state = NovelRunState(
        run_id="prompt-run",
        project_id="p1",
        workflow_id=workflow.id,
        inputs={"stage_configs": {"info": {"reference_mode": "knowledge_base", "reference_summary": "旧港资料摘要"}}},
    )
    prompt = PromptPlanBuilder().build(info, state)
    assert "上传文件 / 知识库" in prompt
    assert "旧港资料摘要" in prompt


def test_stage_contract_validation_rejects_missing_required_fields():
    from novel_workflow.output_contracts import validate_chapter_generation, validate_stage_artifact

    outline = {
        "volumes": [
            {
                "title": "第一卷",
                "chapter_range": "第1-3章",
                "volume_goal": "建立旧案入口",
                "rhythm": "悬念递进",
                "development": "调查推进",
                "midpoint": "中点反转",
                "climax": "卷尾爆点",
                "resolution": "第一层真相公开",
                "character_progression": [],
                "world_reveal": [],
                "foreshadow_plan": [],
            }
        ]
    }
    detail = {
        "chapters": [
            {
                "chapter": "第1章",
                "scene": "旧港档案馆",
                "goal": "修复磁带",
                "entry_state": "回避旧案",
                "conflict": "底噪喊出林澈名字",
                "stakes": "私人记忆被卷入旧案",
                "fact_reveals": [],
                "foreshadow": [],
                "character_shift": "开始怀疑记忆",
                "hook": "求救声来自十年前",
                "continuity_notes": "承接声纹档案设定",
                "wiki_candidates": [],
            }
        ]
    }
    chapter = {"chapter_title": "雾钟未眠", "summary": "缺正文内容"}
    legacy_text = "# 看起来像梗概，但不是结构化 JSON Artifact"

    outline_result = validate_stage_artifact("outline", outline)
    detail_result = validate_stage_artifact("detail_outline", detail)
    chapter_result = validate_chapter_generation(chapter)
    legacy_result = validate_stage_artifact("summary", legacy_text)

    assert outline_result.valid is False
    assert any("opening" in error for error in outline_result.errors)
    assert detail_result.valid is False
    assert any("pov" in error for error in detail_result.errors)
    assert chapter_result.valid is False
    assert any("content" in error for error in chapter_result.errors)
    assert legacy_result.valid is False
    assert legacy_result.artifact == legacy_text
    assert any("structured JSON object" in error for error in legacy_result.errors)


def test_story_brief_contract_rejects_ambiguous_character_relationships():
    from novel_workflow.output_contracts import validate_stage_artifact
    from tests.workflow_runner_harness import story_brief_fixture

    duplicate_names = story_brief_fixture("雾港旧声")
    duplicate_names["characters"][1]["name"] = duplicate_names["characters"][0]["name"]
    unknown_reference = story_brief_fixture("雾港旧声")
    unknown_reference["relationships"][0]["target"] = "不存在的人物"

    duplicate_result = validate_stage_artifact("info_recommend", duplicate_names)
    reference_result = validate_stage_artifact("info_recommend", unknown_reference)

    assert duplicate_result.valid is False
    assert any("names must be unique" in error for error in duplicate_result.errors)
    assert reference_result.valid is False
    assert any("must reference characters" in error for error in reference_result.errors)


def test_character_graph_is_derived_from_info_artifact():
    from novel_workflow.orchestration.helpers import character_graph

    graph = character_graph("info", {
        "characters": [
            {"name": "甲", "identity": "调查者", "motivation": "寻找证据"},
            {"name": "乙", "identity": "证人", "motivation": "保护秘密"},
        ],
        "relationships": [
            {"source": "甲", "target": "乙", "relation": "互相试探", "strength": 0.72},
        ],
    })

    assert [node.name for node in graph.nodes] == ["甲", "乙"]
    assert graph.edges[0].source == "character-1"
    assert graph.edges[0].target == "character-2"
    assert graph.updated_by == "info"
    assert character_graph("info").nodes == []


def test_mode_checkpoint_matrix_matches_product_contract():
    from novel_workflow.orchestration.control import should_wait_for_stage_confirmation

    assert should_wait_for_stage_confirmation("fast", "info", "info_recommend") is False
    assert should_wait_for_stage_confirmation("fast", "summary", "summary") is False
    assert should_wait_for_stage_confirmation("balanced", "info", "info_recommend") is True
    assert should_wait_for_stage_confirmation("balanced", "summary", "summary") is False
    assert should_wait_for_stage_confirmation("deep", "info", "info_recommend") is True
    assert should_wait_for_stage_confirmation("deep", "summary", "summary") is True
    assert should_wait_for_stage_confirmation("deep", "cover", "cover_image") is True
    assert should_wait_for_stage_confirmation("deep", "export", "export_artifact") is False


def test_quality_world_rule_conflict_requires_explicit_hard_setting_violation():
    from novel_workflow.quality.engine import QualityEngine
    from novel_workflow.workflows.schemas import StoryBibleState

    workflow = default_workflow()
    summary = next(node for node in workflow.nodes if node.id == "summary")
    bible = StoryBibleState(world_rules=["世界观硬设定不得被后续阶段推翻"])

    normal = QualityEngine().check_stage(
        summary,
        {
            "one_liner": "主角推翻旧证词。",
            "full_synopsis": "主角发现旧证词被伪造，逐步推翻错误真相，同时保留结局、角色弧、伏笔和主线。",
            "act_structure": [{"title": "旧案", "goal": "追查", "turn": "发现伪证"}],
            "core_conflict": "证词与记忆冲突",
            "character_arcs": [],
            "key_turns": [{"label": "证词", "detail": "伪证被推翻"}],
            "ending_resolution": "结局公开第一层真相",
            "consistency_checks": [],
        },
        story_bible=bible,
        mode="balanced",
    )
    explicit = QualityEngine().check_stage(
        summary,
        {
            "one_liner": "测试硬设定冲突。",
            "full_synopsis": "本阶段会推翻世界观硬设定，人物 冲突 伏笔 结局。",
            "act_structure": [{"title": "冲突", "goal": "测试", "turn": "推翻世界观硬设定"}],
            "core_conflict": "推翻世界观硬设定",
            "character_arcs": [],
            "key_turns": [{"label": "冲突", "detail": "推翻世界观硬设定"}],
            "ending_resolution": "结局",
            "consistency_checks": [],
        },
        story_bible=bible,
        mode="balanced",
    )

    assert normal.passed is True
    assert not any(finding.blocking for finding in normal.findings)
    assert explicit.passed is False
    assert any(finding.blocking for finding in explicit.findings)


def test_prompt_plan_embeds_field_level_json_contract_and_template():
    from novel_workflow.stages.prompt_plan import PromptPlanBuilder
    from novel_workflow.workflows.schemas import NovelRunState

    workflow = default_workflow()
    summary = next(node for node in workflow.nodes if node.id == "summary")
    text = next(node for node in workflow.nodes if node.id == "text")
    state = NovelRunState(run_id="prompt-schema-run", project_id="p1", workflow_id=workflow.id, inputs={"quality_mode": "deep", "title": "雾港"})

    summary_prompt = PromptPlanBuilder().build(summary, state, template_content="自定义梗概模板")
    text_prompt = PromptPlanBuilder().build(text, state, template_content="自定义正文模板")

    assert "自定义梗概模板" in summary_prompt
    assert "只返回 JSON object" in summary_prompt
    assert '"full_synopsis"' in summary_prompt
    assert '"act_structure"' in summary_prompt
    assert "自定义正文模板" in text_prompt
    assert "当前调用只生成一个章节" in text_prompt
    assert '"chapter_title"' in text_prompt
    assert '"content"' in text_prompt


def test_default_workflow_schemas_describe_the_final_editable_artifacts():
    workflow = default_workflow()
    schemas = {node.id: node.output_schema for node in workflow.nodes}

    assert "background" in schemas["info"]["characters"]
    assert {"context_packet", "context_packets", "chapter_deltas"} <= schemas["text"].keys()
    assert "commit_signature" in schemas["text"]["chapters"]
    assert "model_review" in schemas["text"]["chapters"]
    assert "content" in schemas["export"]["chapters"]
    assert "cover_asset" in schemas["export"]


def test_openai_compatible_parses_fenced_and_embedded_json():
    from novel_workflow.providers.openai_compat import _parse_json_object

    assert _parse_json_object('```json\n{"ok": true}\n```') == {"ok": True}
    assert _parse_json_object('说明文字 {"value": 3, "name": "雾港"} 结束') == {"value": 3, "name": "雾港"}
    assert _parse_json_object("不是 JSON") is None


class _FakeSdkClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]


@pytest.mark.asyncio
async def test_openai_compatible_structured_output_requires_json(monkeypatch):
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider, ProviderResponseError

    provider = OpenAICompatibleTextProvider(base_url="https://example.test", api_key="unit-test-secret", model="unit-model")

    async def fake_complete(prompt, *, task_name, json_mode, idempotency_key):
        del prompt, task_name, json_mode, idempotency_key
        return "这不是 JSON"

    monkeypatch.setattr(provider, "_complete", fake_complete)

    with pytest.raises(ProviderResponseError) as exc:
        await provider.generate_structured("prompt", task_name="summary", context={}, schema={"type": "object"})
    assert exc.value.code == "json_parse_failed"


@pytest.mark.asyncio
async def test_openai_compatible_structured_request_uses_json_mode(monkeypatch):
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider

    client = _FakeSdkClient([{"choices": [{"finish_reason": "stop", "message": {"content": "{\"ok\": true}"}}]}])
    provider = OpenAICompatibleTextProvider(
        base_url="https://example.test/v1",
        api_key="unit-test-secret",
        model="unit-model",
        client=client,
    )

    result = await provider.generate_structured("prompt", task_name="summary", context={}, schema={"type": "object"})

    assert result == {"ok": True}
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert client.calls[0]["extra_headers"]["Idempotency-Key"]


@pytest.mark.asyncio
async def test_anthropic_compatibility_template_uses_prompt_only_json_contract():
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider

    client = _FakeSdkClient([{"choices": [{"finish_reason": "stop", "message": {"content": "{\"ok\": true}"}}]}])
    provider = OpenAICompatibleTextProvider(
        base_url="https://api.anthropic.com/v1",
        api_key="unit-test-secret",
        model="claude-sonnet-4-6",
        template_id="anthropic-openai-text",
        client=client,
    )

    result = await provider.generate_structured("prompt", task_name="summary", context={}, schema={"type": "object"})

    assert result == {"ok": True}
    assert "response_format" not in client.calls[0]
    assert "请只返回 JSON 对象" in client.calls[0]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_openai_compatible_reports_truncated_output(monkeypatch):
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider, ProviderResponseError

    response = {"choices": [{"finish_reason": "length", "message": {"content": "{\"ok\":"}}]}
    provider = OpenAICompatibleTextProvider(
        base_url="https://example.test/v1",
        api_key="unit-test-secret",
        model="unit-model",
        client=_FakeSdkClient([response, response, response]),
    )

    with pytest.raises(ProviderResponseError) as exc:
        await provider.generate_structured("prompt", task_name="summary", context={}, schema={"type": "object"})
    assert exc.value.code == "output_truncated"


@pytest.mark.asyncio
async def test_openai_compatible_reports_empty_content(monkeypatch):
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider, ProviderResponseError

    provider = OpenAICompatibleTextProvider(
        base_url="https://example.test/v1",
        api_key="unit-test-secret",
        model="unit-model",
        client=_FakeSdkClient([{"choices": [{"finish_reason": "stop", "message": {"content": ""}}]}]),
    )

    with pytest.raises(ProviderResponseError) as exc:
        await provider.generate_text("prompt", task_name="summary", context={})
    assert exc.value.code == "empty_content"


@pytest.mark.asyncio
async def test_openai_compatible_reports_response_shape_error(monkeypatch):
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider, ProviderResponseError

    provider = OpenAICompatibleTextProvider(
        base_url="https://example.test/v1",
        api_key="unit-test-secret",
        model="unit-model",
        client=_FakeSdkClient([{"choices": []}]),
    )

    with pytest.raises(ProviderResponseError) as exc:
        await provider.generate_text("prompt", task_name="summary", context={})
    assert exc.value.code == "response_shape_error"


@pytest.mark.asyncio
async def test_openai_compatible_retries_structured_output_when_truncated(monkeypatch):
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider

    provider = OpenAICompatibleTextProvider(base_url="https://example.test", api_key="unit-test-secret", model="unit-model")
    calls = []

    async def fake_complete(prompt, *, task_name, json_mode, idempotency_key):
        calls.append({"prompt": prompt, "task_name": task_name, "json_mode": json_mode, "idempotency_key": idempotency_key})
        if len(calls) == 1:
            from novel_workflow.providers.openai_compat import ProviderResponseError

            raise ProviderResponseError("output_truncated", "Provider output was truncated by max_tokens")
        return '{"ok": true}'

    monkeypatch.setattr(provider, "_complete", fake_complete)

    result = await provider.generate_structured("prompt", task_name="summary", context={}, schema={"type": "object"})

    assert result == {"ok": True}
    assert len(calls) == 2
    assert "重新输出要求" in calls[1]["prompt"]


def test_provider_registry_selects_provider_by_profile_id(monkeypatch):
    from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
    from novel_workflow.workflows.schemas import ModelSettings

    monkeypatch.setenv("NOVEL_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("NOVEL_LLM_API_KEY", "unit-test-secret")
    monkeypatch.setenv("NOVEL_LLM_MODEL", "env-model")
    registry = ProviderRegistry.from_env()

    env_provider = registry.text_for("openai-compatible", ModelSettings(model="ignored"))
    real_provider = registry.text_for("openai-compatible", ModelSettings(model="stage-model", max_tokens=77, temperature=0.1))
    from novel_workflow.providers.registry import ProviderUnavailableError

    assert isinstance(env_provider, OpenAICompatibleTextProvider)
    with pytest.raises(ProviderUnavailableError):
        registry.text_for("unknown-profile", ModelSettings(model="ignored"))
    assert isinstance(real_provider, OpenAICompatibleTextProvider)
    assert real_provider.model == "stage-model"
    assert real_provider.max_tokens == 77


def test_smart_search_merges_web_and_knowledge_context(tmp_path, monkeypatch):
    from novel_workflow.api.app import create_app, _enrich_reference_summary
    from novel_workflow.references.schemas import ReferenceSearchResponse, ReferenceSearchResult

    class FakeSearch:
        def search(self, request):
            return ReferenceSearchResponse(
                enabled=True,
                message="联网摘要",
                results=[ReferenceSearchResult(title="联网资料", url="https://example.com/web", content="联网结构参考", score=0.9)],
            )

    monkeypatch.chdir(tmp_path)
    app = create_app()
    app.state.reference_search = FakeSearch()
    app.state.knowledge_base.upload(
        title="用户资料",
        filename="kb.md",
        content_type="text/markdown",
        content=("旧港 用户知识库 记忆实验 伏笔 " * 40).encode("utf-8"),
        project_id="default",
    )
    inputs = {
        "project_id": "default",
        "stage_configs": {
            "info": {
                "reference_mode": "smart_search",
                "enable_web_search": True,
                "reference_keywords": ["旧港", "记忆实验"],
                "reference_query_intent": "检索结构与设定，不抄桥段",
            }
        },
    }
    _enrich_reference_summary(app, inputs)
    summary = inputs["stage_configs"]["info"]["reference_summary"]
    event_types = [event["type"] for event in inputs["rag_events"]]
    assert "联网参考（优先）" in summary
    assert "用户知识库命中（补充）" in summary
    assert summary.index("联网参考（优先）") < summary.index("用户知识库命中（补充）")
    assert "web_results_found" in event_types
    assert "rag_results_found" in event_types
    assert "reference_context_merged" in event_types
    assert "reference_context_injected" in event_types


def test_pause_and_resume_api_marks_run(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    _configure_test_client_provider(client)
    run_id = "pause-api"
    created = client.post("/api/runs", json={"workflow_id": "default-novel-workflow", "run_id": run_id, "inputs": {}})
    assert created.status_code == 200
    pause = client.post(f"/api/runs/{run_id}/pause").json()
    assert pause["status"] == "pause_requested"
    stored = client.get(f"/api/runs/{run_id}").json()
    assert stored["pause_requested"] is True
    resume = client.post(f"/api/runs/{run_id}/resume").json()
    assert resume["status"] == "resumed"
    stored = client.get(f"/api/runs/{run_id}").json()
    assert stored["pause_requested"] is False


def test_rag_empty_knowledge_base_blocks_stream(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    _configure_test_client_provider(client)
    inputs = {
        "project_id": "empty-kb",
        "stage_configs": {
            "info": {
                "reference_mode": "knowledge_base",
                "reference_query_intent": "检索用户上传资料",
                "reference_keywords": ["旧港"],
            }
        },
    }
    with client.stream(
        "POST",
        "/api/runs/stream",
        json={"workflow_id": "default-novel-workflow", "run_id": "blocked-rag", "inputs": inputs},
    ) as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())
    assert any("run_blocked" in line for line in lines)


def test_live_run_blocks_incomplete_real_provider_before_stream(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = next(item for item in client.get("/api/providers").json() if item["id"] == "openai-compatible")
    provider["base_url"] = ""
    provider["api_key_env"] = ""
    provider["enabled"] = True
    client.post("/api/providers", json=provider)
    workflow = client.get("/api/workflows/default").json()
    for node in workflow["nodes"]:
        if node["type"] in {"info_recommend", "summary", "outline", "detail_outline", "chapter_text"}:
            node["provider_profile_id"] = "openai-compatible"
    client.post("/api/workflows", json=workflow)

    response = client.post(
        "/api/runs/stream",
        json={
            "workflow_id": workflow["id"],
            "run_id": "blocked-provider",
            "inputs": {"execution_mode": "live", "project_id": "provider-blocked"},
        },
    )

    assert response.status_code == 409
    assert "Provider 配置不完整" in response.json()["detail"]
    assert "缺少 Base URL" in response.json()["detail"]


@pytest.mark.asyncio
async def test_stream_runner_events_can_skip_input_reference_events(monkeypatch):
    from types import SimpleNamespace
    import novel_workflow.api.sse as sse

    class FakeStore:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def append_event(self, run_id: str, event: dict) -> None:
            self.events.append({"run_id": run_id, **event})

    class FakeRunner:
        def __init__(self, **kwargs) -> None:
            del kwargs

        async def run(self, workflow, *, run_id, inputs):
            del workflow, inputs
            yield {"type": "run_resumed", "run_id": run_id}

    app = SimpleNamespace(
        state=SimpleNamespace(
            providers=object(),
            wiki_store=object(),
            run_store=FakeStore(),
        )
    )
    inputs = {"rag_events": [{"type": "reference_collection_started", "source": "smart_search"}]}
    monkeypatch.setattr(sse, "NovelWorkflowRunner", FakeRunner)

    with_input = [payload async for payload in sse.stream_runner_events(app, object(), "run-a", inputs)]
    without_input = [payload async for payload in sse.stream_runner_events(app, object(), "run-b", inputs, emit_input_events=False)]

    assert "reference_collection_started" in with_input[0]
    assert all("reference_collection_started" not in payload for payload in without_input)
    assert any("run_resumed" in payload for payload in without_input)


def test_run_insight_subresource_apis(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    _configure_test_client_provider(client)
    run_id = "api-run"
    approver = _approve_streaming_brief_later(client, run_id)
    with client.stream(
        "POST",
        "/api/runs/stream",
        json={"workflow_id": "default-novel-workflow", "run_id": run_id, "inputs": {"project_id": "p-api", "title": "雾港 API"}},
    ) as response:
        assert response.status_code == 200
        for _ in response.iter_lines():
            pass
    approver.join(timeout=1)

    quality = client.get(f"/api/runs/{run_id}/quality").json()
    chapters = client.get(f"/api/runs/{run_id}/chapters").json()
    graph = client.get(f"/api/runs/{run_id}/character-graph").json()
    writing = client.get(f"/api/runs/{run_id}/writing").json()
    world = client.get(f"/api/runs/{run_id}/worldbuilding").json()
    wiki = client.get(f"/api/runs/{run_id}/wiki-state").json()
    variants = client.get(f"/api/runs/{run_id}/variants").json()
    assert quality["quality_events"]
    assert chapters["chapter_progress"]
    assert graph["character_graph"]["nodes"]
    assert writing["chapter_drafts"]
    assert world["worldbuilding"]
    assert wiki["wiki_state"]
    assert variants["selected_variants"] == []
    assert variants["chapter_drafts"]
    assert variants["token_estimates"]


def _approve_streaming_brief_later(client, run_id: str):
    def approve() -> None:
        for _ in range(120):
            time.sleep(0.05)
            response = client.get(f"/api/runs/{run_id}")
            if response.status_code != 200:
                continue
            stored = response.json()
            approval = stored.get("approval") or {}
            if approval.get("required"):
                artifact = _approved_test_artifact(approval.get("artifact"))
                client.post(
                    f"/api/runs/{run_id}/approve-artifact",
                    json={"node_id": approval.get("node_id") or "info", "output_key": approval.get("output_key") or "info_recommend", "artifact": artifact},
                )

    thread = threading.Thread(target=approve, daemon=True)
    thread.start()
    return thread
