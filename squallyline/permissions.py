"""
Shared DRF permissions.

The project has two overlapping notions of "admin":
  * Django's ``is_staff`` flag (what ``rest_framework.permissions.IsAdminUser``
    checks), which only gets set for superusers.
  * ``User.role``, the field the app actually assigns at registration.

Everything here keys off ``role`` so a user created through the API with
role='admin' behaves like an admin without needing the staff flag too.
Superusers always pass.
"""
from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Owner-level access: catalogue, pricing, slots, analytics."""

    message = 'Administrator access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or getattr(user, 'role', None) == 'admin')
        )


class IsStaffRole(BasePermission):
    """Day-to-day shop floor access: admins and apprentices."""

    message = 'Staff access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or getattr(user, 'role', None) in ('admin', 'apprentice')
            )
        )
