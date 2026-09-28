import json

from rest_framework import status
from rest_framework.test import APITestCase


class ApiDocsTests(APITestCase):
    def get_schema(self):
        response = self.client.get("/api/schema/?format=json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return json.loads(response.content)

    def test_swagger_ui_is_public(self):
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_schema_is_public_and_lists_key_paths(self):
        paths = self.get_schema()["paths"]
        for path in (
            "/api/v1/auth/register/",
            "/api/v1/auth/login/",
            "/api/v1/auth/token/refresh/",
            "/api/v1/categories/",
            "/api/v1/requests/",
            "/api/v1/requests/{id}/",
            "/api/v1/requests/{id}/assign/",
            "/api/v1/requests/{id}/comments/",
            "/api/v1/requests/{id}/attachment/",
            "/api/v1/statistics/",
        ):
            with self.subTest(path=path):
                self.assertIn(path, paths)

    def test_jwt_bearer_security_scheme_documented(self):
        schemes = self.get_schema()["components"]["securitySchemes"]
        self.assertEqual(schemes["jwtAuth"]["scheme"], "bearer")

    def test_create_request_body_excludes_server_owned_fields(self):
        schema = self.get_schema()
        body = schema["components"]["schemas"]["ServiceRequestCreateRequest"]["properties"]
        self.assertEqual(sorted(body), ["attachment", "category", "description", "priority", "title"])
        self.assertEqual(body["attachment"]["format"], "binary")

    def test_attachment_download_documented_as_binary_any_media_type(self):
        op = self.get_schema()["paths"]["/api/v1/requests/{id}/attachment/"]["get"]
        self.assertEqual(
            op["responses"]["200"]["content"],
            {"*/*": {"schema": {"type": "string", "format": "binary"}}},
        )

    def test_comments_list_documented_as_plain_array(self):
        op = self.get_schema()["paths"]["/api/v1/requests/{id}/comments/"]["get"]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(schema["type"], "array")