from __future__ import annotations

"""Immutable, unit-addressable persistence for hierarchical planning aggregates."""

import hashlib
import json
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


PlanningStageId = Literal["spine", "volumes", "detail"]


class PlanningAggregateManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    stage_id: PlanningStageId
    version_id: str
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: str = Field(min_length=1, max_length=240)
    created_at: str
    unit_files: dict[str, list[str]]
    unit_counts: dict[str, int]


class PlanningAggregateCandidateManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    stage_id: PlanningStageId
    candidate_id: str
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: str = Field(min_length=1, max_length=240)
    created_at: str
    unit_files: dict[str, list[str]]
    unit_counts: dict[str, int]


class PlanningAggregateAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    stage_id: PlanningStageId
    candidate_id: str
    version_id: str
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_at: str


class PlanningAggregateStore:
    """Store one compact root plus separate bounded unit files per version.

    A version is assembled in a temporary directory and published by one
    directory rename.  The latest pointer is updated only after the complete
    version exists, so a partial unit set can never become readable authority.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def commit(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        root: BaseModel,
        units: Mapping[str, Sequence[BaseModel]],
        *,
        source: str,
    ) -> PlanningAggregateManifest:
        require_safe_id(run_id, label="run identifier")
        require_safe_id(source, label="planning source")
        root_payload, unit_payloads, unit_files, signature = _aggregate_payload(
            stage_id,
            root,
            units,
            source=source,
        )
        version_id = f"{stage_id}-v-{signature[:20]}"
        manifest = PlanningAggregateManifest(
            run_id=run_id,
            stage_id=stage_id,
            version_id=version_id,
            signature=signature,
            source=source,
            created_at=_now(),
            unit_files=unit_files,
            unit_counts={name: len(values) for name, values in unit_payloads.items()},
        )

        final_dir = self._version_dir(run_id, stage_id, version_id)
        with self._lock:
            if final_dir.exists():
                existing = self._read_manifest(final_dir)
                if existing.signature != signature or existing.source != source:
                    raise ValueError("Planning aggregate version identity collision")
                atomic_write_json(
                    self._latest_path(run_id),
                    self._latest_payload(run_id, stage_id, version_id),
                )
                return existing
            stage_dir = final_dir.parent
            stage_dir.mkdir(parents=True, exist_ok=True)
            temp_dir = Path(
                tempfile.mkdtemp(
                    prefix=f".{version_id}.",
                    suffix=".tmp",
                    dir=stage_dir,
                )
            )
            try:
                atomic_write_json(temp_dir / "manifest.json", manifest.model_dump(mode="json"))
                atomic_write_json(temp_dir / "root.json", root_payload)
                for collection, payloads in unit_payloads.items():
                    for filename, payload in zip(unit_files[collection], payloads, strict=True):
                        atomic_write_json(temp_dir / "units" / filename, payload)
                final_dir.parent.mkdir(parents=True, exist_ok=True)
                temp_dir.replace(final_dir)
                atomic_write_json(
                    self._latest_path(run_id),
                    self._latest_payload(run_id, stage_id, version_id),
                )
            except Exception:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise
        return manifest

    def save_candidate(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        root: BaseModel,
        units: Mapping[str, Sequence[BaseModel]],
        *,
        source: str,
    ) -> PlanningAggregateCandidateManifest:
        """Persist a complete candidate without changing committed authority."""

        require_safe_id(run_id, label="run identifier")
        require_safe_id(source, label="planning source")
        root_payload, unit_payloads, unit_files, signature = _aggregate_payload(
            stage_id,
            root,
            units,
            source=source,
        )
        candidate_id = f"{stage_id}-candidate-{signature[:20]}"
        manifest = PlanningAggregateCandidateManifest(
            run_id=run_id,
            stage_id=stage_id,
            candidate_id=candidate_id,
            signature=signature,
            source=source,
            created_at=_now(),
            unit_files=unit_files,
            unit_counts={name: len(values) for name, values in unit_payloads.items()},
        )
        final_dir = self._candidate_dir(run_id, stage_id, candidate_id)
        with self._lock:
            if final_dir.exists():
                existing = self._read_candidate_manifest(final_dir)
                expected = manifest.model_copy(update={"created_at": existing.created_at})
                if existing != expected:
                    raise ValueError("Planning candidate identity collision")
                return existing
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            temp_dir = Path(
                tempfile.mkdtemp(
                    prefix=f".{candidate_id}.",
                    suffix=".tmp",
                    dir=final_dir.parent,
                )
            )
            try:
                atomic_write_json(temp_dir / "manifest.json", manifest.model_dump(mode="json"))
                atomic_write_json(temp_dir / "root.json", root_payload)
                for collection, payloads in unit_payloads.items():
                    for filename, payload in zip(unit_files[collection], payloads, strict=True):
                        atomic_write_json(temp_dir / "units" / filename, payload)
                temp_dir.replace(final_dir)
            except Exception:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise
        return manifest

    def candidate_manifest(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        candidate_id: str,
    ) -> PlanningAggregateCandidateManifest:
        manifest = self._read_candidate_manifest(
            self._candidate_dir(run_id, stage_id, candidate_id)
        )
        if (
            manifest.run_id != run_id
            or manifest.stage_id != stage_id
            or manifest.candidate_id != candidate_id
        ):
            raise ValueError("Planning candidate manifest identity mismatch")
        return manifest

    def candidate_exists(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        candidate_id: str,
    ) -> bool:
        return self._candidate_dir(run_id, stage_id, candidate_id).is_dir()

    def read_candidate(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        candidate_id: str,
    ) -> dict[str, Any]:
        manifest = self.candidate_manifest(run_id, stage_id, candidate_id)
        candidate_dir = self._candidate_dir(run_id, stage_id, candidate_id)
        units = {
            collection: [read_json(candidate_dir / "units" / filename) for filename in filenames]
            for collection, filenames in manifest.unit_files.items()
        }
        return {
            "manifest": manifest.model_dump(mode="json"),
            "root": read_json(candidate_dir / "root.json"),
            "units": units,
        }

    def list_candidates(
        self,
        run_id: str,
        stage_id: PlanningStageId,
    ) -> list[PlanningAggregateCandidateManifest]:
        directory = self.root / run_id / "candidates" / stage_id
        if not directory.exists():
            return []
        return sorted(
            (
                self._read_candidate_manifest(path)
                for path in directory.iterdir()
                if path.is_dir() and not path.name.startswith(".")
            ),
            key=lambda item: (item.created_at, item.candidate_id),
        )

    def record_acceptance(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        candidate_id: str,
        version_id: str,
    ) -> PlanningAggregateAcceptance:
        candidate = self.candidate_manifest(run_id, stage_id, candidate_id)
        committed = self.manifest(run_id, stage_id, version_id)
        if candidate.signature != committed.signature:
            raise ValueError("Accepted planning version must preserve the candidate signature")
        acceptance = PlanningAggregateAcceptance(
            run_id=run_id,
            stage_id=stage_id,
            candidate_id=candidate_id,
            version_id=version_id,
            signature=committed.signature,
            accepted_at=_now(),
        )
        path = self._acceptance_path(run_id, stage_id, candidate_id)
        with self._lock:
            if path.exists():
                existing = PlanningAggregateAcceptance.model_validate(read_json(path))
                expected = acceptance.model_copy(update={"accepted_at": existing.accepted_at})
                if existing != expected:
                    raise ValueError("Planning candidate acceptance is immutable")
                return existing
            atomic_write_json(path, acceptance.model_dump(mode="json"))
        return acceptance

    def candidate_acceptance(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        candidate_id: str,
    ) -> PlanningAggregateAcceptance:
        value = PlanningAggregateAcceptance.model_validate(
            read_json(self._acceptance_path(run_id, stage_id, candidate_id))
        )
        if (
            value.run_id != run_id
            or value.stage_id != stage_id
            or value.candidate_id != candidate_id
        ):
            raise ValueError("Planning candidate acceptance identity mismatch")
        return value

    def read(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        version = version_id or self.latest_version(run_id, stage_id)
        manifest = self.manifest(run_id, stage_id, version)
        units: dict[str, list[dict[str, Any]]] = {}
        for collection, filenames in manifest.unit_files.items():
            units[collection] = [
                self._read_unit_file(run_id, stage_id, version, collection, filename)
                for filename in filenames
            ]
        return {
            "manifest": manifest.model_dump(mode="json"),
            "root": self.read_root(run_id, stage_id, version),
            "units": units,
        }

    def manifest(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        version_id: str,
    ) -> PlanningAggregateManifest:
        """Read one explicit committed version; Context must never use latest implicitly."""

        manifest = self._read_manifest(self._version_dir(run_id, stage_id, version_id))
        if (
            manifest.run_id != run_id
            or manifest.stage_id != stage_id
            or manifest.version_id != version_id
        ):
            raise ValueError("Planning aggregate manifest identity mismatch")
        return manifest

    def read_root(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        version_id: str,
    ) -> dict[str, Any]:
        self.manifest(run_id, stage_id, version_id)
        return read_json(self._version_dir(run_id, stage_id, version_id) / "root.json")

    def read_unit(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        version_id: str,
        collection: str,
        unit_id: str,
    ) -> dict[str, Any]:
        """Read one manifest-owned unit without loading the complete aggregate."""

        require_safe_id(collection, label="planning unit collection")
        require_safe_id(unit_id, label="planning unit id")
        manifest = self.manifest(run_id, stage_id, version_id)
        filename = f"{collection}--{unit_id}.json"
        if filename not in manifest.unit_files.get(collection, []):
            raise KeyError(
                f"Planning aggregate {stage_id}:{version_id} does not own "
                f"{collection}:{unit_id}"
            )
        return self._read_unit_file(
            run_id,
            stage_id,
            version_id,
            collection,
            filename,
        )

    def read_units(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        version_id: str,
        collection: str,
        unit_ids: Sequence[str],
    ) -> list[dict[str, Any]]:
        return [
            self.read_unit(run_id, stage_id, version_id, collection, unit_id)
            for unit_id in unit_ids
        ]

    def latest_version(self, run_id: str, stage_id: PlanningStageId) -> str:
        latest = read_json(self._latest_path(run_id))
        version_id = str((latest.get(stage_id) or ""))
        if not version_id:
            raise FileNotFoundError(f"{run_id}:{stage_id}:latest")
        require_safe_id(version_id, label="planning version")
        return version_id

    def list_versions(
        self,
        run_id: str,
        stage_id: PlanningStageId,
    ) -> list[PlanningAggregateManifest]:
        directory = self.root / run_id / stage_id
        if not directory.exists():
            return []
        return sorted(
            (
                self._read_manifest(path)
                for path in directory.iterdir()
                if path.is_dir() and not path.name.startswith(".")
            ),
            key=lambda item: item.created_at,
        )

    def _latest_path(self, run_id: str) -> Path:
        return self.root / run_id / "planning-index.json"

    def _latest_payload(self, run_id: str, stage_id: PlanningStageId, version_id: str) -> dict[str, Any]:
        path = self._latest_path(run_id)
        value = read_json(path) if path.exists() else {}
        value[stage_id] = version_id
        return value

    def _version_dir(self, run_id: str, stage_id: PlanningStageId, version_id: str) -> Path:
        require_safe_id(run_id, label="run identifier")
        require_safe_id(version_id, label="planning version")
        return self.root / run_id / stage_id / version_id

    def _candidate_dir(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        candidate_id: str,
    ) -> Path:
        require_safe_id(run_id, label="run identifier")
        require_safe_id(candidate_id, label="planning candidate")
        return self.root / run_id / "candidates" / stage_id / candidate_id

    def _acceptance_path(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        candidate_id: str,
    ) -> Path:
        require_safe_id(run_id, label="run identifier")
        require_safe_id(candidate_id, label="planning candidate")
        return self.root / run_id / "candidate_acceptances" / stage_id / f"{candidate_id}.json"

    def _read_manifest(self, version_dir: Path) -> PlanningAggregateManifest:
        return PlanningAggregateManifest.model_validate_json(
            (version_dir / "manifest.json").read_text(encoding="utf-8")
        )

    def _read_candidate_manifest(
        self,
        candidate_dir: Path,
    ) -> PlanningAggregateCandidateManifest:
        return PlanningAggregateCandidateManifest.model_validate_json(
            (candidate_dir / "manifest.json").read_text(encoding="utf-8")
        )

    def _read_unit_file(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        version_id: str,
        collection: str,
        filename: str,
    ) -> dict[str, Any]:
        expected_prefix = f"{collection}--"
        if not filename.startswith(expected_prefix) or not filename.endswith(".json"):
            raise ValueError("Planning manifest contains an invalid unit filename")
        return read_json(
            self._version_dir(run_id, stage_id, version_id) / "units" / filename
        )


def _unit_id(payload: dict[str, Any], collection: str) -> str:
    value = str(payload.get("id") or payload.get("ref") or "")
    if not value:
        raise ValueError(f"Planning {collection} unit is missing a stable id")
    require_safe_id(value, label=f"{collection} unit id")
    return value


def _aggregate_payload(
    stage_id: PlanningStageId,
    root: BaseModel,
    units: Mapping[str, Sequence[BaseModel]],
    *,
    source: str,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, list[str]], str]:
    if not units or any(not name or not values for name, values in units.items()):
        raise ValueError("Planning aggregate must contain named non-empty unit collections")
    root_payload = root.model_dump(mode="json")
    unit_payloads: dict[str, list[dict[str, Any]]] = {}
    unit_files: dict[str, list[str]] = {}
    for collection, models in units.items():
        require_safe_id(collection, label="planning unit collection")
        payloads = [model.model_dump(mode="json") for model in models]
        ids = [_unit_id(payload, collection) for payload in payloads]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Planning {collection} units must have unique ids")
        unit_payloads[collection] = payloads
        unit_files[collection] = [f"{collection}--{unit_id}.json" for unit_id in ids]
    signature = _digest(
        {
            "stage_id": stage_id,
            "root": root_payload,
            "units": unit_payloads,
            "source": source,
        }
    )
    return root_payload, unit_payloads, unit_files, signature


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "PlanningAggregateAcceptance",
    "PlanningAggregateCandidateManifest",
    "PlanningAggregateManifest",
    "PlanningAggregateStore",
    "PlanningStageId",
]
