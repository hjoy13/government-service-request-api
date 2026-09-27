from rest_framework import mixins, viewsets

from .models import ServiceRequest
from .permissions import ServiceRequestPermission
from .serializers import ServiceRequestSerializer


class ServiceRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ServiceRequestSerializer
    permission_classes = (ServiceRequestPermission,)

    def get_queryset(self):
        user = self.request.user
        queryset = ServiceRequest.objects.select_related("category", "created_by", "assigned_to")

        if getattr(user, "is_admin_role", False):
            return queryset
        if getattr(user, "is_officer", False):
            return queryset.filter(assigned_to=user)
        if getattr(user, "is_citizen", False):
            return queryset.filter(created_by=user)
        return queryset.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)