"""Regression smoke tests — verify existing functionality not broken by XR changes.

TDD baseline — these should PASS before and after PR6 implementation.
"""
import pytest

from tests.helpers import (
    create_test_user,
    create_test_venue,
    login_user,
    auth_headers,
)


class TestExistingBookingFlow:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_and_list_booking(self, client, db_session):
        admin = await create_test_user(db_session, username="xr-reg-bk", role="admin")
        venue = await create_test_venue(db_session, name="XR Reg Booking Venue")
        token = await login_user(client, "xr-reg-bk")

        resp = await client.post(
            "/api/v1/bookings",
            json={
                "venue_id": venue.id,
                "title": "Regression Booking",
                "start_time": "2026-10-01T09:00:00",
                "end_time": "2026-10-01T11:00:00",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201

        resp = await client.get("/api/v1/bookings", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestExistingVenueFlow:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_venue_crud(self, client, db_session):
        admin = await create_test_user(db_session, username="xr-reg-venue", role="admin")
        token = await login_user(client, "xr-reg-venue")

        resp = await client.post(
            "/api/v1/venues",
            json={"name": "XR Reg New Venue", "capacity": 30},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        venue_id = resp.json()["id"]

        resp = await client.get(
            f"/api/v1/venues/{venue_id}", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "XR Reg New Venue"


class TestExistingAuthFlow:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_login_returns_token(self, client, db_session):
        await create_test_user(db_session, username="xr-reg-auth", role="student")
        token = await login_user(client, "xr-reg-auth")
        assert token is not None
        assert len(token) > 0


class TestHealthEndpoint:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_health_check(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
