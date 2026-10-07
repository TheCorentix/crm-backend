# app/routers/users.py
import uuid
from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import secrets
from sqlalchemy import select
from datetime import datetime, timedelta
from app.models.password_reset import PasswordResetToken
from app.services.email_service import EmailService

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.schemas.user import (
    UserCreate, BankAdminCreate, UserUpdate, UserResponse,
    UserListItem, UserStatusUpdate,
    PasswordReset, ActivityLogResponse, BankerOut,
)
from app.services.user_service import UserService

router = APIRouter(
    dependencies=[Depends(get_current_user)]   # all routes require login
)


# ── LIST — GET /users/ ────────────────────────────────
@router.get("/", response_model=List[UserListItem])
async def list_users(
    search:  Optional[str] = Query(None),
    role:    Optional[str] = Query(None),
    status:  Optional[str] = Query(None),
    page:    int           = Query(1, ge=1),
    limit:   int           = Query(50, ge=1, le=100),
    db:      AsyncSession  = Depends(get_db),
    current: CurrentUser   = Depends(require_roles(["super_admin"])),
):
    return await UserService.list_users(db, search, role, status, page, limit)


# ── CREATE REGULAR USER — POST /users/ ───────────────
# Accepts all roles EXCEPT bank_admin (blocked at schema level).
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin"])),
):
    existing = await UserService.get_by_email(db, str(payload.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    return await UserService.create_user(db, payload)


# ── CREATE BANK ADMIN — POST /users/bank-admin ───────
# Separate endpoint enforces bank-specific required fields
# (bank_name, employee_id, branch) and always sets role = bank_admin.
# Must be declared BEFORE /{user_id} routes to avoid path conflicts.
@router.post(
    "/bank-admin",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bank_admin(
    payload: BankAdminCreate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin"])),
):
    existing = await UserService.get_by_email(db, str(payload.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    return await UserService.create_bank_admin(db, payload)


# ── LIST BANKERS — GET /users/bankers ─────────────────
# Returns active bank_admin users for the assign-to-banker dropdown.
# Must be declared BEFORE /{user_id} to avoid path conflict.
@router.get("/bankers", response_model=List[BankerOut])
async def list_bankers(
    bank_name: Optional[str] = Query(None, description="Filter by bank name"),
    db:        AsyncSession  = Depends(get_db),
    current:   CurrentUser   = Depends(
        require_roles(["super_admin", "admin", "pre_sales_admin"])
    ),
):
    return await UserService.list_bankers(db, bank_name)


# ── GET ONE — GET /users/{user_id} ────────────────────
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin"])),
):
    user = await UserService.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── UPDATE — PUT /users/{user_id} ─────────────────────
# role → bank_admin is blocked at schema level (UserUpdate model_validator)
# and also guarded in the service layer.
@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin"])),
):
    # Check email uniqueness if email is being changed
    if payload.email:
        existing = await UserService.get_by_email(db, str(payload.email))
        if existing and existing.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another account",
            )
    user = await UserService.update_user(db, user_id, payload)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── DELETE — DELETE /users/{user_id} ──────────────────
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin"])),
):
    deleted = await UserService.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


# ── STATUS — PATCH /users/{user_id}/status ───────────
@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin"])),
):
    user = await UserService.update_status(db, user_id, payload.status)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── SEND RESET LINK — POST /users/{user_id}/send-reset-link ─────────
@router.post("/{user_id}/send-reset-link")
async def send_reset_link(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(["super_admin"])),
):

    # get user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # generate token
    token = secrets.token_urlsafe(32)

    reset = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(minutes=60),
    )

    db.add(reset)
    await db.commit()

    reset_url = f"http://localhost:5173/reset-password/{token}"

    EmailService.send_password_reset_link(
        to_email=user.email,
        to_name=user.name,
        reset_url=reset_url,
    )

    return {"message": f"Reset link sent to {user.email}"}

# ── PASSWORD RESET — PATCH /users/{user_id}/password ─
@router.patch("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: uuid.UUID,
    payload: PasswordReset,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin"])),
):
    done = await UserService.reset_password(db, user_id, payload.new_password)
    if not done:
        raise HTTPException(status_code=404, detail="User not found")


# ── ACTIVITY — GET /users/{user_id}/activity ─────────
@router.get("/{user_id}/activity", response_model=List[ActivityLogResponse])
async def get_activity(
    user_id: uuid.UUID,
    limit:   int          = Query(20, ge=1, le=100),
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin"])),
):
    return await UserService.get_activity(db, user_id, limit)