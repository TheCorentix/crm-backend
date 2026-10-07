# app/services/user_service.py
import uuid
from typing import Optional, List

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, ActivityLog
from app.schemas.user import UserCreate, UserUpdate, BankAdminCreate
from app.services.auth_service import AuthService


class UserService:

    # ── List with filters ─────────────────────────────
    @staticmethod
    async def list_users(
        db:     AsyncSession,
        search: Optional[str],
        role:   Optional[str],
        status: Optional[str],
        page:   int,
        limit:  int,
    ) -> List[User]:
        q = select(User)

        if search:
            term = f"%{search.lower()}%"
            q = q.where(
                or_(
                    func.lower(User.name).like(term),
                    func.lower(User.email).like(term),
                )
            )
        if role:
            q = q.where(User.role == role)
        if status:
            q = q.where(User.status == status)

        q = q.order_by(User.created_at.desc())
        q = q.offset((page - 1) * limit).limit(limit)

        result = await db.execute(q)
        return result.scalars().all()

    # ── Get single ────────────────────────────────────
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    # ── Create regular user (non bank_admin) ──────────
    @staticmethod
    async def create_user(db: AsyncSession, payload: UserCreate) -> User:
        # Schema's model_validator already blocks bank_admin role —
        # this guard is a defence-in-depth safety net.
        if payload.role == "bank_admin":
            raise ValueError(
                "Use create_bank_admin() to create bank admin users."
            )

        user = User(
            name     = payload.name,
            email    = payload.email,
            password = AuthService.hash_password(payload.password),
            role     = payload.role,
            status   = "active",
        )
        db.add(user)
        await db.flush()
        await UserService._log(
            db, user.id,
            f"User account created: {user.email} [{user.role}]",
            "user", user.id,
        )
        await db.commit()
        await db.refresh(user)
        return user

    # ── Create bank admin — POST /users/bank-admin ────
    @staticmethod
    async def create_bank_admin(db: AsyncSession, payload: BankAdminCreate) -> User:
        user = User(
            name          = payload.name,
            email         = payload.email,
            password      = AuthService.hash_password(payload.password),
            role          = "bank_admin",           # always hardcoded here
            status        = "active",
            bank_name     = payload.bank_name,
            employee_id   = payload.employee_id,
            branch        = payload.branch,
            manager_email = str(payload.manager_email) if payload.manager_email else None,
            manager_phone = payload.manager_phone,
        )
        db.add(user)
        await db.flush()
        await UserService._log(
            db, user.id,
            f"Bank admin created: {user.email} [{user.bank_name}]",
            "user", user.id,
        )
        await db.commit()
        await db.refresh(user)
        return user

    # ── Update ────────────────────────────────────────
    @staticmethod
    async def update_user(
        db:      AsyncSession,
        user_id: uuid.UUID,
        payload: UserUpdate,
    ) -> Optional[User]:
        user = await UserService.get_by_id(db, user_id)
        if not user:
            return None

        # Schema's model_validator already blocks role → bank_admin,
        # but guard here too so the service is safe when called directly.
        if payload.role == "bank_admin":
            raise ValueError(
                "Cannot change role to bank_admin via update_user(). "
                "Use create_bank_admin() instead."
            )

        if payload.name          is not None: user.name          = payload.name
        if payload.email         is not None: user.email         = payload.email
        if payload.role          is not None: user.role          = payload.role
        if payload.bank_name     is not None: user.bank_name     = payload.bank_name
        if payload.employee_id   is not None: user.employee_id   = payload.employee_id
        if payload.branch        is not None: user.branch        = payload.branch
        if payload.manager_email is not None: user.manager_email = str(payload.manager_email)
        if payload.manager_phone is not None: user.manager_phone = payload.manager_phone

        await UserService._log(
            db, user_id,
            f"User profile updated: {user.email}",
            "user", user_id,
        )
        await db.commit()
        await db.refresh(user)
        return user

    # ── Delete ────────────────────────────────────────
    @staticmethod
    async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> bool:
        user = await UserService.get_by_id(db, user_id)
        if not user:
            return False
        await db.delete(user)
        await db.commit()
        return True

    # ── Status toggle ─────────────────────────────────
    @staticmethod
    async def update_status(
        db:      AsyncSession,
        user_id: uuid.UUID,
        status:  str,
    ) -> Optional[User]:
        user = await UserService.get_by_id(db, user_id)
        if not user:
            return None

        user.status = status
        action = "activated" if status == "active" else "deactivated"
        await UserService._log(
            db, user_id,
            f"User account {action}: {user.email}",
            "user", user_id,
        )
        await db.commit()
        await db.refresh(user)
        return user

    # ── Password reset ────────────────────────────────
    @staticmethod
    async def reset_password(
        db:           AsyncSession,
        user_id:      uuid.UUID,
        new_password: str,
    ) -> bool:
        user = await UserService.get_by_id(db, user_id)
        if not user:
            return False

        user.password = AuthService.hash_password(new_password)
        await UserService._log(
            db, user_id,
            f"Password reset for: {user.email}",
            "user", user_id,
        )
        await db.commit()
        return True

    # ── Activity log ──────────────────────────────────
    @staticmethod
    async def get_activity(
        db:      AsyncSession,
        user_id: uuid.UUID,
        limit:   int = 20,
    ) -> List[ActivityLog]:
        result = await db.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # ── List bankers (for assign-to-banker dropdown) ──
    @staticmethod
    async def list_bankers(
        db:        AsyncSession,
        bank_name: Optional[str] = None,
    ) -> List[User]:
        q = select(User).where(
            User.role   == "bank_admin",
            User.status == "active",
        )
        if bank_name:
            q = q.where(User.bank_name == bank_name)
        q = q.order_by(User.name)
        result = await db.execute(q)
        return result.scalars().all()

    # ── Internal log helper ───────────────────────────
    @staticmethod
    async def _log(
        db:          AsyncSession,
        user_id:     uuid.UUID,
        action:      str,
        entity_type: str,
        entity_id:   uuid.UUID,
    ) -> None:
        db.add(ActivityLog(
            user_id     = user_id,
            action      = action,
            entity_type = entity_type,
            entity_id   = entity_id,
        ))