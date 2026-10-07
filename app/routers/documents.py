# app/routers/documents.py
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.services.document_service import DocumentService
from app.config import settings

router = APIRouter()

STAFF_ROLES = ["super_admin", "admin", "pre_sales_admin", "post_sales_admin", "bank_admin"]


# ── SEND UPLOAD LINK — POST /documents/send-upload-link/{loan_id} ──
# Requires auth — called by pre-sales from the Sales Overview alert
@router.post("/send-upload-link/{loan_id}")
async def send_upload_link(
    loan_id:  uuid.UUID,
    db:       AsyncSession = Depends(get_db),
    current:  CurrentUser  = Depends(require_roles(["super_admin", "admin", "pre_sales_admin"])),
    _auth:    CurrentUser  = Depends(get_current_user),
):
    """
    Generate a secure upload token and email the customer.
    Loan must be in 'documents_required' stage.
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
    return await DocumentService.send_upload_link(
        db           = db,
        loan_id      = loan_id,
        sent_by      = current.id,
        frontend_url = frontend_url,
    )


# ── VALIDATE TOKEN — GET /documents/validate/{token} ──
# Public — no auth required (customer opens this link)
@router.get("/validate/{token}")
async def validate_token(
    token: str,
    db:    AsyncSession = Depends(get_db),
):
    """
    Validate an upload token.
    Called by the frontend upload page before showing the form.
    Returns loan info and banker's note.
    """
    return await DocumentService.validate_token(db, token)


# ── UPLOAD DOCUMENTS — POST /documents/upload/{token} ──
# Public — no auth required (customer uploads here)
@router.post("/upload/{token}")
async def upload_documents(
    token: str,
    files: List[UploadFile] = File(...),
    db:    AsyncSession     = Depends(get_db),
):
    """
    Accept document uploads from customer.
    - Validates token (not used, not expired)
    - Stores files in PostgreSQL
    - Auto-updates loan stage → docs_review_complete
    - Notifies banker via email
    """
    return await DocumentService.upload_documents(db, token, files)


# ── LIST DOCUMENTS — GET /documents/loan/{loan_id} ──
# Auth required — for staff to see uploaded docs
@router.get("/loan/{loan_id}")
async def list_documents(
    loan_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(STAFF_ROLES)),
    _auth:   CurrentUser  = Depends(get_current_user),
):
    """
    List all documents uploaded for a loan.
    Returns metadata only (no file bytes).
    """
    return await DocumentService.list_documents(db, loan_id)


# ── DOWNLOAD DOCUMENT — GET /documents/download/{doc_id} ──
# Auth required — staff downloads a specific file
@router.get("/download/{doc_id}")
async def download_document(
    doc_id:  uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(STAFF_ROLES)),
    _auth:   CurrentUser  = Depends(get_current_user),
):
    """
    Download a specific document by ID.
    Returns raw file bytes with correct content-type header.
    """
    doc = await DocumentService.get_document(db, doc_id)
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")

    return Response(
        content     = doc.file_data,
        media_type  = doc.content_type,
        headers     = {
            "Content-Disposition": f'attachment; filename="{doc.filename}"',
            "Content-Length"     : str(doc.file_size),
        },
    )

# ── LIST DOCUMENT REQUESTS — GET /documents/requests/{loan_id} ──
@router.get("/requests/{loan_id}")
async def list_document_requests(
    loan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(STAFF_ROLES)),
    _auth: CurrentUser = Depends(get_current_user),
):
    """
    List requested documents and their status for a loan.
    """
    return await DocumentService.list_document_requests(db, loan_id)