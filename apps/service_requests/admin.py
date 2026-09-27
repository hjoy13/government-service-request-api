from django.contrib import admin

from .models import ServiceRequest


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "category", "priority", "status",
        "created_by", "assigned_to", "created_at",
    )
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "description")
    list_select_related = ("category", "created_by", "assigned_to")