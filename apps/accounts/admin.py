from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")

    # Edit page: Django's standard sections + the application role
    fieldsets = UserAdmin.fieldsets + (
        ("Application role", {"fields": ("role",)}),
    )

    # "Add user" page: also require email and choose the role at creation
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Profile and role", {"fields": ("email", "role")}),
    )