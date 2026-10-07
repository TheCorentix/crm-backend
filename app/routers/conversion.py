# app/routers/conversion.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser

from app.schemas.conversion import (
    ContactStateUpdate,
    ConversionResponse,
    EligibilityResponse,
)

from app.services.conversion_service import ConversionService

router = APIRouter(dependencies=[Depends(get_current_user)])

CONVERT_ROLES = ["super_admin", "admin", "pre_sales_admin"]


@router.patch("/contacts/{contact_id}/state")
async def update_contact_state(
    contact_id: uuid.UUID,
    payload: ContactStateUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(CONVERT_ROLES)),
):
    try:
        contact = await ConversionService.update_contact_status(
            db=db,
            contact_id=contact_id,
            new_status=payload.status,
            notes=payload.notes,
            user_id=current.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return {
        "success": True,
        "contact_id": str(contact.id),
        "ref": contact.contact_id,
        "status": contact.status,
        "updated_at": contact.updated_at,
    }


@router.patch("/leads/{lead_id}/stage")
async def update_lead_stage(
    lead_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(CONVERT_ROLES)),
):
    stage = payload.get("stage")

    if not stage:
        raise HTTPException(status_code=400, detail="stage is required")

    try:
        lead = await ConversionService.update_lead_stage(
            db=db,
            lead_id=lead_id,
            stage=stage,
            notes=payload.get("notes"),
            user_id=current.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return {
        "success": True,
        "lead_id": str(lead.id),
        "ref": lead.loan_id,
        "stage": lead.stage,
        "updated_at": lead.updated_at,
    }


@router.get(
    "/contacts/{contact_id}/convert-to-lead/check",
    response_model=EligibilityResponse,
)
async def check_eligibility(
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(CONVERT_ROLES)),
):
    return await ConversionService.check_contact_eligibility(
        db=db,
        contact_id=contact_id,
    )


@router.post(
    "/contacts/{contact_id}/convert-to-lead",
    response_model=ConversionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def contact_to_lead(
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(CONVERT_ROLES)),
):
    try:
        return await ConversionService.contact_to_lead(
            db=db,
            contact_id=contact_id,
            user_id=current.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))