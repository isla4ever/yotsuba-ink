"""Immutable persistence for redacted Phase 32 release evidence bundles."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from novel_workflow.output_contracts.phase32_release_evidence import (
    Phase32ContinuityEvidenceBundle,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class Phase32ReleaseEvidenceStoreError(ValueError):
    code = "phase32_release_evidence_store_invalid"


class Phase32ReleaseEvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def write(
        self,
        bundle: Phase32ContinuityEvidenceBundle,
    ) -> Phase32ContinuityEvidenceBundle:
        safe_run_id = require_safe_id(bundle.run_id, label="run_id")
        path = self._path(safe_run_id, bundle.bundle_ref)
        with self._lock:
            if path.exists():
                existing = self._read_path(path)
                if existing.model_dump(mode="json") != bundle.model_dump(mode="json"):
                    raise Phase32ReleaseEvidenceStoreError(
                        "Release evidence bundle identity is immutable"
                    )
                return existing
            atomic_write_json(path, bundle.model_dump(mode="json"))
        return bundle

    def read(
        self,
        run_id: str,
        bundle_ref: str,
    ) -> Phase32ContinuityEvidenceBundle:
        safe_run_id = require_safe_id(run_id, label="run_id")
        bundle = self._read_path(self._path(safe_run_id, bundle_ref))
        if bundle.run_id != safe_run_id or bundle.bundle_ref != bundle_ref:
            raise Phase32ReleaseEvidenceStoreError(
                "Release evidence bundle storage identity differs"
            )
        return bundle

    def list(self, run_id: str) -> tuple[Phase32ContinuityEvidenceBundle, ...]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return ()
        return tuple(
            sorted(
                (self._read_path(path) for path in directory.glob("*.json")),
                key=lambda item: (item.generated_at, item.bundle_ref),
            )
        )

    def latest(self, run_id: str) -> Phase32ContinuityEvidenceBundle | None:
        bundles = self.list(run_id)
        return bundles[-1] if bundles else None

    def _path(self, run_id: str, bundle_ref: str) -> Path:
        safe_ref = require_safe_id(bundle_ref, label="bundle_ref")
        if not safe_ref.startswith("p32-continuity-evidence-"):
            raise ValueError("Invalid continuity evidence bundle reference")
        return self.root / run_id / f"{safe_ref}.json"

    @staticmethod
    def _read_path(path: Path) -> Phase32ContinuityEvidenceBundle:
        try:
            return Phase32ContinuityEvidenceBundle.model_validate(read_json(path))
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ReleaseEvidenceStoreError(
                f"Malformed Phase 32 release evidence bundle: {path.name}"
            ) from exc


__all__ = ["Phase32ReleaseEvidenceStore", "Phase32ReleaseEvidenceStoreError"]
