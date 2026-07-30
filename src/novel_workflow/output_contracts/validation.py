from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from novel_workflow.output_contracts.schemas import (
    ChapterTextContract,
    ChapterGenerationContract,
    CoverContract,
    DetailOutlineContract,
    ExportContract,
    OutlineContract,
    StoryBriefContract,
    SummaryContract,
)


class ArtifactValidationResult(BaseModel):
    valid: bool
    schema_name: str = ""
    artifact: Any = None
    errors: list[str] = []


SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "info_recommend": StoryBriefContract,
    "summary": SummaryContract,
    "outline": OutlineContract,
    "detail_outline": DetailOutlineContract,
    "chapter_text": ChapterTextContract,
    "cover_image": CoverContract,
    "export_artifact": ExportContract,
    "chapter_generation": ChapterGenerationContract,
}


def validate_stage_artifact(stage_type: str, artifact: Any) -> ArtifactValidationResult:
    model = SCHEMA_MODELS.get(stage_type)
    if model is None:
        return ArtifactValidationResult(valid=True, artifact=artifact)
    if not isinstance(artifact, dict):
        return ArtifactValidationResult(
            valid=False,
            schema_name=model.__name__,
            artifact=artifact,
            errors=["artifact: expected a structured JSON object"],
        )
    try:
        parsed = model.model_validate(artifact)
    except ValidationError as exc:
        return ArtifactValidationResult(
            valid=False,
            schema_name=model.__name__,
            artifact=artifact,
            errors=[_format_validation_error(error) for error in exc.errors()],
        )
    return ArtifactValidationResult(valid=True, schema_name=model.__name__, artifact=parsed.model_dump())


def validate_chapter_generation(artifact: Any) -> ArtifactValidationResult:
    return validate_stage_artifact("chapter_generation", artifact)


def _format_validation_error(error: dict[str, Any]) -> str:
    location = ".".join(str(part) for part in error.get("loc", ()))
    message = str(error.get("msg", "invalid"))
    return f"{location}: {message}" if location else message
