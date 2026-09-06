"""Persistence contract for Phase 32 route Runs.

This repository is intentionally dormant until the graph, preflight, branch,
history and API cutover can switch together. It never parses or executes a
Phase 27 definition.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:  # pragma: no cover - production and process-recovery tests are POSIX.
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX keeps the in-process guard.
    fcntl = None  # type: ignore[assignment]

from novel_workflow.runtime.graph.route_run_state import (
    RouteRunStateSnapshot,
    SequentialStageProgress,
    initial_route_run_state,
    restore_route_run_state,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.storage.route_run_event import (
    RouteRunEventEnvelope,
    restore_route_run_event,
)
from novel_workflow.storage.route_run_read_model import (
    RouteRunReadModel,
    initial_route_run_read_model,
    restore_route_run_read_model,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


PHASE32_ARCHITECTURE_VERSION = "phase32-routes-v1"


class Phase32PersistenceError(ValueError):
    code = "phase32_persistence_invalid"


class Phase32ArchitectureError(Phase32PersistenceError):
    code = "phase32_architecture_rejected"


class Phase27ExecutionRejected(Phase32ArchitectureError):
    code = "phase27_run_requires_archive_reader"


@dataclass(frozen=True, slots=True)
class Phase32RunRecord:
    definition: GraphRunDefinition
    state: RouteRunStateSnapshot
    read_model: RouteRunReadModel


class Phase32RunRepository:
    """Durable Phase 32 definition, checkpoint projection and event stream."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs_root = root / "runs"
        self.events_root = root / "events"
        self.lock_root = root / ".run-locks"
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.events_root.mkdir(parents=True, exist_ok=True)
        self.lock_root.mkdir(parents=True, exist_ok=True)
        self._locks_guard = threading.RLock()
        self._run_locks: dict[str, threading.RLock] = {}
        self._thread_state = threading.local()

    def create(
        self,
        definition: GraphRunDefinition,
        *,
        state: RouteRunStateSnapshot | None = None,
        read_model: RouteRunReadModel | None = None,
        updated_at: str | None = None,
    ) -> Phase32RunRecord:
        state = state or initial_route_run_state(definition)
        read_model = read_model or initial_route_run_read_model(
            definition,
            updated_at=updated_at or _now(),
        )
        self._validate_record(definition, state, read_model)
        self._validate_projection_pair(state, read_model)
        run_id = require_safe_id(definition.run_id, label="run_id")
        target = self._run_dir(run_id)
        with self._run_guard(run_id):
            if target.exists():
                raise FileExistsError(run_id)
            staging = self.runs_root / f".{run_id}.staging"
            if staging.exists() or staging.is_symlink():
                recovered = _recover_create_staging(
                    staging,
                    definition=definition,
                )
                if recovered is not None:
                    self._validate_record(
                        recovered.definition,
                        recovered.state,
                        recovered.read_model,
                    )
                    self._validate_projection_pair(
                        recovered.state,
                        recovered.read_model,
                    )
                    staging.replace(target)
                    return recovered
            staging.mkdir(parents=True)
            try:
                atomic_write_json(
                    staging / "definition.json",
                    definition.model_dump(mode="json"),
                )
                atomic_write_json(
                    staging / "state.json",
                    state.model_dump(mode="json"),
                )
                atomic_write_json(
                    staging / "read_model.json",
                    read_model.model_dump(mode="json"),
                )
                staging.replace(target)
            except Exception:
                if staging.exists() or staging.is_symlink():
                    _clear_internal_staging(
                        staging,
                        allowed_names={
                            "definition.json",
                            "state.json",
                            "read_model.json",
                        },
                        label="creation",
                    )
                raise
        return Phase32RunRecord(definition, state, read_model)

    def read(self, run_id: str) -> Phase32RunRecord:
        safe_run_id = require_safe_id(run_id, label="run_id")
        with self._run_guard(safe_run_id):
            self._recover_projection(safe_run_id)
            definition = self.definition(safe_run_id)
            state = self.state(safe_run_id, definition=definition)
            read_model = self.read_model(safe_run_id, definition=definition)
            self._validate_record(definition, state, read_model)
            self._validate_projection_pair(state, read_model)
            return Phase32RunRecord(definition, state, read_model)

    def definition(self, run_id: str) -> GraphRunDefinition:
        run_id = require_safe_id(run_id, label="run_id")
        with self._run_guard(run_id):
            payload = self._read_object(self._run_dir(run_id) / "definition.json")
            self._require_phase32_architecture(payload, run_id)
            try:
                definition = GraphRunDefinition.model_validate(payload)
            except Exception as exc:
                raise Phase32PersistenceError(
                    f"Malformed Phase 32 Run definition: {run_id}"
                ) from exc
            if definition.run_id != run_id:
                raise Phase32PersistenceError("Run folder and definition identity differ")
            return definition

    def state(
        self,
        run_id: str,
        *,
        definition: GraphRunDefinition | None = None,
    ) -> RouteRunStateSnapshot:
        safe_run_id = require_safe_id(run_id, label="run_id")
        with self._run_guard(safe_run_id):
            self._recover_projection(safe_run_id)
            definition = definition or self.definition(safe_run_id)
            payload = self._read_object(self._run_dir(safe_run_id) / "state.json")
            try:
                return restore_route_run_state(definition, payload)
            except Exception as exc:
                raise Phase32PersistenceError(
                    f"Malformed Phase 32 Run state: {safe_run_id}"
                ) from exc

    def read_model(
        self,
        run_id: str,
        *,
        definition: GraphRunDefinition | None = None,
    ) -> RouteRunReadModel:
        safe_run_id = require_safe_id(run_id, label="run_id")
        with self._run_guard(safe_run_id):
            self._recover_projection(safe_run_id)
            definition = definition or self.definition(safe_run_id)
            payload = self._read_object(
                self._run_dir(safe_run_id) / "read_model.json"
            )
            try:
                return restore_route_run_read_model(definition, payload)
            except Exception as exc:
                raise Phase32PersistenceError(
                    f"Malformed Phase 32 Run read model: {safe_run_id}"
                ) from exc

    def commit_projection(
        self,
        run_id: str,
        *,
        state: RouteRunStateSnapshot,
        read_model: RouteRunReadModel,
    ) -> Phase32RunRecord:
        return self._commit_projection(
            run_id,
            state=state,
            read_model=read_model,
            event=None,
        )

    def commit_projection_with_event(
        self,
        run_id: str,
        *,
        state: RouteRunStateSnapshot,
        read_model: RouteRunReadModel,
        event: RouteRunEventEnvelope,
    ) -> Phase32RunRecord:
        """Commit a projection and one event through the same recovery journal."""

        return self._commit_projection(
            run_id,
            state=state,
            read_model=read_model,
            event=event,
        )

    def _commit_projection(
        self,
        run_id: str,
        *,
        state: RouteRunStateSnapshot,
        read_model: RouteRunReadModel,
        event: RouteRunEventEnvelope | None,
    ) -> Phase32RunRecord:
        safe_run_id = require_safe_id(run_id, label="run_id")
        with self._run_guard(safe_run_id):
            current = self.read(safe_run_id)
            definition = current.definition
            self._validate_record(definition, state, read_model)
            self._validate_projection_pair(state, read_model)
            self._validate_sequential_progress_transition(
                current.state.sequential_stage_progress,
                state.sequential_stage_progress,
            )
            self._validate_sequential_progress_transition(
                current.read_model.sequential_stage_progress,
                read_model.sequential_stage_progress,
            )
            if event is not None:
                try:
                    event = event.validate_for_definition(definition)
                except Exception as exc:
                    raise Phase32PersistenceError(
                        f"Phase 32 event does not match its Run: {run_id}"
                    ) from exc
                expected_sequence = len(self.events(safe_run_id)) + 1
                if event.sequence != expected_sequence:
                    raise Phase32PersistenceError(
                        f"Event sequence must be {expected_sequence}, got {event.sequence}"
                    )
            staging = self.runs_root / f".{safe_run_id}.projection.staging"
            if staging.exists() or staging.is_symlink():
                _clear_internal_staging(
                    staging,
                    allowed_names={"state.json", "read_model.json"},
                    label="projection",
                )
            staging.mkdir(parents=True)
            try:
                atomic_write_json(
                    staging / "state.json",
                    state.model_dump(mode="json"),
                )
                atomic_write_json(
                    staging / "read_model.json",
                    read_model.model_dump(mode="json"),
                )
                journal_payload = {
                    "architecture_version": PHASE32_ARCHITECTURE_VERSION,
                    "run_id": run_id,
                    "definition_digest": definition.definition_digest,
                    "state": state.model_dump(mode="json"),
                    "read_model": read_model.model_dump(mode="json"),
                }
                if event is not None:
                    journal_payload["event"] = event.model_dump(mode="json")
                atomic_write_json(
                    self._projection_journal_path(safe_run_id),
                    journal_payload,
                )
                self._replace_projection_file(
                    staging / "state.json",
                    self._run_dir(safe_run_id) / "state.json",
                )
                self._replace_projection_file(
                    staging / "read_model.json",
                    self._run_dir(safe_run_id) / "read_model.json",
                )
                if event is not None:
                    self._append_event_unlocked(event)
                self._projection_journal_path(safe_run_id).unlink(missing_ok=True)
                staging.rmdir()
            except Exception:
                if staging.exists() or staging.is_symlink():
                    _clear_internal_staging(
                        staging,
                        allowed_names={"state.json", "read_model.json"},
                        label="projection",
                    )
                raise
        return self.read(safe_run_id)

    def append_event(self, event: RouteRunEventEnvelope) -> RouteRunEventEnvelope:
        safe_run_id = require_safe_id(event.run_id, label="run_id")
        with self._run_guard(safe_run_id):
            definition = self.definition(safe_run_id)
            try:
                event = event.validate_for_definition(definition)
            except Exception as exc:
                raise Phase32PersistenceError(
                    f"Phase 32 event does not match its Run: {safe_run_id}"
                ) from exc
            return self._append_event_unlocked(event)

    def _append_event_unlocked(self, event: RouteRunEventEnvelope) -> RouteRunEventEnvelope:
        path = self._event_path(event.run_id)
        events = self.events(event.run_id)
        existing = next((item for item in events if item.event_id == event.event_id), None)
        if existing is not None:
            if existing != event:
                raise Phase32PersistenceError(
                    f"Event idempotency conflict: {event.event_id}"
                )
            return existing
        expected_sequence = len(events) + 1
        if event.sequence != expected_sequence:
            raise Phase32PersistenceError(
                f"Event sequence must be {expected_sequence}, got {event.sequence}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def events(self, run_id: str, *, after: int = 0) -> list[RouteRunEventEnvelope]:
        if after < 0:
            raise ValueError("Event cursor cannot be negative")
        safe_run_id = require_safe_id(run_id, label="run_id")
        with self._run_guard(safe_run_id):
            definition = self.definition(safe_run_id)
            path = self._event_path(safe_run_id)
            if not path.exists():
                return []
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                raise Phase32PersistenceError(
                    f"Cannot read Phase 32 events: {safe_run_id}"
                ) from exc
            restored: list[RouteRunEventEnvelope] = []
            seen: set[str] = set()
            for line_number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    event = restore_route_run_event(definition, payload)
                except Exception as exc:
                    raise Phase32PersistenceError(
                        f"Malformed Phase 32 event at line {line_number}: {safe_run_id}"
                    ) from exc
                if event.sequence != len(restored) + 1:
                    raise Phase32PersistenceError(
                        f"Phase 32 event sequence is not contiguous: {safe_run_id}"
                    )
                if event.event_id in seen:
                    raise Phase32PersistenceError(
                        f"Phase 32 event id is duplicated: {safe_run_id}"
                    )
                seen.add(event.event_id)
                restored.append(event)
            return [event for event in restored if event.sequence > after]

    def list_read_models(self) -> list[RouteRunReadModel]:
        records: list[RouteRunReadModel] = []
        for path in sorted(self.runs_root.glob("*/read_model.json")):
            if path.parent.name.startswith("."):
                continue
            records.append(self.read(path.parent.name).read_model)
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def exists(self, run_id: str) -> bool:
        run_id = require_safe_id(run_id, label="run_id")
        with self._run_guard(run_id):
            return (self._run_dir(run_id) / "definition.json").exists()

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_root / require_safe_id(run_id, label="run_id")

    def _event_path(self, run_id: str) -> Path:
        return self.events_root / require_safe_id(run_id, label="run_id") / "events.jsonl"

    def _projection_journal_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "projection.journal.json"

    @staticmethod
    def _replace_projection_file(source: Path, target: Path) -> None:
        source.replace(target)

    def _recover_projection(self, run_id: str) -> None:
        safe_run_id = require_safe_id(run_id, label="run_id")
        with self._run_guard(safe_run_id):
            journal = self._projection_journal_path(safe_run_id)
            if not journal.exists():
                staging = self.runs_root / f".{safe_run_id}.projection.staging"
                if staging.exists() or staging.is_symlink():
                    _clear_internal_staging(
                        staging,
                        allowed_names={"state.json", "read_model.json"},
                        label="projection",
                    )
                return
            definition = self.definition(safe_run_id)
            payload = self._read_object(journal)
            if payload.get("architecture_version") != PHASE32_ARCHITECTURE_VERSION:
                raise Phase32ArchitectureError(
                    f"Unsupported Phase 32 projection journal: {safe_run_id}"
                )
            if payload.get("run_id") != safe_run_id:
                raise Phase32PersistenceError(
                    "Projection journal and Run identity differ"
                )
            if payload.get("definition_digest") != definition.definition_digest:
                raise Phase32PersistenceError(
                    "Projection journal definition digest does not match its Run"
                )
            state_payload = payload.get("state")
            read_model_payload = payload.get("read_model")
            event_payload = payload.get("event")
            if not isinstance(state_payload, dict) or not isinstance(
                read_model_payload, dict
            ):
                raise Phase32PersistenceError(
                    "Projection journal must contain state and read_model objects"
                )
            try:
                state = restore_route_run_state(definition, state_payload)
                read_model = restore_route_run_read_model(
                    definition,
                    read_model_payload,
                )
                self._validate_record(definition, state, read_model)
                self._validate_projection_pair(state, read_model)
                current_state = restore_route_run_state(
                    definition,
                    self._read_object(self._run_dir(safe_run_id) / "state.json"),
                )
                current_read_model = restore_route_run_read_model(
                    definition,
                    self._read_object(
                        self._run_dir(safe_run_id) / "read_model.json"
                    ),
                )
                self._validate_sequential_progress_transition(
                    current_state.sequential_stage_progress,
                    state.sequential_stage_progress,
                )
                self._validate_sequential_progress_transition(
                    current_read_model.sequential_stage_progress,
                    read_model.sequential_stage_progress,
                )
                event = None
                if event_payload is not None:
                    if not isinstance(event_payload, dict):
                        raise ValueError("Projection journal event must be an object")
                    event = restore_route_run_event(definition, event_payload)
            except Exception as exc:
                raise Phase32PersistenceError(
                    f"Projection journal does not match its Run: {safe_run_id}"
                ) from exc
            atomic_write_json(
                self._run_dir(safe_run_id) / "state.json",
                state.model_dump(mode="json"),
            )
            atomic_write_json(
                self._run_dir(safe_run_id) / "read_model.json",
                read_model.model_dump(mode="json"),
            )
            if event is not None:
                self._append_event_unlocked(event)
            journal.unlink(missing_ok=True)
            staging = self.runs_root / f".{safe_run_id}.projection.staging"
            if staging.exists() or staging.is_symlink():
                _clear_internal_staging(
                    staging,
                    allowed_names={"state.json", "read_model.json"},
                    label="projection",
                )

    def _thread_lock_for(self, safe_run_id: str) -> threading.RLock:
        with self._locks_guard:
            return self._run_locks.setdefault(safe_run_id, threading.RLock())

    @contextmanager
    def _run_guard(self, run_id: str) -> Iterator[None]:
        """Serialize one Run across threads, repository instances, and processes."""

        safe_run_id = require_safe_id(run_id, label="run_id")
        thread_lock = self._thread_lock_for(safe_run_id)
        with thread_lock:
            held_run_ids = getattr(self._thread_state, "held_run_ids", None)
            if held_run_ids is None:
                held_run_ids = set()
                self._thread_state.held_run_ids = held_run_ids
            if safe_run_id in held_run_ids:
                yield
                return

            handle = None
            held_run_ids.add(safe_run_id)
            try:
                if fcntl is not None:
                    lock_name = hashlib.sha256(safe_run_id.encode("utf-8")).hexdigest()
                    handle = (self.lock_root / f"{lock_name}.lock").open("a+b")
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                if handle is not None:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    finally:
                        handle.close()
                held_run_ids.remove(safe_run_id)

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        try:
            payload = read_json(path)
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise Phase32PersistenceError(f"Malformed JSON: {path.name}") from exc
        if not isinstance(payload, dict):
            raise Phase32PersistenceError(f"JSON root must be an object: {path.name}")
        return payload

    @staticmethod
    def _require_phase32_architecture(payload: dict[str, Any], run_id: str) -> None:
        architecture = payload.get("architecture_version")
        if architecture == "phase27-vnext":
            raise Phase27ExecutionRejected(
                f"Phase 27 Run is archive-only and cannot enter Phase 32 repository: {run_id}"
            )
        if architecture != PHASE32_ARCHITECTURE_VERSION:
            raise Phase32ArchitectureError(
                f"Unsupported Phase 32 Run architecture: {architecture!r}"
            )

    @staticmethod
    def _validate_record(
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        read_model: RouteRunReadModel,
    ) -> None:
        try:
            state.validate_for_definition(definition)
            read_model.validate_for_definition(definition)
        except Exception as exc:
            raise Phase32PersistenceError(
                "Phase 32 state/read model does not match its definition"
            ) from exc
        if state.status != read_model.status:
            raise Phase32PersistenceError("State and read model statuses differ")
        if state.active_stage_id != read_model.active_stage_id:
            raise Phase32PersistenceError("State and read model active stages differ")
        if state.active_amendment_id != read_model.active_amendment_id:
            raise Phase32PersistenceError("State and read model active amendments differ")
        if state.stale_stage_ids != read_model.stale_stage_ids:
            raise Phase32PersistenceError("State and read model stale stages differ")
        if state.historical_frozen_stage_ids != read_model.historical_frozen_stage_ids:
            raise Phase32PersistenceError(
                "State and read model historical frozen stages differ"
            )

    @staticmethod
    def _validate_projection_pair(
        state: RouteRunStateSnapshot,
        read_model: RouteRunReadModel,
    ) -> None:
        if state.active_unit_ref != read_model.active_unit_ref:
            raise Phase32PersistenceError("State and read model active units differ")
        projected_artifact_refs = {
            stage_id: projection.artifact_ref
            for stage_id, projection in read_model.artifact_refs.items()
        }
        if state.artifact_refs != projected_artifact_refs:
            raise Phase32PersistenceError("State and read model Artifact refs differ")
        projected_progress = {
            stage_id: SequentialStageProgress.model_validate(payload)
            for stage_id, payload in state.sequential_stage_progress.items()
        }
        if projected_progress != read_model.sequential_stage_progress:
            raise Phase32PersistenceError(
                "State and read model sequential stage progress differs"
            )

    @staticmethod
    def _validate_sequential_progress_transition(
        previous_payloads: dict[str, Any],
        next_payloads: dict[str, Any],
    ) -> None:
        previous = {
            stage_id: SequentialStageProgress.model_validate(payload)
            for stage_id, payload in previous_payloads.items()
        }
        next_progress = {
            stage_id: SequentialStageProgress.model_validate(payload)
            for stage_id, payload in next_payloads.items()
        }
        for stage_id, previous_stage in previous.items():
            next_stage = next_progress.get(stage_id)
            if next_stage is None:
                raise Phase32PersistenceError(
                    f"Sequential stage progress cannot be removed: {stage_id}"
                )
            if previous_stage.ordered_unit_refs != next_stage.ordered_unit_refs:
                raise Phase32PersistenceError(
                    f"Sequential stage ordered unit refs cannot change: {stage_id}"
                )
            previous_commits = tuple(previous_stage.committed_artifact_refs.items())
            next_commits = tuple(next_stage.committed_artifact_refs.items())
            if len(next_commits) < len(previous_commits):
                raise Phase32PersistenceError(
                    f"Sequential stage committed Artifact prefix cannot shrink: {stage_id}"
                )
            if next_commits[: len(previous_commits)] != previous_commits:
                raise Phase32PersistenceError(
                    f"Sequential stage committed Artifact prefix cannot change: {stage_id}"
                )


def _recover_create_staging(
    path: Path,
    *,
    definition: GraphRunDefinition,
) -> Phase32RunRecord | None:
    """Reuse a complete matching create, or clear only a known partial create."""

    allowed_names = {"definition.json", "state.json", "read_model.json"}
    direct, temporary = _internal_staging_children(
        path,
        allowed_names=allowed_names,
        label="creation",
    )
    if direct == allowed_names:
        try:
            staged_definition = GraphRunDefinition.model_validate(
                read_json(path / "definition.json")
            )
            staged_state = restore_route_run_state(
                staged_definition,
                read_json(path / "state.json"),
            )
            staged_read_model = restore_route_run_read_model(
                staged_definition,
                read_json(path / "read_model.json"),
            )
        except Exception as exc:
            raise Phase32PersistenceError(
                "Complete Phase 32 creation staging is unreadable"
            ) from exc
        if staged_definition != definition:
            raise Phase32PersistenceError(
                "Complete Phase 32 creation staging targets another frozen Run"
            )
        for child in temporary:
            child.unlink()
        return Phase32RunRecord(
            definition=staged_definition,
            state=staged_state,
            read_model=staged_read_model,
        )

    _clear_internal_staging(
        path,
        allowed_names=allowed_names,
        label="creation",
    )
    return None


def _clear_internal_staging(
    path: Path,
    *,
    allowed_names: set[str],
    label: str,
) -> None:
    _, children = _internal_staging_children(
        path,
        allowed_names=allowed_names,
        label=label,
        include_direct_in_children=True,
    )
    for child in children:
        child.unlink()
    path.rmdir()


def _internal_staging_children(
    path: Path,
    *,
    allowed_names: set[str],
    label: str,
    include_direct_in_children: bool = False,
) -> tuple[set[str], list[Path]]:
    if path.is_symlink() or not path.is_dir():
        raise Phase32PersistenceError(
            f"Phase 32 {label} staging is not an internal directory"
        )
    direct: set[str] = set()
    selected: list[Path] = []
    for child in path.iterdir():
        if child.is_symlink() or not child.is_file():
            raise Phase32PersistenceError(
                f"Phase 32 {label} staging contains an unknown entry"
            )
        if child.name in allowed_names:
            direct.add(child.name)
            if include_direct_in_children:
                selected.append(child)
            continue
        if _is_internal_atomic_temp(child.name, allowed_names):
            selected.append(child)
            continue
        raise Phase32PersistenceError(
            f"Phase 32 {label} staging contains an unknown file"
        )
    return direct, selected


def _is_internal_atomic_temp(name: str, allowed_names: set[str]) -> bool:
    for target_name in allowed_names:
        prefix = f".{target_name}."
        if not name.startswith(prefix) or not name.endswith(".tmp"):
            continue
        identity = name[len(prefix) : -len(".tmp")]
        parts = identity.split(".")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            return True
    return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "PHASE32_ARCHITECTURE_VERSION",
    "Phase27ExecutionRejected",
    "Phase32ArchitectureError",
    "Phase32PersistenceError",
    "Phase32RunRecord",
    "Phase32RunRepository",
]
