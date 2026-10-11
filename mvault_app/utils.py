import hashlib
import json
import re
import shlex
from django.utils import timezone
from .models import AuditEvent, RecordRevision

SECRET_TERMS = ("PASSWORD", "PASSWD", "SECRET", "TOKEN", "API_KEY", "ACCESS_KEY", "PRIVATE_KEY", "CREDENTIAL", "AUTH", "CLIENT_SECRET")
CLEAR_PLAIN_TERMS = ("PUBLIC", "HOST", "PORT", "DEBUG", "ENV", "MODE", "REGION", "LANG", "TIMEZONE", "LOG_LEVEL", "FEATURE")

def env_value_type(key):
    normalized = key.upper()
    if any(term in normalized for term in SECRET_TERMS):
        return "secret"
    if any(term in normalized for term in CLEAR_PLAIN_TERMS):
        return "plain"
    return "secret"

def parse_env(text):
    parsed = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("export "):
            if line.startswith("export "):
                line = line[7:].lstrip()
            else:
                continue
        if "=" not in line:
            raise ValueError(f"Line {line_number}: expected KEY=value")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Line {line_number}: invalid variable name")
        try:
            parts = shlex.split(raw_value, comments=True, posix=True)
        except ValueError as exc:
            raise ValueError(f"Line {line_number}: {exc}") from exc
        parsed[key] = " ".join(parts)
    return parsed

def export_env(records):
    lines = []
    for record in records.order_by("name", "id"):
        value = record.data.get("value", "")
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        lines.append(f'{record.name}="{escaped}"')
    return "\n".join(lines) + ("\n" if lines else "")

def save_revision(record, actor):
    return RecordRevision.objects.create(record=record, actor=actor, snapshot=record.snapshot())


def pretty_json(text):
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return text

def human_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB"):
        if value < 1024 or unit == "MB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024

def file_sha256(upload):
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    return digest.hexdigest()
