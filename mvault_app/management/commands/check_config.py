from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError
from mvault_app import storage


class Command(BaseCommand):
    help = "Report how mVault is configured and flag problems (no secret values are printed)."

    def handle(self, *args, **options):
        problems = []
        db = settings.DATABASES["default"]
        self.stdout.write(f"Version:        {settings.APP_VERSION}")
        self.stdout.write(f"Base URL:       {settings.BASE_URL or '(not set)'}")
        self.stdout.write(f"Database:       {db['USER']}@{db['HOST']}:{db['PORT']}/{db['NAME']}")
        try:
            connection.ensure_connection()
            self.stdout.write("  connection:   ok")
        except OperationalError as exc:
            problems.append(f"Database connection failed: {exc}")
        if settings.S3_CONFIGURED:
            self.stdout.write(f"Object storage: {settings.S3_ENDPOINT_URL}")
            client = storage.get_storage().client
            for label, bucket in (("icons", settings.S3_ICONS_BUCKET), ("avatars", settings.S3_AVATARS_BUCKET), ("attachments", settings.S3_ATTACHMENTS_BUCKET)):
                try:
                    client.head_bucket(Bucket=bucket)
                    self.stdout.write(f"  {label:<12} {bucket}: ok")
                except Exception as exc:
                    problems.append(f"Bucket {bucket} ({label}) is not reachable: {exc}")
        else:
            self.stdout.write("Object storage: not configured (icons, avatars and file records are disabled)")
        if not settings.BASE_URL:
            problems.append("MVAULT_BASE_URL is not set; set it to the public URL so cookies, CSRF and hosts are configured correctly.")
        elif not settings.HTTPS_BASE:
            problems.append("MVAULT_BASE_URL is not https; passwords travel unencrypted. Put mVault behind a TLS reverse proxy.")
        if settings.DEBUG:
            problems.append("DJANGO_DEBUG is enabled; never run production with it.")
        for message in problems:
            self.stdout.write(self.style.WARNING(f"! {message}"))
        self.stdout.write(self.style.SUCCESS("Configuration looks good.") if not problems else f"{len(problems)} issue(s) found.")
