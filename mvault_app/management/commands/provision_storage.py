import time
from botocore.exceptions import ClientError, EndpointConnectionError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from mvault_app import storage


class Command(BaseCommand):
    help = "Create the icons, avatars and attachments buckets when they do not exist (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--wait", type=int, default=0, metavar="SECONDS", help="Retry while the storage endpoint is not reachable yet.")

    def handle(self, *args, **options):
        if not settings.S3_CONFIGURED:
            self.stdout.write("Object storage is not configured; nothing to provision.")
            return
        client = storage.get_storage().client
        deadline = time.monotonic() + options["wait"]
        for bucket in (settings.S3_ICONS_BUCKET, settings.S3_AVATARS_BUCKET, settings.S3_ATTACHMENTS_BUCKET):
            while True:
                try:
                    self._ensure(client, bucket)
                    break
                except EndpointConnectionError as exc:
                    if time.monotonic() >= deadline:
                        raise CommandError(f"Storage endpoint is not reachable: {exc}") from exc
                    time.sleep(2)
                except ClientError as exc:
                    raise CommandError(f"Could not provision bucket {bucket}: {exc}") from exc

    def _ensure(self, client, bucket):
        try:
            client.head_bucket(Bucket=bucket)
            self.stdout.write(f"Bucket {bucket}: exists")
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            kwargs = {} if settings.S3_REGION == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": settings.S3_REGION}}
            client.create_bucket(Bucket=bucket, **kwargs)
            self.stdout.write(f"Bucket {bucket}: created")
