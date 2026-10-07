# app/schemas/user.py
import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator, ConfigDict


VALID_ROLES = [
    "super_admin",
    "admin",
    "pre_sales_admin",
    "pre_sales_user",
    "post_sales_admin",
    "bank_admin",
]

VALID_STATUSES = ["active", "inactive"]

VALID_BANKS = [
    "HDFC Bank",
    "SBI",
    "ICICI Bank",
    "Axis Bank",
    "Kotak Bank",
    "Bank of Baroda",
    "PNB",
    "Canara Bank",
]

# ── Bank name aliases (case-insensitive) ──────────────
BANK_NAME_ALIASES: dict[str, str] = {
    # HDFC
    "hdfc":                 "HDFC Bank",
    "hdfc bank":            "HDFC Bank",
    # SBI
    "sbi":                  "SBI",
    "state bank":           "SBI",
    "state bank of india":  "SBI",
    # ICICI
    "icici":                "ICICI Bank",
    "icici bank":           "ICICI Bank",
    # Axis
    "axis":                 "Axis Bank",
    "axis bank":            "Axis Bank",
    # Kotak
    "kotak":                "Kotak Bank",
    "kotak bank":           "Kotak Bank",
    "kotak mahindra":       "Kotak Bank",
    "kotak mahindra bank":  "Kotak Bank",
    # Bank of Baroda
    "bob":                  "Bank of Baroda",
    "bank of baroda":       "Bank of Baroda",
    # PNB
    "pnb":                  "PNB",
    "punjab national bank": "PNB",
    # Canara
    "canara":               "Canara Bank",
    "canara bank":          "Canara Bank",
}

# ── Phone regex: optional +, then digits/spaces/hyphens, 7–15 chars ──
_PHONE_RE = re.compile(r"^\+?[\d\s\-]{7,15}$")

# ── Employee ID: alphanumeric + hyphens/underscores, 3–20 chars ──────
_EMP_ID_RE = re.compile(r"^[A-Za-z0-9\-_]{3,20}$")


def normalize_bank_name(v: str) -> str:
    """Map any alias/shorthand to the canonical bank name."""
    normalized = BANK_NAME_ALIASES.get(v.strip().lower())
    if not normalized:
        raise ValueError(
            f"Unrecognized bank name '{v}'. Valid banks: {VALID_BANKS}"
        )
    return normalized


def validate_name(v: str) -> str:
    """Strip whitespace and enforce minimum length."""
    v = v.strip()
    if len(v) < 2:
        raise ValueError("Name must be at least 2 characters")
    if len(v) > 100:
        raise ValueError("Name must be at most 100 characters")
    return v


# ── BASE ──────────────────────────────────────────────
class UserBase(BaseModel):
    name:  str
    email: EmailStr
    role:  str

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        return validate_name(v)

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        return v


# ── CREATE — POST /users/ (non bank_admin roles only) ─
class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @model_validator(mode="after")
    def bank_admin_not_allowed(self) -> "UserCreate":
        if self.role == "bank_admin":
            raise ValueError(
                "Use POST /api/users/bank-admin to create bank admin users"
            )
        return self


# ── BANK ADMIN CREATE — POST /users/bank-admin ────────
class BankAdminCreate(BaseModel):
    name:          str
    email:         EmailStr
    password:      str
    bank_name:     str                         # required — normalized to canonical
    employee_id:   str                         # required — alphanumeric 3–20 chars
    branch:        str                         # required
    manager_email: Optional[EmailStr] = None   # optional
    manager_phone: Optional[str]      = None   # optional — validated if provided

    # role is always bank_admin — set explicitly by service layer,
    # not accepted from request body to prevent tampering
    role: str = "bank_admin"

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        return validate_name(v)

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("bank_name")
    @classmethod
    def bank_name_must_be_valid(cls, v: str) -> str:
        return normalize_bank_name(v)

    @field_validator("employee_id")
    @classmethod
    def employee_id_must_be_valid(cls, v: str) -> str:
        v = v.strip()
        if not _EMP_ID_RE.match(v):
            raise ValueError(
                "employee_id must be 3–20 alphanumeric characters "
                "(hyphens and underscores allowed)"
            )
        return v

    @field_validator("branch")
    @classmethod
    def branch_must_be_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("branch must be at least 2 characters")
        return v

    @field_validator("manager_phone")
    @classmethod
    def phone_format(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not _PHONE_RE.match(v):
                raise ValueError(
                    "manager_phone must be a valid phone number "
                    "(7–15 digits, optional leading +)"
                )
        return v


# ── UPDATE — PUT /users/{id} ──────────────────────────
class UserUpdate(BaseModel):
    name:          Optional[str]      = None
    email:         Optional[EmailStr] = None
    role:          Optional[str]      = None
    bank_name:     Optional[str]      = None
    employee_id:   Optional[str]      = None
    branch:        Optional[str]      = None
    manager_email: Optional[EmailStr] = None
    manager_phone: Optional[str]      = None

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_name(v)
        return v

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        return v

    @field_validator("bank_name")
    @classmethod
    def bank_name_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None:
            return normalize_bank_name(v)
        return v

    @field_validator("employee_id")
    @classmethod
    def employee_id_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not _EMP_ID_RE.match(v):
                raise ValueError(
                    "employee_id must be 3–20 alphanumeric characters "
                    "(hyphens and underscores allowed)"
                )
        return v

    @field_validator("manager_phone")
    @classmethod
    def phone_format(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not _PHONE_RE.match(v):
                raise ValueError(
                    "manager_phone must be a valid phone number "
                    "(7–15 digits, optional leading +)"
                )
        return v

    @model_validator(mode="after")
    def block_bank_admin_role_update(self) -> "UserUpdate":
        """
        Prevent escalating any user's role to bank_admin via the
        general update endpoint. Use POST /api/users/bank-admin instead.
        """
        if self.role == "bank_admin":
            raise ValueError(
                "Cannot set role to bank_admin via this endpoint. "
                "Use POST /api/users/bank-admin to create bank admin users."
            )
        return self


# ── STATUS PATCH — PATCH /users/{id}/status ──────────
class UserStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError("status must be 'active' or 'inactive'")
        return v


# ── PASSWORD RESET — PATCH /users/{id}/password ───────
class PasswordReset(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


# ── RESPONSE ──────────────────────────────────────────
class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id:            uuid.UUID
    status:        str
    bank_name:     Optional[str]      = None
    employee_id:   Optional[str]      = None
    branch:        Optional[str]      = None
    manager_email: Optional[str]      = None
    manager_phone: Optional[str]      = None
    created_at:    datetime
    last_login:    Optional[datetime] = None


# ── LIST ITEM (lighter) ───────────────────────────────
class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:            uuid.UUID
    name:          str
    email:         str
    role:          str
    status:        str
    bank_name:     Optional[str]      = None
    employee_id:   Optional[str]      = None
    branch:        Optional[str]      = None
    manager_email: Optional[str]      = None
    manager_phone: Optional[str]      = None
    created_at:    datetime
    last_login:    Optional[datetime] = None


# ── ACTIVITY LOG RESPONSE ─────────────────────────────
class ActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          uuid.UUID
    action:      str
    entity_type: Optional[str]       = None
    entity_id:   Optional[uuid.UUID] = None
    created_at:  datetime


# ── BANKER DROPDOWN (for assign-to-banker) ────────────
class BankerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          uuid.UUID
    name:        str
    email:       str
    bank_name:   Optional[str] = None
    employee_id: Optional[str] = None
    branch:      Optional[str] = None