from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import stage_pointer
from novel_workflow.storage.chapter_store import ChapterStore
from novel_workflow.storage.artifact_store import ArtifactStore
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.narrative_run_repository import (
    NarrativeRunRepository,
    RunDefinition,
    RunReadModel,
)


@dataclass(frozen=True, slots=True)
class RunHistoryProjection:
    """Deterministic UI projection over the LangGraph Run authority."""

    runs: NarrativeRunRepository
    exports: ExportStore
    chapters: ChapterStore
    artifacts: ArtifactStore
    # Word totals scan every chapter file of a run; cache per (run, updated_at)
    # so terminal runs are only summed once per process.
    _words_cache: dict[str, tuple[str, int]] = field(default_factory=dict)

    def list(
        self,
        *,
        project_id: str = "",
        status: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for projection in self.runs.list():
            if project_id and projection.project_id != project_id:
                continue
            if status and projection.status != status:
                continue
            item = self._production_item(projection)
            if item is None:
                continue
            items.append(item)
            if limit is not None and len(items) >= limit:
                break
        return items

    def latest(self, project_id: str) -> dict[str, Any] | None:
        for projection in self.runs.list():
            if projection.project_id == project_id:
                item = self._production_item(projection)
                if item is not None:
                    return item
        return None

    def has_project_run(self, project_id: str) -> bool:
        """Check ownership without materializing exports or UI history items."""
        return any(item.project_id == project_id for item in self.runs.list())

    def item(self, projection: RunReadModel) -> dict[str, Any]:
        definition = self.runs.definition(projection.run_id)
        return self._item_from_definition(projection, definition)

    def _production_item(self, projection: RunReadModel) -> dict[str, Any] | None:
        try:
            definition = self.runs.definition(projection.run_id)
        except (FileNotFoundError, ValueError):
            return None
        return self._item_from_definition(projection, definition)

    def _item_from_definition(
        self,
        projection: RunReadModel,
        definition: RunDefinition,
    ) -> dict[str, Any]:
        completed = [
            stage
            for stage, value in projection.stage_status.items()
            if value == "completed"
        ]
        exports = self.exports.list(projection.run_id)
        return {
            "run_id": projection.run_id,
            "project_id": projection.project_id,
            "title": self._generated_title(projection.run_id),
            "quality_mode": definition.quality_mode,
            "status": projection.status,
            "current_stage": stage_pointer(projection.active_stage_id),
            "completed_stage_ids": completed,
            "created_at": definition.created_at,
            "updated_at": projection.updated_at,
            "completed_at": (
                projection.updated_at if projection.status == "completed" else ""
            ),
            "words": self._word_total(projection),
            "total_tokens": projection.provider_usage.total_tokens,
            "estimated_cost_usd": None,
            "summary": _run_summary(projection, completed),
            "can_branch": (
                projection.status == "awaiting_decision"
                and bool(projection.checkpoint_id and projection.pending_decisions)
            ),
            "checkpoint_id": projection.checkpoint_id,
            "export_ready": "export" in completed,
            "export_count": len(exports),
            "latest_export": exports[0].model_dump(mode="json") if exports else None,
        }

    def _word_total(self, projection: RunReadModel) -> int:
        cached = self._words_cache.get(projection.run_id)
        if cached is not None and cached[0] == projection.updated_at:
            return cached[1]
        total = self.chapters.latest_word_total(projection.run_id)
        self._words_cache[projection.run_id] = (projection.updated_at, total)
        return total

    def _generated_title(self, run_id: str) -> str:
        try:
            return str(self.artifacts.latest(run_id, "brief").payload["title"])
        except (FileNotFoundError, KeyError):
            return "待定书名"


_STATUS_TEXT = {
    "created": "已创建，等待启动",
    "running": "创作进行中",
    "awaiting_decision": "等待作者决策",
    "failed": "运行失败",
    "completed": "创作完成",
    "cancelled": "已取消",
}


def _run_summary(projection: RunReadModel, completed: list[str]) -> str:
    status_text = _STATUS_TEXT.get(projection.status, projection.status)
    stage_label = str(stage_pointer(projection.active_stage_id).get("label") or "")
    if projection.status == "completed":
        return f"{status_text}，全部 {len(completed)} 个阶段交付"
    if projection.status in {"running", "awaiting_decision"} and stage_label:
        return f"{status_text} · 当前阶段：{stage_label}"
    if projection.status == "failed" and stage_label:
        return f"{status_text} · 停在：{stage_label}"
    return status_text


__all__ = ["RunHistoryProjection"]
