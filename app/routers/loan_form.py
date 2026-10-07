# app/routers/loan_form.py
import uuid
from typing import Optional, List

from fastapi import (
    APIRouter, Depends, HTTPException,
    status, UploadFile, File, Form,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database        import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth    import CurrentUser
from app.schemas.loan_form import (
    SendFormLinkResponse,
    TokenValidateResponse,
    LoanFormSubmit,
    LoanFormSubmitResponse,
    FormStatusResponse,
    LoanFormDetail,
)
from app.services.loan_form_service import LoanFormService

router = APIRouter()

ADMIN_ROLES = ["super_admin", "admin", "pre_sales_admin"]


# ═════════════════════════════════════════════════════
# 1. SEND FORM LINK
#    POST /api/forms/send-loan-form/{contact_id}
#    Admin sends the secure link to customer email
# ═════════════════════════════════════════════════════

@router.post(
    "/send-loan-form/{contact_id}",
    response_model=SendFormLinkResponse,
    dependencies=[Depends(get_current_user)],
    summary="Generate secure link and send to customer email",
)
async def send_loan_form(
    contact_id: uuid.UUID,
    db:         AsyncSession = Depends(get_db),
    current:    CurrentUser  = Depends(require_roles(ADMIN_ROLES)),
):
    """
    Generates a signed JWT link and emails it to the contact.

    Link format:
    https://maneendrakummari.github.io/Loan/?token=<signed_jwt>

    Token expires in 24 hours (configurable in .env).
    """
    try:
        return await LoanFormService.send_form_link(
            db         = db,
            contact_id = contact_id,
            sent_by    = current.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═════════════════════════════════════════════════════
# 2. VALIDATE TOKEN
#    GET /api/forms/validate-token?token=eyJ...
#    GitHub Pages calls this on page load
#    NO auth required — public endpoint
# ═════════════════════════════════════════════════════

@router.get(
    "/validate-token",
    response_model=TokenValidateResponse,
    summary="Validate token and return contact details to pre-fill form",
)
async def validate_token(
    token: str,
    db:    AsyncSession = Depends(get_db),
):
    """
    Called by GitHub Pages frontend when customer opens the link.

    If valid — returns contact details to pre-fill the form.
    If expired or invalid — returns valid: false with reason.
    """
    result = await LoanFormService.validate_token(db, token)

    if not result["valid"]:
        # Return 200 with valid:false so frontend can show
        # a proper "link expired" message instead of error page
        return TokenValidateResponse(
            valid  = False,
            reason = result["reason"],
        )

    return TokenValidateResponse(
        valid      = True,
        contact_id = result["contact_id"],
        name       = result["name"],
        email      = result["email"],
        phone      = result["phone"],
        loan_type  = result["loan_type"],
        amount     = result["amount"],
        reason     = None,
    )


# ═════════════════════════════════════════════════════
# 3. SUBMIT LOAN APPLICATION
#    POST /api/forms/loan-details
#    GitHub Pages frontend submits this
#    NO auth required — public endpoint
#    Accepts multipart/form-data
# ═════════════════════════════════════════════════════

@router.post(
    "/loan-details",
    response_model=LoanFormSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit loan application form with documents",
)
async def submit_loan_form(
    # ── Token ─────────────────────────────────────────
    token: str = Form(...),

    # ── Main applicant — personal ─────────────────────
    name:   Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    email:  Optional[str] = Form(None),

    # ── Main applicant — KYC ──────────────────────────
    aadhaar_number: Optional[str] = Form(None),
    pan_number:     Optional[str] = Form(None),

    # ── Employment ────────────────────────────────────
    employment_type: Optional[str] = Form(None),  # salaried | business

    # ── Salaried income ───────────────────────────────
    monthly_income: Optional[int] = Form(None),

    # ── Business income ───────────────────────────────
    annual_turnover: Optional[int] = Form(None),

    # ── Loan ──────────────────────────────────────────
    loan_type:   Optional[str] = Form(None),
    loan_amount: Optional[int] = Form(None),
    cibil_score: Optional[int] = Form(None),

    # ── Co-applicant ──────────────────────────────────
    has_co_applicant:            bool             = Form(False),
    co_applicant_name:           Optional[str]    = Form(None),
    co_applicant_mobile:         Optional[str]    = Form(None),
    co_applicant_email:          Optional[str]    = Form(None),
    co_applicant_pan_number:     Optional[str]    = Form(None),
    co_applicant_aadhaar_number: Optional[str]    = Form(None),

    # ── Main applicant documents ──────────────────────
    passport_photo:        Optional[UploadFile]       = File(None),
    aadhaar_document:      Optional[UploadFile]       = File(None),
    pan_document:          Optional[UploadFile]       = File(None),

    # ── Salaried documents ────────────────────────────
    payslips:              Optional[List[UploadFile]] = File(None),
    salary_bank_statement: Optional[UploadFile]       = File(None),
    form_16:               Optional[UploadFile]       = File(None),

    # ── Business documents ────────────────────────────
    itr_documents:         Optional[List[UploadFile]] = File(None),
    msme_certificate:      Optional[UploadFile]       = File(None),
    labour_license:        Optional[UploadFile]       = File(None),
    gst_certificate:       Optional[UploadFile]       = File(None),
    gstr_filings:          Optional[List[UploadFile]] = File(None),

    # ── Co-applicant documents ────────────────────────
    co_applicant_pan:    Optional[UploadFile] = File(None),
    co_applicant_aadhaar: Optional[UploadFile] = File(None),

    # ── DB ────────────────────────────────────────────
    db: AsyncSession = Depends(get_db),
):
    """
    Receives the full loan application from GitHub Pages.
    Token is validated server side to extract contact_id.
    All documents are saved to uploads/loan_documents/<contact_id>/
    """
    payload = LoanFormSubmit(
        token                      = token,
        name                       = name,
        mobile                     = mobile,
        email                      = email,
        aadhaar_number             = aadhaar_number,
        pan_number                 = pan_number,
        employment_type            = employment_type,
        monthly_income             = monthly_income,
        annual_turnover            = annual_turnover,
        loan_type                  = loan_type,
        loan_amount                = loan_amount,
        cibil_score                = cibil_score,
        has_co_applicant           = has_co_applicant,
        co_applicant_name          = co_applicant_name,
        co_applicant_mobile        = co_applicant_mobile,
        co_applicant_email         = co_applicant_email,
        co_applicant_pan_number    = co_applicant_pan_number,
        co_applicant_aadhaar_number = co_applicant_aadhaar_number,
    )

    try:
        submission = await LoanFormService.submit_form(
            db                     = db,
            payload                = payload,
            passport_photo         = passport_photo,
            aadhaar_document       = aadhaar_document,
            pan_document           = pan_document,
            payslips               = payslips               or [],
            salary_bank_statement  = salary_bank_statement,
            form_16                = form_16,
            itr_documents          = itr_documents          or [],
            msme_certificate       = msme_certificate,
            labour_license         = labour_license,
            gst_certificate        = gst_certificate,
            gstr_filings           = gstr_filings           or [],
            co_applicant_pan       = co_applicant_pan,
            co_applicant_aadhaar   = co_applicant_aadhaar,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return LoanFormSubmitResponse(
        success       = True,
        submission_id = submission.id,
        contact_id    = submission.contact_id,
        message       = "Loan application submitted successfully",
        submitted_at  = submission.submitted_at,
    )


# ═════════════════════════════════════════════════════
# 4. CHECK FORM STATUS
#    GET /api/forms/status/{contact_id}
#    Admin checks if customer has filled the form
# ═════════════════════════════════════════════════════

@router.get(
    "/status/{contact_id}",
    response_model=FormStatusResponse,
    dependencies=[Depends(get_current_user)],
    summary="Check if contact has submitted the loan form",
)
async def get_form_status(
    contact_id: uuid.UUID,
    db:         AsyncSession = Depends(get_db),
    current:    CurrentUser  = Depends(
        require_roles(ADMIN_ROLES + ["pre_sales_user"])
    ),
):
    try:
        return await LoanFormService.get_form_status(db, contact_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ═════════════════════════════════════════════════════
# 5. GET FULL SUBMISSION DETAIL
#    GET /api/forms/submission/{contact_id}
#    Admin reviews all data before converting to lead
# ═════════════════════════════════════════════════════

@router.get(
    "/submission/{contact_id}",
    response_model=LoanFormDetail,
    dependencies=[Depends(get_current_user)],
    summary="Get full loan form submission details for admin review",
)
async def get_submission_detail(
    contact_id: uuid.UUID,
    db:         AsyncSession = Depends(get_db),
    current:    CurrentUser  = Depends(require_roles(ADMIN_ROLES)),
):
    """
    Returns all submitted data including document paths.
    Admin reviews this before clicking Confirm Convert to Lead.
    """
    submission = await LoanFormService.get_submission_detail(db, contact_id)
    if not submission:
        raise HTTPException(
            status_code=404,
            detail="No form submission found for this contact"
        )
    return submission