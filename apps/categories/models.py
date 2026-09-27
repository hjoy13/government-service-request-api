from django.db import models
from django.db.models.functions import Lower


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_category_name_case_insensitive",
                violation_error_message="A category with this name already exists.",
            ),
        ]

    def __str__(self):
        return self.name