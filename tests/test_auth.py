from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

VALID_PASSWORD = "Road-Repair-2026!"


class RegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse("register")

    def payload(self, **overrides):
        data = {
            "username": "citizen1",
            "email": "citizen1@example.com",
            "password": VALID_PASSWORD,
        }
        data.update(overrides)
        return data

    def test_register_creates_citizen_with_hashed_password(self):
        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], User.Role.CITIZEN)
        self.assertNotIn("password", response.data)

        user = User.objects.get(username="citizen1")
        self.assertEqual(user.role, User.Role.CITIZEN)
        self.assertNotEqual(user.password, VALID_PASSWORD)
        self.assertTrue(user.check_password(VALID_PASSWORD))

    def test_register_lowercases_email(self):
        response = self.client.post(
            self.url, self.payload(email="Citizen1@Example.COM"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(username="citizen1").email, "citizen1@example.com")

    def test_register_rejects_privileged_roles(self):
        for role in (User.Role.OFFICER, User.Role.ADMIN):
            with self.subTest(role=role):
                response = self.client.post(self.url, self.payload(role=role), format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("role", response.data)
                self.assertFalse(User.objects.filter(username="citizen1").exists())

    def test_register_rejects_django_privilege_flags(self):
        for field in ("is_staff", "is_superuser"):
            with self.subTest(field=field):
                response = self.client.post(self.url, self.payload(**{field: True}), format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
                self.assertFalse(User.objects.filter(username="citizen1").exists())

    def test_register_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            username="existing", email="citizen1@example.com", password=VALID_PASSWORD
        )

        response = self.client.post(
            self.url, self.payload(email="CITIZEN1@Example.com"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_rejects_weak_password(self):
        response = self.client.post(self.url, self.payload(password="12345"), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(username="citizen1").exists())

    def test_register_ignores_invalid_bearer_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")

        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class JWTAuthTests(APITestCase):
    def setUp(self):
        self.login_url = reverse("token_obtain_pair")
        self.refresh_url = reverse("token_refresh")
        User.objects.create_user(
            username="citizen1", email="citizen1@example.com", password=VALID_PASSWORD
        )

    def login(self, password=VALID_PASSWORD, username="citizen1"):
        return self.client.post(
            self.login_url, {"username": username, "password": password}, format="json"
        )

    def test_login_returns_access_and_refresh_tokens(self):
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password_returns_401(self):
        response = self.login(password="wrong-password")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_unknown_user_returns_401(self):
        response = self.login(username="nobody")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self):
        refresh = self.login().data["refresh"]

        response = self.client.post(self.refresh_url, {"refresh": refresh}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_with_invalid_token_returns_401(self):
        response = self.client.post(self.refresh_url, {"refresh": "garbage"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)