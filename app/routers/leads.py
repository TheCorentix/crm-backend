# app/routers/leads.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadStateUpdate,
    LeadResponse, LeadListItem, AssignToBankerRequest
)
from app.services.lead_service import LeadService

router = APIRouter(
    dependencies=[Depends(get_current_user)]
)

READ_ROLES  = ["super_admin", "admin", "pre_sales_admin", "pre_sales_user", "post_sales_admin", "bank_admin"]
WRITE_ROLES = ["super_admin", "admin", "pre_sales_admin"]


# ── LIST — GET /leads ─────────────────────────────────
@router.get("/", response_model=List[LeadListItem])
async def list_leads(
    search:      Optional[str]       = Query(None),
    stage:       Optional[str]       = Query(None),
    loan_type:   Optional[str]       = Query(None),
    assigned_to: Optional[uuid.UUID] = Query(None),
    page:        int                 = Query(1, ge=1),
    limit:       int                 = Query(50, ge=1, le=100),
    db:          AsyncSession        = Depends(get_db),
    current:     CurrentUser         = Depends(require_roles(READ_ROLES)),
):
    return await LeadService.list_leads(db, search, stage, loan_type, assigned_to, page, limit)


# ── CREATE — POST /leads ──────────────────────────────
@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(WRITE_ROLES)),
):
    return await LeadService.create_lead(db, payload, current.id)


# ── GET ONE — GET /leads/{id} ─────────────────────────
@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(READ_ROLES)),
):
    lead = await LeadService.get_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


# ── UPDATE — PUT /leads/{id} ──────────────────────────
@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(WRITE_ROLES)),
):
    lead = await LeadService.update_lead(db, lead_id, payload)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


# ── DELETE — DELETE /leads/{id} ───────────────────────
@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin", "admin"])),
):
    deleted = await LeadService.delete_lead(db, lead_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lead not found")


# ── STATE CHANGE — PATCH /leads/{id}/state ────────────
@router.patch("/{lead_id}/state", response_model=LeadResponse)
async def update_lead_state(
    lead_id: uuid.UUID,
    payload: LeadStateUpdate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(WRITE_ROLES)),
):
    lead = await LeadService.update_state(db, lead_id, payload, current.id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


# ── SEND TO BANK — POST /leads/{id}/send-to-bank ──────
class SendToBankRequest(BaseModel):
    bank_name: str
    banker_id: uuid.UUID


@router.post("/{lead_id}/send-to-bank", response_model=LeadResponse)
async def send_to_bank(
    lead_id: uuid.UUID,
    payload: SendToBankRequest,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin", "admin", "pre_sales_admin"])),
):
    """
    Promotes a Qualified lead to the post-sales pipeline.
    Creates a Loan record assigned to the specified banker.
    Only the assigned bank_admin can see this loan in their dashboard.
    """
    lead = await LeadService.send_to_bank(
        db,
        lead_id   = lead_id,
        bank_name = payload.bank_name,
        banker_id = payload.banker_id,
        user_id   = current.id,
    )

    if not lead:
        raise HTTPException(
            status_code=400,
            detail="Lead not found, not Qualified, or banker is invalid",
        )

    return lead


# ── ASSIGN TO BANKER — POST /leads/{id}/assign-to-banker ──────
@router.post("/{lead_id}/assign-to-banker", response_model=dict)
async def assign_lead_to_banker(
    lead_id: UUID,
    payload: AssignToBankerRequest,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["pre_sales_admin", "admin", "super_admin"])),
):
    """
    Assign (or re-assign) a lead to a specific banker within a bank.
    Unlike send-to-bank, this works on any lead stage and updates
    the existing Loan record if one already exists.
    """
    return await LeadService.assign_lead_to_banker(
        db=db,
        lead_id=lead_id,
        bank_name=payload.bank_name,
        banker_id=payload.banker_id,
        current_user=current,
    )