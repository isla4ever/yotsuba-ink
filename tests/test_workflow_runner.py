from __future__ import annotations

import pytest
import asyncio
import threading
import time

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.templates import default_workflow


@pytest.mark.asyncio
async def test_default_workflow_runs_with_mock_providers(tmp_path):
    workflow = default_workflow()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = ProviderRegistry.from_env()
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
    assert any(event["type"] == "variant_generated" for event in events)
    assert any(event["type"] == "variant_judged" for event in events)
    assert any(event["type"] == "best_variant_selected" for event in events)
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
    assert saved["state"]["selected_variants"]
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
    assert workflow.version == "0.9.0"
    assert required_keys <= set(fields)
    assert all(fields[key].required for key in required_keys)
    assert reference_keys <= set(fields)
    assert fields["reference_mode"].default == "smart_search"
    assert info.quality_policy.min_score == 0.82
    assert "模板味风险" in info.quality_policy.checks


def test_default_workflow_has_canvas_layout_without_crosscutting_execution_nodes():
    workflow = default_workflow()
    assert workflow.canvas_layout.crosscutting_visible is True
    assert "wiki-layer" in workflow.canvas_layout.nodes
    assert "quality-layer" in workflow.canvas_layout.nodes
    assert workflow.canvas_layout.nodes["wiki-layer"].x < workflow.canvas_layout.nodes["info"].x
    assert workflow.canvas_layout.nodes["quality-layer"].x > workflow.canvas_layout.nodes["info"].x
    assert workflow.canvas_layout.nodes["summary"].y > workflow.canvas_layout.nodes["info"].y
    assert all(node.id not in {"wiki-layer", "quality-layer"} for node in workflow.nodes)
    assert all(edge.source not in {"wiki-layer", "quality-layer"} for edge in workflow.edges)


def test_default_workflow_order_runs_text_before_cover():
    from novel_workflow.workflows.compiler import NovelWorkflowCompiler

    workflow = default_workflow()
    order = [node.id for node in NovelWorkflowCompiler().compile_order(workflow)]
    assert order == ["info", "summary", "outline", "detail", "text", "cover", "export"]
    assert all(edge.source != "summary" or edge.target != "cover" for edge in workflow.edges)
    assert any(edge.source == "text" and edge.target == "cover" for edge in workflow.edges)


def test_default_workflow_has_quality_mode_and_variant_policy():
    workflow = default_workflow()
    text = next(node for node in workflow.nodes if node.id == "text")
    info = next(node for node in workflow.nodes if node.id == "info")
    assert workflow.quality_mode == "balanced"
    assert text.variant_policy.enabled is True
    assert text.variant_policy.candidate_count == 2
    assert info.variant_policy.enabled is False


@pytest.mark.asyncio
async def test_deep_mode_does_not_generate_variants_for_story_brief(tmp_path):
    workflow = default_workflow()
    workflow.quality_mode = "deep"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = ProviderRegistry.from_env()
    run_id = "deep-run"
    store.create(run_id, workflow, {"project_id": "p-deep", "title": "深度测试"})
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, {"project_id": "p-deep", "title": "深度测试"})
    info_variants = [event for event in events if event["type"] == "variant_generated" and event.get("node_id") == "info"]
    summary_variants = [event for event in events if event["type"] == "variant_generated" and event.get("node_id") == "summary"]
    assert not info_variants
    assert len(summary_variants) >= 3
    assert not any(event["type"] == "best_variant_selected" and event.get("node_id") == "info" for event in events)


@pytest.mark.asyncio
async def test_incomplete_detail_outline_blocks_writing(tmp_path, monkeypatch):
    workflow = default_workflow()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = ProviderRegistry.from_env()

    async def short_detail(prompt, *, task_name, context):
        if task_name == "detail_outline":
            return "第1章：只有一章。"
        return "人物 冲突 伏笔 世界观 正文 " * 40

    monkeypatch.setattr(providers.text_provider, "generate_text", short_detail)
    run_id = "blocked-writing"
    store.create(run_id, workflow, {"project_id": "p-block", "title": "阻断测试"})
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, {"project_id": "p-block", "title": "阻断测试"})
    assert any(event["type"] == "node_failed" and event.get("node_id") == "text" for event in events)
    assert not any(event["type"] == "phase_changed" and event.get("phase") == "writing" for event in events)


@pytest.mark.asyncio
async def test_balanced_mode_creates_revision_directive_for_chapter_handoff(tmp_path, monkeypatch):
    workflow = default_workflow()
    workflow.quality_mode = "balanced"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = ProviderRegistry.from_env()

    async def no_handoff_text(prompt, *, task_name, context):
        if task_name == "chapter_text":
            return "人物 冲突 伏笔 世界观 正文 " * 40
        if task_name == "detail_outline":
            return (
                "第1章：旧案开启，投放伏笔。\n"
                "第2章：人物追查线索，推进伏笔。\n"
                "第3章：关系变化，继续追查。"
            )
        return "人物 冲突 伏笔 世界观 结局 角色弧 第1卷：旧案开启 " * 20

    monkeypatch.setattr(providers.text_provider, "generate_text", no_handoff_text)
    run_id = "revision-run"
    inputs = {"project_id": "p-rev", "title": "修订测试", "stage_configs": {"detail": {"chapter_count": 3}, "text": {"chapter_count": 3}}}
    store.create(run_id, workflow, inputs)
    runner = NovelWorkflowRunner(providers=providers, wiki_store=wiki, run_store=store)
    events = await _run_with_brief_approval(runner, workflow, store, run_id, inputs)
    assert any(event["type"] == "revision_directive_created" and event.get("chapter") == "第2章" for event in events)
    assert any(event["type"] == "revision_applied" for event in events)
    saved = store.read(run_id)["state"]
    assert saved["revision_directives"]
    assert "[质量修订]" in saved["artifacts"]["chapters"]


@pytest.mark.asyncio
async def test_fast_mode_skips_revision_directives(tmp_path, monkeypatch):
    workflow = default_workflow()
    workflow.quality_mode = "fast"
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = ProviderRegistry.from_env()

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
async def test_worldbuilding_hard_conflict_blocks_pipeline(tmp_path, monkeypatch):
    workflow = default_workflow()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    providers = ProviderRegistry.from_env()

    async def conflict_text(prompt, *, task_name, context):
        if task_name == "summary":
            return "本阶段会推翻世界观硬设定，人物 冲突 伏笔 结局。"
        return "人物 冲突 伏笔 世界观 结局 角色弧 第1卷：旧案开启 " * 20

    monkeypatch.setattr(providers.text_provider, "generate_text", conflict_text)
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
        for _ in range(120):
            await asyncio.sleep(0.05)
            if store.approval_pending(run_id, node_id="info"):
                approval = store.read(run_id).get("approval") or {}
                artifact = f"{approval.get('artifact', '')}\n\n[人工定稿] 保留核心卖点、人物边界和世界观硬约束。"
                store.approve_artifact(run_id, node_id="info", output_key="info_recommend", artifact=artifact)
                return

    approver = asyncio.create_task(approve_when_needed())
    try:
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            events.append(event)
    finally:
        await approver
    return events


def test_provider_and_prompt_api_seed_defaults():
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    client = TestClient(create_app())
    providers = client.get("/api/providers").json()
    prompts = client.get("/api/prompts").json()
    workflows = client.get("/api/workflows").json()
    assert any(item["id"] == "mock-text" for item in providers)
    assert any(item["id"] == "prompt-info" for item in prompts)
    assert workflows[0]["global_inputs"]


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


def test_run_insight_subresource_apis(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
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
    assert variants["selected_variants"]


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
                artifact = f"{approval.get('artifact', '')}\n\n[人工定稿] API 测试确认稿。"
                client.post(
                    f"/api/runs/{run_id}/approve-artifact",
                    json={"node_id": "info", "output_key": "info_recommend", "artifact": artifact},
                )
                return

    thread = threading.Thread(target=approve, daemon=True)
    thread.start()
    return thread
