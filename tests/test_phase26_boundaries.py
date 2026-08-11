from __future__ import annotations

from pathlib import Path
import json
import re
import tomllib

from novel_workflow.output_contracts.artifacts_vnext import STAGE_ORDER
from novel_workflow.output_contracts.prompt_materials import PROMPT_MATERIAL_KEYS
from novel_workflow.runtime.graph.narrative_graph import build_narrative_graph
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.workflows.templates import default_prompt_templates, default_workflow


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "novel_workflow"


def _read_python_files(*parts: str) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for part in parts
        for path in (SRC / part).rglob("*.py")
        if path.exists()
    )


def test_phase26_has_one_eight_stage_production_order() -> None:
    assert STAGE_ORDER == (
        "info",
        "characters",
        "summary",
        "outline",
        "detail",
        "text",
        "cover",
        "export",
    )
    assert NarrativeRunState.__annotations__["artifact_refs"]
    assert build_narrative_graph


def test_prompt_metadata_and_frontend_fixture_match_graph_context_materials() -> None:
    fixture = json.loads(
        (ROOT / "apps" / "web" / "test-fixtures" / "prompt-material-contract.json")
        .read_text(encoding="utf-8")
    )
    backend_contract = {
        stage_id: list(keys) for stage_id, keys in PROMPT_MATERIAL_KEYS.items()
    }
    prompt_metadata = {
        prompt.stage_type: prompt.variables for prompt in default_prompt_templates()
    }
    assert backend_contract == fixture
    assert prompt_metadata == fixture


def test_default_text_prompt_keeps_version_identity_in_langgraph() -> None:
    text_prompt = next(
        prompt for prompt in default_prompt_templates() if prompt.stage_type == "text"
    )

    assert "不得返回 version_id" in text_prompt.content
    assert "版本身份由 LangGraph 运行时确定性生成" in text_prompt.content


def test_production_uses_langgraph_without_a_direct_langchain_dependency() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]
    direct_names = {
        re.split(r"[<>=!~\[]", dependency, maxsplit=1)[0].strip().lower()
        for dependency in dependencies
    }
    assert not {name for name in direct_names if name.startswith("langchain")}

    source = _read_python_files("")
    assert re.search(r"(?m)^\s*(?:from|import)\s+langchain(?:\.|\s|$)", source) is None


def test_api_and_graph_do_not_import_deleted_production_paths() -> None:
    source = _read_python_files("api", "runtime/graph", "output_contracts", "storage")
    forbidden_imports = (
        "novel_workflow.orchestration",
        "novel_workflow.stages",
        "novel_workflow.acceptance",
        "workflows.runner",
        "runtime_engine",
    )
    for token in forbidden_imports:
        assert token not in source


def test_deleted_runtime_files_cannot_return_as_importable_production_paths() -> None:
    deleted = (
        SRC / "workflows" / "runner.py",
        SRC / "orchestration" / "stream.py",
        SRC / "orchestration" / "control.py",
        SRC / "providers" / "fallback.py",
        SRC / "providers" / "stage_probe.py",
        SRC / "storage" / "run_store.py",
        SRC / "storage" / "run_control_store.py",
        SRC / "output_contracts" / "detail_outline.py",
    )
    assert all(not path.exists() for path in deleted)


def test_graph_and_provider_contracts_have_no_implicit_fallback_controls() -> None:
    source = _read_python_files("runtime/graph", "providers", "workflows")
    for token in (
        "fallback_targets",
        "fallback_review_waves",
        "def generate_structured(",
        "parse_json_object_result",
        "fallback_reason",
    ):
        assert token not in source


def test_workflow_configuration_does_not_duplicate_runtime_or_artifact_authorities() -> None:
    forbidden = {
        "params",
        "input_refs",
        "output_key",
        "memory_policy",
        "output_schema",
        "quality_policy",
    }
    for node in default_workflow().nodes:
        assert forbidden.isdisjoint(node.model_fields_set)
    assert not (SRC / "workflows" / "preference_calibration_policy.py").exists()


def test_production_run_routes_do_not_read_the_archive() -> None:
    source = (SRC / "api" / "routes" / "runs.py").read_text(encoding="utf-8")
    assert "legacy_run_viewer" not in source
    assert "archived_run_read_only" not in source


def test_deleted_frontend_quality_and_revision_contracts_cannot_return() -> None:
    contracts = ROOT / "apps" / "web" / "src" / "features" / "pipeline" / "contracts"
    deleted = (
        contracts / "chapterReview.ts",
        contracts / "chapterRevision.ts",
        contracts / "quality.ts",
    )
    assert all(not path.exists() for path in deleted)


def test_deleted_frontend_compatibility_helpers_cannot_return() -> None:
    running = ROOT / "apps" / "web" / "src" / "features" / "pipeline" / "running"
    deleted = (
        running / "artifactParsing.ts",
        running / "infoWorldbuildingDigest.ts",
        running / "stageViewData.ts",
    )
    assert all(not path.exists() for path in deleted)

    project_scope = (
        ROOT / "apps" / "web" / "src" / "features" / "pipeline" / "state" / "projectScope.ts"
    ).read_text(encoding="utf-8")
    assert "Project-scoped storage requires an active project" in project_scope
    assert "return projectId ?" not in project_scope
