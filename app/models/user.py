# app/models/user.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    # ── Primary key ───────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Identity ──────────────────────────────────────
    name: Mapped[str]     = mapped_column(String(100), nullable=False)
    email: Mapped[str]    = mapped_column(String(150), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt hash

    # ── Role & status ─────────────────────────────────
    # super_admin | admin | pre_sales_admin | pre_sales_user | post_sales_admin | bank_admin
    role: Mapped[str]   = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # active | inactive

    # ── Bank info (only for bank_admin role) ──────────
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # e.g. "HDFC Bank", "SBI", "ICICI Bank" — null for all other roles

    employee_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # bank employee ID — required for bank_admin; max 50 chars

    branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # bank branch name — required for bank_admin

    manager_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # manager / branch email — optional for bank_admin

    manager_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # manager / branch phone — optional for bank_admin; E.164 or local format

    # ── Timestamps ────────────────────────────────────
    created_at: Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────
    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        "ActivityLog", back_populates="user", cascade="all, delete-orphan"
    )
    assigned_leads: Mapped[list["Lead"]] = relationship(
        "Lead", foreign_keys="Lead.assigned_to", back_populates="assignee"
    )
    assigned_loans: Mapped[list["Loan"]] = relationship(
        "Loan", foreign_keys="Loan.assigned_to", back_populates="assignee"
    )
    # Loans this banker is assigned to (bank_admin only)
    banker_loans: Mapped[list["Loan"]] = relationship(
        "Loan", foreign_keys="Loan.banker_id", back_populates="banker"
    )
    created_contacts: Mapped[list["Contact"]] = relationship(
        "Contact", foreign_keys="Contact.created_by", back_populates="creator"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role}]>"


class ActivityLog(Base):
    """Audit trail — every state change, login, or admin action."""
    __tablename__ = "activity_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[str]                 = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str | None]     = mapped_column(String(50),  nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user: Mapped["User | None"] = relationship("User", back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog {self.action} by {self.user_id}>"