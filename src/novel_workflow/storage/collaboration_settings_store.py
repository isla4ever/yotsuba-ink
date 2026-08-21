from __future__ import annotations

from pathlib import Path

from novel_workflow.output_contracts.author_collaboration import CollaborationSettings
from novel_workflow.storage.atomic_json import atomic_write_json, read_json


class CollaborationSettingsStore:
    """Single global authority for author-collaboration defaults."""

    def __init__(self, root: Path) -> None:
        self.path = root / "settings.json"

    def read(self) -> CollaborationSettings:
        if not self.path.exists():
            return CollaborationSettings()
        return CollaborationSettings.model_validate(read_json(self.path))

    def exists(self) -> bool:
        return self.path.exists()

    def write(self, settings: CollaborationSettings) -> CollaborationSettings:
        atomic_write_json(self.path, settings.model_dump(mode="json"))
        return settings


__all__ = ["CollaborationSettingsStore"]
