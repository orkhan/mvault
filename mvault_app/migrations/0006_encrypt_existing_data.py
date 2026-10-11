import json
from django.db import migrations
from mvault_app.crypto import PREFIX, decrypt_text, encrypt_text

TARGETS = [("mvault_app_record", "data"), ("mvault_app_recordrevision", "snapshot"), ("mvault_app_attachment", "meta")]


def encrypt_plaintext_rows(apps, schema_editor):
    """Encrypt every value column still holding plaintext JSON. Already-encrypted rows are skipped."""
    cursor = schema_editor.connection.cursor()
    for table, column in TARGETS:
        cursor.execute(f'SELECT id, "{column}" FROM {table} WHERE "{column}" NOT LIKE %s', [PREFIX + "%"])
        for row_id, raw in cursor.fetchall():
            json.loads(raw)  # refuse to wrap anything that is not valid JSON
            cursor.execute(f'UPDATE {table} SET "{column}" = %s WHERE id = %s', [encrypt_text(raw), row_id])


def decrypt_rows(apps, schema_editor):
    """Reverse: restore plaintext JSON text so 0005 can convert the columns back to jsonb."""
    cursor = schema_editor.connection.cursor()
    for table, column in TARGETS:
        cursor.execute(f'SELECT id, "{column}" FROM {table} WHERE "{column}" LIKE %s', [PREFIX + "%"])
        for row_id, raw in cursor.fetchall():
            cursor.execute(f'UPDATE {table} SET "{column}" = %s WHERE id = %s', [decrypt_text(raw), row_id])


class Migration(migrations.Migration):

    dependencies = [
        ('mvault_app', '0005_encrypt_columns'),
    ]

    operations = [
        migrations.RunPython(encrypt_plaintext_rows, decrypt_rows),
    ]
