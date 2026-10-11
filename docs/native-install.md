# Native install (Linux and macOS)

> **Coming in v0.4.0.** This page is a skeleton that records the design from [PLAN.md](../PLAN.md) (Phase 4). The installer is being written by another workstream; commands here are **not yet available** and details will be finalised when it ships.

A Docker-free installer that puts PostgreSQL, MinIO and mVault on the host, or any subset of them.

## Planned usage

```bash
curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/install.sh | sh
```

Planned flags: `--version`, `--prefix`, `--port`, `--base-url`, `--no-postgres`, `--no-minio`, `--upgrade`, `--uninstall`, `--yes`. The script is intended to be idempotent, verify downloads against `SHA256SUMS`, and never overwrite existing secrets.

## Planned layout

| | Linux | macOS |
|---|---|---|
| App | `/opt/mvault` (release tarball + managed Python 3.12 venv via `uv`) | `~/Library/Application Support/mvault/app` |
| Config / secrets | `/etc/mvault/mvault.env` (0640 `root:mvault`) | `<support dir>/mvault.env` (0600) |
| PostgreSQL | Distro package, own database `mvault`, localhost only | Homebrew `postgresql@17` (bundled fallback) |
| MinIO | Pinned-source binary, data `/var/lib/mvault/minio`, localhost only | Same binary, data in the support dir |
| Services | `mvault-web.service`, `mvault-minio.service` (+ `postgresql.service`), **enabled and started by default**, run as user `mvault` | Processes started by the CLI; no auto-start |

## Planned `mvault` command

`start`, `stop`, `restart`, `status`, `logs`, `enable`, `disable`, `version`, `upgrade`, `backup`, `restore`, `config`, `admin`, `manage`, `doctor`, `uninstall`. On Linux the service verbs call `systemctl`; on macOS `start/stop/restart/status/logs` manage the PostgreSQL, MinIO and web processes directly.

## Until then

Use [Docker](installation.md) or [build from source](development.md). Configuration is identical: see the [configuration reference](configuration.md).
