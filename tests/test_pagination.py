from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.service_requests.models import ServiceRequest

User = get_user_model()
URL = "/api/v1/requests/"


class RequestListPaginationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        def make(username, role):
            return User.objects.create_user(
                username=username, email=f"{username}@example.com", role=role
            )

        cls.admin = make("pg_admin", User.Role.ADMIN)
        cls.citizen = make("pg_citizen", User.Role.CITIZEN)
        cls.other_citizen = make("pg_other_citizen", User.Role.CITIZEN)
        category = Category.objects.create(name="Pg Category")

        ServiceRequest.objects.bulk_create(
            [ServiceRequest(category=category, title=f"R{i}", description="d", created_by=cls.citizen)
             for i in range(100)]
            + [ServiceRequest(category=category, title=f"O{i}", description="d", created_by=cls.other_citizen)
               for i in range(5)]
        )
        cls.total = 105

    def get(self, user, query=""):
        self.client.force_authenticate(user)
        return self.client.get(URL + query)

    def test_default_page_shape_and_size(self):
        response = self.get(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(response.data["count"], self.total)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIn("page=2", response.data["next"])
        self.assertIsNone(response.data["previous"])

    def test_last_page(self):
        response = self.get(self.admin, "?page=6")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_page_size_query_param(self):
        response = self.get(self.admin, "?page_size=5")
        self.assertEqual(len(response.data["results"]), 5)

    def test_page_size_is_capped_at_100(self):
        response = self.get(self.admin, "?page_size=1000")
        self.assertEqual(len(response.data["results"]), 100)

    def test_invalid_page_returns_404(self):
        for query in ("?page=999", "?page=abc"):
            with self.subTest(query=query):
                self.assertEqual(self.get(self.admin, query).status_code, status.HTTP_404_NOT_FOUND)

    def test_pages_cover_every_row_exactly_once(self):
        seen = []
        for page in range(1, 7):
            seen += [item["id"] for item in self.get(self.admin, f"?page={page}").data["results"]]
        self.assertEqual(len(seen), self.total)
        self.assertEqual(set(seen), set(ServiceRequest.objects.values_list("id", flat=True)))

    def test_count_respects_role_scope(self):
        self.assertEqual(self.get(self.citizen).data["count"], 100)
        self.assertEqual(self.get(self.other_citizen).data["count"], 5)

    def test_categories_list_is_not_paginated(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/categories/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)