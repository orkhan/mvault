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
            if not admin.is_admin:
                # Members choose their own e-mail address, so one could claim the configured administrator
                # address before an operator switches MVAULT_ADMIN_EMAIL to it. Promote only when there is no
                # administrator at all (an operator deliberately designating an account).
                if User.objects.filter(is_admin=True).exists():
                    raise CommandError("MVAULT_ADMIN_EMAIL belongs to a member account while another administrator exists; choose another address")
                admin.is_admin = True
                admin.is_staff = True
                admin.save(update_fields=["is_admin", "is_staff"])
            self.stdout.write("mVault administrator already exists")
            return
        if not password:
            raise CommandError("Set MVAULT_ADMIN_PASSWORD to initialize the administrator")
        admin = User.objects.create_superuser(email=email, password=password, full_name="mVault Administrator")
        # The bootstrap password may sit in container logs or a secrets file; it is never meant to stay in use.
        admin.must_change_password = True
        admin.save(update_fields=["must_change_password"])
        self.stdout.write("Created mVault administrator")
