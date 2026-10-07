# app/routers/bank_logging.py
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.models.user import User
from app.services.bank_logging_service import BankLoggingService

router = APIRouter(
    dependencies=[Depends(get_current_user)]
)

PRE_SALES_ROLES  = ["super_admin", "admin", "pre_sales_admin"]
ASSIGN_ROLES     = ["super_admin", "admin", "pre_sales_admin"]


# ── REQUEST SCHEMAS ───────────────────────────────────

class LogToBankRequest(BaseModel):
    bank_name: str


class AssignBankerRequest(BaseModel):
    banker_id: uuid.UUID


# ── 1. LOG LEAD TO BANK — POST /bank-logging/leads/{lead_id}/log-to-bank ──
@router.post("/leads/{lead_id}/log-to-bank")
async def log_lead_to_bank(
    lead_id: uuid.UUID,
    payload: LogToBankRequest,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(PRE_SALES_ROLES)),
):
    """
    Stage 1 — Log a Qualified lead to a bank (no banker assigned yet).
    Creates a Loan record with banker_id = NULL.
    Banker CANNOT see this loan until a banker is assigned.
    Lead stage → 'Logged to Bank'.
    """
    return await BankLoggingService.log_to_bank(
        db        = db,
        lead_id   = lead_id,
        bank_name = payload.bank_name,
        user_id   = current.id,
    )


# ── 2. ASSIGN BANKER — POST /bank-logging/loans/{loan_id}/assign-banker ──
@router.post("/loans/{loan_id}/assign-banker")
async def assign_banker_to_loan(
    loan_id:  uuid.UUID,
    payload:  AssignBankerRequest,
    db:       AsyncSession = Depends(get_db),
    current:  CurrentUser  = Depends(require_roles(ASSIGN_ROLES)),
    _user:    User         = Depends(get_current_user),
):
    """
    Stage 2 — Assign a banker to a logged loan.
    Validates banker belongs to the loan's bank.
    Sets banker_id → banker can now see this loan.
    Loan stage → 'submitted_to_bank'.
    Only super_admin, admin, pre_sales_admin can assign.
    """
    # We need the full User object for the service
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.id == current.id)
    )
    current_user = result.scalar_one_or_none()

    return await BankLoggingService.assign_banker(
        db           = db,
        loan_id      = loan_id,
        banker_id    = payload.banker_id,
        current_user = current_user,
    )


# ── 3. LIST UNASSIGNED LOANS — GET /bank-logging/unassigned ──
@router.get("/unassigned")
async def list_unassigned_loans(
    bank_name: Optional[str] = Query(None, description="Filter by bank name"),
    page:      int           = Query(1, ge=1),
    limit:     int           = Query(50, ge=1, le=100),
    db:        AsyncSession  = Depends(get_db),
    current:   CurrentUser   = Depends(require_roles(ASSIGN_ROLES)),
):
    """
    List all loans in 'logged_to_bank' stage with no banker assigned.
    Admin/Super Admin uses this to review and assign bankers.
    NOTE: PAN, email, phone are intentionally excluded from this list.
    """
    return await BankLoggingService.list_unassigned_loans(
        db        = db,
        bank_name = bank_name,
        page      = page,
        limit     = limit,
    )

# ── 4. GET BANKERS BY BANK — GET /bank-logging/bankers/{bank_name} ──
@router.get("/bankers/{bank_name}")
async def get_bankers_by_bank(
    bank_name: str,
    db:        AsyncSession = Depends(get_db),
    current:   CurrentUser  = Depends(require_roles(ASSIGN_ROLES)),
):
    """
    Returns bankers belonging to a specific bank.
    Used by AssignBankerModal dropdown.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(
            User.role == "bank_admin",
            User.bank_name == bank_name
        )
    )

    bankers = result.scalars().all()

    return [
        {
            "id": banker.id,
            "name": banker.name,
            "email": banker.email,
            "bank_name": banker.bank_name
        }
        for banker in bankers
    ]