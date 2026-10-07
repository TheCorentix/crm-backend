# app/services/conversion_service.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.lead import Lead
from app.models.user import ActivityLog
from app.schemas.conversion import (
    ConversionResponse,
    EligibilityResponse,
    VALID_CONTACT_STATES,
    VALID_LEAD_STAGES,
)


class ConversionService:
    @staticmethod
    async def _next_loan_id(db: AsyncSession) -> str:
        result = await db.execute(select(func.max(Lead.loan_id)))
        last_id = result.scalar()

        if last_id:
            number = int(last_id.split("-")[1]) + 1
        else:
            number = 1001

        return f"LD-{number}"

    @staticmethod
    async def _next_contact_id(db: AsyncSession) -> str:
        result = await db.execute(select(func.max(Contact.contact_id)))
        last_id = result.scalar()

        if last_id:
            number = int(last_id.split("-")[1]) + 1
        else:
            number = 1001

        return f"CNT-{number}"

    @staticmethod
    async def _log(
        db: AsyncSession,
        user_id: uuid.UUID,
        action: str,
        entity_id: uuid.UUID,
        entity_type: str = "conversion",
    ) -> None:
        db.add(
            ActivityLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )

    @staticmethod
    async def check_contact_eligibility(
        db: AsyncSession,
        contact_id: uuid.UUID,
    ) -> EligibilityResponse:
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        contact = result.scalar_one_or_none()

        if not contact:
            return EligibilityResponse(
                eligible=False,
                missing_fields=["contact not found"],
                has_pan=False,
                has_phone=False,
                has_email=False,
                warnings=["Contact record does not exist"],
            )

        missing = []
        warnings = []

        if not contact.name:
            missing.append("name")
        if not contact.email:
            missing.append("email")
        if not contact.phone:
            missing.append("phone")

        if not contact.city:
            warnings.append("city is missing — recommended for lead")
        if not getattr(contact, "loan_type", None):
            warnings.append("loan_type is missing — recommended for lead")
        if not getattr(contact, "amount", None):
            warnings.append("loan amount is missing — recommended for lead")

        return EligibilityResponse(
            eligible=len(missing) == 0,
            missing_fields=missing,
            has_pan=bool(getattr(contact, "pan_number", None)),
            has_phone=bool(contact.phone),
            has_email=bool(contact.email),
            warnings=warnings,
        )

    @staticmethod
    async def update_contact_status(
        db: AsyncSession,
        contact_id: uuid.UUID,
        new_status: str,
        notes: Optional[str],
        user_id: uuid.UUID,
    ) -> Optional[Contact]:
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        contact = result.scalar_one_or_none()
        if not contact:
            return None

        if new_status not in VALID_CONTACT_STATES:
            raise ValueError(
                f"Invalid status '{new_status}'. Valid: {VALID_CONTACT_STATES}"
            )

        old_status = contact.status
        contact.status = new_status
        if notes:
            contact.notes = notes
        contact.updated_at = datetime.now(timezone.utc)

        await ConversionService._log(
            db,
            user_id,
            f"Contact {contact.contact_id} status: {old_status} -> {new_status}",
            contact.id,
            entity_type="contact",
        )
        await db.commit()
        await db.refresh(contact)
        return contact

    @staticmethod
    async def update_lead_stage(
        db: AsyncSession,
        lead_id: uuid.UUID,
        stage: str,
        notes: Optional[str],
        user_id: uuid.UUID,
    ) -> Optional[Lead]:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            return None

        if stage not in VALID_LEAD_STAGES:
            raise ValueError(
                f"Invalid stage '{stage}'. Valid: {VALID_LEAD_STAGES}"
            )

        old_stage = lead.stage
        lead.stage = stage
        if notes:
            lead.notes = notes
        lead.updated_at = datetime.now(timezone.utc)

        await ConversionService._log(
            db,
            user_id,
            f"Lead {lead.loan_id} stage: {old_stage} -> {stage}",
            lead.id,
            entity_type="lead",
        )
        await db.commit()
        await db.refresh(lead)
        return lead

    @staticmethod
    async def contact_to_lead(
        db: AsyncSession,
        contact_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ConversionResponse:
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        contact = result.scalar_one_or_none()

        if not contact:
            raise ValueError("Contact not found")

        existing = await db.execute(select(Lead).where(Lead.contact_id == contact_id))
        if existing.scalar_one_or_none():
            raise ValueError("Contact has already been converted to a Lead")

        now = datetime.now(timezone.utc)
        loan_id = await ConversionService._next_loan_id(db)

        missing = []
        if not getattr(contact, "loan_type", None):
            missing.append("loan_type")
        if not getattr(contact, "pan_number", None):
            missing.append("pan_number")
        if not getattr(contact, "cibil_score", None):
            missing.append("cibil_score")

        lead = Lead(
            loan_id=loan_id,
            contact_id=contact.id,
            name=contact.name,
            email=contact.email,
            phone=contact.phone,
            city=contact.city,
            source=contact.source,
            loan_type=getattr(contact, "loan_type", None),
            amount=getattr(contact, "amount", None),
            pan_number=getattr(contact, "pan_number", None),
            cibil_score=getattr(contact, "cibil_score", None),
            employment_type=getattr(contact, "employment_type", None),
            monthly_income=getattr(contact, "monthly_income", None),
            assigned_to=getattr(contact, "assigned_to", None),
            notes=contact.notes,
            stage="new_lead",
            created_at=now,
            updated_at=now,
        )
        db.add(lead)

        contact.status = "converted"
        contact.updated_at = now

        await db.flush()

        await ConversionService._log(
            db=db,
            user_id=user_id,
            action=f"Contact {contact.contact_id} converted to Lead {loan_id}",
            entity_id=lead.id,
        )

        await db.commit()
        await db.refresh(lead)

        return ConversionResponse(
            success=True,
            message=f"Contact {contact.contact_id} successfully converted to Lead {loan_id}",
            from_type="contact",
            to_type="lead",
            from_id=contact.id,
            to_id=lead.id,
            from_ref=contact.contact_id,
            to_ref=loan_id,
            converted_at=now,
            converted_by=user_id,
            missing_fields=missing or None,
        )