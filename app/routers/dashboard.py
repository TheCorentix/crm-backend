# app/routers/dashboard.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.services.dashboard_service import DashboardService

router = APIRouter(
    dependencies=[Depends(get_current_user)]
)


# ── SALES OVERVIEW — GET /dashboard/sales ─────────────
@router.get("/sales")
async def sales_overview(
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin", "admin"])),
):
    """
    Full cross-team KPIs:
    total leads, disbursed, revenue, conversion rate,
    bank approval, default rate, avg days to qualify/disburse.
    """
    return await DashboardService.get_sales_overview(db)


# ── PRE-SALES — GET /dashboard/pre ────────────────────
@router.get("/pre")
async def pre_sales_dashboard(
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles([
        "super_admin", "admin",
        "pre_sales_admin", "pre_sales_user",
    ])),
):
    """
    Pre-sales KPIs:
    stage funnel counts, conversion rates,
    docs pending, team performance breakdown.
    """
    return await DashboardService.get_pre_sales(db)


# ── POST-SALES — GET /dashboard/post ──────────────────
@router.get("/post")
async def post_sales_dashboard(
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles([
        "super_admin", "admin",
        "post_sales_admin", "bank_admin",
    ])),
):
    """
    Post-sales KPIs:
    bank pipeline states, disbursement totals,
    approval/rejection rates per bank.
    """
    return await DashboardService.get_post_sales(db)


# ── TRENDS — GET /dashboard/trends ────────────────────
@router.get("/trends")
async def trends(
    days:    int          = Query(30, ge=7, le=365),
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin", "admin"])),
):
    """
    Time-series data for charts:
    daily new leads, qualifications, disbursements over N days.
    """
    return await DashboardService.get_trends(db, days)


# ── PIPELINE — GET /dashboard/pipeline ────────────────
@router.get("/pipeline")
async def pipeline(
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles([
        "super_admin", "admin",
        "pre_sales_admin", "post_sales_admin",
    ])),
):
    """
    Live count of leads/loans at each stage right now.
    Used for the pipeline flow strip on Sales Overview.
    """
    return await DashboardService.get_pipeline(db)
