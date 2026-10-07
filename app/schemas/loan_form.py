# app/schemas/loan_form.py
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


# ═════════════════════════════════════════════════════
# SEND FORM LINK
# ═════════════════════════════════════════════════════

class SendFormLinkResponse(BaseModel):
    success:      bool
    contact_id:   str
    contact_ref:  str
    email_sent:   bool
    form_url:     str
    expires_in:   str
    message:      str


# ═════════════════════════════════════════════════════
# TOKEN VALIDATION
# (GitHub Pages calls this on page load)
# ═════════════════════════════════════════════════════

class TokenValidateResponse(BaseModel):
    valid:      bool
    contact_id: Optional[str] = None
    name:       Optional[str] = None
    email:      Optional[str] = None
    phone:      Optional[str] = None
    loan_type:  Optional[str] = None
    amount:     Optional[int] = None
    reason:     Optional[str] = None  # error reason if invalid


# ═════════════════════════════════════════════════════
# FORM SUBMISSION
# (sent by GitHub Pages as multipart/form-data)
# ═════════════════════════════════════════════════════

class LoanFormSubmit(BaseModel):
    """
    Text fields only.
    File uploads are handled separately in the router
    as UploadFile parameters.
    """

    # Token (replaces contact_id — validated server side)
    token: str

    # ── Main Applicant — Personal ─────────────────────
    name:   Optional[str]      = None
    mobile: Optional[str]      = None
    email:  Optional[EmailStr] = None

    # ── Main Applicant — KYC ──────────────────────────
    aadhaar_number: Optional[str] = None
    pan_number:     Optional[str] = None

    # ── Employment type ───────────────────────────────
    # salaried | business
    employment_type: Optional[str] = None

    # ── Salaried income fields ────────────────────────
    monthly_income: Optional[int] = None

    # ── Business income fields ────────────────────────
    annual_turnover: Optional[int] = None

    # ── Loan details ──────────────────────────────────
    loan_type:   Optional[str] = None
    loan_amount: Optional[int] = None
    cibil_score: Optional[int] = None

    # ── Co-applicant ──────────────────────────────────
    has_co_applicant:            bool             = False
    co_applicant_name:           Optional[str]    = None
    co_applicant_mobile:         Optional[str]    = None
    co_applicant_email:          Optional[EmailStr] = None
    co_applicant_pan_number:     Optional[str]    = None
    co_applicant_aadhaar_number: Optional[str]    = None


# ═════════════════════════════════════════════════════
# SUBMIT RESPONSE
# ═════════════════════════════════════════════════════

class LoanFormSubmitResponse(BaseModel):
    success:       bool
    submission_id: uuid.UUID
    contact_id:    uuid.UUID
    message:       str
    submitted_at:  datetime


# ═════════════════════════════════════════════════════
# FORM STATUS
# (admin checks if customer has filled the form)
# ═════════════════════════════════════════════════════

class FormStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contact_id:    uuid.UUID
    contact_ref:   Optional[str]       = None
    contact_name:  str
    contact_email: Optional[str]       = None

    # pending | submitted | converted
    form_status:   str
    submitted_at:  Optional[datetime]  = None
    submission_id: Optional[uuid.UUID] = None

    # ── Document checklist ────────────────────────────
    has_pan:            bool = False
    has_aadhaar:        bool = False
    has_passport_photo: bool = False
    has_co_applicant:   bool = False

    # Salaried
    has_payslips:              bool = False
    has_salary_bank_statement: bool = False
    has_form_16:               bool = False

    # Business
    has_itr:              bool = False
    has_msme_certificate: bool = False
    has_labour_license:   bool = False
    has_gst_certificate:  bool = False
    has_gstr_filings:     bool = False


# ═════════════════════════════════════════════════════
# FULL SUBMISSION DETAIL
# (admin reviews before converting to lead)
# ═════════════════════════════════════════════════════

class LoanFormDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          uuid.UUID
    contact_id:  uuid.UUID
    form_status: str

    # Personal
    name:   Optional[str] = None
    mobile: Optional[str] = None
    email:  Optional[str] = None

    # KYC
    aadhaar_number:        Optional[str] = None
    pan_number:            Optional[str] = None
    aadhaar_document_path: Optional[str] = None
    pan_document_path:     Optional[str] = None
    passport_photo_path:   Optional[str] = None

    # Employment
    employment_type: Optional[str] = None

    # Salaried
    monthly_income:             Optional[int] = None
    payslip_paths:              Optional[str] = None
    salary_bank_statement_path: Optional[str] = None
    form_16_path:               Optional[str] = None

    # Business
    annual_turnover:       Optional[int] = None
    itr_paths:             Optional[str] = None
    msme_certificate_path: Optional[str] = None
    labour_license_path:   Optional[str] = None
    gst_certificate_path:  Optional[str] = None
    gstr_filing_paths:     Optional[str] = None

    # Loan
    loan_type:   Optional[str] = None
    loan_amount: Optional[int] = None
    cibil_score: Optional[int] = None

    # Co-applicant
    has_co_applicant:            bool           = False
    co_applicant_name:           Optional[str]  = None
    co_applicant_mobile:         Optional[str]  = None
    co_applicant_email:          Optional[str]  = None
    co_applicant_pan_number:     Optional[str]  = None
    co_applicant_aadhaar_number: Optional[str]  = None
    co_applicant_pan_path:       Optional[str]  = None
    co_applicant_aadhaar_path:   Optional[str]  = None

    submitted_at: Optional[datetime] = None
    created_at:   datetime
    updated_at:   datetime