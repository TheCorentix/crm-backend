# app/routers/bank_dashboard.py
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from app.schemas.user import BankerOut
from app.middleware.auth import get_current_user

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.models.loan import Loan
from app.models.user import User, ActivityLog

router = APIRouter()

BANK_ROLES  = ["bank_admin", "super_admin"]
ROUTE_ROLES = ["super_admin", "admin", "pre_sales_admin"]
SALES_ROLES = ["super_admin", "admin", "pre_sales_admin"]


# ── Schemas ───────────────────────────────────────────

class BankKpis(BaseModel):
    total:                  int = 0
    submitted_to_bank:      int = 0
    under_review:           int = 0
    documents_required:     int = 0
    docs_review_complete:   int = 0
    bank_processing:        int = 0
    bank_approved:          int = 0
    partially_approved:     int = 0
    bank_rejected:          int = 0
    loan_disbursed:         int = 0
    total_amount_requested: int = 0


class BankLoanItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                    uuid.UUID
    loan_id:               Optional[str]      = None
    contact_name:          Optional[str]      = None
    contact_email:         Optional[str]      = None
    phone:                 Optional[str]      = None
    pan_number:            Optional[str]      = None
    loan_amount_requested: Optional[int]      = None
    loan_amount_approved:  Optional[int]      = None
    credit_score:          Optional[int]      = None
    bank_name:             Optional[str]      = None
    banker_id: Optional[uuid.UUID] = None
    bank_reference:        Optional[str]      = None
    rejection_reason:      Optional[str]      = None
    stage:                 str
    last_comment:          Optional[str]      = None
    notes:                 Optional[str]      = None
    created_at:            datetime
    state_updated_at:      datetime


class BankDashboardResponse(BaseModel):
    banker_name: str
    bank_name:   Optional[str]
    kpis:        BankKpis
    loans:       List[BankLoanItem]


class StageUpdateRequest(BaseModel):
    stage:            str
    comment:          str
    notes:            Optional[str] = None
    disbursed_amount: Optional[int] = None


class DocsRequiredRequest(BaseModel):
    comment: str


class DocsRequiredResponse(BaseModel):
    success:         bool
    loan_id:         str
    stage_updated:   bool
    notified_count:  int
    notified_emails: List[str]


class PendingDocsItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                    uuid.UUID
    loan_id:               Optional[str] = None
    contact_name:          Optional[str] = None
    contact_email:         Optional[str] = None
    phone:                 Optional[str] = None
    loan_amount_requested: Optional[int] = None
    bank_name:             Optional[str] = None
    last_comment:          Optional[str] = None
    state_updated_at:      datetime


# ── GET BANK DASHBOARD ────────────────────────────────
@router.get("/", response_model=BankDashboardResponse)
async def get_bank_dashboard(
    banker_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(BANK_ROLES)),
):
    banker_result = await db.execute(select(User).where(User.id == current.id))
    banker = banker_result.scalar_one_or_none()
    if not banker:
        raise HTTPException(status_code=404, detail="Banker not found")

    # super_admin sees ALL loans, bank_admin sees only their own
    if current.role == "bank_admin":
        loan_query = select(Loan).where(Loan.banker_id == current.id)

    elif banker_id:
        loan_query = select(Loan).where(Loan.banker_id == banker_id)

    else:
        loan_query = select(Loan)

    loans_result = await db.execute(
        loan_query.order_by(Loan.created_at.desc())
    )
    loans = loans_result.scalars().all()

    kpis = BankKpis(
        total                  = len(loans),
        submitted_to_bank      = sum(1 for l in loans if l.stage == "submitted_to_bank"),
        under_review           = sum(1 for l in loans if l.stage == "under_review"),
        documents_required     = sum(1 for l in loans if l.stage == "documents_required"),
        docs_review_complete   = sum(1 for l in loans if l.stage == "docs_review_complete"),
        bank_processing        = sum(1 for l in loans if l.stage == "bank_processing"),
        bank_approved          = sum(1 for l in loans if l.stage == "bank_approved"),
        partially_approved     = sum(1 for l in loans if l.stage == "partially_approved"),
        bank_rejected          = sum(1 for l in loans if l.stage == "bank_rejected"),
        loan_disbursed         = sum(1 for l in loans if l.stage == "loan_disbursed"),
        total_amount_requested = sum(l.loan_amount_requested or 0 for l in loans),
    )

    if current.role == "bank_admin":
        bank_name = banker.bank_name
    else:
        bank_name = "All Banks"

    return {
        "banker_name": banker.name,
        "bank_name":   bank_name,
        "kpis":        kpis,
        "loans":       loans,
    }


# ── GET LOANS (with filters) ──────────────────────────
@router.get("/loans", response_model=List[BankLoanItem])
async def get_my_loans(
    stage:   Optional[str] = Query(None),
    search:  Optional[str] = Query(None),
    page:    int           = Query(1, ge=1),
    limit:   int           = Query(50, ge=1, le=100),
    db:      AsyncSession  = Depends(get_db),
    current: CurrentUser   = Depends(require_roles(BANK_ROLES)),
):
    # super_admin sees ALL loans, bank_admin sees only their own
    if current.role == "bank_admin":
        q = select(Loan).where(Loan.banker_id == current.id)
    else:
        q = select(Loan)

    if stage:
        q = q.where(Loan.stage == stage)

    if search:
        term = f"%{search.lower()}%"
        q = q.where(or_(
            func.lower(Loan.contact_name).like(term),
            func.lower(Loan.loan_id).like(term),
            func.lower(Loan.pan_number).like(term),
            func.lower(Loan.contact_email).like(term),
        ))

    q = q.order_by(Loan.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


# ── GET SINGLE LOAN ───────────────────────────────────
@router.get("/loans/{loan_id}", response_model=BankLoanItem)
async def get_loan_detail(
    loan_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(BANK_ROLES)),
):
    # super_admin can access any loan, bank_admin only their own
    if current.role == "bank_admin":
        q = select(Loan).where(
            Loan.id        == loan_id,
            Loan.banker_id == current.id,
        )
    else:
        q = select(Loan).where(Loan.id == loan_id)

    result = await db.execute(q)
    loan   = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(
            status_code=404,
            detail="Loan not found or not assigned to your account",
        )
    return loan


# ── UPDATE LOAN STAGE ─────────────────────────────────
@router.patch("/loans/{loan_id}/stage", response_model=BankLoanItem)
async def update_loan_stage(
    loan_id: uuid.UUID,
    payload: StageUpdateRequest,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(BANK_ROLES)),
):
    if not payload.comment or not payload.comment.strip():
        raise HTTPException(status_code=400, detail="Comment is mandatory for every stage update")

    if current.role == "bank_admin":
        q = select(Loan).where(
            Loan.id        == loan_id,
            Loan.banker_id == current.id,
        )
    else:
        q = select(Loan).where(Loan.id == loan_id)

    result = await db.execute(q)
    loan   = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found or not assigned to your account")

    old_stage             = loan.stage
    loan.stage            = payload.stage
    loan.state_updated_at = datetime.now(timezone.utc)
    loan.last_comment     = payload.comment.strip()

    # Set disbursed_amount when marking as loan_disbursed
    if payload.stage == "loan_disbursed":
        loan.disbursed_amount = (
            payload.disbursed_amount
            or loan.loan_amount_approved
            or loan.loan_amount_requested
        )
        loan.disbursed_at = datetime.now(timezone.utc)

    ts           = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    comment_line = f"[{ts}] {payload.comment.strip()}"
    loan.notes   = f"{loan.notes}\n{comment_line}" if loan.notes else comment_line

    if payload.notes:
        loan.notes = f"{loan.notes}\n{payload.notes}"

    db.add(ActivityLog(
        user_id     = current.id,
        action      = f"Loan {loan.loan_id} stage: {old_stage} → {payload.stage} | {payload.comment.strip()}",
        entity_type = "loan",
        entity_id   = loan.id,
    ))

    await db.commit()
    await db.refresh(loan)
    return loan


# ── NOTIFY DOCS REQUIRED ──────────────────────────────
@router.post("/loans/{loan_id}/notify-docs-required", response_model=DocsRequiredResponse)
async def notify_docs_required(
    loan_id: uuid.UUID,
    payload: DocsRequiredRequest,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(BANK_ROLES)),
):
    if not payload.comment or not payload.comment.strip():
        raise HTTPException(status_code=400, detail="Comment is mandatory")

    if current.role == "bank_admin":
        q = select(Loan).where(
            Loan.id        == loan_id,
            Loan.banker_id == current.id,
        )
    else:
        q = select(Loan).where(Loan.id == loan_id)

    result = await db.execute(q)
    loan   = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found or not assigned to your account")

    loan.stage            = "documents_required"
    loan.state_updated_at = datetime.now(timezone.utc)
    loan.last_comment     = payload.comment.strip()

    ts           = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    comment_line = f"[{ts}] DOCS REQUIRED: {payload.comment.strip()}"
    loan.notes   = f"{loan.notes}\n{comment_line}" if loan.notes else comment_line

    db.add(ActivityLog(
        user_id     = current.id,
        action      = f"Loan {loan.loan_id} docs required — awaiting sales action | {payload.comment.strip()}",
        entity_type = "loan",
        entity_id   = loan.id,
    ))

    await db.commit()
    await db.refresh(loan)

    return {
        "success":         True,
        "loan_id":         loan.loan_id or str(loan.id),
        "stage_updated":   True,
        "notified_count":  0,
        "notified_emails": [],
    }


# ── PENDING DOCS — for Sales Overview alert panel ─────
@router.get("/pending-docs", response_model=List[PendingDocsItem])
async def get_pending_docs(
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(SALES_ROLES)),
):
    result = await db.execute(
        select(Loan)
        .where(Loan.stage == "documents_required")
        .order_by(Loan.state_updated_at.desc())
    )
    return result.scalars().all()


# ── BANKERS — single endpoint with optional bank_name filter ──
@router.get("/bankers", response_model=list[BankerOut])
async def get_bankers(
    bank_name: Optional[str] = Query(default=None),
    db:        AsyncSession  = Depends(get_db),
    current:   CurrentUser   = Depends(require_roles(
        ["super_admin", "admin", "pre_sales_admin", "bank_admin"]
    )),
):
    query = select(User).where(
        User.role   == "bank_admin",
        User.status == "active",
    )
    if bank_name:
        query = query.where(User.bank_name == bank_name)

    result = await db.execute(query)
    return result.scalars().all()

# ── GET BANKS ──────────────────────────────
@router.get("/banks", response_model=list[str])
async def get_banks(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(
        ["super_admin", "admin", "pre_sales_admin", "bank_admin"]
    )),
):
    result = await db.execute(
        select(User.bank_name)
        .where(
            User.role == "bank_admin",
            User.status == "active"
        )
        .distinct()
    )

    banks = [row[0] for row in result.all() if row[0]]

    return banks