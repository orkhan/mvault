from django.conf import settings


def _current_location(request):
    """Return (project_id, folder_id) of the project/folder the user is browsing, else (None, None).

    Record pages count as being inside the record's folder and project.
    """
    match = getattr(request, "resolver_match", None)
    if match is None:
        return None, None
    from .models import Folder, Record
    kwargs = match.kwargs
    if "record_id" in kwargs or (match.url_name == "share_create" and kwargs.get("kind") == "record"):
        record_id = kwargs.get("record_id") or kwargs.get("object_id")
        row = Record.objects.filter(pk=record_id, owner=request.user).values_list("project_id", "folder_id").first()
        return row or (None, None)
    if "folder_id" in kwargs and "project_id" not in kwargs:
        row = Folder.objects.filter(pk=kwargs["folder_id"]).values_list("project_id", "pk").first()
        return row or (None, None)
    if match.url_name == "share_create" and kwargs.get("kind") == "project":
        return kwargs.get("object_id"), None
    return kwargs.get("project_id"), kwargs.get("folder_id")


def sidebar(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or user.is_admin:
        return {"sidebar_projects": []}
    from .models import Project
    project_id, folder_id = _current_location(request)
    return {
        "sidebar_projects": Project.objects.filter(owner=user, is_deleted=False).prefetch_related("folders"),
        "active_project_id": project_id,
        "active_folder_id": folder_id,
    }


def app_meta(request):
    return {"app_version": settings.APP_VERSION}
