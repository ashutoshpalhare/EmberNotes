import os
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a consistent SQLite database snapshot. PostgreSQL backups should use pg_dump or provider snapshots."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="Destination .sqlite3 file (default: backups/ember-<timestamp>.sqlite3)")

    def handle(self, *args, **options):
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError(
                "This command supports SQLite only. For PostgreSQL, use pg_dump or your managed provider's backup/snapshot service."
            )

        source = Path(database["NAME"]).resolve()
        if not source.is_file():
            raise CommandError(f"Database file does not exist: {source}")

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = Path(options["output"] or (Path(settings.BASE_DIR) / "backups" / f"ember-{timestamp}.sqlite3")).expanduser().resolve()
        if source == destination:
            raise CommandError("Backup output must not be the live database file.")
        if destination.exists():
            raise CommandError(f"Refusing to overwrite an existing backup: {destination}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_db:
                with sqlite3.connect(destination) as backup_db:
                    source_db.backup(backup_db)
                    check = backup_db.execute("PRAGMA integrity_check").fetchone()[0]
                    if check != "ok":
                        raise CommandError(f"Backup integrity check failed: {check}")
            try:
                os.chmod(destination, 0o600)
            except OSError:
                pass
        except sqlite3.Error as exc:
            destination.unlink(missing_ok=True)
            raise CommandError(f"Could not create SQLite backup: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"SQLite backup created and integrity-checked: {destination}"))
