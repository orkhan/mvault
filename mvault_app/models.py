from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from .fields import EncryptedJSONField

VAULT_ICON_CHOICES = [
    ("key", "Key"), ("card", "Credit card"), ("code", "Code"), ("lock", "Lock"),
    ("grid", "Grid"), ("users", "Users"), ("clock", "Clock"), ("cog", "Settings"),
    ("folder", "Folder"), ("shield", "Shield"), ("server", "Server"), ("database", "Database"),
    ("globe", "Globe"), ("briefcase", "Briefcase"), ("star", "Star"), ("home", "Home"),
    ("cloud", "Cloud"), ("bolt", "Bolt"),
]


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, full_name=""):
        if not email:
            raise ValueError("An email address is required")
        user = self.model(email=self.normalize_email(email).lower(), full_name=full_name)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, full_name="Administrator"):
        user = self.create_user(email, password, full_name)
        user.is_admin = True
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=160)
    preferred_language = models.CharField(max_length=2, choices=[("en", "English"), ("ru", "Russian")], default="en")
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    avatar_key = models.CharField(max_length=200, blank=True, default="")
    date_joined = models.DateTimeField(default=timezone.now)
    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    def __str__(self):
        return self.full_name or self.email

    @property
    def first_name(self):
        return self.full_name.split()[0] if self.full_name.split() else self.email.split("@")[0]

    @property
    def initials(self):
        parts = self.full_name.split()
        return "".join(p[0] for p in parts[:2]).upper() or self.email[:1].upper()


class Project(models.Model):
    TYPES = [("password_vault", "Passwords"), ("bank_cards_vault", "Bank Cards"), ("secret_vault", "Secrets"), ("json_vault", "JSON"), ("file_vault", "Files")]
    ICON_CHOICES = VAULT_ICON_CHOICES
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=120)
    project_type = models.CharField(max_length=24, choices=TYPES)
    icon = models.CharField(max_length=24, choices=ICON_CHOICES, default="shield")
    custom_icon_key = models.CharField(max_length=200, blank=True, default="")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("name"), "owner", condition=Q(is_deleted=False), name="unique_active_project_name_per_owner")]
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Folder(models.Model):
    ICON_CHOICES = VAULT_ICON_CHOICES
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="folders")
    name = models.CharField(max_length=120)
    icon = models.CharField(max_length=24, choices=ICON_CHOICES, default="folder")
    custom_icon_key = models.CharField(max_length=200, blank=True, default="")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(Lower("name"), "project", condition=Q(is_deleted=False), name="unique_active_folder_name_per_project")]
        ordering = ["name", "id"]


class Record(models.Model):
    TYPES = [("password", "Password"), ("bank_card", "Bank card"), ("variable", "Environment variable"), ("json", "JSON"), ("file", "File")]
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="records")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="records")
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.SET_NULL, related_name="records")
    record_type = models.CharField(max_length=16, choices=TYPES)
    name = models.CharField(max_length=160)
    data = EncryptedJSONField()
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["owner", "project", "is_deleted"])]
        constraints = [
            models.UniqueConstraint(Lower("name"), "project", condition=Q(is_deleted=False, folder__isnull=True), name="unique_active_direct_record_name"),
            models.UniqueConstraint(Lower("name"), "folder", condition=Q(is_deleted=False, folder__isnull=False), name="unique_active_folder_record_name"),
        ]

    @property
    def attachment(self):
        return self.attachments.filter(replaced_at__isnull=True).order_by("-created_at", "-id").first()

    def snapshot(self):
        snapshot = {"record_type": self.record_type, "name": self.name, "data": self.data, "project_id": self.project_id, "folder_id": self.folder_id}
        if self.record_type == "file":
            current = self.attachment
            snapshot["attachment_id"] = current.pk if current else None
        return snapshot


class Attachment(models.Model):
    """A file stored in the private MinIO bucket and linked to a file record.

    Replacing a file keeps the previous row (with ``replaced_at`` set) and its object so
    record history stays meaningful; objects are never deleted automatically.
    """
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="attachments")
    object_key = models.CharField(max_length=200, unique=True)
    size = models.BigIntegerField()
    sha256 = models.CharField(max_length=64, blank=True, default="")
    meta = EncryptedJSONField()  # {"name": ..., "content_type": ...}
    uploaded_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="uploaded_attachments")
    created_at = models.DateTimeField(auto_now_add=True)
    replaced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def name(self):
        return self.meta.get("name", "file")

    @property
    def content_type(self):
        return self.meta.get("content_type") or "application/octet-stream"


class RecordRevision(models.Model):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="revisions")
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    snapshot = EncryptedJSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at", "-id"]


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="audit_events")
    owner = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="owned_audit_events")
    action = models.CharField(max_length=40)
    project = models.ForeignKey(Project, null=True, on_delete=models.SET_NULL)
    folder = models.ForeignKey(Folder, null=True, on_delete=models.SET_NULL)
    record = models.ForeignKey(Record, null=True, on_delete=models.SET_NULL)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at", "-id"]


class LoginAttempt(models.Model):
    """A failed sign-in, kept briefly to throttle repeated guessing."""
    email = models.CharField(max_length=254)
    ip = models.CharField(max_length=45, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [models.Index(fields=["email", "created_at"]), models.Index(fields=["ip", "created_at"])]


class ProjectShare(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="shares")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_shares")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_project_shares")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "recipient"], condition=Q(revoked_at__isnull=True), name="unique_live_project_share")]


class RecordShare(models.Model):
    record = models.ForeignKey(Record, on_delete=models.CASCADE, related_name="shares")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="record_shares")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_record_shares")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["record", "recipient"], condition=Q(revoked_at__isnull=True), name="unique_live_record_share")]


def record_audit(actor, owner, action, record=None, project=None, folder=None, details=None):
    return AuditEvent.objects.create(actor=actor, owner=owner, action=action, record=record,
        project=project or getattr(record, "project", None), folder=folder or getattr(record, "folder", None), details=details or {})
