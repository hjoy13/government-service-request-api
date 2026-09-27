from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminRole(BasePermission):
    """Application ADMIN role only (not Django is_staff / is_superuser)."""

    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin_role)


class IsAdminRoleOrReadOnly(BasePermission):
    """Any authenticated user may read; only the ADMIN role may write."""

    message = "Only administrators can modify this resource."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_admin_role