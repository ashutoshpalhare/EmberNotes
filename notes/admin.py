from django.contrib import admin

from .models import Note, Tag


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("display_title", "user", "is_pinned", "is_archived", "deleted_at", "updated_at")
    list_filter = ("is_pinned", "is_archived")
    search_fields = ("title", "user__username")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "user")
