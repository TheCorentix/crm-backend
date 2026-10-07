# app/models/loan_form.py
import uuid
from datetime import datetime
from sqlalchemy import String, BigInteger, Text, DateTime, ForeignKey, func, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LoanFormSubmission(Base):
    """
    Stores loan application form data submitted by the customer
    via the GitHub Pages form.
    Linked 1-to-1 with a Contact.
    """
    __tablename__ = "loan_form_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Linked contact ────────────────────────────────
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # ═════════════════════════════════════════════════
    # MAIN APPLICANT — PERSONAL DETAILS
    # ═════════════════════════════════════════════════

    name:   Mapped[str | None] = mapped_column(String(100), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20),  nullable=True)
    email:  Mapped[str | None] = mapped_column(String(150), nullable=True)

    # ── KYC Documents ─────────────────────────────────
    aadhaar_number:       Mapped[str | None] = mapped_column(String(20), nullable=True)
    pan_number:           Mapped[str | None] = mapped_column(String(20), nullable=True)
    aadhaar_document_path: Mapped[str | None] = mapped_column(Text, nullable=True)  # uploaded file path
    pan_document_path:     Mapped[str | None] = mapped_column(Text, nullable=True)  # uploaded file path

    # ── Passport Size Photo ───────────────────────────
    passport_photo_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Employment Type ───────────────────────────────
    # salaried | business
    employment_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ═════════════════════════════════════════════════
    # MAIN APPLICANT — SALARIED INCOME DETAILS
    # (filled only if employment_type = 'salaried')
    # ═════════════════════════════════════════════════

    monthly_income: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Latest 6 months payslips — comma-separated file paths
    payslip_paths: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Latest 1 year salary account bank statement
    salary_bank_statement_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Latest Form 16
    form_16_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ═════════════════════════════════════════════════
    # MAIN APPLICANT — BUSINESS INCOME DETAILS
    # (filled only if employment_type = 'business')
    # ═════════════════════════════════════════════════

    annual_turnover: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Latest 2 years computational ITRs — comma-separated file paths
    itr_paths: Mapped[str | None] = mapped_column(Text, nullable=True)

    # MSME Certificate
    msme_certificate_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Labour License
    labour_license_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # GST Certificate
    gst_certificate_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Latest 1 year GSTR filing statement — comma-separated file paths
    gstr_filing_paths: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ═════════════════════════════════════════════════
    # LOAN DETAILS
    # ═════════════════════════════════════════════════

    loan_type:   Mapped[str | None] = mapped_column(String(100), nullable=True)
    loan_amount: Mapped[int | None] = mapped_column(BigInteger,  nullable=True)
    cibil_score: Mapped[int | None] = mapped_column(BigInteger,  nullable=True)

    # ═════════════════════════════════════════════════
    # CO-APPLICANT DETAILS
    # ═════════════════════════════════════════════════

    has_co_applicant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    co_applicant_name:   Mapped[str | None] = mapped_column(String(100), nullable=True)
    co_applicant_mobile: Mapped[str | None] = mapped_column(String(20),  nullable=True)
    co_applicant_email:  Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Co-applicant KYC
    co_applicant_pan_number:    Mapped[str | None] = mapped_column(String(20), nullable=True)
    co_applicant_aadhaar_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    co_applicant_pan_path:      Mapped[str | None] = mapped_column(Text, nullable=True)
    co_applicant_aadhaar_path:  Mapped[str | None] = mapped_column(Text, nullable=True)

    # ═════════════════════════════════════════════════
    # FORM STATUS & TIMESTAMPS
    # ═════════════════════════════════════════════════

    # pending | submitted | converted
    form_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationship ──────────────────────────────────
    contact: Mapped["Contact"] = relationship(
        "Contact", foreign_keys=[contact_id]
    )

    def __repr__(self) -> str:
        return f"<LoanFormSubmission contact={self.contact_id} [{self.form_status}]>"