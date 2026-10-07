# app/middleware/auth.py
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import CurrentUser
from app.services.auth_service import AuthService

# ── Bearer token extractor ────────────────────────────
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db:          AsyncSession                 = Depends(get_db),
) -> CurrentUser:
    """
    Extracts and validates the JWT from the Authorization header.
    Injects CurrentUser into any route that depends on this function.

    Usage in router:
        current: CurrentUser = Depends(get_current_user)
    """
    token = credentials.credentials

    # 1. Decode the token
    payload = AuthService.decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Ensure it is an access token (not a refresh token)
    if payload.get("type") == "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cannot use refresh token as access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Extract user info from payload
    try:
        user_id = uuid.UUID(payload["sub"])
        role    = payload["role"]
        name    = payload["name"]
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Verify user still exists and is active in DB
    user = await AuthService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    return CurrentUser(id=user_id, name=name, role=role)


async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> CurrentUser | None:
    """
    Same as get_current_user but returns None instead of raising
    for public routes that optionally accept auth.
    """
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None