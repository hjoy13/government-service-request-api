from rest_framework import mixins, viewsets, status

from .models import ServiceRequest
from .permissions import ServiceRequestPermission
from .serializers import ServiceRequestSerializer, AssignOfficerSerializer, CommentSerializer
from rest_framework.decorators import action
from rest_framework.response import Response

from django.http import FileResponse
from rest_framework.exceptions import NotFound
import os

from apps.accounts.permissions import IsAdminRole

from django.db.models import Count, Q
from rest_framework.views import APIView

from apps.categories.models import Category
from .models import Priority, Status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from .filters import ServiceRequestFilter, ServiceRequestOrderingFilter

class ServiceRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ServiceRequestSerializer
    permission_classes = (ServiceRequestPermission,)
    http_method_names = ["get", "post", "patch", "head", "options"]

    filter_backends = (DjangoFilterBackend, SearchFilter, ServiceRequestOrderingFilter)
    filterset_class = ServiceRequestFilter
    search_fields = ("title", "description")
    ordering_fields = ("created_at", "updated_at", "priority")
    ordering = ("-created_at",)

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

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def assign(self, request, pk=None):
        service_request = self.get_object()

        input_serializer = AssignOfficerSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        service_request.assigned_to = input_serializer.validated_data["officer_id"]
        service_request.save(update_fields=["assigned_to", "updated_at"])

        output = ServiceRequestSerializer(
            service_request, context=self.get_serializer_context()
        )
        return Response(output.data)    
    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        service_request = self.get_object()

        if request.method == "POST":
            serializer = CommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(service_request=service_request, author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        comments = service_request.comments.all()
        return Response(CommentSerializer(comments, many=True).data)

    @action(detail=True, methods=["get"])
    def attachment(self, request, pk=None):
        service_request = self.get_object()

        if not service_request.attachment:
            raise NotFound("This request has no attachment.")

        try:
            file_handle = service_request.attachment.open("rb")
        except FileNotFoundError:
            raise NotFound("The attachment file is missing.")

        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=os.path.basename(service_request.attachment.name),
        )

class StatisticsView(APIView):
    permission_classes = (IsAdminRole,)

    def get(self, request):
        aggregates = {
            "total": Count("id"),
            "unassigned": Count("id", filter=Q(assigned_to__isnull=True)),
        }
        for value in Status.values:
            aggregates[f"status_{value}"] = Count("id", filter=Q(status=value))
        for value in Priority.values:
            aggregates[f"priority_{value}"] = Count("id", filter=Q(priority=value))

        counts = ServiceRequest.objects.aggregate(**aggregates)

        by_category = (
            Category.objects.annotate(count=Count("service_requests"))
            .order_by("name")
            .values("id", "name", "count")
        )

        return Response({
            "total_requests": counts["total"],
            "by_status": {v.lower(): counts[f"status_{v}"] for v in Status.values},
            "by_priority": {v.lower(): counts[f"priority_{v}"] for v in Priority.values},
            "unassigned": counts["unassigned"],
            "by_category": list(by_category),
        })    