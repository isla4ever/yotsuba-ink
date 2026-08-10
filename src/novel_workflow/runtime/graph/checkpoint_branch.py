from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from langgraph.types import Interrupt


class CheckpointBranchError(ValueError):
    pass


async def copy_checkpoint_lineage(
    checkpointer: Any,
    *,
    source_thread_id: str,
    target_thread_id: str,
    checkpoint_id: str,
) -> None:
    """Copy one top-level checkpoint and all lineage needed by its subgraphs."""

    source_config = {"configurable": {"thread_id": source_thread_id}}
    records = [record async for record in checkpointer.alist(source_config)]
    selected = next(
        (
            record
            for record in records
            if record.config["configurable"].get("checkpoint_ns", "") == ""
            and record.config["configurable"].get("checkpoint_id") == checkpoint_id
        ),
        None,
    )
    if selected is None:
        raise CheckpointBranchError("Unknown top-level checkpoint")

    selected_ts = str(selected.checkpoint.get("ts") or "")
    later_top_level = sorted(
        str(record.checkpoint.get("ts") or "")
        for record in records
        if record.config["configurable"].get("checkpoint_ns", "") == ""
        and str(record.checkpoint.get("ts") or "") > selected_ts
    )
    cutoff = later_top_level[0] if later_top_level else ""
    lineage = [
        record
        for record in records
        if str(record.checkpoint.get("ts") or "") <= selected_ts
        or (cutoff and str(record.checkpoint.get("ts") or "") < cutoff)
        or (not cutoff)
    ]

    for record in sorted(lineage, key=lambda item: str(item.checkpoint.get("ts") or "")):
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
        for task_id, channel, value in record.pending_writes or []:
            grouped_writes[task_id].append(
                (channel, _remap_identity(deepcopy(value), source_thread_id, target_thread_id))
            )
        for task_id, writes in grouped_writes.items():
            await checkpointer.aput_writes(saved_config, writes, task_id)


def remap_run_identity(value: Any, source_run_id: str, target_run_id: str) -> Any:
    return _remap_identity(deepcopy(value), source_run_id, target_run_id)


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


__all__ = ["CheckpointBranchError", "copy_checkpoint_lineage", "remap_run_identity"]
