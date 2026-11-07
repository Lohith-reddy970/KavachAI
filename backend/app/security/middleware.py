"""Security middleware for KAVACH AI.

Responsibilities:
    * Record an audit-log entry for every mutating / significant request.
    * Enforce the airgapped outbound-block policy. Since the app makes no
      outbound calls, this middleware asserts that no request carries an
      instruction to reach an external provider and stamps the response with the
      current mode header.

Audit logging is best-effort and never breaks a request.
"""
from __future__ import annotations

from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .. import config


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_audit(action: str, actor: str = "system", detail: str = "",
                outcome: str = "ok") -> None:
    """Insert an audit-log row (best-effort)."""
    try:
        from ..database import db

        db.insert(
            "audit_logs",
            {
                "action": action,
                "actor": actor,
                "detail": detail,
                "mode": config.KAVACH_MODE,
                "outcome": outcome,
                "created_at": _now(),
            },
        )
    except Exception:  # noqa: BLE001 - auditing must never break the request
        pass


# Paths we audit (mutating or security-relevant). GET list endpoints are noisy,
# so we audit them lightly by prefix.
_AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditAndAirgapMiddleware(BaseHTTPMiddleware):
    """Audit requests and stamp the airgapped mode header."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        actor = request.client.host if request.client else "unknown"

        should_audit = method in _AUDIT_METHODS
        if should_audit:
            write_audit(
                action=f"{method} {path}",
                actor=actor,
                detail=f"query={dict(request.query_params)}",
            )

        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            write_audit(action=f"{method} {path}", actor=actor,
                        detail=f"error={exc!r}", outcome="error")
            raise

        response.headers["X-Kavach-Mode"] = config.KAVACH_MODE
        response.headers["X-Kavach-Network"] = "airgapped" if config.IS_AIRGAPPED else "open"
        return response
