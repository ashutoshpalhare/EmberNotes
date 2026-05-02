from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from notes.models import Note


class Command(BaseCommand):
    help = "Permanently delete notes that have been in the trash longer than --days (default 30)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        count, _ = Note.objects.filter(deleted_at__lt=cutoff).delete()
        self.stdout.write(f"Deleted {count} object(s) trashed before {cutoff:%Y-%m-%d}.")
