import json
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt import PromptTemplateOut, PromptTemplateUpdate

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptTemplateOut])
async def list_templates(
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).order_by(PromptTemplate.name))
    templates = result.scalars().all()
    return [
        PromptTemplateOut(
            id=t.id, name=t.name, description=t.description,
            template_text=t.template_text, variables=json.loads(t.variables),
            updated_at=t.updated_at, updated_by=t.updated_by,
        ) for t in templates
    ]


@router.put("/{name}", response_model=PromptTemplateOut)
async def update_template(
    name: str,
    data: PromptTemplateUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.name == name))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    allowed_vars = set(json.loads(template.variables))
    used_vars = set(re.findall(r'\{(\w+)\}', data.template_text))
    invalid = used_vars - allowed_vars
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid variables: {', '.join(sorted(invalid))}",
        )

    template.template_text = data.template_text
    template.updated_by = current_user["id"]
    await db.flush()

    return PromptTemplateOut(
        id=template.id, name=template.name, description=template.description,
        template_text=template.template_text, variables=json.loads(template.variables),
        updated_at=template.updated_at, updated_by=template.updated_by,
    )
