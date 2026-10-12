from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from .forms import RecordForm
from .models import AuditEvent, Folder, Project, ProjectShare, Record, RecordRevision, RecordShare, User

@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MvaultWorkflowTests(TestCase):
    def setUp(self):
        self.alex = User.objects.create_user("alex@example.test", "Secure-Password-2026!", "Alex Member")
        self.sam = User.objects.create_user("sam@example.test", "Secure-Password-2026!", "Sam Member")
        self.admin = User.objects.create_superuser("admin@example.test", "Secure-Admin-2026!", "Admin")
        self.project = Project.objects.create(owner=self.alex, name="Passwords", project_type="password_vault")
        self.folder = Folder.objects.create(project=self.project, name="Work")
        self.record = Record.objects.create(owner=self.alex, project=self.project, folder=self.folder, record_type="password", name="Mail", data={"username": "alex", "password": "p@ssword", "website": "https://example.test", "notes": "primary"})

    def test_admin_and_member_surfaces_are_separate(self):
        self.client.force_login(self.admin)
        admin_page = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(admin_page.status_code, 200)
        self.assertContains(admin_page, "class=\"sidebar-spacer\"")
        self.assertEqual(self.client.get(reverse("record_detail", args=[self.record.id])).status_code, 403)
        self.client.force_login(self.alex)
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_member_layout_uses_full_width_sidebar_icons_and_places_version_after_logout(self):
        self.client.force_login(self.alex)
        response = self.client.get(reverse("dashboard"))
        html = response.content.decode()
        self.assertContains(response, 'href="#mv-icon-grid"')
        self.assertContains(response, 'href="#mv-icon-logout"')
        self.assertContains(response, 'class="profile profile-link"')
        self.assertContains(response, 'href="/settings/"')
        self.assertIn("max-width:none", html)
        self.assertIn("margin:0;align-self:start", html)
        self.assertIn("@media (max-width:760px)", html)
        self.assertLess(html.index("Log out"), html.index("© mVault"))
        self.assertIn("position:sticky;top:0", html)
        self.assertIn("class=\"sidebar-project-scroll\"", html)
        self.assertIn("overflow-y:auto;overscroll-behavior:contain", html)
        self.assertIn("justify-content:flex-start", html)
        self.assertIn("@media(max-width:760px)", html)
        sidebar_markup = html.split("</style>", 1)[1]
        self.assertLess(sidebar_markup.index("Your projects"), sidebar_markup.index('class="sidebar-project-scroll"'))

    def test_breadcrumbs_are_consistent_across_all_rendered_pages(self):
        def assert_breadcrumb(url, client=None):
            client = client or self.client
            response = client.get(url)
            self.assertEqual(response.status_code, 200, url)
            html = response.content.decode()
            self.assertEqual(html.count('class="breadcrumbs" aria-label="Breadcrumb"'), 1, url)

        self.client.force_login(self.alex)
        member_urls = [
            reverse("dashboard"), reverse("audit_log"), reverse("shared_items"), reverse("settings"),
            reverse("password_change"), reverse("project_create"),
            reverse("project_detail", args=[self.project.id]), reverse("project_edit", args=[self.project.id]),
            reverse("folder_create", args=[self.project.id]), reverse("folder_detail", args=[self.folder.id]),
            reverse("folder_edit", args=[self.folder.id]), reverse("record_create", args=[self.project.id]),
            reverse("record_create_in_folder", args=[self.project.id, self.folder.id]),
            reverse("record_detail", args=[self.record.id]), reverse("record_edit", args=[self.record.id]),
            reverse("record_history", args=[self.record.id]),
            reverse("share_create", args=["project", self.project.id]),
            reverse("share_create", args=["record", self.record.id]),
        ]
        for url in member_urls:
            with self.subTest(url=url):
                assert_breadcrumb(url)

        ProjectShare.objects.create(project=self.project, recipient=self.sam, created_by=self.alex)
        self.client.force_login(self.sam)
        for url in (
            reverse("shared_items"), reverse("project_detail", args=[self.project.id]),
            reverse("folder_detail", args=[self.folder.id]), reverse("record_detail", args=[self.record.id]),
            reverse("record_copy", args=[self.record.id]),
        ):
            with self.subTest(url=url):
                assert_breadcrumb(url)

        self.client.force_login(self.admin)
        for url in (
            reverse("admin_dashboard"), reverse("member_create"),
            reverse("member_password", args=[self.alex.id]), reverse("member_delete", args=[self.alex.id]),
        ):
            with self.subTest(url=url):
                assert_breadcrumb(url)

        self.alex.must_change_password = True
        self.alex.save(update_fields=["must_change_password"])
        self.client.force_login(self.alex)
        assert_breadcrumb(reverse("password_change_required"))

        self.client.logout()
        assert_breadcrumb(reverse("login"))

    def test_mobile_sidebar_starts_closed_and_has_accessible_hamburger_toggle(self):
        self.client.force_login(self.alex)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, 'class="mobile-menu-toggle secondary"')
        self.assertContains(response, 'aria-controls="app-sidebar" aria-expanded="false"')
        self.assertContains(response, 'aria-label="Open menu"')
        self.assertContains(response, 'id="app-sidebar" inert')
        self.assertContains(response, "transform:translateX(-105%)")
        self.assertContains(response, ".layout.sidebar-open aside{transform:translateX(0)}")
        self.assertContains(response, "data-sidebar-backdrop")
        self.assertContains(response, "event.key==='Escape'")

    def test_login_layout_centers_form_and_pins_copyright_footer(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('<body class="signed-out">', html)
        self.assertIn("place-items:center", html)
        self.assertIn("position:fixed", html)
        self.assertIn("@media(max-width:600px)", html)

    def test_russian_preference_localizes_dashboard_and_project_choices(self):
        self.alex.preferred_language = "ru"
        self.alex.save(update_fields=["preferred_language"])
        self.client.force_login(self.alex)

        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "Главная")
        self.assertContains(dashboard, "Ваши проекты")
        self.assertContains(dashboard, "Здравствуйте")

        project_form = self.client.get(reverse("project_create"))
        self.assertContains(project_form, "Банковские карты")
        self.assertContains(project_form, "Создать проект")

    def test_every_language_covers_all_russian_strings_and_renders(self):
        from .locales import TABLES
        from .templatetags.mvault_i18n import RU
        self.assertEqual({"az", "be", "es", "tr", "uk"}, set(TABLES))
        for code, table in TABLES.items():
            self.assertFalse(set(RU) - set(table), code)
            self.assertTrue(all(table.values()), code)
        self.client.force_login(self.alex)
        for code in TABLES:
            self.client.post(reverse("settings"), {"full_name": "Alex", "email": self.alex.email, "preferred_language": code})
            self.alex.refresh_from_db()
            self.assertEqual(self.alex.preferred_language, code)
            self.assertContains(self.client.get(reverse("dashboard")), f'<html lang="{code}"')
            self.assertContains(self.client.get(reverse("project_create")), TABLES[code]["Create a project"])
        self.client.post(reverse("settings"), {"full_name": "Alex", "email": self.alex.email, "preferred_language": "xx"})
        self.alex.refresh_from_db()
        self.assertEqual(self.alex.preferred_language, "en")

    def test_russian_record_form_localizes_field_choices(self):
        self.alex.preferred_language = "ru"
        self.alex.save(update_fields=["preferred_language"])
        self.client.force_login(self.alex)

        secret_project = Project.objects.create(owner=self.alex, name="Secrets", project_type="secret_vault")
        secret_folder = Folder.objects.create(project=secret_project, name="Development")
        response = self.client.get(reverse("record_create_in_folder", args=[secret_project.id, secret_folder.id]))
        self.assertContains(response, "Переменная окружения / секрет")
        self.assertContains(response, "Файл")
        self.assertContains(response, "Обычный текст")

    def test_record_form_offers_project_type_plus_json_and_file(self):
        extra = {"json_value", "file", "notes"}
        expected_fields = {
            "password_vault": {"name", "username", "password", "website"} | extra,
            "bank_cards_vault": {"name", "cardholder", "number", "expiration", "cvv", "issuer", "pin"} | extra,
            "secret_vault": {"name", "value", "value_type"} | extra,
        }
        for project_type, fields in expected_fields.items():
            with self.subTest(project_type=project_type):
                form = RecordForm(project_type=project_type)
                self.assertSetEqual(set(form.fields) - {"record_type"}, fields)
                self.assertEqual([kind for kind, _ in form.fields["record_type"].choices][1:], ["json", "file"])
        edit_form = RecordForm(project_type="password_vault", record_type="password")
        self.assertSetEqual(set(edit_form.fields) - {"record_type"}, {"name", "username", "password", "website", "notes"})
        with self.assertRaises(ValueError):
            RecordForm(project_type="password_vault", record_type="bank_card")

    def test_brand_assets_are_public_and_whitelisted(self):
        for path, kind in (("/favicon.ico", "image/x-icon"), ("/brand/favicon.svg", "image/svg+xml"), ("/brand/mvault-logo.svg", "image/svg+xml")):
            response = self.client.get(path)
            self.assertEqual((response.status_code, response["Content-Type"]), (200, kind))
        self.assertEqual(self.client.get("/brand/uikit.css").status_code, 404)
        self.assertEqual(self.client.get("/brand/..%2Fviews.py").status_code, 404)

    def test_bank_card_field_validation(self):
        def errors(**data):
            form = RecordForm({"record_type": "bank_card", "name": "c", **data}, project_type="bank_cards_vault", record_type="bank_card", initial={"record_type": "bank_card"})
            form.is_valid()
            return set(form.errors)
        self.assertEqual(errors(number="4111 1111 1111 1111", expiration="1/29", cvv="12", pin="12a"), {"expiration", "cvv", "pin"})
        self.assertEqual(errors(number="4111111111111112"), {"number"})
        self.assertEqual(errors(number="378282246310005", cvv="123"), {"cvv"})
        self.assertEqual(errors(number="378282246310005", cvv="1234", expiration="12/2029", pin="1234"), set())

    def test_record_type_cannot_be_changed_through_create_or_edit_post(self):
        self.client.force_login(self.alex)
        create = self.client.post(reverse("record_create", args=[self.project.id]), {
            "record_type": "bank_card", "name": "Injected card", "number": "4111111111111111",
        })
        self.assertEqual(create.status_code, 200)
        self.assertFalse(Record.objects.filter(name="Injected card").exists())

        edit = self.client.post(reverse("record_edit", args=[self.record.id]), {
            "record_type": "bank_card", "name": "Mail", "number": "4111111111111111",
        })
        self.assertEqual(edit.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.record_type, "password")

    def test_each_project_type_creates_only_its_matching_record_type(self):
        self.client.force_login(self.alex)
        definitions = [
            ("bank_cards_vault", "bank_card", "Travel card", {"cardholder": "Alex", "number": "4111111111111111"}),
            ("secret_vault", "variable", "SERVICE_TOKEN", {"value": "local-fake-token", "value_type": "secret"}),
        ]
        for project_type, record_type, name, extra in definitions:
            project = Project.objects.create(owner=self.alex, name=f"{project_type} project", project_type=project_type)
            folder = Folder.objects.create(project=project, name="Development") if project_type == "secret_vault" else None
            url = reverse("record_create_in_folder", args=[project.id, folder.id]) if folder else reverse("record_create", args=[project.id])
            form_page = self.client.get(url)
            self.assertEqual(form_page.status_code, 200)
            self.assertContains(form_page, '<select name="record_type"')
            self.assertContains(form_page, "name=\"number\"" if record_type == "bank_card" else "name=\"value\"")
            self.assertNotContains(form_page, "name=\"password\"")
            response = self.client.post(url, {
                "record_type": record_type, "name": name, **extra,
            })
            self.assertEqual(response.status_code, 302)
            record = Record.objects.get(owner=self.alex, project=project, record_type=record_type, name=name)
            self.assertEqual(record.folder_id, folder.id if folder else None)

    def test_project_type_is_read_only_after_creation(self):
        self.client.force_login(self.alex)
        response = self.client.get(reverse("project_edit", args=[self.project.id]))
        self.assertContains(response, "Passwords")
        self.assertNotContains(response, 'name="project_type"')
        self.assertContains(response, 'name="icon"')
        response = self.client.post(reverse("project_edit", args=[self.project.id]), {
            "name": "Renamed project", "project_type": "secret_vault", "icon": "database",
        })
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Renamed project")
        self.assertEqual(self.project.project_type, "password_vault")
        self.assertEqual(self.project.icon, "database")

    def test_share_pages_show_object_hierarchy_breadcrumbs(self):
        self.client.force_login(self.alex)
        project_share_page = self.client.get(reverse("share_create", args=["project", self.project.id]))
        self.assertContains(project_share_page, f'href="{reverse("dashboard")}"')
        self.assertContains(project_share_page, f'href="{reverse("project_detail", args=[self.project.id])}"')
        self.assertContains(project_share_page, "Passwords")

        record_share_page = self.client.get(reverse("share_create", args=["record", self.record.id]))
        self.assertContains(record_share_page, f'href="{reverse("project_detail", args=[self.project.id])}"')
        self.assertContains(record_share_page, f'href="{reverse("folder_detail", args=[self.folder.id])}"')
        self.assertContains(record_share_page, f'href="{reverse("record_detail", args=[self.record.id])}"')
        self.assertContains(record_share_page, "Work")
        self.assertContains(record_share_page, "Mail")

    def test_project_and_folder_icons_can_be_created_and_changed(self):
        self.client.force_login(self.alex)
        self.assertEqual(self.project.icon, "shield")
        self.assertEqual(self.folder.icon, "folder")
        new_project_form = self.client.get(reverse("project_create"))
        self.assertContains(new_project_form, 'id="id_icon_shield"')
        self.assertContains(new_project_form, 'value="shield" checked')
        created_project = self.client.post(reverse("project_create"), {
            "name": "Cloud services", "project_type": "password_vault", "icon": "cloud",
        })
        self.assertEqual(created_project.status_code, 302)
        project = Project.objects.get(owner=self.alex, name="Cloud services")
        self.assertEqual(project.icon, "cloud")
        self.assertContains(self.client.get(reverse("dashboard")), 'href="#mv-icon-cloud"')

        created_folder = self.client.post(reverse("folder_create", args=[project.id]), {
            "name": "Work", "icon": "briefcase",
        })
        self.assertEqual(created_folder.status_code, 302)
        folder = Folder.objects.get(project=project, name="Work")
        self.assertEqual(folder.icon, "briefcase")
        self.assertContains(self.client.get(reverse("folder_edit", args=[folder.id])), 'value="briefcase" checked')

        edited_folder = self.client.post(reverse("folder_edit", args=[folder.id]), {
            "name": "Personal", "icon": "star",
        })
        self.assertEqual(edited_folder.status_code, 302)
        folder.refresh_from_db()
        self.assertEqual(folder.name, "Personal")
        self.assertEqual(folder.icon, "star")

    def test_secret_projects_require_folders_and_project_tree_shows_records(self):
        self.client.force_login(self.alex)
        secrets = Project.objects.create(owner=self.alex, name="Secrets", project_type="secret_vault")
        self.assertEqual(self.client.get(reverse("record_create", args=[secrets.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("record_create", args=[secrets.id]), {
            "record_type": "variable", "name": "NO_FOLDER", "value": "secret", "value_type": "secret",
        }).status_code, 404)
        self.assertFalse(Record.objects.filter(project=secrets).exists())

        secret_folder = Folder.objects.create(project=secrets, name="Production")
        secret_record = Record.objects.create(owner=self.alex, project=secrets, folder=secret_folder, record_type="variable", name="API_TOKEN", data={"value": "token", "value_type": "secret"})
        # A legacy root record should not appear in a Secrets project tree.
        legacy_root_record = Record.objects.create(owner=self.alex, project=secrets, record_type="variable", name="LEGACY_TOKEN", data={"value": "old", "value_type": "secret"})
        secret_page = self.client.get(reverse("project_detail", args=[secrets.id]))
        self.assertContains(secret_page, "Production")
        self.assertContains(secret_page, "API_TOKEN")
        self.assertNotContains(secret_page, "LEGACY_TOKEN")
        self.assertNotContains(secret_page, "name=\"record_type\"")
        self.assertNotContains(secret_page, "Add record")
        self.assertContains(secret_page, "Add folder")

        root_record = Record.objects.create(owner=self.alex, project=self.project, record_type="password", name="Direct record", data={"password": "root"})
        tree_folder_record = Record.objects.create(owner=self.alex, project=self.project, folder=self.folder, record_type="password", name="Folder record", data={"password": "nested"})
        page = self.client.get(reverse("project_detail", args=[self.project.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "project-tree")
        self.assertContains(page, '<details class="tree-folder">', html=False)
        self.assertContains(page, 'project-page-actions project-page-actions-four')
        self.assertNotContains(page, '<details class="tree-folder" open>', html=False)
        self.assertContains(page, 'class="tree-record-entry" data-tree-record')
        self.assertNotContains(page, '<details class="tree-record-entry" data-tree-record open>', html=False)
        self.assertContains(page, 'class="tree-record">')
        self.assertContains(page, "Open record")
        self.assertContains(page, 'href="#mv-icon-chevron-right"')
        self.assertContains(page, 'href="#mv-icon-chevron-down"')
        self.assertContains(page, ".tree-folder-summary>span:nth-child(2),.tree-record>span:nth-child(2){flex:1;min-width:0}")
        self.assertContains(page, ".tree-record-entry[open]>.tree-record .tree-chevron .tree-chevron-open")
        self.assertContains(page, ".tree-record-entry[open]{margin:0 0 8px 10px;padding-left:10px;border-left:2px solid var(--border-strong)}")
        self.assertNotContains(page, "record.open=")
        self.assertContains(page, "Work")
        self.assertContains(page, "Folder record")
        self.assertContains(page, "Direct record")
        self.assertContains(page, reverse("record_detail", args=[root_record.id]))
        self.assertContains(page, reverse("record_detail", args=[tree_folder_record.id]))

    def test_project_tree_has_copy_and_reveal_actions_for_sensitive_fields(self):
        self.client.force_login(self.alex)
        cards = Project.objects.create(owner=self.alex, name="Cards", project_type="bank_cards_vault")
        card_folder = Folder.objects.create(project=cards, name="Travel")
        card = Record.objects.create(owner=self.alex, project=cards, folder=card_folder, record_type="bank_card", name="Travel card", data={
            "cardholder": "Alex Member", "number": "4111111111111111", "expiration": "12/29", "cvv": "123", "notes": "trip",
        })
        page = self.client.get(reverse("project_detail", args=[cards.id]))
        self.assertContains(page, 'href="#mv-icon-card"')
        self.assertContains(page, f'id="value-{card.id}-number"')
        self.assertContains(page, f'id="value-{card.id}-expiration"')
        self.assertContains(page, f'id="value-{card.id}-cvv"')
        self.assertContains(page, f"vaultAction(this,'reveal','expiration',{card.id})")
        self.assertContains(page, f"vaultAction(this,'copy','notes',{card.id})")
        for secret_value in ("4111111111111111", "12/29", "123"):
            self.assertNotContains(page, secret_value)

    def test_local_seed_command_creates_repeatable_demo_users_records_and_shares(self):
        from unittest.mock import patch

        with patch.dict("os.environ", {"MVAULT_SEED_PASSWORD": "Seed-Password-For-Tests-2026!"}):
            call_command("seed_local", verbosity=0)
            call_command("seed_local", verbosity=0)

        alice = User.objects.get(email="alice@example.test")
        bob = User.objects.get(email="bob@example.test")
        self.assertEqual(alice.projects.filter(is_deleted=False).count(), 3)
        self.assertEqual(bob.projects.filter(is_deleted=False).count(), 3)
        self.assertEqual(Record.objects.filter(owner=alice, is_deleted=False).count(), 5)
        self.assertEqual(Record.objects.filter(owner=bob, is_deleted=False).count(), 5)
        self.assertTrue(ProjectShare.objects.filter(project__owner=bob, recipient=alice, revoked_at__isnull=True).exists())
        self.assertTrue(RecordShare.objects.filter(record__owner=bob, recipient=alice, revoked_at__isnull=True).exists())

    def test_unshared_member_cannot_open_another_members_record(self):
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("record_detail", args=[self.record.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse("project_detail", args=[self.project.id])).status_code, 404)

    def test_shared_record_is_view_only_and_recipient_copy_is_independent(self):
        RecordShare.objects.create(record=self.record, recipient=self.sam, created_by=self.alex)
        Project.objects.create(owner=self.sam, name="Passwords", project_type="password_vault")
        self.client.force_login(self.sam)
        page = self.client.get(reverse("record_detail", args=[self.record.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "*****")
        self.assertNotContains(page, "p@ssword")
        self.assertContains(page, f'href="{reverse("shared_items")}"')
        self.assertNotContains(page, f'href="{reverse("project_detail", args=[self.project.id])}"')
        copy_page = self.client.get(reverse("record_copy", args=[self.record.id]))
        self.assertContains(copy_page, f'href="{reverse("shared_items")}"')
        self.assertContains(copy_page, f'href="{reverse("record_detail", args=[self.record.id])}"')
        self.assertContains(copy_page, "Copy shared record")
        self.assertEqual(self.client.post(reverse("record_edit", args=[self.record.id]), {"name": "Changed"}).status_code, 404)
        self.client.post(reverse("record_copy", args=[self.record.id]), {"project": Project.objects.get(owner=self.sam).id})
        copy = Record.objects.get(owner=self.sam)
        self.assertNotEqual(copy.pk, self.record.pk)
        copy.data["password"] = "recipient-value"
        copy.save()
        self.record.refresh_from_db()
        self.assertEqual(self.record.data["password"], "p@ssword")
        self.assertTrue(AuditEvent.objects.filter(action="shared_record_viewed", record=self.record).exists())

    def test_reveal_and_copy_actions_are_audited(self):
        self.client.force_login(self.alex)
        detail_page = self.client.get(reverse("record_detail", args=[self.record.id]))
        self.assertContains(detail_page, 'class="actions record-page-actions"')
        self.assertContains(detail_page, 'class="actions record-detail-actions"')
        self.assertContains(detail_page, "@media(max-width:760px)")
        self.assertContains(detail_page, ".record-field .actions>.compact-button,.record-detail-actions>button")
        response = self.client.post(reverse("record_value_action", args=[self.record.id]), {"action": "reveal", "field": "password"})
        self.assertEqual(response.json()["value"], "p@ssword")
        self.client.post(reverse("record_value_action", args=[self.record.id]), {"action": "copy", "field": "password"})
        self.assertEqual(AuditEvent.objects.filter(action__in=["value_reveal", "value_copy"], record=self.record).count(), 2)

    def test_folder_page_shows_per_field_copy_reveal_and_import_dialog(self):
        self.client.force_login(self.alex)
        response = self.client.get(reverse("folder_detail", args=[self.folder.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="actions folder-page-actions"')
        self.assertContains(response, ".folder-page-actions{grid-template-columns:repeat(2,minmax(0,1fr))}")
        self.assertContains(response, ".record-page-actions{grid-template-columns:repeat(auto-fit,minmax(85px,1fr))}")
        self.assertContains(response, ".project-page-actions{grid-template-columns:repeat(3,minmax(0,1fr))}")
        self.assertContains(response, f'id="value-{self.record.id}-password"')
        self.assertContains(response, "vaultAction(this,'reveal','password'")
        self.assertContains(response, "vaultAction(this,'copy','username'")
        self.assertContains(response, "name=\"single_delete\"")
        self.assertContains(response, "Share selected")
        self.assertContains(response, "Delete selected")

        secrets = Project.objects.create(owner=self.alex, name="Secrets", project_type="secret_vault")
        folder = Folder.objects.create(project=secrets, name="Local")
        modal = self.client.get(reverse("folder_detail", args=[folder.id]))
        self.assertContains(modal, '<dialog id="import-env-modal"', html=False)
        self.assertContains(modal, "showModal()")
        self.assertContains(modal, "Import environment variables")

    def test_folder_bulk_delete_soft_deletes_and_keeps_revisions(self):
        extra = Record.objects.create(owner=self.alex, project=self.project, folder=self.folder, record_type="password", name="Other", data={"password": "another"})
        self.client.force_login(self.alex)
        response = self.client.post(reverse("folder_record_actions", args=[self.folder.id]), {
            "bulk_action": "delete", "record_ids": [self.record.id, extra.id],
        })
        self.assertRedirects(response, reverse("folder_detail", args=[self.folder.id]))
        self.record.refresh_from_db()
        extra.refresh_from_db()
        self.assertTrue(self.record.is_deleted)
        self.assertTrue(extra.is_deleted)
        self.assertEqual(RecordRevision.objects.filter(record__in=[self.record, extra]).count(), 2)
        self.assertEqual(AuditEvent.objects.filter(action="record_deleted", record__in=[self.record, extra]).count(), 2)

    def test_folder_bulk_share_grants_only_selected_folder_records(self):
        extra = Record.objects.create(owner=self.alex, project=self.project, folder=self.folder, record_type="password", name="Other", data={"password": "another"})
        elsewhere = Record.objects.create(owner=self.alex, project=self.project, record_type="password", name="Outside", data={"password": "outside"})
        self.client.force_login(self.alex)
        response = self.client.post(reverse("folder_record_actions", args=[self.folder.id]), {
            "bulk_action": "share", "recipient": self.sam.id, "record_ids": [self.record.id, extra.id, elsewhere.id],
        })
        self.assertRedirects(response, reverse("folder_detail", args=[self.folder.id]))
        self.assertEqual(RecordShare.objects.filter(recipient=self.sam).count(), 2)
        self.assertFalse(RecordShare.objects.filter(record=elsewhere, recipient=self.sam).exists())
        self.assertEqual(AuditEvent.objects.filter(action="record_shared", record__in=[self.record, extra]).count(), 2)

    def test_folder_single_delete_rejects_records_from_another_folder(self):
        other_folder = Folder.objects.create(project=self.project, name="Personal")
        outside = Record.objects.create(owner=self.alex, project=self.project, folder=other_folder, record_type="password", name="Private", data={})
        self.client.force_login(self.alex)
        response = self.client.post(reverse("folder_record_actions", args=[self.folder.id]), {"single_delete": outside.id})
        self.assertEqual(response.status_code, 404)
        outside.refresh_from_db()
        self.assertFalse(outside.is_deleted)

    def test_dashboard_and_audit_show_readable_activity_labels_and_actor(self):
        AuditEvent.objects.create(actor=self.alex, owner=self.alex, action="value_copy", record=self.record)
        AuditEvent.objects.create(actor=self.sam, owner=self.alex, action="value_reveal", record=self.record)
        self.client.force_login(self.alex)

        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "Copied value")
        self.assertContains(dashboard, "Revealed value")
        self.assertContains(dashboard, "Alex Member")
        self.assertContains(dashboard, "Sam Member")
        self.assertNotContains(dashboard, "Value_Copy")

        audit = self.client.get(reverse("audit_log"))
        self.assertContains(audit, "Copied value")
        self.assertContains(audit, "Revealed value")
        self.assertContains(audit, "Alex Member")
        self.assertContains(audit, "alex@example.test")
        self.assertContains(audit, "Sam Member")
        self.assertNotContains(audit, "Value_Reveal")

    def test_shared_items_are_grouped_as_trees_without_expanding_record_only_access(self):
        ProjectShare.objects.create(project=self.project, recipient=self.sam, created_by=self.alex)
        secret_project = Project.objects.create(owner=self.alex, name="Shared secrets", project_type="secret_vault")
        secret_folder = Folder.objects.create(project=secret_project, name="Production")
        shared_secret = Record.objects.create(owner=self.alex, project=secret_project, folder=secret_folder, record_type="variable", name="API_TOKEN", data={"value": "token-value", "value_type": "secret"})
        private_secret = Record.objects.create(owner=self.alex, project=secret_project, folder=secret_folder, record_type="variable", name="PRIVATE_KEY", data={"value": "private-value", "value_type": "secret"})
        RecordShare.objects.create(record=shared_secret, recipient=self.sam, created_by=self.alex)

        self.client.force_login(self.sam)
        page = self.client.get(reverse("shared_items"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f'href="{reverse("dashboard")}"')
        self.assertContains(page, 'class="breadcrumbs" aria-label="Breadcrumb"')
        self.assertContains(page, 'aria-current="page">Shared with me</span>')
        self.assertContains(page, "Passwords")
        self.assertContains(page, "Mail")
        self.assertContains(page, "Shared secrets")
        self.assertContains(page, "Production")
        self.assertContains(page, "API_TOKEN")
        self.assertContains(page, 'href="#mv-icon-code"')
        self.assertNotContains(page, "PRIVATE_KEY")
        self.assertNotContains(page, "private-value")
        self.assertContains(page, 'class="tree-record-entry" data-tree-record')
        self.assertNotContains(page, '<details class="tree-record-entry" data-tree-record open>', html=False)
        self.assertContains(page, "Open record")
        self.assertContains(page, "vaultAction(this,'reveal','password'")
        self.assertContains(page, "vaultAction(this,'copy','value'")
        self.assertContains(page, '<details class="tree-folder">', html=False)
        self.assertNotContains(page, '<details class="tree-folder" open>', html=False)
        self.assertNotContains(page, reverse("folder_detail", args=[secret_folder.id]))

    def test_dashboard_and_audit_link_to_accessible_objects_but_not_account_events(self):
        AuditEvent.objects.create(actor=self.alex, owner=self.alex, action="record_updated", record=self.record)
        AuditEvent.objects.create(actor=self.alex, owner=self.alex, action="folder_updated", project=self.project, folder=self.folder)
        AuditEvent.objects.create(actor=self.alex, owner=self.alex, action="project_updated", project=self.project)
        AuditEvent.objects.create(actor=self.alex, owner=self.alex, action="login")
        self.client.force_login(self.alex)

        for url_name in ("dashboard", "audit_log"):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            self.assertIn(f'href="{reverse("record_detail", args=[self.record.id])}"', html)
            self.assertIn(f'href="{reverse("folder_detail", args=[self.folder.id])}"', html)
            self.assertIn(f'href="{reverse("project_detail", args=[self.project.id])}"', html)
            self.assertEqual(html.count('class="list-row activity-link"'), 3)

    def test_deleted_record_activity_links_to_its_history(self):
        self.record.is_deleted = True
        self.record.save(update_fields=["is_deleted"])
        AuditEvent.objects.create(actor=self.alex, owner=self.alex, action="record_deleted", record=self.record)
        self.client.force_login(self.alex)
        response = self.client.get(reverse("audit_log"))
        self.assertContains(response, f'href="{reverse("record_history", args=[self.record.id])}"')

    def test_record_update_keeps_previous_revision_and_reuses_deleted_names(self):
        self.client.force_login(self.alex)
        response = self.client.post(reverse("record_edit", args=[self.record.id]), {"record_type": "password", "name": "Mail", "username": "alex", "password": "new-secret", "website": "https://example.test", "notes": "updated"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RecordRevision.objects.get(record=self.record).snapshot["data"]["password"], "p@ssword")
        self.client.post(reverse("record_delete", args=[self.record.id]))
        self.assertEqual(self.client.post(reverse("record_create", args=[self.project.id]), {"record_type": "password", "name": "Mail", "password": "replacement"}).status_code, 302)
        self.assertEqual(Record.objects.filter(project=self.project, name="Mail", is_deleted=False).count(), 1)

    def test_env_import_upserts_keys_and_classifies_sensitive_values(self):
        secret_project = Project.objects.create(owner=self.alex, name="Secrets", project_type="secret_vault")
        env_folder = Folder.objects.create(project=secret_project, name="Dev")
        self.client.force_login(self.alex)
        upload = self._upload("API_TOKEN=first\nPUBLIC_URL=https://example.test\nDATABASE_URL=postgres://app:pass@example.test/db\n")
        self.client.post(reverse("env_import", args=[env_folder.id]), {"env_file": upload})
        upload = self._upload("API_TOKEN=second\nPUBLIC_URL=https://example.test\nDATABASE_URL=postgres://app:pass@example.test/db\n")
        self.client.post(reverse("env_import", args=[env_folder.id]), {"env_file": upload})
        token = Record.objects.get(project=secret_project, name="API_TOKEN", is_deleted=False)
        public = Record.objects.get(project=secret_project, name="PUBLIC_URL", is_deleted=False)
        db_url = Record.objects.get(project=secret_project, name="DATABASE_URL", is_deleted=False)
        self.assertEqual(token.data, {"value": "second", "value_type": "secret"})
        self.assertEqual(public.data["value_type"], "plain")
        self.assertEqual(db_url.data["value_type"], "secret")
        self.assertEqual(Record.objects.filter(project=secret_project, name="API_TOKEN", is_deleted=False).count(), 1)
        export = self.client.get(reverse("env_export", args=[env_folder.id]))
        self.assertIn(b'API_TOKEN="second"', export.content)

    @staticmethod
    def _upload(value):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile("vars.env", value.encode(), content_type="text/plain")

    def test_admin_member_create_seeds_default_projects_and_forced_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("member_create"), {"full_name": "New Person", "email": "new@example.test", "password": "Valid-New-Password-2026!"})
        self.assertEqual(response.status_code, 302)
        member = User.objects.get(email="new@example.test")
        self.assertTrue(member.must_change_password)
        self.assertSetEqual(set(member.projects.values_list("name", flat=True)), {"Passwords", "Bank Cards"})
        self.assertEqual(member.projects.get(name="Passwords").icon, "shield")
        self.assertEqual(member.projects.get(name="Bank Cards").icon, "card")

    def test_admin_member_form_has_password_visibility_control_for_generated_password(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("member_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-strong-password data-target="id_password"')
        self.assertContains(response, 'type="password" name="password"')
        self.assertContains(response, 'data-password-toggle data-target="id_password"')
        self.assertContains(response, 'aria-label="Reveal" aria-pressed="false"')
        self.assertContains(response, 'data-show-label="Reveal" data-hide-label="Hide"')
        self.assertContains(response, "const visible=field.type==='password';field.type=visible?'text':'password'")
        self.assertContains(response, "navigator.clipboard.writeText(out)")

    def test_deactivation_revokes_live_shares(self):
        project_share = ProjectShare.objects.create(project=self.project, recipient=self.sam, created_by=self.alex)
        RecordShare.objects.create(record=self.record, recipient=self.sam, created_by=self.alex)
        self.client.force_login(self.admin)
        self.client.post(reverse("member_toggle", args=[self.alex.id]))
        project_share.refresh_from_db()
        self.assertIsNotNone(project_share.revoked_at)
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("record_detail", args=[self.record.id])).status_code, 404)

    def test_temporary_password_requires_change_before_access(self):
        self.alex.must_change_password = True
        self.alex.save(update_fields=["must_change_password"])
        self.client.force_login(self.alex)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("password_change_required"))
        response = self.client.post(reverse("password_change_required"), {"old_password": "Secure-Password-2026!", "new_password1": "Fresh-Long-Password-2026!", "new_password2": "Fresh-Long-Password-2026!"})
        self.assertRedirects(response, reverse("dashboard"))
        self.alex.refresh_from_db()
        self.assertFalse(self.alex.must_change_password)

    def test_permanent_delete_transfer_moves_owned_project_and_history(self):
        self.record.revisions.create(actor=self.alex, snapshot=self.record.snapshot())
        self.client.force_login(self.admin)
        response = self.client.post(reverse("member_delete", args=[self.alex.id]), {"mode": "transfer", "target": self.sam.id})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.alex.pk).exists())
        self.project.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.project.owner, self.sam)
        self.assertEqual(self.record.owner, self.sam)
        self.assertEqual(self.record.revisions.count(), 1)

    def test_permanent_delete_purge_removes_records_and_revision_history(self):
        self.record.revisions.create(actor=self.alex, snapshot=self.record.snapshot())
        self.client.force_login(self.admin)
        self.client.post(reverse("member_delete", args=[self.alex.id]), {"mode": "purge"})
        self.assertFalse(User.objects.filter(pk=self.alex.pk).exists())
        self.assertFalse(Record.objects.filter(pk=self.record.pk).exists())
        self.assertFalse(RecordRevision.objects.exists())


import io
from unittest import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from PIL import Image
from .crypto import PREFIX, decrypt_text, encrypt_text
from .models import Attachment, LoginAttempt
from django.utils import timezone


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, bucket, key, fileobj, content_type):
        self.objects[(bucket, key)] = fileobj.read()
        fileobj.close()  # boto3 closes uploaded file objects

    def open(self, bucket, key):
        data = self.objects[(bucket, key)]
        body = mock.Mock()
        body.iter_chunks = lambda size: iter([data])
        return body, len(data)

    def delete(self, bucket, key):
        self.objects.pop((bucket, key), None)

    def copy(self, bucket, source_key, target_key):
        self.objects[(bucket, target_key)] = self.objects[(bucket, source_key)]


def png_bytes(size=(300, 200)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buffer, "PNG")
    return buffer.getvalue()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class V020FeatureTests(TestCase):
    def setUp(self):
        self.fake = FakeStorage()
        patcher = mock.patch("mvault_app.storage.get_storage", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.alex = User.objects.create_user("alex@example.test", "Secure-Password-2026!", "Alex Member")
        self.sam = User.objects.create_user("sam@example.test", "Secure-Password-2026!", "Sam Member")
        self.client.force_login(self.alex)

    def raw(self, table, column, row_id):
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT "{column}" FROM {table} WHERE id = %s', [row_id])
            return cursor.fetchone()[0]

    def test_values_are_encrypted_at_rest_and_round_trip(self):
        project = Project.objects.create(owner=self.alex, name="Passwords", project_type="password_vault")
        record = Record.objects.create(owner=self.alex, project=project, record_type="password", name="Mail", data={"password": "hunter2-plain", "username": "alex"})
        save_revision = RecordRevision.objects.create(record=record, actor=self.alex, snapshot=record.snapshot())
        for table, column, row_id in [("mvault_app_record", "data", record.pk), ("mvault_app_recordrevision", "snapshot", save_revision.pk)]:
            stored = self.raw(table, column, row_id)
            self.assertTrue(stored.startswith(PREFIX))
            self.assertNotIn("hunter2", stored)
        self.assertEqual(Record.objects.get(pk=record.pk).data["password"], "hunter2-plain")
        self.assertEqual(RecordRevision.objects.get(pk=save_revision.pk).snapshot["data"]["username"], "alex")
        self.assertNotEqual(encrypt_text("x"), encrypt_text("x"))
        self.assertEqual(decrypt_text(encrypt_text("héllo")), "héllo")

    def test_plaintext_rows_remain_readable_until_migrated(self):
        project = Project.objects.create(owner=self.alex, name="Passwords", project_type="password_vault")
        record = Record.objects.create(owner=self.alex, project=project, record_type="password", name="Legacy", data={})
        with connection.cursor() as cursor:
            cursor.execute("UPDATE mvault_app_record SET data = %s WHERE id = %s", ['{"password": "old"}', record.pk])
        self.assertEqual(Record.objects.get(pk=record.pk).data, {"password": "old"})

    def test_json_record_validates_and_renders_prettified(self):
        project = Project.objects.create(owner=self.alex, name="Configs", project_type="json_vault")
        url = reverse("record_create", args=[project.id])
        bad = self.client.post(url, {"record_type": "json", "name": "cfg", "json_value": "{not json"})
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, "Invalid JSON")
        response = self.client.post(url, {"record_type": "json", "name": "cfg", "json_value": '{"a":[1,2],"b":{"c":true}}', "notes": ""})
        record = Record.objects.get(name="cfg")
        self.assertRedirects(response, reverse("record_detail", args=[record.id]))
        self.assertEqual(record.record_type, "json")
        self.assertNotIn('"a"', self.raw("mvault_app_record", "data", record.pk))
        page = self.client.get(reverse("record_detail", args=[record.id]))
        self.assertContains(page, "data-json-view")
        self.assertContains(page, "&quot;a&quot;: [\n    1,")
        copied = self.client.post(reverse("record_value_action", args=[record.id]), {"action": "copy", "field": "value"})
        self.assertIn('"a": [\n    1,', copied.json()["value"])

    def test_file_record_upload_download_replace_and_access(self):
        project = Project.objects.create(owner=self.alex, name="Docs", project_type="file_vault")
        url = reverse("record_create", args=[project.id])
        missing = self.client.post(url, {"record_type": "file", "name": "passport"})
        self.assertContains(missing, "Choose a file to upload.")
        upload = SimpleUploadedFile("scan.pdf", b"%PDF-binary", content_type="application/pdf")
        self.client.post(url, {"record_type": "file", "name": "passport", "notes": "n", "file": upload})
        record = Record.objects.get(name="passport")
        attachment = record.attachment
        self.assertEqual((attachment.name, attachment.size), ("scan.pdf", 11))
        self.assertNotIn("scan.pdf", self.raw("mvault_app_attachment", "meta", attachment.pk))
        self.assertIn(("mvault-attachments", attachment.object_key), self.fake.objects)
        download = self.client.get(reverse("record_download", args=[record.id]))
        self.assertEqual(b"".join(download.streaming_content), b"%PDF-binary")
        self.assertIn("scan.pdf", download["Content-Disposition"])
        self.assertTrue(AuditEvent.objects.filter(action="file_downloaded", record=record).exists())
        self.client.post(reverse("record_edit", args=[record.id]), {"record_type": "file", "name": "passport", "notes": "n", "file": SimpleUploadedFile("v2.pdf", b"second")})
        self.assertEqual(record.attachment.name, "v2.pdf")
        self.assertEqual(Attachment.objects.filter(record=record).count(), 2)
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("record_download", args=[record.id])).status_code, 404)
        RecordShare.objects.create(record=record, recipient=self.sam, created_by=self.alex)
        self.assertEqual(self.client.get(reverse("record_download", args=[record.id])).status_code, 200)

    def test_file_size_limit_and_copy_of_shared_file(self):
        project = Project.objects.create(owner=self.alex, name="Docs", project_type="file_vault")
        big = SimpleUploadedFile("big.bin", b"x" * (50 * 1024 * 1024 + 1))
        response = self.client.post(reverse("record_create", args=[project.id]), {"record_type": "file", "name": "big", "file": big})
        self.assertContains(response, "50 MB or smaller")
        self.assertFalse(Record.objects.filter(name="big").exists())
        self.client.post(reverse("record_create", args=[project.id]), {"record_type": "file", "name": "ok", "file": SimpleUploadedFile("a.txt", b"hello")})
        record = Record.objects.get(name="ok")
        RecordShare.objects.create(record=record, recipient=self.sam, created_by=self.alex)
        sam_files = Project.objects.create(owner=self.sam, name="Mine", project_type="file_vault")
        pw = Project.objects.create(owner=self.sam, name="Pw", project_type="password_vault")
        self.client.force_login(self.sam)
        form = self.client.get(reverse("record_copy", args=[record.id]))
        secret = Project.objects.create(owner=self.sam, name="Env", project_type="secret_vault")
        form = self.client.get(reverse("record_copy", args=[record.id]))
        self.assertContains(form, f'<option value="{sam_files.id}"')
        self.assertContains(form, f'<option value="{pw.id}"')
        self.assertNotContains(form, f'<option value="{secret.id}"')
        self.client.post(reverse("record_copy", args=[record.id]), {"project": sam_files.id})
        copied = Record.objects.get(owner=self.sam, name="ok")
        self.assertNotEqual(copied.attachment.object_key, record.attachment.object_key)
        self.assertEqual(self.fake.objects[("mvault-attachments", copied.attachment.object_key)], b"hello")

    def test_custom_icons_upload_validate_and_render(self):
        project = Project.objects.create(owner=self.alex, name="Passwords", project_type="password_vault")
        icon = SimpleUploadedFile("logo.png", png_bytes(), content_type="image/png")
        self.client.post(reverse("project_edit", args=[project.id]), {"name": "Passwords", "icon": "shield", "icon_file": icon})
        project.refresh_from_db()
        self.assertTrue(project.custom_icon_key.startswith("projects/"))
        stored = self.fake.objects[("mvault-icons", project.custom_icon_key)]
        self.assertEqual(Image.open(io.BytesIO(stored)).size[0], 128)
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, f"/media/icons/{project.custom_icon_key}")
        folder_response = self.client.post(reverse("folder_create", args=[project.id]), {"name": "Work", "icon": "folder", "icon_file": SimpleUploadedFile("x.png", b"not an image")})
        self.assertContains(folder_response, "not a valid image")
        self.assertFalse(Folder.objects.filter(name="Work").exists())
        self.client.post(reverse("folder_create", args=[project.id]), {"name": "Work", "icon": "folder", "icon_file": SimpleUploadedFile("f.png", png_bytes((40, 40)))})
        self.assertTrue(Folder.objects.get(name="Work").custom_icon_key.startswith("folders/"))
        self.client.post(reverse("project_edit", args=[project.id]), {"name": "Passwords", "icon": "shield", "remove_custom_icon": "on"})
        project.refresh_from_db()
        self.assertEqual(project.custom_icon_key, "")

    def test_sidebar_marks_current_project_and_folder(self):
        project = Project.objects.create(owner=self.alex, name="Passwords", project_type="password_vault")
        other = Project.objects.create(owner=self.alex, name="Other", project_type="password_vault")
        folder = Folder.objects.create(project=project, name="Work")
        record = Record.objects.create(owner=self.alex, project=project, folder=folder, record_type="password", name="Mail", data={})
        direct = Record.objects.create(owner=self.alex, project=project, record_type="password", name="Direct", data={})

        def active(url):
            html = self.client.get(url).content.decode()
            scroll = html.split('class="sidebar-project-scroll"', 1)[1].split("</div>", 1)[0]
            return [part.split(">")[1].split("<")[-1] if False else part for part in scroll.split("<a ")[1:] if 'active' in part.split(">", 1)[0]]

        self.assertEqual(len(active(reverse("project_detail", args=[project.id]))), 1)
        self.assertEqual(len(active(reverse("folder_detail", args=[folder.id]))), 2)
        self.assertEqual(len(active(reverse("record_detail", args=[record.id]))), 2)
        self.assertEqual(len(active(reverse("record_edit", args=[direct.id]))), 1)
        self.assertEqual(len(active(reverse("dashboard"))), 0)
        self.assertIn(f'href="/projects/{other.id}/"', self.client.get(reverse("project_detail", args=[project.id])).content.decode())


import csv
import zipfile


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ExportAllTests(TestCase):
    def setUp(self):
        self.fake = FakeStorage()
        patcher = mock.patch("mvault_app.storage.get_storage", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.alex = User.objects.create_user("alex@example.test", "Secure-Password-2026!", "Alex Member")
        self.sam = User.objects.create_user("sam@example.test", "Secure-Password-2026!", "Sam Member")
        self.client.force_login(self.alex)

    def test_export_zip_tree_decrypted_csv_and_files(self):
        pw = Project.objects.create(owner=self.alex, name="Passwords", project_type="password_vault")
        work = Folder.objects.create(project=pw, name="Work/Team")
        Record.objects.create(owner=self.alex, project=pw, folder=work, record_type="password", name="Mail", data={"username": "alex", "password": "s3cret,\"x\""})
        Record.objects.create(owner=self.alex, project=pw, record_type="password", name="Gone", data={"password": "x"}, is_deleted=True)
        files = Project.objects.create(owner=self.alex, name="Docs", project_type="file_vault")
        self.client.post(reverse("record_create", args=[files.id]), {"record_type": "file", "name": "Passport scan", "notes": "front", "file": SimpleUploadedFile("orig.pdf", b"%PDF-data")})
        Project.objects.create(owner=self.alex, name="Empty", project_type="json_vault")
        other = Project.objects.create(owner=self.sam, name="Sam private", project_type="password_vault")
        Record.objects.create(owner=self.sam, project=other, record_type="password", name="Hidden", data={"password": "nope"})

        self.assertEqual(self.client.get(reverse("export_all")).status_code, 405)
        response = self.client.post(reverse("export_all"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        archive = zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content)))
        names = set(archive.namelist())
        self.assertEqual(names, {"Passwords/Work_Team/records.csv", "Passwords/records.csv", "Docs/records.csv", "Docs/Passport scan.pdf", "Empty/records.csv"})
        rows = list(csv.DictReader(io.StringIO(archive.read("Passwords/Work_Team/records.csv").decode("utf-8-sig"))))
        self.assertEqual(rows[0]["password"], 's3cret,"x"')
        self.assertEqual(rows[0]["name"], "Mail")
        self.assertEqual(archive.read("Docs/Passport scan.pdf"), b"%PDF-data")
        doc_rows = list(csv.DictReader(io.StringIO(archive.read("Docs/records.csv").decode("utf-8-sig"))))
        self.assertEqual((doc_rows[0]["file"], doc_rows[0]["notes"]), ("Passport scan.pdf", "front"))
        self.assertNotIn(b"Hidden", b"".join(archive.read(n) for n in names))
        self.assertTrue(AuditEvent.objects.filter(action="data_exported", actor=self.alex).exists())

    def test_export_button_on_settings_and_version(self):
        page = self.client.get(reverse("settings"))
        self.assertContains(page, reverse("export_all"))
        self.assertContains(page, "version 0.5.0")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class JsonAndFileInEveryProjectTests(TestCase):
    def setUp(self):
        patcher = mock.patch("mvault_app.storage.get_storage", return_value=FakeStorage())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.alex = User.objects.create_user("alex@example.test", "Secure-Password-2026!", "Alex Member")
        self.client.force_login(self.alex)

    def test_json_and_file_records_can_be_created_in_every_project_type(self):
        for project_type in ("password_vault", "bank_cards_vault", "secret_vault"):
            project = Project.objects.create(owner=self.alex, name=project_type, project_type=project_type)
            folder = Folder.objects.create(project=project, name="Env") if project_type == "secret_vault" else None
            url = reverse("record_create_in_folder", args=[project.id, folder.id]) if folder else reverse("record_create", args=[project.id])
            page = self.client.get(url)
            self.assertContains(page, '<option value="json"')
            self.assertContains(page, '<option value="file"')
            self.assertContains(page, "data-json-editor")
            self.assertContains(page, 'enctype="multipart/form-data"')
            self.client.post(url, {"record_type": "json", "name": "settings", "json_value": '{"a": 1}'})
            self.client.post(url, {"record_type": "file", "name": "attachment", "file": SimpleUploadedFile("a.txt", b"hi")})
            self.assertEqual(Record.objects.get(project=project, name="settings").record_type, "json")
            stored = Record.objects.get(project=project, name="attachment")
            self.assertEqual((stored.record_type, stored.attachment.name), ("file", "a.txt"))
            self.assertEqual(self.client.get(reverse("record_edit", args=[stored.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("record_detail", args=[Record.objects.get(name="settings", project__project_type="password_vault").id])).status_code, 200)

    def test_new_projects_do_not_offer_json_or_file_project_types(self):
        page = self.client.get(reverse("project_create"))
        self.assertNotContains(page, 'value="json_vault"')
        self.assertNotContains(page, 'value="file_vault"')


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DeletingFileRecordsRemovesStoredFilesTests(TestCase):
    def setUp(self):
        self.fake = FakeStorage()
        patcher = mock.patch("mvault_app.storage.get_storage", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.alex = User.objects.create_user("alex@example.test", "Secure-Password-2026!", "Alex Member")
        self.client.force_login(self.alex)
        self.project = Project.objects.create(owner=self.alex, name="Docs", project_type="password_vault")
        self.folder = Folder.objects.create(project=self.project, name="Scans")

    def make_file(self, name, folder=None, versions=1):
        url = reverse("record_create_in_folder", args=[self.project.id, folder.id]) if folder else reverse("record_create", args=[self.project.id])
        self.client.post(url, {"record_type": "file", "name": name, "file": SimpleUploadedFile(f"{name}.txt", b"v1")})
        record = Record.objects.get(project=self.project, name=name)
        for n in range(2, versions + 1):
            self.client.post(reverse("record_edit", args=[record.id]), {"record_type": "file", "name": name, "file": SimpleUploadedFile(f"{name}.txt", b"v%d" % n)})
        return record

    def stored(self):
        return {key for (_bucket, key) in self.fake.objects}

    def test_single_delete_removes_every_version_from_storage(self):
        record = self.make_file("passport", versions=2)
        self.assertEqual(len(self.stored()), 2)
        self.client.post(reverse("record_delete", args=[record.id]))
        self.assertEqual(self.stored(), set())
        self.assertFalse(Attachment.objects.filter(record=record).exists())
        self.assertTrue(Record.objects.get(pk=record.pk).is_deleted)

    def test_bulk_folder_and_project_deletes_remove_files(self):
        keep = self.make_file("keep")
        a = self.make_file("a", self.folder)
        b = self.make_file("b", self.folder)
        self.client.post(reverse("folder_record_actions", args=[self.folder.id]), {"bulk_action": "delete", "record_ids": [a.id]})
        self.assertEqual(len(self.stored()), 2)
        self.client.post(reverse("folder_delete", args=[self.folder.id]))
        self.assertEqual(len(self.stored()), 1)
        self.assertTrue(Attachment.objects.filter(record=keep).exists())
        self.client.post(reverse("project_delete", args=[self.project.id]))
        self.assertEqual(self.stored(), set())
        self.assertFalse(Attachment.objects.filter(record=b).exists())

    def test_failed_storage_delete_keeps_row_for_retry_and_still_deletes_record(self):
        record = self.make_file("stuck")
        with mock.patch.object(self.fake, "delete", side_effect=RuntimeError("down")):
            response = self.client.post(reverse("record_delete", args=[record.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Record.objects.get(pk=record.pk).is_deleted)
        self.assertEqual(Attachment.objects.filter(record=record).count(), 1)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AvatarTests(TestCase):
    def setUp(self):
        self.fake = FakeStorage()
        patcher = mock.patch("mvault_app.storage.get_storage", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.alex = User.objects.create_user("Alex@Example.test", "Secure-Password-2026!", "Alex Member")
        self.client.force_login(self.alex)

    def sidebar_avatar(self):
        html = self.client.get(reverse("dashboard")).content.decode()
        return html.split('<div class="avatar">', 1)[1].split("</div>", 1)[0]

    def test_gravatar_is_tried_first_with_initials_underneath(self):
        import hashlib
        digest = hashlib.sha256(b"alex@example.test").hexdigest()
        markup = self.sidebar_avatar()
        self.assertIn("avatar-initials\">AM<", markup)
        self.assertIn(f"https://gravatar.com/avatar/{digest}?s=96&amp;d=404", markup)
        self.assertIn('onerror="this.remove()"', markup)

    def test_uploaded_avatar_wins_over_gravatar_and_can_be_removed_or_replaced(self):
        upload = SimpleUploadedFile("me.png", png_bytes((500, 300)), content_type="image/png")
        self.client.post(reverse("avatar_update"), {"avatar": upload})
        self.alex.refresh_from_db()
        key = self.alex.avatar_key
        self.assertTrue(key.startswith("users/"))
        stored = self.fake.objects[("mvault-avatars", key)]
        self.assertEqual(Image.open(io.BytesIO(stored)).size, (256, 256))
        markup = self.sidebar_avatar()
        self.assertIn(f"/media/avatars/{key}", markup)
        self.assertNotIn("gravatar.com", markup)
        self.client.post(reverse("avatar_update"), {"avatar": SimpleUploadedFile("b.png", png_bytes(), content_type="image/png")})
        self.alex.refresh_from_db()
        self.assertNotEqual(self.alex.avatar_key, key)
        self.assertNotIn(("mvault-avatars", key), self.fake.objects)
        self.client.post(reverse("avatar_update"), {"remove": "1"})
        self.alex.refresh_from_db()
        self.assertEqual(self.alex.avatar_key, "")
        self.assertEqual([k for (b, k) in self.fake.objects if b == "mvault-avatars"], [])
        self.assertIn("gravatar.com", self.sidebar_avatar())

    def test_invalid_avatar_is_rejected_and_settings_page_shows_form(self):
        response = self.client.post(reverse("avatar_update"), {"avatar": SimpleUploadedFile("x.png", b"not an image")}, follow=True)
        self.assertContains(response, "not a valid image")
        self.alex.refresh_from_db()
        self.assertEqual(self.alex.avatar_key, "")
        self.assertContains(self.client.get(reverse("settings")), reverse("avatar_update"))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MediaProxyTests(TestCase):
    def setUp(self):
        self.fake = FakeStorage()
        patcher = mock.patch("mvault_app.storage.get_storage", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.alex = User.objects.create_user("alex@example.test", "Secure-Password-2026!", "Alex Member")

    def test_icons_and_avatars_are_served_through_the_app_to_signed_in_users_only(self):
        key = "projects/" + "a" * 32 + ".png"
        self.fake.objects[("mvault-icons", key)] = b"PNGDATA"
        self.assertEqual(self.client.get(f"/media/icons/{key}").status_code, 302)
        self.client.force_login(self.alex)
        response = self.client.get(f"/media/icons/{key}")
        self.assertEqual((response.status_code, b"".join(response.streaming_content), response["Content-Type"]), (200, b"PNGDATA", "image/png"))
        self.assertEqual(self.client.get("/media/icons/projects/missing.png").status_code, 404)
        self.assertEqual(self.client.get("/media/attachments/" + key).status_code, 404)
        self.assertEqual(self.client.get("/media/icons/../x.png").status_code, 404)

    @override_settings(ICONS_PUBLIC_BASE_URL="https://cdn.example.test/icons")
    def test_configured_public_base_url_is_used_instead(self):
        from .storage import icon_public_url
        self.assertEqual(icon_public_url("projects/x.png"), "https://cdn.example.test/icons/projects/x.png")


from django.core.management import CommandError
from .crypto import derive_key


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], LOGIN_MAX_ATTEMPTS=3)
class HardeningTests(TestCase):
    def setUp(self):
        self.alex = User.objects.create_user("alex@example.test", "Secure-Password-2026!", "Alex Member")

    def attempt(self, password, ip="203.0.113.9"):
        return self.client.post(reverse("login"), {"username": "alex@example.test", "password": password}, HTTP_X_FORWARDED_FOR=f"1.2.3.4, {ip}")

    def test_repeated_failures_lock_sign_in_until_window_passes_and_success_resets(self):
        for _ in range(3):
            self.assertEqual(self.attempt("wrong").status_code, 200)
        locked = self.attempt("Secure-Password-2026!")
        self.assertEqual(locked.status_code, 429)
        self.assertContains(locked, "Too many failed sign-in attempts", status_code=429)
        LoginAttempt.objects.update(created_at=timezone.now() - timezone.timedelta(hours=1))
        self.assertEqual(self.attempt("Secure-Password-2026!").status_code, 302)
        self.assertFalse(LoginAttempt.objects.filter(email="alex@example.test").exists())

    def test_throttle_uses_the_proxy_appended_address_not_the_spoofed_one(self):
        from .throttle import client_ip
        request = mock.Mock(META={"HTTP_X_FORWARDED_FOR": "6.6.6.6, 198.51.100.7", "REMOTE_ADDR": "10.0.0.2"})
        self.assertEqual(client_ip(request), "198.51.100.7")
        with override_settings(TRUST_PROXY_HEADERS=False):
            self.assertEqual(client_ip(request), "10.0.0.2")

    def test_security_headers_are_sent(self):
        response = self.client.get(reverse("login"))
        csp = response["Content-Security-Policy"]
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("img-src 'self' data: https://gravatar.com", csp)
        self.assertEqual(response["X-Frame-Options"], "DENY")

    @override_settings(S3_CONFIGURED=False)
    def test_file_records_and_uploads_are_unavailable_without_object_storage(self):
        project = Project.objects.create(owner=self.alex, name="P", project_type="password_vault")
        self.client.force_login(self.alex)
        page = self.client.get(reverse("record_create", args=[project.id]))
        self.assertContains(page, '<option value="json"')
        self.assertNotContains(page, '<option value="file"')
        response = self.client.post(reverse("avatar_update"), {"avatar": SimpleUploadedFile("a.png", png_bytes(), content_type="image/png")}, follow=True)
        self.assertContains(response, "File storage is not configured")


class RotateEncryptionKeyTests(TestCase):
    def test_values_are_reencrypted_to_the_new_key_and_wrong_old_key_changes_nothing(self):
        owner = User.objects.create_user("alex@example.test", "Secure-Password-2026!", "Alex")
        project = Project.objects.create(owner=owner, name="P", project_type="password_vault")
        record = Record.objects.create(owner=owner, project=project, record_type="password", name="Mail", data={"password": "p1"})
        with connection.cursor() as cursor:
            cursor.execute("SELECT data FROM mvault_app_record WHERE id = %s", [record.pk])
            before = cursor.fetchone()[0]
        env = {"OLD_MVAULT_ENCRYPTION_KEY": "wrong", "OLD_MVAULT_ENCRYPTION_SALT": "wrong"}
        with mock.patch.dict("os.environ", env), self.assertRaises(Exception):
            call_command("rotate_encryption_key", verbosity=0)
        with connection.cursor() as cursor:
            cursor.execute("SELECT data FROM mvault_app_record WHERE id = %s", [record.pk])
            self.assertEqual(cursor.fetchone()[0], before)
        # Simulate: data was encrypted under an old key/salt, the app now runs with new ones.
        old = {"OLD_MVAULT_ENCRYPTION_KEY": "old-master", "OLD_MVAULT_ENCRYPTION_SALT": "old-salt"}
        old_key = derive_key("old-master", "old-salt")
        with connection.cursor() as cursor:
            cursor.execute("UPDATE mvault_app_record SET data = %s WHERE id = %s", [encrypt_text('{"password":"p1"}', old_key), record.pk])
        with mock.patch.dict("os.environ", old):
            call_command("rotate_encryption_key", "--dry-run", verbosity=0)
            self.assertRaises(Exception, lambda: Record.objects.get(pk=record.pk).data)
            call_command("rotate_encryption_key", verbosity=0)
        self.assertEqual(Record.objects.get(pk=record.pk).data, {"password": "p1"})
        with mock.patch.dict("os.environ", {"OLD_MVAULT_ENCRYPTION_KEY": "", "OLD_MVAULT_ENCRYPTION_SALT": ""}), self.assertRaises(CommandError):
            call_command("rotate_encryption_key", verbosity=0)
