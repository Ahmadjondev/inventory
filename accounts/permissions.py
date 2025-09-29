from rest_framework import permissions


class RolePermission(permissions.BasePermission):
    """RBAC permission based on a view's allowed_roles attribute.

    If a view (ViewSet/APIView) defines allowed_roles = ["admin", ...] the request.user.role
    must be in that list. If allowed_roles is absent, access is granted (other permissions may still deny).
    """

    message = "You do not have permission to perform this action for your role."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        allowed = getattr(view, "allowed_roles", None)
        if allowed is None:
            return True
        return request.user.role in allowed
