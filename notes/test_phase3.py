import json
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Note

User = get_user_model()


class PhaseThreeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("phase3-alice", password="Strong-pass-123!")
        cls.bob = User.objects.create_user("phase3-bob", password="Strong-pass-456!")

    def setUp(self):
        self.client.force_login(self.alice)

    def test_export_contains_only_current_users_notes_and_is_private(self):
        Note.objects.create(user=self.alice, title="My note", body="Private body")
        Note.objects.create(user=self.bob, title="Other user's secret", body="Do not export")
        response = self.client.get(reverse("notes:export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        payload = json.loads(response.content)
        self.assertEqual(payload["format"], "ember-notes")
        self.assertEqual(payload["version"], 1)
        self.assertEqual([item["title"] for item in payload["notes"]], ["My note"])
        self.assertNotIn("Other user's secret", response.content.decode())

    def test_import_creates_notes_and_tags_for_current_user(self):
        payload = {"format": "ember-notes", "version": 1, "notes": [{
            "title": "Imported", "body": "Hello **world**", "tags": ["Work", "ideas"],
            "is_pinned": True, "is_archived": False, "deleted_at": None,
        }]}
        upload = SimpleUploadedFile("backup.json", json.dumps(payload).encode(), content_type="application/json")
        response = self.client.post(reverse("notes:import"), {"file": upload})
        self.assertRedirects(response, reverse("notes:list"))
        note = Note.objects.get(user=self.alice, title="Imported")
        self.assertEqual(note.body, "Hello **world**")
        self.assertTrue(note.is_pinned)
        self.assertEqual(sorted(note.tags.values_list("name", flat=True)), ["ideas", "work"])
        self.assertFalse(Note.objects.filter(user=self.bob, title="Imported").exists())

    def test_invalid_import_is_rejected_without_partial_writes(self):
        payload = {"format": "ember-notes", "version": 1, "notes": [
            {"title": "Valid-looking", "body": "ok", "tags": []},
            {"title": "x" * 201, "body": "too long title", "tags": []},
        ]}
        upload = SimpleUploadedFile("bad.json", json.dumps(payload).encode(), content_type="application/json")
        response = self.client.post(reverse("notes:import"), {"file": upload})
        self.assertRedirects(response, reverse("notes:import"))
        self.assertFalse(Note.objects.filter(user=self.alice, title="Valid-looking").exists())

    def test_markdown_preview_sanitizes_script_and_javascript_links(self):
        response = self.client.post(
            reverse("notes:preview"),
            data=json.dumps({"body": "# Safe heading\n\n<script>alert(1)</script>\n\n[bad](javascript:alert(2))"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        html = response.json()["html"]
        self.assertIn("<h1>Safe heading</h1>", html)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("href=\"javascript:", html.lower())

    def test_markdown_preview_requires_auth_and_rejects_bad_payload(self):
        self.client.logout()
        response = self.client.post(reverse("notes:preview"), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.alice)
        response = self.client.post(reverse("notes:preview"), data="[]", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_import_page_and_export_route_require_auth(self):
        self.assertEqual(self.client.get(reverse("notes:import")).status_code, 200)
        self.client.logout()
        for name in ("notes:import", "notes:export"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
