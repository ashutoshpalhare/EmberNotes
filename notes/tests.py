import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import parse_tags
from .models import Note, Tag

User = get_user_model()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="pw-alice-123!")
        cls.bob = User.objects.create_user("bob", password="pw-bob-123!")

    def setUp(self):
        self.client.force_login(self.alice)

    def note(self, user=None, **kw):
        return Note.objects.create(user=user or self.alice, **kw)

    def autosave(self, note, **data):
        return self.client.post(reverse("notes:autosave", args=[note.pk]),
                                json.dumps(data), content_type="application/json")


class AuthTests(Base):
    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        for name, args in [("notes:list", []), ("notes:edit", [1]), ("notes:autosave", [1])]:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 302)
            self.assertIn("/accounts/login/", r.url)

    def test_signup_creates_user_and_logs_in(self):
        self.client.logout()
        r = self.client.post(reverse("signup"), {"username": "carol", "password1": "Sturdy-pass-9876", "password2": "Sturdy-pass-9876"})
        self.assertRedirects(r, reverse("notes:list"))
        self.assertTrue(User.objects.filter(username="carol").exists())
        self.assertEqual(self.client.get(reverse("notes:list")).status_code, 200)

    def test_weak_password_rejected(self):
        self.client.logout()
        r = self.client.post(reverse("signup"), {"username": "dan", "password1": "12345678", "password2": "12345678"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="dan").exists())

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)


class IsolationTests(Base):
    def test_other_users_note_is_404_everywhere(self):
        n = self.note(self.bob, title="secret")
        self.assertEqual(self.client.get(reverse("notes:edit", args=[n.pk])).status_code, 404)
        self.assertEqual(self.autosave(n, title="hacked").status_code, 404)
        for action in ["pin", "archive", "trash", "restore", "delete"]:
            self.assertEqual(self.client.post(reverse("notes:action", args=[n.pk, action])).status_code, 404)
        n.refresh_from_db()
        self.assertEqual(n.title, "secret")

    def test_list_only_shows_own_notes(self):
        self.note(title="mine")
        self.note(self.bob, title="theirs")
        r = self.client.get(reverse("notes:list"))
        self.assertContains(r, "mine")
        self.assertNotContains(r, "theirs")

    def test_tags_are_per_user(self):
        n = self.note(self.bob)
        n.set_tags(["shared"])
        self.assertEqual(self.client.get(reverse("notes:list"), {"tag": "shared"}).context["page"].paginator.count, 0)

    def test_empty_trash_only_affects_own(self):
        mine = self.note(deleted_at=timezone.now())
        theirs = self.note(self.bob, deleted_at=timezone.now())
        self.client.post(reverse("notes:empty_trash"))
        self.assertFalse(Note.objects.filter(pk=mine.pk).exists())
        self.assertTrue(Note.objects.filter(pk=theirs.pk).exists())


class CrudTests(Base):
    def test_create_redirects_to_editor(self):
        r = self.client.post(reverse("notes:create"))
        note = Note.objects.get(user=self.alice)
        self.assertRedirects(r, reverse("notes:edit", args=[note.pk]))

    def test_create_rejects_get(self):
        self.assertEqual(self.client.get(reverse("notes:create")).status_code, 405)

    def test_form_save_updates_note_and_tags(self):
        n = self.note()
        r = self.client.post(reverse("notes:edit", args=[n.pk]), {"title": "Plan", "body": "Ship it", "tags": "Work, Ideas, work"})
        self.assertRedirects(r, reverse("notes:edit", args=[n.pk]))
        n.refresh_from_db()
        self.assertEqual((n.title, n.body), ("Plan", "Ship it"))
        self.assertEqual(sorted(t.name for t in n.tags.all()), ["ideas", "work"])

    def test_title_too_long_is_rejected(self):
        n = self.note(title="ok")
        r = self.client.post(reverse("notes:edit", args=[n.pk]), {"title": "x" * 201, "body": "", "tags": ""})
        self.assertEqual(r.status_code, 200)
        n.refresh_from_db()
        self.assertEqual(n.title, "ok")

    def test_title_is_escaped(self):
        self.note(title="<script>alert(1)</script>")
        r = self.client.get(reverse("notes:list"))
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")


class AutosaveTests(Base):
    def test_autosave_saves_content_and_tags(self):
        n = self.note()
        r = self.autosave(n, title="T", body="B", tags="a, b")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        n.refresh_from_db()
        self.assertEqual((n.title, n.body), ("T", "B"))
        self.assertEqual(n.tag_string(), "a, b")

    def test_autosave_validation_error(self):
        n = self.note(title="keep")
        r = self.autosave(n, title="x" * 500)
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())
        r = self.autosave(n, title="ok", tags=",".join(f"t{i}" for i in range(11)))
        self.assertEqual(r.status_code, 400)
        n.refresh_from_db()
        self.assertEqual(n.title, "keep")

    def test_autosave_bad_json(self):
        n = self.note()
        r = self.client.post(reverse("notes:autosave", args=[n.pk]), "not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_autosave_trashed_note_conflicts(self):
        n = self.note(deleted_at=timezone.now())
        self.assertEqual(self.autosave(n, title="x").status_code, 409)

    def test_autosave_get_not_allowed(self):
        n = self.note()
        self.assertEqual(self.client.get(reverse("notes:autosave", args=[n.pk])).status_code, 405)

    def test_orphan_tags_removed(self):
        n = self.note()
        self.autosave(n, tags="temp")
        self.autosave(n, tags="")
        self.assertFalse(Tag.objects.filter(user=self.alice).exists())


class WorkflowTests(Base):
    def act(self, n, action, **extra):
        return self.client.post(reverse("notes:action", args=[n.pk, action]), extra)

    def test_pin_toggle_does_not_change_updated_at(self):
        n = self.note()
        before = Note.objects.get(pk=n.pk).updated_at
        self.act(n, "pin")
        n.refresh_from_db()
        self.assertTrue(n.is_pinned)
        self.assertEqual(n.updated_at, before)
        self.act(n, "pin")
        n.refresh_from_db()
        self.assertFalse(n.is_pinned)

    def test_archive_and_unarchive(self):
        n = self.note(is_pinned=True)
        self.act(n, "archive")
        n.refresh_from_db()
        self.assertTrue(n.is_archived)
        self.assertFalse(n.is_pinned)
        self.assertEqual(self.client.get(reverse("notes:list")).context["page"].paginator.count, 0)
        self.assertEqual(self.client.get(reverse("notes:list"), {"view": "archive"}).context["page"].paginator.count, 1)
        self.act(n, "archive")
        n.refresh_from_db()
        self.assertFalse(n.is_archived)

    def test_trash_restore_delete(self):
        n = self.note(is_pinned=True)
        self.act(n, "trash")
        n.refresh_from_db()
        self.assertTrue(n.is_trashed)
        self.assertFalse(n.is_pinned)
        self.assertEqual(self.client.get(reverse("notes:list"), {"view": "trash"}).context["page"].paginator.count, 1)
        self.act(n, "pin")  # blocked while trashed
        n.refresh_from_db()
        self.assertFalse(n.is_pinned)
        self.act(n, "restore")
        n.refresh_from_db()
        self.assertFalse(n.is_trashed)
        self.act(n, "delete")  # must be trashed first
        self.assertTrue(Note.objects.filter(pk=n.pk).exists())
        self.act(n, "trash")
        self.act(n, "delete")
        self.assertFalse(Note.objects.filter(pk=n.pk).exists())

    def test_actions_require_post_and_known_action(self):
        n = self.note()
        self.assertEqual(self.client.get(reverse("notes:action", args=[n.pk, "trash"])).status_code, 405)
        self.assertEqual(self.act(n, "explode").status_code, 404)

    def test_open_redirect_blocked(self):
        n = self.note()
        r = self.act(n, "pin", next="https://evil.example/")
        self.assertRedirects(r, reverse("notes:list"))

    def test_trashed_note_is_read_only(self):
        n = self.note(title="old", deleted_at=timezone.now())
        self.client.post(reverse("notes:edit", args=[n.pk]), {"title": "new", "body": "", "tags": ""})
        n.refresh_from_db()
        self.assertEqual(n.title, "old")
        self.assertContains(self.client.get(reverse("notes:edit", args=[n.pk])), "in the trash")

    def test_purge_trash_command(self):
        old = self.note(deleted_at=timezone.now() - timedelta(days=40))
        fresh = self.note(deleted_at=timezone.now() - timedelta(days=2))
        call_command("purge_trash", stdout=open("/dev/null", "w"))
        self.assertFalse(Note.objects.filter(pk=old.pk).exists())
        self.assertTrue(Note.objects.filter(pk=fresh.pk).exists())


class SearchSortTests(Base):
    def count(self, **params):
        return self.client.get(reverse("notes:list"), params).context["page"].paginator.count

    def test_search_title_body_and_tag(self):
        a = self.note(title="Groceries", body="milk and eggs")
        b = self.note(title="Roadmap", body="launch plan")
        b.set_tags(["work"])
        self.assertEqual(self.count(q="groceries"), 1)
        self.assertEqual(self.count(q="EGGS"), 1)
        self.assertEqual(self.count(q="work"), 1)
        self.assertEqual(self.count(q="milk plan"), 0)  # every word must match
        self.assertEqual(self.count(q="nothing"), 0)
        self.assertEqual(self.count(), 2)

    def test_tag_filter(self):
        a = self.note(title="A")
        a.set_tags(["x"])
        self.note(title="B")
        self.assertEqual(self.count(tag="x"), 1)

    def test_search_does_not_duplicate_multi_tag_notes(self):
        n = self.note(title="A")
        n.set_tags(["work-a", "work-b"])
        self.assertEqual(self.count(q="work"), 1)

    def test_empty_search_state_rendered(self):
        r = self.client.get(reverse("notes:list"), {"q": "zzz"})
        self.assertContains(r, "No notes match")

    def test_sort_title_and_pinned_first(self):
        self.note(title="banana")
        self.note(title="apple")
        self.note(title="zebra", is_pinned=True)
        r = self.client.get(reverse("notes:list"), {"sort": "title"})
        self.assertEqual([n.title for n in r.context["page"].object_list], ["zebra", "apple", "banana"])

    def test_invalid_params_fall_back(self):
        self.assertEqual(self.client.get(reverse("notes:list"), {"view": "x", "sort": "y", "page": "abc"}).status_code, 200)

    def test_pagination(self):
        Note.objects.bulk_create([Note(user=self.alice, title=f"n{i}") for i in range(30)])
        r = self.client.get(reverse("notes:list"), {"page": 2})
        self.assertEqual(len(r.context["page"].object_list), 6)


class UnitTests(TestCase):
    def test_parse_tags(self):
        self.assertEqual(parse_tags(" Work , #ideas,WORK,, "), ["work", "ideas"])
        self.assertEqual(parse_tags(""), [])

    def test_error_pages_render(self):
        self.assertEqual(self.client.get("/definitely-missing/").status_code, 404)
        self.assertContains(self.client.get("/definitely-missing/"), "Note not found", status_code=404)
