"""XR Provider protocol, null implementation, and provider factory."""
from __future__ import annotations

import dataclasses
from typing import Any, Protocol, runtime_checkable

from app.config import settings


@dataclasses.dataclass
class XRResult:
    """Return type for all XR provider calls."""
    success: bool
    external_session_id: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None


@runtime_checkable
class XRProvider(Protocol):
    """Abstract interface for XR platform integration."""

    @property
    def name(self) -> str: ...

    async def create_session(self, *, booking_id: int) -> XRResult: ...

    async def cancel_session(self, *, session_id: str) -> XRResult: ...

    async def update_session(self, *, session_id: str, updates: dict) -> XRResult: ...


class NullXRProvider:
    """No-op XR provider. All methods succeed without external calls."""

    @property
    def name(self) -> str:
        return "null"

    async def create_session(self, *, booking_id: int) -> XRResult:
        return XRResult(success=True)

    async def cancel_session(self, *, session_id: str) -> XRResult:
        return XRResult(success=True)

    async def update_session(self, *, session_id: str, updates: dict) -> XRResult:
        return XRResult(success=True)


_PROVIDER_REGISTRY: dict[str, type] = {
    "null": NullXRProvider,
}


def get_xr_provider() -> XRProvider:
    """Return the configured XR provider instance."""
    provider_name = settings.XR_PROVIDER
    cls = _PROVIDER_REGISTRY.get(provider_name)
    if cls is None:
        raise ValueError(f"Unknown XR provider: {provider_name}")
    return cls()
