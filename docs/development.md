# Development

## Requirements

- Python 3.12 and [`uv`](https://docs.astral.sh/uv/) (or a virtualenv with `requirements.txt`)
- A local PostgreSQL 14+ (the tests need a real PostgreSQL; the test runner creates and drops its own `test_…` database, so the role needs `CREATEDB`)
- Docker (optional) to build the images

## Setup

```bash
git clone https://github.com/orkhan/mvault && cd mvault
cp .env.local.example .env.local
```

Create a local role and database, then fill `.env.local` (`DB_*`, `DJANGO_SECRET_KEY`, `MVAULT_ADMIN_PASSWORD`, `MVAULT_SEED_PASSWORD`):

```sql
CREATE ROLE mvault_local LOGIN PASSWORD 'dev-only' CREATEDB;
CREATE DATABASE mvault_local OWNER mvault_local;
```

`.env.local` is loaded automatically by `settings.py` and is git-ignored. With `DJANGO_DEBUG=true` the encryption key and salt fall back to insecure development values, so you do not need to set them locally.

## Run

```bash
uv run --python 3.12 --with-requirements requirements.txt python manage.py migrate
uv run --python 3.12 --with-requirements requirements.txt python manage.py ensure_admin
uv run --python 3.12 --with-requirements requirements.txt python manage.py runserver 127.0.0.1:8010
```

Demo data (users `alice@example.test` and `bob@example.test`, projects, records, shares):

```bash
uv run --python 3.12 --with-requirements requirements.txt python manage.py seed_local
```

## Tests

```bash
uv run --python 3.12 --with-requirements requirements.txt python manage.py test
uv run --python 3.12 --with-requirements requirements.txt python manage.py makemigrations --check --dry-run
```

Both must pass before a pull request. CI also runs ruff (`ruff.toml`), `manage.py check`, pip-audit, hadolint, shellcheck and Docker builds of both targets. Tests live in `mvault_app/tests.py`. Object storage is replaced by an in-memory `FakeStorage` by patching `mvault_app.storage.get_storage`; the settings supply dummy S3 values when running tests, so no MinIO is needed. A log line such as `RuntimeError: down` during the run comes from a test that simulates a storage failure and is expected.

## Optional: local MinIO

Only needed to try uploads end to end. Set `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` in `.env.local`, start any S3-compatible server, and run `python manage.py provision_storage`.

## Build the images

```bash
docker build --target slim -t mvault:slim .
docker build --target aio  -t mvault:aio  .      # compiles MinIO from source; takes several minutes
```

Multi-arch builds (`linux/amd64`, `linux/arm64`) are done in CI.

## Project layout

See [architecture.md](architecture.md#code-layout). Conventions for contributors and coding agents are in [AGENTS.md](../AGENTS.md).

## Adding things

- **A stored value:** it must go through `EncryptedJSONField` (or be genuinely non-sensitive metadata). Add a reversible migration.
- **A setting:** read it in `mvault_project/settings.py` via `env()` / `env_bool()` (this gives `_FILE` support for free), document it in [configuration.md](configuration.md) and `.env.example`.
- **UI text:** wrap in the `{% tr %}` tag and add the Russian string to `RU` in `mvault_app/templatetags/mvault_i18n.py`.
- **An icon:** add it to `ICONS` in `mvault_i18n.py` and a `<symbol>` in `templates/mvault/icons.html`.
