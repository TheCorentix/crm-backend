import pandas as pd
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.database import engine
from app.models.lead import Lead


EXCEL_FILE = "loan_records.xlsx"


async def import_loans():

    df = pd.read_excel(EXCEL_FILE)

    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as db:

        for _, row in df.iterrows():

            lead = Lead(
                lead_id=str(row["loan_id"]),
                contact_name=row["name"],
                contact_email=row["email"],
                phone=str(row["phone"]),
                company=row.get("employment_type", ""),
                state="new",   # default state
                expected_loan_amount=row["loan_amount"],
                updated_at=row["timestamp"]
            )

            db.add(lead)

        await db.commit()

    print("✅ Loan records imported successfully")


if __name__ == "__main__":
    asyncio.run(import_loans())