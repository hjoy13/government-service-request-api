from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # A Django superuser should also hold the application-level ADMIN role.
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CITIZEN = "CITIZEN", "Citizen"
        OFFICER = "OFFICER", "Officer"
        ADMIN = "ADMIN", "Admin"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CITIZEN,
    )

    objects = CustomUserManager()

    @property
    def is_citizen(self):
        return self.role == self.Role.CITIZEN

    @property
    def is_officer(self):
        return self.role == self.Role.OFFICER

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    def __str__(self):
        return f"{self.username} ({self.role})"