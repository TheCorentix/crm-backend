import uuid
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact


class ContactService:

    # ── CREATE CONTACT ─────────────────────────────
    @staticmethod
    async def create_contact(db: AsyncSession, payload, user_id):

        # Generate human readable contact id
        result = await db.execute(select(Contact).order_by(Contact.created_at.desc()).limit(1))
        last_contact = result.scalar_one_or_none()

        if last_contact and last_contact.contact_id:
            last_num = int(last_contact.contact_id.split("-")[1])
            new_contact_id = f"CNT-{last_num + 1:03d}"
        else:
            new_contact_id = "CNT-001"

        contact = Contact(
            id=uuid.uuid4(),
            contact_id=new_contact_id,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            city=payload.city,
            source=payload.source,
            status=payload.status,
            loan_type=payload.loan_type,
            amount=payload.amount,
            notes=payload.notes,
            created_by=user_id
        )

        db.add(contact)
        await db.commit()
        await db.refresh(contact)

        return contact

    # ── LIST CONTACTS ─────────────────────────────
    @staticmethod
    async def list_contacts(db, search, status, source, page, limit):

        query = select(Contact)

        if search:
            query = query.where(
                or_(
                    Contact.name.ilike(f"%{search}%"),
                    Contact.email.ilike(f"%{search}%"),
                    Contact.phone.ilike(f"%{search}%"),
                    Contact.city.ilike(f"%{search}%"),
                )
            )

        if status:
            query = query.where(Contact.status == status)

        if source:
            query = query.where(Contact.source == source)

        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)

        return result.scalars().all()

    # ── GET CONTACT BY ID ─────────────────────────
    @staticmethod
    async def get_by_id(db, contact_id):

        result = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )

        return result.scalar_one_or_none()

    # ── UPDATE CONTACT ────────────────────────────
    @staticmethod
    async def update_contact(db, contact_id, payload):

        result = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )

        contact = result.scalar_one_or_none()

        if not contact:
            return None

        update_data = payload.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(contact, field, value)

        await db.commit()
        await db.refresh(contact)

        return contact

    # ── DELETE CONTACT ────────────────────────────
    @staticmethod
    async def delete_contact(db, contact_id):

        result = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )

        contact = result.scalar_one_or_none()

        if not contact:
            return False

        await db.delete(contact)
        await db.commit()

        return True