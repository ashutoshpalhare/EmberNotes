from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

MAX_TAGS_PER_NOTE = 10
MAX_TAG_LENGTH = 40


class Tag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="note_tags")
    name = models.CharField(max_length=MAX_TAG_LENGTH)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="unique_tag_per_user")]

    def __str__(self):
        return self.name


class NoteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False, deleted_at__isnull=True)

    def archived(self):
        return self.filter(is_archived=True, deleted_at__isnull=True)

    def trashed(self):
        return self.filter(deleted_at__isnull=False)


class Note(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="notes")
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NoteQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "-updated_at"], name="note_user_updated_idx"),
            models.Index(fields=["user", "is_pinned"], name="note_user_pinned_idx"),
            models.Index(fields=["user", "deleted_at"], name="note_user_deleted_idx"),
        ]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.title.strip() or "Untitled note"

    @property
    def is_trashed(self):
        return self.deleted_at is not None

    @transaction.atomic
    def set_tags(self, names):
        """Replace this note's tags with `names` (already cleaned) and drop orphaned tags."""
        tags = [Tag.objects.get_or_create(user=self.user, name=n)[0] for n in names]
        self.tags.set(tags)
        Tag.objects.filter(user=self.user, notes__isnull=True).delete()

    def tag_string(self):
        return ", ".join(t.name for t in self.tags.all())

    def move_to_trash(self):
        Note.objects.filter(pk=self.pk).update(deleted_at=timezone.now(), is_pinned=False, is_archived=False)
