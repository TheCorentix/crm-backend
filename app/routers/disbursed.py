# app/routers/disbursed.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.services.disbursed_service import DisbursedService

router = APIRouter(
    dependencies=[Depends(get_current_user)]
)

ACCESS_ROLES = ["super_admin", "admin", "post_sales_admin", "bank_admin"]


# ── SUMMARY — GET /disbursed/summary ─────────────────
@router.get("/summary")
async def disbursed_summary(
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(ACCESS_ROLES)),
):
    """
    Summary stats: total disbursed count, total amount,
    and per-bank breakdown.
    """
    return await DisbursedService.get_summary(db)


# ── LIST — GET /disbursed ─────────────────────────────
@router.get("/")
async def list_disbursed(
    search:    Optional[str] = Query(None, description="Search by name, email, phone, PAN, loan ID"),
    bank_name: Optional[str] = Query(None, description="Filter by bank name"),
    page:      int           = Query(1, ge=1),
    limit:     int           = Query(50, ge=1, le=100),
    db:        AsyncSession  = Depends(get_db),
    current:   CurrentUser   = Depends(require_roles(ACCESS_ROLES)),
):
    """
    List all disbursed loans with full lead + banker details.
    Supports search and bank filter.
    """
    return await DisbursedService.list_disbursed(
        db        = db,
        search    = search,
        bank_name = bank_name,
        page      = page,
        limit     = limit,
    )


# ── DETAIL — GET /disbursed/{loan_id} ────────────────
@router.get("/{loan_id}")
async def get_disbursed(
    loan_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(ACCESS_ROLES)),
):
    """
    Full detail of a single disbursed loan — complete
    lead journey from creation to bank disbursement.
    """
    record = await DisbursedService.get_disbursed_by_id(db, loan_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail="Disbursed loan not found",
        )
    return record