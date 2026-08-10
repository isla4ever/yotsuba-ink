from __future__ import annotations

import json

import pytest

from novel_workflow.archive import ArchivedRunReadOnlyError, LegacyRunViewer


def test_legacy_runs_are_read_only_and_not_executable(tmp_path) -> None:
    run_dir = tmp_path / "legacy-runs" / "run-old"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": "run-old", "state": {"runtime_phase": "failed"}}),
        encoding="utf-8",
    )
    viewer = LegacyRunViewer(tmp_path / "legacy-runs")

    archived = viewer.read("run-old")
    assert archived["archive"]["status"] == "archived_read_only"
    assert archived["capabilities"] == {
        "execute": False,
        "resume": False,
        "decide": False,
        "branch": False,
        "stream": False,
        "writeback": False,
        "provider": False,
    }
    with pytest.raises(ArchivedRunReadOnlyError) as exc:
        viewer.reject_mutation("run-old")
    assert exc.value.code == "archived_run_read_only"
