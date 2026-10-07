# app/schemas/lead.py
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID


VALID_STAGES = [
    "New Lead",
    "In Progress",
    "Under Review",
    "Documents Pending",
    "Qualified",
    "Not Qualified",
]

VALID_LOAN_TYPES = [
    "Home Loan",
    "Personal Loan",
    "Business Loan",
    "Vehicle Loan",
    "Loan Against Property",
]

VALID_EMPLOYMENT = ["Salaried", "Self-employed"]


# ── BASE ──────────────────────────────────────────────
class LeadBase(BaseModel):
    name:            str
    email:           Optional[EmailStr] = None
    phone:           Optional[str]      = None
    pan_number:      Optional[str]      = None
    city:            Optional[str]      = None
    loan_type:       Optional[str]      = None
    amount:          Optional[int]      = None
    source:          Optional[str]      = None
    cibil_score:     Optional[int]      = None
    employment_type: Optional[str]      = None
    monthly_income:  Optional[int]      = None
    notes:           Optional[str]      = None


# ── CREATE — POST /leads ──────────────────────────────
class LeadCreate(LeadBase):
    stage:       str                  = "New Lead"
    contact_id:  Optional[uuid.UUID]  = None
    assigned_to: Optional[uuid.UUID]  = None


# ── UPDATE — PUT /leads/{id} ──────────────────────────
class LeadUpdate(BaseModel):
    name:            Optional[str]       = None
    email:           Optional[EmailStr]  = None
    phone:           Optional[str]       = None
    pan_number:      Optional[str]       = None
    city:            Optional[str]       = None
    loan_type:       Optional[str]       = None
    amount:          Optional[int]       = None
    source:          Optional[str]       = None
    cibil_score:     Optional[int]       = None
    employment_type: Optional[str]       = None
    monthly_income:  Optional[int]       = None
    notes:           Optional[str]       = None
    assigned_to:     Optional[uuid.UUID] = None


# ── STAGE CHANGE — PATCH /leads/{id}/state ────────────
class LeadStateUpdate(BaseModel):
    stage: str
    notes: Optional[str] = None


# ── RESPONSE ──────────────────────────────────────────
class LeadResponse(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id:               uuid.UUID
    loan_id:          Optional[str]       = None   # LD-1001
    contact_id:       Optional[uuid.UUID] = None
    stage:            str
    assigned_to:      Optional[uuid.UUID] = None
    assigned_to_name: Optional[str]       = None
    created_at:       datetime
    updated_at:       datetime


# ── LIST ITEM (lighter) ───────────────────────────────
class LeadListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:               uuid.UUID
    loan_id:          Optional[str] = None
    name:             str
    email:            Optional[str] = None
    phone:            Optional[str] = None
    pan_number:       Optional[str] = None
    city:             Optional[str] = None
    loan_type:        Optional[str] = None
    amount:           Optional[int] = None
    stage:            str
    cibil_score:      Optional[int] = None
    employment_type:  Optional[str] = None
    assigned_to:      Optional[uuid.UUID] = None
    assigned_to_name: Optional[str]       = None
    bank_name:        Optional[str]       = None   # ← NEW: set when sent to bank
    created_at:       datetime
    updated_at:       datetime
# ── FILTERS ───────────────────────────────────────────
class LeadFilters(BaseModel):
    search:      Optional[str]       = None   # name | email | pan | city
    stage:       Optional[str]       = None
    loan_type:   Optional[str]       = None
    assigned_to: Optional[uuid.UUID] = None
    page:        int = 1
    limit:       int = 50

from pydantic import BaseModel

class SendToBankRequest(BaseModel):
    bank_name: str


class AssignToBankerRequest(BaseModel):
    bank_name: str
    banker_id: UUID