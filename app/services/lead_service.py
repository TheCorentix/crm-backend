# app/services/lead_service.py
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead
from app.models.loan import Loan
from app.models.user import ActivityLog, User
from app.schemas.lead import LeadCreate, LeadUpdate, LeadStateUpdate


class LeadService:

    @staticmethod
    async def _next_loan_id(db: AsyncSession) -> str:
        result = await db.execute(select(func.count()).select_from(Lead))
        count  = result.scalar() or 0
        return f"LD-{1001 + count}"

    @staticmethod
    async def _next_ps_id(db: AsyncSession) -> str:
        result = await db.execute(select(func.count()).select_from(Loan))
        count  = result.scalar() or 0
        return f"PS-{2001 + count}"

    @staticmethod
    async def _log(
        db:        AsyncSession,
        user_id:   uuid.UUID,
        action:    str,
        entity_id: uuid.UUID,
    ) -> None:
        db.add(ActivityLog(
            user_id=user_id,
            action=action,
            entity_type="lead",
            entity_id=entity_id,
        ))

    @staticmethod
    async def list_leads(
        db:          AsyncSession,
        search:      Optional[str],
        stage:       Optional[str],
        loan_type:   Optional[str],
        assigned_to: Optional[uuid.UUID],
        page:        int,
        limit:       int,
    ) -> List[Lead]:
        q = select(Lead).options(
            selectinload(Lead.assignee),
            selectinload(Lead.loan),
        )

        if search:
            term = f"%{search.lower()}%"
            q = q.where(
                or_(
                    func.lower(Lead.name).like(term),
                    func.lower(Lead.email).like(term),
                    func.lower(Lead.pan_number).like(term),
                    func.lower(Lead.city).like(term),
                    func.lower(Lead.loan_id).like(term),
                )
            )
        if stage:
            q = q.where(Lead.stage == stage)
        if loan_type:
            q = q.where(Lead.loan_type == loan_type)
        if assigned_to:
            q = q.where(Lead.assigned_to == assigned_to)

        q = q.order_by(Lead.created_at.desc())
        q = q.offset((page - 1) * limit).limit(limit)

        result = await db.execute(q)
        leads  = result.scalars().all()

        for lead in leads:
            lead.assigned_to_name = lead.assignee.name if lead.assignee else None
            lead.bank_name        = lead.loan.bank_name if lead.loan else None

        return leads

    @staticmethod
    async def get_by_id(db: AsyncSession, lead_id: uuid.UUID) -> Optional[Lead]:
        result = await db.execute(
            select(Lead)
            .options(selectinload(Lead.assignee))
            .where(Lead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if lead and lead.assignee:
            lead.assigned_to_name = lead.assignee.name
        return lead

    @staticmethod
    async def create_lead(
        db:         AsyncSession,
        payload:    LeadCreate,
        created_by: uuid.UUID,
    ) -> Lead:
        loan_id = await LeadService._next_loan_id(db)

        lead = Lead(
            loan_id         = loan_id,
            contact_id      = payload.contact_id,
            name            = payload.name,
            email           = payload.email,
            phone           = payload.phone,
            pan_number      = payload.pan_number,
            city            = payload.city,
            loan_type       = payload.loan_type,
            amount          = payload.amount,
            stage           = payload.stage,
            source          = payload.source,
            cibil_score     = payload.cibil_score,
            employment_type = payload.employment_type,
            monthly_income  = payload.monthly_income,
            notes           = payload.notes,
            assigned_to     = payload.assigned_to,
        )
        db.add(lead)
        await db.flush()

        await LeadService._log(
            db, created_by,
            f"Lead {loan_id} created for {lead.name}",
            lead.id,
        )
        await db.commit()
        await db.refresh(lead)
        return lead

    @staticmethod
    async def update_lead(
        db:      AsyncSession,
        lead_id: uuid.UUID,
        payload: LeadUpdate,
    ) -> Optional[Lead]:
        lead = await LeadService.get_by_id(db, lead_id)
        if not lead:
            return None

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(lead, field, value)

        lead.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(lead)
        return lead

    @staticmethod
    async def delete_lead(db: AsyncSession, lead_id: uuid.UUID) -> bool:
        lead = await LeadService.get_by_id(db, lead_id)
        if not lead:
            return False
        await db.delete(lead)
        await db.commit()
        return True

    @staticmethod
    async def update_state(
        db:      AsyncSession,
        lead_id: uuid.UUID,
        payload: LeadStateUpdate,
        user_id: uuid.UUID,
    ) -> Optional[Lead]:
        lead = await LeadService.get_by_id(db, lead_id)
        if not lead:
            return None

        old_stage  = lead.stage
        lead.stage = payload.stage
        if payload.notes:
            lead.notes = payload.notes
        lead.updated_at = datetime.now(timezone.utc)

        await LeadService._log(
            db, user_id,
            f"Lead {lead.loan_id} stage: {old_stage} → {payload.stage}",
            lead.id,
        )
        await db.commit()
        await db.refresh(lead)
        return lead

    @staticmethod
    async def send_to_bank(
        db:        AsyncSession,
        lead_id:   uuid.UUID,
        bank_name: str,
        banker_id: uuid.UUID,
        user_id:   uuid.UUID,
    ) -> Optional[Lead]:
        """
        Promote a Qualified lead to post-sales pipeline:
        1. Verify the banker is a valid active bank_admin
        2. Move lead stage → Sent to Bank
        3. Create a Loan record with banker_id set and stage = submitted_to_bank
        Only the assigned banker can see this loan in their dashboard.
        """
        lead = await LeadService.get_by_id(db, lead_id)
        if not lead:
            return None

        # Only Qualified leads can be sent to bank
        if lead.stage not in ("Qualified", "qualified"):
            return None

        # Verify banker exists and is active bank_admin
        banker_result = await db.execute(
            select(User).where(
                User.id     == banker_id,
                User.role   == "bank_admin",
                User.status == "active",
            )
        )
        banker = banker_result.scalar_one_or_none()
        if not banker:
            return None

        # Update lead stage
        lead.stage      = "Sent to Bank"
        lead.updated_at = datetime.now(timezone.utc)

        # Create loan record
        ps_id = await LeadService._next_ps_id(db)
        loan  = Loan(
            loan_id               = ps_id,
            lead_id               = lead.id,
            contact_name          = lead.name,
            contact_email         = lead.email,
            phone                 = lead.phone,
            pan_number            = lead.pan_number,
            loan_amount_requested = lead.amount,
            credit_score          = lead.cibil_score,
            bank_name             = bank_name,
            banker_id             = banker_id,
            stage                 = "submitted_to_bank",
            assigned_to           = lead.assigned_to,
        )
        db.add(loan)

        await LeadService._log(
            db, user_id,
            f"Lead {lead.loan_id} sent to {bank_name} (banker: {banker.name}) → Loan {ps_id} created",
            lead.id,
        )

        await db.commit()
        await db.refresh(lead)
        return lead

    @staticmethod
    async def assign_lead_to_banker(
        db:           AsyncSession,
        lead_id:      uuid.UUID,
        bank_name:    str,
        banker_id:    uuid.UUID,
        current_user: User,
    ) -> dict:
        """
        Assign (or re-assign) a lead to a specific banker within a bank.
        - If a Loan already exists for this lead → update banker_id, bank_name, stage.
        - If no Loan exists → create a new Loan record.
        - Updates lead stage → Sent to Bank.
        - Validates that the banker belongs to the specified bank.
        Unlike send_to_bank, this does NOT restrict to Qualified stage only,
        allowing re-assignment of already-routed leads.
        """
        # 1. Fetch the lead
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # 2. Validate banker — must be active bank_admin belonging to the given bank
        banker_result = await db.execute(
            select(User).where(
                User.id        == banker_id,
                User.role      == "bank_admin",
                User.bank_name == bank_name,
                User.status    == "active",
            )
        )
        banker = banker_result.scalar_one_or_none()
        if not banker:
            raise HTTPException(
                status_code=400,
                detail="Banker not found or does not belong to the specified bank",
            )

        # 3. Check if a Loan already exists for this lead
        loan_result = await db.execute(select(Loan).where(Loan.lead_id == lead_id))
        loan = loan_result.scalar_one_or_none()

        if loan:
            # Re-assign existing loan to new banker
            old_banker_id  = loan.banker_id
            loan.banker_id = banker_id
            loan.bank_name = bank_name
            loan.stage     = "submitted_to_bank"

            await LeadService._log(
                db, current_user.id,
                f"Lead {lead.loan_id} re-assigned to {banker.name} at {bank_name} "
                f"(Loan {loan.loan_id} updated)",
                lead.id,
            )
        else:
            # Create a fresh Loan record
            ps_id = await LeadService._next_ps_id(db)
            loan  = Loan(
                loan_id               = ps_id,
                lead_id               = lead.id,
                contact_name          = lead.name,
                contact_email         = lead.email,
                phone                 = lead.phone,
                pan_number            = lead.pan_number,
                loan_amount_requested = lead.amount,
                credit_score          = lead.cibil_score,
                bank_name             = bank_name,
                banker_id             = banker_id,
                stage                 = "submitted_to_bank",
                assigned_to           = current_user.id,
            )
            db.add(loan)

            await LeadService._log(
                db, current_user.id,
                f"Lead {lead.loan_id} assigned to {banker.name} at {bank_name} "
                f"→ Loan {ps_id} created",
                lead.id,
            )

        # 4. Update lead stage
        lead.stage      = "Sent to Bank"
        lead.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(loan)

        return {
            "message"       : f"Lead successfully assigned to {banker.name} at {bank_name}",
            "loan_id"       : str(loan.id),
            "loan_reference": loan.loan_id,
            "banker_id"     : str(banker_id),
            "banker_name"   : banker.name,
            "bank_name"     : bank_name,
            "stage"         : loan.stage,
        }