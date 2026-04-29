"""Tests for XRProvider protocol, NullXRProvider, and provider factory.

TDD RED phase — all tests written before implementation.

Covers:
  1. XRResult dataclass fields
  2. NullXRProvider no-op behavior
  3. Provider factory lookup
  4. Protocol compliance
"""
import pytest

from app.config import settings


class TestXRResult:
    def test_success_defaults(self):
        from app.services.xr_provider import XRResult

        r = XRResult(success=True)
        assert r.success is True
        assert r.external_session_id is None
        assert r.error is None
        assert r.raw_response is None

    def test_failure_with_error(self):
        from app.services.xr_provider import XRResult

        r = XRResult(success=False, error="connection refused")
        assert r.success is False
        assert r.error == "connection refused"
        assert r.external_session_id is None

    def test_success_with_external_id_and_response(self):
        from app.services.xr_provider import XRResult

        r = XRResult(
            success=True,
            external_session_id="ext-session-42",
            raw_response={"status": "ok", "url": "xr://room/42"},
        )
        assert r.external_session_id == "ext-session-42"
        assert r.raw_response == {"status": "ok", "url": "xr://room/42"}


class TestNullXRProvider:
    @pytest.fixture
    def provider(self):
        from app.services.xr_provider import NullXRProvider

        return NullXRProvider()

    def test_name_is_null(self, provider):
        assert provider.name == "null"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_session_returns_success(self, provider):
        result = await provider.create_session(booking_id=1)
        assert result.success is True
        assert result.external_session_id is None

    @pytest.mark.asyncio(loop_scope="session")
    async def test_cancel_session_returns_success(self, provider):
        result = await provider.cancel_session(session_id="any-id")
        assert result.success is True

    def test_satisfies_xr_provider_protocol(self, provider):
        from app.services.xr_provider import XRProvider

        assert isinstance(provider, XRProvider)


class TestGetXrProvider:
    def test_returns_null_by_default(self):
        from app.services.xr_provider import NullXRProvider, get_xr_provider

        p = get_xr_provider()
        assert isinstance(p, NullXRProvider)

    def test_returns_null_when_explicitly_configured(self, monkeypatch):
        from app.services.xr_provider import NullXRProvider, get_xr_provider

        monkeypatch.setattr(settings, "XR_PROVIDER", "null")
        p = get_xr_provider()
        assert isinstance(p, NullXRProvider)

    def test_unknown_provider_name_raises_value_error(self, monkeypatch):
        from app.services.xr_provider import get_xr_provider

        monkeypatch.setattr(settings, "XR_PROVIDER", "nonexistent_vendor")
        with pytest.raises(ValueError, match="Unknown XR provider"):
            get_xr_provider()
