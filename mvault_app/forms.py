import json
import re
import secrets
import string
from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from .models import Project, User, VAULT_ICON_CHOICES

class LoginForm(forms.Form):
    username = forms.EmailField(label="Email")
    password = forms.CharField(widget=forms.PasswordInput)

class MemberCreateForm(forms.Form):
    full_name = forms.CharField(max_length=160)
    email = forms.EmailField()
    password = forms.CharField(min_length=12, widget=forms.PasswordInput)
    use_strong_password = forms.BooleanField(required=False)
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if password:
            validate_password(password)
        return password
    @staticmethod
    def generate_password(length=24):
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        return "".join(secrets.choice(alphabet) for _ in range(length))

class SetTemporaryPasswordForm(forms.Form):
    password = forms.CharField(min_length=12, widget=forms.PasswordInput)
    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

class CustomIconMixin(forms.Form):
    """Optional uploaded icon that replaces the built-in icon; validated and stored by storage.save_icon."""
    icon_file = forms.FileField(required=False, label="Custom icon", widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp,image/gif"}))
    remove_custom_icon = forms.BooleanField(required=False, label="Remove custom icon")

    def clean_icon_file(self):
        upload = self.cleaned_data.get("icon_file")
        if upload and upload.size > settings.MAX_ICON_BYTES:
            raise forms.ValidationError("Icons must be 2 MB or smaller.")
        return upload


class ProjectForm(CustomIconMixin, forms.ModelForm):
    def __init__(self, *args, language="en", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["icon"].initial = self.instance.icon if self.instance and self.instance.pk else "shield"
        if self.instance and self.instance.pk:
            self.fields.pop("project_type", None)
        else:  # JSON and File records are available in every project, so they have no dedicated project type
            self.fields["project_type"].choices = [c for c in self.fields["project_type"].choices if c[0] in ("password_vault", "bank_cards_vault", "secret_vault")]
        if language == "ru":
            if "project_type" in self.fields:
                self.fields["project_type"].choices = [("password_vault", "Пароли"), ("bank_cards_vault", "Банковские карты"), ("secret_vault", "Секреты")]
    class Meta:
        model = Project
        fields = ["name", "project_type", "icon"]

class FolderForm(CustomIconMixin):
    PRESETS = ["Dev", "Development", "Local", "Test", "Testing", "QA", "UAT", "Integration", "Sandbox", "Preview", "Review", "Stage", "Staging", "Pre-Prod", "Pre-Production", "Prod", "Production", "Canary", "Performance", "Demo", "Training", "Disaster Recovery"]
    name = forms.CharField(max_length=120)
    icon = forms.ChoiceField(choices=VAULT_ICON_CHOICES, initial="folder")

class RecordForm(forms.Form):
    record_type = forms.ChoiceField(choices=[("password", "Password"), ("bank_card", "Bank card"), ("variable", "Environment / secret variable")])
    name = forms.CharField(max_length=160, label="Title / key")
    username = forms.CharField(max_length=240, required=False)
    password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=True))
    website = forms.URLField(required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea)
    cardholder = forms.CharField(max_length=160, required=False)
    number = forms.CharField(max_length=40, required=False)
    expiration = forms.CharField(max_length=12, required=False)
    cvv = forms.CharField(max_length=8, required=False, widget=forms.PasswordInput(render_value=True))
    issuer = forms.CharField(max_length=160, required=False)
    pin = forms.CharField(max_length=16, required=False, widget=forms.PasswordInput(render_value=True))
    value = forms.CharField(required=False, widget=forms.Textarea)
    value_type = forms.ChoiceField(choices=[("secret", "Secret"), ("plain", "Plain")], initial="secret", required=False)
    json_value = forms.CharField(required=False, label="JSON", widget=forms.Textarea(attrs={"spellcheck": "false", "data-json-editor": "1", "rows": 16}))
    file = forms.FileField(required=False, label="File (max 50 MB)", widget=forms.FileInput)
    PROJECT_RECORD_TYPES = {
        "password_vault": ("password", "Password"),
        "bank_cards_vault": ("bank_card", "Bank card"),
        "secret_vault": ("variable", "Environment variable"),
        "json_vault": ("json", "JSON"),
        "file_vault": ("file", "File"),
    }
    TYPE_FIELDS = {
        "password": {"record_type", "name", "username", "password", "website", "notes"},
        "bank_card": {"record_type", "name", "cardholder", "number", "expiration", "cvv", "issuer", "pin", "notes"},
        "variable": {"record_type", "name", "value", "value_type"},
        "json": {"record_type", "name", "json_value", "notes"},
        "file": {"record_type", "name", "file", "notes"},
    }

    TYPE_LABELS = {"password": "Password", "bank_card": "Bank card", "variable": "Environment variable", "json": "JSON", "file": "File"}
    TYPE_LABELS_RU = {"password": "Пароль", "bank_card": "Банковская карта", "variable": "Переменная окружения / секрет", "json": "JSON", "file": "Файл"}

    @classmethod
    def allowed_types(cls, project_type):
        """Record types a project accepts: its own type plus JSON and File (available in every project)."""
        primary = cls.PROJECT_RECORD_TYPES.get(project_type, (None, None))[0]
        if not primary:
            raise ValueError("RecordForm requires a supported project_type.")
        return list(dict.fromkeys([primary, "json", "file"]))

    def __init__(self, *args, project_type=None, record_type=None, language="en", has_file=False, **kwargs):
        """``record_type`` fixes the type (editing); without it the user picks one of the allowed types."""
        super().__init__(*args, **kwargs)
        self.has_file = has_file
        allowed = self.allowed_types(project_type)
        if record_type is not None and record_type not in allowed:
            raise ValueError("Record type is not allowed in this project.")
        self.type_fixed = record_type is not None
        labels = self.TYPE_LABELS_RU if language == "ru" else self.TYPE_LABELS
        shown = [record_type] if self.type_fixed else allowed
        self.fields["record_type"].choices = [(kind, labels[kind]) for kind in shown]
        self.initial.setdefault("record_type", shown[0])
        if self.type_fixed:
            self.fields["record_type"].widget = forms.HiddenInput()
        keep = set().union(*(self.TYPE_FIELDS[kind] for kind in shown))
        for field_name in tuple(self.fields):
            if field_name not in keep:
                self.fields.pop(field_name)
        for field_name, field in self.fields.items():
            field.record_types = [kind for kind in shown if field_name in self.TYPE_FIELDS[kind] and field_name not in ("record_type", "name")]
            field.widget.attrs.setdefault("class", "field")
        if language == "ru" and "value_type" in self.fields:
            self.fields["value_type"].choices = [("secret", "Секрет"), ("plain", "Обычный текст")]
    @classmethod
    def from_record(cls, record):
        return cls(project_type=record.project.project_type,
                   initial={"record_type": record.record_type, "name": record.name, **record.data})
    def clean(self):
        cleaned = super().clean()
        if self.type_fixed and cleaned.get("record_type") != self.initial.get("record_type"):
            self.add_error("record_type", "Record type cannot be changed.")
        if cleaned.get("record_type") == "variable" and cleaned.get("name") and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cleaned["name"].strip()):
            self.add_error("name", "Variable keys must use letters, numbers, and underscores, and cannot start with a number.")
        if cleaned.get("record_type") == "json":
            text = (cleaned.get("json_value") or "").strip()
            if not text:
                self.add_error("json_value", "Enter a JSON document.")
            else:
                try:
                    json.loads(text)
                except ValueError as exc:
                    self.add_error("json_value", f"Invalid JSON: {exc}")
        if cleaned.get("record_type") == "file":
            upload = cleaned.get("file")
            if upload and upload.size > settings.MAX_ATTACHMENT_BYTES:
                self.add_error("file", "Files must be 50 MB or smaller.")
            elif not upload and not self.has_file:
                self.add_error("file", "Choose a file to upload.")
        return cleaned
    def payload(self):
        kind = self.cleaned_data["record_type"]
        keys = {"password": ["username", "password", "website", "notes"], "bank_card": ["cardholder", "number", "expiration", "cvv", "issuer", "pin", "notes"], "variable": ["value", "value_type"], "json": ["value", "notes"], "file": ["notes"]}[kind]
        payload = {key: self.cleaned_data.get(key, "") for key in keys}
        if kind == "json":
            payload["value"] = self.cleaned_data["json_value"].strip()
        if kind == "variable" and not payload["value_type"]:
            payload["value_type"] = "secret"
        return payload
