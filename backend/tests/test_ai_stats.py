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


@pytest.mark.asyncio(loop_scope="session")
async def test_stats_aggregate(client, db_session):
    await create_test_user(db_session, username="admin_s", role="admin")
    student = await create_test_user(db_session, username="stu_s", role="student")
    token = await login_user(client, "admin_s")

    db_session.add(AIUsageLog(
        user_id=student.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, cost_microdollars=45,
        latency_ms=200, status="success",
    ))
    db_session.add(AIUsageLog(
        user_id=student.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=80, completion_tokens=40, cost_microdollars=36,
        latency_ms=150, status="error",
    ))
    await db_session.flush()

    resp = await client.get("/api/ai/stats", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_calls"] == 2
    assert data["total_prompt_tokens"] == 180
    assert data["success_rate"] == 0.5


@pytest.mark.asyncio(loop_scope="session")
async def test_stats_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu_s2", role="student")
    token = await login_user(client, "stu_s2")

    resp = await client.get("/api/ai/stats", headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_feedback_summary(client, db_session):
    await create_test_user(db_session, username="admin_f", role="admin")
    student = await create_test_user(db_session, username="stu_f", role="student")
    token = await login_user(client, "admin_f")

    from app.models.ai_feedback import AIFeedback
    log1 = AIUsageLog(
        user_id=student.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log1)
    await db_session.flush()

    log2 = AIUsageLog(
        user_id=student.id, endpoint="test2", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log2)
    await db_session.flush()

    db_session.add(AIFeedback(ai_usage_log_id=log1.id, user_id=student.id, rating=1))
    db_session.add(AIFeedback(ai_usage_log_id=log2.id, user_id=student.id, rating=-1, comment="不好"))
    await db_session.flush()

    resp = await client.get("/api/ai/stats/feedback", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["positive_count"] == 1
    assert data["negative_count"] == 1
