from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.service_requests.models import Priority, ServiceRequest, Status

User = get_user_model()
URL = "/api/v1/requests/"


class RequestListQueryTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        def make(username, role):
            return User.objects.create_user(
                username=username, email=f"{username}@example.com", role=role
            )

        cls.admin = make("lq_admin", User.Role.ADMIN)
        cls.citizen = make("lq_citizen", User.Role.CITIZEN)
        cls.other_citizen = make("lq_other_citizen", User.Role.CITIZEN)
        cls.officer = make("lq_officer", User.Role.OFFICER)
        cls.other_officer = make("lq_other_officer", User.Role.OFFICER)

        cls.roads = Category.objects.create(name="Lq Roads")
        cls.water = Category.objects.create(name="Lq Water")

        base = timezone.now() - timedelta(days=1)

        def req(offset, owner, category, status_value, priority_value, officer, title, description="d"):
            obj = ServiceRequest.objects.create(
                category=category, title=title, description=description,
                status=status_value, priority=priority_value,
                created_by=owner, assigned_to=officer,
            )
            ServiceRequest.objects.filter(pk=obj.pk).update(created_at=base + timedelta(minutes=offset))
            return obj

        cls.r1 = req(0, cls.citizen, cls.roads, Status.OPEN, Priority.LOW, None, "Pothole near school")
        cls.r2 = req(1, cls.citizen, cls.roads, Status.IN_PROGRESS, Priority.URGENT, cls.officer, "Broken streetlight")
        cls.r3 = req(2, cls.citizen, cls.water, Status.RESOLVED, Priority.MEDIUM, cls.officer,
                     "Water leak", "Pipe burst near the school")
        cls.r4 = req(3, cls.other_citizen, cls.water, Status.OPEN, Priority.HIGH, cls.other_officer,
                     "Pothole on highway")

    def get(self, user, query=""):
        self.client.force_authenticate(user)
        return self.client.get(URL + query)

    @staticmethod
    def ids(response):
        return [item["id"] for item in response.data["results"]]

    def assert_ids(self, user, query, expected, ordered=False):
        response = self.get(user, query)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_ids = [obj.pk for obj in expected]
        if ordered:
            self.assertEqual(self.ids(response), expected_ids)
        else:
            self.assertCountEqual(self.ids(response), expected_ids)

    # ---- filters (admin sees everything) ----
    def test_filter_by_status(self):
        self.assert_ids(self.admin, "?status=OPEN", [self.r1, self.r4])

    def test_filter_by_priority(self):
        self.assert_ids(self.admin, "?priority=URGENT", [self.r2])

    def test_filter_by_category(self):
        self.assert_ids(self.admin, f"?category={self.water.pk}", [self.r3, self.r4])

    def test_filter_by_assigned_officer(self):
        self.assert_ids(self.admin, f"?assigned_to={self.officer.pk}", [self.r2, self.r3])

    def test_filter_unassigned_true_and_false(self):
        self.assert_ids(self.admin, "?unassigned=true", [self.r1])
        self.assert_ids(self.admin, "?unassigned=false", [self.r2, self.r3, self.r4])

    def test_filters_combine(self):
        self.assert_ids(self.admin, f"?status=OPEN&category={self.roads.pk}", [self.r1])

    def test_invalid_filter_values_return_400(self):
        for query, key in (("?status=FOO", "status"), ("?priority=CRITICAL", "priority"),
                           ("?category=abc", "category"), ("?assigned_to=abc", "assigned_to")):
            with self.subTest(query=query):
                response = self.get(self.admin, query)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(key, response.data)

    def test_unknown_ids_return_empty_list_not_error(self):
        self.assert_ids(self.admin, "?category=999999", [])
        self.assert_ids(self.admin, "?assigned_to=999999", [])

    # ---- search ----
    def test_search_matches_title_and_description_case_insensitive(self):
        self.assert_ids(self.admin, "?search=SCHOOL", [self.r1, self.r3])

    # ---- ordering ----
    def test_default_ordering_is_newest_first(self):
        self.assert_ids(self.admin, "", [self.r4, self.r3, self.r2, self.r1], ordered=True)

    def test_ordering_by_created_at_ascending(self):
        self.assert_ids(self.admin, "?ordering=created_at", [self.r1, self.r2, self.r3, self.r4], ordered=True)

    def test_ordering_by_priority_uses_severity_not_alphabet(self):
        self.assert_ids(self.admin, "?ordering=priority", [self.r1, self.r3, self.r4, self.r2], ordered=True)
        self.assert_ids(self.admin, "?ordering=-priority", [self.r2, self.r4, self.r3, self.r1], ordered=True)

    def test_disallowed_ordering_field_falls_back_to_default(self):
        self.assert_ids(self.admin, "?ordering=title", [self.r4, self.r3, self.r2, self.r1], ordered=True)

    # ---- filters never widen role scope ----
    def test_citizen_filter_stays_within_own_requests(self):
        self.assert_ids(self.citizen, f"?category={self.water.pk}", [self.r3])
        self.assert_ids(self.citizen, "?search=Pothole", [self.r1])

    def test_officer_cannot_see_unassigned_via_filter(self):
        self.assert_ids(self.officer, "?unassigned=true", [])

    def test_officer_cannot_see_other_officers_requests_via_filter(self):
        self.assert_ids(self.other_officer, f"?assigned_to={self.officer.pk}", [])