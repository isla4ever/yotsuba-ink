from __future__ import annotations

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app


def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    return TestClient(create_app())


def short_intent() -> dict[str, object]:
    return {
        "creative_intent": "一名夜班急救调度员接到来自未来的报警电话，并发现每次干预都在改写家人的旧案。",
        "creation_kind": "novel",
        "novel_length_class": "short_novel",
        "requested_target": 20_000,
    }


def test_catalog_exposes_only_canonical_phase32_route_entries(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)

    response = api.get("/api/creation-wizard/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"routes", "workflow_catalog"}
    assert [item["route"]["route_id"] for item in payload["routes"]] == [
        "screenplay_sample",
        "short_novel",
        "long_novel",
    ]
    assert payload["routes"][2]["review_policy"]["route_id"] == "long_novel"
    assert [item["workflow_id"] for item in payload["workflow_catalog"][:3]] == [
        "official.screenplay_sample",
        "official.short_novel",
        "official.long_novel",
    ]
    assert not {
        "official-deepseek-fast",
        "official-deepseek-balanced",
        "official-deepseek-deep",
    } & {item["workflow_id"] for item in payload["workflow_catalog"]}


def test_recommendation_is_server_filtered_and_freezes_scale_profile(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)

    response = api.post(
        "/api/creation-wizard/recommend",
        json={"intent": short_intent()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["creation_route_id"] == "short_novel"
    assert payload["scale_profile"]["target"] == 20_000
    assert [item["workflow"]["workflow_id"] for item in payload["recommendations"]] == [
        "official.short_novel"
    ]


def test_resolve_accepts_only_an_existing_official_selection(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)

    existing = api.post(
        "/api/creation-wizard/resolve",
        json={
            "selection": {
                "intent": short_intent(),
                "mode": "existing",
                "workflow_id": "official.short_novel",
            }
        },
    )
    assert existing.status_code == 200
    assert existing.json()["selection_kind"] == "existing"
    assert existing.json()["selection"]["workflow_id"] == "official.short_novel"

    created = api.post(
        "/api/creation-wizard/resolve",
        json={
            "selection": {
                "intent": short_intent(),
                "mode": "new",
            }
        },
    )
    assert created.status_code == 422


def test_resolve_rejects_a_workflow_from_another_creation_route(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)

    response = api.post(
        "/api/creation-wizard/resolve",
        json={
            "selection": {
                "intent": short_intent(),
                "mode": "existing",
                "workflow_id": "official.screenplay_sample",
            }
        },
    )

    assert response.status_code == 422
    assert "does not match" in response.json()["detail"]
