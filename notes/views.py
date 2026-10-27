import json
from urllib.parse import urlencode

import bleach
import markdown
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import NoteForm, parse_tags
from .models import Note

PAGE_SIZE = 24
MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_NOTES = 5000
VIEWS = {
    "all": ("All notes", "Nothing here yet", "Create your first note and it will show up here."),
    "pinned": ("Pinned", "No pinned notes", "Pin a note to keep it at the top of your list."),
    "archive": ("Archive", "Archive is empty", "Archive notes you want out of the way but not deleted."),
    "trash": ("Trash", "Trash is empty", "Deleted notes land here until you remove them for good."),
}
SORTS = {
    "updated": ("Last edited", ["-updated_at"]),
    "created": ("Date created", ["-created_at"]),
    "title": ("Title A to Z", [Lower("title").asc(), "-updated_at"]),
}
MARKDOWN_TAGS = [
    "p", "br", "hr", "strong", "em", "del", "blockquote", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6", "pre", "code", "a", "table",
    "thead", "tbody", "tr", "th", "td",
]
MARKDOWN_ATTRIBUTES = {"a": ["href", "title"], "code": ["class"]}


def _safe_next(request, fallback):
    target = request.POST.get("next", "")
    ok = url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure())
    return target if ok and target else fallback


@login_required
def note_list(request):
    view = request.GET.get("view", "all")
    if view not in VIEWS:
        view = "all"
    sort = request.GET.get("sort", "updated")
    if sort not in SORTS:
        sort = "updated"
    layout = "list" if request.GET.get("layout") == "list" else "grid"
    q = request.GET.get("q", "").strip()[:100]
    tag = request.GET.get("tag", "").strip()[:40]

    qs = Note.objects.filter(user=request.user).prefetch_related("tags")
    qs = {
        "all": qs.active(),
        "pinned": qs.active().filter(is_pinned=True),
        "archive": qs.archived(),
        "trash": qs.trashed(),
    }[view]
    if tag:
        qs = qs.filter(tags__name=tag)
    for term in q.split():
        qs = qs.filter(Q(title__icontains=term) | Q(body__icontains=term) | Q(tags__name__icontains=term))
    qs = qs.distinct()
    order = SORTS[sort][1]
    if view == "all" and not q:
        order = ["-is_pinned", *order]
    page = Paginator(qs.order_by(*order), PAGE_SIZE).get_page(request.GET.get("page"))

    params = {"view": view, "sort": sort, "layout": layout, "q": q, "tag": tag}
    base = urlencode({k: v for k, v in params.items() if v})
    heading = f"#{tag}" if tag else VIEWS[view][0]
    return render(request, "notes/list.html", {
        "page": page, "view": view, "current_view": view, "sort": sort, "layout": layout,
        "q": q, "tag": tag, "heading": heading, "empty": VIEWS[view][1:],
        "sorts": [(k, v[0]) for k, v in SORTS.items()], "qs_base": base,
        "filtered": bool(q or tag), "current_path": request.get_full_path(),
    })


@login_required
@require_POST
def note_create(request):
    note = Note.objects.create(user=request.user)
    return redirect("notes:edit", pk=note.pk)


def _own_note(request, pk):
    return get_object_or_404(Note.objects.prefetch_related("tags"), pk=pk, user=request.user)


@login_required
@require_http_methods(["GET", "POST"])
def note_edit(request, pk):
    note = _own_note(request, pk)
    readonly = note.is_trashed
    if request.method == "POST":
        if readonly:
            messages.error(request, "This note is in the trash. Restore it to edit.")
            return redirect("notes:edit", pk=note.pk)
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, "Note saved.")
            return redirect("notes:edit", pk=note.pk)
    else:
        form = NoteForm(instance=note)
    return render(request, "notes/editor.html", {
        "note": note, "form": form, "readonly": readonly, "current_view": "",
        "list_url": reverse("notes:list"), "word_count": len(note.body.split()),
    })


@login_required
@require_POST
def note_autosave(request, pk):
    note = _own_note(request, pk)
    if note.is_trashed:
        return JsonResponse({"error": "This note is in the trash."}, status=409)
    try:
        data = json.loads(request.body or b"{}")
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request."}, status=400)

    if any(key in data and not isinstance(data[key], str) for key in ("title", "body", "tags")):
        return JsonResponse({"error": "Title, body, and tags must be text."}, status=400)

    form = NoteForm({"title": data.get("title", ""), "body": data.get("body", ""),
                     "tags": data.get("tags", "")}, instance=note)
    if not form.is_valid():
        first = next(iter(form.errors.values()))[0]
        return JsonResponse({"error": first}, status=400)
    note = form.save()
    return JsonResponse({"ok": True, "updated_at": note.updated_at.isoformat()})


@login_required
@require_POST
def note_preview(request):
    """Render a small Markdown subset and sanitize the HTML before returning it."""
    try:
        data = json.loads(request.body or b"{}")
        if not isinstance(data, dict) or not isinstance(data.get("body", ""), str):
            raise ValueError
        body = data.get("body", "")
        if len(body) > 100_000:
            return JsonResponse({"error": "Preview is limited to 100,000 characters."}, status=400)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid preview request."}, status=400)

    rendered = markdown.markdown(
        body, extensions=["fenced_code", "tables", "sane_lists"], output_format="html5"
    )
    safe_html = bleach.clean(
        rendered, tags=MARKDOWN_TAGS, attributes=MARKDOWN_ATTRIBUTES,
        protocols=["http", "https", "mailto"], strip=True,
    )
    return JsonResponse({"html": safe_html})


@login_required
def export_notes(request):
    """Download only the current user's notes in a versioned JSON format."""
    notes = Note.objects.filter(user=request.user).prefetch_related("tags").order_by("pk")
    payload = {
        "format": "ember-notes",
        "version": 1,
        "exported_at": timezone.now().isoformat(),
        "notes": [{
            "title": note.title,
            "body": note.body,
            "tags": sorted(tag.name for tag in note.tags.all()),
            "is_pinned": note.is_pinned,
            "is_archived": note.is_archived,
            "deleted_at": note.deleted_at.isoformat() if note.deleted_at else None,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        } for note in notes],
    }
    response = HttpResponse(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="ember-notes-export.json"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def import_notes(request):
    if request.method == "GET":
        return render(request, "notes/import.html", {"current_view": ""})

    upload = request.FILES.get("file")
    if not upload:
        messages.error(request, "Choose an Ember JSON export file to import.")
        return redirect("notes:import")
    if upload.size > MAX_IMPORT_BYTES:
        messages.error(request, "Import files must be 2 MB or smaller.")
        return redirect("notes:import")

    try:
        payload = json.loads(upload.read().decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("format") != "ember-notes" or payload.get("version") != 1:
            raise ValueError("This is not a supported Ember Notes export.")
        records = payload.get("notes")
        if not isinstance(records, list) or len(records) > MAX_IMPORT_NOTES:
            raise ValueError("The export must contain a list of at most 5,000 notes.")
        cleaned = []
        for item in records:
            if not isinstance(item, dict):
                raise ValueError("Every note entry must be an object.")
            title, body, tags = item.get("title", ""), item.get("body", ""), item.get("tags", [])
            if not isinstance(title, str) or len(title) > 200:
                raise ValueError("A note title is invalid or longer than 200 characters.")
            if not isinstance(body, str) or len(body) > 100_000:
                raise ValueError("A note body is invalid or longer than 100,000 characters.")
            if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                raise ValueError("Note tags must be a list of text values.")
            normalized_tags = parse_tags(",".join(tags))
            if not isinstance(item.get("is_pinned", False), bool) or not isinstance(item.get("is_archived", False), bool):
                raise ValueError("Pin and archive values must be true or false.")
            deleted_at = item.get("deleted_at")
            if deleted_at is not None:
                if not isinstance(deleted_at, str):
                    raise ValueError("A deleted-at value is invalid.")
                deleted_at = timezone.datetime.fromisoformat(deleted_at)
                if timezone.is_naive(deleted_at):
                    deleted_at = timezone.make_aware(deleted_at, timezone.get_current_timezone())
            cleaned.append({
                "title": title, "body": body, "tags": normalized_tags,
                "is_pinned": item.get("is_pinned", False),
                "is_archived": item.get("is_archived", False),
                "deleted_at": deleted_at,
            })
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, OverflowError) as exc:
        messages.error(request, f"Import rejected: {exc}")
        return redirect("notes:import")

    with transaction.atomic():
        for item in cleaned:
            note = Note.objects.create(
                user=request.user, title=item["title"], body=item["body"],
                is_pinned=item["is_pinned"] and item["deleted_at"] is None,
                is_archived=item["is_archived"] and item["deleted_at"] is None,
                deleted_at=item["deleted_at"],
            )
            note.set_tags(item["tags"])
    messages.success(request, f"Imported {len(cleaned)} note{'s' if len(cleaned) != 1 else ''}.")
    return redirect("notes:list")


@login_required
@require_POST
def note_action(request, pk, action):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    qs = Note.objects.filter(pk=note.pk, user=request.user)
    fallback = reverse("notes:list")
    if action not in {"pin", "archive", "trash", "restore", "delete"}:
        raise Http404
    if action in {"pin", "archive", "trash"} and note.is_trashed:
        messages.error(request, "Restore this note first.")
    elif action == "pin":
        qs.update(is_pinned=not note.is_pinned)
        messages.success(request, "Note unpinned." if note.is_pinned else "Note pinned.")
    elif action == "archive":
        qs.update(is_archived=not note.is_archived, is_pinned=False)
        messages.success(request, "Note restored from archive." if note.is_archived else "Note archived.")
    elif action == "trash":
        note.move_to_trash()
        messages.success(request, "Moved to trash.")
    elif action == "restore":
        qs.update(deleted_at=None)
        messages.success(request, "Note restored.")
    elif action == "delete":
        if not note.is_trashed:
            messages.error(request, "Move the note to trash before deleting it forever.")
        else:
            note.delete()
            messages.success(request, "Note deleted forever.")
    return redirect(_safe_next(request, fallback))


@login_required
@require_POST
def trash_empty(request):
    count, _ = Note.objects.filter(user=request.user, deleted_at__isnull=False).delete()
    messages.success(request, "Trash emptied." if count else "Trash was already empty.")
    return redirect("notes:list")
