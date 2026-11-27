"""Request id + one log line per request (pure ASGI middleware, so streaming and
background tasks are unaffected)."""

import logging
import time

from .logging_setup import REQUEST_ID_RE, new_request_id, request_id_var

log = logging.getLogger("ppa_ai.request")


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Reuse a caller's id (for example from a proxy) only if it looks like an id;
        # anything else could be used to inject text into the logs.
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if REQUEST_ID_RE.match(incoming) else new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [(b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            level = logging.WARNING if status >= 500 else logging.INFO
            # Health checks run every few seconds on a host; keep them out of the INFO stream.
            if route.startswith("/health") and status < 500:
                level = logging.DEBUG
            log.log(level, "request finished", extra={
                "method": scope.get("method"), "route": route, "status": status,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            })
            request_id_var.reset(token)
