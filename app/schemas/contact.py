# app/schemas/contact.py
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


VALID_STATUSES = ["New", "Contacted", "Qualified", "Unqualified"]
VALID_SOURCES  = ["website_form", "referral", "walk_in", "social_media"]


# ── BASE ──────────────────────────────────────────────
class ContactBase(BaseModel):
    name:      str
    email:     Optional[EmailStr] = None
    phone:     Optional[str]      = None
    city:      Optional[str]      = None
    source:    Optional[str]      = None
    loan_type: Optional[str]      = None
    amount:    Optional[int]      = None   # in rupees
    notes:     Optional[str]      = None


# ── CREATE — POST /contacts ───────────────────────────
class ContactCreate(ContactBase):
    status: str = "New"


# ── UPDATE — PUT /contacts/{id} ───────────────────────
class ContactUpdate(BaseModel):
    name:      Optional[str]      = None
    email:     Optional[EmailStr] = None
    phone:     Optional[str]      = None
    city:      Optional[str]      = None
    source:    Optional[str]      = None
    status:    Optional[str]      = None
    loan_type: Optional[str]      = None
    amount:    Optional[int]      = None
    notes:     Optional[str]      = None


# ── RESPONSE ──────────────────────────────────────────
class ContactResponse(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id:         uuid.UUID
    contact_id: Optional[str]       = None   # CNT-001
    status:     str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None


# ── LIST ITEM (lighter) ───────────────────────────────
class ContactListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         uuid.UUID
    contact_id: Optional[str] = None
    name:       str
    email:      Optional[str] = None
    phone:      Optional[str] = None
    city:       Optional[str] = None
    source:     Optional[str] = None
    status:     str
    loan_type:  Optional[str] = None
    amount:     Optional[int] = None
    created_at: datetime


# ── FILTERS (query params) ────────────────────────────
class ContactFilters(BaseModel):
    search:  Optional[str] = None   # name | email | phone | city
    status:  Optional[str] = None
    source:  Optional[str] = None
    page:    int = 1
    limit:   int = 50