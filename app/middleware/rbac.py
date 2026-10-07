# app/middleware/rbac.py
from typing import List
from fastapi import Depends, HTTPException, status

from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser


# ── Role permissions map ──────────────────────────────
ROLE_PERMISSIONS: dict[str, List[str]] = {
    "super_admin": [
        "users:read",    "users:write",
        "contacts:read", "contacts:write",
        "leads:read",    "leads:write",
        "loans:read",    "loans:write",
        "loans:bank",
        "dashboard:sales",
        "dashboard:pre",
        "dashboard:post",
        "dashboard:trends",
    ],
    "admin": [
        "contacts:read", "contacts:write",
        "leads:read",    "leads:write",
        "loans:read",    "loans:write",
        "loans:bank",
        "dashboard:sales",
        "dashboard:pre",
        "dashboard:post",
        "dashboard:trends",
    ],
    "pre_sales_admin": [
        "contacts:read", "contacts:write",
        "leads:read",    "leads:write",
        "dashboard:pre",
    ],
    "pre_sales_user": [
        "contacts:read",
        "leads:read",
        "dashboard:pre",
    ],
    "post_sales_admin": [
        "contacts:read",
        "leads:read",
        "loans:read",    "loans:write",
        "dashboard:post",
    ],
    "bank_admin": [
        "contacts:read",
        "leads:read",
        "loans:read",    "loans:bank",
        "dashboard:post",
    ],
}


def require_roles(allowed_roles: List[str]):
    """
    Route-level role guard.

    Usage in router:
        current: CurrentUser = Depends(require_roles(["super_admin", "admin"]))

    Raises 403 if the current user's role is not in allowed_roles.
    """
    async def _guard(
        current: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if current.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}",
            )
        return current
    return _guard


def require_permission(permission: str):
    """
    Permission-level guard (more granular than role guard).

    Usage in router:
        current: CurrentUser = Depends(require_permission("leads:write"))

    Raises 403 if the current user's role does not have the permission.
    """
    async def _guard(
        current: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        role_perms = ROLE_PERMISSIONS.get(current.role, [])
        if permission not in role_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {permission}",
            )
        return current
    return _guard


def require_self_or_roles(allowed_roles: List[str]):
    """
    Allows access if the user is accessing their OWN resource
    OR if they have one of the allowed roles.

    Usage in router:
        current: CurrentUser = Depends(require_self_or_roles(["super_admin"]))

    Then in route body check:
        if str(current.id) != str(target_user_id):
            raise HTTPException(403)
    """
    async def _guard(
        current: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if current.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}",
            )
        return current
    return _guard
