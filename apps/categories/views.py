from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException

from apps.accounts.permissions import IsAdminRoleOrReadOnly

from .models import Category
from .serializers import CategorySerializer


class CategoryInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "This category is used by service requests and cannot be deleted. "
        "Deactivate it instead by setting is_active to false."
    )
    default_code = "category_in_use"


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = (IsAdminRoleOrReadOnly,)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = Category.objects.all()
        if not getattr(self.request.user, "is_admin_role", False):
            queryset = queryset.filter(is_active=True)
        return queryset

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise CategoryInUse()