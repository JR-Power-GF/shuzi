import pytest
from tests.helpers import create_test_user, login_user, auth_headers
from app.models.ai_usage_log import AIUsageLog


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_positive_feedback(client, db_session):
    user = await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    log = AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": 1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["rating"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_negative_feedback_with_comment(client, db_session):
    user = await create_test_user(db_session, username="teacher2", role="teacher")
    token = await login_user(client, "teacher2")

    log = AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": -1, "comment": "回答不准确"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["comment"] == "回答不准确"


@pytest.mark.asyncio(loop_scope="session")
async def test_feedback_cross_user_forbidden(client, db_session):
    teacher = await create_test_user(db_session, username="teacher_x", role="teacher")
    await create_test_user(db_session, username="teacher_y", role="teacher")
    token2 = await login_user(client, "teacher_y")

    log = AIUsageLog(
        user_id=teacher.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": 1},
        headers=auth_headers(token2),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_feedback_duplicate_rejected(client, db_session):
    user = await create_test_user(db_session, username="teacher_z", role="teacher")
    token = await login_user(client, "teacher_z")

    log = AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": 1},
        headers=auth_headers(token),
    )

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": -1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_feedback_rating_too_high_rejected(client, db_session):
    user = await create_test_user(db_session, username="teacher_rating_hi", role="teacher")
    token = await login_user(client, "teacher_rating_hi")

    log = AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": 2},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_feedback_rating_too_low_rejected(client, db_session):
    user = await create_test_user(db_session, username="teacher_rating_lo", role="teacher")
    token = await login_user(client, "teacher_rating_lo")

    log = AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": -2},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422
