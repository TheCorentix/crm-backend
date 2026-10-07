# app/services/loan_form_service.py
import uuid
import os
import shutil
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from app.models.contact   import Contact
from app.models.loan_form import LoanFormSubmission
from app.schemas.loan_form import LoanFormSubmit, FormStatusResponse
from app.services.form_token_service import FormTokenService
from app.services.email_service      import EmailService
from app.config import settings

UPLOAD_DIR = "uploads/loan_documents"


class LoanFormService:

    # ═════════════════════════════════════════════════
    # HELPERS
    # ═════════════════════════════════════════════════

    @staticmethod
    def _upload_dir(contact_id: uuid.UUID) -> str:
        path = os.path.join(UPLOAD_DIR, str(contact_id))
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    async def _save_file(
        file:       UploadFile,
        contact_id: uuid.UUID,
        label:      str,
    ) -> str:
        upload_dir = LoanFormService._upload_dir(contact_id)
        ext        = os.path.splitext(file.filename or "")[1] or ".bin"
        filename   = f"{label}_{uuid.uuid4().hex[:8]}{ext}"
        filepath   = os.path.join(upload_dir, filename)

        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)

        return filepath

    @staticmethod
    async def _save_multiple_files(
        files:      List[UploadFile],
        contact_id: uuid.UUID,
        label:      str,
    ) -> str:
        paths = []
        for i, file in enumerate(files):
            path = await LoanFormService._save_file(
                file, contact_id, f"{label}_{i + 1}"
            )
            paths.append(path)
        return ",".join(paths)

    # ═════════════════════════════════════════════════
    # 1. SEND FORM LINK
    # ═════════════════════════════════════════════════

    @staticmethod
    async def send_form_link(
        db:         AsyncSession,
        contact_id: uuid.UUID,
        sent_by:    uuid.UUID,
    ) -> dict:
        result  = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )
        contact = result.scalar_one_or_none()

        if not contact:
            raise ValueError("Contact not found")
        if not contact.email:
            raise ValueError("Contact has no email address on record")

        # Generate signed URL
        form_url = FormTokenService.build_form_url(contact_id)

        # Send email — ✅ changed to FORM_LINK_EXPIRE_MINUTES
        sent = EmailService.send_loan_form_link(
            to_email       = contact.email,
            to_name        = contact.name,
            form_url       = form_url,
            contact_ref    = contact.contact_id or str(contact_id),
            expire_minutes = settings.FORM_LINK_EXPIRE_MINUTES,
        )

        # Update contact status
        contact.status     = "Contacted"
        contact.updated_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "success":     True,
            "contact_id":  str(contact_id),
            "contact_ref": contact.contact_id or str(contact_id),
            "email_sent":  sent,
            "form_url":    form_url,
            # ✅ changed to FORM_LINK_EXPIRE_MINUTES
            "expires_in":  f"{settings.FORM_LINK_EXPIRE_MINUTES} minutes",
            "message":     f"Loan form link sent to {contact.email}",
        }

    # ═════════════════════════════════════════════════
    # 2. VALIDATE TOKEN
    # ═════════════════════════════════════════════════

    @staticmethod
    async def validate_token(
        db:    AsyncSession,
        token: str,
    ) -> dict:
        result = FormTokenService.validate_token(token)

        if not result["valid"]:
            return {
                "valid":  False,
                "reason": result["reason"],
            }

        contact_result = await db.execute(
            select(Contact).where(Contact.id == result["contact_id"])
        )
        contact = contact_result.scalar_one_or_none()

        if not contact:
            return {
                "valid":  False,
                "reason": "Contact not found",
            }

        return {
            "valid":      True,
            "contact_id": str(result["contact_id"]),
            "name":       contact.name,
            "email":      contact.email,
            "phone":      contact.phone,
            "loan_type":  contact.loan_type,
            "amount":     contact.amount,
            "reason":     None,
        }

    # ═════════════════════════════════════════════════
    # 3. SUBMIT FORM
    # ═════════════════════════════════════════════════

    @staticmethod
    async def submit_form(
        db:      AsyncSession,
        payload: LoanFormSubmit,
        passport_photo:        Optional[UploadFile]       = None,
        aadhaar_document:      Optional[UploadFile]       = None,
        pan_document:          Optional[UploadFile]       = None,
        payslips:              Optional[List[UploadFile]] = None,
        salary_bank_statement: Optional[UploadFile]       = None,
        form_16:               Optional[UploadFile]       = None,
        itr_documents:         Optional[List[UploadFile]] = None,
        msme_certificate:      Optional[UploadFile]       = None,
        labour_license:        Optional[UploadFile]       = None,
        gst_certificate:       Optional[UploadFile]       = None,
        gstr_filings:          Optional[List[UploadFile]] = None,
        co_applicant_pan:      Optional[UploadFile]       = None,
        co_applicant_aadhaar:  Optional[UploadFile]       = None,
    ) -> LoanFormSubmission:

        # Validate token
        token_result = FormTokenService.validate_token(payload.token)
        if not token_result["valid"]:
            raise ValueError(f"Link is invalid or expired: {token_result['reason']}")

        contact_id = token_result["contact_id"]

        result  = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )
        contact = result.scalar_one_or_none()
        if not contact:
            raise ValueError("Contact not found")

        now = datetime.now(timezone.utc)

        # ── Save files ────────────────────────────────
        passport_path   = None
        aadhaar_path    = None
        pan_path        = None
        payslip_paths   = None
        salary_bs_path  = None
        form16_path     = None
        itr_paths       = None
        msme_path       = None
        labour_path     = None
        gst_path        = None
        gstr_paths      = None
        co_pan_path     = None
        co_aadhaar_path = None

        if passport_photo:
            passport_path = await LoanFormService._save_file(
                passport_photo, contact_id, "passport_photo"
            )
        if aadhaar_document:
            aadhaar_path = await LoanFormService._save_file(
                aadhaar_document, contact_id, "aadhaar"
            )
        if pan_document:
            pan_path = await LoanFormService._save_file(
                pan_document, contact_id, "pan"
            )
        if payslips:
            payslip_paths = await LoanFormService._save_multiple_files(
                payslips, contact_id, "payslip"
            )
        if salary_bank_statement:
            salary_bs_path = await LoanFormService._save_file(
                salary_bank_statement, contact_id, "salary_bank_statement"
            )
        if form_16:
            form16_path = await LoanFormService._save_file(
                form_16, contact_id, "form_16"
            )
        if itr_documents:
            itr_paths = await LoanFormService._save_multiple_files(
                itr_documents, contact_id, "itr"
            )
        if msme_certificate:
            msme_path = await LoanFormService._save_file(
                msme_certificate, contact_id, "msme_certificate"
            )
        if labour_license:
            labour_path = await LoanFormService._save_file(
                labour_license, contact_id, "labour_license"
            )
        if gst_certificate:
            gst_path = await LoanFormService._save_file(
                gst_certificate, contact_id, "gst_certificate"
            )
        if gstr_filings:
            gstr_paths = await LoanFormService._save_multiple_files(
                gstr_filings, contact_id, "gstr_filing"
            )
        if co_applicant_pan:
            co_pan_path = await LoanFormService._save_file(
                co_applicant_pan, contact_id, "co_pan"
            )
        if co_applicant_aadhaar:
            co_aadhaar_path = await LoanFormService._save_file(
                co_applicant_aadhaar, contact_id, "co_aadhaar"
            )

        # ── Check if submission exists ────────────────
        existing = await db.execute(
            select(LoanFormSubmission)
            .where(LoanFormSubmission.contact_id == contact_id)
        )
        submission = existing.scalar_one_or_none()

        if submission:
            submission.name            = payload.name            or submission.name
            submission.mobile          = payload.mobile          or submission.mobile
            submission.email           = payload.email           or submission.email
            submission.aadhaar_number  = payload.aadhaar_number  or submission.aadhaar_number
            submission.pan_number      = payload.pan_number      or submission.pan_number
            submission.employment_type = payload.employment_type or submission.employment_type
            submission.monthly_income  = payload.monthly_income  or submission.monthly_income
            submission.annual_turnover = payload.annual_turnover or submission.annual_turnover
            submission.loan_type       = payload.loan_type       or submission.loan_type
            submission.loan_amount     = payload.loan_amount     or submission.loan_amount
            submission.cibil_score     = payload.cibil_score     or submission.cibil_score
            submission.has_co_applicant            = payload.has_co_applicant
            submission.co_applicant_name           = payload.co_applicant_name           or submission.co_applicant_name
            submission.co_applicant_mobile         = payload.co_applicant_mobile         or submission.co_applicant_mobile
            submission.co_applicant_email          = payload.co_applicant_email          or submission.co_applicant_email
            submission.co_applicant_pan_number     = payload.co_applicant_pan_number     or submission.co_applicant_pan_number
            submission.co_applicant_aadhaar_number = payload.co_applicant_aadhaar_number or submission.co_applicant_aadhaar_number
            if passport_path:   submission.passport_photo_path         = passport_path
            if aadhaar_path:    submission.aadhaar_document_path       = aadhaar_path
            if pan_path:        submission.pan_document_path           = pan_path
            if payslip_paths:   submission.payslip_paths               = payslip_paths
            if salary_bs_path:  submission.salary_bank_statement_path  = salary_bs_path
            if form16_path:     submission.form_16_path                = form16_path
            if itr_paths:       submission.itr_paths                   = itr_paths
            if msme_path:       submission.msme_certificate_path       = msme_path
            if labour_path:     submission.labour_license_path         = labour_path
            if gst_path:        submission.gst_certificate_path        = gst_path
            if gstr_paths:      submission.gstr_filing_paths           = gstr_paths
            if co_pan_path:     submission.co_applicant_pan_path       = co_pan_path
            if co_aadhaar_path: submission.co_applicant_aadhaar_path   = co_aadhaar_path
            submission.form_status  = "submitted"
            submission.submitted_at = now
            submission.updated_at   = now
        else:
            submission = LoanFormSubmission(
                contact_id                  = contact_id,
                name                        = payload.name,
                mobile                      = payload.mobile,
                email                       = payload.email,
                aadhaar_number              = payload.aadhaar_number,
                pan_number                  = payload.pan_number,
                employment_type             = payload.employment_type,
                monthly_income              = payload.monthly_income,
                annual_turnover             = payload.annual_turnover,
                loan_type                   = payload.loan_type,
                loan_amount                 = payload.loan_amount,
                cibil_score                 = payload.cibil_score,
                has_co_applicant            = payload.has_co_applicant,
                co_applicant_name           = payload.co_applicant_name,
                co_applicant_mobile         = payload.co_applicant_mobile,
                co_applicant_email          = payload.co_applicant_email,
                co_applicant_pan_number     = payload.co_applicant_pan_number,
                co_applicant_aadhaar_number = payload.co_applicant_aadhaar_number,
                passport_photo_path         = passport_path,
                aadhaar_document_path       = aadhaar_path,
                pan_document_path           = pan_path,
                payslip_paths               = payslip_paths,
                salary_bank_statement_path  = salary_bs_path,
                form_16_path                = form16_path,
                itr_paths                   = itr_paths,
                msme_certificate_path       = msme_path,
                labour_license_path         = labour_path,
                gst_certificate_path        = gst_path,
                gstr_filing_paths           = gstr_paths,
                co_applicant_pan_path       = co_pan_path,
                co_applicant_aadhaar_path   = co_aadhaar_path,
                form_status                 = "submitted",
                submitted_at                = now,
                created_at                  = now,
                updated_at                  = now,
            )
            db.add(submission)

        # Sync back to contact
        if payload.name:   contact.name  = payload.name
        if payload.mobile: contact.phone = payload.mobile
        if payload.email:  contact.email = payload.email
        contact.status     = "Qualified"
        contact.updated_at = now

        await db.commit()
        await db.refresh(submission)
        return submission

    # ═════════════════════════════════════════════════
    # 4. GET FORM STATUS
    # ═════════════════════════════════════════════════

    @staticmethod
    async def get_form_status(
        db:         AsyncSession,
        contact_id: uuid.UUID,
    ) -> FormStatusResponse:
        result  = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )
        contact = result.scalar_one_or_none()
        if not contact:
            raise ValueError("Contact not found")

        sub_result = await db.execute(
            select(LoanFormSubmission)
            .where(LoanFormSubmission.contact_id == contact_id)
        )
        sub = sub_result.scalar_one_or_none()

        return FormStatusResponse(
            contact_id    = contact.id,
            contact_ref   = contact.contact_id,
            contact_name  = contact.name,
            contact_email = contact.email,
            form_status   = sub.form_status if sub else "pending",
            submitted_at  = sub.submitted_at if sub else None,
            submission_id = sub.id if sub else None,
            has_pan            = bool(sub and sub.pan_document_path),
            has_aadhaar        = bool(sub and sub.aadhaar_document_path),
            has_passport_photo = bool(sub and sub.passport_photo_path),
            has_co_applicant   = bool(sub and sub.has_co_applicant),
            has_payslips              = bool(sub and sub.payslip_paths),
            has_salary_bank_statement = bool(sub and sub.salary_bank_statement_path),
            has_form_16               = bool(sub and sub.form_16_path),
            has_itr              = bool(sub and sub.itr_paths),
            has_msme_certificate = bool(sub and sub.msme_certificate_path),
            has_labour_license   = bool(sub and sub.labour_license_path),
            has_gst_certificate  = bool(sub and sub.gst_certificate_path),
            has_gstr_filings     = bool(sub and sub.gstr_filing_paths),
        )

    # ═════════════════════════════════════════════════
    # 5. GET FULL SUBMISSION DETAIL
    # ═════════════════════════════════════════════════

    @staticmethod
    async def get_submission_detail(
        db:         AsyncSession,
        contact_id: uuid.UUID,
    ) -> Optional[LoanFormSubmission]:
        result = await db.execute(
            select(LoanFormSubmission)
            .where(LoanFormSubmission.contact_id == contact_id)
        )
        return result.scalar_one_or_none()