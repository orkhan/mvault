# Claude Code instructions

@AGENTS.md

## Claude-specific notes

- Use **plan mode** before changing migrations, `crypto.py`/`fields.py`, authentication, sharing/authorisation, the Dockerfile or installers. Describe the data and security impact first.
- Run the test suite and `makemigrations --check --dry-run` before saying a task is done; report honestly if you could not run them.
- Prefer small, focused commits with the commit prefixes from AGENTS.md. Do not commit unless asked.
- Never print or echo the contents of `.env`, `.env.local` or key files; when you need to confirm a variable is set, check for presence only.
- Keep user-facing text translated: add the string to `RU` in `mvault_app/templatetags/mvault_i18n.py` and to every table in `mvault_app/locales/` together with the English one.
