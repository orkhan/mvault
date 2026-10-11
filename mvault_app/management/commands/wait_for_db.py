import time
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

class Command(BaseCommand):
    help = "Wait for the configured database to accept a connection."
    def handle(self, *args, **options):
        deadline = time.monotonic() + 120
        while True:
            try:
                connections["default"].ensure_connection()
                self.stdout.write("Database is ready")
                return
            except OperationalError as exc:
                if time.monotonic() >= deadline:
                    raise CommandError(f"Database did not become ready: {exc}") from exc
                time.sleep(2)
