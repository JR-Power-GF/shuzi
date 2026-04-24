import pytest
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.services.ai import AIService, MockProvider


@pytest.mark.asyncio(loop_scope="session")
async def test_get_config_reads_from_db(db_session: AsyncSession):
    db_session.add(AIConfig(key="model", value="gpt-4o"))
    db_session.add(AIConfig(key="budget_student", value="50000"))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)

    assert config["model"] == "gpt-4o"
    assert config["budget_student"] == 50000
