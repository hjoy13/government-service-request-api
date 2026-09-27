from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.categories.models import Category

User = get_user_model()


class CategoryAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin1", email="admin1@example.com", role=User.Role.ADMIN
        )
        cls.officer = User.objects.create_user(
            username="officer1", email="officer1@example.com", role=User.Role.OFFICER
        )
        cls.citizen = User.objects.create_user(
            username="citizen1", email="citizen1@example.com", role=User.Role.CITIZEN
        )
        cls.active = Category.objects.create(name="Roads")
        cls.inactive = Category.objects.create(name="Water Supply", is_active=False)
        cls.list_url = reverse("category-list")

    def detail_url(self, category):
        return reverse("category-detail", args=[category.pk])

    @staticmethod
    def names(response):
        return [item["name"] for item in response.data]

    # --- authentication ---------------------------------------------------

    def test_anonymous_request_is_rejected_with_401(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- visibility -------------------------------------------------------

    def test_non_admin_roles_list_only_active_categories(self):
        for user in (self.citizen, self.officer):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                response = self.client.get(self.list_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(self.names(response), ["Roads"])

    def test_admin_lists_all_categories_including_inactive(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.names(response), ["Roads", "Water Supply"])

    def test_non_admin_cannot_retrieve_inactive_category(self):
        self.client.force_authenticate(self.citizen)
        response = self.client.get(self.detail_url(self.inactive))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- create -----------------------------------------------------------

    def test_admin_can_create_category(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url, {"name": "Electricity", "description": "Power outages"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Electricity")
        self.assertTrue(response.data["is_active"])
        self.assertTrue(Category.objects.filter(name="Electricity").exists())

    def test_citizen_and_officer_cannot_create_category(self):
        for user in (self.citizen, self.officer):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                response = self.client.post(self.list_url, {"name": "Hacked"}, format="json")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Category.objects.filter(name="Hacked").exists())

    def test_create_rejects_case_insensitive_duplicate_name(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.list_url, {"name": "rOADS"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_create_rejects_blank_name(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.list_url, {"name": "   "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    # --- update -----------------------------------------------------------

    def test_admin_can_patch_category(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            self.detail_url(self.active), {"description": "Updated"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active.refresh_from_db()
        self.assertEqual(self.active.description, "Updated")

    def test_admin_can_deactivate_category(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            self.detail_url(self.active), {"is_active": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active.refresh_from_db()
        self.assertFalse(self.active.is_active)

    def test_patch_same_name_different_case_on_itself_is_allowed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.detail_url(self.active), {"name": "ROADS"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_rename_to_existing_name_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            self.detail_url(self.active), {"name": "water supply"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_citizen_cannot_patch_category(self):
        self.client.force_authenticate(self.citizen)
        response = self.client.patch(self.detail_url(self.active), {"name": "Hacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.active.refresh_from_db()
        self.assertEqual(self.active.name, "Roads")

    def test_put_is_not_allowed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.put(self.detail_url(self.active), {"name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # --- delete -----------------------------------------------------------

    def test_admin_can_delete_category(self):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.detail_url(self.active))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(pk=self.active.pk).exists())

    def test_citizen_cannot_delete_category(self):
        self.client.force_authenticate(self.citizen)
        response = self.client.delete(self.detail_url(self.active))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Category.objects.filter(pk=self.active.pk).exists())