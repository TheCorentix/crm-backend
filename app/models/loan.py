# app/models/loan.py
import uuid
from datetime import datetime
from sqlalchemy import String, BigInteger, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# ── BANK STAGES ───────────────────────────────────────
BANK_STAGES = [
    "logged_to_bank",
    "pending_assignment",
    "submitted_to_bank",
    "under_review",
    "documents_required",
    "docs_review_complete",
    "bank_processing",
    "sanctioned",
    "bank_approved",
    "partially_approved",
    "bank_rejected",
    "disbursement_initiated",
    "loan_disbursed",
    "loan_closed",
    "default",
    "deal_lost"
]


class Loan(Base):
    """
    Post-sales pipeline record.
    Created automatically when a Lead is sent to bank.
    Tracks bank interactions through to disbursement.
    """
    __tablename__ = "loans"

    # ── Primary key ───────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Human-readable ID ─────────────────────────────
    loan_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    # e.g. PS-2001 — auto-generated in service layer

    # ── Linked lead ───────────────────────────────────
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Applicant snapshot (denormalised for speed) ───
    contact_name: Mapped[str | None]  = mapped_column(String(100), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None]         = mapped_column(String(20),  nullable=True)
    pan_number: Mapped[str | None]    = mapped_column(String(20),  nullable=True)

    # ── Loan details ──────────────────────────────────
    loan_amount_requested: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    loan_amount_approved: Mapped[int | None]  = mapped_column(BigInteger, nullable=True)
    disbursed_amount: Mapped[int | None]      = mapped_column(BigInteger, nullable=True)
    credit_score: Mapped[int | None]          = mapped_column(Integer,    nullable=True)

    # ── Bank details ──────────────────────────────────
    bank_name: Mapped[str | None]        = mapped_column(String(100), nullable=True)
    bank_reference: Mapped[str | None]   = mapped_column(String(100), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text,        nullable=True)

    # ── Post-sales state ──────────────────────────────
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="logged_to_bank", index=True)
    # logged_to_bank → pending_assignment → submitted_to_bank → under_review
# → documents_required → docs_review_complete → bank_processing
# → sanctioned → bank_approved / partially_approved / bank_rejected
# → disbursement_initiated → loan_disbursed → loan_closed / default / deal_lost

    # ── Assignment ────────────────────────────────────
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── NEW: Bank admin who handles this loan ─────────
    # Only the banker whose id matches this field can see this loan
    banker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── NEW: Last mandatory comment from banker ───────
    last_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────
    created_at: Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    state_updated_at: Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now())
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────
    lead:     Mapped["Lead | None"] = relationship("Lead", back_populates="loan")
    assignee: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_loans")

    # ── NEW: Relationship to assigned banker ──────────
    banker:   Mapped["User | None"] = relationship("User", foreign_keys=[banker_id], backref="routed_loans")

    def __repr__(self) -> str:
        return f"<Loan {self.loan_id} [{self.stage}]>"