# app/services/disbursed_service.py
import uuid
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.loan import Loan
from app.models.lead import Lead
from app.models.user import User


class DisbursedService:

    @staticmethod
    async def list_disbursed(
        db:        AsyncSession,
        search:    Optional[str]      = None,
        bank_name: Optional[str]      = None,
        page:      int                = 1,
        limit:     int                = 50,
    ) -> list[dict]:
        """
        List all loans that have been disbursed by banks.
        Includes full lead + loan + banker details.
        A loan is considered disbursed when:
          - disbursed_amount is set, OR
          - stage is bank_approved / partially_approved
        """
        q = (
            select(Loan)
            .options(
                selectinload(Loan.lead),
                selectinload(Loan.banker),
                selectinload(Loan.assignee),
            )
            .where(
                or_(
                    Loan.disbursed_amount.isnot(None),
                    Loan.stage.in_(["bank_approved", "partially_approved"]),
                )
            )
        )

        if search:
            term = f"%{search.lower()}%"
            q = q.where(
                or_(
                    func.lower(Loan.contact_name).like(term),
                    func.lower(Loan.contact_email).like(term),
                    func.lower(Loan.phone).like(term),
                    func.lower(Loan.pan_number).like(term),
                    func.lower(Loan.loan_id).like(term),
                    func.lower(Loan.bank_name).like(term),
                )
            )

        if bank_name:
            q = q.where(Loan.bank_name == bank_name)

        q = q.order_by(Loan.state_updated_at.desc())
        q = q.offset((page - 1) * limit).limit(limit)

        result = await db.execute(q)
        loans  = result.scalars().all()

        return [DisbursedService._serialize(loan) for loan in loans]

    @staticmethod
    async def get_disbursed_by_id(
        db:      AsyncSession,
        loan_id: uuid.UUID,
    ) -> Optional[dict]:
        """
        Get full details of a single disbursed loan by ID.
        """
        result = await db.execute(
            select(Loan)
            .options(
                selectinload(Loan.lead),
                selectinload(Loan.banker),
                selectinload(Loan.assignee),
            )
            .where(
                Loan.id == loan_id,
                or_(
                    Loan.disbursed_amount.isnot(None),
                    Loan.stage.in_(["bank_approved", "partially_approved"]),
                ),
            )
        )
        loan = result.scalar_one_or_none()
        if not loan:
            return None
        return DisbursedService._serialize(loan)

    @staticmethod
    async def get_summary(db: AsyncSession) -> dict:
        """
        Summary stats for disbursed loans.
        Total count, total disbursed amount, per-bank breakdown.
        """
        # Total disbursed count + amount
        total_q = await db.execute(
            select(
                func.count(Loan.id).label("total"),
                func.sum(Loan.disbursed_amount).label("total_amount"),
                func.sum(Loan.loan_amount_requested).label("total_requested"),
            )
            .where(
                or_(
                    Loan.disbursed_amount.isnot(None),
                    Loan.stage.in_(["bank_approved", "partially_approved"]),
                )
            )
        )
        total_row = total_q.one()

        # Per-bank breakdown
        bank_q = await db.execute(
            select(
                Loan.bank_name,
                func.count(Loan.id).label("count"),
                func.sum(Loan.disbursed_amount).label("amount"),
            )
            .where(
                or_(
                    Loan.disbursed_amount.isnot(None),
                    Loan.stage.in_(["bank_approved", "partially_approved"]),
                )
            )
            .group_by(Loan.bank_name)
            .order_by(func.count(Loan.id).desc())
        )
        bank_rows = bank_q.all()

        return {
            "total_disbursed"       : total_row.total or 0,
            "total_disbursed_amount": total_row.total_amount or 0,
            "total_requested_amount": total_row.total_requested or 0,
            "by_bank": [
                {
                    "bank_name": row.bank_name,
                    "count"    : row.count,
                    "amount"   : row.amount or 0,
                }
                for row in bank_rows
            ],
        }

    @staticmethod
    def _serialize(loan: Loan) -> dict:
        """Build the full lead-to-disbursement response dict."""
        lead = loan.lead

        return {
            # ── Loan info ──────────────────────────────
            "loan_id"              : str(loan.id),
            "loan_reference"       : loan.loan_id,
            "stage"                : loan.stage,
            "loan_amount_requested": loan.loan_amount_requested,
            "loan_amount_approved" : loan.loan_amount_approved,
            "disbursed_amount"     : loan.disbursed_amount,
            "credit_score"         : loan.credit_score,
            "bank_name"            : loan.bank_name,
            "bank_reference"       : loan.bank_reference,
            "last_comment"         : loan.last_comment,
            "notes"                : loan.notes,
            "created_at"           : loan.created_at.isoformat() if loan.created_at else None,
            "state_updated_at"     : loan.state_updated_at.isoformat() if loan.state_updated_at else None,
            "disbursed_at"         : loan.disbursed_at.isoformat() if loan.disbursed_at else None,

            # ── Applicant info (from loan snapshot) ───
            "contact_name" : loan.contact_name,
            "contact_email": loan.contact_email,
            "phone"        : loan.phone,
            "pan_number"   : loan.pan_number,

            # ── Lead journey info ─────────────────────
            "lead": {
                "lead_id"        : str(lead.id) if lead else None,
                "lead_reference" : lead.loan_id if lead else None,
                "name"           : lead.name if lead else None,
                "email"          : lead.email if lead else None,
                "phone"          : lead.phone if lead else None,
                "pan_number"     : lead.pan_number if lead else None,
                "city"           : lead.city if lead else None,
                "loan_type"      : lead.loan_type if lead else None,
                "amount_requested": lead.amount if lead else None,
                "cibil_score"    : lead.cibil_score if lead else None,
                "employment_type": lead.employment_type if lead else None,
                "monthly_income" : lead.monthly_income if lead else None,
                "source"         : lead.source if lead else None,
                "lead_stage"     : lead.stage if lead else None,
                "lead_created_at": lead.created_at.isoformat() if lead and lead.created_at else None,
            } if lead else None,

            # ── Banker info ───────────────────────────
            "banker": {
                "banker_id"  : str(loan.banker.id) if loan.banker else None,
                "banker_name": loan.banker.name if loan.banker else None,
                "banker_email": loan.banker.email if loan.banker else None,
                "bank_name"  : loan.banker.bank_name if loan.banker else None,
                "branch"     : loan.banker.branch if loan.banker else None,
            } if loan.banker else None,

            # ── Pre-sales user who routed the lead ────
            "routed_by": {
                "user_id": str(loan.assignee.id) if loan.assignee else None,
                "name"   : loan.assignee.name if loan.assignee else None,
                "email"  : loan.assignee.email if loan.assignee else None,
                "role"   : loan.assignee.role if loan.assignee else None,
            } if loan.assignee else None,
        }