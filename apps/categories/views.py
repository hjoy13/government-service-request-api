from rest_framework import viewsets

from apps.accounts.permissions import IsAdminRoleOrReadOnly

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = (IsAdminRoleOrReadOnly,)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = Category.objects.all()
        if not getattr(self.request.user, "is_admin_role", False):
            queryset = queryset.filter(is_active=True)
        return queryset