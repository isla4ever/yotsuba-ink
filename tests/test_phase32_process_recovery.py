from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from novel_workflow.orchestration.phase32_graph_execution import Phase32GraphExecutionService
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.runtime.graph.phase32_checkpointer import open_phase32_checkpointer
from novel_workflow.runtime.graph.route_graph import RouteStageCandidate
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE


class _Driver:
    async def generate_stage(self, *, stage, **kwargs):
        return RouteStageCandidate(artifact_ref=f"candidate:{stage.stage_id}")

    async def validate_stage(self, **kwargs):
        return None

    async def commit_stage(self, *, stage, **kwargs):
        return f"artifact:{stage.stage_id}"


_CHILD_SCRIPT = r'''
import asyncio
import os
import sys
from pathlib import Path

from novel_workflow.orchestration.phase32_graph_execution import Phase32GraphExecutionService
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.runtime.graph.phase32_checkpointer import open_phase32_checkpointer
from novel_workflow.providers.phase32_contract import Phase32ProviderRequest, Phase32ProviderResponse
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.output_contracts.phase32_route_artifacts import ScreenplayBriefArtifact
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE


class Gateway:
    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        payload = ScreenplayBriefArtifact(
            title="失序档案",
            sample_type="调查悬疑样片",
            target_minutes=12,
            premise="公共档案的签名链正在被有意抹除。",
            audience_promise="证据推动的调查样片。",
            visible_conflict="主角必须在闭馆前证明签名页被替换。",
            ending_effect="签名页在听证会上重新拼合。",
            tone="冷峻、克制",
        ).model_dump(mode="json")
        return Phase32ProviderResponse(payload=payload)


async def main() -> None:
    root = Path(sys.argv[1])
    fixture = create_phase32_run_fixture(
        root / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="subprocess-recovery-run",
        project_id="subprocess-recovery-project",
        creative_intent="验证真实子进程退出后的 checkpoint 恢复。",
    )
    driver = Phase32RouteDriver(Phase32ArtifactStore(root / "artifacts"), Gateway())
    async with open_phase32_checkpointer(root / "checkpoints") as checkpointer:
        result = await Phase32GraphExecutionService(fixture.repository).step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
        )
        assert result.interrupted
        assert result.decision
        os._exit(0)


asyncio.run(main())
'''


@pytest.mark.asyncio
async def test_phase32_recovers_checkpoint_after_abrupt_child_process_exit(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(repository_root / "src"), environment.get("PYTHONPATH", "")])
    )
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_SCRIPT, str(tmp_path)],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr

    repository = Phase32RunRepository(tmp_path / "runtime")
    record = repository.read("subprocess-recovery-run")
    assert record.state.status == "awaiting_decision"
    assert record.read_model.pending_decisions
    assert record.read_model.checkpoint_id
    history = repository.events(record.definition.run_id)
    first_event_cursor = history[-1].sequence
    decision_event = next(event for event in history if event.type == "decision.required")

    async with open_phase32_checkpointer(tmp_path / "checkpoints") as checkpointer:
        resumed = await Phase32GraphExecutionService(repository).step(
            record.definition.run_id,
            driver=_Driver(),
            checkpointer=checkpointer,
            resume={
                "decision_id": record.read_model.pending_decisions[0].decision_id,
                "action": "accept",
                "domain_revision": int((decision_event.payload or {}).get("domain_revision", -1)),
            },
        )
    assert resumed.interrupted is True
    assert resumed.decision is not None
    assert resumed.decision["stage_id"] != "brief"

    page = Phase32EventProjection(repository).page(
        record.definition.run_id,
        after=first_event_cursor,
    )
    assert page.events
    assert page.events[0].sequence == first_event_cursor + 1
    assert any(event.type in {"stage.started", "decision.resolved"} for event in page.events)
