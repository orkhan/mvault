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
- [ ] Create public `orkhan/mvault`, push, set description/topics, enable private vulnerability reporting

### Phase 1 — Configuration hardening (app)
- [ ] Settings reference: every env var documented in one table (`docs/configuration.md`), `*_FILE` secret variants
- [ ] Optional storage: app works without S3 (uploads disabled with a clear message) when nothing is configured
- [ ] `DATABASE_URL` support, `MVAULT_TIME_ZONE`, `MVAULT_ADMIN_EMAIL`, `MVAULT_BASE_URL` (CSRF/allowed hosts derived from it)
- [ ] Production security defaults: HSTS (behind HTTPS), CSP, login throttling/lockout, secure cookie defaults
- [ ] `manage.py` helpers: `check_config`, `rotate_encryption_key` (re-encrypt all values with a new key/salt), `backup`/`restore` guidance
- [ ] Keep upgrade path for the maintainer's deployment (`MVAULT_ADMIN_EMAIL`, public base URLs)

### Phase 2 — Docker images (multi-arch)
- [x] `Dockerfile` with targets `slim` and `aio` (Debian bookworm-slim, Python 3.12, non-root app user)
- [x] Go build stage for MinIO (pinned tag + commit, cross-compiled per `TARGETARCH`), licenses copied to `/licenses`
- [x] s6-overlay services: `postgres`, `minio`, `bootstrap` (secret generation, initdb, bucket provisioning), `migrate`, `web` (gunicorn)
- [x] Healthcheck, graceful shutdown, `/data` volume, single exposed port 8000
- [x] `compose.yaml` (all-in-one), `compose.external.yaml` (existing PostgreSQL + MinIO), `compose.dev.yaml`
- [ ] `scripts/provision-minio.sh` (idempotent buckets/policy/service user for people with their own MinIO)
- [ ] Smoke test on amd64 — **done on a scratch host: aio first start/restart, embedded PostgreSQL + MinIO, file/icon round trips, slim with external PostgreSQL**. Still open: arm64 build/run (CI with QEMU), size/CVE scan (trivy)

### Phase 3 — CI/CD (GitHub Actions)
- [ ] `ci.yml`: lint (ruff), tests against PostgreSQL service, `makemigrations --check`, `pip-audit`, hadolint, shellcheck
- [ ] `docker.yml`: buildx multi-arch, push to GHCR on tags and `main` (`edge`), provenance + SBOM attestations, trivy scan
- [ ] `release.yml`: on `v*` tag → GitHub release with notes; assets `mvault-<ver>-{linux,darwin}-{amd64,arm64}.tar.gz` (app + installer helpers), pinned-source MinIO binaries for the same four targets, and `SHA256SUMS` (signed with cosign/attestation) used by `install.sh` and the Proxmox installer
- [x] Dependabot (pip, docker, actions), CodeQL, secret scanning + push protection
- [x] GHCR package `ghcr.io/orkhan/mvault` public (anonymous pull verified, amd64 + arm64)
- [ ] Branch protection on `main` (required CI checks) — **after v0.4.0 is released**, so it does not block release commits

### Phase 4 — Native installer for Linux and macOS (`curl | sh`)
- [ ] `install.sh`: detects OS/arch/distro, verifies prerequisites, downloads the release tarball and checks it against `SHA256SUMS`; flags `--version`, `--prefix`, `--port`, `--base-url`, `--no-postgres`, `--no-minio`, `--upgrade`, `--uninstall`, `--yes`; idempotent, safe to re-run; never overwrites existing secrets
- [ ] Python: pinned `uv` (checksum-verified) installs a managed Python 3.12 and the locked dependencies into a venv, so Debian/Ubuntu/RHEL/macOS system Python versions are irrelevant
- [ ] PostgreSQL: Linux distro packages (apt/dnf), own role + database, localhost only; macOS Homebrew `postgresql@17` (bundled-binaries fallback). Skipped with `--no-postgres` → `DATABASE_URL` prompt/flag
- [ ] MinIO: pinned-source binary from the release, own user and data dir, listens on localhost only, buckets provisioned with `manage.py provision_storage`. Skipped with `--no-minio` → `S3_*` flags or storage disabled
- [ ] Linux services: `mvault-web.service`, `mvault-minio.service` with hardening (`NoNewPrivileges`, `ProtectSystem`, `PrivateTmp`, …), ordered after PostgreSQL, **enabled and started by default**; unattended-friendly
- [ ] macOS: no auto-start; the `mvault` command starts/stops/restarts/reports status and tails logs for the PostgreSQL, MinIO and web processes
- [ ] `mvault` CLI (single POSIX/bash script, installed to `/usr/local/bin`): `start|stop|restart|status|logs|enable|disable|version|upgrade|backup|restore|config|admin|manage|doctor|uninstall`
- [ ] First-run bootstrap equals the container's: generated secrets (key, salt, DB/MinIO passwords), first-admin password printed once and forced to change
- [ ] `upgrade`: stop → backup (pg_dump + config) → new release → migrate → start, with rollback on failure
- [ ] Tested on Debian 12/13, Ubuntu 22.04/24.04, a RHEL-family distro (Rocky/Fedora), Raspberry Pi OS (arm64) and macOS (Apple silicon + Intel) — fresh machines and re-runs

### Phase 5 — Proxmox / community-scripts
- [ ] `ct/mvault.sh` + `install/mvault-install.sh` following the community-scripts template (Debian 13 LXC, 2 vCPU / 2 GB / 8 GB defaults, unprivileged)
- [ ] Native install = the Phase 4 Linux layout inside the LXC (PostgreSQL from apt, venv in `/opt/mvault`, MinIO release binary, systemd units, `mvault` CLI), expressed with the community-scripts helper functions; credentials in `/root/mvault.creds`; `update_script` calls `mvault upgrade`-equivalent steps
- [ ] Prompts honour `var_*` variables for unattended installs; options to use an existing PostgreSQL / S3
- [ ] Test on a real Proxmox host (amd64; arm64 where possible), including update path and backup/restore
- [ ] Prepare the submission (fork of community-scripts' dev repo, PR text, logo/metadata). **Do not open the PR without the maintainer's go-ahead.** Check acceptance criteria (popularity/stars, maintenance commitment) first.
- [ ] Until accepted: a one-liner in this repo's docs that creates the LXC with `pct` and runs `install.sh` inside it

### Phase 6 — Documentation
- [ ] `README.md`: pitch, feature list, screenshots, quick start (3 commands), install options, security model, links
- [ ] `docs/`: install (Docker AIO / external / native Linux and macOS / Proxmox), configuration reference, reverse proxy (NPM, Caddy, Traefik, nginx), backup & restore, upgrading, key management & rotation, security/threat model, architecture, FAQ, troubleshooting
- [ ] `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, issue + PR templates, `CODEOWNERS`
- [ ] Screenshots/GIF generated from the seeded demo data (no real data)

### Phase 7 — Agent guidance
- [ ] `AGENTS.md` (single source of truth for Codex/Claude/others): project map, commands, conventions, security rules (never log values, never commit secrets), release checklist
- [ ] `CLAUDE.md` importing `@AGENTS.md` plus Claude-specific notes; `.claude/` kept out of the repo unless shared on purpose

### Phase 8 — Release and homelab switch-over
- [ ] Tag `v0.4.0`, verify the GHCR multi-arch manifest and release assets, run every install path from scratch (Docker AIO, Docker external, native Linux VM, native macOS, fresh LXC)
- [ ] Switch the maintainer's homelab to `ghcr.io/orkhan/mvault:<ver>-slim` with the existing PostgreSQL/MinIO and `MVAULT_ADMIN_EMAIL` preserved
- [ ] Announce (GitHub release, r/selfhosted, awesome-selfhosted PR) once docs and CI are green

## Risks and open questions

- **MinIO upstream** is in maintenance mode / archived; pinning a source tag keeps builds reproducible but we won't get fixes. Mitigation: the app only needs S3 — document SeaweedFS/Garage as alternatives and keep the embedded store behind one provisioning script.
- **Embedding PostgreSQL** means major-version upgrades inside the image need a dump/restore step; document it and pin the major version per image line.
- **Security expectations**: a public password manager attracts scrutiny. Encryption is application-level (AES-GCM); key and salt live next to the app, so database-only leaks are covered but a full host compromise is not. State this plainly in `docs/security.md`. No independent audit yet.
- **community-scripts acceptance** is not guaranteed and may require traction first; the standalone installer keeps Proxmox users covered meanwhile.
- **Native installs vary by distro**: PostgreSQL package names/versions and service names differ (`postgresql` vs versioned units). The installer detects them and the docs list the tested matrix; unsupported distros get a clear message and the Docker path.
- **Docker disk space** on the maintainer's workstation is tight (Docker Desktop VM nearly full); multi-arch builds need pruning or a remote builder (GitHub Actions does the real builds).
