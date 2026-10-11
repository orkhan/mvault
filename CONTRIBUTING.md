# Contributing to mVault

Thanks for helping! mVault is a small project, so a short conversation before a big change saves everyone time. Please be kind: see the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Bugs and ideas:** open an issue using a template. For install or configuration problems use *Installation / configuration help*. **Never paste secrets** (encryption keys, passwords, `.env` contents, URLs with passwords).
- **Security problems:** do **not** open an issue; report privately ([SECURITY.md](SECURITY.md)).
- **Code, docs, translations:** open a pull request. For anything larger than a small fix, open an issue first so we can agree on the approach.
- **Translations:** the interface is English and Russian. UI strings go through `{% tr %}`; the Russian text lives in the `RU` dictionary in `mvault_app/templatetags/mvault_i18n.py`.

## Development setup

See [docs/development.md](docs/development.md). In short: Python 3.12, `uv`, a local PostgreSQL, then

```bash
cp .env.local.example .env.local        # fill in the database settings
uv run --python 3.12 --with-requirements requirements.txt python manage.py test
uv run --python 3.12 --with-requirements requirements.txt python manage.py makemigrations --check --dry-run
```

## Pull request checklist

- [ ] The change is focused; unrelated cleanups are separate PRs.
- [ ] Tests pass and new behaviour has tests (storage is faked in tests; no network or MinIO needed).
- [ ] `makemigrations --check --dry-run` reports no changes; new migrations are **reversible**.
- [ ] User-visible text uses `{% tr %}` and has a Russian translation.
- [ ] Docs updated (`docs/`, `.env.example`, [configuration reference](docs/configuration.md)) and an entry added under *Unreleased* in [CHANGELOG.md](CHANGELOG.md).
- [ ] No secrets, personal data, real hostnames or IP addresses in code, tests, docs or screenshots (use `example.com`, `example.test`).
- [ ] You are comfortable licensing the contribution under the [MIT License](LICENSE).

## Commit style

Short imperative subject with a type prefix, matching the existing history: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `release:`. Explain the *why* in the body when it is not obvious. Small, reviewable commits are preferred.

## Security-sensitive areas

Changes here get extra scrutiny; explain your reasoning in the PR:

- `mvault_app/crypto.py`, `fields.py` and migrations that touch encrypted columns (the key/salt, nonces, formats, and the rotation command).
- Authentication and sessions: `views.login_view`, `throttle.py`, `middleware.py`, password flows.
- Authorisation: sharing (`ProjectShare`, `RecordShare`), `record_accessible`, admin vs member decorators.
- Storage and uploads: `storage.py`, file/icon/avatar views, the `/media/` route, `Content-Disposition` handling.
- `settings.py` defaults, the CSP, and anything that logs or prints values (never log secrets or vault values).
- The Dockerfile, s6 scripts, installers and CI workflows.

## Conduct and review

Maintainers review as time allows. Expect questions; they are about the code, not you. Thank you for contributing.

> Coding agents (Codex, Claude Code, …) should read [AGENTS.md](AGENTS.md) first.
