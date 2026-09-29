from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

VALID_PASSWORD = "Str0ng-Pass-9x!"


class LoginRateLimitTests(APITestCase):
    """Login is limited to 5 attempts per minute per client IP (scope "login")."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="rl_citizen", email="rl_citizen@example.com", password=VALID_PASSWORD
        )

    def setUp(self):
        # Throttle counters live in the cache and are shared across tests in one run.
        cache.clear()
        self.url = reverse("token_obtain_pair")

    def tearDown(self):
        cache.clear()

    def attempt(self, password):
        return self.client.post(
            self.url, {"username": "rl_citizen", "password": password}, format="json"
        )

    def test_sixth_attempt_within_a_minute_is_throttled(self):
        for _ in range(5):
            self.assertEqual(self.attempt("wrong-password").status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.attempt("wrong-password")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", response.headers)

    def test_correct_password_is_also_blocked_once_throttled(self):
        for _ in range(5):
            self.attempt("wrong-password")

        response = self.attempt(VALID_PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertNotIn("access", response.data)

    def test_attempts_under_the_limit_still_succeed(self):
        for _ in range(4):
            self.attempt("wrong-password")

        response = self.attempt(VALID_PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)