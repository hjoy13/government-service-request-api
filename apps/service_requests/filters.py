from django_filters import rest_framework as filters

from .models import Priority, ServiceRequest, Status
from django.db.models import Case, IntegerField, Value, When
from rest_framework.filters import OrderingFilter

class ServiceRequestFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=Status.choices)
    priority = filters.ChoiceFilter(choices=Priority.choices)
    category = filters.NumberFilter(field_name="category_id")
    assigned_to = filters.NumberFilter(field_name="assigned_to_id")
    unassigned = filters.BooleanFilter(field_name="assigned_to", lookup_expr="isnull")

    class Meta:
        model = ServiceRequest
        fields = ("status", "priority", "category", "assigned_to", "unassigned")

    # Priority.values is declared LOW, MEDIUM, HIGH, URGENT → ranks 1..4
PRIORITY_RANK = Case(
    *[When(priority=value, then=Value(rank)) for rank, value in enumerate(Priority.values, start=1)],
    output_field=IntegerField(),
)    

class ServiceRequestOrderingFilter(OrderingFilter):
    def filter_queryset(self, request, queryset, view):
        queryset = queryset.annotate(priority_rank=PRIORITY_RANK)
        return super().filter_queryset(request, queryset, view)

    def get_ordering(self, request, queryset, view):
        ordering = list(super().get_ordering(request, queryset, view) or [])
        mapped = [
            field.replace("priority", "priority_rank") if field.lstrip("-") == "priority" else field
            for field in ordering
        ]
        return [*mapped, "-id"]