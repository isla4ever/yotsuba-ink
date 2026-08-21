from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from novel_workflow.output_contracts.author_collaboration import (
    ArtifactPatchCandidate,
    CollaborationMessage,
    CollaborationStreamEvent,
    CollaborationThread,
    CollaborationTurn,
    CollaborationTurnStatus,
)
from novel_workflow.storage.atomic_json import (
    atomic_write_json,
    read_json,
    require_safe_id,
)


_TURN_TRANSITIONS: dict[CollaborationTurnStatus, set[CollaborationTurnStatus]] = {
    "awaiting_context": {"queued", "cancelled"},
    "queued": {"streaming", "cancelled", "failed"},
    "streaming": {
        "completed",
        "cancelled",
        "failed",
        "contract_rejected",
    },
    "completed": set(),
    "cancelled": set(),
    "failed": set(),
    "contract_rejected": set(),
}


class CollaborationStore:
    """File-backed authority for collaboration threads, turns, messages and patches."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create_thread(self, thread: CollaborationThread) -> CollaborationThread:
        path = self._thread_path(thread.run_id, thread.thread_id)
        with self._lock:
            if path.exists():
                existing = CollaborationThread.model_validate(read_json(path))
                expected = thread.model_copy(
                    update={
                        "created_at": existing.created_at,
                        "updated_at": existing.updated_at,
                    }
                )
                if existing != expected:
                    raise ValueError("Collaboration thread identity was reused")
                return existing
            atomic_write_json(path, thread.model_dump(mode="json"))
            self.append_event(
                thread.run_id,
                thread.thread_id,
                "thread.created",
                payload={"stage_id": thread.stage_id, "title": thread.title},
            )
        return thread

    def update_thread(
        self,
        run_id: str,
        thread_id: str,
        **changes: object,
    ) -> CollaborationThread:
        with self._lock:
            current = self.read_thread(run_id, thread_id)
            updated = current.model_copy(update={**changes, "updated_at": _now()})
            atomic_write_json(
                self._thread_path(run_id, thread_id),
                updated.model_dump(mode="json"),
            )
            self.append_event(
                run_id,
                thread_id,
                "thread.updated",
                payload={"status": updated.status, "title": updated.title},
            )
            return updated

    def read_thread(self, run_id: str, thread_id: str) -> CollaborationThread:
        value = CollaborationThread.model_validate(
            read_json(self._thread_path(run_id, thread_id))
        )
        if value.run_id != run_id or value.thread_id != thread_id:
            raise ValueError("Collaboration thread identity mismatch")
        return value

    def list_threads(
        self,
        run_id: str,
        *,
        include_archived: bool = True,
    ) -> list[CollaborationThread]:
        directory = self._run_dir(run_id) / "threads"
        if not directory.exists():
            return []
        threads = [
            CollaborationThread.model_validate(read_json(path))
            for path in directory.glob("*.json")
        ]
        threads = [item for item in threads if item.status != "deleted"]
        if not include_archived:
            threads = [item for item in threads if item.status == "active"]
        return sorted(threads, key=lambda item: item.updated_at, reverse=True)

    def create_turn(self, turn: CollaborationTurn) -> CollaborationTurn:
        replay = self.find_turn_by_client_id(
            turn.run_id,
            turn.thread_id,
            turn.client_turn_id,
        )
        if replay is not None:
            if _turn_request_signature(replay) != _turn_request_signature(turn):
                raise ValueError("turn_replay_conflict")
            return replay
        path = self._turn_path(turn.run_id, turn.thread_id, turn.turn_id)
        with self._lock:
            if path.exists():
                raise ValueError("Collaboration turn identity was reused")
            atomic_write_json(path, turn.model_dump(mode="json"))
            self.append_event(
                turn.run_id,
                turn.thread_id,
                "turn.started",
                turn_id=turn.turn_id,
                payload={"mode": turn.mode, "status": turn.status},
            )
            self.update_thread(
                turn.run_id,
                turn.thread_id,
                turn_count=self.read_thread(turn.run_id, turn.thread_id).turn_count + 1,
            )
        return turn

    def transition_turn(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
        status: CollaborationTurnStatus,
        **changes: object,
    ) -> CollaborationTurn:
        with self._lock:
            current = self.read_turn(run_id, thread_id, turn_id)
            if current.status == status:
                return current
            if status not in _TURN_TRANSITIONS[current.status]:
                raise ValueError(
                    f"Invalid collaboration turn transition {current.status} -> {status}"
                )
            updated = current.model_copy(
                update={**changes, "status": status, "updated_at": _now()}
            )
            atomic_write_json(
                self._turn_path(run_id, thread_id, turn_id),
                updated.model_dump(mode="json"),
            )
            return updated

    def read_turn(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
    ) -> CollaborationTurn:
        value = CollaborationTurn.model_validate(
            read_json(self._turn_path(run_id, thread_id, turn_id))
        )
        if (
            value.run_id != run_id
            or value.thread_id != thread_id
            or value.turn_id != turn_id
        ):
            raise ValueError("Collaboration turn identity mismatch")
        return value

    def find_turn_by_client_id(
        self,
        run_id: str,
        thread_id: str,
        client_turn_id: str,
    ) -> CollaborationTurn | None:
        for turn in self.list_turns(run_id, thread_id):
            if turn.client_turn_id == client_turn_id:
                return turn
        return None

    def list_turns(self, run_id: str, thread_id: str) -> list[CollaborationTurn]:
        directory = self._run_dir(run_id) / "turns" / thread_id
        if not directory.exists():
            return []
        return sorted(
            (
                CollaborationTurn.model_validate(read_json(path))
                for path in directory.glob("*.json")
            ),
            key=lambda item: (item.created_at, item.turn_id),
        )

    def write_message(self, run_id: str, message: CollaborationMessage) -> CollaborationMessage:
        thread = self.read_thread(run_id, message.thread_id)
        if thread.run_id != run_id:
            raise ValueError("Message Run does not match its thread")
        path = self._message_path(run_id, message.thread_id, message.message_id)
        with self._lock:
            if path.exists():
                existing = CollaborationMessage.model_validate(read_json(path))
                expected = message.model_copy(update={"created_at": existing.created_at})
                if existing != expected:
                    raise ValueError("Collaboration messages are immutable")
                return existing
            atomic_write_json(path, message.model_dump(mode="json"))
        return message

    def read_message(
        self,
        run_id: str,
        thread_id: str,
        message_id: str,
    ) -> CollaborationMessage:
        value = CollaborationMessage.model_validate(
            read_json(self._message_path(run_id, thread_id, message_id))
        )
        if value.thread_id != thread_id or value.message_id != message_id:
            raise ValueError("Collaboration message identity mismatch")
        return value

    def list_messages(
        self,
        run_id: str,
        thread_id: str,
        *,
        limit: int = 80,
    ) -> list[CollaborationMessage]:
        directory = self._run_dir(run_id) / "messages" / thread_id
        if not directory.exists():
            return []
        items = sorted(
            (
                CollaborationMessage.model_validate(read_json(path))
                for path in directory.glob("*.json")
            ),
            key=lambda item: (item.created_at, item.message_id),
        )
        return items[-max(1, limit) :]

    def write_patch(self, patch: ArtifactPatchCandidate) -> ArtifactPatchCandidate:
        path = self._patch_path(patch.run_id, patch.patch_id)
        with self._lock:
            if path.exists():
                existing = ArtifactPatchCandidate.model_validate(read_json(path))
                expected = patch.model_copy(
                    update={
                        "created_at": existing.created_at,
                        "updated_at": existing.updated_at,
                    }
                )
                if existing != expected:
                    raise ValueError("Patch candidate identity was reused")
                return existing
            atomic_write_json(path, patch.model_dump(mode="json"))
            self.update_thread(patch.run_id, patch.thread_id, has_unapplied_patch=True)
        return patch

    def transition_patch(
        self,
        run_id: str,
        patch_id: str,
        status: str,
        *,
        writeback_ref: str = "",
    ) -> ArtifactPatchCandidate:
        if status not in {"accepted", "rejected", "stale"}:
            raise ValueError("Invalid patch decision")
        with self._lock:
            current = self.read_patch(run_id, patch_id)
            if current.status == status:
                return current
            if current.status != "proposed":
                raise ValueError("Patch candidate decision is immutable")
            updated = current.model_copy(
                update={
                    "status": status,
                    "writeback_ref": writeback_ref,
                    "updated_at": _now(),
                }
            )
            atomic_write_json(
                self._patch_path(run_id, patch_id),
                updated.model_dump(mode="json"),
            )
            pending = any(
                item.status == "proposed"
                for item in self.list_patches(run_id, thread_id=current.thread_id)
                if item.patch_id != patch_id
            )
            self.update_thread(
                run_id,
                current.thread_id,
                has_unapplied_patch=pending,
            )
            return updated

    def read_patch(self, run_id: str, patch_id: str) -> ArtifactPatchCandidate:
        value = ArtifactPatchCandidate.model_validate(
            read_json(self._patch_path(run_id, patch_id))
        )
        if value.run_id != run_id or value.patch_id != patch_id:
            raise ValueError("Patch candidate identity mismatch")
        return value

    def list_patches(
        self,
        run_id: str,
        *,
        thread_id: str = "",
    ) -> list[ArtifactPatchCandidate]:
        directory = self._run_dir(run_id) / "patches"
        if not directory.exists():
            return []
        items = [
            ArtifactPatchCandidate.model_validate(read_json(path))
            for path in directory.glob("*.json")
        ]
        if thread_id:
            items = [item for item in items if item.thread_id == thread_id]
        return sorted(items, key=lambda item: (item.created_at, item.patch_id))

    def append_event(
        self,
        run_id: str,
        thread_id: str,
        event_type: str,
        *,
        turn_id: str = "",
        payload: dict[str, object] | None = None,
    ) -> CollaborationStreamEvent:
        with self._lock:
            directory = self._run_dir(run_id) / "stream" / thread_id
            index_path = directory / "index.json"
            index = read_json(index_path) if index_path.exists() else {"sequence": 0}
            sequence = int(index.get("sequence") or 0) + 1
            event = CollaborationStreamEvent(
                sequence=sequence,
                event_id=f"collab-{thread_id}-{sequence}",
                thread_id=thread_id,
                turn_id=turn_id,
                type=event_type,
                payload=payload or {},
                created_at=_now(),
            )
            atomic_write_json(
                directory / f"{sequence:012d}.json",
                event.model_dump(mode="json"),
            )
            atomic_write_json(index_path, {"sequence": sequence})
            return event

    def read_events(
        self,
        run_id: str,
        thread_id: str,
        *,
        after: int = 0,
    ) -> list[CollaborationStreamEvent]:
        directory = self._run_dir(run_id) / "stream" / thread_id
        if not directory.exists():
            return []
        return [
            CollaborationStreamEvent.model_validate(read_json(path))
            for path in sorted(directory.glob("*.json"))
            if path.name != "index.json" and int(path.stem) > after
        ]

    @staticmethod
    def new_thread_id() -> str:
        return f"collab-{uuid4().hex}"

    @staticmethod
    def turn_id(thread_id: str, client_turn_id: str) -> str:
        digest = hashlib.sha256(
            f"{thread_id}\0{client_turn_id}".encode("utf-8")
        ).hexdigest()
        return f"turn-{digest[:32]}"

    def _run_dir(self, run_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        return self.root / run_id

    def _thread_path(self, run_id: str, thread_id: str) -> Path:
        require_safe_id(thread_id, label="collaboration thread_id")
        return self._run_dir(run_id) / "threads" / f"{thread_id}.json"

    def _turn_path(self, run_id: str, thread_id: str, turn_id: str) -> Path:
        require_safe_id(turn_id, label="collaboration turn_id")
        return self._run_dir(run_id) / "turns" / thread_id / f"{turn_id}.json"

    def _message_path(
        self,
        run_id: str,
        thread_id: str,
        message_id: str,
    ) -> Path:
        require_safe_id(message_id, label="collaboration message_id")
        return self._run_dir(run_id) / "messages" / thread_id / f"{message_id}.json"

    def _patch_path(self, run_id: str, patch_id: str) -> Path:
        require_safe_id(patch_id, label="collaboration patch_id")
        return self._run_dir(run_id) / "patches" / f"{patch_id}.json"


def _turn_request_signature(turn: CollaborationTurn) -> str:
    encoded = json.dumps(
        {
            "thread_id": turn.thread_id,
            "client_turn_id": turn.client_turn_id,
            "mode": turn.mode,
            "user_message_ref": turn.user_message_ref,
            "context_receipt_ref": turn.context_receipt_ref,
            "preview_signature": turn.context_preview_signature,
            "selection_anchor": (
                turn.selection_anchor.model_dump(mode="json")
                if turn.selection_anchor
                else None
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["CollaborationStore"]
