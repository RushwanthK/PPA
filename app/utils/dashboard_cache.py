"""User-scoped Redis cache for dashboard aggregates.

Uses cache-aside with TTL and a per-user generation token. A write changes the
user's generation after the database commit, making all previous dashboard
entries unreachable without scanning Redis keys. Cache failures never fail the
financial request; they fall back to the database, with TTL bounding stale data
if invalidation itself cannot reach Redis.
"""

import json
import secrets

from flask import current_app, has_app_context


DASHBOARD_RESOURCES = ("summary", "asset-allocation")
SPENDING_RANGES = ("30d", "3m", "6m", "1y", "all")
GENERATION_TTL_SECONDS = 30 * 24 * 60 * 60


def _redis_client():
    if not has_app_context():
        return None
    return current_app.extensions.get("ppa_dashboard_redis")


def _generation_key(user_id):
    return f"ppa:dashboard:v1:user:{int(user_id)}:generation"


def _cache_key(user_id, generation, resource, variant=None):
    suffix = f":{variant}" if variant is not None else ""
    return (
        f"ppa:dashboard:v1:user:{int(user_id)}:g:{generation}:"
        f"{resource}{suffix}"
    )


def _get_generation(client, user_id):
    key = _generation_key(user_id)
    current = client.get(key)
    if current is None:
        # A random token avoids reusing an old namespace if Redis evicts or
        # expires a generation key while old, short-lived values still exist.
        client.set(
            key,
            secrets.token_hex(16),
            nx=True,
            ex=GENERATION_TTL_SECONDS,
        )
        current = client.get(key)
    if current is None:
        raise RuntimeError("Dashboard cache generation is unavailable")
    if isinstance(current, bytes):
        current = current.decode("ascii")
    return str(current)


def get_cached_dashboard_payload(user_id, resource, variant=None):
    """Return (payload, generation, status); status is HIT, MISS or BYPASS."""
    client = _redis_client()
    if client is None:
        return None, None, "BYPASS"

    try:
        generation = _get_generation(client, user_id)
        key = _cache_key(user_id, generation, resource, variant)
        raw = client.get(key)
        if raw is None:
            return None, generation, "MISS"

        payload = json.loads(raw)

        # Avoid serving an entry if a successful write invalidated this user
        # between the generation lookup and the payload lookup.
        latest_generation = _get_generation(client, user_id)
        if latest_generation != generation:
            return None, latest_generation, "MISS"

        return payload, generation, "HIT"
    except Exception as exc:
        current_app.logger.warning(
            "Dashboard cache read failed; bypassing Redis (%s)",
            type(exc).__name__,
        )
        return None, None, "BYPASS"


def set_cached_dashboard_payload(
    user_id, resource, generation, payload, variant=None
):
    """Store a payload under the generation observed before calculation."""
    client = _redis_client()
    if client is None or generation is None:
        return False

    try:
        ttl = max(1, int(current_app.config.get(
            "DASHBOARD_CACHE_TTL_SECONDS", 60
        )))
        client.set(
            _cache_key(user_id, generation, resource, variant),
            json.dumps(payload, separators=(",", ":"), allow_nan=False),
            ex=ttl,
        )
        return True
    except Exception as exc:
        current_app.logger.warning(
            "Dashboard cache write failed; continuing without cache (%s)",
            type(exc).__name__,
        )
        return False


def invalidate_dashboard_cache(user_id):
    """Invalidate all dashboard resources for one user after a DB commit."""
    if user_id is None:
        return False

    client = _redis_client()
    if client is None:
        return False

    try:
        client.set(
            _generation_key(user_id),
            secrets.token_hex(16),
            ex=GENERATION_TTL_SECONDS,
        )
        return True
    except Exception as exc:
        # The financial write has already committed. Never turn a successful
        # write into an API error because Redis is temporarily unavailable.
        current_app.logger.warning(
            "Dashboard cache invalidation failed; TTL will bound staleness (%s)",
            type(exc).__name__,
        )
        return False
