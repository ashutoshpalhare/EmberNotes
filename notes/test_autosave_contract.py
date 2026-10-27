import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notes.models import Note

User = get_user_model()


class AutosavePayloadContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("payload-user", password="Strong-test-pass-123!")

    def setUp(self):
        self.client.force_login(self.user)
        self.note = Note.objects.create(user=self.user, title="Original", body="Keep this")

    def post_payload(self, payload):
        return self.client.post(
            reverse("notes:autosave", args=[self.note.pk]),
            json.dumps(payload),
            content_type="application/json",
        )

    def test_rejects_non_object_json(self):
        for payload in ([], ["title"], None, "text", 42):
            with self.subTest(payload=payload):
                response = self.post_payload(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json())

    def test_rejects_non_text_fields_without_mutating_note(self):
        invalid_payloads = (
            {"title": ["unexpected", "array"]},
            {"body": {"unexpected": "object"}},
            {"tags": 123},
            {"title": None},
            {"body": True},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.post_payload(payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json())
                self.note.refresh_from_db()
                self.assertEqual(self.note.title, "Original")
                self.assertEqual(self.note.body, "Keep this")

    def test_accepts_text_fields_and_saves_them(self):
        response = self.post_payload({"title": "Updated", "body": "Text only", "tags": "work"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, "Updated")
        self.assertEqual(self.note.body, "Text only")
        self.assertEqual(self.note.tag_string(), "work")

    def test_oversized_body_is_rejected_without_mutation(self):
        response = self.post_payload({"title": "Changed", "body": "x" * 100_001, "tags": ""})
        self.assertEqual(response.status_code, 400)
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, "Original")
        self.assertEqual(self.note.body, "Keep this")
