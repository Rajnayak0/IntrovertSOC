"""Role-based access (local roles only: admin / analyst / viewer)."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import User


class IsAdminRole(BasePermission):
    """Admins only (user management, model config, playbook definitions)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin_role)


class ReadOnlyOrAdmin(BasePermission):
    """Any authenticated user may read; only admins may write."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(user.is_admin_role)


class IsEditor(BasePermission):
    """Analysts and admins may write; viewers are read-only."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(user.can_edit)


def user_role(user) -> str:
    if not user or not user.is_authenticated:
        return "anonymous"
    return getattr(user, "role", User.Role.VIEWER)
