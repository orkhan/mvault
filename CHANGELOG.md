# Changelog

All notable changes to mVault are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow [Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may contain breaking changes, called out below).

## [Unreleased]

## [0.4.0] - 2026-10-11

First public release.

### Added
- **Native installer** (`install.sh`) for Linux (systemd, enabled by default) and macOS, with the `mvault` command (`start stop restart status logs backup restore upgrade doctor ...`), checksum-verified downloads, automatic rollback on a failed upgrade, and options to use your own PostgreSQL or S3 storage.
- **Proxmox VE LXC helper scripts** (`proxmox/ct/mvault.sh`, `proxmox/install/mvault-install.sh`) built on the native installer and the community-scripts framework.
- **CI and release automation**: lint, tests, `pip-audit`, hadolint, shellcheck, CodeQL, multi-arch image publishing to GHCR with SBOM and provenance, release assets (app tarball, pinned-source MinIO binaries, `SHA256SUMS`).
- Container images defined by one `Dockerfile` with two targets: `slim` (app only) and `aio` (app + PostgreSQL 15 + MinIO under s6-overlay), multi-arch (`linux/amd64`, `linux/arm64`) in CI. The all-in-one image skips its embedded PostgreSQL or MinIO when `DB_HOST`/`DATABASE_URL` or `S3_ENDPOINT_URL` are set. MinIO is built from a pinned upstream source tag.
- `compose.yaml` (all-in-one), `compose.external.yaml` (own PostgreSQL/MinIO) and `compose.dev.yaml`.
- Configuration: `DATABASE_URL`, `NAME_FILE` secret variants for every setting, `MVAULT_BASE_URL` (derives allowed hosts, CSRF origins, secure cookies, HSTS), `MVAULT_ADMIN_EMAIL`, `MVAULT_TIME_ZONE`, `MVAULT_HSTS_SECONDS`, `S3_REGION`.
- Management commands: `check_config`, `provision_storage`, `rotate_encryption_key`.
- Sign-in throttling (HTTP 429 after repeated failures per e-mail and per client address) with `MVAULT_LOGIN_MAX_ATTEMPTS`, `MVAULT_LOGIN_WINDOW_SECONDS`, `MVAULT_TRUST_PROXY`.
- `Content-Security-Policy` and `Referrer-Policy` headers.
- Icons and avatars are served by the app at `/media/…` (signed-in users), so a separate public storage host is no longer needed.
- Documentation, `AGENTS.md`/`CLAUDE.md`, contribution and security policies, issue and pull request templates.

### Security
- The all-in-one image pins PostgreSQL 15 and refuses to start on a data directory written by a different major version instead of touching it; the dump/restore procedure is in `docs/upgrading.md`.
- README, `SECURITY.md` and `docs/security.md` state plainly that mVault has not been independently audited.

### Changed
- **Breaking for pre-release deployments** (see [docs/upgrading.md](docs/upgrading.md)):
  - The administrator e-mail is `MVAULT_ADMIN_EMAIL` (default `admin@mvault.local`) instead of a fixed address.
  - `S3_ENDPOINT_URL` has no default; storage is optional and file records, icons and avatars are disabled without it.
  - `DB_HOST` defaults to `localhost`; the time zone defaults to `UTC`.
  - Secure cookies and HSTS follow `MVAULT_BASE_URL` instead of being always on.
  - `ICONS_PUBLIC_BASE_URL`/`AVATARS_PUBLIC_BASE_URL` default to empty (app-served media).
- Demo data (`seed_local`) uses `alice@example.test` and `bob@example.test`.

### Fixed
- Add-record form: JSON and file fields now appear before Notes, and the subtitle no longer claims the type comes from the project.
- JSON record view uses the full width; dashboard greeting no longer ends with an ellipsis.
- Dependency floors raised: `cryptography` (known vulnerabilities), `gunicorn` 26, `argon2-cffi`, `boto3`, `Pillow`.

## [0.3.0] - 2026-10-11

### Added
- Avatars: members upload a picture in Settings (stored in a dedicated `mvault-avatars` bucket). The sidebar shows the uploaded avatar, otherwise the Gravatar for the member's e-mail, otherwise initials.
- JSON editor line numbers and live syntax highlighting.

### Changed
- JSON and file records are available in **every** project type; the add-record form has a type selector that shows only the fields of the chosen type. JSON and file are no longer offered as separate project types for new projects.

### Fixed
- Deleting a file record (single, bulk, folder, project, or member purge) now also deletes its stored files.

## [0.2.1] - 2026-10-11

### Added
- *Settings → Export all data*: a ZIP shaped like the member's project/folder tree, with a CSV of decrypted values per location and file records as the original files.

## [0.2.0] - 2026-10-11

### Added
- S3-compatible object storage (MinIO) for icons and file attachments.
- **JSON** records with a validating editor and a prettified view; **file** records up to 50 MB (new `Attachment` table).
- Custom icons for projects and folders (validated and resized to 128 px).
- Encryption at rest: record values, history and attachment metadata are stored as AES-256-GCM ciphertext with a key derived (scrypt) from `MVAULT_ENCRYPTION_KEY` and `MVAULT_ENCRYPTION_SALT`. Migration `0006` encrypts existing plaintext rows in place and is reversible.
- The sidebar highlights the current project and folder, including while viewing a record inside them.

## [0.1.0] - 2026-10-08

### Added
- Initial release: admin-managed member accounts with Argon2id password hashes; projects with fixed types (passwords, bank cards, secrets), folders and records; masked values with audited reveal/copy; record history; activity log; read-only project and record sharing with copy-to-vault; `.env` import/export for secret projects; English and Russian interface.

[Unreleased]: https://github.com/orkhan/mvault/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/orkhan/mvault/releases/tag/v0.4.0
[0.3.0]: https://github.com/orkhan/mvault/releases/tag/v0.3.0
[0.2.1]: https://github.com/orkhan/mvault/releases/tag/v0.2.1
[0.2.0]: https://github.com/orkhan/mvault/releases/tag/v0.2.0
[0.1.0]: https://github.com/orkhan/mvault/releases/tag/v0.1.0
