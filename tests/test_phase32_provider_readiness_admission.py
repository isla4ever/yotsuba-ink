from __future__ import annotations

import json
import multiprocessing
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from novel_workflow.orchestration.phase32_provider_readiness_admission import (
    Phase32ProviderReadinessAdmissionError,
    admit_phase32_provider_readiness,
    continuity_acceptance_provider_readiness_policy,
    current_phase32_provider_readiness_verdict,
    require_current_phase32_provider_readiness,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.storage.phase32_provider_readiness_store import (
    Phase32ProviderReadinessAdmission,
    Phase32ProviderReadinessAdmissionPolicy,
    Phase32ProviderReadinessStore,
    Phase32ProviderReadinessStoreError,
    readiness_admission_ref,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.graph_run_definition import freeze_graph_run_definition
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE


OBSERVED_AT = datetime.fromisoformat("2026-08-23T13:00:00+08:00")


def _write_admission_in_process(
    root: str,
    values: dict[str, object],
    start,
    results,
) -> None:
    admission = Phase32ProviderReadinessAdmission.model_validate(values)
    start.wait(timeout=10)
    try:
        Phase32ProviderReadinessStore(Path(root)).write(admission)
    except Phase32ProviderReadinessStoreError:
        results.put("conflict")
    else:
        results.put("written")


def _definition(tmp_path: Path):
    return create_phase32_run_fixture(
        tmp_path / "run",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="readiness-admission-run",
        project_id="readiness-admission-project",
        creative_intent="验证持久 readiness admission",
        workflow_id="official.screenplay_sample",
    ).definition


def _policy(**updates: object) -> Phase32ProviderReadinessAdmissionPolicy:
    values: dict[str, object] = {
        "required_model_id": "phase32-fixture-model",
        "required_profile_kind": "production",
        "max_pricing_age_hours": 24,
        "max_admission_age_seconds": 900,
    }
    values.update(updates)
    return Phase32ProviderReadinessAdmissionPolicy.model_validate(values)


def test_continuity_policy_is_code_owned_and_strict() -> None:
    policy = continuity_acceptance_provider_readiness_policy()

    assert policy.require_canonical_workflow is True
    assert policy.require_text_only is True
    assert policy.required_model_id == "deepseek-v4-pro"
    assert policy.required_profile_kind == "continuity_acceptance"
    assert policy.max_pricing_age_hours == 24


def test_admission_is_redacted_content_addressed_and_idempotent(tmp_path: Path) -> None:
    definition = _definition(tmp_path)
    store = Phase32ProviderReadinessStore(tmp_path / "readiness")
    resolved: list[str] = []

    def resolve_secret(secret_ref: str) -> str:
        resolved.append(secret_ref)
        return "private-provider-key-must-not-persist"

    admission = admit_phase32_provider_readiness(
        definition,
        store=store,
        policy=_policy(),
        secret_resolver=resolve_secret,
        now=OBSERVED_AT,
    )
    replay = admit_phase32_provider_readiness(
        definition,
        store=store,
        policy=_policy(),
        secret_resolver=resolve_secret,
        now=OBSERVED_AT,
    )

    assert replay == admission
    assert admission.verdict == "ready"
    assert admission.definition_digest == definition.definition_digest
    assert admission.observed_at == "2026-08-23T05:00:00+00:00"
    assert admission.expires_at == "2026-08-23T05:15:00+00:00"
    assert admission.report.observed_at == admission.observed_at
    assert admission.report.require_canonical_workflow is True
    assert admission.report.require_text_only is True
    assert len(store.list(definition.run_id)) == 1
    assert resolved

    serialized = admission.model_dump_json()
    assert "private-provider-key-must-not-persist" not in serialized
    assert "phase32-fixture.invalid" not in serialized
    for forbidden_field in (
        '"base_url"',
        '"secret_ref"',
        '"secret_value"',
        '"source_url"',
        '"prompt"',
        '"payload"',
    ):
        assert forbidden_field not in serialized

    verdict = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=_policy(),
        now=OBSERVED_AT + timedelta(minutes=10),
    )
    assert verdict.ready is True
    assert verdict.issue_codes == ()
    restarted_store = Phase32ProviderReadinessStore(store.root)
    assert (
        require_current_phase32_provider_readiness(
            definition,
            store=restarted_store,
            policy=_policy(),
            now=OBSERVED_AT + timedelta(minutes=10),
        )
        == admission
    )


def test_current_verdict_fails_closed_on_expiry_definition_or_policy_drift(
    tmp_path: Path,
) -> None:
    definition = _definition(tmp_path)
    store = Phase32ProviderReadinessStore(tmp_path / "readiness")
    policy = _policy()
    admit_phase32_provider_readiness(
        definition,
        store=store,
        policy=policy,
        secret_resolver=lambda _ref: "configured",
        now=OBSERVED_AT,
    )

    expired = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=policy,
        now=OBSERVED_AT + timedelta(seconds=900),
    )
    assert expired.ready is False
    assert "readiness_admission_expired" in expired.issue_codes

    future = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=policy,
        now=OBSERVED_AT - timedelta(seconds=1),
    )
    assert future.ready is False
    assert future.issue_codes == ("readiness_observation_in_future",)

    drifted_definition = freeze_graph_run_definition(
        run_id=definition.run_id,
        project_id=definition.project_id,
        workflow_id=definition.workflow_id,
        workflow_revision=definition.workflow_revision,
        workflow_digest=definition.workflow_digest,
        route_contract=definition.route_contract,
        scale_profile=definition.scale_profile,
        inputs=definition.inputs,
        provider_bindings_by_stage=definition.provider_bindings_by_stage,
        export_profile=definition.export_profile,
        created_at="2026-08-23T12:00:01+08:00",
    )
    drifted = current_phase32_provider_readiness_verdict(
        drifted_definition,
        store=store,
        policy=policy,
        now=OBSERVED_AT + timedelta(minutes=1),
    )
    assert drifted.ready is False
    assert drifted.issue_codes == (
        "readiness_definition_drift",
        "readiness_report_definition_mismatch",
    )

    policy_drift = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=_policy(max_admission_age_seconds=600),
        now=OBSERVED_AT + timedelta(minutes=1),
    )
    assert policy_drift.ready is False
    assert policy_drift.issue_codes == ("readiness_policy_mismatch",)

    with pytest.raises(Phase32ProviderReadinessAdmissionError) as captured:
        require_current_phase32_provider_readiness(
            definition,
            store=store,
            policy=policy,
            now=OBSERVED_AT + timedelta(seconds=900),
        )
    assert "readiness_admission_expired" in captured.value.verdict.issue_codes


def test_blocked_or_missing_configuration_never_becomes_current_ready(
    tmp_path: Path,
) -> None:
    definition = _definition(tmp_path)
    store = Phase32ProviderReadinessStore(tmp_path / "readiness")
    policy = _policy()

    missing = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=policy,
        now=OBSERVED_AT,
    )
    assert missing.ready is False
    assert missing.issue_codes == ("readiness_admission_missing",)

    def fail_secret_resolution(_ref: str) -> str:
        raise RuntimeError("secret-material-must-not-escape")

    ready_admission = admit_phase32_provider_readiness(
        definition,
        store=store,
        policy=policy,
        secret_resolver=lambda _ref: "configured",
        now=OBSERVED_AT,
    )
    assert ready_admission.verdict == "ready"

    admission = admit_phase32_provider_readiness(
        definition,
        store=store,
        policy=policy,
        secret_resolver=fail_secret_resolution,
        now=OBSERVED_AT + timedelta(minutes=1),
    )
    assert admission.verdict == "blocked"
    assert "secret_resolution_failed" in admission.report.issue_codes
    assert "secret-material-must-not-escape" not in admission.model_dump_json()

    blocked = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=policy,
        now=OBSERVED_AT + timedelta(minutes=2),
    )
    assert blocked.ready is False
    assert blocked.issue_codes[:2] == (
        "readiness_configuration_blocked",
        "secret_resolution_failed",
    )
    assert "secret_missing" in blocked.issue_codes


def test_tampering_and_caller_extended_expiry_fail_closed(tmp_path: Path) -> None:
    definition = _definition(tmp_path)
    store = Phase32ProviderReadinessStore(tmp_path / "readiness")
    admission = admit_phase32_provider_readiness(
        definition,
        store=store,
        policy=_policy(),
        secret_resolver=lambda _ref: "configured",
        now=OBSERVED_AT,
    )

    extended = admission.model_dump(mode="json")
    extended["expires_at"] = "2026-08-24T05:00:00+00:00"
    with pytest.raises(ValueError, match="expiry differs"):
        Phase32ProviderReadinessAdmission.model_validate(extended)

    path = (
        store.root
        / definition.run_id
        / f"{admission.admission_ref}.json"
    )
    corrupted = json.loads(path.read_text(encoding="utf-8"))
    corrupted["definition_digest"] = "f" * 64
    path.write_text(json.dumps(corrupted), encoding="utf-8")

    with pytest.raises(Phase32ProviderReadinessStoreError):
        store.latest(definition.run_id)
    verdict = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=_policy(),
        now=OBSERVED_AT + timedelta(minutes=1),
    )
    assert verdict.ready is False
    assert verdict.issue_codes == ("readiness_admission_unreadable",)


@pytest.mark.parametrize(
    "forge_report",
    (
        lambda report: report["stages"][0].update({"secret_present": False}),
        lambda report: report["stages"][0].update(
            {
                "secret_present": False,
                "ready": False,
                "issue_codes": ["secret_missing"],
            }
        ),
        lambda report: report["stages"].pop(),
    ),
    ids=(
        "contradictory-ready-stage",
        "unaggregated-blocked-stage",
        "missing-final-stage",
    ),
)
def test_content_addressed_ready_admission_rejects_semantic_forgery(
    tmp_path: Path,
    forge_report,
) -> None:
    definition = _definition(tmp_path)
    admission = admit_phase32_provider_readiness(
        definition,
        store=Phase32ProviderReadinessStore(tmp_path / "readiness"),
        policy=_policy(),
        secret_resolver=lambda _ref: "configured",
        now=OBSERVED_AT,
    )
    forged = admission.model_dump(mode="json")
    forge_report(forged["report"])
    forged["report_digest"] = canonical_digest(forged["report"])
    forged["admission_ref"] = readiness_admission_ref(
        {key: value for key, value in forged.items() if key != "admission_ref"}
    )

    with pytest.raises(ValueError, match="(?:Ready )?Provider "):
        Phase32ProviderReadinessAdmission.model_validate(forged)


@pytest.mark.parametrize(
    ("field", "value", "issue_code"),
    (
        (
            "workflow_id",
            "official.long_novel",
            "readiness_report_workflow_mismatch",
        ),
        (
            "creation_route_id",
            "long_novel",
            "readiness_report_route_mismatch",
        ),
    ),
)
def test_current_verdict_rejects_rehashed_report_identity_drift(
    tmp_path: Path,
    field: str,
    value: str,
    issue_code: str,
) -> None:
    definition = _definition(tmp_path)
    source = Phase32ProviderReadinessStore(tmp_path / "readiness-source")
    admission = admit_phase32_provider_readiness(
        definition,
        store=source,
        policy=_policy(),
        secret_resolver=lambda _ref: "configured",
        now=OBSERVED_AT,
    )
    forged = admission.model_dump(mode="json")
    forged["report"][field] = value
    forged["report_digest"] = canonical_digest(forged["report"])
    forged["admission_ref"] = readiness_admission_ref(
        {key: item for key, item in forged.items() if key != "admission_ref"}
    )
    parsed = Phase32ProviderReadinessAdmission.model_validate(forged)
    target = Phase32ProviderReadinessStore(tmp_path / "readiness-target")
    target.write(parsed)

    verdict = current_phase32_provider_readiness_verdict(
        definition,
        store=target,
        policy=_policy(),
        now=OBSERVED_AT + timedelta(minutes=1),
    )

    assert verdict.ready is False
    assert issue_code in verdict.issue_codes


def test_current_verdict_rejects_rehashed_stage_provider_identity_drift(
    tmp_path: Path,
) -> None:
    definition = _definition(tmp_path)
    source = Phase32ProviderReadinessStore(tmp_path / "readiness-source")
    admission = admit_phase32_provider_readiness(
        definition,
        store=source,
        policy=_policy(),
        secret_resolver=lambda _ref: "configured",
        now=OBSERVED_AT,
    )
    forged = admission.model_dump(mode="json")
    forged["report"]["stages"][0]["provider_profile_id"] = "another-provider"
    forged["report_digest"] = canonical_digest(forged["report"])
    forged["admission_ref"] = readiness_admission_ref(
        {key: item for key, item in forged.items() if key != "admission_ref"}
    )
    parsed = Phase32ProviderReadinessAdmission.model_validate(forged)
    target = Phase32ProviderReadinessStore(tmp_path / "readiness-target")
    target.write(parsed)

    verdict = current_phase32_provider_readiness_verdict(
        definition,
        store=target,
        policy=_policy(),
        now=OBSERVED_AT + timedelta(minutes=1),
    )

    assert verdict.ready is False
    assert verdict.issue_codes == ("readiness_report_stage_identity_mismatch",)


@pytest.mark.parametrize(
    "mutation",
    ("missing", "extra", "reordered", "replaced"),
)
def test_current_verdict_rejects_rehashed_stage_manifest_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    definition = _definition(tmp_path)
    admission = admit_phase32_provider_readiness(
        definition,
        store=Phase32ProviderReadinessStore(tmp_path / "readiness-source"),
        policy=_policy(),
        secret_resolver=lambda _ref: "configured",
        now=OBSERVED_AT,
    )
    forged = admission.model_dump(mode="json")
    report = forged["report"]
    if mutation == "missing":
        report["stages"].pop()
        report["expected_stage_ids"].pop()
    elif mutation == "extra":
        extra = dict(report["stages"][-1])
        extra["stage_id"] = "unexpected_stage"
        report["stages"].append(extra)
        report["expected_stage_ids"].append("unexpected_stage")
    elif mutation == "reordered":
        report["stages"].reverse()
        report["expected_stage_ids"].reverse()
    else:
        report["stages"][0]["stage_id"] = "replacement_stage"
        report["expected_stage_ids"][0] = "replacement_stage"
    forged["report_digest"] = canonical_digest(report)
    forged["admission_ref"] = readiness_admission_ref(
        {key: item for key, item in forged.items() if key != "admission_ref"}
    )
    parsed = Phase32ProviderReadinessAdmission.model_validate(forged)
    target = Phase32ProviderReadinessStore(tmp_path / "readiness-target")
    target.write(parsed)

    verdict = current_phase32_provider_readiness_verdict(
        definition,
        store=target,
        policy=_policy(),
        now=OBSERVED_AT + timedelta(minutes=1),
    )

    assert verdict.ready is False
    assert "readiness_report_stage_manifest_mismatch" in verdict.issue_codes


def test_pricing_can_expire_before_the_admission_ttl(tmp_path: Path) -> None:
    definition = _definition(tmp_path)
    store = Phase32ProviderReadinessStore(tmp_path / "readiness")
    policy = _policy(max_admission_age_seconds=3_600)
    near_pricing_expiry = datetime.fromisoformat("2026-08-24T11:59:00+08:00")
    admission = admit_phase32_provider_readiness(
        definition,
        store=store,
        policy=policy,
        secret_resolver=lambda _ref: "configured",
        now=near_pricing_expiry,
    )
    assert admission.verdict == "ready"
    assert admission.expires_at == "2026-08-24T04:00:00+00:00"

    verdict = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=policy,
        now=near_pricing_expiry + timedelta(minutes=1),
    )
    assert verdict.ready is False
    assert verdict.issue_codes == ("readiness_admission_expired",)


def test_same_instant_observations_are_serialized_across_processes(
    tmp_path: Path,
) -> None:
    definition = _definition(tmp_path)
    policy = _policy()
    ready = admit_phase32_provider_readiness(
        definition,
        store=Phase32ProviderReadinessStore(tmp_path / "ready-source"),
        policy=policy,
        secret_resolver=lambda _ref: "configured",
        now=OBSERVED_AT,
    )
    blocked = admit_phase32_provider_readiness(
        definition,
        store=Phase32ProviderReadinessStore(tmp_path / "blocked-source"),
        policy=policy,
        secret_resolver=lambda _ref: None,
        now=OBSERVED_AT,
    )
    assert ready.admission_ref != blocked.admission_ref

    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    target_root = tmp_path / "concurrent-readiness"
    processes = [
        context.Process(
            target=_write_admission_in_process,
            args=(
                str(target_root),
                admission.model_dump(mode="json"),
                start,
                results,
            ),
        )
        for admission in (ready, blocked)
    ]
    for process in processes:
        process.start()
    start.set()
    outcomes = sorted(results.get(timeout=15) for _ in processes)
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0

    assert outcomes == ["conflict", "written"]
    assert len(Phase32ProviderReadinessStore(target_root).list(definition.run_id)) == 1
