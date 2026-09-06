from __future__ import annotations

import json
from pathlib import Path
import tomllib

import pytest
from fastapi.testclient import TestClient

from novel_workflow import __version__
from novel_workflow.api.app import create_app


ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_are_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))

    assert project["project"]["version"] == __version__ == "0.1.0"
    assert package["version"] == __version__
    assert create_app().version == __version__


def test_health_reports_only_canonical_creation_workflows(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = TestClient(create_app()).get("/api/health")

    assert response.status_code == 200
    assert response.json()["workflows"] == [
        "official.screenplay_sample",
        "official.short_novel",
        "official.long_novel",
    ]


def test_openapi_does_not_publish_retired_workflow_or_prompt_writers(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = TestClient(create_app()).get("/openapi.json").json()["paths"]

    assert not any(path.startswith("/api/workflows") for path in paths)
    assert not any(path.startswith("/api/prompts") for path in paths)


def test_openapi_creation_contract_has_no_unreleased_workflow_mode(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    schemas = TestClient(create_app()).get("/openapi.json").json()["components"][
        "schemas"
    ]
    selection = schemas["WorkflowSelection"]

    assert selection["properties"]["mode"]["const"] == "existing"
    assert "new_workflow_label" not in selection["properties"]


def test_cors_accepts_local_ui_and_rejects_untrusted_origin(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())

    allowed = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5176"})
    rejected = client.get("/api/health", headers={"Origin": "https://untrusted.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5176"
    assert "access-control-allow-origin" not in rejected.headers


def test_cors_requires_explicit_origins(monkeypatch) -> None:
    monkeypatch.setenv("YOTSUBA_CORS_ORIGINS", "*")

    with pytest.raises(ValueError, match="explicit trusted origins"):
        create_app()
