"""Authentication middleware for sensitive endpoint re-authentication.

Requirement 12.4: Re-authentication within 10-minute window for wallet/account access.
"""

from __future__ import annotations

import time

from fastapi import HTTPException
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings

_RECENT_AUTH_MAX_AGE = 10 * 60  # 10 minutes

# Path prefixes that require recent authentication
SENSITIVE_PREFIXES: list[str] = [
    "/api/v1/wallet",
    "/api/v1/account",
]


class RecentAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests to sensitive endpoints when the JWT is older than 10 minutes.

    This complements the ``require_recent_auth`` dependency in ``app/api/deps.py``
    by providing a middleware-level guard that can be applied globally.
    """

    def __init__(self, app: ASGIApp, sensitive_prefixes: list[str] | None = None) -> None:
        super().__init__(app)
        self.sensitive_prefixes = sensitive_prefixes or SENSITIVE_PREFIXES

    def _is_sensitive(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.sensitive_prefixes)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # BaseHTTPMiddleware does not support WebSocket — pass through
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        if not self._is_sensitive(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            # No valid bearer token — let downstream auth handle rejection
            return await call_next(request)

        try:
            payload = jwt.decode(
                parts[1],
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except JWTError:
            # Invalid token — let downstream auth handle rejection
            return await call_next(request)

        if payload.get("type") != "access":
            return await call_next(request)

        iat = payload.get("iat")
        if iat is None or (time.time() - iat) > _RECENT_AUTH_MAX_AGE:
            raise HTTPException(
                status_code=401,
                detail="Re-authentication required for wallet access",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
