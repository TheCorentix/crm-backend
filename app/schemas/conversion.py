# app/schemas/conversion.py
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


VALID_CONTACT_STATES = [
    "New", "Contacted", "Qualified", "Unqualified",
    "new_contact", "attempted_contact", "contacted",
    "documents_pending", "not_interested", "converted",
]

VALID_LEAD_STAGES = [
    "New Lead", "In Progress", "Under Review", "Documents Pending",
    "Qualified", "Not Qualified",
    "new_lead", "opportunity_open", "opportunity_in_progress",
    "opportunity_submitted", "under_review", "documents_pending",
    "qualified", "not_qualified",
]


class ContactStateUpdate(BaseModel):
    status: str
    notes: Optional[str] = None




class ConversionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    message: str
    from_type: str
    to_type: str
    from_id: uuid.UUID
    to_id: uuid.UUID
    from_ref: Optional[str] = None
    to_ref: Optional[str] = None
    converted_at: datetime
    converted_by: uuid.UUID
    missing_fields: Optional[list[str]] = None


class EligibilityResponse(BaseModel):
    eligible: bool
    missing_fields: list[str]
    has_pan: bool
    has_phone: bool
    has_email: bool
    warnings: list[str]