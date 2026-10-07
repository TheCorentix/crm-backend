# app/routers/performance.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.services.performance_service import PerformanceService

router = APIRouter(
    dependencies=[Depends(get_current_user)]
)

SALES_ROLES = ["super_admin", "admin"]


# ── TEAM PERFORMANCE — GET /performance/team ──────────
@router.get("/team")
async def team_performance(
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(SALES_ROLES)),
):
    """
    Team Performance table for Sales Overview.
    Returns per-user breakdown:
    leads handled, qualified, disbursed, conversion %, vs target.
    Covers pre-sales, post-sales, and bank admin roles.
    """
    return await PerformanceService.get_team_performance(db)


# ── BANK PERFORMANCE — GET /performance/bank ──────────
@router.get("/bank")
async def bank_performance(
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(SALES_ROLES)),
):
    """
    Bank Partner Performance table for Sales Overview.
    Returns per-bank breakdown:
    loans sent, approved, rejected, approval rate %.
    """
    return await PerformanceService.get_bank_performance(db)