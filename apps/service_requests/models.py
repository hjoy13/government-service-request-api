from django.conf import settings
from django.db import models

from apps.accounts.models import User


class Priority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    URGENT = "URGENT", "Urgent"


class Status(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"


class ServiceRequest(models.Model):
    # Aliases so callers can write ServiceRequest.Status.OPEN
    Priority = Priority
    Status = Status

    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.PROTECT,
        related_name="service_requests",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="service_requests_created",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests_assigned",
        limit_choices_to={"role": User.Role.OFFICER},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=Status.values),
                name="service_request_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__in=Priority.values),
                name="service_request_priority_valid",
            ),
        ]

    def __str__(self):
        return f"#{self.pk} {self.title}"