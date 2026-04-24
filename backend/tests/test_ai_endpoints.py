import pytest
from tests.helpers import create_test_user, login_user, auth_headers
from app.models.ai_config import AIConfig


@pytest.mark.asyncio(loop_scope="session")
async def test_ai_test_call(client, db_session):
    await create_test_user(db_session, username="admin_t", role="admin")
    token = await login_user(client, "admin_t")

    resp = await client.post("/api/ai/test", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "usage_log_id" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_read_config(client, db_session):
    await create_test_user(db_session, username="admin_r", role="admin")
    token = await login_user(client, "admin_r")

    resp = await client.get("/api/ai/config", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "model" in data
    assert "is_configured" in data
    assert "budget_admin" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_update_config_model(client, db_session):
    await create_test_user(db_session, username="admin_u", role="admin")
    token = await login_user(client, "admin_u")

    resp = await client.put(
        "/api/ai/config",
        json={"model": "gpt-4o"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["model"] == "gpt-4o"

    resp2 = await client.get("/api/ai/config", headers=auth_headers(token))
    assert resp2.json()["model"] == "gpt-4o"


@pytest.mark.asyncio(loop_scope="session")
async def test_config_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu_c", role="student")
    token = await login_user(client, "stu_c")

    resp = await client.get("/api/ai/config", headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_test_call_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu_t", role="student")
    token = await login_user(client, "stu_t")

    resp = await client.post("/api/ai/test", headers=auth_headers(token))
    assert resp.status_code == 403
