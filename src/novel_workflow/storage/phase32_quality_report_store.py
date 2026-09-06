"""Append-only persistence for immutable Phase 32 text quality reports."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from novel_workflow.quality.phase32_quality_report import Phase32TextQualityReport
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class Phase32QualityReportStoreError(ValueError):
    code = "phase32_quality_report_store_invalid"


class Phase32QualityReportStore:
    """Persist a contiguous supersession chain without mutating old reports."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def append(self, report: Phase32TextQualityReport) -> Phase32TextQualityReport:
        with self._lock:
            try:
                existing = self.read(report.run_id, report.report_ref)
            except FileNotFoundError:
                existing = None
            if existing is not None:
                if existing != report:
                    raise Phase32QualityReportStoreError(
                        "Quality report identity is immutable"
                    )
                return existing
            reports = self.list(report.run_id)
            expected_sequence = len(reports) + 1
            if report.sequence != expected_sequence:
                raise Phase32QualityReportStoreError(
                    f"Quality report sequence must be {expected_sequence}"
                )
            expected_parent = reports[-1].report_ref if reports else None
            if report.supersedes_report_ref != expected_parent:
                raise Phase32QualityReportStoreError(
                    "Quality report must supersede the current append-only head"
                )
            path = self._path(report.run_id, report.sequence, report.report_ref)
            atomic_write_json(path, report.model_dump(mode="json"))
            return report

    def read(self, run_id: str, report_ref: str) -> Phase32TextQualityReport:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_ref = require_safe_id(report_ref, label="report_ref")
        matches = list((self.root / safe_run_id).glob(f"*-{safe_ref}.json"))
        if not matches:
            raise FileNotFoundError(report_ref)
        if len(matches) != 1:
            raise Phase32QualityReportStoreError("Quality report ref is duplicated")
        report = self._read_path(matches[0])
        if report.run_id != safe_run_id or report.report_ref != safe_ref:
            raise Phase32QualityReportStoreError("Quality report storage identity differs")
        return report

    def list(self, run_id: str) -> list[Phase32TextQualityReport]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return []
        reports = sorted(
            (self._read_path(path) for path in directory.glob("*.json")),
            key=lambda item: item.sequence,
        )
        previous_ref: str | None = None
        for expected_sequence, report in enumerate(reports, start=1):
            if report.run_id != safe_run_id:
                raise Phase32QualityReportStoreError(
                    "Quality report belongs to another Run"
                )
            if report.sequence != expected_sequence:
                raise Phase32QualityReportStoreError(
                    "Quality report sequence is not contiguous"
                )
            if report.supersedes_report_ref != previous_ref:
                raise Phase32QualityReportStoreError(
                    "Quality report supersession chain is broken"
                )
            previous_ref = report.report_ref
        return reports

    def latest(self, run_id: str) -> Phase32TextQualityReport | None:
        reports = self.list(run_id)
        return reports[-1] if reports else None

    def _path(self, run_id: str, sequence: int, report_ref: str) -> Path:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_ref = require_safe_id(report_ref, label="report_ref")
        return self.root / safe_run_id / f"{sequence:06d}-{safe_ref}.json"

    @staticmethod
    def _read_path(path: Path) -> Phase32TextQualityReport:
        try:
            return Phase32TextQualityReport.model_validate(read_json(path))
        except Exception as exc:
            raise Phase32QualityReportStoreError(
                f"Malformed Phase 32 quality report: {path.name}"
            ) from exc


__all__ = ["Phase32QualityReportStore", "Phase32QualityReportStoreError"]
