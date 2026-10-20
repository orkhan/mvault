# Changelog

All notable changes to mVault are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow [Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may contain breaking changes, called out below).

## [Unreleased]

## [0.8.0] - 2026-10-20

### Added
- Chrome extension 1.2.0 suggests matching logins automatically: when a page with a login form opens and your vault has records for its exact hostname, a card lists them (and the toolbar badge shows the count). Nothing is filled until you click a record.
- The extension offers to save a login after you sign in or sign up, or to update a changed password. You pick the project and folder, can rename the record, and can choose "Not now" or "Never for this site". Logins already in your vault are not offered again. Two-step logins and single-page apps are handled; passwords captured for a prompt live only in memory for about a minute.
- Both features are opt-in (a switch in the extension popup that asks for access to all sites) and can be turned off separately; hidden sites can be restored from the popup.
- Server endpoints `/extension/projects/`, `/extension/save-check/` and `/extension/save/` (member accounts only, owner-only writes, no response caching); saves and updates are written to record history and the activity log.
- A versioned Chrome extension ZIP is available from GitHub releases, with installation steps in the README and extension guide.

### Changed
- The extension no longer needs an open mVault tab for lookups: it asks the server with your session cookie and only opens a background tab when you click Fill or Save and no mVault tab is open.

## [0.7.0] - 2026-10-16

### Changed
- The Chrome extension shows the username with every accessible password record matching the active site's exact hostname, and the full match list can be scrolled.

## [0.6.0] - 2026-10-16

### Added
- Chrome extension (`extension/`) for user-initiated username and password autofill from active password records with an exact website hostname match. It uses the signed-in mVault browser session and records successful fills in the audit log. Setup and security details are in [docs/chrome-extension.md](docs/chrome-extension.md).

## [0.5.2] - 2026-10-13

### Changed
- The Log out button is red, and Dashboard, Shared with me, Activity and Settings are highlighted in the sidebar on their pages.

### Fixed
- Breadcrumb links were larger than on the dashboard because the sidebar `nav a` styles leaked into them.

## [0.5.1] - 2026-10-12

### Fixed
- Breadcrumbs were never translated (the include lost the request, so `{% tr %}` fell back to English) in every language, Russian included.
- Untranslated UI text found by an audit of templates, views, forms, storage errors and inline scripts: page titles (history, share, reset password, delete member), "Delete {name}?" and "For {name}" headings, project type on the dashboard, "Former member", the admin dashboard activity list (showed raw action names), the CVV/PIN field labels, the "Valid JSON" status, the Users/Clock icon names and the sign-in throttling and other login errors.
- Flash messages built from variables (for example "Deleted 3 record(s).", "Shared with …", "Copied into …", "Imported … variables.") are now translated through `{name}`-style patterns; storage, import-parser and form validation errors too.

### Added
- `{% tr "Text {name}" name=value %}` and pattern keys in the translation tables; tests check that every template string, message, activity label and icon name exists in all seven languages.

## [0.5.0] - 2026-10-12

### Changed
- New brand: logo in the sidebar and sign-in page, favicon, Apple touch icon and web manifest (served from `/brand/…` and `/favicon.ico`).
- New colour palette (Night neutrals with a Vault Brass accent) applied across the interface; the design tokens are in `docs/design/uikit.css`.
- README screenshots regenerated with the new theme.

### Added
- Interface languages: Azerbaijani, Turkish, Spanish (Spain), Belarusian and Ukrainian, selectable in Settings. Translations live in `mvault_app/locales/`; the machine-assisted texts would benefit from native-speaker review.
- Record form: reveal/hide (eye) button for the Password and CVV inputs; bank card number (12–19 digits, Luhn), expiry (MM/YY), CVV (3 digits, 4 for Amex) and PIN (4–12 digits) are validated in the browser and on the server.
- Contribution docs now describe a `Co-authored-by` trailer convention for crediting coding agents (Claude, Codex) on commits.
- Proxmox helper: options to use an existing PostgreSQL and/or S3-compatible storage (`var_database_url`, `var_s3_*`, `var_provision_buckets`, `var_no_storage`, `var_base_url`, `var_admin_email`), plus interactive questions for hand-run installs; input is validated before anything is changed.

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

[Unreleased]: https://github.com/orkhan/mvault/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/orkhan/mvault/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/orkhan/mvault/compare/v0.5.2...v0.6.0
[0.5.2]: https://github.com/orkhan/mvault/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/orkhan/mvault/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/orkhan/mvault/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/orkhan/mvault/releases/tag/v0.4.0
[0.3.0]: https://github.com/orkhan/mvault/commit/32b0578

<!-- 0.1.0 to 0.2.1 were developed in a private repository before the project went public; the public history starts at 0.3.0 (see the link above). -->
