import json
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate


class PromptService:
    async def get_template(self, db: AsyncSession, name: str) -> dict:
        result = await db.execute(
            select(PromptTemplate).where(PromptTemplate.name == name)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError(f"Template '{name}' not found")
        return {
            "name": template.name,
            "description": template.description,
            "template_text": template.template_text,
            "variables": json.loads(template.variables),
        }

    async def fill_template(self, db: AsyncSession, name: str, context: dict) -> str:
        template = await self.get_template(db, name)
        required_vars = set(template["variables"])
        provided_vars = set(context.keys())
        missing = required_vars - provided_vars
        if missing:
            raise ValueError(f"Missing template variables: {', '.join(sorted(missing))}")
        safe_context = {k: str(v).replace("{", "{{").replace("}", "}}") for k, v in context.items()}
        return template["template_text"].format(**safe_context)
