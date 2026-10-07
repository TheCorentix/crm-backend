# app/schemas/auth.py
import uuid
from pydantic import BaseModel, EmailStr


# ── LOGIN REQUEST ─────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── USER INFO (returned after login) ──────────────────
class UserInfo(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: str


# ── TOKEN RESPONSE ────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfo


# ── REFRESH REQUEST ───────────────────────────────────
class RefreshRequest(BaseModel):
    refresh_token: str


# ── TOKEN PAYLOAD (inside JWT) ────────────────────────
class TokenPayload(BaseModel):
    sub: str    # user UUID
    role: str
    name: str
    exp: int


# ── CURRENT USER (injected by auth middleware) ────────
class CurrentUser(BaseModel):
    id: uuid.UUID
    name: str
    role: str