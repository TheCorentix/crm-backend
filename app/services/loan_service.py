from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.loan import Loan


class LoanService:

    @staticmethod
    async def list_loans(db: AsyncSession, search, stage, bank_name, assigned_to, page, limit):

        query = select(Loan)

        if search:
            query = query.where(Loan.contact_name.ilike(f"%{search}%"))

        if stage:
            query = query.where(Loan.stage == stage)

        if bank_name:
            query = query.where(Loan.bank_name == bank_name)

        if assigned_to:
            query = query.where(Loan.assigned_to == assigned_to)

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        loans = result.scalars().all()

        return loans