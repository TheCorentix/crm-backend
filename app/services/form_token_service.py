# app/services/form_token_service.py
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt

from app.config import settings


class FormTokenService:

    # ── Generate signed token ─────────────────────────

    @staticmethod
    def generate_token(contact_id: uuid.UUID) -> str:
        """
        Creates a signed JWT containing the contact_id.
        Expires in FORM_LINK_EXPIRE_HOURS (default 24 hours).
        """
        expire = datetime.now(timezone.utc) + timedelta(
            hours=settings.FORM_LINK_EXPIRE_MINUTES
        )
        payload = {
            "sub":  str(contact_id),
            "type": "loan_form",
            "exp":  expire,
            "iat":  datetime.now(timezone.utc),
        }
        return jwt.encode(
            payload,
            settings.FORM_LINK_SECRET,
            algorithm="HS256",
        )

    # ── Build full URL ────────────────────────────────

    @staticmethod
    def build_form_url(contact_id: uuid.UUID) -> str:
        """
        https://maneendrakummari.github.io/Loan/?token=eyJ...
        """
        token = FormTokenService.generate_token(contact_id)
        return f"{settings.LOAN_FORM_BASE_URL}?token={token}"

    # ── Validate token ────────────────────────────────

    @staticmethod
    def validate_token(token: str) -> dict:
        """
        Returns:
        {
            "valid":      True | False,
            "contact_id": uuid | None,
            "reason":     None | "error string"
        }
        """
        try:
            payload = jwt.decode(
                token,
                settings.FORM_LINK_SECRET,
                algorithms=["HS256"],
            )

            if payload.get("type") != "loan_form":
                return {
                    "valid":      False,
                    "contact_id": None,
                    "reason":     "Invalid token type",
                }

            contact_id = payload.get("sub")
            if not contact_id:
                return {
                    "valid":      False,
                    "contact_id": None,
                    "reason":     "Missing contact_id in token",
                }

            return {
                "valid":      True,
                "contact_id": uuid.UUID(contact_id),
                "reason":     None,
            }

        except JWTError as e:
            return {
                "valid":      False,
                "contact_id": None,
                "reason":     str(e),
            }