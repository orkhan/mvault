import os
from django.core.management.base import BaseCommand, CommandError
from mvault_app.models import User

class Command(BaseCommand):
    help = "Create the initial mVault administrator when missing."
    def handle(self, *args, **options):
        email = (os.environ.get("MVAULT_ADMIN_EMAIL") or "admin@mvault.local").strip().lower()
        password = os.environ.get("MVault_ADMIN_PASSWORD") or os.environ.get("MVAULT_ADMIN_PASSWORD")
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
        User.objects.create_superuser(email=email, password=password, full_name="mVault Administrator")
        self.stdout.write("Created mVault administrator")
