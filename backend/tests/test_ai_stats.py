import pytest
from tests.helpers import create_test_user, login_user, auth_headers
from app.models.ai_usage_log import AIUsageLog


@pytest.mark.asyncio(loop_scope="session")
async def test_usage_query_admin(client, db_session):
    await create_test_user(db_session, username="admin_q", role="admin")
    student = await create_test_user(db_session, username="stu_q", role="student")
    token = await login_user(client, "admin_q")

    db_session.add(AIUsageLog(
        user_id=student.id, endpoint="student_qa", model="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, cost_microdollars=45,
        latency_ms=200, status="success",
    ))
    await db_session.flush()

    resp = await client.get("/api/ai/usage", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["endpoint"] == "student_qa"


@pytest.mark.asyncio(loop_scope="session")
async def test_usage_query_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu_q2", role="student")
    token = await login_user(client, "stu_q2")

    resp = await client.get("/api/ai/usage", headers=auth_headers(token))
    assert resp.status_code == 403
