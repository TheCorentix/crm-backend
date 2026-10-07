# app/services/auth_service.py

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.auth import TokenResponse, UserInfo


# ── Password hashing ──────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# In-memory refresh token blacklist
# (replace with Redis in production)
_blacklisted_tokens: set[str] = set()


class AuthService:

    # ── Helpers ───────────────────────────────────────

    @staticmethod
    def hash_password(plain: str) -> str:
        return pwd_context.hash(plain)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    @staticmethod
    def _create_token(data: dict, expires_delta: timedelta) -> str:
        payload = data.copy()
        payload["exp"] = datetime.now(timezone.utc) + expires_delta

        return jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

    @staticmethod
    def create_access_token(user: User) -> str:
        return AuthService._create_token(
            {
                "sub": str(user.id),
                "role": user.role,
                "name": user.name,
            },
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    @staticmethod
    def create_refresh_token(user: User) -> str:
        return AuthService._create_token(
            {
                "sub": str(user.id),
                "type": "refresh",
            },
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        try:
            return jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except JWTError:
            return None


    # ── Core auth methods ─────────────────────────────

    @staticmethod
    async def get_user_by_email(
        db: AsyncSession,
        email: str
    ) -> Optional[User]:

        result = await db.execute(
            select(User).where(User.email == email)
        )

        return result.scalar_one_or_none()


    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> Optional[User]:

        result = await db.execute(
            select(User).where(User.id == user_id)
        )

        return result.scalar_one_or_none()


    # ── LOGIN ─────────────────────────────────────────

    @staticmethod
    async def login(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> Optional[TokenResponse]:

        # 1. Find user
        user = await AuthService.get_user_by_email(db, email)

        if not user:
            return None

        # 2. Verify password
        if not AuthService.verify_password(password, user.password):
            return None

        # 3. Check account status
        if user.status != "active":
            return None

        # 4. Update last login
        user.last_login = datetime.now(timezone.utc)
        await db.commit()

        # 5. Generate tokens
        access_token = AuthService.create_access_token(user)
        refresh_token = AuthService.create_refresh_token(user)

        # 6. Return response
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserInfo(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role
            )
        )


    # ── REFRESH TOKEN ─────────────────────────────────

    @staticmethod
    async def refresh_token(
        db: AsyncSession,
        refresh_token: str,
    ) -> Optional[TokenResponse]:

        # 1. Check blacklist
        if refresh_token in _blacklisted_tokens:
            return None

        # 2. Decode token
        payload = AuthService.decode_token(refresh_token)

        if not payload:
            return None

        # 3. Verify token type
        if payload.get("type") != "refresh":
            return None

        # 4. Get user
        user_id = uuid.UUID(payload["sub"])

        user = await AuthService.get_user_by_id(db, user_id)

        if not user or user.status != "active":
            return None

        # 5. Issue new tokens
        new_access_token = AuthService.create_access_token(user)
        new_refresh_token = AuthService.create_refresh_token(user)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            user=UserInfo(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role
            )
        )


    # ── LOGOUT ────────────────────────────────────────

    @staticmethod
    async def logout(
        db: AsyncSession,
        refresh_token: str
    ) -> None:
        """Blacklist the refresh token so it cannot be reused."""
        _blacklisted_tokens.add(refresh_token)