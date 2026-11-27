"""Read-only access to the user's PPA data through Flask's existing GET endpoints.

The AI service never connects to the finance database. It calls Flask with the
user's own token, so Flask's checks decide what is visible: a user can only ever
read their own accounts, exactly as in the app.
"""

import logging
from typing import Any

import httpx

log = logging.getLogger("ppa_ai.data")


class DataAuthError(Exception):
    """Flask rejected the token (expired or revoked since it was checked)."""


class DataUnavailable(Exception):
    """Flask could not be reached or returned an error."""


class FlaskDataClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient, *, timeout: float = 5.0):
        self._base = base_url.rstrip("/")
        self._client = client
        self._timeout = timeout

    async def get(self, path: str, token: str, params: dict | None = None) -> Any:
        """GET a Flask endpoint as the user. Returns parsed JSON, or None for 404."""
        if not path.startswith("/") or ".." in path:
            raise ValueError("path must be an absolute API path")
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        try:
            response = await self._client.get(self._base + path, params=clean, timeout=self._timeout,
                                              headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            log.warning("Flask data request failed", extra={"error_type": type(exc).__name__})
            raise DataUnavailable() from None
        if response.status_code in (401, 422):
            raise DataAuthError()
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            log.warning("Flask data request returned an error", extra={"status_code": response.status_code})
            raise DataUnavailable()
        try:
            return response.json()
        except ValueError:
            raise DataUnavailable() from None
