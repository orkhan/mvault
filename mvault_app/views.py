import csv
import io
import logging
import os
import re
import tempfile
import zipfile
import secrets
import string
from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST
from .decorators import admin_required, member_required
from .forms import LoginForm, MemberCreateForm, ProjectForm, FolderForm, RecordForm, SetTemporaryPasswordForm
from . import storage
from .models import Attachment, AuditEvent, Folder, Project, ProjectShare, Record, RecordRevision, RecordShare, User, record_audit
from .utils import parse_env, env_value_type, export_env, file_sha256, human_size, pretty_json, save_revision


def apply_custom_icon(obj, kind, form):
    """Store/clear an uploaded custom icon on a project or folder before it is saved.

    Returns False (after attaching a form error) when the upload is rejected.
    """
    upload = form.cleaned_data.get("icon_file")
    if upload:
        try:
            obj.custom_icon_key = storage.save_icon(kind, upload)
        except storage.StorageError as exc:
            form.add_error("icon_file", str(exc))
            return False
    elif form.cleaned_data.get("remove_custom_icon"):
        obj.custom_icon_key = ""
    return True


def record_accessible(user, record):
    """Return (allowed, shared) for reading a record: owner, project share, or record share."""
    if record.owner_id == user.id:
        return True, False
    project_grant = ProjectShare.objects.filter(project=record.project, recipient=user, revoked_at__isnull=True, project__owner__is_active=True).exists()
    record_grant = RecordShare.objects.filter(record=record, recipient=user, revoked_at__isnull=True, record__owner__is_active=True).exists()
    return project_grant or record_grant, True


def attach_file(record, upload, actor):
    """Upload ``upload`` and make it the record's current attachment (older ones are kept for history)."""
    digest = file_sha256(upload)
    key = storage.save_attachment(upload)
    Attachment.objects.filter(record=record, replaced_at__isnull=True).update(replaced_at=timezone.now())
    return Attachment.objects.create(
        record=record, object_key=key, size=upload.size, sha256=digest, uploaded_by=actor,
        meta={"name": upload.name[:240], "content_type": upload.content_type or "application/octet-stream"},
    )


logger = logging.getLogger(__name__)


def delete_stored_files(object_keys):
    """Remove attachment objects from storage; rows whose object could not be removed are returned."""
    failed = []
    for key in object_keys:
        try:
            storage.delete_attachment(key)
        except Exception:
            logger.exception("Could not delete attachment object %s", key)
            failed.append(key)
    return failed


def purge_record_files(record_ids):
    """Delete the stored files (every version) of the given file records and drop their Attachment rows.

    Rows stay when the object could not be deleted so the cleanup can be retried.
    """
    attachments = list(Attachment.objects.filter(record_id__in=list(record_ids), record__record_type="file"))
    failed = set(delete_stored_files(a.object_key for a in attachments))
    Attachment.objects.filter(pk__in=[a.pk for a in attachments if a.object_key not in failed]).delete()


def health(request):
    return HttpResponse("ok", content_type="text/plain")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("admin_dashboard" if request.user.is_admin else "dashboard")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(request, username=form.cleaned_data["username"].lower(), password=form.cleaned_data["password"])
        if user is not None:
            if not user.is_active:
                form.add_error(None, "This account is deactivated.")
            else:
                login(request, user)
                AuditEvent.objects.create(actor=user, owner=user, action="login")
                if user.must_change_password:
                    return redirect("password_change_required")
                return redirect("admin_dashboard" if user.is_admin else "dashboard")
        else:
            form.add_error(None, "Email or password is incorrect.")
    return render(request, "mvault/login.html", {"form": form})

@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        AuditEvent.objects.create(actor=request.user, owner=request.user, action="logout")
    logout(request)
    return redirect("login")

@member_required
def dashboard(request):
    projects = Project.objects.filter(owner=request.user, is_deleted=False).annotate(record_count=Count("records", filter=Q(records__is_deleted=False)))
    latest = list(AuditEvent.objects.filter(Q(owner=request.user) | Q(actor=request.user)).select_related("actor", "project", "folder", "record", "record__owner", "folder__project__owner", "project__owner")[:15])
    for event in latest:
        event.activity_url = activity_target_url(event, request.user)
    return render(request, "mvault/dashboard.html", {"projects": projects, "latest_events": latest})


def activity_target_url(event, user):
    if event.record_id:
        record = event.record
        if record.owner_id == user.id:
            return reverse("record_history", args=[record.pk]) if record.is_deleted else reverse("record_detail", args=[record.pk])
        if record.is_deleted or not record.owner.is_active:
            return None
        project_access = ProjectShare.objects.filter(project=record.project, recipient=user, revoked_at__isnull=True, project__owner__is_active=True).exists()
        record_access = RecordShare.objects.filter(record=record, recipient=user, revoked_at__isnull=True, record__owner__is_active=True).exists()
        return reverse("record_detail", args=[record.pk]) if project_access or record_access else None
    if event.folder_id:
        folder = event.folder
        if folder.is_deleted or folder.project.is_deleted:
            return None
        access = folder.project.owner_id == user.id or ProjectShare.objects.filter(project=folder.project, recipient=user, revoked_at__isnull=True, project__owner__is_active=True).exists()
        return reverse("folder_detail", args=[folder.pk]) if access else None
    if event.project_id:
        project = event.project
        if project.is_deleted:
            return None
        access = project.owner_id == user.id or ProjectShare.objects.filter(project=project, recipient=user, revoked_at__isnull=True, project__owner__is_active=True).exists()
        return reverse("project_detail", args=[project.pk]) if access else None
    return None

@admin_required
def admin_dashboard(request):
    members = User.objects.filter(is_admin=False).order_by("full_name", "email")
    events = AuditEvent.objects.filter(Q(action__startswith="member_") | Q(actor=request.user)).select_related("actor", "owner")[:15]
    return render(request, "mvault/admin_dashboard.html", {"members": members, "events": events})

@admin_required
def member_create(request):
    form = MemberCreateForm(request.POST or None)
    generated = ""
    if request.method == "POST":
        if request.POST.get("generate") == "1":
            generated = MemberCreateForm.generate_password()
            form = MemberCreateForm(initial={"full_name": request.POST.get("full_name", ""), "email": request.POST.get("email", ""), "password": generated, "use_strong_password": True})
        elif form.is_valid():
            with transaction.atomic():
                member = User.objects.create_user(form.cleaned_data["email"], form.cleaned_data["password"], form.cleaned_data["full_name"])
                member.must_change_password = True
                member.save(update_fields=["must_change_password"])
                Project.objects.bulk_create([
                    Project(owner=member, name="Passwords", project_type="password_vault", icon="shield"),
                    Project(owner=member, name="Bank Cards", project_type="bank_cards_vault", icon="card"),
                ])
                AuditEvent.objects.create(actor=request.user, owner=member, action="member_created", details={"email": member.email})
            messages.success(request, f"Created account for {member.full_name}. They must change the assigned password at first login.")
            return redirect("admin_dashboard")
    return render(request, "mvault/member_form.html", {"form": form, "generated": generated})

@admin_required
@require_POST
def member_toggle(request, user_id):
    member = get_object_or_404(User, pk=user_id, is_admin=False)
    member.is_active = not member.is_active
    member.save(update_fields=["is_active"])
    if not member.is_active:
        ProjectShare.objects.filter(Q(project__owner=member) | Q(recipient=member), revoked_at__isnull=True).update(revoked_at=timezone.now())
        RecordShare.objects.filter(Q(record__owner=member) | Q(recipient=member), revoked_at__isnull=True).update(revoked_at=timezone.now())
    AuditEvent.objects.create(actor=request.user, owner=member, action="member_activated" if member.is_active else "member_deactivated")
    messages.success(request, f"{member.full_name} is {'active' if member.is_active else 'deactivated'}.")
    return redirect("admin_dashboard")

@admin_required
def member_password(request, user_id):
    member = get_object_or_404(User, pk=user_id, is_admin=False)
    form = SetTemporaryPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        member.set_password(form.cleaned_data["password"])
        member.must_change_password = True
        member.save(update_fields=["password", "must_change_password"])
        AuditEvent.objects.create(actor=request.user, owner=member, action="member_password_reset")
        messages.success(request, "Temporary password set. The member must change it at next sign-in.")
        return redirect("admin_dashboard")
    return render(request, "mvault/member_password.html", {"member": member, "form": form})

@admin_required
def member_delete(request, user_id):
    member = get_object_or_404(User, pk=user_id, is_admin=False)
    targets = User.objects.filter(is_admin=False, is_active=True).exclude(pk=member.pk)
    if request.method == "POST":
        mode = request.POST.get("mode")
        with transaction.atomic():
            if mode == "transfer":
                target = get_object_or_404(targets, pk=request.POST.get("target"))
                AuditEvent.objects.filter(owner=member).exclude(project__isnull=True, folder__isnull=True, record__isnull=True).update(owner=target)
                for project in Project.objects.filter(owner=member):
                    original_name = project.name
                    if Project.objects.filter(owner=target, name__iexact=original_name, is_deleted=False).exists():
                        project.name = f"{original_name} (from {member.full_name})"[:120]
                    project.owner = target
                    project.save(update_fields=["owner", "name"])
                Record.objects.filter(owner=member).update(owner=target)
            elif mode == "purge":
                purged_keys = list(Attachment.objects.filter(record__owner=member).values_list("object_key", flat=True))
                AuditEvent.objects.filter(owner=member).delete()
            else:
                messages.error(request, "Choose transfer or purge before permanently deleting the account.")
                return redirect("member_delete", user_id=member.pk)
            ProjectShare.objects.filter(Q(project__owner=member) | Q(recipient=member), revoked_at__isnull=True).update(revoked_at=timezone.now())
            RecordShare.objects.filter(Q(record__owner=member) | Q(recipient=member), revoked_at__isnull=True).update(revoked_at=timezone.now())
            AuditEvent.objects.create(actor=request.user, owner=None, action="member_deleted", details={"email": member.email, "mode": mode})
            member.delete()
        if mode == "purge":
            delete_stored_files(purged_keys)
        messages.success(request, "Account permanently deleted.")
        return redirect("admin_dashboard")
    return render(request, "mvault/member_delete.html", {"member": member, "targets": targets})

@member_required
def settings_view(request):
    user = request.user
    if request.method == "POST":
        user.full_name = request.POST.get("full_name", "").strip()[:160]
        user.preferred_language = request.POST.get("preferred_language", "en") if request.POST.get("preferred_language") in {"en", "ru"} else "en"
        email = request.POST.get("email", "").strip().lower()
        if not user.full_name or not email:
            messages.error(request, "Name and email are required.")
        elif User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            messages.error(request, "That email address is already used.")
        else:
            user.email = email
            user.save(update_fields=["full_name", "email", "preferred_language"])
            messages.success(request, "Settings saved.")
            return redirect("settings")
    return render(request, "mvault/settings.html")

@member_required
@require_POST
def avatar_update(request):
    user = request.user
    upload = request.FILES.get("avatar")
    if request.POST.get("remove") and not upload:
        old, user.avatar_key = user.avatar_key, ""
        user.save(update_fields=["avatar_key"])
        if old:
            storage.delete_avatar(old)
        messages.success(request, "Avatar removed.")
    elif upload:
        try:
            key = storage.save_avatar(upload)
        except storage.StorageError as exc:
            messages.error(request, str(exc))
        else:
            old, user.avatar_key = user.avatar_key, key
            user.save(update_fields=["avatar_key"])
            if old:
                storage.delete_avatar(old)
            messages.success(request, "Avatar updated.")
    else:
        messages.error(request, "Choose an image to upload.")
    return redirect("settings")


MEDIA_BUCKETS = {"icons": "S3_ICONS_BUCKET", "avatars": "S3_AVATARS_BUCKET"}


@login_required
def public_media(request, kind, key):
    """Serve icons and avatars from object storage so no separate public storage host is required."""
    if kind not in MEDIA_BUCKETS or not re.fullmatch(r"(projects|folders|users)/[0-9a-f]{32}\.png", key):
        raise Http404
    try:
        body, length = storage.get_storage().open(getattr(settings, MEDIA_BUCKETS[kind]), key)
    except Exception:
        raise Http404
    response = StreamingHttpResponse(body.iter_chunks(64 * 1024), content_type="image/png")
    response["Content-Length"] = str(length)
    response["Cache-Control"] = "private, max-age=86400, immutable"
    return response


@member_required
def change_password(request, required=False):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, user)
        AuditEvent.objects.create(actor=user, owner=user, action="password_changed")
        messages.success(request, "Password changed.")
        return redirect("dashboard")
    return render(request, "mvault/password_change.html", {"form": form, "required": required})

def password_change_required(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.must_change_password:
        return redirect("admin_dashboard" if request.user.is_admin else "dashboard")
    if request.user.is_admin:
        form = PasswordChangeForm(request.user, request.POST or None)
        if request.method == "POST" and form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["password", "must_change_password"])
            update_session_auth_hash(request, user)
            return redirect("admin_dashboard")
        return render(request, "mvault/password_change.html", {"form": form, "required": True})
    return change_password(request, required=True)

@member_required
def project_create(request):
    form = ProjectForm(request.POST or None, request.FILES or None, language=request.user.preferred_language)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        if Project.objects.filter(owner=request.user, name__iexact=project.name.strip(), is_deleted=False).exists():
            form.add_error("name", "An active project with this name already exists.")
        elif apply_custom_icon(project, "projects", form):
            project.name = project.name.strip()
            project.save()
            record_audit(request.user, request.user, "project_created", project=project)
            return redirect("project_detail", project_id=project.pk)
    return render(request, "mvault/project_form.html", {"form": form})

@member_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, pk=project_id, is_deleted=False)
    shared = False
    if project.owner_id != request.user.id:
        grant = ProjectShare.objects.filter(project=project, recipient=request.user, revoked_at__isnull=True, project__owner__is_active=True).first()
        if not grant:
            raise Http404
        shared = True
    folders = project.folders.filter(is_deleted=False).prefetch_related(
        Prefetch("records", queryset=Record.objects.filter(is_deleted=False), to_attr="active_records")
    ).annotate(record_count=Count("records", filter=Q(records__is_deleted=False)))
    folders = list(folders)
    for folder in folders:
        for record in folder.active_records:
            record.vault_fields = build_record_fields(record)
    records = list(Record.objects.filter(project=project, folder__isnull=True, is_deleted=False)) if project.project_type != "secret_vault" else []
    for record in records:
        record.vault_fields = build_record_fields(record)
    return render(request, "mvault/project_detail.html", {"project": project, "folders": folders, "records": records, "readonly": shared})

@member_required
def folder_create(request, project_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user, is_deleted=False)
    form = FolderForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"].strip()
        if Folder.objects.filter(project=project, name__iexact=name, is_deleted=False).exists():
            form.add_error("name", "An active folder with this name already exists in the project.")
        else:
            folder = Folder(project=project, name=name, icon=form.cleaned_data["icon"])
            if not apply_custom_icon(folder, "folders", form):
                return render(request, "mvault/folder_form.html", {"form": form, "project": project, "presets": FolderForm.PRESETS})
            folder.save()
            record_audit(request.user, request.user, "folder_created", project=project, folder=folder)
            return redirect("folder_detail", folder_id=folder.pk)
    return render(request, "mvault/folder_form.html", {"form": form, "project": project, "presets": FolderForm.PRESETS})

@member_required
def folder_detail(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, is_deleted=False)
    project = folder.project
    shared = False
    if project.owner_id != request.user.id:
        if not ProjectShare.objects.filter(project=project, recipient=request.user, revoked_at__isnull=True, project__owner__is_active=True).exists():
            raise Http404
        shared = True
    records = list(folder.records.filter(is_deleted=False).select_related("owner", "project"))
    for record in records:
        record.vault_fields = build_record_fields(record)
    recipients = User.objects.filter(is_admin=False, is_active=True).exclude(pk=request.user.pk) if not shared else User.objects.none()
    return render(request, "mvault/folder_detail.html", {"folder": folder, "project": project, "records": records, "readonly": shared, "recipients": recipients})


def build_record_fields(record):
    labels = {"username": "Username", "password": "Password", "website": "Website", "notes": "Notes", "cardholder": "Cardholder", "number": "Card number", "expiration": "Expiration", "cvv": "CVV", "issuer": "Issuer / bank", "pin": "Card PIN", "value": "Value", "value_type": "Value type"}
    sensitive = {"password", "number", "expiration", "cvv", "pin"}
    fields = [{"key": "key", "label": "Variable key", "value": record.name, "masked": False}] if record.record_type == "variable" else []
    if record.record_type == "file":
        current = record.attachment
        if current:
            fields.append({"key": "attachment", "label": "File", "value": f"{current.name} · {human_size(current.size)}", "masked": False,
                           "download_url": reverse("record_download", args=[record.pk]), "meta": f"{current.content_type} · SHA-256 {current.sha256[:16]}…" if current.sha256 else current.content_type})
        else:
            fields.append({"key": "attachment", "label": "File", "value": "", "masked": False})
    for key, value in record.data.items():
        if key == "value_type":
            continue
        if record.record_type == "json" and key == "value":
            fields.append({"key": key, "label": "JSON", "value": pretty_json(value), "masked": False, "is_json": True})
            continue
        fields.append({"key": key, "label": labels.get(key, key.title()), "value": value, "masked": key in sensitive or (record.record_type == "variable" and record.data.get("value_type") == "secret")})
    return fields


@member_required
@require_POST
def folder_record_actions(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, project__owner=request.user, project__is_deleted=False, is_deleted=False)
    single_delete = request.POST.get("single_delete")
    if single_delete:
        record = get_object_or_404(Record, pk=single_delete, folder=folder, owner=request.user, is_deleted=False)
        records = [record]
        action = "delete"
    else:
        selected_ids = request.POST.getlist("record_ids")
        records = list(Record.objects.filter(pk__in=selected_ids, folder=folder, owner=request.user, is_deleted=False).select_related("project"))
        action = request.POST.get("bulk_action")
        if not records:
            messages.error(request, "Select at least one record.")
            return redirect("folder_detail", folder_id=folder.pk)

    if action == "delete":
        with transaction.atomic():
            for record in records:
                save_revision(record, request.user)
                record.is_deleted = True
                record.save(update_fields=["is_deleted", "updated_at"])
                record_audit(request.user, request.user, "record_deleted", record=record)
        purge_record_files(r.pk for r in records if r.record_type == "file")
        messages.success(request, f"Deleted {len(records)} record(s).")
    elif action == "share" and not single_delete:
        recipient = get_object_or_404(User, pk=request.POST.get("recipient"), is_admin=False, is_active=True)
        if recipient.pk == request.user.pk:
            raise Http404
        with transaction.atomic():
            for record in records:
                RecordShare.objects.get_or_create(record=record, recipient=recipient, revoked_at__isnull=True, defaults={"created_by": request.user})
                record_audit(request.user, request.user, "record_shared", record=record, details={"recipient": recipient.email})
        messages.success(request, f"Shared {len(records)} record(s) with {recipient.full_name}.")
    else:
        raise Http404
    return redirect("folder_detail", folder_id=folder.pk)

@member_required
def record_create(request, project_id, folder_id=None):
    project = get_object_or_404(Project, pk=project_id, owner=request.user, is_deleted=False)
    if project.project_type == "secret_vault" and folder_id is None:
        raise Http404
    folder = get_object_or_404(Folder, pk=folder_id, project=project, is_deleted=False) if folder_id else None
    allowed_types = RecordForm.allowed_types(project.project_type)
    form = RecordForm(request.POST or None, request.FILES or None, project_type=project.project_type,
                      initial={"record_type": allowed_types[0]}, language=request.user.preferred_language)
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"].strip()
        kind = form.cleaned_data["record_type"]
        if kind not in allowed_types:
            form.add_error("record_type", "This record type is not available in this project.")
        elif Record.objects.filter(project=project, folder=folder, name__iexact=name, is_deleted=False).exists():
            form.add_error("name", "An active record with this name already exists in this location.")
        else:
            try:
                with transaction.atomic():
                    record = Record.objects.create(owner=request.user, project=project, folder=folder, record_type=kind, name=name, data=form.payload())
                    if kind == "file":
                        attach_file(record, form.cleaned_data["file"], request.user)
                    save_revision(record, request.user)
            except storage.StorageError as exc:
                form.add_error("file", str(exc))
            else:
                record_audit(request.user, request.user, "record_created", record=record)
                return redirect("record_detail", record_id=record.pk)
    return render(request, "mvault/record_form.html", {"form": form, "project": project, "folder": folder,
                  "record_type_label": project.get_project_type_display(), "creating": True, "multipart": True})

@member_required
def record_detail(request, record_id):
    record = get_object_or_404(Record.objects.select_related("project", "folder", "owner"), pk=record_id, is_deleted=False)
    allowed, shared = record_accessible(request.user, record)
    if not allowed:
        raise Http404
    if shared:
        record_audit(request.user, record.owner, "shared_record_viewed", record=record)
    fields = build_record_fields(record)
    return render(request, "mvault/record_detail.html", {"record": record, "readonly": shared, "fields": fields, "revisions": record.revisions.select_related("actor")[:50]})

@member_required
def record_download(request, record_id):
    record = get_object_or_404(Record.objects.select_related("project", "owner"), pk=record_id, is_deleted=False, record_type="file")
    allowed, shared = record_accessible(request.user, record)
    attachment = record.attachment
    if not allowed or attachment is None:
        raise Http404
    try:
        body, length = storage.get_storage().open(settings.S3_ATTACHMENTS_BUCKET, attachment.object_key)
    except Exception:
        messages.error(request, "The file could not be retrieved from storage.")
        return redirect("record_detail", record_id=record.pk)
    record_audit(request.user, record.owner, "file_downloaded", record=record, details={"attachment_id": attachment.pk})
    response = StreamingHttpResponse(body.iter_chunks(64 * 1024), content_type=attachment.content_type)
    response["Content-Length"] = str(length)
    response["Content-Disposition"] = content_disposition_header(True, attachment.name)
    response["Cache-Control"] = "private, no-store"
    return response

@member_required
def record_edit(request, record_id):
    record = get_object_or_404(Record, pk=record_id, owner=request.user, is_deleted=False)
    if record.record_type not in RecordForm.allowed_types(record.project.project_type):
        raise Http404
    initial = {"record_type": record.record_type, "name": record.name, **record.data}
    if record.record_type == "json":
        initial["json_value"] = pretty_json(record.data.get("value", ""))
    current_file = record.attachment if record.record_type == "file" else None
    form = RecordForm(request.POST or None, request.FILES or None, project_type=record.project.project_type, record_type=record.record_type,
                      initial=initial, language=request.user.preferred_language, has_file=current_file is not None)
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"].strip()
        if Record.objects.filter(project=record.project, folder=record.folder, name__iexact=name, is_deleted=False).exclude(pk=record.pk).exists():
            form.add_error("name", "An active record with this name already exists in this location.")
        else:
            try:
                with transaction.atomic():
                    save_revision(record, request.user)
                    record.name = name
                    record.data = form.payload()
                    record.save()
                    if record.record_type == "file" and form.cleaned_data.get("file"):
                        attach_file(record, form.cleaned_data["file"], request.user)
            except storage.StorageError as exc:
                form.add_error("file", str(exc))
            else:
                record_audit(request.user, request.user, "record_updated", record=record)
                return redirect("record_detail", record_id=record.pk)
    return render(request, "mvault/record_form.html", {"form": form, "project": record.project,
                  "folder": record.folder, "record": record, "record_type_label": record.project.get_project_type_display(),
                  "creating": False, "current_file": current_file, "multipart": True})

@member_required
@require_POST
def record_delete(request, record_id):
    record = get_object_or_404(Record, pk=record_id, owner=request.user, is_deleted=False)
    save_revision(record, request.user)
    record.is_deleted = True
    record.save(update_fields=["is_deleted", "updated_at"])
    record_audit(request.user, request.user, "record_deleted", record=record)
    if record.record_type == "file":
        purge_record_files([record.pk])
    return redirect("folder_detail", folder_id=record.folder_id) if record.folder_id else redirect("project_detail", project_id=record.project_id)

@member_required
@require_POST
def folder_delete(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, project__owner=request.user, is_deleted=False)
    file_ids = list(folder.records.filter(is_deleted=False, record_type="file").values_list("pk", flat=True))
    folder.is_deleted = True
    folder.save(update_fields=["is_deleted"])
    folder.records.filter(is_deleted=False).update(is_deleted=True)
    purge_record_files(file_ids)
    record_audit(request.user, request.user, "folder_deleted", project=folder.project, folder=folder)
    return redirect("project_detail", project_id=folder.project_id)

@member_required
def record_history(request, record_id):
    record = get_object_or_404(Record, pk=record_id, owner=request.user)
    revisions = record.revisions.select_related("actor")
    return render(request, "mvault/history.html", {"record": record, "revisions": revisions})

@member_required
def audit_log(request):
    events = AuditEvent.objects.filter(Q(owner=request.user) | Q(actor=request.user)).select_related("actor", "project", "project__owner", "folder", "folder__project", "folder__project__owner", "record", "record__owner", "record__project")
    page = max(int(request.GET.get("page", "1")) if request.GET.get("page", "1").isdigit() else 1, 1)
    per_page = 30
    total = events.count()
    page_events = list(events[(page-1)*per_page:page*per_page])
    for event in page_events:
        event.activity_url = activity_target_url(event, request.user)
    return render(request, "mvault/audit.html", {"events": page_events, "page": page, "has_next": total > page*per_page, "has_previous": page > 1})

@member_required
def share_create(request, kind, object_id):
    if kind == "project":
        obj = get_object_or_404(Project, pk=object_id, owner=request.user, is_deleted=False)
    elif kind == "record":
        obj = get_object_or_404(Record, pk=object_id, owner=request.user, is_deleted=False)
    else:
        raise Http404
    recipients = User.objects.filter(is_admin=False, is_active=True).exclude(pk=request.user.pk)
    if request.method == "POST":
        recipient = get_object_or_404(recipients, pk=request.POST.get("recipient"))
        if kind == "project":
            ProjectShare.objects.get_or_create(project=obj, recipient=recipient, revoked_at__isnull=True, defaults={"created_by": request.user})
        else:
            RecordShare.objects.get_or_create(record=obj, recipient=recipient, revoked_at__isnull=True, defaults={"created_by": request.user})
        record_audit(request.user, request.user, "project_shared" if kind == "project" else "record_shared", record=obj if kind == "record" else None, project=obj if kind == "project" else None, details={"recipient": recipient.email})
        messages.success(request, f"Shared with {recipient.full_name}.")
        return redirect("record_detail", record_id=obj.pk) if kind == "record" else redirect("project_detail", project_id=obj.pk)
    return render(request, "mvault/share_form.html", {"kind": kind, "object": obj, "recipients": recipients})

@member_required
def shared_items(request):
    project_shares = list(ProjectShare.objects.filter(
        recipient=request.user, revoked_at__isnull=True, project__owner__is_active=True, project__is_deleted=False,
    ).select_related("project", "project__owner"))
    shared_project_ids = {share.project_id for share in project_shares}
    trees = []

    for share in project_shares:
        project = share.project
        folders = list(project.folders.filter(is_deleted=False).prefetch_related(
            Prefetch("records", queryset=Record.objects.filter(is_deleted=False).select_related("project", "owner"), to_attr="active_records")
        ).annotate(record_count=Count("records", filter=Q(records__is_deleted=False))))
        for folder in folders:
            for record in folder.active_records:
                record.vault_fields = build_record_fields(record)
        folder_trees = [{"folder": folder, "active_records": folder.active_records, "record_count": folder.record_count} for folder in folders]
        root_records = list(project.records.filter(folder__isnull=True, is_deleted=False).select_related("project", "owner")) if project.project_type != "secret_vault" else []
        for record in root_records:
            record.vault_fields = build_record_fields(record)
        trees.append({"project": project, "owner": project.owner, "access": "Shared project", "folders": folder_trees, "records": root_records})

    record_shares = RecordShare.objects.filter(
        recipient=request.user, revoked_at__isnull=True, record__owner__is_active=True, record__is_deleted=False,
        record__project__owner__is_active=True, record__project__is_deleted=False,
    ).exclude(record__project_id__in=shared_project_ids).select_related(
        "record", "record__project", "record__project__owner", "record__owner", "record__folder",
    )
    grouped = {}
    for share in record_shares:
        record = share.record
        record.vault_fields = build_record_fields(record)
        project = record.project
        tree = grouped.setdefault(project.pk, {"project": project, "owner": project.owner, "access": "Shared records", "folders_by_id": {}, "records": []})
        if record.folder and not record.folder.is_deleted:
            folder = tree["folders_by_id"].setdefault(record.folder_id, {"folder": record.folder, "active_records": [], "record_count": 0})
            folder["active_records"].append(record)
            folder["record_count"] += 1
        else:
            tree["records"].append(record)
    for tree in grouped.values():
        tree["folders"] = list(tree.pop("folders_by_id").values())
        trees.append(tree)

    trees.sort(key=lambda tree: (tree["project"].name.casefold(), tree["project"].pk))
    return render(request, "mvault/shared.html", {"shared_trees": trees})

@member_required
def record_copy(request, record_id):
    source = get_object_or_404(Record, pk=record_id, is_deleted=False)
    access = ProjectShare.objects.filter(project=source.project, recipient=request.user, revoked_at__isnull=True, project__owner__is_active=True).exists() or RecordShare.objects.filter(record=source, recipient=request.user, revoked_at__isnull=True, record__owner__is_active=True).exists()
    if not access:
        raise Http404
    projects = Project.objects.filter(owner=request.user, is_deleted=False)
    if source.record_type in ("json", "file"):
        projects = projects.exclude(project_type="secret_vault")  # records there must live in an environment folder
    else:
        projects = projects.filter(project_type=source.project.project_type)
    if request.method == "POST":
        destination = get_object_or_404(projects, pk=request.POST.get("project"))
        name = source.name
        if Record.objects.filter(project=destination, folder__isnull=True, name__iexact=name, is_deleted=False).exists():
            suffix = 1
            while Record.objects.filter(project=destination, folder__isnull=True, name__iexact=f"{source.name} (copy {suffix})", is_deleted=False).exists():
                suffix += 1
            name = f"{source.name} (copy {suffix})"
        source_attachment = source.attachment if source.record_type == "file" else None
        try:
            with transaction.atomic():
                copied = Record.objects.create(owner=request.user, project=destination, record_type=source.record_type, name=name, data=source.data)
                if source_attachment:
                    Attachment.objects.create(record=copied, object_key=storage.copy_attachment(source_attachment.object_key), size=source_attachment.size,
                                              sha256=source_attachment.sha256, meta=source_attachment.meta, uploaded_by=request.user)
                save_revision(copied, request.user)
        except storage.StorageError as exc:
            messages.error(request, str(exc))
            return redirect("record_detail", record_id=source.pk)
        record_audit(request.user, request.user, "shared_record_copied", record=copied, details={"source_record_id": source.pk})
        messages.success(request, f"Copied into {destination.name}.")
        return redirect("record_detail", record_id=copied.pk)
    return render(request, "mvault/copy_form.html", {"record": source, "projects": projects})

@member_required
def env_import(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, project__owner=request.user, project__project_type="secret_vault", is_deleted=False)
    if request.method == "POST":
        upload = request.FILES.get("env_file")
        if not upload or upload.size > 1024 * 1024:
            messages.error(request, "Choose a .env file smaller than 1 MB.")
            return redirect("folder_detail", folder_id=folder.pk)
        try:
            values = parse_env(upload.read().decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            messages.error(request, f"Could not import file: {exc}")
            return redirect("folder_detail", folder_id=folder.pk)
        for key in values:
            collision = Record.objects.filter(project=folder.project, folder=folder, owner=request.user, is_deleted=False, name__iexact=key).first()
            if collision and collision.record_type != "variable":
                messages.error(request, f"Could not import {key}: a non-variable record already uses that name.")
                return redirect("folder_detail", folder_id=folder.pk)
        with transaction.atomic():
            for key, value in values.items():
                record = Record.objects.filter(project=folder.project, folder=folder, owner=request.user, name__iexact=key, record_type="variable", is_deleted=False).first()
                if record:
                    save_revision(record, request.user)
                    record.data = {"value": value, "value_type": record.data.get("value_type", env_value_type(key))}
                    record.save(update_fields=["data", "updated_at"])
                    record_audit(request.user, request.user, "record_import_updated", record=record)
                else:
                    record = Record.objects.create(owner=request.user, project=folder.project, folder=folder, record_type="variable", name=key, data={"value": value, "value_type": env_value_type(key)})
                    save_revision(record, request.user)
                    record_audit(request.user, request.user, "record_imported", record=record)
        messages.success(request, f"Imported {len(values)} variables.")
    return redirect("folder_detail", folder_id=folder.pk)

@member_required
def env_export(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, project__owner=request.user, project__project_type="secret_vault", is_deleted=False)
    records = folder.records.filter(is_deleted=False, record_type="variable")
    response = HttpResponse(export_env(records), content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{slugify(folder.name) or "environment"}.env"'
    record_audit(request.user, request.user, "env_exported", project=folder.project, folder=folder)
    return response

@member_required
def project_edit(request, project_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user, is_deleted=False)
    form = ProjectForm(request.POST or None, request.FILES or None, instance=project, language=request.user.preferred_language)
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"].strip()
        if Project.objects.filter(owner=request.user, name__iexact=name, is_deleted=False).exclude(pk=project.pk).exists():
            form.add_error("name", "An active project with this name already exists.")
        elif apply_custom_icon(project, "projects", form):
            project.name = name
            project.icon = form.cleaned_data["icon"]
            project.save()
            record_audit(request.user, request.user, "project_updated", project=project)
            return redirect("project_detail", project_id=project.pk)
    return render(request, "mvault/project_form.html", {"form": form, "project": project})

@member_required
@require_POST
def project_delete(request, project_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user, is_deleted=False)
    file_ids = list(project.records.filter(is_deleted=False, record_type="file").values_list("pk", flat=True))
    project.is_deleted = True
    project.save(update_fields=["is_deleted"])
    project.folders.filter(is_deleted=False).update(is_deleted=True)
    project.records.filter(is_deleted=False).update(is_deleted=True)
    purge_record_files(file_ids)
    ProjectShare.objects.filter(project=project, revoked_at__isnull=True).update(revoked_at=timezone.now())
    record_audit(request.user, request.user, "project_deleted", project=project)
    return redirect("dashboard")

@member_required
def folder_edit(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, project__owner=request.user, is_deleted=False)
    form = FolderForm(request.POST or None, request.FILES or None, initial={"name": folder.name, "icon": folder.icon})
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"].strip()
        if Folder.objects.filter(project=folder.project, name__iexact=name, is_deleted=False).exclude(pk=folder.pk).exists():
            form.add_error("name", "An active folder with this name already exists.")
        elif apply_custom_icon(folder, "folders", form):
            folder.name = name
            folder.icon = form.cleaned_data["icon"]
            folder.save(update_fields=["name", "icon", "custom_icon_key"])
            record_audit(request.user, request.user, "folder_updated", project=folder.project, folder=folder)
            return redirect("folder_detail", folder_id=folder.pk)
    return render(request, "mvault/folder_form.html", {"form": form, "project": folder.project, "folder": folder, "presets": FolderForm.PRESETS})


@member_required
@require_POST
def record_value_action(request, record_id):
    record = get_object_or_404(Record, pk=record_id, is_deleted=False)
    if record.owner_id == request.user.id:
        shared = False
    else:
        shared = ProjectShare.objects.filter(project=record.project, recipient=request.user, revoked_at__isnull=True, project__owner__is_active=True).exists() or RecordShare.objects.filter(record=record, recipient=request.user, revoked_at__isnull=True, record__owner__is_active=True).exists()
        if not shared:
            raise Http404
    field = request.POST.get("field", "")
    action = request.POST.get("action", "")
    if action not in {"reveal", "copy"}:
        return HttpResponseForbidden()
    if field == "key" and record.record_type == "variable":
        value = record.name
    elif field in record.data:
        value = pretty_json(record.data[field]) if record.record_type == "json" and field == "value" else str(record.data[field])
    else:
        raise Http404
    record_audit(request.user, record.owner, f"value_{action}", record=record, details={"field": field})
    return JsonResponse({"value": value})

@member_required
@require_POST
def share_revoke(request, kind, share_id):
    if kind == "project":
        grant = get_object_or_404(ProjectShare, pk=share_id, project__owner=request.user, revoked_at__isnull=True)
    elif kind == "record":
        grant = get_object_or_404(RecordShare, pk=share_id, record__owner=request.user, revoked_at__isnull=True)
    else:
        raise Http404
    grant.revoked_at = timezone.now()
    grant.save(update_fields=["revoked_at"])
    messages.success(request, "Share revoked.")
    return redirect("project_detail", project_id=grant.project_id) if kind == "project" else redirect("record_detail", record_id=grant.record_id)


def _safe_part(text, fallback="untitled"):
    cleaned = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", str(text)).strip(" .")[:100]
    return cleaned or fallback


def _unique(name, used):
    candidate, n = name, 2
    while candidate.lower() in used:
        stem, ext = os.path.splitext(name)
        candidate, n = f"{stem} ({n}){ext}", n + 1
    used.add(candidate.lower())
    return candidate


@member_required
@require_POST
def export_all(request):
    """Download every active project/folder/record of the member as a ZIP of CSV files (decrypted) plus attached files."""
    user = request.user
    records = (Record.objects.filter(owner=user, is_deleted=False, project__owner=user, project__is_deleted=False)
               .exclude(folder__is_deleted=True).select_related("project", "folder").order_by("project__name", "folder__name", "name", "id"))
    groups = {}
    for record in records:
        groups.setdefault((record.project, record.folder), []).append(record)
    for project in Project.objects.filter(owner=user, is_deleted=False):  # keep empty projects/folders in the tree
        groups.setdefault((project, None), [])
        for folder in project.folders.filter(is_deleted=False):
            groups.setdefault((project, folder), [])

    archive_file = tempfile.TemporaryFile()
    project_dirs, folder_dirs, exported = {}, {}, 0
    with zipfile.ZipFile(archive_file, "w", zipfile.ZIP_DEFLATED) as archive:
        for (project, folder), items in sorted(groups.items(), key=lambda kv: (kv[0][0].name.lower(), kv[0][0].pk, kv[0][1].name.lower() if kv[0][1] else "", kv[0][1].pk if kv[0][1] else 0)):
            if project.pk not in project_dirs:
                project_dirs[project.pk] = _unique(_safe_part(project.name), {v.lower() for v in project_dirs.values()})
            project_dir = project_dirs[project.pk]
            directory = project_dir
            if folder:
                taken = {v.lower() for (pid, _), v in folder_dirs.items() if pid == project.pk}
                directory = f"{project_dir}/" + folder_dirs.setdefault((project.pk, folder.pk), _unique(_safe_part(folder.name), taken))
            used_files = {"records.csv"}
            rows, columns = [], []
            for record in items:
                row = {"record_type": record.record_type, "name": record.name}
                row.update({key: ("" if value is None else str(value)) for key, value in record.data.items()})
                if record.record_type == "file":
                    attachment = record.attachment
                    if attachment:
                        ext = os.path.splitext(attachment.name)[1][:20]
                        filename = _unique(_safe_part(record.name) + ext, used_files)
                        body, _length = storage.get_storage().open(settings.S3_ATTACHMENTS_BUCKET, attachment.object_key)
                        with archive.open(f"{directory}/{filename}", "w", force_zip64=True) as target:
                            for chunk in body.iter_chunks(64 * 1024):
                                target.write(chunk)
                        row["file"] = filename
                for key in row:
                    if key not in columns:
                        columns.append(key)
                rows.append(row)
                exported += 1
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=columns or ["record_type", "name"], restval="")
            writer.writeheader()
            writer.writerows(rows)
            archive.writestr(f"{directory}/records.csv", "\ufeff" + buffer.getvalue())
    archive_file.seek(0)
    record_audit(user, user, "data_exported", details={"records": exported})
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    return FileResponse(archive_file, as_attachment=True, filename=f"mvault-export-{stamp}.zip", content_type="application/zip")
