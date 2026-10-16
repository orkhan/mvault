# mVault open-source plan

Goal: publish mVault as an open-source, self-hostable family vault that installs four ways: an all-in-one multi-arch Docker image, a slim Docker image for people who already run PostgreSQL and MinIO/S3, a native `curl | sh` installer for Linux and macOS (no Docker, PostgreSQL + MinIO + the app on the host), and a Proxmox LXC helper script (targeting community-scripts.org) that builds on the native installer. Repository: `github.com/orkhan/mvault` (public, MIT).

Status legend: `[ ]` todo, `[x]` done.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| License | MIT | Maximum adoption. Bundled PostgreSQL (PostgreSQL License) and MinIO (AGPL-3.0) remain separate programs; their licenses and the MinIO source reference ship in the image (`/licenses`). |
| Repo history | Fresh history, not the homelab repo's | The homelab history contains personal hostnames/IPs/emails. Only the app source is copied. Commits use the GitHub no-reply address. |
| Registry | `ghcr.io/orkhan/mvault` | Same account as the repo, free, multi-arch manifests, no extra credentials in CI. Docker Hub mirror can be added later. |
| Platforms | `linux/amd64`, `linux/arm64` | Covers x86 servers/LXCs and Raspberry Pi / Apple-silicon homelabs. |
| Image flavours | `:<ver>` / `:latest` (all-in-one) and `:<ver>-slim` (app only) | Slim is for people with existing PostgreSQL + S3 (the maintainer's own setup). |
| Process model (all-in-one) | s6-overlay supervises PostgreSQL, MinIO, mVault | Ordered start (db → migrate → app), clean shutdown, multi-arch. One image, one `/data` volume, one published port (8000). |
| Reverse proxy | Not bundled | Users bring NPM/Caddy/Traefik/nginx. Docs give ready snippets (body size, timeouts, forwarded proto). |
| Icons/avatars delivery | Served by the app at `/media/...` by default | No second public hostname is needed. Optional `ICONS_PUBLIC_BASE_URL` / `AVATARS_PUBLIC_BASE_URL` keep the public-bucket mode (maintainer's homelab). |
| MinIO source | Built from a pinned upstream tag+commit in the image build; license shipped | Official images were withdrawn; building from source avoids trusting a third-party mirror. Alternative object stores (SeaweedFS, Garage) stay possible because the app only speaks S3. |
| Native installer | One `install.sh` (`curl -fsSL .../install.sh \| sh`) for Linux and macOS, PostgreSQL + MinIO + app together or any of them skipped | Docker-free install for VMs, bare metal, LXC and Macs. Linux: systemd units enabled by default. macOS: a `mvault` command (`start`/`stop`/`restart`/`status`/`logs`), no auto-start. Release tarballs per OS/arch; Python via a pinned `uv`-managed interpreter so system Python does not matter. |
| Proxmox | Native install in a Debian LXC (no Docker inside) = the Linux native installer, wrapped in the community-scripts framework | community-scripts convention: `ct/mvault.sh` + `install/mvault-install.sh`, systemd services, `update_script`. Same layout, units and `mvault` CLI as any Linux install. |
| First public version | v0.4.0 | 0.3.0 is the current private homelab release; 0.4.0 adds packaging/config changes. |

## Deployment modes (one codebase)

| Component | Embedded (default in all-in-one image) | External (slim image, or all-in-one with overrides) |
|---|---|---|
| PostgreSQL | Started by s6 on `127.0.0.1:5432`, data in `/data/postgres`, random password in `/data/config` | Set `DB_HOST` (or `DATABASE_URL`) → embedded PostgreSQL is skipped |
| Object storage | MinIO on `127.0.0.1:9000`, data in `/data/minio`, root creds generated on first start | Set `S3_ENDPOINT_URL` (+ keys, bucket names) → embedded MinIO is skipped |
| Secrets | Generated once into `/data/config/secrets.env` if not supplied (Django key, encryption key + salt, admin password) | Supply via env / Docker secrets (`*_FILE` variants) |

### Native install layout (Linux and macOS, no Docker)

| Item | Linux | macOS |
|---|---|---|
| App | `/opt/mvault` (release tarball + `uv`-managed Python venv) | `~/Library/Application Support/mvault/app` (per-user; `--prefix` to change) |
| Config / secrets | `/etc/mvault/mvault.env` (0640 `root:mvault`), generated on first install | `<support dir>/mvault.env` (0600) |
| Data | PostgreSQL via distro packages (own cluster/db `mvault`), MinIO data in `/var/lib/mvault/minio` | Homebrew PostgreSQL (or bundled binaries) with data in the support dir, MinIO data in the support dir |
| Services | `mvault-web.service`, `mvault-minio.service` (+ distro `postgresql.service`), enabled and started by the installer, run as user `mvault` | Plain processes started by the CLI (pidfiles + logs); optional `mvault service install` for launchd later |
| CLI | `/usr/local/bin/mvault`: `start stop restart status logs enable disable upgrade backup restore config admin manage doctor uninstall version` (service verbs call `systemctl`) | Same CLI; `start stop restart status logs` manage PostgreSQL, MinIO and the web process directly |
| Skipping parts | `--no-postgres` / `--no-minio` (point `mvault.env` at your own `DATABASE_URL` / `S3_*`) | Same flags |

## Phases

### Phase 0 — Repository bootstrap
- [x] Create `~/mvault`, copy the app source (no `.env`, no build artefacts, no history)
- [x] Scrub personal/deployment data from code defaults (admin address, URLs, timezone, demo users)
- [x] Serve icons/avatars through the app by default (`/media/...`)
- [x] MIT `LICENSE`, this plan
- [x] Create public `orkhan/mvault`, push, set description/topics, enable private vulnerability reporting

### Phase 1 — Configuration hardening (app)
- [x] Settings reference: every env var documented in one table (`docs/configuration.md`), `*_FILE` secret variants
- [x] Optional storage: app works without S3 (uploads disabled with a clear message) when nothing is configured
- [x] `DATABASE_URL` support, `MVAULT_TIME_ZONE`, `MVAULT_ADMIN_EMAIL`, `MVAULT_BASE_URL` (CSRF/allowed hosts derived from it)
- [x] Production security defaults: HSTS (behind HTTPS), CSP, login throttling/lockout, secure cookie defaults
- [x] `manage.py` helpers: `check_config`, `rotate_encryption_key` (re-encrypt all values with a new key/salt), `backup`/`restore` guidance
- [x] Keep upgrade path for the maintainer's deployment (`MVAULT_ADMIN_EMAIL`, public base URLs) — documented in `docs/upgrading.md`; applied in the Phase 8 switch-over

### Phase 2 — Docker images (multi-arch)
- [x] `Dockerfile` with targets `slim` and `aio` (Debian bookworm-slim, Python 3.12, non-root app user)
- [x] Go build stage for MinIO (pinned tag + commit, cross-compiled per `TARGETARCH`), licenses copied to `/licenses`
- [x] s6-overlay services: `postgres`, `minio`, `bootstrap` (secret generation, initdb, bucket provisioning), `migrate`, `web` (gunicorn)
- [x] Healthcheck, graceful shutdown, `/data` volume, single exposed port 8000
- [x] `compose.yaml` (all-in-one), `compose.external.yaml` (existing PostgreSQL + MinIO), `compose.dev.yaml`
- [x] `scripts/provision-minio.sh` (idempotent buckets/policy/service user for people with their own MinIO) — covered by `manage.py provision_storage` and the `mc` recipe in `docs/installation.md` (no separate script)
- [x] Smoke test on amd64 on a scratch host: aio first start/restart, embedded PostgreSQL + MinIO, file/icon round trips, slim with external PostgreSQL; trivy scan runs in CI
- [x] Run (not just build) the arm64 images — built by CI via QEMU, not yet executed on arm64 hardware — executed natively on Apple silicon (aarch64): embedded PostgreSQL + MinIO, buckets, file/icon round trip

### Phase 3 — CI/CD (GitHub Actions)
- [x] `ci.yml`: lint (ruff), tests against PostgreSQL service, `makemigrations --check`, `pip-audit`, hadolint, shellcheck — green on GitHub
- [x] `docker.yml`: buildx multi-arch, push to GHCR on tags and `main` (`edge`), provenance + SBOM attestations, trivy scan — `edge`/`edge-slim` published; anonymous pull verified; version tags appear with the first `v*` tag
- [x] `release.yml`: on `v*` tag → GitHub release with notes; assets `mvault-<ver>-{linux,darwin}-{amd64,arm64}.tar.gz` (app + installer helpers), pinned-source MinIO binaries for the same four targets, and `SHA256SUMS` (signed with cosign/attestation) used by `install.sh` and the Proxmox installer — written and actionlint-clean but has never run; first real run is the v0.4.0 tag — ran green on the v0.4.0 tag: app tarball, four MinIO binaries + licenses, `SHA256SUMS`, `install.sh`
- [x] Dependabot (pip, docker, actions), CodeQL, secret scanning + push protection
- [x] GHCR package `ghcr.io/orkhan/mvault` public (anonymous pull verified, amd64 + arm64)
- [x] Branch protection on `main` (required CI checks) — **after v0.4.0 is released**, so it does not block release commits — enabled after the v0.4.0 release: required CI checks, no force-push/deletion, owner can still push

### Phase 4 — Native installer for Linux and macOS (`curl | sh`)
- [x] `install.sh`: detects OS/arch/distro, verifies prerequisites, downloads the release tarball and checks it against `SHA256SUMS`; flags `--version`, `--prefix`, `--port`, `--base-url`, `--no-postgres`, `--no-minio`, `--upgrade`, `--uninstall`, `--yes`; idempotent, safe to re-run; never overwrites existing secrets
- [x] Python: pinned `uv` (checksum-verified) installs a managed Python 3.12 and the locked dependencies into a venv, so Debian/Ubuntu/RHEL/macOS system Python versions are irrelevant
- [x] PostgreSQL: Linux distro packages (apt/dnf), own role + database, localhost only; macOS Homebrew `postgresql@17` (bundled-binaries fallback). Skipped with `--no-postgres` → `DATABASE_URL` prompt/flag
- [x] MinIO: pinned-source binary from the release, own user and data dir, listens on localhost only, buckets provisioned with `manage.py provision_storage`. Skipped with `--no-minio` → `S3_*` flags or storage disabled
- [x] Linux services: `mvault-web.service`, `mvault-minio.service` with hardening (`NoNewPrivileges`, `ProtectSystem`, `PrivateTmp`, …), ordered after PostgreSQL, **enabled and started by default**; unattended-friendly
- [x] macOS: no auto-start; the `mvault` command starts/stops/restarts/reports status and tails logs for the PostgreSQL, MinIO and web processes
- [x] `mvault` CLI (single POSIX/bash script, installed to `/usr/local/bin`): `start|stop|restart|status|logs|enable|disable|version|upgrade|backup|restore|config|admin|manage|doctor|uninstall`
- [x] First-run bootstrap equals the container's: generated secrets (key, salt, DB/MinIO passwords), first-admin password printed once and forced to change
- [x] `upgrade`: stop → backup (pg_dump + config) → new release → migrate → start, with rollback on failure
- [x] Tested: macOS (Apple silicon), real systemd in Debian 12, Ubuntu 24.04 and Fedora 44 containers (install, reboot persistence, upgrade, rollback, backup/restore, re-run, uninstall/purge, checksum tamper)
- [ ] Still untested: Raspberry Pi OS (arm64), Rocky/Alma, Intel Mac, macOS with a real Homebrew install, an unprivileged Proxmox LXC — tracked in [#6](https://github.com/orkhan/mvault/issues/6)

### Phase 5 — Proxmox / community-scripts
- [x] `ct/mvault.sh` + `install/mvault-install.sh` following the community-scripts template (Debian 13 LXC, 2 vCPU / 2 GB / 8 GB defaults, unprivileged) — `proxmox/`; syntax- and shellcheck-clean
- [x] Native install = the Phase 4 Linux layout inside the LXC (PostgreSQL from apt, venv in `/opt/mvault`, MinIO release binary, systemd units, `mvault` CLI), expressed with the community-scripts helper functions; credentials in `/root/mvault.creds`; `update_script` calls `mvault upgrade`-equivalent steps — the install script runs the release's `install.sh` inside the LXC
- [x] Prompts honour `var_*` variables for unattended installs; options to use an existing PostgreSQL / S3 — `var_database_url`, `var_s3_*`, `var_provision_buckets`, `var_no_storage`, `var_base_url`, `var_admin_email` (+ interactive whiptail questions); flag mapping unit-tested in CI, external-DB + no-storage run end to end on real systemd
- [ ] Test on a real Proxmox host (amd64; arm64 where possible), including update path and backup/restore — not done: needs a Proxmox host (and the real release assets) — tracked in [#7](https://github.com/orkhan/mvault/issues/7)
- [x] Prepare the submission (fork of community-scripts' dev repo, PR text, logo/metadata). **Do not open the PR without the maintainer's go-ahead.** Check acceptance criteria (popularity/stars, maintenance commitment) first. — `proxmox/SUBMISSION.md`; the PR itself is NOT opened (needs maintainer go-ahead)
- [x] Until accepted: a one-liner in this repo's docs that creates the LXC with `pct` and runs `install.sh` inside it — `COMMUNITY_SCRIPTS_URL=… bash -c "$(curl …/proxmox/ct/mvault.sh)"` in `docs/proxmox.md`

### Phase 6 — Documentation
- [x] `README.md`: pitch, feature list, screenshots, quick start (3 commands), install options, security model, links
- [x] `docs/`: install (Docker AIO / external / native Linux and macOS / Proxmox), configuration reference, reverse proxy (NPM, Caddy, Traefik, nginx), backup & restore, upgrading, key management & rotation, security/threat model, architecture, FAQ, troubleshooting
- [x] `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, issue + PR templates, `CODEOWNERS`
- [x] Screenshots/GIF generated from the seeded demo data (no real data)

### Phase 7 — Agent guidance
- [x] `AGENTS.md` (single source of truth for Codex/Claude/others): project map, commands, conventions, security rules (never log values, never commit secrets), release checklist
- [x] `CLAUDE.md` importing `@AGENTS.md` plus Claude-specific notes; `.claude/` kept out of the repo unless shared on purpose

### Phase 8 — Release and homelab switch-over
- [x] Tag `v0.4.0`, verify the GHCR multi-arch manifest and release assets, run every install path from scratch (Docker AIO, Docker external, native Linux VM, native macOS, fresh LXC) — tag pushed; release + images verified (six version tags, amd64+arm64); aio run on amd64 and arm64, slim with external PostgreSQL, and the real `curl | sh` on a systemd Debian 12 container
- [x] Switch the maintainer's homelab to `ghcr.io/orkhan/mvault:<ver>-slim` with the existing PostgreSQL/MinIO and `MVAULT_ADMIN_EMAIL` preserved — done 2026-10-11: `0.4.0-slim` from GHCR, backup first, admin e-mail/URL/time zone preserved; one admin, 45/45 records decrypt
- [ ] Announce (GitHub release, r/selfhosted, awesome-selfhosted PR) once docs and CI are green — tracked in [#8](https://github.com/orkhan/mvault/issues/8)

### Phase 9 — Browser autofill
- [x] Manifest V3 Chrome extension with user-initiated fill, exact-host matching, scoped host permission, and seven interface locales
- [x] Authenticated mVault endpoints return matching labels and selected credentials only after server-side access and hostname checks; successful fills are audited
- [x] Document setup and security; cover owner, shared-record, and exact-host access in tests
- [ ] Manually smoke test the unpacked extension in Chrome against a local mVault instance

## Risks and decisions (resolved 2026-10-11)

| Risk | Decision |
|---|---|
| **MinIO upstream** is in maintenance mode; no future fixes. | Keep the pinned MinIO for 0.4.0 (scoped Trivy exemption until 2027-01-11); document S3 alternatives (SeaweedFS, Garage, …); revisit the embedded store in 0.5. |
| **Embedded PostgreSQL** major upgrades need a data migration. | Pin the major per image line (0.4.x = PostgreSQL 15); the image refuses to start on a mismatched data directory; dump/restore procedure documented in `docs/upgrading.md`. |
| **Security expectations** for a public password manager. | Before any announcement: a prominent "not independently audited" notice (README, SECURITY.md, `docs/security.md`). TOTP 2FA, passphrase-wrapped keys and an external review are post-0.4 roadmap items, not blockers. |
| **community-scripts acceptance** is uncertain. | Submit only after a real Proxmox test and some adoption; the standalone one-liner in `docs/proxmox.md` covers Proxmox users meanwhile. |
| **Native installs vary by distro.** | Officially support Debian/Ubuntu and Fedora/RHEL-like (as tested); others get a clear "unsupported" message and the Docker path. |
| **Docker disk space** on the maintainer's workstation. | Prune build cache and dangling images only (done); GitHub Actions and a remote builder do the real builds. |
| **Release timing** | Tag v0.4.0 as soon as CI is green on `main`; real arm64 and Proxmox checks follow as 0.4.x patches if they find anything. |
