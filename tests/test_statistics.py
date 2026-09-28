from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.service_requests.models import Priority, ServiceRequest, Status

User = get_user_model()


class StatisticsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        def make(username, role):
            return User.objects.create_user(
                username=username, email=f"{username}@example.com", role=role
            )

        cls.admin = make("st_admin", User.Role.ADMIN)
        cls.citizen = make("st_citizen", User.Role.CITIZEN)
        cls.officer = make("st_officer", User.Role.OFFICER)

        cls.roads = Category.objects.create(name="St Roads")
        cls.water = Category.objects.create(name="St Water", is_active=False)
        cls.empty = Category.objects.create(name="St Empty")

        def req(category, status_value, priority_value, assigned):
            return ServiceRequest.objects.create(
                category=category, title="t", description="d",
                status=status_value, priority=priority_value,
                created_by=cls.citizen,
                assigned_to=cls.officer if assigned else None,
            )

        req(cls.roads, Status.OPEN, Priority.LOW, False)
        req(cls.roads, Status.OPEN, Priority.HIGH, True)
        req(cls.roads, Status.IN_PROGRESS, Priority.URGENT, True)
        req(cls.water, Status.RESOLVED, Priority.MEDIUM, True)
        req(cls.water, Status.CLOSED, Priority.HIGH, False)

        cls.url = reverse("statistics")

    def get_as(self, user):
        if user is not None:
            self.client.force_authenticate(user)
        return self.client.get(self.url)

    # ---- exact counts ----
    def test_total_and_unassigned(self):
        response = self.get_as(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_requests"], 5)
        self.assertEqual(response.data["unassigned"], 2)

    def test_by_status(self):
        response = self.get_as(self.admin)
        self.assertEqual(
            response.data["by_status"],
            {"open": 2, "in_progress": 1, "resolved": 1, "closed": 1},
        )

    def test_by_priority(self):
        response = self.get_as(self.admin)
        self.assertEqual(
            response.data["by_priority"],
            {"low": 1, "medium": 1, "high": 2, "urgent": 1},
        )

    def test_by_category_includes_empty_and_inactive_sorted_by_name(self):
        response = self.get_as(self.admin)
        self.assertEqual(
            response.data["by_category"],
            [
                {"id": self.empty.pk, "name": "St Empty", "count": 0},
                {"id": self.roads.pk, "name": "St Roads", "count": 3},
                {"id": self.water.pk, "name": "St Water", "count": 2},
            ],
        )

    def test_empty_database_returns_all_keys_with_zeros(self):
        ServiceRequest.objects.all().delete()
        response = self.get_as(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_requests"], 0)
        self.assertEqual(response.data["unassigned"], 0)
        self.assertEqual(
            response.data["by_status"],
            {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0},
        )
        self.assertEqual(
            response.data["by_priority"],
            {"low": 0, "medium": 0, "high": 0, "urgent": 0},
        )
        self.assertTrue(all(c["count"] == 0 for c in response.data["by_category"]))

    def test_uses_two_queries(self):
        self.client.force_authenticate(self.admin)
        with self.assertNumQueries(2):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ---- access ----
    def test_citizen_forbidden(self):
        self.assertEqual(self.get_as(self.citizen).status_code, status.HTTP_403_FORBIDDEN)

    def test_officer_forbidden(self):
        self.assertEqual(self.get_as(self.officer).status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_unauthorized(self):
        self.assertEqual(self.get_as(None).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_not_allowed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)