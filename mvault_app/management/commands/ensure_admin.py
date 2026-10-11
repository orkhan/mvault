import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from mvault_app.models import User

class Command(BaseCommand):
    help = "Create the initial mVault administrator when missing."
    def handle(self, *args, **options):
        email = settings.ADMIN_EMAIL
        password = settings.ADMIN_PASSWORD
        admin = User.objects.filter(email=email).first()
        if admin:
            if not admin.is_admin:
                admin.is_admin = True
                admin.is_staff = True
                admin.save(update_fields=["is_admin", "is_staff"])
            self.stdout.write("mVault administrator already exists")
            return
        if not password:
            raise CommandError("Set MVAULT_ADMIN_PASSWORD to initialize the administrator")
        admin = User.objects.create_superuser(email=email, password=password, full_name="mVault Administrator")
        if os.environ.get("MVAULT_ADMIN_MUST_CHANGE", "").lower() in {"1", "true", "yes"}:
            admin.must_change_password = True
            admin.save(update_fields=["must_change_password"])
        self.stdout.write("Created mVault administrator")
