# Proxmox VE LXC

Run mVault in its own Debian LXC on Proxmox VE, **without Docker**. The helper creates the container and installs PostgreSQL, MinIO and mVault inside it using the same [native installer](native-install.md) as any Linux machine, so the layout, systemd services and the `mvault` command are identical.

> **Status:** the scripts are written and syntax-checked, but have **not yet been run on a real Proxmox host** (see [Testing](#testing)). They follow the [community-scripts](https://community-scripts.org/) framework; submission there is a separate, later step.

## Create the container

Run this on the **Proxmox host** shell (as root):

```bash
COMMUNITY_SCRIPTS_URL=https://raw.githubusercontent.com/orkhan/mvault/main/proxmox \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/proxmox/ct/mvault.sh)"
```

The framework's menu lets you accept the defaults or customise the container. Defaults: Debian 13, unprivileged, 2 vCPU, 2 GB RAM, 8 GB disk (the image also supports arm64 hosts). When it finishes you get the URL (`http://<container-ip>:8000`).

First sign-in details are in the container:

```bash
pct exec <CTID> -- cat /root/mvault.creds
```

Sign in as the administrator, change the generated password when asked, and **back up `MVAULT_ENCRYPTION_KEY` and `MVAULT_ENCRYPTION_SALT`** from `/etc/mvault/mvault.env` — without them stored values cannot be decrypted. See [Backup and restore](backup-restore.md).

Unattended installs honour the framework's `var_*` variables (for example `var_cpu`, `var_ram`, `var_disk`, `var_hostname`, `var_ctid`).

## Put a reverse proxy in front

The container serves plain HTTP on port 8000 and does not include a proxy. Terminate TLS with your own (Nginx Proxy Manager, Caddy, Traefik, …); see [Reverse proxy](reverse-proxy.md), then tell mVault its public address:

```bash
pct exec <CTID> -- mvault config set MVAULT_BASE_URL https://vault.example.com
pct exec <CTID> -- mvault restart
```

## Manage

Inside the container (`pct enter <CTID>`):

| Command | What it does |
|---|---|
| `mvault status` | Shows PostgreSQL, MinIO and the web app and the URL |
| `mvault restart` / `stop` / `start` | Controls the systemd services |
| `mvault logs [web\|minio]` | Follows the logs |
| `mvault backup` | Backs up the database and configuration to one `tar.gz` |
| `mvault doctor` | Checks the configuration |

## Update

From the Proxmox host, re-run the same one-liner inside the existing container, or directly in the container:

```bash
pct exec <CTID> -- mvault upgrade --yes
```

An update takes a backup first and rolls back if the new version does not start.

## Use your own PostgreSQL or S3 storage

By default the container gets its own PostgreSQL and MinIO. When you run the helper interactively it asks two questions ("Use an existing PostgreSQL?" and "Use existing S3-compatible storage?"); answer *Yes* and fill in the details. For unattended installs set the variables before running the one-liner (they are read by the install script, and the credentials are never echoed):

| Variable | Effect |
|---|---|
| `var_database_url` | `postgres://user:password@host:5432/dbname` — use this PostgreSQL, install none |
| `var_s3_endpoint`, `var_s3_access_key`, `var_s3_secret_key` | Use this S3-compatible storage (MinIO, Ceph, …), install no MinIO. All three are required together |
| `var_provision_buckets=yes` | Create the buckets (`mvault-icons`, `mvault-avatars`, `mvault-attachments`) if missing — needs `s3:CreateBucket` |
| `var_no_storage=yes` | Run without object storage: icons, avatars and file records are unavailable |
| `var_base_url` | Public URL, for example `https://vault.example.com` (default `http://<container-ip>:8000`) |
| `var_admin_email` | First administrator (default `admin@mvault.local`) |

```bash
var_database_url='postgres://mvault:secret@pg.lan:5432/mvault' \
var_s3_endpoint='http://minio.lan:9000' var_s3_access_key='AK' var_s3_secret_key='SK' var_provision_buckets=yes \
COMMUNITY_SCRIPTS_URL=https://raw.githubusercontent.com/orkhan/mvault/main/proxmox \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/proxmox/ct/mvault.sh)"
```

Invalid values (a non-`postgres://` URL, an endpoint without `http(s)://`, an S3 endpoint without keys) stop the install with a clear message before anything is changed. With an external PostgreSQL, backing up that database is your responsibility; `mvault backup` inside the container still saves the configuration. The container-side layout and flags are described in [Native install](native-install.md).

## Testing

What was verified: both scripts pass `shellcheck` and `bash -n`; the mapping from the `var_*` settings to installer flags is covered by `proxmox/test/args-test.sh` (run in CI); the installer was run with the flags generated for *external PostgreSQL + no object storage* on a real-systemd Debian 12 container against a throwaway PostgreSQL (status showed PostgreSQL external, storage disabled, embedded services inactive, app healthy); and the installer itself is tested separately (see [native install](native-install.md)). The interactive questions use `whiptail` and are not yet exercised on a real Proxmox host. **Not yet verified on a real Proxmox host:** container creation through the framework, systemd sandboxing inside an *unprivileged* LXC (the framework enables `nesting`, which the unit hardening needs), and the update path. If you try it, please report results in an issue.

## Submitting to community-scripts

Their contribution guide requires new scripts to be sent to their development repository first, tested on a real Proxmox instance, and reviewed; acceptance is not guaranteed and may depend on project adoption. The plan is to submit only after a real Proxmox test and once v0.4.0 has some real users; until then this page's one-liner is the supported route. The metadata sheet for that submission is in [`proxmox/SUBMISSION.md`](../proxmox/SUBMISSION.md).
