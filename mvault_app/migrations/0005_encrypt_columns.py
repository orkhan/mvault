from django.db import migrations
import mvault_app.fields


class Migration(migrations.Migration):
    """Convert vault value columns from jsonb to text (existing rows keep their plaintext JSON until 0006)."""

    dependencies = [
        ('mvault_app', '0004_v020_schema'),
    ]

    operations = [
        migrations.AlterField(
            model_name='record',
            name='data',
            field=mvault_app.fields.EncryptedJSONField(default=dict),
        ),
        migrations.AlterField(
            model_name='recordrevision',
            name='snapshot',
            field=mvault_app.fields.EncryptedJSONField(default=dict),
        ),
    ]
