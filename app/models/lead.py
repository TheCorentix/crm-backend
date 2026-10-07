# app/models/lead.py
import uuid
from datetime import datetime
from sqlalchemy import String, BigInteger, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Lead(Base):
    """
    Qualified prospect in the pre-sales pipeline.
    Created from a Contact or directly by pre-sales admin.
    Promoted to Loan when sent to bank.
    """
    __tablename__ = "leads"

    # ── Primary key ───────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Human-readable ID ─────────────────────────────
    loan_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    # e.g. LD-1001 — auto-generated in service layer

    # ── Linked contact (optional) ─────────────────────
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Personal details ──────────────────────────────
    name: Mapped[str]              = mapped_column(String(100), nullable=False)
    email: Mapped[str | None]      = mapped_column(String(150), nullable=True, index=True)
    phone: Mapped[str | None]      = mapped_column(String(20),  nullable=True)
    pan_number: Mapped[str | None] = mapped_column(String(20),  nullable=True)
    city: Mapped[str | None]       = mapped_column(String(100), nullable=True)

    # ── Loan details ──────────────────────────────────
    loan_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Home Loan | Personal Loan | Business Loan | Vehicle Loan | Loan Against Property
    amount: Mapped[int | None]    = mapped_column(BigInteger,  nullable=True)  # requested in ₹

    # ── Pipeline stage ────────────────────────────────
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="New Lead", index=True)
    # New Lead | In Progress | Under Review | Documents Pending | Qualified | Not Qualified

    # ── Source ────────────────────────────────────────
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Financial profile ─────────────────────────────
    cibil_score: Mapped[int | None]      = mapped_column(Integer,    nullable=True)
    employment_type: Mapped[str | None]  = mapped_column(String(50), nullable=True)
    # Salaried | Self-employed
    monthly_income: Mapped[int | None]   = mapped_column(BigInteger, nullable=True)

    # ── Assignment ────────────────────────────────────
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Relationships ─────────────────────────────────
    contact:  Mapped["Contact | None"] = relationship("Contact", back_populates="lead")
    assignee: Mapped["User | None"]    = relationship("User",    foreign_keys=[assigned_to], back_populates="assigned_leads")
    loan:     Mapped["Loan | None"]    = relationship("Loan",    back_populates="lead", uselist=False)
    # one lead becomes one loan when sent to bank

    def __repr__(self) -> str:
        return f"<Lead {self.loan_id} {self.name} [{self.stage}]>"