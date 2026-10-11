import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from mvault_app.crypto import PREFIX, decrypt_text, derive_key, encrypt_text

TARGETS = [("mvault_app_record", "data"), ("mvault_app_recordrevision", "snapshot"), ("mvault_app_attachment", "meta")]


class Command(BaseCommand):
    help = (
        "Re-encrypt all stored values from an old key/salt to the current MVAULT_ENCRYPTION_KEY/SALT. "
        "Provide the previous values in OLD_MVAULT_ENCRYPTION_KEY and OLD_MVAULT_ENCRYPTION_SALT. "
        "Stop the app first and back up the database."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Decrypt everything with the old key but change nothing.")

    def handle(self, *args, **options):
        old_master, old_salt = os.environ.get("OLD_MVAULT_ENCRYPTION_KEY", ""), os.environ.get("OLD_MVAULT_ENCRYPTION_SALT", "")
        if not (old_master and old_salt):
            raise CommandError("Set OLD_MVAULT_ENCRYPTION_KEY and OLD_MVAULT_ENCRYPTION_SALT to the values currently in use.")
        old_key = derive_key(old_master, old_salt)
        new_key = derive_key(settings.ENCRYPTION_KEY, settings.ENCRYPTION_SALT)
        if old_key == new_key:
            raise CommandError("The old and new key/salt are identical; nothing to rotate.")
        total = 0
        with transaction.atomic(), connection.cursor() as cursor:
            for table, column in TARGETS:
                cursor.execute(f'SELECT id, "{column}" FROM {table} WHERE "{column}" LIKE %s', [PREFIX + "%"])
                for row_id, token in cursor.fetchall():
                    plaintext = decrypt_text(token, old_key)  # raises if the old key is wrong: nothing is committed
                    if not options["dry_run"]:
                        cursor.execute(f'UPDATE {table} SET "{column}" = %s WHERE id = %s', [encrypt_text(plaintext, new_key), row_id])
                    total += 1
        verb = "would re-encrypt" if options["dry_run"] else "re-encrypted"
        self.stdout.write(self.style.SUCCESS(f"{verb.capitalize()} {total} value(s). Remove the OLD_* variables once the app runs with the new key."))
