from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
from django.utils import timezone

from apps.categories.models import Category
from apps.service_requests.models import ServiceRequest, Status, Comment

User = get_user_model()


def make_user(username, role):
    return User.objects.create_user(username=username, email=f"{username}@example.com", role=role)


class ServiceRequestTestBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin1", User.Role.ADMIN)
        cls.officer1 = make_user("officer1", User.Role.OFFICER)
        cls.officer2 = make_user("officer2", User.Role.OFFICER)
        cls.citizen1 = make_user("citizen1", User.Role.CITIZEN)
        cls.citizen2 = make_user("citizen2", User.Role.CITIZEN)

        cls.roads = Category.objects.create(name="Roads")
        cls.water = Category.objects.create(name="Water Supply", is_active=False)

        cls.r1 = ServiceRequest.objects.create(
            category=cls.roads, title="Pothole", description="Near school",
            created_by=cls.citizen1, assigned_to=cls.officer1,
        )
        cls.r2 = ServiceRequest.objects.create(
            category=cls.roads, title="Broken streetlight", description="Main road",
            created_by=cls.citizen2, assigned_to=cls.officer2,
        )
        cls.r3 = ServiceRequest.objects.create(
            category=cls.roads, title="Blocked drain", description="Market area",
            created_by=cls.citizen1,
        )
        cls.list_url = reverse("service-request-list")

    def detail_url(self, service_request):
        return reverse("service-request-detail", args=[service_request.pk])

    @staticmethod
    def ids(response):
        return {item["id"] for item in response.data["results"]}

    def valid_payload(self, **overrides):
        data = {
            "category": self.roads.pk,
            "title": "Overflowing garbage bin",
            "description": "Not collected for a week",
            "priority": ServiceRequest.Priority.HIGH,
        }
        data.update(overrides)
        return data


class ServiceRequestCreateTests(ServiceRequestTestBase):
    def test_citizen_can_create_request_with_server_controlled_fields(self):
        self.client.force_authenticate(self.citizen1)

        response = self.client.post(self.list_url, self.valid_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = ServiceRequest.objects.get(pk=response.data["id"])
        self.assertEqual(created.created_by, self.citizen1)
        self.assertEqual(created.status, ServiceRequest.Status.OPEN)
        self.assertIsNone(created.assigned_to)
        self.assertEqual(created.priority, ServiceRequest.Priority.HIGH)

    def test_priority_defaults_to_medium_when_omitted(self):
        self.client.force_authenticate(self.citizen1)
        payload = self.valid_payload()
        del payload["priority"]

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["priority"], ServiceRequest.Priority.MEDIUM)

    def test_restricted_fields_are_rejected_on_create(self):
        self.client.force_authenticate(self.citizen1)
        before = ServiceRequest.objects.count()
        restricted = {
            "status": ServiceRequest.Status.RESOLVED,
            "assigned_to": self.officer1.pk,
            "created_by": self.citizen2.pk,
        }
        for field, value in restricted.items():
            with self.subTest(field=field):
                response = self.client.post(
                    self.list_url, self.valid_payload(**{field: value}), format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.assertEqual(ServiceRequest.objects.count(), before)

    def test_inactive_category_is_rejected(self):
        self.client.force_authenticate(self.citizen1)
        response = self.client.post(
            self.list_url, self.valid_payload(category=self.water.pk), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", response.data)

    def test_nonexistent_category_is_rejected(self):
        self.client.force_authenticate(self.citizen1)
        response = self.client.post(self.list_url, self.valid_payload(category=999999), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", response.data)

    def test_invalid_priority_is_rejected(self):
        self.client.force_authenticate(self.citizen1)
        response = self.client.post(
            self.list_url, self.valid_payload(priority="CRITICAL"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("priority", response.data)

    def test_officer_and_admin_cannot_create_requests(self):
        before = ServiceRequest.objects.count()
        for user in (self.officer1, self.admin):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                response = self.client.post(self.list_url, self.valid_payload(), format="json")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ServiceRequest.objects.count(), before)

    def test_anonymous_cannot_create_or_list(self):
        self.assertEqual(
            self.client.post(self.list_url, self.valid_payload(), format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED)


class ServiceRequestVisibilityTests(ServiceRequestTestBase):
    def test_citizen_lists_only_own_requests(self):
        self.client.force_authenticate(self.citizen1)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.r1.pk, self.r3.pk})

    def test_citizen_cannot_retrieve_another_citizens_request(self):
        self.client.force_authenticate(self.citizen1)
        response = self.client.get(self.detail_url(self.r2))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_officer_lists_only_requests_assigned_to_self(self):
        self.client.force_authenticate(self.officer1)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.r1.pk})

    def test_officer_cannot_retrieve_other_or_unassigned_requests(self):
        self.client.force_authenticate(self.officer1)
        for other in (self.r2, self.r3):
            with self.subTest(request=other.title):
                response = self.client.get(self.detail_url(other))
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_lists_all_requests(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.r1.pk, self.r2.pk, self.r3.pk})

    def test_admin_can_retrieve_any_request(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.detail_url(self.r2))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created_by"], self.citizen2.pk)

    def test_put_and_delete_are_not_allowed(self):
        self.client.force_authenticate(self.admin)
        put = self.client.put(self.detail_url(self.r1), self.valid_payload(), format="json")
        delete = self.client.delete(self.detail_url(self.r1))
        self.assertEqual(put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(ServiceRequest.objects.filter(pk=self.r1.pk).exists())

class ServiceRequestUpdateTests(ServiceRequestTestBase):
    def patch(self, user, service_request, data):
        self.client.force_authenticate(user)
        return self.client.patch(self.detail_url(service_request), data, format="json")

    # --- citizen ----------------------------------------------------------

    def test_citizen_can_edit_content_of_own_open_request(self):
        electricity = Category.objects.create(name="Electricity")

        response = self.patch(self.citizen1, self.r1, {
            "title": "Deep pothole", "description": "Getting worse", "category": electricity.pk,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.title, "Deep pothole")
        self.assertEqual(self.r1.description, "Getting worse")
        self.assertEqual(self.r1.category, electricity)

    def test_citizen_cannot_edit_after_processing_started(self):
        ServiceRequest.objects.filter(pk=self.r1.pk).update(status=ServiceRequest.Status.IN_PROGRESS)

        response = self.patch(self.citizen1, self.r1, {"title": "Changed"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.title, "Pothole")

    def test_citizen_cannot_change_staff_or_system_fields(self):
        attempts = {
            "status": ServiceRequest.Status.RESOLVED,
            "priority": ServiceRequest.Priority.URGENT,
            "assigned_to": self.officer2.pk,
            "created_by": self.citizen2.pk,
        }
        for field, value in attempts.items():
            with self.subTest(field=field):
                response = self.patch(self.citizen1, self.r1, {field: value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.status, ServiceRequest.Status.OPEN)
        self.assertEqual(self.r1.priority, ServiceRequest.Priority.MEDIUM)
        self.assertEqual(self.r1.assigned_to, self.officer1)
        self.assertEqual(self.r1.created_by, self.citizen1)

    def test_citizen_cannot_move_request_to_inactive_category(self):
        response = self.patch(self.citizen1, self.r1, {"category": self.water.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", response.data)

    def test_citizen_cannot_patch_another_citizens_request(self):
        response = self.patch(self.citizen1, self.r2, {"title": "Hijacked"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.r2.refresh_from_db()
        self.assertEqual(self.r2.title, "Broken streetlight")

    # --- officer ----------------------------------------------------------

    def test_officer_can_update_status_and_priority_of_assigned_request(self):
        response = self.patch(self.officer1, self.r1, {
            "status": ServiceRequest.Status.IN_PROGRESS,
            "priority": ServiceRequest.Priority.URGENT,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.status, ServiceRequest.Status.IN_PROGRESS)
        self.assertEqual(self.r1.priority, ServiceRequest.Priority.URGENT)

    def test_officer_cannot_edit_content_or_assignment(self):
        attempts = {
            "title": "Officer rewrite",
            "description": "Officer rewrite",
            "category": self.roads.pk,
            "assigned_to": self.officer2.pk,
        }
        for field, value in attempts.items():
            with self.subTest(field=field):
                response = self.patch(self.officer1, self.r1, {field: value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.title, "Pothole")
        self.assertEqual(self.r1.assigned_to, self.officer1)

    def test_officer_cannot_patch_other_or_unassigned_requests(self):
        for other in (self.r2, self.r3):
            with self.subTest(request=other.title):
                response = self.patch(
                    self.officer1, other, {"status": ServiceRequest.Status.RESOLVED}
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                other.refresh_from_db()
                self.assertEqual(other.status, ServiceRequest.Status.OPEN)

    # --- admin ------------------------------------------------------------

    def test_admin_can_update_status_and_priority_of_any_request(self):
        response = self.patch(self.admin, self.r2, {
            "status": ServiceRequest.Status.RESOLVED,
            "priority": ServiceRequest.Priority.LOW,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.r2.refresh_from_db()
        self.assertEqual(self.r2.status, ServiceRequest.Status.RESOLVED)
        self.assertEqual(self.r2.priority, ServiceRequest.Priority.LOW)

    def test_admin_cannot_edit_content_or_system_fields(self):
        attempts = {
            "title": "Admin rewrite",
            "assigned_to": self.officer2.pk,
            "created_by": self.citizen2.pk,
        }
        for field, value in attempts.items():
            with self.subTest(field=field):
                response = self.patch(self.admin, self.r1, {field: value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    # --- status values ----------------------------------------------------

    def test_invalid_status_value_is_rejected(self):
        response = self.patch(self.officer1, self.r1, {"status": "DONE"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_status_can_move_in_any_direction(self):
        ServiceRequest.objects.filter(pk=self.r1.pk).update(status=ServiceRequest.Status.RESOLVED)

        response = self.patch(self.officer1, self.r1, {"status": ServiceRequest.Status.OPEN})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.status, ServiceRequest.Status.OPEN)

class ServiceRequestAssignTests(APITestCase):
    

    @classmethod
    def setUpTestData(cls):
        def make(username, role, **extra):
            return User.objects.create_user(
                username=username, email=f"{username}@example.com", role=role, **extra
            )

        cls.admin = make("asg_admin", User.Role.ADMIN)
        cls.citizen = make("asg_citizen", User.Role.CITIZEN)
        cls.officer1 = make("asg_officer1", User.Role.OFFICER)
        cls.officer2 = make("asg_officer2", User.Role.OFFICER)
        cls.inactive_officer = make("asg_officer_off", User.Role.OFFICER, is_active=False)

        cls.category = Category.objects.create(name="Assign Test Category")

        cls.unassigned = ServiceRequest.objects.create(
            category=cls.category, title="Unassigned", description="d",
            created_by=cls.citizen,
        )
        cls.assigned = ServiceRequest.objects.create(
            category=cls.category, title="Assigned", description="d",
            created_by=cls.citizen, assigned_to=cls.officer1,
            status=Status.IN_PROGRESS,
        )

    def assign_url(self, pk):
        return f"/api/v1/requests/{pk}/assign/"

    def test_admin_assigns_officer_to_unassigned_request(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.assign_url(self.unassigned.pk), {"officer_id": self.officer1.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["assigned_to"], self.officer1.pk)
        self.unassigned.refresh_from_db()
        self.assertEqual(self.unassigned.assigned_to, self.officer1)

    def test_admin_reassigns_to_another_officer(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.assign_url(self.assigned.pk), {"officer_id": self.officer2.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assigned.refresh_from_db()
        self.assertEqual(self.assigned.assigned_to, self.officer2)

    def test_assignment_does_not_change_status(self):
        self.client.force_authenticate(self.admin)
        self.client.post(
            self.assign_url(self.assigned.pk), {"officer_id": self.officer2.pk}, format="json"
        )
        self.assigned.refresh_from_db()
        self.assertEqual(self.assigned.status, Status.IN_PROGRESS)

    def test_reassignment_moves_visibility_between_officers(self):
        self.client.force_authenticate(self.admin)
        self.client.post(
            self.assign_url(self.assigned.pk), {"officer_id": self.officer2.pk}, format="json"
        )
        detail = f"/api/v1/requests/{self.assigned.pk}/"

        self.client.force_authenticate(self.officer2)
        self.assertEqual(self.client.get(detail).status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.officer1)
        self.assertEqual(self.client.get(detail).status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_assignment_targets_rejected(self):
        self.client.force_authenticate(self.admin)
        cases = {
            "citizen": {"officer_id": self.citizen.pk},
            "admin": {"officer_id": self.admin.pk},
            "inactive officer": {"officer_id": self.inactive_officer.pk},
            "nonexistent": {"officer_id": 999999},
            "non-integer": {"officer_id": "abc"},
            "missing": {},
        }
        for label, body in cases.items():
            with self.subTest(label):
                response = self.client.post(
                    self.assign_url(self.unassigned.pk), body, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("officer_id", response.data)
                self.unassigned.refresh_from_db()
                self.assertIsNone(self.unassigned.assigned_to)

    def test_non_admin_roles_cannot_assign(self):
        for label, user in {"citizen": self.citizen, "officer": self.officer1}.items():
            with self.subTest(label):
                self.client.force_authenticate(user)
                response = self.client.post(
                    self.assign_url(self.assigned.pk), {"officer_id": self.officer2.pk}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assigned.refresh_from_db()
                self.assertEqual(self.assigned.assigned_to, self.officer1)

    def test_anonymous_cannot_assign(self):
        response = self.client.post(
            self.assign_url(self.unassigned.pk), {"officer_id": self.officer1.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_assign_nonexistent_request_returns_404(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.assign_url(999999), {"officer_id": self.officer1.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_on_assign_not_allowed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.assign_url(self.unassigned.pk))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

class ServiceRequestCommentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        def make(username, role):
            return User.objects.create_user(
                username=username, email=f"{username}@example.com", role=role
            )

        cls.admin = make("cmt_admin", User.Role.ADMIN)
        cls.citizen = make("cmt_citizen", User.Role.CITIZEN)
        cls.other_citizen = make("cmt_other_citizen", User.Role.CITIZEN)
        cls.officer = make("cmt_officer", User.Role.OFFICER)
        cls.other_officer = make("cmt_other_officer", User.Role.OFFICER)

        cls.category = Category.objects.create(name="Comment Test Category")
        cls.request_obj = ServiceRequest.objects.create(
            category=cls.category, title="Streetlight out", description="d",
            created_by=cls.citizen, assigned_to=cls.officer,
        )
        cls.other_request = ServiceRequest.objects.create(
            category=cls.category, title="Other", description="d",
            created_by=cls.other_citizen,
        )

    def url(self, pk=None):
        return f"/api/v1/requests/{pk or self.request_obj.pk}/comments/"

    def post_comment(self, user, text="Any update?"):
        self.client.force_authenticate(user)
        return self.client.post(self.url(), {"text": text}, format="json")

    def test_citizen_comments_on_own_request(self):
        response = self.post_comment(self.citizen)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author"], self.citizen.pk)
        self.assertEqual(response.data["service_request"], self.request_obj.pk)
        comment = Comment.objects.get(pk=response.data["id"])
        self.assertEqual(comment.author, self.citizen)
        self.assertEqual(comment.service_request, self.request_obj)

    def test_assigned_officer_can_comment(self):
        response = self.post_comment(self.officer)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author"], self.officer.pk)

    def test_admin_can_comment_on_any_request(self):
        response = self.post_comment(self.admin)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_out_of_scope_users_get_404_and_nothing_is_written(self):
        for label, user in {"other citizen": self.other_citizen, "other officer": self.other_officer}.items():
            with self.subTest(label):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_404_NOT_FOUND)
                response = self.client.post(self.url(), {"text": "sneaky"}, format="json")
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Comment.objects.count(), 0)

    def test_list_is_oldest_first_and_scoped_to_the_request(self):
        now = timezone.now()
        newer = Comment.objects.create(service_request=self.request_obj, author=self.officer, text="newer")
        older = Comment.objects.create(service_request=self.request_obj, author=self.citizen, text="older")
        Comment.objects.filter(pk=newer.pk).update(created_at=now)
        Comment.objects.filter(pk=older.pk).update(created_at=now - timedelta(minutes=5))
        Comment.objects.create(service_request=self.other_request, author=self.other_citizen, text="elsewhere")

        self.client.force_authenticate(self.citizen)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c["text"] for c in response.data], ["older", "newer"])

    def test_server_owned_fields_in_body_rejected(self):
        self.client.force_authenticate(self.citizen)
        for field, value in {
            "author": self.admin.pk,
            "service_request": self.other_request.pk,
            "id": 999,
            "created_at": "2020-01-01T00:00:00Z",
        }.items():
            with self.subTest(field):
                response = self.client.post(self.url(), {"text": "hi", field: value}, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.assertEqual(Comment.objects.count(), 0)

    def test_invalid_text_rejected(self):
        self.client.force_authenticate(self.citizen)
        for label, body in {
            "missing": {},
            "blank": {"text": ""},
            "whitespace": {"text": "   "},
            "too long": {"text": "x" * 2001},
        }.items():
            with self.subTest(label):
                response = self.client.post(self.url(), body, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("text", response.data)
        self.assertEqual(Comment.objects.count(), 0)

    def test_anonymous_gets_401(self):
        self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.post(self.url(), {"text": "hi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comments_cannot_be_edited_or_deleted(self):
        self.client.force_authenticate(self.admin)
        for method in ("put", "patch", "delete"):
            with self.subTest(method):
                response = getattr(self.client, method)(self.url(), {"text": "x"}, format="json")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)        