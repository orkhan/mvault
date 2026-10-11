import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mvault_app.models import Folder, Project, ProjectShare, Record, RecordShare, User


class Command(BaseCommand):
    help = "Create repeatable demo users, vault data, and shares for local mVault testing."

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("MVAULT_SEED_PASSWORD")
        if not password:
            raise CommandError("Set MVAULT_SEED_PASSWORD in .env.local before seeding.")

        alice = self._user("alice@example.test", "Alice Example", password)
        bob = self._user("bob@example.test", "Bob Example", password)

        alice_projects = self._projects(alice)
        bob_projects = self._projects(bob)
        self._records(alice, alice_projects, "alice")
        bob_records = self._records(bob, bob_projects, "bob")

        self._share_project(bob_projects["secret_vault"], alice, bob)
        self._share_record(bob_records["card"], alice, bob)

        self.stdout.write(self.style.SUCCESS(
            "Local mVault demo data is ready for alice@example.test and bob@example.test."
        ))

    def _user(self, email, full_name, password):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"full_name": full_name, "preferred_language": "en"},
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
        elif user.is_admin:
            raise CommandError(f"Seed member {email} is currently marked as an administrator.")
        return user

    def _projects(self, owner):
        definitions = {
            "password_vault": ("Passwords", "passwords", "shield"),
            "bank_cards_vault": ("Bank Cards", "cards", "card"),
            "secret_vault": ("Secrets", "secrets", "code"),
        }
        projects = {}
        for project_type, (name, _, icon) in definitions.items():
            project, _ = Project.objects.get_or_create(
                owner=owner,
                name=name,
                is_deleted=False,
                defaults={"project_type": project_type, "icon": icon},
            )
            if project.project_type != project_type:
                raise CommandError(f"Seed project {name!r} for {owner.email} has an unexpected type.")
            projects[project_type] = project
        return projects

    def _records(self, owner, projects, prefix):
        passwords = projects["password_vault"]
        cards = projects["bank_cards_vault"]
        secrets_project = projects["secret_vault"]
        dev, _ = Folder.objects.get_or_create(project=secrets_project, name="Development", is_deleted=False)
        prod, _ = Folder.objects.get_or_create(project=secrets_project, name="Production", is_deleted=False)

        password_record = self._record(
            owner, passwords, None, "Example mail account", "password",
            {"username": f"{prefix}@example.test", "password": "local-demo-password-change-me",
             "website": "https://example.test", "notes": "Fake local seed data."},
        )
        card_record = self._record(
            owner, cards, None, "Example test card", "bank_card",
            {"cardholder": owner.full_name, "number": "4111111111111111", "expiration": "12/30",
             "cvv": "123", "issuer": "Example Bank", "pin": "0000", "notes": "Fake test card data."},
        )
        self._record(
            owner, secrets_project, dev, "API_TOKEN", "variable",
            {"value": f"{prefix}-example-token-not-valid", "value_type": "secret"},
        )
        self._record(
            owner, secrets_project, dev, "PUBLIC_API_URL", "variable",
            {"value": "https://api.example.test", "value_type": "plain"},
        )
        self._record(
            owner, secrets_project, prod, "DATABASE_URL", "variable",
            {"value": "postgres://demo:replace-me@db.example.test/demo", "value_type": "secret"},
        )
        return {"password": password_record, "card": card_record}

    @staticmethod
    def _record(owner, project, folder, name, record_type, data):
        record, _ = Record.objects.get_or_create(
            owner=owner,
            project=project,
            folder=folder,
            name=name,
            is_deleted=False,
            defaults={"record_type": record_type, "data": data},
        )
        if record.record_type != record_type:
            raise CommandError(f"Seed record {name!r} for {owner.email} has an unexpected type.")
        return record

    @staticmethod
    def _share_project(project, recipient, created_by):
        if not ProjectShare.objects.filter(project=project, recipient=recipient, revoked_at__isnull=True).exists():
            ProjectShare.objects.create(project=project, recipient=recipient, created_by=created_by)

    @staticmethod
    def _share_record(record, recipient, created_by):
        if not RecordShare.objects.filter(record=record, recipient=recipient, revoked_at__isnull=True).exists():
            RecordShare.objects.create(record=record, recipient=recipient, created_by=created_by)
