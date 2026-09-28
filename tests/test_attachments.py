import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.categories.models import Category
from apps.service_requests.models import ServiceRequest, Status
from apps.service_requests.validators import MAX_ATTACHMENT_SIZE

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(prefix="gsr_test_media_")
PDF_BYTES = b"%PDF-1.4 test file"
PNG_BYTES = b"png-bytes"


def pdf(name="evidence.pdf"):
    return SimpleUploadedFile(name, PDF_BYTES, content_type="application/pdf")


def png(name="photo.png"):
    return SimpleUploadedFile(name, PNG_BYTES, content_type="image/png")


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ServiceRequestAttachmentTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        def make(username, role):
            return User.objects.create_user(
                username=username, email=f"{username}@example.com", role=role
            )

        cls.admin = make("att_admin", User.Role.ADMIN)
        cls.citizen = make("att_citizen", User.Role.CITIZEN)
        cls.other_citizen = make("att_other_citizen", User.Role.CITIZEN)
        cls.officer = make("att_officer", User.Role.OFFICER)
        cls.other_officer = make("att_other_officer", User.Role.OFFICER)

        cls.category = Category.objects.create(name="Attachment Test Category")
        cls.with_file = ServiceRequest.objects.create(
            category=cls.category, title="With file", description="d",
            created_by=cls.citizen, assigned_to=cls.officer, attachment=pdf(),
        )
        cls.without_file = ServiceRequest.objects.create(
            category=cls.category, title="No file", description="d",
            created_by=cls.citizen, assigned_to=cls.officer,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    # ---- helpers ----
    def detail_url(self, obj):
        return f"/api/v1/requests/{obj.pk}/"

    def download_url(self, obj):
        return f"/api/v1/requests/{obj.pk}/attachment/"

    def create_with(self, file):
        self.client.force_authenticate(self.citizen)
        return self.client.post(
            "/api/v1/requests/",
            {"category": self.category.pk, "title": "t", "description": "d", "attachment": file},
            format="multipart",
        )

    def patch_attachment(self, user, obj):
        self.client.force_authenticate(user)
        return self.client.patch(self.detail_url(obj), {"attachment": png()}, format="multipart")

    def get_download(self, user, obj):
        if user is not None:
            self.client.force_authenticate(user)
        return self.client.get(self.download_url(obj))

    def assert_download_ok(self, user):
        response = self.get_download(user, self.with_file)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), PDF_BYTES)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))

    # ---- upload on create ----
    def test_citizen_creates_request_with_pdf(self):
        response = self.create_with(pdf("My Report.PDF"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["has_attachment"])
        self.assertNotIn("attachment", response.data)

        name = ServiceRequest.objects.get(pk=response.data["id"]).attachment.name
        self.assertTrue(name.startswith("service_requests/"))
        self.assertTrue(name.endswith(".pdf"))
        self.assertNotIn("Report", name)
        self.assertTrue(os.path.exists(os.path.join(TEMP_MEDIA_ROOT, name)))

    def test_create_without_attachment_reports_false(self):
        self.client.force_authenticate(self.citizen)
        response = self.client.post(
            "/api/v1/requests/",
            {"category": self.category.pk, "title": "t", "description": "d"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["has_attachment"])

    def test_disallowed_extension_rejected(self):
        count = ServiceRequest.objects.count()
        response = self.create_with(SimpleUploadedFile("malware.exe", b"MZ"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("attachment", response.data)
        self.assertEqual(ServiceRequest.objects.count(), count)

    def test_oversized_file_rejected(self):
        count = ServiceRequest.objects.count()
        big = SimpleUploadedFile("big.pdf", b"x" * (MAX_ATTACHMENT_SIZE + 1))
        response = self.create_with(big)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("attachment", response.data)
        self.assertEqual(ServiceRequest.objects.count(), count)

    # ---- replace via PATCH ----
    def test_citizen_replaces_attachment_while_open(self):
        old_name = self.with_file.attachment.name
        response = self.patch_attachment(self.citizen, self.with_file)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.with_file.refresh_from_db()
        self.assertNotEqual(self.with_file.attachment.name, old_name)
        self.assertTrue(self.with_file.attachment.name.endswith(".png"))

    def test_citizen_cannot_replace_attachment_when_not_open(self):
        ServiceRequest.objects.filter(pk=self.with_file.pk).update(status=Status.IN_PROGRESS)
        old_name = self.with_file.attachment.name
        response = self.patch_attachment(self.citizen, self.with_file)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.with_file.refresh_from_db()
        self.assertEqual(self.with_file.attachment.name, old_name)

    def test_assigned_officer_cannot_set_attachment(self):
        response = self.patch_attachment(self.officer, self.with_file)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("attachment", response.data)

    def test_admin_cannot_set_attachment(self):
        response = self.patch_attachment(self.admin, self.with_file)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("attachment", response.data)

    # ---- download ----
    def test_owner_can_download(self):
        self.assert_download_ok(self.citizen)

    def test_assigned_officer_can_download(self):
        self.assert_download_ok(self.officer)

    def test_admin_can_download(self):
        self.assert_download_ok(self.admin)

    def test_other_citizen_gets_404(self):
        response = self.get_download(self.other_citizen, self.with_file)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_officer_gets_404(self):
        response = self.get_download(self.other_officer, self.with_file)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_request_without_file_returns_404(self):
        response = self.get_download(self.citizen, self.without_file)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], "This request has no attachment.")

    def test_anonymous_gets_401(self):
        response = self.get_download(None, self.with_file)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_file_on_disk_returns_404(self):
        obj = ServiceRequest.objects.create(
            category=self.category, title="Lost file", description="d",
            created_by=self.citizen, attachment=pdf(),
        )
        os.remove(obj.attachment.path)
        response = self.get_download(self.citizen, obj)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], "The attachment file is missing.")