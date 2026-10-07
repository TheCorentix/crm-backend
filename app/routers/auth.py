# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest
from app.services.auth_service import AuthService
import uuid
from datetime import datetime
from sqlalchemy import select

from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return access + refresh tokens."""
    tokens = await AuthService.login(db, payload.email, payload.password)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    """Exchange a valid refresh token for a new access token."""
    tokens = await AuthService.refresh_token(db, payload.refresh_token)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return tokens
@router.post("/reset-password/{token}")
async def reset_password_with_token(
    token: str,
    new_password: str,
    db: AsyncSession = Depends(get_db),
):

    # find reset token
    result = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token == token)
    )

    reset = result.scalar_one_or_none()

    if not reset:
        raise HTTPException(status_code=404, detail="Invalid reset token")

    if datetime.utcnow() > reset.expires_at:
        raise HTTPException(status_code=400, detail="Reset link expired")

    # ── ADD YOUR CODE HERE ─────────────────────────────

    user = await db.get(User, reset.user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password = AuthService.hash_password(new_password)

    await db.delete(reset)

    await db.commit()

    return {"message": "Password reset successful"}