"""Authentication by asking the Flask API who the token belongs to.

The AI service holds no JWT secret. Flask's GET /me already checks the signature,
expiry and revocation (logout, "log out of all devices", password change), so it
stays the single source of truth.

Trade-off: results are cached for a few seconds (AUTH_CACHE_SECONDS) to avoid one
extra HTTP call per question. A token revoked in Flask can keep working here for at
most that long.
"""

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass

import httpx


class AuthError(Exception):
    """The token is missing, invalid, expired or revoked (HTTP 401)."""


class AuthUnavailable(Exception):
    """Flask could not be reached, so identity cannot be checked (HTTP 503). Fail closed."""


@dataclass(frozen=True)
class CurrentUser:
    id: int


class FlaskAuthClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient, *, cache_seconds: float = 30.0,
                 timeout: float = 5.0, max_cache: int = 1000, clock=time.monotonic):
        self._url = base_url.rstrip("/") + "/me"
        self._client = client
        self._ttl = cache_seconds
        self._timeout = timeout
        self._max = max_cache
        self._clock = clock
        # Keyed by a hash of the token, so raw tokens are never kept in memory longer than needed.
        self._cache: OrderedDict[str, tuple[float, CurrentUser]] = OrderedDict()

    async def verify(self, token: str) -> CurrentUser:
        key = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = self._clock()
        cached = self._cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

        try:
            response = await self._client.get(self._url, timeout=self._timeout,
                                              headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            raise AuthUnavailable() from None

        if response.status_code in (401, 403, 404, 422):
            self._cache.pop(key, None)
            raise AuthError()
        if response.status_code != 200:
            raise AuthUnavailable()
        try:
            user = CurrentUser(id=int(response.json()["id"]))
        except (ValueError, KeyError, TypeError):
            raise AuthUnavailable() from None
        # Only the user id is kept; /me also returns personal details we do not need.

        if self._ttl > 0:
            self._cache[key] = (now + self._ttl, user)
            self._cache.move_to_end(key)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)
        return user
