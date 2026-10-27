import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Restore a SQLite database backup. This replaces the live database; stop the application first."

    def add_arguments(self, parser):
        parser.add_argument("backup", help="Path to a verified SQLite backup file")
        parser.add_argument("--confirm", action="store_true", help="Required to replace the live database")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Restore is destructive. Stop the app and rerun with --confirm after verifying the backup.")
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError(
                "This command supports SQLite only. Restore PostgreSQL with your provider's documented restore process or pg_restore."
            )

        source = Path(options["backup"]).expanduser().resolve()
        target = Path(database["NAME"]).resolve()
        if not source.is_file():
            raise CommandError(f"Backup file not found: {source}")
        if source == target:
            raise CommandError("The backup path must differ from the live database path.")
        try:
            with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as backup_db:
                result = backup_db.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    raise CommandError(f"Backup integrity check failed: {result}")
        except sqlite3.Error as exc:
            raise CommandError(f"Could not read backup file: {exc}") from exc

        target.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safety_copy = target.with_name(f"{target.name}.pre-restore-{timestamp}")
        connections.close_all()
        try:
            if target.exists():
                shutil.copy2(target, safety_copy)
                try:
                    os.chmod(safety_copy, 0o600)
                except OSError:
                    pass
            temporary = target.with_name(f".{target.name}.restore-tmp")
            shutil.copy2(source, temporary)
            with sqlite3.connect(temporary) as restored_db:
                result = restored_db.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    temporary.unlink(missing_ok=True)
                    raise CommandError(f"Restored copy integrity check failed: {result}")
            os.replace(temporary, target)
            for suffix in ("-wal", "-shm"):
                Path(str(target) + suffix).unlink(missing_ok=True)
        except (OSError, sqlite3.Error) as exc:
            raise CommandError(f"Restore failed: {exc}") from exc

        message = f"SQLite database restored from {source}."
        if safety_copy.exists():
            message += f" Previous database preserved at {safety_copy}."
        self.stdout.write(self.style.SUCCESS(message))
