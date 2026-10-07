from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.loan import Loan
from app.models.user import User


class DashboardService:

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    @staticmethod
    def _loan_bank_field():
        if hasattr(Loan, "bank_name"):
            return Loan.bank_name
        if hasattr(Loan, "current_bank_name"):
            return Loan.current_bank_name
        if hasattr(Loan, "bank"):
            return Loan.bank
        return None

    @staticmethod
    def _loan_disbursed_amount_field():
        if hasattr(Loan, "disbursed_amount"):
            return Loan.disbursed_amount
        if hasattr(Loan, "loan_amount_requested"):
            return Loan.loan_amount_requested
        if hasattr(Loan, "loan_amount"):
            return Loan.loan_amount
        return None

    @staticmethod
    def _loan_stage_field():
        if hasattr(Loan, "stage"):
            return Loan.stage
        if hasattr(Loan, "state"):
            return Loan.state
        return None

    @staticmethod
    def _loan_updated_at_field():
        if hasattr(Loan, "stage_updated_at"):
            return Loan.stage_updated_at
        if hasattr(Loan, "updated_at"):
            return Loan.updated_at
        return None

    # ── Sales Overview ────────────────────────────────
    @staticmethod
    async def get_sales_overview(db: AsyncSession) -> dict:
        disbursed_amount_col = DashboardService._loan_disbursed_amount_field()
        loan_stage_col = DashboardService._loan_stage_field()

        lead_counts = await db.execute(
            select(
                func.count().label("total"),
                func.count(case((Lead.stage == "Qualified", 1))).label("qualified"),
                func.count(case((Lead.stage == "Sent to Bank", 1))).label("sent_to_bank"),
                func.count(case((Lead.stage == "Not Qualified", 1))).label("not_qualified"),
                func.count(case((Lead.stage == "Documents Pending", 1))).label("docs_pending"),
            ).select_from(Lead)
        )
        lc = lead_counts.mappings().one()

        if loan_stage_col is not None and disbursed_amount_col is not None:
            total_disbursed_expr = func.coalesce(
                func.sum(
                    case((loan_stage_col == "loan_disbursed", disbursed_amount_col), else_=0)
                ),
                0,
            )
        else:
            total_disbursed_expr = func.coalesce(func.sum(0), 0)

        if loan_stage_col is not None:
            loan_counts = await db.execute(
                select(
                    func.count().label("total"),
                    func.count(case((loan_stage_col == "loan_disbursed", 1))).label("disbursed"),
                    func.count(case((loan_stage_col == "bank_approved", 1))).label("approved"),
                    func.count(case((loan_stage_col == "bank_rejected", 1))).label("rejected"),
                    func.count(case((loan_stage_col.in_(["default", "defaulted"]), 1))).label("defaulted"),
                    total_disbursed_expr.label("total_disbursed"),
                ).select_from(Loan)
            )
            lnc = loan_counts.mappings().one()
        else:
            lnc = {
                "total": 0,
                "disbursed": 0,
                "approved": 0,
                "rejected": 0,
                "defaulted": 0,
                "total_disbursed": 0,
            }

        total_leads = DashboardService._safe_int(lc["total"])
        total_loans = DashboardService._safe_int(lnc["total"])
        disbursed = DashboardService._safe_int(lnc["disbursed"])
        approved = DashboardService._safe_int(lnc["approved"])
        defaulted = DashboardService._safe_int(lnc["defaulted"])
        qualified = DashboardService._safe_int(lc["qualified"])

        conv_rate = round((disbursed / total_leads) * 100, 1) if total_leads else 0
        bank_approval = round((approved / total_loans) * 100, 1) if total_loans else 0
        pre_conversion = round((qualified / total_leads) * 100, 1) if total_leads else 0
        default_rate = round((defaulted / disbursed) * 100, 1) if disbursed else 0

        avg_qualify = await db.execute(
            select(
                func.avg(
                    func.extract("epoch", Lead.updated_at - Lead.created_at) / 86400
                ).label("avg_days")
            ).where(Lead.stage == "Qualified")
        )
        avg_qualify_days = round(DashboardService._safe_float(avg_qualify.scalar()), 1)

        if loan_stage_col is not None and hasattr(Loan, "disbursed_at"):
            avg_disburse = await db.execute(
                select(
                    func.avg(
                        func.extract("epoch", Loan.disbursed_at - Loan.created_at) / 86400
                    ).label("avg_days")
                ).where(loan_stage_col == "loan_disbursed")
            )
            avg_disburse_days = round(DashboardService._safe_float(avg_disburse.scalar()), 1)
        else:
            avg_disburse_days = 0.0

        return {
            "total_leads": total_leads,
            "qualified": qualified,
            "sent_to_bank": DashboardService._safe_int(lc["sent_to_bank"]),
            "not_qualified": DashboardService._safe_int(lc["not_qualified"]),
            "docs_pending": DashboardService._safe_int(lc["docs_pending"]),
            "loan_disbursed": disbursed,
            "bank_approved": approved,
            "bank_rejected": DashboardService._safe_int(lnc["rejected"]),
            "total_disbursed_amount": DashboardService._safe_int(lnc["total_disbursed"]),
            "conversion_rate": conv_rate,
            "bank_approval": bank_approval,
            "pre_conversion": pre_conversion,
            "default_rate": default_rate,
            "avg_days_qualify": avg_qualify_days,
            "avg_days_disburse": avg_disburse_days,
        }

    # ── Pre-Sales Dashboard ───────────────────────────
    @staticmethod
    async def get_pre_sales(db: AsyncSession) -> dict:
        stage_counts = await db.execute(
            select(Lead.stage, func.count().label("count"))
            .group_by(Lead.stage)
        )
        funnel = {
            (row.stage or "Unknown"): DashboardService._safe_int(row.count)
            for row in stage_counts
        }

        team_perf = await db.execute(
            select(
                User.name,
                User.role,
                func.count(Lead.id).label("leads"),
                func.count(case((Lead.stage == "Qualified", 1))).label("qualified"),
                func.count(case((Lead.stage == "Documents Pending", 1))).label("docs_pending"),
                func.count(case((Lead.stage == "Not Qualified", 1))).label("not_qualified"),
            )
            .join(Lead, Lead.assigned_to == User.id, isouter=True)
            .where(User.role.in_(["pre_sales_admin", "pre_sales_user"]))
            .group_by(User.id, User.name, User.role)
        )

        team = []
        for row in team_perf:
            leads = DashboardService._safe_int(row.leads)
            qualified = DashboardService._safe_int(row.qualified)
            docs_pending = DashboardService._safe_int(row.docs_pending)
            not_qualified = DashboardService._safe_int(row.not_qualified)

            team.append({
                "name": row.name,
                "role": row.role,
                "leads": leads,
                "qualified": qualified,
                "docs_pending": docs_pending,
                "not_qualified": not_qualified,
                "conv_rate": round((qualified / leads) * 100, 1) if leads else 0,
            })

        total_active = sum(funnel.values())
        safe_total = total_active or 1

        return {
            "funnel": funnel,
            "total_active": total_active,
            "conversion_rate": round((funnel.get("Qualified", 0) / safe_total) * 100, 1),
            "docs_pending": funnel.get("Documents Pending", 0),
            "team": team,
        }

    # ── Post-Sales Dashboard ──────────────────────────
    @staticmethod
    async def get_post_sales(db: AsyncSession) -> dict:
        disbursed_amount_col = DashboardService._loan_disbursed_amount_field()
        bank_col = DashboardService._loan_bank_field()
        loan_stage_col = DashboardService._loan_stage_field()

        if loan_stage_col is None:
            return {
                "total": 0,
                "sent_to_bank": 0,
                "bank_processing": 0,
                "bank_approved": 0,
                "loan_disbursed": 0,
                "bank_rejected": 0,
                "defaulted": 0,
                "total_disbursed_amount": 0,
                "stages": {},
                "banks": [],
            }

        stage_counts = await db.execute(
            select(loan_stage_col.label("stage"), func.count().label("count"))
            .group_by(loan_stage_col)
        )

        stages = {
            (row.stage or "unknown"): DashboardService._safe_int(row.count)
            for row in stage_counts
        }

        if disbursed_amount_col is not None:
            total_disbursed_expr = func.coalesce(
                func.sum(
                    case((loan_stage_col == "loan_disbursed", disbursed_amount_col), else_=0)
                ),
                0,
            )
        else:
            total_disbursed_expr = func.coalesce(func.sum(0), 0)

        totals = await db.execute(
            select(
                func.count().label("total"),
                func.count(case((loan_stage_col == "sent_to_bank", 1))).label("sent_to_bank"),
                func.count(case((loan_stage_col == "bank_processing", 1))).label("bank_processing"),
                func.count(case((loan_stage_col == "bank_approved", 1))).label("bank_approved"),
                func.count(case((loan_stage_col == "loan_disbursed", 1))).label("loan_disbursed"),
                func.count(case((loan_stage_col == "bank_rejected", 1))).label("bank_rejected"),
                func.count(case((loan_stage_col.in_(["default", "defaulted"]), 1))).label("defaulted"),
                total_disbursed_expr.label("total_disbursed_amount"),
            ).select_from(Loan)
        )
        t = totals.mappings().one()

        banks = []
        if bank_col is not None:
            bank_perf = await db.execute(
                select(
                    bank_col.label("bank_name"),
                    func.count().label("sent"),
                    func.count(case((loan_stage_col == "bank_approved", 1))).label("approved"),
                    func.count(case((loan_stage_col == "bank_rejected", 1))).label("rejected"),
                    func.count(case((loan_stage_col == "loan_disbursed", 1))).label("disbursed"),
                    total_disbursed_expr.label("total_disbursed"),
                )
                .where(bank_col.isnot(None))
                .group_by(bank_col)
            )

            for row in bank_perf:
                sent = DashboardService._safe_int(row.sent)
                approved = DashboardService._safe_int(row.approved)
                rejected = DashboardService._safe_int(row.rejected)
                disbursed = DashboardService._safe_int(row.disbursed)
                total_disbursed = DashboardService._safe_int(row.total_disbursed)

                banks.append({
                    "name": row.bank_name,
                    "sent": sent,
                    "approved": approved,
                    "rejected": rejected,
                    "disbursed": disbursed,
                    "total_disbursed": total_disbursed,
                    "approval_rate": round((approved / sent) * 100, 1) if sent else 0,
                })

        return {
            "total": DashboardService._safe_int(t["total"]),
            "sent_to_bank": DashboardService._safe_int(t["sent_to_bank"]),
            "bank_processing": DashboardService._safe_int(t["bank_processing"]),
            "bank_approved": DashboardService._safe_int(t["bank_approved"]),
            "loan_disbursed": DashboardService._safe_int(t["loan_disbursed"]),
            "bank_rejected": DashboardService._safe_int(t["bank_rejected"]),
            "defaulted": DashboardService._safe_int(t["defaulted"]),
            "total_disbursed_amount": DashboardService._safe_int(t["total_disbursed_amount"]),
            "stages": stages,
            "banks": banks,
        }

    # ── Trends ────────────────────────────────────────
    @staticmethod
    async def get_trends(db: AsyncSession, days: int = 30) -> list:
        since = datetime.now(timezone.utc) - timedelta(days=days)

        loan_stage_col = DashboardService._loan_stage_field()
        loan_updated_col = DashboardService._loan_updated_at_field()

        daily_leads = await db.execute(
            select(
                func.date(Lead.created_at).label("date"),
                func.count().label("count"),
            )
            .where(Lead.created_at >= since)
            .group_by(func.date(Lead.created_at))
            .order_by(func.date(Lead.created_at))
        )

        daily_qualified = await db.execute(
            select(
                func.date(Lead.updated_at).label("date"),
                func.count().label("count"),
            )
            .where(
                and_(
                    Lead.updated_at >= since,
                    Lead.stage == "Qualified",
                )
            )
            .group_by(func.date(Lead.updated_at))
            .order_by(func.date(Lead.updated_at))
        )

        if loan_stage_col is not None and hasattr(Loan, "disbursed_at"):
            daily_disbursed = await db.execute(
                select(
                    func.date(Loan.disbursed_at).label("date"),
                    func.count().label("count"),
                )
                .where(
                    and_(
                        Loan.disbursed_at >= since,
                        loan_stage_col == "loan_disbursed",
                    )
                )
                .group_by(func.date(Loan.disbursed_at))
                .order_by(func.date(Loan.disbursed_at))
            )
        else:
            daily_disbursed = []

        if loan_stage_col is not None and loan_updated_col is not None:
            daily_rejected = await db.execute(
                select(
                    func.date(loan_updated_col).label("date"),
                    func.count().label("count"),
                )
                .where(
                    and_(
                        loan_updated_col >= since,
                        loan_stage_col == "bank_rejected",
                    )
                )
                .group_by(func.date(loan_updated_col))
                .order_by(func.date(loan_updated_col))
            )

            daily_defaulted = await db.execute(
                select(
                    func.date(loan_updated_col).label("date"),
                    func.count().label("count"),
                )
                .where(
                    and_(
                        loan_updated_col >= since,
                        loan_stage_col.in_(["default", "defaulted"]),
                    )
                )
                .group_by(func.date(loan_updated_col))
                .order_by(func.date(loan_updated_col))
            )
        else:
            daily_rejected = []
            daily_defaulted = []

        merged = defaultdict(lambda: {
            "date": "",
            "new_leads": 0,
            "qualified": 0,
            "lost": 0,
            "disbursed": 0,
            "rejected": 0,
            "defaulted": 0,
        })

        for r in daily_leads:
            d = str(r.date)
            merged[d]["date"] = d
            merged[d]["new_leads"] = DashboardService._safe_int(r.count)

        for r in daily_qualified:
            d = str(r.date)
            merged[d]["date"] = d
            merged[d]["qualified"] = DashboardService._safe_int(r.count)

        for r in daily_disbursed:
            d = str(r.date)
            merged[d]["date"] = d
            merged[d]["disbursed"] = DashboardService._safe_int(r.count)

        for r in daily_rejected:
            d = str(r.date)
            merged[d]["date"] = d
            merged[d]["rejected"] = DashboardService._safe_int(r.count)

        for r in daily_defaulted:
            d = str(r.date)
            merged[d]["date"] = d
            merged[d]["defaulted"] = DashboardService._safe_int(r.count)

        return [merged[d] for d in sorted(merged.keys())]

    # ── Live Pipeline ─────────────────────────────────
    @staticmethod
    async def get_pipeline(db: AsyncSession) -> list:
        loan_stage_col = DashboardService._loan_stage_field()

        if loan_stage_col is None:
            return []

        loan_stages = await db.execute(
            select(loan_stage_col.label("stage"), func.count().label("count"))
            .group_by(loan_stage_col)
            .order_by(loan_stage_col)
        )

        return [
            {
                "stage": r.stage,
                "count": DashboardService._safe_int(r.count),
            }
            for r in loan_stages
        ]