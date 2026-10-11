from urllib.parse import urlsplit
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


class ContentSecurityPolicyMiddleware:
    """Restrictive CSP. Inline scripts/styles are still used by the templates, so those stay allowed."""

    def __init__(self, get_response):
        self.get_response = get_response
        images = ["'self'", "data:", "https://gravatar.com", "https://*.gravatar.com"]
        for base in (settings.ICONS_PUBLIC_BASE_URL, settings.AVATARS_PUBLIC_BASE_URL):
            if base:
                parts = urlsplit(base)
                images.append(f"{parts.scheme}://{parts.netloc}")
        self.policy = "; ".join([
            "default-src 'self'", f"img-src {' '.join(dict.fromkeys(images))}", "style-src 'self' 'unsafe-inline'",
            "script-src 'self' 'unsafe-inline'", "connect-src 'self'", "object-src 'none'", "base-uri 'self'",
            "form-action 'self'", "frame-ancestors 'none'",
        ])

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", self.policy)
        return response
