# Agent instructions

For Codex, Claude Code and other coding agents (human contributors: see [CONTRIBUTING.md](CONTRIBUTING.md)). This file is the single source of truth; `CLAUDE.md` imports it.

mVault is a self-hosted Django vault (passwords, bank cards, env variables, JSON, files) with PostgreSQL, optional S3-compatible storage, and application-level AES-256-GCM encryption. Read [PLAN.md](PLAN.md) for the release roadmap and [docs/architecture.md](docs/architecture.md) before structural changes.

## Project map

- `mvault_project/settings.py` — all configuration, parsed from env (`env()`, `env_bool()`, `NAME_FILE` support). `urls.py`, `wsgi.py`.
- `mvault_app/` — the app. `models.py`, `views.py` (function views with `@member_required` / `@admin_required`), `forms.py`, `crypto.py` + `fields.py` (encryption), `storage.py` (S3, icons/avatars/attachments), `throttle.py`, `middleware.py` (language, forced password change, CSP), `context_processors.py` (sidebar, version), `utils.py`.
- `mvault_app/templates/mvault/` — server-rendered templates; CSS and most JS are inline in `base.html`. `templatetags/mvault_i18n.py` — `{% tr %}`, `{% icon %}`, `{% avatar %}`, `{% entity_icon %}`, breadcrumbs and the **Russian dictionary `RU`**; `locales/` — the az, be, es, tr, uk tables.
- `mvault_app/management/commands/` — `check_config`, `ensure_admin`, `provision_storage`, `rotate_encryption_key`, `seed_local`, `wait_for_db`.
- `mvault_app/migrations/` — `0004`–`0006` introduced encryption (columns became text + in-place encryption); keep them reversible.
- `Dockerfile` (targets `slim`, `aio`), `docker/entrypoint.sh`, `docker/rootfs/etc/s6-overlay/` (all-in-one services), `compose*.yaml`.
- `docs/` — user documentation; `PLAN.md` — roadmap and decisions.

## Commands

```bash
# needs a local PostgreSQL configured in .env.local (see docs/development.md); the role needs CREATEDB
uv run --python 3.12 --with-requirements requirements.txt python manage.py test
uv run --python 3.12 --with-requirements requirements.txt python manage.py makemigrations --check --dry-run
uv run --python 3.12 --with-requirements requirements.txt python manage.py check_config
docker build --target slim -t mvault:slim .     # the aio target compiles MinIO and takes minutes
```

All tests must pass before you finish. A logged `RuntimeError: down` during tests is expected (a test simulates a storage failure). CI (`.github/workflows/ci.yml`) runs ruff (config in `ruff.toml`; run `ruff check .` locally if you have it), the tests against PostgreSQL, `makemigrations --check`, `manage.py check`, pip-audit, hadolint, shellcheck and a Docker build of both targets. Keep Python, shell and the Dockerfile clean for those.

## Conventions

- Match the surrounding style: compact, function-based views, small helpers, minimal comments that explain *why*. Do not reformat unrelated code.
- Auditable actions call `record_audit(...)`; user-facing messages use `messages.success/error` and are rendered through `tr`.
- **i18n:** every new UI string uses `{% tr "…" %}` and needs an entry in `RU` in `mvault_i18n.py` **and** in every `mvault_app/locales/<code>.py` (az, be, es, tr, uk); a test fails if a locale misses a key.
- **Icons:** add the name to `ICONS` in `mvault_i18n.py` and a `<symbol id="mv-icon-…">` to `icons.html`.
- **Storage in tests:** patch `mvault_app.storage.get_storage` with the in-memory `FakeStorage` from `tests.py`; never talk to real S3 or the network in tests. Views must call `storage.get_storage()` via the module so the patch applies.
- **Settings:** add new env vars in `settings.py` using `env()`; document them in `docs/configuration.md` and `.env.example`.
- **Branches:** when the maintainer asks for a new feature, start a new `feat/<short-name>` branch from `main` before changing anything (use `fix/…`, `docs/…` and so on for other work); never build a feature directly on `main`.
- Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `release:`; small and focused. When you (a coding agent) did substantial work on a commit, add a `Co-authored-by` trailer so the contribution is credited — `Co-authored-by: Claude <noreply@anthropic.com>` or `Co-authored-by: Codex <codex@users.noreply.github.com>`. The human running you stays the primary author.

## Rules that must not be broken

1. **Never log, print, return in errors, or put in test output** vault values, passwords, encryption keys/salts, tokens or database URLs with passwords. `check_config` and similar commands print no secret values.
2. **Encryption lives at the model-field layer.** Any new stored value that can be sensitive goes into an `EncryptedJSONField` (or is deliberately non-sensitive metadata, documented as such in `docs/security.md`). Do not add plaintext copies, search indexes or logs of decrypted data. Do not change the ciphertext format (`enc:v1:`) without a versioned, reversible migration plan.
3. **Migrations must be reversible** and safe on existing data. Back up first when changing anything under the encryption columns.
4. **Never commit** `.env`, `.env.local`, keys, tokens, database dumps or exports. Keep **personal data and deployment-specific hostnames/IPs/e-mails out of the repo** (use `example.com`, `example.test`, `192.0.2.x`).
5. Authorisation checks (owner / project share / record share / admin vs member) must stay server-side; add tests for any new endpoint that exposes record data or files.
6. Uploads are validated and size-limited; downloads use `Content-Disposition: attachment`. Do not weaken the CSP, cookie or header settings without a documented reason.
7. When behaviour changes, update in the same change: tests, `docs/`, `.env.example`, `CHANGELOG.md` (*Unreleased*), and, for a release, `APP_VERSION` in `settings.py`.

## Release checklist

1. Tests and `makemigrations --check` pass; images build (`slim`, `aio`).
2. `APP_VERSION` in `settings.py` bumped (a test asserts the footer version; update it).
3. `CHANGELOG.md`: move *Unreleased* to the new version with the date; add upgrade notes to `docs/upgrading.md` for breaking changes.
4. `PLAN.md` status updated; docs consistent with the code.
5. The maintainer tags `vX.Y.Z`; CI builds multi-arch images and release assets. **Agents do not tag or publish.**

## Ask before you…

- publish anything (tags, releases, images, packages), change repository visibility or settings, or open issues/PRs on other projects (for example community-scripts);
- force-push, rewrite history, or delete branches/tags;
- delete or overwrite data, volumes, buckets or databases, or touch the maintainer's running deployments;
- change cryptographic formats, key handling or the authentication model;
- add a dependency (explain licence and maintenance status).

## Quick pointers

- Run only what you need; prefer targeted checks. Say plainly what you verified and what you could not run.
- Docker Desktop disk space on the maintainer's workstation is tight; builds are better done in CI or on a remote builder.
