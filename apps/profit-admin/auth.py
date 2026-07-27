"""
Auth dependency stub for Phase 2 Shopify Admin embed.

v1 (localhost): no authentication — do not expose this server publicly.
Phase 2: validate Shopify session tokens (App Bridge) on /api/* routes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request


async def require_local_or_session(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """
    v1: always allow.

    Phase 2 sketch:
      - Prefer Authorization: Bearer <session_token> from App Bridge
      - Verify JWT (iss, aud=api_key, exp) via Shopify session-token docs
      - Raise 401 if missing/invalid when EMBEDDED_MODE=1
    """
    _ = request, authorization
    embedded = False  # flip when hosting behind Shopify Admin
    if embedded and not authorization:
        raise HTTPException(status_code=401, detail="Session token required")
    return {"mode": "local", "shop": None}


AuthDep = Annotated[dict, Depends(require_local_or_session)]
