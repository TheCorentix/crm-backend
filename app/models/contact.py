# app/models/contact.py
import uuid
from datetime import datetime
from sqlalchemy import String, BigInteger, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Contact(Base):
    """
    Raw enquiries — walk-ins, website forms, referrals.
    First point of capture before a Lead is created.
    """
    __tablename__ = "contacts"

    # ── Primary key ───────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Human-readable ID ─────────────────────────────
    contact_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    # e.g. CNT-001 — auto-generated in service layer

    # ── Personal details ──────────────────────────────
    name: Mapped[str]         = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20),  nullable=True)
    city: Mapped[str | None]  = mapped_column(String(100), nullable=True)

    # ── Enquiry details ───────────────────────────────
    # source: website_form | referral | walk_in | social_media
    source: Mapped[str | None]    = mapped_column(String(50),  nullable=True)
    # status: New | Contacted | Qualified | Unqualified
    status: Mapped[str]           = mapped_column(String(30),  nullable=False, default="New")
    loan_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[int | None]    = mapped_column(BigInteger,  nullable=True)  # in rupees
    notes: Mapped[str | None]     = mapped_column(Text,        nullable=True)

    # ── Timestamps ────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Who created it ────────────────────────────────
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────
    creator: Mapped["User | None"] = relationship("User",    foreign_keys=[created_by], back_populates="created_contacts")
    lead:    Mapped["Lead | None"] = relationship("Lead",    back_populates="contact",  uselist=False)
    # one contact can become one lead

    def __repr__(self) -> str:
        return f"<Contact {self.name} [{self.status}]>"