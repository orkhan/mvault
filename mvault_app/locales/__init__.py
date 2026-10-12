"""Per-language UI string tables (English text -> translation). Russian lives in templatetags/mvault_i18n.py (``RU``)."""
from . import az, be, es, tr, uk

TABLES = {"az": az.STRINGS, "be": be.STRINGS, "es": es.STRINGS, "tr": tr.STRINGS, "uk": uk.STRINGS}
