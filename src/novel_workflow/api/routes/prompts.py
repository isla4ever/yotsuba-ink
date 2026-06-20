from __future__ import annotations

from fastapi import APIRouter, Request

from novel_workflow.api.bootstrap import list_prompt_templates
from novel_workflow.workflows.schemas import PromptTemplate


router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("")
async def list_prompts(request: Request) -> list[PromptTemplate]:
    return list_prompt_templates(request.app)


@router.post("")
async def save_prompt(request: Request, prompt: PromptTemplate) -> PromptTemplate:
    request.app.state.prompt_store.write(prompt.id, prompt.model_dump())
    return prompt
