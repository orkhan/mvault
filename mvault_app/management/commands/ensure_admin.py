from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from mvault_app.models import User

class Command(BaseCommand):
    help = "Create the initial mVault administrator when missing."
    def handle(self, *args, **options):
        email = settings.ADMIN_EMAIL
        password = settings.ADMIN_PASSWORD
        admin = User.objects.filter(email__iexact=email).first()
        if admin:
            # Never promote a member: members choose their own e-mail address, so one could claim the
            # configured administrator address before an operator changes MVAULT_ADMIN_EMAIL to it.
            if not admin.is_admin:
                raise CommandError("MVAULT_ADMIN_EMAIL belongs to a member account; choose another address for the administrator")
            self.stdout.write("mVault administrator already exists")
            return
        if not password:
            raise CommandError("Set MVAULT_ADMIN_PASSWORD to initialize the administrator")
        admin = User.objects.create_superuser(email=email, password=password, full_name="mVault Administrator")
        # The bootstrap password may sit in container logs or a secrets file; it is never meant to stay in use.
        admin.must_change_password = True
        admin.save(update_fields=["must_change_password"])
        self.stdout.write("Created mVault administrator")
