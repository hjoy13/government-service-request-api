from rest_framework.permissions import BasePermission


class ServiceRequestPermission(BasePermission):
    message = "Only citizens can create service requests."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if view.action == "create":
            return user.is_citizen
        return True