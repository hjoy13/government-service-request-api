from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from apps.accounts.permissions import IsAdminRole, IsAdminRoleOrReadOnly

User = get_user_model()


def make_request(user, method="GET"):
    return SimpleNamespace(user=user, method=method)


class IsAdminRoleTests(SimpleTestCase):
    permission = IsAdminRole()

    def test_admin_role_allowed(self):
        request = make_request(User(role=User.Role.ADMIN))
        self.assertTrue(self.permission.has_permission(request, None))

    def test_citizen_and_officer_denied(self):
        for role in (User.Role.CITIZEN, User.Role.OFFICER):
            with self.subTest(role=role):
                request = make_request(User(role=role))
                self.assertFalse(self.permission.has_permission(request, None))

    def test_anonymous_denied(self):
        self.assertFalse(self.permission.has_permission(make_request(AnonymousUser()), None))

    def test_django_superuser_without_admin_role_denied(self):
        user = User(role=User.Role.CITIZEN, is_staff=True, is_superuser=True)
        self.assertFalse(self.permission.has_permission(make_request(user), None))


class IsAdminRoleOrReadOnlyTests(SimpleTestCase):
    permission = IsAdminRoleOrReadOnly()

    def test_safe_methods_allowed_for_every_role(self):
        for role in User.Role.values:
            for method in ("GET", "HEAD", "OPTIONS"):
                with self.subTest(role=role, method=method):
                    request = make_request(User(role=role), method)
                    self.assertTrue(self.permission.has_permission(request, None))

    def test_write_methods_admin_only(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                admin = make_request(User(role=User.Role.ADMIN), method)
                citizen = make_request(User(role=User.Role.CITIZEN), method)
                officer = make_request(User(role=User.Role.OFFICER), method)
                self.assertTrue(self.permission.has_permission(admin, None))
                self.assertFalse(self.permission.has_permission(citizen, None))
                self.assertFalse(self.permission.has_permission(officer, None))

    def test_anonymous_denied_even_for_safe_methods(self):
        request = make_request(AnonymousUser(), "GET")
        self.assertFalse(self.permission.has_permission(request, None))