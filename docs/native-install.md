# Native install (Linux and macOS)

Install mVault **without Docker**: PostgreSQL, MinIO and the app together on the host, or any subset of them. One script, safe to re-run (a re-run is an upgrade; existing secrets are never overwritten). Downloads are verified against the release's `SHA256SUMS`, and Python comes from a pinned, checksum-verified [`uv`](https://docs.astral.sh/uv/), so your system Python does not matter.

## Install

```bash
# Linux (systemd) — as root
curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/install.sh | sudo sh

# macOS — as your user (needs Homebrew PostgreSQL, see below)
curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/install.sh | sh
```

To pass options, append `-s --`, for example:

```bash
curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/install.sh \
  | sudo sh -s -- --base-url https://vault.example.com --admin-email you@example.com
```

When it finishes it prints the URL and the **generated administrator password (shown once; you must change it at first sign-in)**. Back up `mvault.env`: it holds the encryption key and salt, and without them stored data cannot be decrypted.

### Options

| Option | Meaning |
|---|---|
| `--version X.Y.Z` | Install this release (default: latest). |
| `--prefix DIR` | Linux: application directory (default `/opt/mvault`). macOS: base directory for everything. |
| `--bin-dir DIR` | Where the `mvault` command goes. |
| `--port N`, `--bind ADDR` | Web port (default 8000) and bind address (Linux `0.0.0.0`, macOS `127.0.0.1`). |
| `--base-url URL` | Public URL, for example `https://vault.example.com` (recommended behind a reverse proxy). |
| `--admin-email EMAIL` | First administrator (default `admin@mvault.local`). |
| `--no-postgres`, `--database-url URL` | Use your own PostgreSQL (`postgres://user:pass@host:5432/db`). |
| `--no-minio`, `--s3-endpoint URL --s3-access-key K --s3-secret-key S [--provision-buckets]` | Use your own S3-compatible storage. |
| `--no-storage` | Run without object storage (icons, avatars and file records are disabled). |
| `--no-start`, `--no-systemd` | Install without starting services / without installing units. |
| `--upgrade`, `--uninstall [--purge]`, `--yes` | Upgrade, remove (data is kept unless `--purge`), never ask questions. |

The installer asks nothing when it is not attached to a terminal; use `--yes` for the same behaviour interactively.

## What gets installed

| | Linux (system-wide) | macOS (per user) |
|---|---|---|
| Application | `/opt/mvault/releases/<version>` with a `current` symlink | `~/Library/Application Support/mvault/app` |
| Configuration | `/etc/mvault/mvault.env`, `minio.env` (`root:mvault`, mode 0640) | `…/mvault/mvault.env` (0600) |
| Data | `/var/lib/mvault` (MinIO data, backups, logs) | `…/mvault/data` |
| PostgreSQL | Distro packages (`apt`/`dnf`), own role and database `mvault`, localhost only | Homebrew `postgresql@17`, a private cluster on port 54329 |
| MinIO | Pinned-source binary from the release, localhost only | Same |
| Services | `mvault-web.service`, `mvault-minio.service` (and `postgresql`), **enabled at boot and started**, run as user `mvault` with systemd sandboxing | Plain processes managed by the `mvault` command, **no auto-start** |

On macOS install PostgreSQL first with `brew install postgresql@17` (or use `--no-postgres --database-url …`). **Supported:** Debian/Ubuntu (`apt`) and Fedora/RHEL-like (`dnf`) with systemd. Rocky/Alma and Raspberry Pi OS are expected to work but untested. Other distributions are not supported: the installer stops with a clear message, and you can use the Docker images or `--no-postgres --database-url …` with your own PostgreSQL.

## The `mvault` command

```text
mvault start|stop|restart [postgres|minio|web]   control services
mvault status                                    components, health and URL
mvault logs [web|minio|postgres] [-f] [-n N]     show logs
mvault enable | disable                          start at boot (Linux/systemd only)
mvault config [show|path|edit|get K|set K V]     view or change mvault.env
mvault admin reset-password [email]              set a new temporary password
mvault manage <django command...>                run manage.py (check_config, shell, ...)
mvault backup [--with-minio] [-o FILE]           database + configuration archive
mvault restore FILE [--with-config] [--yes]      restore a backup archive
mvault upgrade [--version X.Y.Z] [--yes]         backup, install a new release, roll back on failure
mvault doctor                                    check the installation
mvault uninstall [--purge] [--yes]               remove (keeps data unless --purge)
mvault version
```

On Linux the service verbs call `systemctl`; on macOS the command starts and stops the processes itself.

## Upgrade, back up, uninstall

```bash
sudo mvault upgrade          # backs up first, migrates, rolls back automatically if the new version is unhealthy
sudo mvault backup -o /root/mvault-backup.tar.gz
sudo mvault uninstall        # keeps your data; add --purge to delete it
```

`mvault restore` refuses a backup made with a different encryption key unless you pass `--with-config`. See [Backup and restore](backup-restore.md) and [Upgrading](upgrading.md).

## Behind a reverse proxy

Set the public address, then restart:

```bash
sudo mvault config set MVAULT_BASE_URL https://vault.example.com
sudo mvault restart web
```

mVault does not include a proxy; see [Reverse proxy](reverse-proxy.md).

## Tested

Verified on macOS (Apple silicon) and on real systemd in Debian 12, Ubuntu 24.04 and Fedora containers: install, reboot persistence, upgrade, rollback of a broken release, backup/restore, re-run leaving secrets unchanged, uninstall and purge, and checksum-tamper detection. The published v0.4.0 path was also run end to end as a user would: the one-liner from GitHub on a systemd Debian 12 container resolved "latest", verified the downloads, installed PostgreSQL, MinIO and the app, and `mvault status`/`doctor` reported everything healthy with all units enabled. Not yet verified on Raspberry Pi OS, Rocky/Alma, Intel Macs, macOS with a real Homebrew install, or an unprivileged Proxmox LXC (systemd sandboxing there needs the `nesting` feature); reports are welcome.
