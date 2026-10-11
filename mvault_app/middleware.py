from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import translation


class PreferredLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.supported = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        user = getattr(request, "user", None)
        language = getattr(user, "preferred_language", settings.LANGUAGE_CODE)
        if language not in self.supported:
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = language
        try:
            return self.get_response(request)
        finally:
            translation.deactivate()


class PasswordChangeRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.must_change_password:
            allowed = {reverse("password_change_required"), reverse("logout"), reverse("health")}
            if request.path not in allowed and not request.path.startswith("/static/"):
                return redirect("password_change_required")
        return self.get_response(request)
