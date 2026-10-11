# mVault open-source plan

Goal: publish mVault as an open-source, self-hostable family vault that installs three ways: an all-in-one multi-arch Docker image, a slim Docker image for people who already run PostgreSQL and MinIO/S3, and a Proxmox LXC helper script (targeting community-scripts.org). Repository: `github.com/orkhan/mvault` (public, MIT).

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
| Proxmox | Native install in a Debian LXC (no Docker inside) | community-scripts convention: `ct/mvault.sh` + `install/mvault-install.sh`, systemd services, `update_script`. |
| First public version | v0.4.0 | 0.3.0 is the current private homelab release; 0.4.0 adds packaging/config changes. |

## Deployment modes (one codebase)

| Component | Embedded (default in all-in-one image) | External (slim image, or all-in-one with overrides) |
|---|---|---|
| PostgreSQL | Started by s6 on `127.0.0.1:5432`, data in `/data/postgres`, random password in `/data/config` | Set `DB_HOST` (or `DATABASE_URL`) → embedded PostgreSQL is skipped |
| Object storage | MinIO on `127.0.0.1:9000`, data in `/data/minio`, root creds generated on first start | Set `S3_ENDPOINT_URL` (+ keys, bucket names) → embedded MinIO is skipped |
| Secrets | Generated once into `/data/config/secrets.env` if not supplied (Django key, encryption key + salt, admin password) | Supply via env / Docker secrets (`*_FILE` variants) |

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
- [ ] `Dockerfile` with targets `slim` and `aio` (Debian bookworm-slim, Python 3.12, non-root app user)
- [ ] Go build stage for MinIO (pinned tag + commit, cross-compiled per `TARGETARCH`), licenses copied to `/licenses`
- [ ] s6-overlay services: `postgres`, `minio`, `bootstrap` (secret generation, initdb, bucket provisioning), `migrate`, `web` (gunicorn)
- [ ] Healthcheck, graceful shutdown, `/data` volume, single exposed port 8000
- [ ] `compose.yaml` (all-in-one), `compose.external.yaml` (existing PostgreSQL + MinIO), `compose.dev.yaml`
- [ ] `scripts/provision-minio.sh` (idempotent buckets/policy/service user for people with their own MinIO)
- [ ] Local build + smoke test on amd64 and arm64 (QEMU), size/CVE scan (trivy)

### Phase 3 — CI/CD (GitHub Actions)
- [ ] `ci.yml`: lint (ruff), tests against PostgreSQL service, `makemigrations --check`, `pip-audit`, hadolint, shellcheck
- [ ] `docker.yml`: buildx multi-arch, push to GHCR on tags and `main` (`edge`), provenance + SBOM attestations, trivy scan
- [ ] `release.yml`: on `v*` tag → GitHub release with notes, source tarball, per-arch MinIO binaries (for the Proxmox installer)
- [ ] Dependabot (pip, docker, actions), CodeQL, secret scanning + push protection, branch protection on `main`

### Phase 4 — Proxmox / community-scripts
- [ ] `ct/mvault.sh` + `install/mvault-install.sh` following the community-scripts template (Debian 13 LXC, 2 vCPU / 2 GB / 8 GB defaults, unprivileged)
- [ ] Native install: PostgreSQL from apt, Python venv in `/opt/mvault`, MinIO release binary (optional), systemd units, credentials in `/root/mvault.creds`, `update_script`
- [ ] Prompts honour `var_*` variables for unattended installs; options to use an existing PostgreSQL / S3
- [ ] Test on a real Proxmox host (amd64; arm64 where possible), including update path and backup/restore
- [ ] Prepare the submission (fork of community-scripts' dev repo, PR text, logo/metadata). **Do not open the PR without the maintainer's go-ahead.** Check acceptance criteria (popularity/stars, maintenance commitment) first.
- [ ] Until accepted: `install.sh` one-liner hosted in this repo that runs the same scripts

### Phase 5 — Documentation
- [ ] `README.md`: pitch, feature list, screenshots, quick start (3 commands), install options, security model, links
- [ ] `docs/`: install (Docker AIO / external / Proxmox), configuration reference, reverse proxy (NPM, Caddy, Traefik, nginx), backup & restore, upgrading, key management & rotation, security/threat model, architecture, FAQ, troubleshooting
- [ ] `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, issue + PR templates, `CODEOWNERS`
- [ ] Screenshots/GIF generated from the seeded demo data (no real data)

### Phase 6 — Agent guidance
- [ ] `AGENTS.md` (single source of truth for Codex/Claude/others): project map, commands, conventions, security rules (never log values, never commit secrets), release checklist
- [ ] `CLAUDE.md` importing `@AGENTS.md` plus Claude-specific notes; `.claude/` kept out of the repo unless shared on purpose

### Phase 7 — Release and homelab switch-over
- [ ] Tag `v0.4.0`, verify GHCR multi-arch manifest, run the install paths from scratch (fresh VM, fresh LXC)
- [ ] Switch the maintainer's homelab to `ghcr.io/orkhan/mvault:<ver>-slim` with the existing PostgreSQL/MinIO and `MVAULT_ADMIN_EMAIL` preserved
- [ ] Announce (GitHub release, r/selfhosted, awesome-selfhosted PR) once docs and CI are green

## Risks and open questions

- **MinIO upstream** is in maintenance mode / archived; pinning a source tag keeps builds reproducible but we won't get fixes. Mitigation: the app only needs S3 — document SeaweedFS/Garage as alternatives and keep the embedded store behind one provisioning script.
- **Embedding PostgreSQL** means major-version upgrades inside the image need a dump/restore step; document it and pin the major version per image line.
- **Security expectations**: a public password manager attracts scrutiny. Encryption is application-level (AES-GCM); key and salt live next to the app, so database-only leaks are covered but a full host compromise is not. State this plainly in `docs/security.md`. No independent audit yet.
- **community-scripts acceptance** is not guaranteed and may require traction first; the standalone installer keeps Proxmox users covered meanwhile.
- **Docker disk space** on the maintainer's workstation is tight (Docker Desktop VM nearly full); multi-arch builds need pruning or a remote builder (GitHub Actions does the real builds).
