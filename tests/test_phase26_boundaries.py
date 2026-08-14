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
WEB_PIPELINE = ROOT / "apps" / "web" / "src" / "features" / "pipeline"


def _read_python_files(*parts: str) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for part in parts
        for path in (SRC / part).rglob("*.py")
        if path.exists()
    )


def _read_files(paths: tuple[Path, ...], suffixes: tuple[str, ...]) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for root in paths
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in suffixes
        and "__pycache__" not in path.parts
        and "archive" not in path.parts
        and ".test." not in path.name
    )


def test_phase27_has_one_eight_stage_production_order() -> None:
    assert STAGE_ORDER == (
        "brief",
        "spine",
        "cast",
        "volumes",
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


def test_default_text_prompt_keeps_runtime_owned_identity_in_langgraph() -> None:
    text_prompt = next(
        prompt for prompt in default_prompt_templates() if prompt.stage_type == "text"
    )

    assert "不输出 JSON" in text_prompt.content
    assert "纯文本流" in text_prompt.content


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
        "novel_workflow.orchestration.stream",
        "novel_workflow.orchestration.control",
        "novel_workflow.stages",
        "novel_workflow.acceptance",
        "workflows.runner",
        "runtime_engine",
    )
    for token in forbidden_imports:
        assert token not in source

    orchestration_files = {
        path.relative_to(SRC / "orchestration").as_posix()
        for path in (SRC / "orchestration").rglob("*.py")
    }
    assert orchestration_files == {"__init__.py", "run_preflight.py"}


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
        SRC / "workflows" / "book_scale_plan.py",
    )
    assert all(not path.exists() for path in deleted)


def test_phase27_production_authorities_have_no_retired_stage_identifiers() -> None:
    backend = _read_files(
        (SRC,),
        (".py",),
    )
    frontend = _read_files(
        (WEB_PIPELINE,),
        (".ts", ".tsx"),
    )
    defaults = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "runtime" / "novel_workflow" / "workflows" / "default-novel-workflow.json",
            *sorted((ROOT / "runtime" / "novel_workflow" / "prompts").glob("*.json")),
        )
    )
    production = "\n".join((backend, frontend, defaults))
    retired_symbols = re.compile(
        r"\b(?:BookScalePlan|SummaryArtifact|OutlineArtifact|ChapterPlan|DetailV[123]|detail_v[123])\b"
    )
    assert retired_symbols.search(production) is None

    retired_stage_assignment = re.compile(
        r"\b(?:stage_type|stage_id|active_stage_id|selectedStageType)\b\s*(?:=|:)\s*"
        r"[\"'](?:info|characters|summary|outline|info_recommend|detail_outline|chapter_text|cover_image|export_artifact)[\"']"
    )
    assert retired_stage_assignment.search(production) is None

    runtime_defaults = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "runtime" / "novel_workflow" / "workflows" / "default-novel-workflow.json",
            *sorted((ROOT / "runtime" / "novel_workflow" / "prompts").glob("*.json")),
        )
    )
    retired_runtime_value = re.compile(
        r"[\"'](?:info|characters|summary|outline|info_recommend|detail_outline|chapter_text|cover_image|export_artifact)[\"']"
    )
    assert retired_runtime_value.search(runtime_defaults) is None


def test_phase27_execution_code_does_not_relabel_the_brief_as_info() -> None:
    production_paths = (
        SRC / "runtime" / "graph" / "stage_executor.py",
        SRC / "api" / "routes" / "runs.py",
    )
    production = "\n".join(path.read_text(encoding="utf-8") for path in production_paths)
    assert re.search(r"\binfo(?:_id)?\b", production) is None


def test_retired_default_prompts_and_workflow_files_stay_deleted() -> None:
    retired = (
        "prompt-info.json",
        "prompt-characters.json",
        "prompt-summary.json",
        "prompt-outline.json",
    )
    prompt_root = ROOT / "runtime" / "novel_workflow" / "prompts"
    assert all(not (prompt_root / name).exists() for name in retired)


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
