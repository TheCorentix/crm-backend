# app/services/bank_logging_service.py
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead
from app.models.loan import Loan
from app.models.user import User, ActivityLog


class BankLoggingService:

    # ── Helper: generate next PS id ───────────────────
    @staticmethod
    async def _next_ps_id(db: AsyncSession) -> str:
        from sqlalchemy import func
        result = await db.execute(select(func.count()).select_from(Loan))
        count  = result.scalar() or 0
        return f"PS-{2001 + count}"

    # ── Helper: activity log ──────────────────────────
    @staticmethod
    async def _log(
        db:        AsyncSession,
        user_id:   uuid.UUID,
        action:    str,
        entity_id: uuid.UUID,
    ) -> None:
        db.add(ActivityLog(
            user_id     = user_id,
            action      = action,
            entity_type = "loan",
            entity_id   = entity_id,
        ))

    # ── 1. Log lead to bank (no banker yet) ───────────
    @staticmethod
    async def log_to_bank(
        db:        AsyncSession,
        lead_id:   uuid.UUID,
        bank_name: str,
        user_id:   uuid.UUID,
    ) -> dict:
        """
        Stage 1 of the secure bank routing flow.
        - Only Qualified leads can be logged
        - Creates a Loan with bank_name set, banker_id = NULL
        - Lead stage → Logged to Bank
        - Banker cannot see this loan yet (banker_id is NULL)
        - Personal data is stored but NOT exposed to any banker
        """

        # Fetch lead
        result = await db.execute(
            select(Lead)
            .options(selectinload(Lead.assignee))
            .where(Lead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Only Qualified leads
        if lead.stage not in ("Qualified", "qualified"):
            raise HTTPException(
                status_code=400,
                detail=f"Only Qualified leads can be logged to bank. Current stage: '{lead.stage}'"
            )

        # Check if loan already exists for this lead
        existing = await db.execute(
            select(Loan).where(Loan.lead_id == lead_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="A loan record already exists for this lead. Use assign-banker to assign a banker."
            )

        # Validate bank name
        from app.schemas.user import normalize_bank_name
        try:
            bank_name = normalize_bank_name(bank_name)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid bank name: {bank_name}")

        # Create loan — banker_id is NULL (banker cannot see this yet)
        ps_id = await BankLoggingService._next_ps_id(db)
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
            banker_id             = None,           # ← no banker yet
            stage                 = "logged_to_bank",
            assigned_to           = lead.assigned_to,
        )
        db.add(loan)
        await db.flush()

        # Update lead stage
        lead.stage      = "Logged to Bank"
        lead.updated_at = datetime.now(timezone.utc)

        await BankLoggingService._log(
            db, user_id,
            f"Lead {lead.loan_id} logged to {bank_name} → Loan {ps_id} created (unassigned)",
            loan.id,
        )

        await db.commit()
        await db.refresh(loan)

        return {
            "message"         : f"Lead successfully logged to {bank_name}. Awaiting banker assignment.",
            "loan_id"         : str(loan.id),
            "loan_reference"  : loan.loan_id,
            "bank_name"       : bank_name,
            "stage"           : loan.stage,
            "banker_assigned" : False,
        }

    # ── 2. Assign banker to logged loan ───────────────
    @staticmethod
    async def assign_banker(
        db:           AsyncSession,
        loan_id:      uuid.UUID,
        banker_id:    uuid.UUID,
        current_user: User,
    ) -> dict:
        """
        Stage 2 of the secure bank routing flow.
        - Admin/Super Admin assigns a banker to an unassigned loan
        - Validates banker belongs to the loan's bank
        - Sets banker_id → banker can now see this loan
        - Loan stage → submitted_to_bank
        """

        # Fetch loan
        result = await db.execute(
            select(Loan).where(Loan.id == loan_id)
        )
        loan = result.scalar_one_or_none()
        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found")

        # Must be in logged_to_bank stage
        if loan.stage != "logged_to_bank":
            raise HTTPException(
                status_code=400,
                detail=f"Loan must be in 'logged_to_bank' stage to assign a banker. Current stage: '{loan.stage}'"
            )

        # Must not already have a banker
        if loan.banker_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Loan already has a banker assigned. Use reassign endpoint to change banker."
            )

        # Validate banker — must be active bank_admin belonging to the same bank
        banker_result = await db.execute(
            select(User).where(
                User.id        == banker_id,
                User.role      == "bank_admin",
                User.bank_name == loan.bank_name,
                User.status    == "active",
            )
        )
        banker = banker_result.scalar_one_or_none()
        if not banker:
            raise HTTPException(
                status_code=400,
                detail=f"Banker not found, inactive, or does not belong to {loan.bank_name}",
            )

        # Assign banker and update stage
        loan.banker_id        = banker_id
        loan.stage            = "submitted_to_bank"
        loan.state_updated_at = datetime.now(timezone.utc)

        await BankLoggingService._log(
            db, current_user.id,
            f"Loan {loan.loan_id} assigned to {banker.name} at {loan.bank_name} "
            f"→ stage: submitted_to_bank",
            loan.id,
        )

        await db.commit()
        await db.refresh(loan)

        return {
            "message"        : f"Loan successfully assigned to {banker.name} at {loan.bank_name}",
            "loan_id"        : str(loan.id),
            "loan_reference" : loan.loan_id,
            "bank_name"      : loan.bank_name,
            "banker_id"      : str(banker_id),
            "banker_name"    : banker.name,
            "stage"          : loan.stage,
            "banker_assigned": True,
        }

    # ── 3. List unassigned loans (pending assignment) ─
    @staticmethod
    async def list_unassigned_loans(
        db:        AsyncSession,
        bank_name: Optional[str] = None,
        page:      int           = 1,
        limit:     int           = 50,
    ) -> list[dict]:
        """
        List all loans in 'logged_to_bank' stage with no banker assigned.
        Admin/Super Admin uses this to see what needs assignment.
        """
        q = select(Loan).where(
            Loan.stage     == "logged_to_bank",
            Loan.banker_id == None,
        )

        if bank_name:
            from app.schemas.user import normalize_bank_name
            try:
                bank_name = normalize_bank_name(bank_name)
                q = q.where(Loan.bank_name == bank_name)
            except ValueError:
                pass

        q = q.order_by(Loan.created_at.desc())
        q = q.offset((page - 1) * limit).limit(limit)

        result = await db.execute(q)
        loans  = result.scalars().all()

        return [
            {
                "loan_id"              : str(loan.id),
                "loan_reference"       : loan.loan_id,
                "contact_name"         : loan.contact_name,
                "loan_amount_requested": loan.loan_amount_requested,
                "bank_name"            : loan.bank_name,
                "stage"                : loan.stage,
                "created_at"           : loan.created_at.isoformat(),
                # NOTE: PAN, email, phone intentionally excluded here
                # Full data only visible after banker assignment
            }
            for loan in loans
        ]