# community-scripts submission sheet

Prepared for a future submission to the community-scripts development repository. **Do not submit until** the scripts have been tested on a real Proxmox host and the maintainer agrees; check their current acceptance criteria first.

| Field | Value |
|---|---|
| Name | mVault |
| Slug | `mvault` |
| Description | Self-hosted family vault for passwords, bank cards, secrets, JSON and files, with encryption at rest. |
| Website / source | https://github.com/orkhan/mvault |
| License | MIT |
| Tags | `password-manager`, `vault`, `security` |
| Default resources | 2 vCPU, 2048 MB RAM, 8 GB disk, Debian 13, unprivileged, arm64 supported |
| Port | 8000 (HTTP; use a TLS reverse proxy) |
| Credentials | Generated at install; saved to `/root/mvault.creds`; password change forced at first sign-in |
| Install method | Native: PostgreSQL (apt), uv-managed Python 3.12 venv, MinIO (pinned source build from the release), systemd units, `mvault` CLI |
| Update method | `mvault upgrade --yes` (backup, migrate, rollback on failure) |
| Notes | Back up `/etc/mvault/mvault.env` (encryption key and salt). Optional external PostgreSQL / S3 via the installer's flags. |
| Files | `proxmox/ct/mvault.sh`, `proxmox/install/mvault-install.sh` |
| Logo | to be added (SVG/PNG) |
