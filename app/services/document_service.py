# app/services/document_service.py
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import DocumentRequest, LoanDocument
from app.models.loan import Loan
from app.models.user import User
from app.services.document_email_service import DocumentEmailService


ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB
TOKEN_EXPIRE_HRS = 48


class DocumentService:

    # ── 1. Send upload link to customer ───────────────
    @staticmethod
    async def send_upload_link(
        db: AsyncSession,
        loan_id: uuid.UUID,
        sent_by: uuid.UUID,
        frontend_url: str,
    ) -> dict:

        result = await db.execute(
            select(Loan)
            .options(selectinload(Loan.banker))
            .where(Loan.id == loan_id)
        )
        loan = result.scalar_one_or_none()

        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found")

        if loan.stage != "documents_required":
            raise HTTPException(
                status_code=400,
                detail="Loan must be in 'documents_required' stage to send upload link",
            )

        if not loan.contact_email:
            raise HTTPException(
                status_code=400,
                detail="No customer email on record for this loan",
            )

        existing = await db.execute(
            select(DocumentRequest).where(
                DocumentRequest.loan_id == loan_id,
                DocumentRequest.is_used == False,
                DocumentRequest.expires_at > datetime.now(timezone.utc),
            )
        )

        existing_req = existing.scalar_one_or_none()

        if existing_req:
            token = existing_req.token
        else:
            token = secrets.token_urlsafe(32)

            doc_request = DocumentRequest(
                loan_id=loan_id,
                token=token,
                customer_email=loan.contact_email,
                customer_name=loan.contact_name or "Customer",
                banker_note=loan.last_comment,
                document_name  = loan.last_comment,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HRS),
                sent_by=sent_by,
            )

            db.add(doc_request)
            await db.flush()

        upload_url = f"{frontend_url}/upload-docs/{token}"

        DocumentEmailService.send_upload_link(
            to_email=loan.contact_email,
            to_name=loan.contact_name or "Customer",
            upload_url=upload_url,
            loan_ref=loan.loan_id or str(loan.id),
            banker_note=loan.last_comment,
            bank_name=loan.bank_name,
        )

        await db.commit()

        return {
            "message": f"Upload link sent to {loan.contact_email}",
            "upload_url": upload_url,
            "expires_in": f"{TOKEN_EXPIRE_HRS} hours",
            "customer_email": loan.contact_email,
        }

    # ── 2. Validate token ─────────────────────────────
    @staticmethod
    async def validate_token(
        db: AsyncSession,
        token: str,
    ) -> dict:

        result = await db.execute(
            select(DocumentRequest)
            .options(selectinload(DocumentRequest.loan))
            .where(DocumentRequest.token == token)
        )

        req = result.scalar_one_or_none()

        if not req:
            raise HTTPException(status_code=404, detail="Invalid upload link")

        if req.is_used:
            raise HTTPException(
                status_code=400,
                detail="This upload link has already been used. Please contact your loan officer."
            )

        if datetime.now(timezone.utc) > req.expires_at:
            raise HTTPException(
                status_code=400,
                detail="This upload link has expired."
            )

        loan = req.loan

        return {
            "valid": True,
            "customer_name": req.customer_name,
            "customer_email": req.customer_email,
            "loan_ref": loan.loan_id if loan else None,
            "bank_name": loan.bank_name if loan else None,
            "banker_note": req.banker_note,
            "expires_at": req.expires_at.isoformat(),
        }

    # ── 3. Upload documents ───────────────────────────
    @staticmethod
    async def upload_documents(
        db: AsyncSession,
        token: str,
        files: list[UploadFile],
    ) -> dict:

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        result = await db.execute(
            select(DocumentRequest)
            .options(selectinload(DocumentRequest.loan).selectinload(Loan.banker))
            .where(DocumentRequest.token == token)
        )

        req = result.scalar_one_or_none()

        if not req:
            raise HTTPException(status_code=404, detail="Invalid upload link")

        if req.is_used:
            raise HTTPException(status_code=400, detail="Upload link already used")

        if datetime.now(timezone.utc) > req.expires_at:
            raise HTTPException(status_code=400, detail="Upload link expired")

        loan = req.loan

        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found")

        uploaded = []

        for file in files:

            if file.content_type not in ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}"
                )

            content = await file.read()

            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds 10MB limit"
                )

            doc = LoanDocument(
                request_id=req.id,
                loan_id=loan.id,
                filename=file.filename,
                content_type=file.content_type,
                file_size=len(content),
                file_data=content,
            )

            db.add(doc)
            uploaded.append(file.filename)

        # Update request tracking
        req.is_used = True
        req.used_at = datetime.now(timezone.utc)
        req.status = "uploaded"
        req.uploaded_at = datetime.now(timezone.utc)

        if uploaded:
            req.uploaded_doc_id = doc.id

        loan.stage = "docs_received"
        loan.state_updated_at = datetime.now(timezone.utc)

        await db.flush()

        if loan.banker and loan.banker.email:
            DocumentEmailService.send_banker_notification(
                to_email=loan.banker.email,
                banker_name=loan.banker.name,
                loan_ref=loan.loan_id or str(loan.id),
                customer_name=req.customer_name,
                doc_count=len(uploaded),
            )

        await db.commit()

        return {
            "message": "Documents uploaded successfully.",
            "files_uploaded": uploaded,
            "loan_stage": "docs_received",
        }

    # ── 4. List uploaded documents ────────────────────
    @staticmethod
    async def list_documents(
        db: AsyncSession,
        loan_id: uuid.UUID,
    ) -> list[dict]:

        result = await db.execute(
            select(LoanDocument)
            .where(LoanDocument.loan_id == loan_id)
            .order_by(LoanDocument.uploaded_at.desc())
        )

        docs = result.scalars().all()

        return [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "content_type": doc.content_type,
                "file_size": doc.file_size,
                "uploaded_at": doc.uploaded_at.isoformat(),
            }
            for doc in docs
        ]

    # ── 5. Download document ──────────────────────────
    @staticmethod
    async def get_document(
        db: AsyncSession,
        doc_id: uuid.UUID,
    ) -> Optional[LoanDocument]:

        result = await db.execute(
            select(LoanDocument).where(LoanDocument.id == doc_id)
        )

        return result.scalar_one_or_none()

    # ── 6. List requested documents ───────────────────
    @staticmethod
    async def list_document_requests(
        db: AsyncSession,
        loan_id: uuid.UUID,
    ) -> list[dict]:

        result = await db.execute(
            select(DocumentRequest)
            .where(DocumentRequest.loan_id == loan_id)
            .order_by(DocumentRequest.created_at.desc())
        )

        requests = result.scalars().all()

        return [
            {
                "request_id": str(r.id),
                "document_name": r.document_name,
                "status": r.status,
                "banker_note": r.banker_note,
                "requested_at": r.created_at.isoformat(),
                "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
            }
            for r in requests
        ]