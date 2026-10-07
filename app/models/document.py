# app/models/document.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, func, LargeBinary, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class DocumentRequest(Base):
    """
    Tracks a document upload request sent to a customer.
    Created when pre-sales clicks 'Send Upload Link'.
    Token expires after 48 hours.
    """
    __tablename__ = "document_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Linked loan ───────────────────────────────────
    loan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Secure upload token ───────────────────────────
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )

    # ── Customer details (snapshot) ───────────────────
    customer_email: Mapped[str]       = mapped_column(String(150), nullable=False)
    customer_name:  Mapped[str]       = mapped_column(String(100), nullable=False)

    # ── Banker's note shown to customer ───────────────
    banker_note: Mapped[str | None]   = mapped_column(Text, nullable=True)
    # ── Requested document info ───────────────────────
    document_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    status: Mapped[str] = mapped_column(
    String(30),
    default="requested",
    nullable=False
    )
    uploaded_doc_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    nullable=True
)

    uploaded_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True
)

    # ── Status ────────────────────────────────────────
    is_used:    Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    # True after customer uploads docs

    expires_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime]      = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    used_at: Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Who sent the link ─────────────────────────────
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────
    loan:      Mapped["Loan"]              = relationship("Loan",     foreign_keys=[loan_id])
    documents: Mapped[list["LoanDocument"]] = relationship("LoanDocument", back_populates="request", cascade="all, delete-orphan")
    sender:    Mapped["User | None"]       = relationship("User",     foreign_keys=[sent_by])

    def __repr__(self) -> str:
        return f"<DocumentRequest loan={self.loan_id} used={self.is_used}>"


class LoanDocument(Base):
    """
    A single file uploaded by the customer against a DocumentRequest.
    File content stored as bytes in PostgreSQL.
    """
    __tablename__ = "loan_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Linked request ────────────────────────────────
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Linked loan (denormalised for easy query) ─────
    loan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── File metadata ─────────────────────────────────
    filename:     Mapped[str]         = mapped_column(String(255), nullable=False)
    content_type: Mapped[str]         = mapped_column(String(100), nullable=False)
    # application/pdf | image/jpeg | image/png
    file_size:    Mapped[int]         = mapped_column(Integer, nullable=False)
    # bytes

    # ── File content stored in DB ─────────────────────
    file_data: Mapped[bytes]          = mapped_column(LargeBinary, nullable=False)

    uploaded_at: Mapped[datetime]     = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────
    request: Mapped["DocumentRequest"] = relationship("DocumentRequest", back_populates="documents")

    def __repr__(self) -> str:
        return f"<LoanDocument {self.filename} [{self.content_type}]>"