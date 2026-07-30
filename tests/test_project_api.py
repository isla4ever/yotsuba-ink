from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.storage.project_schemas import ACCENT_HUE_SEQUENCE, next_accent_hue
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    return TestClient(create_app())


def _configure_text_provider(client: TestClient) -> None:
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


def test_project_create_copies_template_workflow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    created = client.post("/api/projects", json={"title": "雾港旧声", "summary": "声纹修复悬疑"})
    assert created.status_code == 200
    project = created.json()
    assert project["id"].startswith("proj-")
    assert project["workflow_id"] == f"wf-{project['id']}"
    assert project["status"] == "active"
    assert project["accent_hue"] == ACCENT_HUE_SEQUENCE[0]
    assert project["latest_run_id"] == ""
    assert project["created_at"] and project["updated_at"]

    workflow = client.get(f"/api/workflows/{project['workflow_id']}")
    assert workflow.status_code == 200
    assert workflow.json()["name"] == "雾港旧声"
    assert workflow.json()["is_template"] is False
    assert len(workflow.json()["nodes"]) == len(default_workflow().nodes)

    listed = client.get("/api/projects").json()
    assert [item["id"] for item in listed] == [project["id"]]
    assert client.get(f"/api/projects/{project['id']}").status_code == 200


def test_project_create_with_unknown_template_is_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/projects", json={"title": "无模板", "template_workflow_id": "missing-template"})
    assert response.status_code == 404


def test_project_create_clears_narrative_seeds_while_template_keeps_demo(tmp_path, monkeypatch):
    """Phase 12 M1：新作品的工作流副本清空叙事种子；default-novel-workflow 旧路径保持演示值。"""
    client = _client(tmp_path, monkeypatch)
    project = client.post("/api/projects", json={"title": "全新空白作品"}).json()

    workflow = client.get(f"/api/workflows/{project['workflow_id']}").json()
    info = next(node for node in workflow["nodes"] if node["id"] == "info")
    fields = {field["key"]: field for field in info["input_schema"]}
    for key in ("audience", "core_concept", "taboos", "reference_query_intent"):
        assert fields[key]["default"] == "", key
    for key in ("keywords", "reference_keywords"):
        assert fields[key]["default"] == [], key
    assert fields["core_concept"]["required"] is True
    # 结构性默认保留，故事字段以外的配置不受影响
    assert fields["genre"]["default"] == "悬疑"
    assert fields["target_words_range"]["default"] == "80-120 万字"
    global_fields = {field["key"]: field["default"] for field in workflow["global_inputs"]}
    assert global_fields["title"] == ""
    assert set(global_fields) == {"title"}

    # 旧路径不动：模板本体（直接跑 default-novel-workflow 的 demo/测试链路）仍带演示种子
    template = client.get("/api/workflows/default-novel-workflow").json()
    template_info = next(node for node in template["nodes"] if node["id"] == "info")
    template_fields = {field["key"]: field["default"] for field in template_info["input_schema"]}
    assert template_fields["core_concept"].startswith("旧港")
    assert template_fields["keywords"] == ["旧港", "记忆实验", "群像", "旧案"]
    assert {field["key"]: field["default"] for field in template["global_inputs"]}["title"] == "雾港旧声"


def test_accent_hue_assignment_is_deterministic(tmp_path, monkeypatch):
    assert next_accent_hue([]) == ACCENT_HUE_SEQUENCE[0]
    assert next_accent_hue([ACCENT_HUE_SEQUENCE[0]]) == ACCENT_HUE_SEQUENCE[1]
    assert next_accent_hue(list(ACCENT_HUE_SEQUENCE)) == ACCENT_HUE_SEQUENCE[0]
    assert next_accent_hue(list(ACCENT_HUE_SEQUENCE) + [ACCENT_HUE_SEQUENCE[0]]) == ACCENT_HUE_SEQUENCE[1]

    client = _client(tmp_path, monkeypatch)
    first = client.post("/api/projects", json={"title": "作品一"}).json()
    second = client.post("/api/projects", json={"title": "作品二"}).json()
    assert first["accent_hue"] == ACCENT_HUE_SEQUENCE[0]
    assert second["accent_hue"] == ACCENT_HUE_SEQUENCE[1]


def test_project_patch_updates_allowed_fields(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.post("/api/projects", json={"title": "旧标题"}).json()
    patched = client.patch(f"/api/projects/{project['id']}", json={"title": "新标题", "status": "archived", "accent_hue": 300})
    assert patched.status_code == 200
    data = patched.json()
    assert data["title"] == "新标题"
    assert data["status"] == "archived"
    assert data["accent_hue"] == 300
    assert data["workflow_id"] == project["workflow_id"]
    assert data["updated_at"] >= project["updated_at"]
    assert client.patch("/api/projects/missing-project", json={"title": "x"}).status_code == 404


def test_project_delete_refuses_when_runs_exist_and_suggests_archive(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.post("/api/projects", json={"title": "有历史的作品"}).json()
    client.app.state.run_store.create("run-guard-1", default_workflow(), {"title": "有历史的作品"}, project_id=project["id"])

    blocked = client.delete(f"/api/projects/{project['id']}")
    assert blocked.status_code == 409
    assert "归档" in blocked.json()["detail"]
    assert client.patch(f"/api/projects/{project['id']}", json={"status": "archived"}).status_code == 200

    empty = client.post("/api/projects", json={"title": "空作品"}).json()
    assert client.delete(f"/api/projects/{empty['id']}").status_code == 200
    assert client.get(f"/api/projects/{empty['id']}").status_code == 404
    assert client.get(f"/api/workflows/{empty['workflow_id']}").status_code == 404
    assert client.delete("/api/projects/missing-project").status_code == 404


def test_project_summary_aggregates_latest_run(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.post("/api/projects", json={"title": "聚合作品"}).json()

    empty_summary = client.get(f"/api/projects/{project['id']}/summary").json()
    assert empty_summary["latest_run"] is None
    assert empty_summary["title"] == "聚合作品"
    assert empty_summary["words"] == 0

    workflow = default_workflow()
    run_id = "summary-run-1"
    store = client.app.state.run_store
    store.create(run_id, workflow, {"project_id": project["id"], "title": "聚合作品"}, project_id=project["id"])
    state = NovelRunState(
        run_id=run_id,
        project_id=project["id"],
        workflow_id=workflow.id,
        inputs={"project_id": project["id"], "title": "聚合作品"},
        run_has_started=True,
        current_stage_id="text",
        current_stage_label="章节文本",
        current_stage_type="chapter_text",
        chapter_progress=[
            {"volume": "第一卷", "chapter": "第1章", "status": "completed", "words": 2100},
            {"volume": "第一卷", "chapter": "第2章", "status": "running", "words": 900},
        ],
    )
    store.update_state(run_id, state)

    summary = client.get(f"/api/projects/{project['id']}/summary").json()
    assert summary["latest_run"]["run_id"] == run_id
    assert summary["status"] == "running"
    assert summary["words"] == 3000
    assert summary["current_stage"]["id"] == "text"
    assert summary["project"]["id"] == project["id"]
    assert client.get("/api/projects/missing-project/summary").status_code == 404


def test_run_request_project_id_threads_to_run_and_history(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _configure_text_provider(client)
    project = client.post("/api/projects", json={"title": "贯通作品"}).json()

    created = client.post(
        "/api/runs",
        json={"workflow_id": project["workflow_id"], "run_id": "thread-run-1", "project_id": project["id"], "inputs": {"title": "贯通作品"}},
    )
    assert created.status_code == 200

    stored = client.get("/api/runs/thread-run-1").json()
    assert stored["project_id"] == project["id"]
    assert stored["inputs"]["project_id"] == project["id"]

    history = client.get("/api/runs/history", params={"project_id": project["id"]}).json()
    assert [item["run_id"] for item in history["items"]] == ["thread-run-1"]
    assert history["items"][0]["project_id"] == project["id"]

    refreshed = client.get(f"/api/projects/{project['id']}").json()
    assert refreshed["latest_run_id"] == "thread-run-1"
    assert refreshed["updated_at"] >= project["updated_at"]


def test_run_store_create_backfills_project_id(tmp_path):
    from novel_workflow.storage.run_store import RunStore

    store = RunStore(tmp_path / "runs")
    workflow = default_workflow()
    store.create("explicit-run", workflow, {}, project_id="proj-explicit")
    assert store.read("explicit-run")["project_id"] == "proj-explicit"

    store.create("inputs-run", workflow, {"project_id": "proj-from-inputs"})
    assert store.read("inputs-run")["project_id"] == "proj-from-inputs"

    store.create("legacy-run", workflow, {})
    assert store.read("legacy-run")["project_id"] == "legacy-run"

    summaries, _ = store.list_history(project_id="proj-explicit")
    assert [item["run_id"] for item in summaries] == ["explicit-run"]


def test_initial_stream_state_falls_back_to_stored_project_id(tmp_path):
    from novel_workflow.orchestration.stream import _initial_state
    from novel_workflow.storage.run_store import RunStore

    store = RunStore(tmp_path / "runs")
    workflow = default_workflow()
    store.create("fallback-run", workflow, {}, project_id="proj-topline")

    class _Runner:
        run_store = store

    state, resumed = _initial_state(_Runner(), workflow, "fallback-run", {})
    assert resumed is False
    assert state.project_id == "proj-topline"
