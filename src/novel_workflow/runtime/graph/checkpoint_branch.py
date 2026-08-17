from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from langgraph.types import Interrupt


class CheckpointBranchError(ValueError):
    pass


CheckpointBranchMode = Literal["active_decision", "stage_boundary"]


@dataclass(frozen=True, slots=True)
class CheckpointBranchPlan:
    source_thread_id: str
    checkpoint_id: str
    records: tuple[Any, ...]
    frontier_values: tuple[dict[str, Any], ...]
    active_interrupt_ids: frozenset[str]
    mode: CheckpointBranchMode


async def build_checkpoint_branch_plan(
    checkpointer: Any,
    *,
    source_thread_id: str,
    checkpoint_id: str,
    mode: CheckpointBranchMode = "active_decision",
) -> CheckpointBranchPlan:
    """Resolve one explicit immutable branch frontier."""

    source_config = {"configurable": {"thread_id": source_thread_id}}
    records = [record async for record in checkpointer.alist(source_config)]
    selected = next(
        (
            record
            for record in records
            if _namespace(record) == "" and _checkpoint_id(record) == checkpoint_id
        ),
        None,
    )
    if selected is None:
        raise CheckpointBranchError("Unknown top-level checkpoint")

    active_interrupt_ids = _interrupt_ids(selected)
    if mode == "active_decision" and not active_interrupt_ids:
        raise CheckpointBranchError(
            "A production branch must start from a checkpoint with an active decision"
        )
    if mode == "stage_boundary" and not _is_stable_stage_boundary(selected):
        raise CheckpointBranchError(
            "A stage-boundary branch requires a completed stage with a resumable next node"
        )

    records_by_key = {
        (_namespace(record), _checkpoint_id(record)): record for record in records
    }
    lineage_keys: set[tuple[str, str]] = set()
    frontier_keys: set[tuple[str, str]] = {("", checkpoint_id)}

    def include_chain(namespace: str, current_id: str) -> None:
        while current_id:
            key = (namespace, current_id)
            if key in lineage_keys:
                return
            record = records_by_key.get(key)
            if record is None:
                raise CheckpointBranchError("Checkpoint lineage is incomplete")
            lineage_keys.add(key)
            parent = record.parent_config or {}
            parent_configurable = parent.get("configurable", {})
            parent_namespace = str(parent_configurable.get("checkpoint_ns", namespace))
            if parent_namespace != namespace:
                raise CheckpointBranchError("Checkpoint lineage crossed namespaces")
            current_id = str(parent_configurable.get("checkpoint_id") or "")

    include_chain("", checkpoint_id)

    if mode == "active_decision":
        for record in records:
            namespace = _namespace(record)
            if not namespace or not (_interrupt_ids(record) & active_interrupt_ids):
                continue
            parents = record.metadata.get("parents") or {}
            if str(parents.get("") or "") != checkpoint_id:
                continue
            record_key = (namespace, _checkpoint_id(record))
            frontier_keys.add(record_key)
            include_chain(*record_key)
            for parent_namespace, parent_id in parents.items():
                parent_namespace = str(parent_namespace)
                parent_id = str(parent_id or "")
                if not parent_namespace or not parent_id:
                    continue
                frontier_keys.add((parent_namespace, parent_id))
                include_chain(parent_namespace, parent_id)

    lineage = tuple(
        sorted(
            (records_by_key[key] for key in lineage_keys),
            key=lambda item: str(item.checkpoint.get("ts") or ""),
        )
    )
    frontiers = tuple(
        sorted(
            (records_by_key[key] for key in frontier_keys),
            key=lambda item: (
                item.config["configurable"].get("checkpoint_ns", ""),
                str(item.checkpoint.get("ts") or ""),
            ),
        )
    )
    return CheckpointBranchPlan(
        source_thread_id=source_thread_id,
        checkpoint_id=checkpoint_id,
        records=lineage,
        frontier_values=tuple(
            deepcopy(record.checkpoint.get("channel_values") or {})
            for record in frontiers
        ),
        active_interrupt_ids=(
            frozenset(active_interrupt_ids)
            if mode == "active_decision"
            else frozenset()
        ),
        mode=mode,
    )


async def copy_checkpoint_lineage(
    checkpointer: Any,
    *,
    source_thread_id: str,
    target_thread_id: str,
    checkpoint_id: str,
    plan: CheckpointBranchPlan | None = None,
) -> None:
    """Copy a branch plan without writes appended after its active interrupt."""

    if plan is None:
        plan = await build_checkpoint_branch_plan(
            checkpointer,
            source_thread_id=source_thread_id,
            checkpoint_id=checkpoint_id,
        )
    if (
        plan.source_thread_id != source_thread_id
        or plan.checkpoint_id != checkpoint_id
    ):
        raise CheckpointBranchError("Checkpoint branch plan identity mismatch")

    for record in plan.records:
        configurable = record.config["configurable"]
        target_config = {
            "configurable": {
                "thread_id": target_thread_id,
                "checkpoint_ns": configurable.get("checkpoint_ns", ""),
            }
        }
        if record.parent_config is not None:
            parent_id = record.parent_config["configurable"].get("checkpoint_id")
            if parent_id:
                target_config["configurable"]["checkpoint_id"] = parent_id
        checkpoint = _remap_identity(
            deepcopy(record.checkpoint), source_thread_id, target_thread_id
        )
        metadata = _remap_identity(
            deepcopy(record.metadata), source_thread_id, target_thread_id
        )
        saved_config = await checkpointer.aput(
            target_config,
            checkpoint,
            metadata,
            checkpoint.get("channel_versions", {}),
        )
        grouped_writes: dict[str, list[tuple[str, Any]]] = defaultdict(list)
        pending_writes = record.pending_writes or []
        if plan.mode == "stage_boundary":
            pending_writes = []
        for task_id, channel, value in pending_writes:
            if (
                _interrupt_ids(record) & plan.active_interrupt_ids
                and channel != "__interrupt__"
            ):
                continue
            grouped_writes[task_id].append(
                (channel, _remap_identity(deepcopy(value), source_thread_id, target_thread_id))
            )
        for task_id, writes in grouped_writes.items():
            await checkpointer.aput_writes(saved_config, writes, task_id)


def remap_run_identity(value: Any, source_run_id: str, target_run_id: str) -> Any:
    return _remap_identity(deepcopy(value), source_run_id, target_run_id)


def _namespace(record: Any) -> str:
    return str(record.config["configurable"].get("checkpoint_ns", ""))


def _checkpoint_id(record: Any) -> str:
    return str(record.config["configurable"].get("checkpoint_id", ""))


def _interrupt_ids(record: Any) -> set[str]:
    ids: set[str] = set()
    for _, channel, value in record.pending_writes or []:
        if channel != "__interrupt__":
            continue
        interrupts = value if isinstance(value, (list, tuple)) else [value]
        ids.update(
            str(item.id)
            for item in interrupts
            if isinstance(item, Interrupt) and item.id
        )
    return ids


def _is_stable_stage_boundary(record: Any) -> bool:
    values = record.checkpoint.get("channel_values") or {}
    active_stage = str(values.get("active_stage_id") or "")
    stage_status = values.get("stage_status") or {}
    has_next_node = any(
        key.startswith("branch:to:")
        for key in values
    )
    return (
        bool(active_stage)
        and stage_status.get(active_stage) == "completed"
        and values.get("status") == "running"
        and values.get("failure") is None
        and has_next_node
    )


def _remap_identity(value: Any, source: str, target: str) -> Any:
    if isinstance(value, str):
        if value == source:
            return target
        if value.startswith(f"{source}:"):
            return f"{target}:{value[len(source) + 1:]}"
        marker = f"run-definition:{source}:"
        if value.startswith(marker):
            return f"run-definition:{target}:{value[len(marker):]}"
        return value
    if isinstance(value, list):
        return [_remap_identity(item, source, target) for item in value]
    if isinstance(value, tuple):
        return tuple(_remap_identity(item, source, target) for item in value)
    if isinstance(value, Interrupt):
        return Interrupt(
            value=_remap_identity(value.value, source, target),
            id=value.id,
        )
    if isinstance(value, dict):
        return {
            key: _remap_identity(item, source, target)
            for key, item in value.items()
        }
    return value


__all__ = [
    "CheckpointBranchError",
    "CheckpointBranchMode",
    "CheckpointBranchPlan",
    "build_checkpoint_branch_plan",
    "copy_checkpoint_lineage",
    "remap_run_identity",
]
