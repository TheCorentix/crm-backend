# app/schemas/loan.py
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


VALID_STATES = [
    "sent_to_bank",
    "bank_processing",
    "bank_approved",
    "bank_rejected",
    "loan_disbursed",
    "deal_lost",
    "default",
]


# ── BASE ──────────────────────────────────────────────
class LoanBase(BaseModel):
    contact_name:          Optional[str]      = None
    contact_email:         Optional[EmailStr] = None
    phone:                 Optional[str]      = None
    pan_number:            Optional[str]      = None
    loan_amount_requested: Optional[int]      = None
    loan_amount_approved:  Optional[int]      = None
    disbursed_amount:      Optional[int]      = None
    credit_score:          Optional[int]      = None
    bank_name:             Optional[str]      = None
    bank_reference:        Optional[str]      = None
    notes:                 Optional[str]      = None


# ── CREATE — called internally when lead → sent to bank
class LoanCreate(LoanBase):
    lead_id:     Optional[uuid.UUID] = None
    assigned_to: Optional[uuid.UUID] = None
    stage:       str = "sent_to_bank"


# ── UPDATE — PUT /loans/{id} ──────────────────────────
class LoanUpdate(BaseModel):
    loan_amount_approved: Optional[int]       = None
    bank_name:            Optional[str]       = None
    bank_reference:       Optional[str]       = None
    rejection_reason:     Optional[str]       = None
    notes:                Optional[str]       = None
    assigned_to:          Optional[uuid.UUID] = None


# ── STATE CHANGE — PATCH /loans/{id}/state ────────────
class LoanStateUpdate(BaseModel):
    stage:            str
    rejection_reason: Optional[str] = None
    disbursed_amount: Optional[int] = None
    notes:            Optional[str] = None


# ── RESPONSE ──────────────────────────────────────────
class LoanResponse(LoanBase):
    model_config = ConfigDict(from_attributes=True)

    id:               uuid.UUID
    loan_id:          Optional[str]       = None   # PS-2001
    lead_id:          Optional[uuid.UUID] = None
    stage:            str
    rejection_reason: Optional[str]       = None
    assigned_to:      Optional[uuid.UUID] = None
    assigned_to_name: Optional[str]       = None
    state_updated_at: datetime
    disbursed_at:     Optional[datetime]  = None
    created_at:       datetime


# ── LIST ITEM (lighter) ───────────────────────────────
class LoanListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                    uuid.UUID
    loan_id:               Optional[str] = None
    contact_name:          Optional[str] = None
    contact_email:         Optional[str] = None
    phone:                 Optional[str] = None
    pan_number:            Optional[str] = None
    stage:                 str
    loan_amount_requested: Optional[int] = None
    credit_score:          Optional[int] = None
    bank_name:             Optional[str] = None
    assigned_to_name:      Optional[str] = None
    state_updated_at:      datetime
    created_at:            datetime


# ── FILTERS ───────────────────────────────────────────
class LoanFilters(BaseModel):
    search:      Optional[str]       = None   # name | email | loan_id
    stage:       Optional[str]       = None
    bank_name:   Optional[str]       = None
    assigned_to: Optional[uuid.UUID] = None
    page:        int = 1
    limit:       int = 50
