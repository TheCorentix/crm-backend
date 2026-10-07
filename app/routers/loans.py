# app/routers/loans.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.schemas.loan import (
    LoanUpdate, LoanStateUpdate,
    LoanResponse, LoanListItem,
)
from app.services.loan_service import LoanService

router = APIRouter(
    dependencies=[Depends(get_current_user)]
)

READ_ROLES  = ["super_admin", "admin", "post_sales_admin", "bank_admin"]
WRITE_ROLES = ["super_admin", "admin", "post_sales_admin"]
BANK_ROLES  = ["super_admin", "admin", "post_sales_admin", "bank_admin"]


# ── LIST — GET /loans ─────────────────────────────────
@router.get("/", response_model=List[LoanListItem])
async def list_loans(
    search:      Optional[str]       = Query(None),
    stage:       Optional[str]       = Query(None),
    bank_name:   Optional[str]       = Query(None),
    assigned_to: Optional[uuid.UUID] = Query(None),
    page:        int                 = Query(1, ge=1),
    limit:       int                 = Query(50, ge=1, le=100),
    db:          AsyncSession        = Depends(get_db),
    current:     CurrentUser         = Depends(require_roles(READ_ROLES)),
):
    return await LoanService.list_loans(db, search, stage, bank_name, assigned_to, page, limit)


# ── GET ONE — GET /loans/{id} ─────────────────────────
@router.get("/{loan_id}", response_model=LoanResponse)
async def get_loan(
    loan_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(READ_ROLES)),
):
    loan = await LoanService.get_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


# ── UPDATE — PUT /loans/{id} ──────────────────────────
@router.put("/{loan_id}", response_model=LoanResponse)
async def update_loan(
    loan_id: uuid.UUID,
    payload: LoanUpdate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(WRITE_ROLES)),
):
    loan = await LoanService.update_loan(db, loan_id, payload)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


# ── STATE CHANGE — PATCH /loans/{id}/state ────────────
@router.patch("/{loan_id}/state", response_model=LoanResponse)
async def update_loan_state(
    loan_id: uuid.UUID,
    payload: LoanStateUpdate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(BANK_ROLES)),
):
    """
    Bank admin can move:  sent_to_bank → bank_processing → bank_approved / bank_rejected
    Post-sales admin can: bank_approved → loan_disbursed | deal_lost | default
    """
    loan = await LoanService.update_state(db, loan_id, payload, current.id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan