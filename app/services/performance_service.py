# app/services/performance_service.py
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.loan import Loan
from app.models.user import User


class PerformanceService:

    @staticmethod
    async def get_team_performance(db: AsyncSession) -> list[dict]:

        pre_q = await db.execute(
            select(
                User.id,
                User.name,
                User.role,
                func.count(Lead.id).label("leads"),
                func.sum(
                    case((Lead.stage == "Qualified", 1), else_=0)
                ).label("qualified"),
                func.sum(
                    case((Lead.stage == "Sent to Bank", 1), else_=0)
                ).label("sent_to_bank"),
            )
            .join(Lead, Lead.assigned_to == User.id, isouter=True)
            .where(User.role.in_(["pre_sales_admin", "pre_sales_user"]))
            .group_by(User.id, User.name, User.role)
        )
        pre_rows = pre_q.all()

        post_q = await db.execute(
            select(
                User.id,
                User.name,
                User.role,
                func.count(Loan.id).label("loans"),
                func.sum(
                    case(
                        (
                            Loan.stage.in_([
                                "bank_approved",
                                "partially_approved",
                                "loan_disbursed"
                            ]),
                            1
                        ),
                        else_=0,
                    )
                ).label("approved"),
                func.sum(
                    case((Loan.disbursed_amount.isnot(None), 1), else_=0)
                ).label("disbursed"),
            )
            .join(Loan, Loan.assigned_to == User.id, isouter=True)
            .where(User.role.in_(["post_sales_admin"]))
            .group_by(User.id, User.name, User.role)
        )
        post_rows = post_q.all()

        bank_q = await db.execute(
            select(
                User.id,
                User.name,
                User.role,
                func.count(Loan.id).label("loans"),
                func.sum(
                    case(
                        (
                            Loan.stage.in_([
                                "bank_approved",
                                "partially_approved",
                                "loan_disbursed"
                            ]),
                            1
                        ),
                        else_=0,
                    )
                ).label("approved"),
                func.sum(
                    case((Loan.disbursed_amount.isnot(None), 1), else_=0)
                ).label("disbursed"),
            )
            .join(Loan, Loan.banker_id == User.id, isouter=True)
            .where(User.role == "bank_admin")
            .group_by(User.id, User.name, User.role)
        )
        bank_rows = bank_q.all()

        result = []

        for row in pre_rows:
            leads = row.leads or 0
            qualified = row.qualified or 0
            conv_pct = round((qualified / leads * 100), 1) if leads > 0 else 0

            result.append({
                "name": row.name,
                "role": _format_role(row.role),
                "leads": leads,
                "qualified": qualified,
                "disbursed": None,
                "conv_pct": conv_pct,
                "vs_target": None,
            })

        for row in post_rows:
            disbursed = row.disbursed or 0
            result.append({
                "name": row.name,
                "role": _format_role(row.role),
                "leads": None,
                "qualified": None,
                "disbursed": disbursed,
                "conv_pct": None,
                "vs_target": None,
            })

        for row in bank_rows:
            disbursed = row.disbursed or 0
            result.append({
                "name": row.name,
                "role": _format_role(row.role),
                "leads": None,
                "qualified": None,
                "disbursed": disbursed,
                "conv_pct": None,
                "vs_target": None,
            })

        return result


    @staticmethod
    async def get_bank_performance(db: AsyncSession) -> list[dict]:

        bankers_q = await db.execute(
            select(
                User.id,
                User.name,
                User.bank_name,
            )
            .where(
                User.role == "bank_admin",
                User.status == "active",
                User.bank_name.isnot(None),
            )
            .order_by(User.bank_name, User.name)
        )
        bankers = bankers_q.all()

        loans_q = await db.execute(
            select(
                Loan.banker_id,
                func.count(Loan.id).label("sent"),
                func.sum(
                    case(
                        (
                            Loan.stage.in_([
                                "bank_approved",
                                "partially_approved",
                                "loan_disbursed"
                            ]),
                            1
                        ),
                        else_=0,
                    )
                ).label("approved"),
                func.sum(
                    case((Loan.stage == "bank_rejected", 1), else_=0)
                ).label("rejected"),
            )
            .where(Loan.banker_id.isnot(None))
            .group_by(Loan.banker_id)
        )

        loan_stats: dict = {}
        for row in loans_q.all():
            loan_stats[str(row.banker_id)] = {
                "sent": row.sent or 0,
                "approved": row.approved or 0,
                "rejected": row.rejected or 0,
            }

        banks: dict[str, dict] = {}

        for banker in bankers:
            bank = banker.bank_name

            if bank not in banks:
                banks[bank] = {
                    "bank": bank,
                    "sent": 0,
                    "approved": 0,
                    "rejected": 0,
                    "approval_rate": 0,
                    "bankers": [],
                }

            stats = loan_stats.get(str(banker.id), {"sent": 0, "approved": 0, "rejected": 0})

            sent = stats["sent"]
            approved = stats["approved"]
            rejected = stats["rejected"]

            banks[bank]["sent"] += sent
            banks[bank]["approved"] += approved
            banks[bank]["rejected"] += rejected

            banks[bank]["bankers"].append({
                "banker_id": str(banker.id),
                "banker_name": banker.name,
                "sent": sent,
                "approved": approved,
                "rejected": rejected,
                "approval_rate": round((approved / sent * 100), 1) if sent > 0 else 0,
            })

        result = []

        for bank_data in banks.values():
            sent = bank_data["sent"]
            bank_data["approval_rate"] = (
                round((bank_data["approved"] / sent * 100), 1) if sent > 0 else 0
            )
            result.append(bank_data)

        return result


def _format_role(role: str) -> str:
    mapping = {
        "super_admin": "Super Admin",
        "admin": "Admin",
        "pre_sales_admin": "Pre-Sales Admin",
        "pre_sales_user": "Pre-Sales User",
        "post_sales_admin": "Post-Sales Admin",
        "bank_admin": "Bank Admin",
    }
    return mapping.get(role, role)