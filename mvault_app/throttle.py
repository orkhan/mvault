"""Sign-in throttling: failed attempts per email and per client address within a sliding window."""
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import LoginAttempt


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if settings.TRUST_PROXY_HEADERS and forwarded:
        return forwarded.split(",")[-1].strip()[:45]  # the entry appended by our own proxy, not client-supplied
    return request.META.get("REMOTE_ADDR", "")[:45]


def _recent(**filters):
    since = timezone.now() - timedelta(seconds=settings.LOGIN_ATTEMPT_WINDOW_SECONDS)
    return LoginAttempt.objects.filter(created_at__gte=since, **filters)


def is_blocked(email, ip):
    """Refuse sign-in after too many recent failures.

    The tight limit counts failures for this e-mail *from this address*, so a stranger who knows a member's
    e-mail cannot lock them out from elsewhere. Per address and per e-mail (from anywhere) there are looser
    limits that still stop spraying many accounts or guessing one account from many addresses.
    """
    limit = settings.LOGIN_MAX_ATTEMPTS
    return (_recent(email=email, ip=ip).count() >= limit or _recent(ip=ip).count() >= limit * 4
            or _recent(email=email).count() >= limit * 10)


def record_failure(email, ip):
    LoginAttempt.objects.create(email=email[:254], ip=ip)
    LoginAttempt.objects.filter(created_at__lt=timezone.now() - timedelta(seconds=settings.LOGIN_ATTEMPT_WINDOW_SECONDS * 4)).delete()


def clear(email):
    LoginAttempt.objects.filter(email=email).delete()
