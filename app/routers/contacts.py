# app/routers/contacts.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_roles
from app.schemas.auth import CurrentUser
from app.schemas.contact import (
    ContactCreate, ContactUpdate,
    ContactResponse, ContactListItem,
)
from app.services.contact_service import ContactService

router = APIRouter(
    dependencies=[Depends(get_current_user)]
)

# Roles that can access contacts
CONTACT_ROLES = [
    "super_admin", "admin",
    "pre_sales_admin", "pre_sales_user",
    "post_sales_admin", "bank_admin",
]


# ── LIST — GET /contacts ──────────────────────────────
@router.get("/", response_model=List[ContactListItem])
async def list_contacts(
    search:  Optional[str] = Query(None),
    status:  Optional[str] = Query(None),
    source:  Optional[str] = Query(None),
    page:    int           = Query(1, ge=1),
    limit:   int           = Query(50, ge=1, le=100),
    db:      AsyncSession  = Depends(get_db),
    current: CurrentUser   = Depends(require_roles(CONTACT_ROLES)),
):
    return await ContactService.list_contacts(db, search, status, source, page, limit)


# ── CREATE — POST /contacts ───────────────────────────
@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate,
    db:      AsyncSession = Depends(get_db),
    current: CurrentUser  = Depends(require_roles(["super_admin", "admin", "pre_sales_admin"])),
):
    return await ContactService.create_contact(db, payload, current.id)


# ── GET ONE — GET /contacts/{id} ──────────────────────
@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: uuid.UUID,
    db:         AsyncSession = Depends(get_db),
    current:    CurrentUser  = Depends(require_roles(CONTACT_ROLES)),
):
    contact = await ContactService.get_by_id(db, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


# ── UPDATE — PUT /contacts/{id} ───────────────────────
@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: uuid.UUID,
    payload:    ContactUpdate,
    db:         AsyncSession = Depends(get_db),
    current:    CurrentUser  = Depends(require_roles(["super_admin", "admin", "pre_sales_admin"])),
):
    contact = await ContactService.update_contact(db, contact_id, payload)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


# ── DELETE — DELETE /contacts/{id} ────────────────────
@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID,
    db:         AsyncSession = Depends(get_db),
    current:    CurrentUser  = Depends(require_roles(["super_admin", "admin"])),
):
    deleted = await ContactService.delete_contact(db, contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")